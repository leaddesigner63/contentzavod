"""add redirects learning metrics

Revision ID: 0002_add_redirects_learning_metrics
Revises: 0001_init_schema
Create Date: 2026-02-10

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_add_redirects_learning_metrics"
down_revision = "0001_init_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("publications", sa.Column("platform_post_url", sa.String(length=512)))
    op.add_column("publications", sa.Column("idempotency_key", sa.String(length=128)))
    op.add_column(
        "publications",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("publications", sa.Column("last_error", sa.Text()))

    op.create_table(
        "integration_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id")),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("token_encrypted", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "redirect_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id")),
        sa.Column("content_item_id", sa.Integer(), sa.ForeignKey("content_items.id")),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("target_url", sa.Text(), nullable=False),
        sa.Column("utm_params", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slug", name="uniq_redirect_slug"),
    )
    op.create_table(
        "click_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id")),
        sa.Column("redirect_link_id", sa.Integer(), sa.ForeignKey("redirect_links.id")),
        sa.Column("content_item_id", sa.Integer(), sa.ForeignKey("content_items.id")),
        sa.Column("ip_address", sa.String(length=64)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("referrer", sa.Text()),
        sa.Column("utm_params", sa.JSON(), nullable=False),
        sa.Column("query_params", sa.JSON(), nullable=False),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "auto_learning_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), unique=True),
        sa.Column("max_changes_per_week", sa.Integer(), nullable=False),
        sa.Column("rollback_threshold", sa.Float(), nullable=False),
        sa.Column("rollback_window", sa.Integer(), nullable=False),
        sa.Column("protected_parameters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "auto_learning_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), unique=True),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("stable_parameters", sa.JSON(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True)),
        sa.Column("changes_in_window", sa.Integer(), nullable=False),
        sa.Column("last_change_at", sa.DateTime(timezone=True)),
        sa.Column("last_rollback_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.alter_column("publications", "attempt_count", server_default=None)


def downgrade() -> None:
    op.drop_table("auto_learning_states")
    op.drop_table("auto_learning_configs")
    op.drop_table("click_events")
    op.drop_table("redirect_links")
    op.drop_table("integration_tokens")
    op.drop_column("publications", "last_error")
    op.drop_column("publications", "attempt_count")
    op.drop_column("publications", "idempotency_key")
    op.drop_column("publications", "platform_post_url")
