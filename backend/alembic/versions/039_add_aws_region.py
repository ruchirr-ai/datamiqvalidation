"""Add missing AWS region column

Revision ID: 039
Revises: 038
"""

from alembic import op
import sqlalchemy as sa

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "migrations_bq_redshift",
        sa.Column("aws_region", sa.String(100), nullable=True)
    )


def downgrade():
    op.drop_column("migrations_bq_redshift", "aws_region")