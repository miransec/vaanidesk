"""One-off migration/order-ref verification helper for Phase 2 security pass."""

from __future__ import annotations

import asyncio
import json

from app.database.session import get_engine
from sqlalchemy import text


async def main() -> None:
    engine = get_engine()
    async with engine.connect() as conn:
        rev = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
        refs = [
            row[0]
            for row in (
                await conn.execute(text("SELECT order_number FROM orders ORDER BY order_number"))
            )
        ]
        tickets = (
            await conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name='support_tickets'"
                )
            )
        ).scalar_one()
        nums = sorted(int(r.removeprefix("VD-")) for r in refs if r.startswith("VD-"))
        report = {
            "alembic_version": rev,
            "order_count": len(refs),
            "unique_order_refs": len(set(refs)),
            "all_vd_prefix": all(r.startswith("VD-") for r in refs),
            "first5": refs[:5],
            "contiguous_from_10001": nums == list(range(10001, 10001 + len(nums))),
            "support_tickets_table_exists": int(tickets) == 1,
        }
        print(json.dumps(report, indent=2))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
