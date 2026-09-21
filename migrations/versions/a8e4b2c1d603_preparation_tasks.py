"""preparation tasks and operation receipts

Revision ID: a8e4b2c1d603
Revises: c7d4e2f8a915
Create Date: 2026-10-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a8e4b2c1d603"
down_revision: Union[str, Sequence[str], None] = "c7d4e2f8a915"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_meal_plan_entry_household", "meal_plan_entry", ["id", "household_id"]
    )

    op.create_table(
        "preparation_task",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("origin", sa.String(24), nullable=False),
        sa.Column("task_type", sa.String(24), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("meal_plan_entry_id", sa.Uuid(), nullable=True),
        sa.Column("recipe_version_id", sa.Uuid(), nullable=True),
        sa.Column("ingredient_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(18, 6), nullable=True),
        sa.Column("unit", sa.String(8), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("completed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_version_id"], ["recipe_version.id"]),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(
            ["meal_plan_entry_id", "household_id"],
            ["meal_plan_entry.id", "meal_plan_entry.household_id"],
            name="fk_preparation_task_entry_household",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("origin IN ('derived', 'manual')", name="ck_preparation_task_origin"),
        sa.CheckConstraint(
            "task_type IN ('defrost', 'soak', 'marinate', 'prepare_ahead', 'manual')",
            name="ck_preparation_task_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'cancelled')",
            name="ck_preparation_task_status",
        ),
        sa.CheckConstraint("version >= 1", name="ck_preparation_task_version_positive"),
        sa.CheckConstraint(
            "amount IS NULL OR amount > 0", name="ck_preparation_task_amount_positive"
        ),
        sa.CheckConstraint(
            "(amount IS NULL) = (unit IS NULL)", name="ck_preparation_task_amount_unit_pair"
        ),
        sa.CheckConstraint(
            "origin <> 'derived' OR (fingerprint IS NOT NULL AND meal_plan_entry_id IS NOT NULL)",
            name="ck_preparation_task_derived_fields",
        ),
        sa.CheckConstraint(
            "status <> 'completed' OR (completed_by_user_id IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="ck_preparation_task_completed_fields",
        ),
    )
    op.create_index("ix_preparation_task_household_id", "preparation_task", ["household_id"])
    op.create_index(
        "ix_preparation_task_meal_plan_entry_id", "preparation_task", ["meal_plan_entry_id"]
    )
    op.create_index(
        "ix_preparation_task_derived_fingerprint",
        "preparation_task",
        ["household_id", "fingerprint"],
        unique=True,
        postgresql_where=sa.text("origin = 'derived'"),
    )
    op.create_index(
        "ix_preparation_task_due_at", "preparation_task", ["household_id", "status", "due_at"]
    )

    op.create_table(
        "preparation_operation",
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
            name="uq_preparation_operation_idempotency",
        ),
    )
    op.create_index(
        "ix_preparation_operation_household_id", "preparation_operation", ["household_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_preparation_operation_household_id", table_name="preparation_operation")
    op.drop_table("preparation_operation")
    op.drop_index("ix_preparation_task_due_at", table_name="preparation_task")
    op.drop_index("ix_preparation_task_derived_fingerprint", table_name="preparation_task")
    op.drop_index("ix_preparation_task_meal_plan_entry_id", table_name="preparation_task")
    op.drop_index("ix_preparation_task_household_id", table_name="preparation_task")
    op.drop_table("preparation_task")
    op.drop_constraint("uq_meal_plan_entry_household", "meal_plan_entry", type_="unique")
