"""add household memory

Revision ID: 6b1354a22e91
Revises: d3c72b91a84f
Create Date: 2026-10-01 02:35:58.126475

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6b1354a22e91"
down_revision: Union[str, Sequence[str], None] = "d3c72b91a84f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "household_diner",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("household_id", sa.UUID(), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("member_user_id", sa.UUID(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_user_id"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", "member_user_id", name="uq_household_diner_member"),
    )
    op.create_index(
        "ix_household_diner_household_id",
        "household_diner",
        ["household_id"],
        unique=False,
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_household_diner_active_name "
        "ON household_diner (household_id, lower(display_name)) "
        "WHERE archived_at IS NULL"
    )

    op.create_table(
        "household_memory",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("household_id", sa.UUID(), nullable=False),
        sa.Column("diner_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint(
            "kind IN ('like', 'dislike', 'restriction', 'goal', 'note')",
            name="ck_household_memory_kind",
        ),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["diner_id"], ["household_diner.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["app_user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_household_memory_household_id",
        "household_memory",
        ["household_id"],
        unique=False,
    )
    op.create_index(
        "ix_household_memory_scope",
        "household_memory",
        ["household_id", "diner_id", "archived_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_household_memory_scope", table_name="household_memory")
    op.drop_index("ix_household_memory_household_id", table_name="household_memory")
    op.drop_table("household_memory")
    op.drop_index("uq_household_diner_active_name", table_name="household_diner")
    op.drop_index("ix_household_diner_household_id", table_name="household_diner")
    op.drop_table("household_diner")
