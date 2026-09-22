"""meal completions, lines, and operation receipts

Revision ID: b6e3d9f2a815
Revises: a8e4b2c1d603
Create Date: 2026-10-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b6e3d9f2a815"
down_revision: Union[str, Sequence[str], None] = "a8e4b2c1d603"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meal_completion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("meal_plan_entry_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="recorded"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("completed_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reopened_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reopened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopen_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["meal_plan_entry_id", "household_id"],
            ["meal_plan_entry.id", "meal_plan_entry.household_id"],
            name="fk_meal_completion_entry_household",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["completed_by_user_id"], ["app_user.id"]
        ),
        sa.ForeignKeyConstraint(
            ["reopened_by_user_id"], ["app_user.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "household_id", name="uq_meal_completion_household"
        ),
        sa.CheckConstraint(
            "state IN ('recorded', 'reopened')", name="ck_meal_completion_state"
        ),
        sa.CheckConstraint(
            "version >= 1", name="ck_meal_completion_version_positive"
        ),
        sa.CheckConstraint(
            "state <> 'reopened' OR (reopened_by_user_id IS NOT NULL "
            "AND reopened_at IS NOT NULL)",
            name="ck_meal_completion_reopened_fields",
        ),
    )
    op.create_index(
        "ix_meal_completion_recorded_entry",
        "meal_completion",
        ["household_id", "meal_plan_entry_id"],
        unique=True,
        postgresql_where="state = 'recorded'",
    )
    op.create_index(
        "ix_meal_completion_completed_at",
        "meal_completion",
        ["household_id", "completed_at"],
    )
    op.create_index(
        op.f("ix_meal_completion_household_id"),
        "meal_completion",
        ["household_id"],
    )
    op.create_index(
        op.f("ix_meal_completion_meal_plan_entry_id"),
        "meal_completion",
        ["meal_plan_entry_id"],
    )

    op.create_table(
        "meal_completion_line",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("meal_completion_id", sa.Uuid(), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(), nullable=False),
        sa.Column("planned_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("actual_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit", sa.String(8), nullable=False),
        sa.Column("optional", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["meal_completion_id", "household_id"],
            ["meal_completion.id", "meal_completion.household_id"],
            name="fk_meal_completion_line_completion_household",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "meal_completion_id",
            "ingredient_id",
            "unit",
            name="uq_meal_completion_line_ingredient",
        ),
        sa.CheckConstraint(
            "planned_amount >= 0", name="ck_meal_completion_line_planned_nonneg"
        ),
        sa.CheckConstraint(
            "actual_amount > 0", name="ck_meal_completion_line_actual_positive"
        ),
        sa.CheckConstraint(
            "length(btrim(unit)) > 0", name="ck_meal_completion_line_unit_nonempty"
        ),
        sa.CheckConstraint(
            "position >= 0", name="ck_meal_completion_line_position_nonneg"
        ),
    )
    op.create_index(
        op.f("ix_meal_completion_line_household_id"),
        "meal_completion_line",
        ["household_id"],
    )
    op.create_index(
        op.f("ix_meal_completion_line_meal_completion_id"),
        "meal_completion_line",
        ["meal_completion_id"],
    )

    op.create_table(
        "completion_operation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("request_hash", sa.String(64), nullable=True),
        sa.Column("result_payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["household_id"], ["household.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "household_id",
            "operation",
            "idempotency_key",
            name="uq_completion_operation_idempotency",
        ),
    )
    op.create_index(
        op.f("ix_completion_operation_household_id"),
        "completion_operation",
        ["household_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_completion_operation_household_id"),
        table_name="completion_operation",
    )
    op.drop_table("completion_operation")

    op.drop_index(
        op.f("ix_meal_completion_line_meal_completion_id"),
        table_name="meal_completion_line",
    )
    op.drop_index(
        op.f("ix_meal_completion_line_household_id"),
        table_name="meal_completion_line",
    )
    op.drop_table("meal_completion_line")

    op.drop_index(
        op.f("ix_meal_completion_meal_plan_entry_id"), table_name="meal_completion"
    )
    op.drop_index(
        op.f("ix_meal_completion_household_id"), table_name="meal_completion"
    )
    op.drop_index("ix_meal_completion_completed_at", table_name="meal_completion")
    op.drop_index("ix_meal_completion_recorded_entry", table_name="meal_completion")
    op.drop_table("meal_completion")
