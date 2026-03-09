"""Add connection_params_encrypted column to connections table

Revision ID: 025
Revises: 024
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa

revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if column already exists (may have been created by a previous branch migration)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='connections' AND column_name='connection_params_encrypted'"
    ))
    if result.fetchone() is None:
        op.add_column('connections', sa.Column('connection_params_encrypted', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('connections', 'connection_params_encrypted')
