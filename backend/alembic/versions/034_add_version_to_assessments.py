"""Add version column to assessments table

Revision ID: 034
Revises: 033
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '034'
down_revision = '033'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('assessments', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    op.drop_column('assessments', 'version')
