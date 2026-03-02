"""add load type and incremental fields

Revision ID: 019
Revises: 018
Create Date: 2026-02-28

"""
from alembic import op
import sqlalchemy as sa


revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('migrations_bq_redshift', sa.Column('load_type', sa.String(20), nullable=True, server_default='full'))
    op.add_column('migrations_bq_redshift', sa.Column('primary_key_column', sa.String(255), nullable=True))
    op.add_column('migrations_bq_redshift', sa.Column('timestamp_column', sa.String(255), nullable=True))
    op.add_column('migrations_bq_redshift', sa.Column('last_extracted_value', sa.Text(), nullable=True))
    op.add_column('migrations_bq_redshift', sa.Column('run_immediately', sa.String(10), nullable=True, server_default='false'))


def downgrade() -> None:
    op.drop_column('migrations_bq_redshift', 'run_immediately')
    op.drop_column('migrations_bq_redshift', 'last_extracted_value')
    op.drop_column('migrations_bq_redshift', 'timestamp_column')
    op.drop_column('migrations_bq_redshift', 'primary_key_column')
    op.drop_column('migrations_bq_redshift', 'load_type')
