"""add batch_name column to conversion_batches

Revision ID: 021
Revises: 020
Create Date: 2026-03-08

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '028'
down_revision = '027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Column may already exist from a previous branch migration — skip if so
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='conversion_batches' AND column_name='batch_name'"
    ))
    if result.fetchone() is not None:
        return

    op.add_column(
        'conversion_batches',
        sa.Column('batch_name', sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('conversion_batches', 'batch_name')
