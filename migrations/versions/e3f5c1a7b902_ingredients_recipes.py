"""ingredients and recipe versions

Revision ID: e3f5c1a7b902
Revises: d92f0d3b1e4a
Create Date: 2026-09-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e3f5c1a7b902"
down_revision: Union[str, Sequence[str], None] = "d92f0d3b1e4a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingredient",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("normalized_name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(80), nullable=True),
        sa.Column("dimension", sa.String(16), nullable=False),
        sa.Column("base_unit", sa.String(8), nullable=False),
        sa.Column("package_size_amount", sa.Numeric(18, 6), nullable=True),
        sa.Column("package_size_unit", sa.String(8), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "dimension IN ('count', 'mass', 'volume')", name="ck_ingredient_dimension"
        ),
        sa.CheckConstraint(
            "base_unit IN ('unit', 'g', 'kg', 'ml', 'l')", name="ck_ingredient_base_unit"
        ),
    )
    op.create_index("ix_ingredient_household_id", "ingredient", ["household_id"])
    op.create_index("ix_ingredient_archived_at", "ingredient", ["archived_at"])
    op.create_index(
        "uq_ingredient_global_normalized_name",
        "ingredient",
        ["normalized_name"],
        unique=True,
        postgresql_where=sa.text("household_id IS NULL AND archived_at IS NULL"),
    )
    op.create_index(
        "uq_ingredient_household_normalized_name",
        "ingredient",
        ["household_id", "normalized_name"],
        unique=True,
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    op.create_table(
        "recipe",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("normalized_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recipe_household_id", "recipe", ["household_id"])
    op.create_index("ix_recipe_normalized_name", "recipe", ["normalized_name"])
    op.create_index("ix_recipe_archived_at", "recipe", ["archived_at"])

    op.create_table(
        "recipe_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("base_servings", sa.Integer(), nullable=False),
        sa.Column("prep_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["published_by_user_id"], ["app_user.id"]),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipe_id", "version_number", name="uq_recipe_version_number"),
        sa.CheckConstraint("base_servings > 0", name="ck_recipe_version_servings"),
        sa.CheckConstraint("prep_minutes >= 0", name="ck_recipe_version_prep_minutes"),
        sa.CheckConstraint(
            "state IN ('draft', 'published', 'archived')", name="ck_recipe_version_state"
        ),
    )
    op.create_index("ix_recipe_version_recipe_id", "recipe_version", ["recipe_id"])

    op.create_table(
        "recipe_version_ingredient",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipe_version_id", sa.Uuid(), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit", sa.String(8), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"]),
        sa.ForeignKeyConstraint(["recipe_version_id"], ["recipe_version.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("amount > 0", name="ck_recipe_ingredient_amount"),
    )
    op.create_index(
        "ix_recipe_version_ingredient_version", "recipe_version_ingredient", ["recipe_version_id"]
    )
    op.create_index(
        "ix_recipe_version_ingredient_ingredient", "recipe_version_ingredient", ["ingredient_id"]
    )

    op.create_table(
        "recipe_instruction",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipe_version_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["recipe_version_id"], ["recipe_version.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipe_version_id", "position", name="uq_recipe_instruction_position"),
    )
    op.create_index("ix_recipe_instruction_version", "recipe_instruction", ["recipe_version_id"])

    op.create_table(
        "recipe_meal_type",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipe_version_id", sa.Uuid(), nullable=False),
        sa.Column("meal_type", sa.String(16), nullable=False),
        sa.ForeignKeyConstraint(["recipe_version_id"], ["recipe_version.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipe_version_id", "meal_type", name="uq_recipe_meal_type"),
        sa.CheckConstraint(
            "meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')", name="ck_recipe_meal_type"
        ),
    )
    op.create_index("ix_recipe_meal_type_version", "recipe_meal_type", ["recipe_version_id"])

    op.create_table(
        "recipe_tag",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("household_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("normalized_name", sa.String(80), nullable=False),
        sa.ForeignKeyConstraint(["household_id"], ["household.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("household_id", "normalized_name", name="uq_recipe_tag_name"),
    )
    op.create_index("ix_recipe_tag_household_id", "recipe_tag", ["household_id"])

    op.create_table(
        "recipe_tag_link",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipe_version_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["recipe_version_id"], ["recipe_version.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["recipe_tag.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipe_version_id", "tag_id", name="uq_recipe_tag_link"),
    )
    op.create_index("ix_recipe_tag_link_version", "recipe_tag_link", ["recipe_version_id"])
    op.create_index("ix_recipe_tag_link_tag", "recipe_tag_link", ["tag_id"])

    op.create_table(
        "recipe_favorite",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("recipe_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipe.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "recipe_id", name="uq_recipe_favorite"),
    )
    op.create_index("ix_recipe_favorite_user_id", "recipe_favorite", ["user_id"])
    op.create_index("ix_recipe_favorite_recipe_id", "recipe_favorite", ["recipe_id"])

    op.create_table(
        "recipe_preparation_rule",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("recipe_version_id", sa.Uuid(), nullable=False),
        sa.Column("rule_type", sa.String(32), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(), nullable=True),
        sa.Column("lead_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredient.id"]),
        sa.ForeignKeyConstraint(["recipe_version_id"], ["recipe_version.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("lead_minutes >= 0", name="ck_recipe_prep_lead_minutes"),
        sa.CheckConstraint(
            "rule_type IN ('defrost', 'soak', 'marinate', 'prepare_ahead')",
            name="ck_recipe_prep_type",
        ),
    )
    op.create_index("ix_recipe_prep_rule_version", "recipe_preparation_rule", ["recipe_version_id"])


def downgrade() -> None:
    op.drop_index("ix_recipe_prep_rule_version", table_name="recipe_preparation_rule")
    op.drop_table("recipe_preparation_rule")
    op.drop_index("ix_recipe_favorite_recipe_id", table_name="recipe_favorite")
    op.drop_index("ix_recipe_favorite_user_id", table_name="recipe_favorite")
    op.drop_table("recipe_favorite")
    op.drop_index("ix_recipe_tag_link_tag", table_name="recipe_tag_link")
    op.drop_index("ix_recipe_tag_link_version", table_name="recipe_tag_link")
    op.drop_table("recipe_tag_link")
    op.drop_index("ix_recipe_tag_household_id", table_name="recipe_tag")
    op.drop_table("recipe_tag")
    op.drop_index("ix_recipe_meal_type_version", table_name="recipe_meal_type")
    op.drop_table("recipe_meal_type")
    op.drop_index("ix_recipe_instruction_version", table_name="recipe_instruction")
    op.drop_table("recipe_instruction")
    op.drop_index("ix_recipe_version_ingredient_ingredient", table_name="recipe_version_ingredient")
    op.drop_index("ix_recipe_version_ingredient_version", table_name="recipe_version_ingredient")
    op.drop_table("recipe_version_ingredient")
    op.drop_index("ix_recipe_version_recipe_id", table_name="recipe_version")
    op.drop_table("recipe_version")
    op.drop_index("ix_recipe_normalized_name", table_name="recipe")
    op.drop_index("ix_recipe_household_id", table_name="recipe")
    op.drop_index("ix_recipe_archived_at", table_name="recipe")
    op.drop_table("recipe")
    op.drop_index("ix_ingredient_archived_at", table_name="ingredient")
    op.drop_index("ix_ingredient_household_id", table_name="ingredient")
    op.drop_index("uq_ingredient_household_normalized_name", table_name="ingredient")
    op.drop_index("uq_ingredient_global_normalized_name", table_name="ingredient")
    op.drop_table("ingredient")
