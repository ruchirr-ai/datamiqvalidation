"""Add missing DataSync agent mode column

Revision ID: 037
Revises: 036
"""

from alembic import op
import sqlalchemy as sa


revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "migrations_bq_redshift",
        sa.Column(
            "datasync_agent_mode",
            sa.String(length=20),
            nullable=True,
            server_default="create_vm",
        ),
    )


def downgrade():
    op.drop_column("migrations_bq_redshift", "datasync_agent_mode")
