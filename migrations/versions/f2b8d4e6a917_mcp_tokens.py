"""mcp agent tokens

Revision ID: f2b8d4e6a917
Revises: c1f4a7e2b908
Create Date: 2026-09-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f2b8d4e6a917"
down_revision: Union[str, Sequence[str], None] = "c1f4a7e2b908"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mcp_token",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("token_prefix", sa.String(24), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_mcp_token_hash"),
    )
    op.create_index("ix_mcp_token_household_id", "mcp_token", ["household_id"])
    op.create_index("ix_mcp_token_user_id", "mcp_token", ["user_id"])
    op.create_index("ix_mcp_token_token_hash", "mcp_token", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_mcp_token_token_hash", table_name="mcp_token")
    op.drop_index("ix_mcp_token_user_id", table_name="mcp_token")
    op.drop_index("ix_mcp_token_household_id", table_name="mcp_token")
    op.drop_table("mcp_token")
