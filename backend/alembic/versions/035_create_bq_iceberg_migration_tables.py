"""create bq iceberg migration tables

Revision ID: 035
Revises: 034
Create Date: 2026-05-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

# revision identifiers, used by Alembic.
revision = '035'
down_revision = '034'
branch_labels = None
depends_on = None


def upgrade():
    # Create migrations_bq_iceberg table
    op.create_table(
        'migrations_bq_iceberg',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('migration_name', sa.String(255), nullable=False),
        sa.Column('pathway', sa.String(10), nullable=False),

        # Source Configuration (BigQuery)
        sa.Column('source_connection_id', sa.Integer(), nullable=True),
        sa.Column('source_project_id', sa.String(255), nullable=True),
        sa.Column('source_dataset', sa.String(255), nullable=True),
        sa.Column('source_tables', ARRAY(sa.Text), nullable=True),

        # Target Configuration (Iceberg)
        sa.Column('target_connection_id', sa.Integer(), nullable=True),
        sa.Column('destination_type', sa.String(50), nullable=False),
        sa.Column('s3_bucket', sa.String(255), nullable=True),
        sa.Column('s3_path_prefix', sa.String(512), nullable=True),
        sa.Column('table_bucket_arn', sa.String(500), nullable=True),
        sa.Column('s3_tables_namespace', sa.String(255), nullable=True),
        sa.Column('aws_region', sa.String(50), nullable=False),
        sa.Column('glue_database_name', sa.String(255), nullable=False),
        sa.Column('dataset_to_db_mapping', JSONB, nullable=True),

        # AWS Credentials (access keys OR role ARN)
        sa.Column('aws_access_key_id', sa.String(255), nullable=True),
        sa.Column('aws_secret_access_key_encrypted', sa.Text(), nullable=True),
        sa.Column('aws_role_arn', sa.String(500), nullable=True),

        # Intermediate Storage
        sa.Column('gcs_bucket', sa.String(255), nullable=True),
        sa.Column('gcs_path', sa.String(500), nullable=True),
        sa.Column('gcs_region', sa.String(100), nullable=True),
        sa.Column('export_format', sa.String(50), nullable=True, server_default='PARQUET'),
        sa.Column('compression', sa.String(50), nullable=True, server_default='ZSTD'),
        sa.Column('service_account_json_encrypted', sa.Text(), nullable=True),

        # Load Configuration
        sa.Column('load_type', sa.String(20), nullable=True, server_default='full'),
        sa.Column('table_load_configs', JSONB, nullable=True),
        sa.Column('parallelism', sa.Integer(), nullable=True, server_default='4'),
        sa.Column('enable_load_stage_verification', sa.Boolean(), nullable=True, server_default='false'),

        # State Management
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('current_stage', sa.String(50), nullable=True),
        sa.Column('checkpoint_data', JSONB, nullable=True),
        sa.Column('resume_point', sa.String(100), nullable=True),

        # Structure Review
        sa.Column('structure_report', JSONB, nullable=True),
        sa.Column('cost_analysis_report', JSONB, nullable=True),
        sa.Column('structure_approved_at', sa.DateTime(), nullable=True),
        sa.Column('structure_approved_by', sa.Integer(), nullable=True),

        # Scheduling
        sa.Column('schedule_type', sa.String(50), nullable=True),
        sa.Column('cron_expression', sa.String(100), nullable=True),
        sa.Column('next_run_time', sa.DateTime(), nullable=True),

        # Metrics
        sa.Column('total_rows_source', sa.BigInteger(), nullable=True),
        sa.Column('total_rows_target', sa.BigInteger(), nullable=True),
        sa.Column('total_bytes_transferred', sa.BigInteger(), nullable=True),
        sa.Column('progress_percentage', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),

        # Metadata
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),

        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "destination_type IN ('iceberg_s3', 'iceberg_s3_tables')",
            name='check_iceberg_dest_type'
        ),
        sa.CheckConstraint(
            "pathway IN ('A', 'B', 'C')",
            name='check_iceberg_pathway'
        ),
        sa.CheckConstraint(
            "parallelism >= 1 AND parallelism <= 16",
            name='check_parallelism_range'
        ),
    )

    # Create indexes on migrations_bq_iceberg
    op.create_index('idx_bq_iceberg_workspace_id', 'migrations_bq_iceberg', ['workspace_id'])
    op.create_index('idx_bq_iceberg_status', 'migrations_bq_iceberg', ['status'])
    op.create_index('idx_bq_iceberg_destination_type', 'migrations_bq_iceberg', ['destination_type'])

    # Create iceberg_table_validations table
    op.create_table(
        'iceberg_table_validations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('migration_id', sa.Integer(), nullable=False),
        sa.Column('table_name', sa.String(255), nullable=False),
        sa.Column('source_row_count', sa.BigInteger(), nullable=True),
        sa.Column('target_row_count', sa.BigInteger(), nullable=True),
        sa.Column('match_status', sa.String(50), nullable=True),
        sa.Column('validation_type', sa.String(20), nullable=True),
        sa.Column('batch_export_count', sa.BigInteger(), nullable=True),
        sa.Column('previous_snapshot_count', sa.BigInteger(), nullable=True),
        sa.Column('error_reason', sa.Text(), nullable=True),
        sa.Column('validated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),

        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['migration_id'],
            ['migrations_bq_iceberg.id'],
            ondelete='CASCADE'
        ),
        sa.UniqueConstraint('migration_id', 'table_name', name='unique_iceberg_validation'),
    )

    # Create index on iceberg_table_validations
    op.create_index('idx_iceberg_validation_migration_id', 'iceberg_table_validations', ['migration_id'])


def downgrade():
    op.drop_table('iceberg_table_validations')
    op.drop_table('migrations_bq_iceberg')
