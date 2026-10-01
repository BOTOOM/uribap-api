"""meal completion outcomes

Revision ID: d3c72b91a84f
Revises: f2b8d4e6a917
Create Date: 2026-09-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d3c72b91a84f"
down_revision: Union[str, Sequence[str], None] = "f2b8d4e6a917"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meal_completion",
        sa.Column(
            "outcome",
            sa.Enum("cooked", "skipped", native_enum=False),
            server_default=sa.text("'cooked'"),
            nullable=False,
        ),
    )
    op.add_column("meal_completion", sa.Column("outcome_note", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_meal_completion_outcome",
        "meal_completion",
        "outcome IN ('cooked', 'skipped')",
    )
    op.execute(
        sa.text(
            """
            UPDATE completion_operation
            SET result_payload = result_payload
                || jsonb_build_object('outcome', 'cooked', 'outcome_note', NULL)
            WHERE result_payload IS NOT NULL
                AND jsonb_typeof(result_payload) = 'object'
                AND result_payload -> 'outcome' IS NULL
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE completion_operation
            SET result_payload = result_payload - 'outcome' - 'outcome_note'
            WHERE result_payload IS NOT NULL
                AND jsonb_typeof(result_payload) = 'object'
            """
        )
    )
    op.drop_constraint("ck_meal_completion_outcome", "meal_completion", type_="check")
    op.drop_column("meal_completion", "outcome_note")
    op.drop_column("meal_completion", "outcome")
