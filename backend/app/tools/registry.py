"""Strict allow-listed tool registry."""

from __future__ import annotations

from app.core.errors import AppError
from app.models import ToolRiskLevel
from app.tools.base import ToolDefinition
from app.tools.orders import (
    OrderRefInput,
    UpdateAddressInput,
    handle_cancel_order,
    handle_check_cancellation_eligibility,
    handle_get_order_details,
    handle_get_order_status,
    handle_update_delivery_address,
)
from app.tools.tickets import (
    CreateTicketInput,
    TicketRefInput,
    TransferHumanInput,
    handle_create_support_ticket,
    handle_get_support_ticket_status,
    handle_transfer_to_human,
)

_REGISTRY: dict[str, ToolDefinition] = {
    "get_order_status": ToolDefinition(
        name="get_order_status",
        description="Return status for an owned order by public reference.",
        input_model=OrderRefInput,
        risk_level=ToolRiskLevel.LOW,
        requires_confirmation=False,
        supports_idempotency=False,
        handler=handle_get_order_status,
    ),
    "get_order_details": ToolDefinition(
        name="get_order_details",
        description="Return safe order details for an owned order.",
        input_model=OrderRefInput,
        risk_level=ToolRiskLevel.MODERATE,
        requires_confirmation=False,
        supports_idempotency=False,
        handler=handle_get_order_details,
    ),
    "update_delivery_address": ToolDefinition(
        name="update_delivery_address",
        description="Update delivery address for an eligible owned order.",
        input_model=UpdateAddressInput,
        risk_level=ToolRiskLevel.HIGH,
        requires_confirmation=True,
        supports_idempotency=True,
        handler=handle_update_delivery_address,
    ),
    "check_cancellation_eligibility": ToolDefinition(
        name="check_cancellation_eligibility",
        description="Deterministic cancellation eligibility for an owned order.",
        input_model=OrderRefInput,
        risk_level=ToolRiskLevel.LOW,
        requires_confirmation=False,
        supports_idempotency=False,
        handler=handle_check_cancellation_eligibility,
    ),
    "cancel_order": ToolDefinition(
        name="cancel_order",
        description="Cancel an eligible owned order after confirmation.",
        input_model=OrderRefInput,
        risk_level=ToolRiskLevel.HIGH,
        requires_confirmation=True,
        supports_idempotency=True,
        handler=handle_cancel_order,
    ),
    "create_support_ticket": ToolDefinition(
        name="create_support_ticket",
        description="Create a support ticket for the authenticated user.",
        input_model=CreateTicketInput,
        risk_level=ToolRiskLevel.MODERATE,
        requires_confirmation=False,
        supports_idempotency=True,
        handler=handle_create_support_ticket,
    ),
    "get_support_ticket_status": ToolDefinition(
        name="get_support_ticket_status",
        description="Return status for an owned support ticket.",
        input_model=TicketRefInput,
        risk_level=ToolRiskLevel.LOW,
        requires_confirmation=False,
        supports_idempotency=False,
        handler=handle_get_support_ticket_status,
    ),
    "transfer_to_human": ToolDefinition(
        name="transfer_to_human",
        description="Queue a human handoff ticket (demo — no live agent).",
        input_model=TransferHumanInput,
        risk_level=ToolRiskLevel.MODERATE,
        requires_confirmation=False,
        supports_idempotency=True,
        handler=handle_transfer_to_human,
    ),
}


def get_tool(name: str) -> ToolDefinition:
    tool = _REGISTRY.get(name)
    if tool is None:
        raise AppError(
            code="tool_not_registered",
            message=f"Tool '{name}' is not in the allow-list.",
            status_code=400,
        )
    return tool


def list_tools() -> list[ToolDefinition]:
    return list(_REGISTRY.values())


def is_registered(name: str) -> bool:
    return name in _REGISTRY
