"""add per-table check flags to validation_table_results

Revision ID: 033
Revises: 032
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = '033'
down_revision = '032'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('validation_table_results', sa.Column('ddl_check', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.add_column('validation_table_results', sa.Column('row_count_check', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.add_column('validation_table_results', sa.Column('data_match_check', sa.Boolean(), nullable=False, server_default=sa.text('true')))


def downgrade():
    op.drop_column('validation_table_results', 'data_match_check')
    op.drop_column('validation_table_results', 'row_count_check')
    op.drop_column('validation_table_results', 'ddl_check')
