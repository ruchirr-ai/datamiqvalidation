"""add table_load_configs JSONB column for per-table incremental settings

Revision ID: 021
Revises: 020
Create Date: 2026-03-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('migrations_bq_redshift', sa.Column('table_load_configs', JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column('migrations_bq_redshift', 'table_load_configs')
