"""add batch_name column to conversion_batches

Revision ID: 021
Revises: 020
Create Date: 2026-03-08

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'conversion_batches',
        sa.Column('batch_name', sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('conversion_batches', 'batch_name')
