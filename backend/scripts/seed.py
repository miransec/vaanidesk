from __future__ import annotations

import argparse
import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, select, text

# Allow running as `python -m scripts.seed` from backend/
ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.demo_personas import (  # noqa: E402
    CURATED_DEMO_ORDERS,
    PRODUCT_DEMO_KEYS,
    PRODUCT_DEMO_PERSONAS,
    TEST_COMPAT_PERSONAS,
)
from app.database.session import SessionLocal, get_engine  # noqa: E402
from app.models import (  # noqa: E402
    Conversation,
    Message,
    MessageRole,
    Order,
    OrderItem,
    OrderStatus,
    Product,
    User,
)

DEMO_USERS = [
    {
        "id": UUID(row["id"]),
        "email": row["email"],
        "display_name": row["display_name"],
        "demo_key": row["demo_key"],
    }
    for row in [*PRODUCT_DEMO_PERSONAS, *TEST_COMPAT_PERSONAS]
]

# Bulk filler statuses (curated matrix is authoritative for product demos).
STATUSES = [
    OrderStatus.PENDING,
    OrderStatus.CONFIRMED,
    OrderStatus.SHIPPED,
    OrderStatus.DELIVERED,
    OrderStatus.CANCELLED,
    OrderStatus.REFUNDED,
]


async def seed(*, force: bool = False) -> dict[str, int | str | list[str] | dict[str, str]]:
    products_path = REPO / "sample_data" / "products" / "products.json"
    product_rows = json.loads(products_path.read_text(encoding="utf-8"))
    if len(product_rows) < 25:
        raise RuntimeError("Expected at least 25 products in sample_data/products/products.json")

    async with SessionLocal() as db:
        if force:
            await db.execute(
                text(
                    "TRUNCATE idempotency_records, tool_executions, agent_traces, "
                    "support_tickets, order_items, orders, messages, conversations, "
                    "products, users CASCADE"
                )
            )
            await db.commit()

        users_by_key = await _ensure_users(db)
        products = await _ensure_products(db, product_rows)
        curated = await _ensure_curated_orders(db, users_by_key, products)
        filler_created = await _ensure_filler_orders(db, list(users_by_key.values()), products)
        await _ensure_welcome_chats(db, list(users_by_key.values()))
        await db.commit()

        counts = await _counts(db)
        return {
            **counts,
            "seeded": 1,
            "mode": "applied" if force or filler_created or curated["created"] else "synced",
            "curated_orders": curated["matrix"],
            "curated_orders_created": curated["created"],
            "curated_orders_updated": curated["updated"],
            "filler_orders_created": filler_created,
            "product_demo_keys": sorted(PRODUCT_DEMO_KEYS),
        }


async def _ensure_users(db) -> dict[str, User]:
    users_by_key: dict[str, User] = {}
    for row in DEMO_USERS:
        existing = (
            await db.execute(select(User).where(User.demo_key == row["demo_key"]))
        ).scalar_one_or_none()
        if existing:
            existing.email = row["email"]
            existing.display_name = row["display_name"]
            users_by_key[row["demo_key"]] = existing
            continue
        # Prefer stable UUID from persona catalog when inserting fresh.
        by_id = (await db.execute(select(User).where(User.id == row["id"]))).scalar_one_or_none()
        if by_id is not None:
            by_id.email = row["email"]
            by_id.display_name = row["display_name"]
            by_id.demo_key = row["demo_key"]
            users_by_key[row["demo_key"]] = by_id
            continue
        user = User(**row)
        db.add(user)
        users_by_key[row["demo_key"]] = user
    await db.flush()
    return users_by_key


async def _ensure_products(db, product_rows: list[dict]) -> list[Product]:
    products: list[Product] = []
    for row in product_rows:
        existing = (
            await db.execute(select(Product).where(Product.sku == row["sku"]))
        ).scalar_one_or_none()
        if existing:
            products.append(existing)
            continue
        product = Product(
            id=uuid5(NAMESPACE_URL, f"vaanidesk:product:{row['sku']}"),
            sku=row["sku"],
            name=row["name"],
            description=row["description"],
            price=Decimal(row["price"]),
            currency="INR",
        )
        db.add(product)
        products.append(product)
    await db.flush()
    return products


