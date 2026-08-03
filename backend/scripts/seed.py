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
        "id": UUID("11111111-1111-1111-1111-111111111111"),
        "email": "anya.mehta@example.com",
        "display_name": "Anya Mehta",
        "demo_key": "demo-anya",
    },
    {
        "id": UUID("22222222-2222-2222-2222-222222222222"),
        "email": "rahul.nair@example.com",
        "display_name": "Rahul Nair",
        "demo_key": "demo-rahul",
    },
    {
        "id": UUID("33333333-3333-3333-3333-333333333333"),
        "email": "priya.deshmukh@example.com",
        "display_name": "Priya Deshmukh",
        "demo_key": "demo-priya",
    },
    {
        "id": UUID("44444444-4444-4444-4444-444444444444"),
        "email": "arjun.kapoor@example.com",
        "display_name": "Arjun Kapoor",
        "demo_key": "demo-arjun",
    },
]

STATUSES = [
    OrderStatus.PENDING,
    OrderStatus.CONFIRMED,
    OrderStatus.SHIPPED,
    OrderStatus.DELIVERED,
    OrderStatus.CANCELLED,
    OrderStatus.REFUNDED,
]


async def seed(*, force: bool = False) -> dict[str, int]:
    products_path = REPO / "sample_data" / "products" / "products.json"
    product_rows = json.loads(products_path.read_text(encoding="utf-8"))
    if len(product_rows) < 25:
        raise RuntimeError("Expected at least 25 products in sample_data/products/products.json")

    async with SessionLocal() as db:
        existing_users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
        if existing_users and not force:
            # Idempotent path: ensure counts, skip recreating everything.
            counts = await _counts(db)
            if counts["users"] >= 4 and counts["products"] >= 25 and counts["orders"] >= 50:
                return {**counts, "seeded": 0, "mode": "already_present"}

        if force:
            await db.execute(
                text(
                    "TRUNCATE order_items, orders, messages, conversations, products, users CASCADE"
                )
            )
            await db.commit()

        # Users (upsert by demo_key)
        users: list[User] = []
        for row in DEMO_USERS:
            existing = (
                await db.execute(select(User).where(User.demo_key == row["demo_key"]))
            ).scalar_one_or_none()
            if existing:
                users.append(existing)
                continue
            user = User(**row)
            db.add(user)
            users.append(user)
        await db.flush()

        # Products (upsert by sku)
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

        # Orders — create until 50 unique order_numbers exist
        existing_order_count = (
            await db.execute(select(func.count()).select_from(Order))
        ).scalar_one()
        created_orders = 0
        order_number = 8300
        while existing_order_count + created_orders < 50:
            number = str(order_number)
            order_number += 1
            exists = (
                await db.execute(select(Order).where(Order.order_number == number))
            ).scalar_one_or_none()
            if exists:
                continue
            user = users[created_orders % len(users)]
            product = products[created_orders % len(products)]
            qty = (created_orders % 3) + 1
            status = STATUSES[created_orders % len(STATUSES)]
            total = (product.price * qty).quantize(Decimal("0.01"))
            order = Order(
                id=uuid5(NAMESPACE_URL, f"vaanidesk:order:{number}"),
                user_id=user.id,
                order_number=number,
                status=status,
                total_amount=total,
                currency="INR",
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
            created_orders += 1

        # Sample conversations/messages if missing
        for idx, user in enumerate(users):
            title = f"Welcome chat — {user.display_name}"
            existing_conv = (
                await db.execute(
                    select(Conversation).where(
                        Conversation.user_id == user.id, Conversation.title == title
                    )
                )
            ).scalar_one_or_none()
            if existing_conv:
                continue
            conv = Conversation(
                id=uuid5(NAMESPACE_URL, f"vaanidesk:conversation:{user.demo_key}"),
                user_id=user.id,
                title=title,
            )
            db.add(conv)
            await db.flush()
            samples = [
                (
                    MessageRole.USER,
                    ["Hello", "Namaste", "mera order kahan hai", "माझी ऑर्डर कुठे आहे"][idx],
                ),
                (
                    MessageRole.ASSISTANT,
                    "Welcome to VaaniDesk Phase 1 mock chat. "
                    "(Mock provider — not a production model.)",
                ),
            ]
            for role, content in samples:
                db.add(
                    Message(
                        conversation_id=conv.id,
                        role=role,
                        content=content,
                        request_id="seed",
                        provider_metadata={"is_mock": True, "provider": "mock"}
                        if role == MessageRole.ASSISTANT
                        else None,
                    )
                )

        await db.commit()
        counts = await _counts(db)
        return {**counts, "seeded": 1, "mode": "applied", "orders_created": created_orders}


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
