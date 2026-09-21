"""inventory lots and append-only movements

Revision ID: f4a7c9d1e203
Revises: e3f5c1a7b902
Create Date: 2026-09-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f4a7c9d1e203"
down_revision: Union[str, Sequence[str], None] = "e3f5c1a7b902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inventory_lot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(), nullable=False),
        sa.Column("quantity_on_hand", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit", sa.String(8), nullable=False),
        sa.Column("location", sa.String(24), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "household_id", name="uq_inventory_lot_household"),
        sa.CheckConstraint("quantity_on_hand >= 0", name="ck_inventory_lot_quantity_nonnegative"),
        sa.CheckConstraint(
            "location IN ('pantry', 'refrigerator', 'freezer')", name="ck_inventory_lot_location"
        ),
    )
    op.create_index("ix_inventory_lot_household_id", "inventory_lot", ["household_id"])
    op.create_index("ix_inventory_lot_ingredient_id", "inventory_lot", ["ingredient_id"])
    op.create_index("ix_inventory_lot_available", "inventory_lot", ["available"])
    op.create_index("ix_inventory_lot_expiration_date", "inventory_lot", ["expiration_date"])
    op.create_index(
        "ix_inventory_lot_positive_by_ingredient",
        "inventory_lot",
        ["household_id", "ingredient_id", "expiration_date"],
        postgresql_where=sa.text("quantity_on_hand > 0 AND available IS TRUE"),
    )

    op.create_table(
        "inventory_movement",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("lot_id", sa.Uuid(), nullable=False),
        sa.Column("delta", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit", sa.String(8), nullable=False),
        sa.Column("movement_type", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(80), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column(
            "operation", sa.String(80), nullable=False, server_default="inventory_adjustment"
        ),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("request_hash", sa.String(64), nullable=True),
        sa.Column("result_quantity_on_hand", sa.Numeric(18, 6), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["lot_id", "household_id"],
            ["inventory_lot.id", "inventory_lot.household_id"],
            name="fk_inventory_movement_lot_household",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id", "operation", "idempotency_key", name="uq_inventory_movement_idempotency"
        ),
        sa.CheckConstraint("delta <> 0", name="ck_inventory_movement_delta_nonzero"),
        sa.CheckConstraint(
            "movement_type IN ('purchase', 'meal_consumption', 'manual_adjustment', 'waste', 'reversal')",
            name="ck_inventory_movement_type",
        ),
    )
    op.create_index("ix_inventory_movement_household_id", "inventory_movement", ["household_id"])
    op.create_index("ix_inventory_movement_lot_id", "inventory_movement", ["lot_id"])
    op.create_index("ix_inventory_movement_actor_user_id", "inventory_movement", ["actor_user_id"])
    op.execute(
        """
        CREATE FUNCTION prevent_inventory_movement_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'inventory_movement is append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER inventory_movement_append_only
        BEFORE UPDATE OR DELETE ON inventory_movement
        FOR EACH ROW EXECUTE FUNCTION prevent_inventory_movement_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS inventory_movement_append_only ON inventory_movement")
    op.execute("DROP FUNCTION IF EXISTS prevent_inventory_movement_mutation()")
    op.drop_index("ix_inventory_movement_actor_user_id", table_name="inventory_movement")
    op.drop_index("ix_inventory_movement_lot_id", table_name="inventory_movement")
    op.drop_index("ix_inventory_movement_household_id", table_name="inventory_movement")
    op.drop_table("inventory_movement")
    op.drop_index("ix_inventory_lot_positive_by_ingredient", table_name="inventory_lot")
    op.drop_index("ix_inventory_lot_expiration_date", table_name="inventory_lot")
    op.drop_index("ix_inventory_lot_available", table_name="inventory_lot")
    op.drop_index("ix_inventory_lot_ingredient_id", table_name="inventory_lot")
    op.drop_index("ix_inventory_lot_household_id", table_name="inventory_lot")
    op.drop_table("inventory_lot")