async def _ensure_curated_orders(
    db, users_by_key: dict[str, User], products: list[Product]
) -> dict[str, int | dict[str, str]]:
    created = 0
    updated = 0
    matrix: dict[str, str] = {}
    for spec in CURATED_DEMO_ORDERS:
        user = users_by_key[spec["demo_key"]]
        number = spec["order_number"]
        status = OrderStatus(spec["status"])
        product = products[int(spec["sku_index"]) % len(products)]
        qty = 1
        total = (product.price * qty).quantize(Decimal("0.01"))
        address = f"{user.display_name}, Demo Address {number}, Mumbai, MH 400001"
        order_id = uuid5(NAMESPACE_URL, f"vaanidesk:order:{number}")
        existing = (
            await db.execute(select(Order).where(Order.order_number == number))
        ).scalar_one_or_none()
        if existing is None:
            existing = (
                await db.execute(select(Order).where(Order.id == order_id))
            ).scalar_one_or_none()
        if existing is None:
            order = Order(
                id=order_id,
                user_id=user.id,
                order_number=number,
                status=status,
                total_amount=total,
                currency="INR",
                delivery_address=address,
            )
            db.add(order)
            await db.flush()
            db.add(
                OrderItem(
                    id=uuid5(NAMESPACE_URL, f"vaanidesk:order-item:{number}"),
                    order_id=order.id,
                    product_id=product.id,
                    quantity=qty,
                    unit_price=product.price,
                )
            )
            created += 1
        else:
            existing.user_id = user.id
            existing.status = status
            existing.total_amount = total
            existing.currency = "INR"
            existing.delivery_address = address
            updated += 1
        matrix[number] = f"{spec['demo_key']}:{status.value}"
    await db.flush()
    return {"created": created, "updated": updated, "matrix": matrix}


async def _ensure_filler_orders(db, users: list[User], products: list[Product]) -> int:
    """Keep a bulk demo catalog (>=50 orders) without touching curated numbers."""
    curated_numbers = {spec["order_number"] for spec in CURATED_DEMO_ORDERS}
    existing_order_count = (await db.execute(select(func.count()).select_from(Order))).scalar_one()
    created = 0
    next_ref = 10100
    while existing_order_count + created < 50:
        number = f"VD-{next_ref}"
        next_ref += 1
        if number in curated_numbers:
            continue
        exists = (
            await db.execute(select(Order).where(Order.order_number == number))
        ).scalar_one_or_none()
        if exists:
            continue
        user = users[created % len(users)]
        product = products[created % len(products)]
        qty = (created % 3) + 1
        status = STATUSES[created % len(STATUSES)]
        total = (product.price * qty).quantize(Decimal("0.01"))
        address = f"{user.display_name}, Demo Address {next_ref - 1}, Mumbai, MH 400001"
        order = Order(
            id=uuid5(NAMESPACE_URL, f"vaanidesk:order:{number}"),
            user_id=user.id,
            order_number=number,
            status=status,
            total_amount=total,
            currency="INR",
            delivery_address=address,
        )
        db.add(order)
        await db.flush()
        db.add(
            OrderItem(
                id=uuid5(NAMESPACE_URL, f"vaanidesk:order-item:{number}"),
                order_id=order.id,
                product_id=product.id,
                quantity=qty,
                unit_price=product.price,
            )
        )
        created += 1
    return created


async def _ensure_welcome_chats(db, users: list[User]) -> None:
    for idx, user in enumerate(users):
        title = f"Welcome chat — {user.display_name}"
        conv_id = uuid5(NAMESPACE_URL, f"vaanidesk:conversation:{user.demo_key}")
        existing_conv = (
            await db.execute(select(Conversation).where(Conversation.id == conv_id))
        ).scalar_one_or_none()
        if existing_conv:
            existing_conv.title = title
            continue
        existing_by_title = (
            await db.execute(
                select(Conversation).where(
                    Conversation.user_id == user.id, Conversation.title == title
                )
            )
        ).scalar_one_or_none()
        if existing_by_title:
            continue
        conv = Conversation(id=conv_id, user_id=user.id, title=title)
        db.add(conv)
        await db.flush()
        samples = [
            (MessageRole.USER, ["Hello", "Namaste", "mera order kahan hai"][idx % 3]),
            (
                MessageRole.ASSISTANT,
                "Hi — I'm VaaniDesk Support. How can I help you today?",
            ),
        ]
        for role, content in samples:
            db.add(
                Message(
                    conversation_id=conv.id,
                    role=role,
                    content=content,
                    request_id="seed",
                    provider_metadata={"is_mock": True, "provider": "workflow-heuristic"}
                    if role == MessageRole.ASSISTANT
                    else None,
                )
            )


async def _counts(db) -> dict[str, int]:
    return {
        "users": (await db.execute(select(func.count()).select_from(User))).scalar_one(),
        "products": (await db.execute(select(func.count()).select_from(Product))).scalar_one(),
        "orders": (await db.execute(select(func.count()).select_from(Order))).scalar_one(),
        "conversations": (
            await db.execute(select(func.count()).select_from(Conversation))
        ).scalar_one(),
        "messages": (await db.execute(select(func.count()).select_from(Message))).scalar_one(),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Idempotent VaaniDesk sample-data seed")
    parser.add_argument("--force", action="store_true", help="Truncate and reseed")
    args = parser.parse_args()
    result = await seed(force=args.force)
    print(json.dumps(result, indent=2))
    eng = get_engine()
    await eng.dispose()


if __name__ == "__main__":
    asyncio.run(main())
