"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2025-09-29 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("tg_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.Text()),
        sa.Column("full_name", sa.Text()),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("owner_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("canceled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "event_participants",
        sa.Column("event_id", sa.BigInteger(), sa.ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="invited",
        ),
        sa.CheckConstraint("status in ('invited','going','declined','maybe')", name="event_participants_status_check"),
    )

    op.create_table(
        "expenses",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("event_id", sa.BigInteger(), sa.ForeignKey("events.id", ondelete="CASCADE")),
        sa.Column("payer_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="EUR"),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "expense_items",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("expense_id", sa.BigInteger(), sa.ForeignKey("expenses.id", ondelete="CASCADE")),
        sa.Column("label", sa.Text()),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
    )

    op.create_table(
        "expense_item_consumers",
        sa.Column("item_id", sa.BigInteger(), sa.ForeignKey("expense_items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "reminders",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("event_id", sa.BigInteger(), sa.ForeignKey("events.id", ondelete="CASCADE")),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "event_invite_links",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("event_id", sa.BigInteger(), sa.ForeignKey("events.id", ondelete="CASCADE")),
        sa.Column("token", sa.Text(), nullable=False, unique=True),
        sa.Column("max_uses", sa.Integer()),
        sa.Column("uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )

    op.create_index("idx_users_tg_id", "users", ["tg_id"], unique=True)
    op.create_index("idx_event_participants_event", "event_participants", ["event_id"])
    op.create_index("idx_event_participants_user", "event_participants", ["user_id"])
    op.create_index("idx_expenses_event", "expenses", ["event_id"])


def downgrade() -> None:
    op.drop_index("idx_expenses_event", table_name="expenses")
    op.drop_index("idx_event_participants_user", table_name="event_participants")
    op.drop_index("idx_event_participants_event", table_name="event_participants")
    op.drop_index("idx_users_tg_id", table_name="users")

    op.drop_table("event_invite_links")
    op.drop_table("reminders")
    op.drop_table("expense_item_consumers")
    op.drop_table("expense_items")
    op.drop_table("expenses")
    op.drop_table("event_participants")
    op.drop_table("events")
    op.drop_table("users")

