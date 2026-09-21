"""identity and household domain

Revision ID: d92f0d3b1e4a
Revises: acc60b26baac
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d92f0d3b1e4a"
down_revision: Union[str, Sequence[str], None] = "acc60b26baac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("display_name", sa.String(length=240), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'disabled')", name="ck_app_user_status"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_app_user_email", "app_user", ["email"])

    op.create_table(
        "user_identity",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("issuer", sa.String(length=2048), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False, server_default="oidc"),
        sa.Column("last_claims_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issuer", "subject", name="uq_user_identity_issuer_subject"),
    )
    op.create_index("ix_user_identity_user_id", "user_identity", ["user_id"])

    op.create_table(
        "household",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("locale", sa.String(length=32), nullable=False, server_default="es"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="UTC"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_household_status"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "household_member",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_household_member_role"),
        sa.CheckConstraint("status IN ('active', 'revoked', 'left')", name="ck_household_member_status"),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", "user_id", name="uq_household_member_household_user"),
    )
    op.create_index("ix_household_member_household_id", "household_member", ["household_id"])
    op.create_index("ix_household_member_user_id", "household_member", ["user_id"])

    op.create_table(
        "household_invitation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("invited_email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("requested_role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("accepted_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("requested_role IN ('admin', 'member')", name="ck_household_invitation_role"),
        sa.CheckConstraint("status IN ('pending', 'accepted', 'revoked', 'expired')", name="ck_household_invitation_status"),
        sa.ForeignKeyConstraint(["accepted_by_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_household_invitation_token_hash"),
    )
    op.create_index("ix_household_invitation_household_id", "household_invitation", ["household_id"])
    op.create_index("ix_household_invitation_invited_email", "household_invitation", ["invited_email"])

    op.create_table(
        "audit_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("household_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=120), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_event_actor_user_id", "audit_event", ["actor_user_id"])
    op.create_index("ix_audit_event_household_id", "audit_event", ["household_id"])

    op.create_table(
        "email_outbox_entry",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("template_data", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_email_outbox_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_email_outbox_dedupe_key"),
    )


def downgrade() -> None:
    op.drop_table("email_outbox_entry")
    op.drop_index("ix_audit_event_household_id", table_name="audit_event")
    op.drop_index("ix_audit_event_actor_user_id", table_name="audit_event")
    op.drop_table("audit_event")
    op.drop_index("ix_household_invitation_invited_email", table_name="household_invitation")
    op.drop_index("ix_household_invitation_household_id", table_name="household_invitation")
    op.drop_table("household_invitation")
    op.drop_index("ix_household_member_user_id", table_name="household_member")
    op.drop_index("ix_household_member_household_id", table_name="household_member")
    op.drop_table("household_member")
    op.drop_table("household")
    op.drop_index("ix_user_identity_user_id", table_name="user_identity")
    op.drop_table("user_identity")
    op.drop_index("ix_app_user_email", table_name="app_user")
    op.drop_table("app_user")
