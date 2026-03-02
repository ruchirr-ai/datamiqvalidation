"""add_missing_migration_columns

Revision ID: 6ffb69876d21
Revises: 017
Create Date: 2026-02-28 16:35:07.828655

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6ffb69876d21'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing columns to migrations_bq_redshift table
    op.add_column('migrations_bq_redshift', sa.Column('aws_access_key_id', sa.String(255), nullable=True))
    op.add_column('migrations_bq_redshift', sa.Column('aws_secret_access_key_encrypted', sa.Text(), nullable=True))
    op.add_column('migrations_bq_redshift', sa.Column('transfer_job_name', sa.String(500), nullable=True))
    op.add_column('migrations_bq_redshift', sa.Column('overwrite_existing_files', sa.String(10), nullable=True, server_default='false'))
    op.add_column('migrations_bq_redshift', sa.Column('delete_source_after_transfer', sa.String(10), nullable=True, server_default='false'))
    op.add_column('migrations_bq_redshift', sa.Column('last_run_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove the added columns
    op.drop_column('migrations_bq_redshift', 'last_run_at')
    op.drop_column('migrations_bq_redshift', 'delete_source_after_transfer')
    op.drop_column('migrations_bq_redshift', 'overwrite_existing_files')
    op.drop_column('migrations_bq_redshift', 'transfer_job_name')
    op.drop_column('migrations_bq_redshift', 'aws_secret_access_key_encrypted')
    op.drop_column('migrations_bq_redshift', 'aws_access_key_id')
