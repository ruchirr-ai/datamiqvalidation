"""add run_name to validation_runs

Revision ID: 032
Revises: 031
Create Date: 2026-03-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '032'
down_revision = '031'
branch_labels = None
depends_on = None


def upgrade():
    # Idempotency check: skip if column already exists
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='validation_runs' AND column_name='run_name'"
    ))
    if result.fetchone() is not None:
        return

    op.add_column('validation_runs', sa.Column('run_name', sa.String(255), nullable=True))


def downgrade():
    op.drop_column('validation_runs', 'run_name')
