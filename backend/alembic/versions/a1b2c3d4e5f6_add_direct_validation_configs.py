"""add direct_validation_configs table

Revision ID: a1b2c3d4e5f6
Revises: fa9d4cb18f15
Create Date: 2026-09-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "fa9d4cb18f15"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "direct_validation_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("source_connection_id", sa.Integer(), nullable=False),
        sa.Column("target_connection_id", sa.Integer(), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_direct_validation_configs_workspace",
        "direct_validation_configs",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_direct_validation_configs_workspace",
        table_name="direct_validation_configs",
    )
    op.drop_table("direct_validation_configs")
