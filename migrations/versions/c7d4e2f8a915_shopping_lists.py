"""shopping lists, items, and operation receipts

Revision ID: c7d4e2f8a915
Revises: b5c9e1a3d407
Create Date: 2026-09-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c7d4e2f8a915"
down_revision: Union[str, Sequence[str], None] = "b5c9e1a3d407"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shopping_list",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("from_date", sa.Date(), nullable=False),
        sa.Column("to_date", sa.Date(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="open"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "household_id", name="uq_shopping_list_household"),
        sa.CheckConstraint("to_date >= from_date", name="ck_shopping_list_window_order"),
        sa.CheckConstraint(
            "state IN ('open', 'completed', 'archived')", name="ck_shopping_list_state"
        ),
        sa.CheckConstraint("version >= 1", name="ck_shopping_list_version_positive"),
    )
    op.create_index("ix_shopping_list_household_id", "shopping_list", ["household_id"])
    op.create_index(
        "ix_shopping_list_active_window",
        "shopping_list",
        ["household_id", "from_date", "to_date"],
        unique=True,
        postgresql_where=sa.text("state <> 'archived'"),
    )

    op.create_table(
        "shopping_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("shopping_list_id", sa.Uuid(), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(), nullable=False),
        sa.Column("unit", sa.String(8), nullable=False),
        sa.Column("needed_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("optional_amount", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("purchased_amount", sa.Numeric(18, 6), nullable=True),
        sa.Column("purchased_lot_id", sa.Uuid(), nullable=True),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"]),
        sa.ForeignKeyConstraint(["purchased_lot_id"], ["inventory_lot.id"]),
        sa.ForeignKeyConstraint(
            ["shopping_list_id", "household_id"],
            ["shopping_list.id", "shopping_list.household_id"],
            name="fk_shopping_item_list_household",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "shopping_list_id", "ingredient_id", "unit", name="uq_shopping_item_line"
        ),
        sa.CheckConstraint("needed_amount > 0", name="ck_shopping_item_needed_positive"),
        sa.CheckConstraint("optional_amount >= 0", name="ck_shopping_item_optional_nonneg"),
        sa.CheckConstraint(
            "purchased_amount IS NULL OR purchased_amount > 0",
            name="ck_shopping_item_purchased_positive",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'purchased', 'skipped')", name="ck_shopping_item_status"
        ),
        sa.CheckConstraint(
            "status <> 'purchased' OR (purchased_amount IS NOT NULL "
            "AND purchased_lot_id IS NOT NULL AND purchased_at IS NOT NULL)",
            name="ck_shopping_item_purchased_fields",
        ),
        sa.CheckConstraint("position >= 0", name="ck_shopping_item_position_nonneg"),
    )
    op.create_index("ix_shopping_item_household_id", "shopping_item", ["household_id"])
    op.create_index("ix_shopping_item_shopping_list_id", "shopping_item", ["shopping_list_id"])
    op.create_index("ix_shopping_item_ingredient_id", "shopping_item", ["ingredient_id"])

    op.create_table(
        "shopping_operation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("request_hash", sa.String(64), nullable=True),
        sa.Column("result_payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "operation",
            "idempotency_key",
            name="uq_shopping_operation_idempotency",
        ),
    )
    op.create_index(
        "ix_shopping_operation_household_id", "shopping_operation", ["household_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_shopping_operation_household_id", table_name="shopping_operation")
    op.drop_table("shopping_operation")
    op.drop_index("ix_shopping_item_ingredient_id", table_name="shopping_item")
    op.drop_index("ix_shopping_item_shopping_list_id", table_name="shopping_item")
    op.drop_index("ix_shopping_item_household_id", table_name="shopping_item")
    op.drop_table("shopping_item")
    op.drop_index("ix_shopping_list_active_window", table_name="shopping_list")
    op.drop_index("ix_shopping_list_household_id", table_name="shopping_list")
    op.drop_table("shopping_list")
