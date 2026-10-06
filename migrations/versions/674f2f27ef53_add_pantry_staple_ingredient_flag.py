"""add pantry staple ingredient flag

Revision ID: 674f2f27ef53
Revises: 6b1354a22e91
Create Date: 2026-10-06 00:42:08.637019

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "674f2f27ef53"
down_revision: str | Sequence[str] | None = "6b1354a22e91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ingredient",
        sa.Column(
            "pantry_staple",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("ingredient", "pantry_staple")
