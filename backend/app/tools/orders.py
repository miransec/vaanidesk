"""Order-related allow-listed tools."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.models import Order, OrderItem, OrderStatus, User


class OrderRefInput(BaseModel):
    order_ref: str = Field(min_length=3, max_length=32)

    @field_validator("order_ref")
    @classmethod
    def normalize_ref(cls, value: str) -> str:
        return value.strip().upper()


class UpdateAddressInput(OrderRefInput):
    new_address: str = Field(min_length=10, max_length=500)

    @field_validator("new_address")
    @classmethod
    def clean_address(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if len(cleaned) < 10:
            raise ValueError("address must be at least 10 characters")
        return cleaned


async def get_owned_order(
    *,
    db: AsyncSession,
    user: User,
    order_ref: str,
    with_items: bool = False,
) -> Order:
    """Lookup by authenticated user + public order reference only."""
    stmt = select(Order).where(Order.user_id == user.id, Order.order_number == order_ref.upper())
    if with_items:
        stmt = stmt.options(selectinload(Order.items).selectinload(OrderItem.product))
    order = (await db.execute(stmt)).scalar_one_or_none()
    if order is None:
        raise AppError(
            code="order_not_found",
            message="Order not found for this user.",
            status_code=404,
        )
    return order


def cancellation_eligible(status: OrderStatus) -> tuple[bool, str]:
    if status in {OrderStatus.PENDING, OrderStatus.CONFIRMED}:
        return True, f"status_{status.value}_allows_cancellation"
    if status == OrderStatus.SHIPPED:
        return False, "already_shipped"
    if status == OrderStatus.DELIVERED:
        return False, "already_delivered"
    if status == OrderStatus.CANCELLED:
        return False, "already_cancelled"
    if status == OrderStatus.REFUNDED:
        return False, "already_refunded"
    return False, "status_not_cancellable"


def address_change_allowed(status: OrderStatus) -> tuple[bool, str]:
    if status in {OrderStatus.PENDING, OrderStatus.CONFIRMED}:
        return True, f"status_{status.value}_allows_address_update"
    return False, f"status_{status.value}_blocks_address_update"


async def handle_get_order_status(
    *, db: AsyncSession, user: User, args: OrderRefInput, **_: Any
) -> dict[str, Any]:
    order = await get_owned_order(db=db, user=user, order_ref=args.order_ref)
    return {
        "order_ref": order.order_number,
        "status": order.status.value,
        "delivery_address": order.delivery_address,
        "currency": order.currency,
        "total_amount": str(order.total_amount),
    }


async def handle_get_order_details(
    *, db: AsyncSession, user: User, args: OrderRefInput, **_: Any
) -> dict[str, Any]:
    order = await get_owned_order(db=db, user=user, order_ref=args.order_ref, with_items=True)
    items = [
        {
            "sku": item.product.sku if item.product else None,
            "name": item.product.name if item.product else None,
            "quantity": item.quantity,
            "unit_price": str(item.unit_price),
        }
        for item in order.items
    ]
    return {
        "order_ref": order.order_number,
        "status": order.status.value,
        "delivery_address": order.delivery_address,
        "currency": order.currency,
        "total_amount": str(order.total_amount),
        "items": items,
    }


async def handle_check_cancellation_eligibility(
    *, db: AsyncSession, user: User, args: OrderRefInput, **_: Any
) -> dict[str, Any]:
    order = await get_owned_order(db=db, user=user, order_ref=args.order_ref)
    eligible, reason = cancellation_eligible(order.status)
    return {
        "order_ref": order.order_number,
        "status": order.status.value,
        "eligible": eligible,
        "reason": reason,
    }


async def handle_cancel_order(
    *, db: AsyncSession, user: User, args: OrderRefInput, **_: Any
) -> dict[str, Any]:
    order = await get_owned_order(db=db, user=user, order_ref=args.order_ref)
    eligible, reason = cancellation_eligible(order.status)
    if not eligible:
        raise AppError(
            code="cancellation_not_allowed",
            message=f"Order cannot be cancelled ({reason}).",
            status_code=400,
            details={"reason": reason, "status": order.status.value},
        )
    order.status = OrderStatus.CANCELLED
    await db.flush()
    return {
        "order_ref": order.order_number,
        "status": order.status.value,
        "cancelled": True,
        "reason": reason,
    }


async def handle_update_delivery_address(
    *, db: AsyncSession, user: User, args: UpdateAddressInput, **_: Any
) -> dict[str, Any]:
    order = await get_owned_order(db=db, user=user, order_ref=args.order_ref)
    allowed, reason = address_change_allowed(order.status)
    if not allowed:
        raise AppError(
            code="address_update_not_allowed",
            message=f"Address cannot be updated ({reason}).",
            status_code=400,
            details={"reason": reason, "status": order.status.value},
        )
    order.delivery_address = args.new_address
    await db.flush()
    return {
        "order_ref": order.order_number,
        "status": order.status.value,
        "delivery_address": order.delivery_address,
        "updated": True,
        "reason": reason,
    }


async def assert_order_owned_by(*, db: AsyncSession, user_id: UUID, order_ref: str) -> bool:
    stmt = select(Order.id).where(Order.user_id == user_id, Order.order_number == order_ref.upper())
    return (await db.execute(stmt)).scalar_one_or_none() is not None
