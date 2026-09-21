"""meal plans, entries, state events, and operation receipts

Revision ID: b5c9e1a3d407
Revises: f4a7c9d1e203
Create Date: 2026-09-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b5c9e1a3d407"
down_revision: Union[str, Sequence[str], None] = "f4a7c9d1e203"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meal_plan",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("week_start_date", sa.Date(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="draft"),
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
        sa.UniqueConstraint("id", "household_id", name="uq_meal_plan_household"),
        sa.CheckConstraint("version >= 1", name="ck_meal_plan_version_positive"),
        sa.CheckConstraint(
            "state IN ('draft', 'proposed', 'approved', 'archived')", name="ck_meal_plan_state"
        ),
    )
    op.create_index("ix_meal_plan_household_id", "meal_plan", ["household_id"])
    op.create_index(
        "ix_meal_plan_active_week",
        "meal_plan",
        ["household_id", "week_start_date"],
        unique=True,
        postgresql_where=sa.text("state <> 'archived'"),
    )

    op.create_table(
        "meal_plan_entry",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("meal_plan_id", sa.Uuid(), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("meal_type", sa.String(24), nullable=False),
        sa.Column("recipe_version_id", sa.Uuid(), nullable=False),
        sa.Column("servings", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("added_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["added_by_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_version_id"], ["recipe_version.id"]),
        sa.ForeignKeyConstraint(
            ["meal_plan_id", "household_id"],
            ["meal_plan.id", "meal_plan.household_id"],
            name="fk_meal_plan_entry_plan_household",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "meal_plan_id",
            "planned_date",
            "meal_type",
            "position",
            name="uq_meal_plan_entry_slot",
        ),
        sa.CheckConstraint("servings > 0", name="ck_meal_plan_entry_servings_positive"),
        sa.CheckConstraint(
            "meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')",
            name="ck_meal_plan_entry_meal_type",
        ),
    )
    op.create_index("ix_meal_plan_entry_household_id", "meal_plan_entry", ["household_id"])
    op.create_index("ix_meal_plan_entry_meal_plan_id", "meal_plan_entry", ["meal_plan_id"])

    op.create_table(
        "meal_plan_state_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("meal_plan_id", sa.Uuid(), nullable=False),
        sa.Column("from_state", sa.String(24), nullable=True),
        sa.Column("to_state", sa.String(24), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["meal_plan_id", "household_id"],
            ["meal_plan.id", "meal_plan.household_id"],
            name="fk_meal_plan_state_event_plan_household",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "to_state IN ('draft', 'proposed', 'approved', 'archived')",
            name="ck_meal_plan_state_event_to_state",
        ),
    )
    op.create_index(
        "ix_meal_plan_state_event_household_id", "meal_plan_state_event", ["household_id"]
    )
    op.create_index(
        "ix_meal_plan_state_event_meal_plan_id", "meal_plan_state_event", ["meal_plan_id"]
    )
    op.execute(
        """
        CREATE FUNCTION prevent_meal_plan_state_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'meal_plan_state_event is append-only';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER meal_plan_state_event_append_only
        BEFORE UPDATE OR DELETE ON meal_plan_state_event
        FOR EACH ROW EXECUTE FUNCTION prevent_meal_plan_state_event_mutation();
        """
    )

    op.create_table(
        "meal_plan_operation",
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
            name="uq_meal_plan_operation_idempotency",
        ),
    )
    op.create_index("ix_meal_plan_operation_household_id", "meal_plan_operation", ["household_id"])


def downgrade() -> None:
    op.drop_index("ix_meal_plan_operation_household_id", table_name="meal_plan_operation")
    op.drop_table("meal_plan_operation")
    op.execute(
        "DROP TRIGGER IF EXISTS meal_plan_state_event_append_only ON meal_plan_state_event"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_meal_plan_state_event_mutation()")
    op.drop_index("ix_meal_plan_state_event_meal_plan_id", table_name="meal_plan_state_event")
    op.drop_index("ix_meal_plan_state_event_household_id", table_name="meal_plan_state_event")
    op.drop_table("meal_plan_state_event")
    op.drop_index("ix_meal_plan_entry_meal_plan_id", table_name="meal_plan_entry")
    op.drop_index("ix_meal_plan_entry_household_id", table_name="meal_plan_entry")
    op.drop_table("meal_plan_entry")
    op.drop_index("ix_meal_plan_active_week", table_name="meal_plan")
    op.drop_index("ix_meal_plan_household_id", table_name="meal_plan")
    op.drop_table("meal_plan")
