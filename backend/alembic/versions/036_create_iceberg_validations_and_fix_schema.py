"""create iceberg_table_validations and fix migrations_bq_iceberg schema

This migration is a catch-up migration for environments where 035 was applied
manually (e.g. directly via SQL on EC2) and may be missing:
  - iceberg_table_validations table (required for cascade delete in the delete endpoint)
  - unique constraint on migrations_bq_iceberg(workspace_id, migration_name)
  - migration_logs table (if not already present from other migrations)

Revision ID: 036
Revises: 035
Create Date: 2026-07-14

NOTE: Due to duplicate revision 035 in the codebase, run this migration manually:
  cd backend && python -c "
  from alembic.config import Config
  from alembic import command
  alembic_cfg = Config('alembic.ini')
  # Or run upgrade() directly
  "
  
  Or apply directly via psql / Python:
  from alembic.versions.036_create_iceberg_validations_and_fix_schema import upgrade

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = '036'
down_revision = '035'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # -------------------------------------------------------------------------
    # 1. Create iceberg_table_validations if it doesn't exist
    # -------------------------------------------------------------------------
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = 'iceberg_table_validations'"
    ))
    if not result.fetchone():
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
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(
                ['migration_id'],
                ['migrations_bq_iceberg.id'],
                ondelete='CASCADE',
            ),
            sa.UniqueConstraint(
                'migration_id', 'table_name',
                name='unique_iceberg_validation',
            ),
        )
        op.create_index(
            'idx_iceberg_validation_migration_id',
            'iceberg_table_validations',
            ['migration_id'],
        )

    # -------------------------------------------------------------------------
    # 2. Add unique constraint on migrations_bq_iceberg(workspace_id, migration_name)
    #    if it doesn't already exist
    # -------------------------------------------------------------------------
    result2 = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.table_constraints "
        "WHERE table_name = 'migrations_bq_iceberg' "
        "AND constraint_name = 'unique_migration_name_per_workspace'"
    ))
    if not result2.fetchone():
        op.create_unique_constraint(
            'unique_migration_name_per_workspace',
            'migrations_bq_iceberg',
            ['workspace_id', 'migration_name'],
        )

    # -------------------------------------------------------------------------
    # 3. Create migration_logs table if it doesn't exist
    #    (needed by the delete_migration endpoint)
    # -------------------------------------------------------------------------
    result3 = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = 'migration_logs'"
    ))
    if not result3.fetchone():
        op.create_table(
            'migration_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('migration_id', sa.Integer(), nullable=False),
            sa.Column('migration_type', sa.String(50), nullable=True),
            sa.Column('stage', sa.String(50), nullable=True),
            sa.Column('level', sa.String(20), nullable=True, server_default='INFO'),
            sa.Column('message', sa.Text(), nullable=True),
            sa.Column('extra_data', JSONB, nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('idx_migration_logs_migration_id', 'migration_logs', ['migration_id'])
        op.create_index('idx_migration_logs_created_at', 'migration_logs', ['created_at'])


def downgrade() -> None:
    conn = op.get_bind()

    # Only drop if we created them (check existence)
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name='iceberg_table_validations'"
    ))
    if result.fetchone():
        op.drop_table('iceberg_table_validations')

    result2 = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.table_constraints "
        "WHERE constraint_name='unique_migration_name_per_workspace'"
    ))
    if result2.fetchone():
        op.drop_constraint(
            'unique_migration_name_per_workspace',
            'migrations_bq_iceberg',
            type_='unique',
        )
