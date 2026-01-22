"""add versioning history and project storage

Revision ID: 0003_add_versioning_history_and_project_storage
Revises: 0002_add_redirects_learning_metrics
Create Date: 2026-02-20

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_add_versioning_history_and_project_storage"
down_revision = "0002_add_redirects_learning_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "brand_configs",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "brand_configs",
        sa.Column("is_stable", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "prompt_versions",
        sa.Column("is_stable", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_table(
        "brand_config_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id")),
        sa.Column("brand_config_id", sa.Integer(), sa.ForeignKey("brand_configs.id")),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("change_summary", sa.Text()),
        sa.Column("change_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "prompt_version_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id")),
        sa.Column("prompt_version_id", sa.Integer(), sa.ForeignKey("prompt_versions.id")),
        sa.Column("prompt_key", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("change_summary", sa.Text()),
        sa.Column("change_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "project_datasets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id")),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("storage_uri", sa.Text()),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name", name="uniq_project_dataset"),
    )
    op.create_table(
        "project_vector_indexes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id")),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name", name="uniq_project_vector_index"),
    )

    op.execute(
        """
        INSERT INTO project_datasets
            (project_id, name, kind, storage_uri, is_active, created_at)
        SELECT
            id,
            'project_' || id || '_dataset',
            'atoms',
            's3://datasets/project_' || id,
            true,
            NOW()
        FROM projects
        """
    )
    op.execute(
        """
        INSERT INTO project_vector_indexes
            (project_id, name, provider, embedding_dimension, metadata, created_at)
        SELECT
            id,
            'project_' || id || '_atoms',
            'pgvector',
            1536,
            '{"table": "atoms"}',
            NOW()
        FROM projects
        """
    )

    op.alter_column("brand_configs", "is_active", server_default=None)
    op.alter_column("brand_configs", "is_stable", server_default=None)
    op.alter_column("prompt_versions", "is_stable", server_default=None)


def downgrade() -> None:
    op.drop_table("project_vector_indexes")
    op.drop_table("project_datasets")
    op.drop_table("prompt_version_history")
    op.drop_table("brand_config_history")
    op.drop_column("prompt_versions", "is_stable")
    op.drop_column("brand_configs", "is_stable")
    op.drop_column("brand_configs", "is_active")
