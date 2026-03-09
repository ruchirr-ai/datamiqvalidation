"""Create copy_history table for tracking Redshift COPY commands

Revision ID: 023
Revises: 022
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade():
    # Table may already exist from a previous branch migration — skip if so
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT tablename FROM pg_tables WHERE tablename='copy_history'"
    ))
    if result.fetchone() is not None:
        return

    op.create_table(
        'copy_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('migration_id', sa.Integer(), nullable=False, index=True),
        sa.Column('migration_name', sa.String(255), nullable=False),
        sa.Column('schema_name', sa.String(255), nullable=False),
        sa.Column('table_name', sa.String(255), nullable=False),
        sa.Column('copy_command', sa.Text(), nullable=False),
        sa.Column('source_uri', sa.Text()),
        sa.Column('file_format', sa.String(50)),
        sa.Column('compression', sa.String(50)),
        sa.Column('iam_role_arn', sa.String(500)),
        sa.Column('status', sa.String(50), nullable=False, server_default='running'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('duration_seconds', sa.Float()),
        sa.Column('rows_loaded', sa.BigInteger(), server_default='0'),
        sa.Column('bytes_loaded', sa.BigInteger(), server_default='0'),
        sa.Column('error_message', sa.Text()),
        sa.Column('error_details', JSONB()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('copy_history')
