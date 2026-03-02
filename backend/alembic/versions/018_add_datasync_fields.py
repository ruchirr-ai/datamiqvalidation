"""add datasync and service account fields for Path B

Revision ID: 018
Revises: 6ffb69876d21
Create Date: 2026-02-28

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '018'
down_revision = '016_add_dependency_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Columns previously in 6ffb69876d21 (merged here to fix broken chain)
    op.add_column('migrations_bq_redshift', sa.Column('aws_access_key_id', sa.String(255), nullable=True))
    op.add_column('migrations_bq_redshift', sa.Column('aws_secret_access_key_encrypted', sa.Text(), nullable=True))
    op.add_column('migrations_bq_redshift', sa.Column('transfer_job_name', sa.String(500), nullable=True))
    op.add_column('migrations_bq_redshift', sa.Column('overwrite_existing_files', sa.String(10), nullable=True, server_default='false'))
    op.add_column('migrations_bq_redshift', sa.Column('delete_source_after_transfer', sa.String(10), nullable=True, server_default='false'))
    op.add_column('migrations_bq_redshift', sa.Column('last_run_at', sa.DateTime(), nullable=True))
    
    # Path B: AWS DataSync fields
    op.add_column('migrations_bq_redshift', sa.Column('datasync_subnet_id', sa.String(255), nullable=True))
    op.add_column('migrations_bq_redshift', sa.Column('datasync_security_group_id', sa.String(255), nullable=True))
    op.add_column('migrations_bq_redshift', sa.Column('datasync_instance_type', sa.String(50), nullable=True, server_default='m5.xlarge'))
    op.add_column('migrations_bq_redshift', sa.Column('gcs_access_key', sa.String(255), nullable=True))
    op.add_column('migrations_bq_redshift', sa.Column('gcs_secret_key_encrypted', sa.Text(), nullable=True))
    # GCS region for export
    op.add_column('migrations_bq_redshift', sa.Column('gcs_region', sa.String(100), nullable=True))
    # Service account JSON (encrypted) for BigQuery export
    op.add_column('migrations_bq_redshift', sa.Column('service_account_json_encrypted', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('migrations_bq_redshift', 'service_account_json_encrypted')
    op.drop_column('migrations_bq_redshift', 'gcs_region')
    op.drop_column('migrations_bq_redshift', 'gcs_secret_key_encrypted')
    op.drop_column('migrations_bq_redshift', 'gcs_access_key')
    op.drop_column('migrations_bq_redshift', 'datasync_instance_type')
    op.drop_column('migrations_bq_redshift', 'datasync_security_group_id')
    op.drop_column('migrations_bq_redshift', 'datasync_subnet_id')
