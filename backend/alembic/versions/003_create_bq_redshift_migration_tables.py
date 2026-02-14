"""create bq redshift migration tables

Revision ID: 003
Revises: 002
Create Date: 2026-02-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Create migrations_bq_redshift table
    op.create_table(
        'migrations_bq_redshift',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('migration_name', sa.String(255), nullable=False),
        sa.Column('pathway', sa.String(10), nullable=False),
        
        # Source Configuration
        sa.Column('source_connection_id', sa.Integer(), nullable=True),
        sa.Column('source_project_id', sa.String(255), nullable=True),
        sa.Column('source_dataset', sa.String(255), nullable=True),
        sa.Column('source_tables', ARRAY(sa.Text), nullable=True),
        
        # Target Configuration
        sa.Column('target_connection_id', sa.Integer(), nullable=True),
        sa.Column('target_cluster', sa.String(255), nullable=True),
        sa.Column('target_database', sa.String(255), nullable=True),
        sa.Column('target_schema', sa.String(255), nullable=True),
        
        # Intermediate Storage
        sa.Column('gcs_bucket', sa.String(255), nullable=True),
        sa.Column('gcs_path', sa.String(500), nullable=True),
        sa.Column('s3_bucket', sa.String(255), nullable=True),
        sa.Column('s3_path', sa.String(500), nullable=True),
        
        # State Management
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('current_stage', sa.String(50), nullable=True),
        sa.Column('checkpoint_data', JSONB, nullable=True),
        sa.Column('manifest_uri', sa.Text(), nullable=True),
        sa.Column('resume_point', sa.String(100), nullable=True),
        
        # Scheduling
        sa.Column('schedule_type', sa.String(50), nullable=True),
        sa.Column('cron_expression', sa.String(100), nullable=True),
        sa.Column('next_run_time', sa.DateTime(), nullable=True),
        
        # Metrics
        sa.Column('total_rows_source', sa.BigInteger(), nullable=True),
        sa.Column('total_rows_target', sa.BigInteger(), nullable=True),
        sa.Column('total_bytes_transferred', sa.BigInteger(), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        
        # Metadata
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint("pathway IN ('A', 'B', 'C', 'D')", name='check_pathway'),
        sa.UniqueConstraint('workspace_id', 'migration_name', name='unique_migration_per_workspace')
    )
    
    # Create indexes
    op.create_index('idx_migrations_bq_redshift_workspace', 'migrations_bq_redshift', ['workspace_id'])
    op.create_index('idx_migrations_bq_redshift_status', 'migrations_bq_redshift', ['status'])
    op.create_index('idx_migrations_bq_redshift_next_run', 'migrations_bq_redshift', ['next_run_time'])
    
    # Create migration_shards table
    op.create_table(
        'migration_shards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('migration_id', sa.Integer(), nullable=False),
        sa.Column('shard_index', sa.Integer(), nullable=False),
        sa.Column('table_name', sa.String(255), nullable=False),
        
        # Shard Details
        sa.Column('gcs_uri', sa.Text(), nullable=True),
        sa.Column('s3_uri', sa.Text(), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('row_count', sa.BigInteger(), nullable=True),
        sa.Column('checksum', sa.String(64), nullable=True),
        
        # Status Tracking
        sa.Column('export_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('export_completed_at', sa.DateTime(), nullable=True),
        sa.Column('transfer_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('transfer_completed_at', sa.DateTime(), nullable=True),
        sa.Column('load_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('load_completed_at', sa.DateTime(), nullable=True),
        
        # Error Handling
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_error_time', sa.DateTime(), nullable=True),
        
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['migration_id'], ['migrations_bq_redshift.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('migration_id', 'table_name', 'shard_index', name='unique_shard_per_migration')
    )
    
    # Create indexes
    op.create_index('idx_migration_shards_migration', 'migration_shards', ['migration_id'])
    op.create_index('idx_migration_shards_status', 'migration_shards', 
                    ['migration_id', 'export_status', 'transfer_status', 'load_status'])
    
    # Create migration_logs table
    op.create_table(
        'migration_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('migration_id', sa.Integer(), nullable=False),
        sa.Column('shard_id', sa.Integer(), nullable=True),
        
        sa.Column('log_level', sa.String(20), nullable=False),
        sa.Column('stage', sa.String(50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        sa.Column('metadata', JSONB, nullable=True),
        
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['migration_id'], ['migrations_bq_redshift.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shard_id'], ['migration_shards.id'], ondelete='SET NULL')
    )
    
    # Create indexes
    op.create_index('idx_migration_logs_migration', 'migration_logs', ['migration_id'])
    op.create_index('idx_migration_logs_level', 'migration_logs', ['log_level'])
    op.create_index('idx_migration_logs_created', 'migration_logs', ['created_at'])


def downgrade():
    op.drop_table('migration_logs')
    op.drop_table('migration_shards')
    op.drop_table('migrations_bq_redshift')
