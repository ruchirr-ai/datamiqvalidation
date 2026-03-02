"""add truncate_before_load field

Revision ID: 020
Revises: 019
Create Date: 2026-03-02

"""
from alembic import op
import sqlalchemy as sa


revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('migrations_bq_redshift', sa.Column('truncate_before_load', sa.String(10), nullable=True, server_default='false'))


def downgrade() -> None:
    op.drop_column('migrations_bq_redshift', 'truncate_before_load')
