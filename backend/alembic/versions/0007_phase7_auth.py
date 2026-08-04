"""Phase 7 — production auth, sessions, roles.

Revision ID: 0007_phase7
Revises: 0006_phase6
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_phase7"
down_revision: str | None = "0006_phase6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(512), nullable=True))
    op.add_column(
        "users", sa.Column("role", sa.String(32), nullable=False, server_default="customer")
    )
    op.add_column(
        "users",
        sa.Column("is_disabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "users",
        sa.Column(
            "failed_login_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
    )
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("users", "demo_key", existing_type=sa.String(64), nullable=True)

    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("family_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("is_revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_refresh_sessions_user", "refresh_sessions", ["user_id"])
    op.create_index("ix_refresh_sessions_family", "refresh_sessions", ["family_id"])
    op.create_index(
        "ix_refresh_sessions_token_hash", "refresh_sessions", ["token_hash"], unique=True
    )

    op.create_table(
        "auth_audit_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_auth_audit_user", "auth_audit_events", ["user_id"])
    op.create_index("ix_auth_audit_created", "auth_audit_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("auth_audit_events")
    op.drop_table("refresh_sessions")
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
    op.drop_column("users", "is_disabled")
    op.drop_column("users", "role")
    op.drop_column("users", "password_hash")
    op.execute("UPDATE users SET demo_key = id::text WHERE demo_key IS NULL")
    op.alter_column("users", "demo_key", existing_type=sa.String(64), nullable=False)
