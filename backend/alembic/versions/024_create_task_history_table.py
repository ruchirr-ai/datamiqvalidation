"""Create task_history table for tracking DataSync tasks

Revision ID: 024
Revises: 023
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '024'
down_revision = '023'
branch_labels = None
depends_on = None


def upgrade():
    # Table may already exist from a previous branch migration — skip if so
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT tablename FROM pg_tables WHERE tablename='task_history'"
    ))
    if result.fetchone() is not None:
        return

    op.create_table(
        'task_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('migration_id', sa.Integer(), nullable=False, index=True),
        sa.Column('migration_name', sa.String(255), nullable=False),
        sa.Column('task_arn', sa.String(500)),
        sa.Column('execution_arn', sa.String(500)),
        sa.Column('task_name', sa.String(255)),
        sa.Column('task_type', sa.String(50), server_default='datasync'),
        sa.Column('agent_arn', sa.String(500)),
        sa.Column('agent_ip', sa.String(100)),
        sa.Column('source_location_arn', sa.String(500)),
        sa.Column('source_uri', sa.Text()),
        sa.Column('dest_location_arn', sa.String(500)),
        sa.Column('dest_uri', sa.Text()),
        sa.Column('table_name', sa.String(255)),
        sa.Column('status', sa.String(50), nullable=False, server_default='running'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('duration_seconds', sa.Float()),
        sa.Column('files_transferred', sa.BigInteger(), server_default='0'),
        sa.Column('bytes_transferred', sa.BigInteger(), server_default='0'),
        sa.Column('error_message', sa.Text()),
        sa.Column('error_code', sa.String(100)),
        sa.Column('error_details', JSONB()),
        sa.Column('raw_result', JSONB()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('task_history')
