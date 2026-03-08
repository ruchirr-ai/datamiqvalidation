"""create history tables

Revision ID: 020
Revises: 019
Create Date: 2026-03-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None


def upgrade():
    # Create copy_history table
    op.create_table(
        'copy_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('migration_id', sa.Integer(), nullable=False),
        sa.Column('migration_name', sa.String(255), nullable=True),
        sa.Column('schema_name', sa.String(255), nullable=True),
        sa.Column('table_name', sa.String(255), nullable=False),
        sa.Column('copy_command', sa.Text(), nullable=False),
        sa.Column('source_uri', sa.String(1000), nullable=False),
        sa.Column('file_format', sa.String(50), nullable=True),
        sa.Column('compression', sa.String(50), nullable=True),
        sa.Column('iam_role_arn', sa.String(500), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='running'),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('rows_loaded', sa.BigInteger(), nullable=True),
        sa.Column('bytes_loaded', sa.BigInteger(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for copy_history
    op.create_index('idx_copy_history_migration_id', 'copy_history', ['migration_id'])
    op.create_index('idx_copy_history_status', 'copy_history', ['status'])
    op.create_index('idx_copy_history_started_at', 'copy_history', ['started_at'])
    op.create_index('idx_copy_history_schema_name', 'copy_history', ['schema_name'])
    op.create_index('idx_copy_history_table_name', 'copy_history', ['table_name'])
    
    # Create task_history table
    op.create_table(
        'task_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('migration_id', sa.Integer(), nullable=False),
        sa.Column('migration_name', sa.String(255), nullable=True),
        sa.Column('task_arn', sa.String(500), nullable=False),
        sa.Column('execution_arn', sa.String(500), nullable=True),
        sa.Column('task_name', sa.String(255), nullable=True),
        sa.Column('task_type', sa.String(50), nullable=True),
        sa.Column('agent_arn', sa.String(500), nullable=False),
        sa.Column('agent_ip', sa.String(50), nullable=False),
        sa.Column('source_location_arn', sa.String(500), nullable=True),
        sa.Column('source_uri', sa.String(1000), nullable=False),
        sa.Column('dest_location_arn', sa.String(500), nullable=True),
        sa.Column('dest_uri', sa.String(1000), nullable=False),
        sa.Column('table_name', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='running'),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('files_transferred', sa.BigInteger(), nullable=True),
        sa.Column('bytes_transferred', sa.BigInteger(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(100), nullable=True),
        sa.Column('error_details', JSONB, nullable=True),
        sa.Column('raw_result', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for task_history
    op.create_index('idx_task_history_migration_id', 'task_history', ['migration_id'])
    op.create_index('idx_task_history_status', 'task_history', ['status'])
    op.create_index('idx_task_history_started_at', 'task_history', ['started_at'])
    op.create_index('idx_task_history_agent_ip', 'task_history', ['agent_ip'])
    op.create_index('idx_task_history_task_type', 'task_history', ['task_type'])
    
    # Create datasync_agents table
    op.create_table(
        'datasync_agents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('vm_ip', sa.String(50), nullable=False),
        sa.Column('agent_arn', sa.String(500), nullable=False),
        sa.Column('aws_region', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='unknown'),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create unique index on vm_ip for datasync_agents
    op.create_index('idx_datasync_agents_vm_ip', 'datasync_agents', ['vm_ip'], unique=True)
    op.create_index('idx_datasync_agents_workspace_id', 'datasync_agents', ['workspace_id'])
    op.create_index('idx_datasync_agents_status', 'datasync_agents', ['status'])
    
    # Create foreign key for datasync_agents
    op.create_foreign_key(
        'fk_datasync_agents_workspace_id',
        'datasync_agents', 'workspaces',
        ['workspace_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    # Drop tables in reverse order
    op.drop_table('datasync_agents')
    op.drop_table('task_history')
    op.drop_table('copy_history')
