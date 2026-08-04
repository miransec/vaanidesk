"""Curated product-demo personas (not auth/test fixtures)."""

from __future__ import annotations

# Stable demo_key values used by automated tests and the product demo UI.
# Only these identities are returned by GET /api/v1/demo-users.
#
# Historical note: Aarav Sharma keeps the internal key ``demo-anya``.
# That key shipped in v1.0.0 tests, restricted-doc allowlists, docs, and
# X-Demo-User-Key fixtures. Renaming would break published compatibility.
# Customer UI never displays the key — only display_name + email.
PRODUCT_DEMO_KEYS: frozenset[str] = frozenset(
    {
        "demo-anya",  # Aarav Sharma — primary customer demo (historical key)
        "demo-rahul",  # Rahul Verma — cross-user AuthZ demo
        "demo-meera",  # Meera Patel — delivered / refund-friendly demo
    }
)

# Extra seeded identities retained for automated tests (not shown in product chat).
TEST_COMPAT_DEMO_KEYS: frozenset[str] = frozenset({"demo-priya", "demo-arjun"})

# Display metadata for seed + docs. Keys must stay stable for X-Demo-User-Key tests.
PRODUCT_DEMO_PERSONAS: list[dict[str, str]] = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "aarav.demo@example.com",
        "display_name": "Aarav Sharma",
        "demo_key": "demo-anya",
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "email": "rahul.demo@example.com",
        "display_name": "Rahul Verma",
        "demo_key": "demo-rahul",
    },
    {
        "id": "55555555-5555-5555-5555-555555555555",
        "email": "meera.demo@example.com",
        "display_name": "Meera Patel",
        "demo_key": "demo-meera",
    },
]

TEST_COMPAT_PERSONAS: list[dict[str, str]] = [
    {
        "id": "33333333-3333-3333-3333-333333333333",
        "email": "priya.demo@example.com",
        "display_name": "Priya Deshmukh",
        "demo_key": "demo-priya",
    },
    {
        "id": "44444444-4444-4444-4444-444444444444",
        "email": "arjun.demo@example.com",
        "display_name": "Arjun Kapoor",
        "demo_key": "demo-arjun",
    },
]

# Deterministic curated orders for product demos (upserted on every seed).
# Status values must match OrderStatus enum names (lowercase).
CURATED_DEMO_ORDERS: list[dict[str, str]] = [
    {
        "demo_key": "demo-anya",
        "order_number": "VD-10021",
        "status": "shipped",
        "sku_index": "0",
        "note": "Aarav active / out-for-delivery style order",
    },
    {
        "demo_key": "demo-anya",
        "order_number": "VD-10022",
        "status": "pending",
        "sku_index": "1",
        "note": "Aarav cancellable order",
    },
    {
        "demo_key": "demo-anya",
        "order_number": "VD-10023",
        "status": "delivered",
        "sku_index": "2",
        "note": "Aarav delivered order",
    },
    {
        "demo_key": "demo-rahul",
        "order_number": "VD-10031",
        "status": "confirmed",
        "sku_index": "3",
        "note": "Rahul distinct order for cross-user AuthZ demos",
    },
    {
        "demo_key": "demo-rahul",
        "order_number": "VD-10032",
        "status": "shipped",
        "sku_index": "4",
        "note": "Rahul second active order",
    },
    {
        "demo_key": "demo-meera",
        "order_number": "VD-10041",
        "status": "delivered",
        "sku_index": "5",
        "note": "Meera delivered / refund-friendly scenario",
    },
    {
        "demo_key": "demo-meera",
        "order_number": "VD-10042",
        "status": "pending",
        "sku_index": "6",
        "note": "Meera cancellable order",
    },
]
