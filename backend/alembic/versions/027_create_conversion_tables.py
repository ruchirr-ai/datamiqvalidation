"""create conversion tables

Revision ID: 019
Revises: 018
Create Date: 2026-03-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '027'
down_revision = '026'
branch_labels = None
depends_on = None


def upgrade():
    # Tables may already exist from a previous branch migration — skip if so
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT tablename FROM pg_tables WHERE tablename='conversion_batches'"
    ))
    if result.fetchone() is not None:
        return

    # Create conversion_batches table
    op.create_table(
        'conversion_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('migration_project_id', sa.Integer(), nullable=True),
        sa.Column('source_connection_id', sa.Integer(), nullable=False),
        sa.Column('target_connection_id', sa.Integer(), nullable=False),
        sa.Column('bedrock_model', sa.String(255), nullable=True),
        sa.Column('aws_region', sa.String(50), nullable=True),
        sa.Column('prompt_template_path', sa.String(500), nullable=True),
        sa.Column('use_sqlglot', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('total_assets', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_assets', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_assets', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for conversion_batches
    op.create_index('idx_conversion_batches_workspace_id', 'conversion_batches', ['workspace_id'])
    op.create_index('idx_conversion_batches_status', 'conversion_batches', ['status'])
    op.create_index('idx_conversion_batches_migration_project_id', 'conversion_batches', ['migration_project_id'])
    
    # Create foreign keys for conversion_batches
    op.create_foreign_key(
        'fk_conversion_batches_workspace_id',
        'conversion_batches', 'workspaces',
        ['workspace_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_conversion_batches_source_connection_id',
        'conversion_batches', 'connections',
        ['source_connection_id'], ['id'],
        ondelete='RESTRICT'
    )
    op.create_foreign_key(
        'fk_conversion_batches_target_connection_id',
        'conversion_batches', 'connections',
        ['target_connection_id'], ['id'],
        ondelete='RESTRICT'
    )
    op.create_foreign_key(
        'fk_conversion_batches_created_by',
        'conversion_batches', 'users',
        ['created_by'], ['id'],
        ondelete='SET NULL'
    )
    
    # Create conversion_jobs table
    op.create_table(
        'conversion_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=True),
        sa.Column('source_code', sa.Text(), nullable=False),
        sa.Column('target_code', sa.Text(), nullable=True),
        sa.Column('source_dialect', sa.String(50), nullable=False),
        sa.Column('target_dialect', sa.String(50), nullable=False),
        sa.Column('asset_type', sa.String(50), nullable=False),
        sa.Column('asset_name', sa.String(255), nullable=True),
        sa.Column('bedrock_model', sa.String(255), nullable=True),
        sa.Column('aws_region', sa.String(50), nullable=True),
        sa.Column('prompt_template_path', sa.String(500), nullable=True),
        sa.Column('use_sqlglot', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sqlglot_success', sa.Boolean(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for conversion_jobs
    op.create_index('idx_conversion_jobs_workspace_id', 'conversion_jobs', ['workspace_id'])
    op.create_index('idx_conversion_jobs_batch_id', 'conversion_jobs', ['batch_id'])
    op.create_index('idx_conversion_jobs_status', 'conversion_jobs', ['status'])
    op.create_index('idx_conversion_jobs_asset_type', 'conversion_jobs', ['asset_type'])
    op.create_index('idx_conversion_jobs_created_at', 'conversion_jobs', ['created_at'])
    
    # Create foreign keys for conversion_jobs
    op.create_foreign_key(
        'fk_conversion_jobs_workspace_id',
        'conversion_jobs', 'workspaces',
        ['workspace_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_conversion_jobs_batch_id',
        'conversion_jobs', 'conversion_batches',
        ['batch_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_foreign_key(
        'fk_conversion_jobs_created_by',
        'conversion_jobs', 'users',
        ['created_by'], ['id'],
        ondelete='SET NULL'
    )
    
    # Create conversion_logs table
    op.create_table(
        'conversion_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('log_level', sa.String(20), nullable=False, server_default='INFO'),
        sa.Column('step_name', sa.String(100), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for conversion_logs
    op.create_index('idx_conversion_logs_job_id', 'conversion_logs', ['job_id'])
    op.create_index('idx_conversion_logs_workspace_id', 'conversion_logs', ['workspace_id'])
    op.create_index('idx_conversion_logs_timestamp', 'conversion_logs', ['timestamp'])
    
    # Create foreign keys for conversion_logs
    op.create_foreign_key(
        'fk_conversion_logs_job_id',
        'conversion_logs', 'conversion_jobs',
        ['job_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_conversion_logs_workspace_id',
        'conversion_logs', 'workspaces',
        ['workspace_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table('conversion_logs')
    op.drop_table('conversion_jobs')
    op.drop_table('conversion_batches')
