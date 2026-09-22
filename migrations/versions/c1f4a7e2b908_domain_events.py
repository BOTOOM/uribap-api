"""domain events, email delivery intents, suppressed outbox status

Revision ID: c1f4a7e2b908
Revises: b6e3d9f2a815
Create Date: 2026-10-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c1f4a7e2b908"
down_revision: Union[str, Sequence[str], None] = "b6e3d9f2a815"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "domain_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("aggregate_type", sa.String(length=64), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(kind)) > 0", name="ck_domain_event_kind_nonempty"
        ),
        sa.CheckConstraint(
            "length(btrim(aggregate_type)) > 0",
            name="ck_domain_event_aggregate_type_nonempty",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["app_user.id"], name="fk_domain_event_actor_user_id"
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            name="fk_domain_event_household_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "household_id", name="uq_domain_event_household"),
    )
    op.create_index(
        "ix_domain_event_feed", "domain_event", ["household_id", "occurred_at"]
    )
    op.create_index("ix_domain_event_kind", "domain_event", ["household_id", "kind"])
    op.create_index(
        op.f("ix_domain_event_household_id"), "domain_event", ["household_id"]
    )

    op.create_table(
        "email_delivery_intent",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email_outbox_entry_id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=True),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome IN ('sent', 'suppressed', 'failed')",
            name="ck_email_delivery_intent_outcome",
        ),
        sa.CheckConstraint(
            "attempt_number >= 1", name="ck_email_delivery_intent_attempt_positive"
        ),
        sa.CheckConstraint(
            "length(btrim(subject)) > 0",
            name="ck_email_delivery_intent_subject_nonempty",
        ),
        sa.ForeignKeyConstraint(
            ["email_outbox_entry_id"],
            ["email_outbox_entry.id"],
            name="fk_email_delivery_intent_entry_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["household_id"],
            ["household.id"],
            name="fk_email_delivery_intent_household_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_delivery_intent_entry",
        "email_delivery_intent",
        ["email_outbox_entry_id", "created_at"],
    )
    op.create_index(
        op.f("ix_email_delivery_intent_household_id"),
        "email_delivery_intent",
        ["household_id"],
    )

    op.drop_constraint("ck_email_outbox_status", "email_outbox_entry", type_="check")
    op.create_check_constraint(
        "ck_email_outbox_status",
        "email_outbox_entry",
        "status IN ('pending', 'sent', 'failed', 'suppressed')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_email_outbox_status", "email_outbox_entry", type_="check")
    op.create_check_constraint(
        "ck_email_outbox_status",
        "email_outbox_entry",
        "status IN ('pending', 'sent', 'failed')",
    )
    op.drop_index(
        op.f("ix_email_delivery_intent_household_id"),
        table_name="email_delivery_intent",
    )
    op.drop_index("ix_email_delivery_intent_entry", table_name="email_delivery_intent")
    op.drop_table("email_delivery_intent")
    op.drop_index(op.f("ix_domain_event_household_id"), table_name="domain_event")
    op.drop_index("ix_domain_event_kind", table_name="domain_event")
    op.drop_index("ix_domain_event_feed", table_name="domain_event")
    op.drop_table("domain_event")
