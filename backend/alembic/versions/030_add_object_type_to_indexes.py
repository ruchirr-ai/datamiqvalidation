"""Add object_type column to assessment_indexes

Revision ID: 030
Revises: 029
Create Date: 2026-03-10
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '030'
down_revision = '029'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('assessment_indexes', sa.Column('object_type', sa.String(50), nullable=True, server_default='TABLE'))


def downgrade() -> None:
    op.drop_column('assessment_indexes', 'object_type')
