"""create validation tables

Revision ID: 031
Revises: 030
Create Date: 2026-03-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '031'
down_revision = '030'
branch_labels = None
depends_on = None


def upgrade():
    # Skip if tables already exist from a previous branch migration
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT tablename FROM pg_tables WHERE tablename='validation_runs'"
    ))
    if result.fetchone() is not None:
        return

    # Create validation_runs table first (referenced by FK)
    op.create_table(
        'validation_runs',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('migration_id', sa.Integer(), nullable=False),
        sa.Column('source_connection_id', sa.Integer(), nullable=False),
        sa.Column('target_connection_id', sa.Integer(), nullable=False),
        sa.Column('bedrock_model', sa.String(255), nullable=True),
        sa.Column('batch_size', sa.Integer(), nullable=False, server_default='10000'),
        sa.Column('type_mapping_overrides', JSONB(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('progress_percentage', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tables_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tables_passed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tables_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tables_error', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for validation_runs
    op.create_index('idx_validation_runs_workspace', 'validation_runs', ['workspace_id'])
    op.create_index('idx_validation_runs_migration', 'validation_runs', ['migration_id'])
    op.create_index('idx_validation_runs_status', 'validation_runs', ['status'])

    # Create validation_table_results table (references validation_runs)
    op.create_table(
        'validation_table_results',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('table_name', sa.String(255), nullable=False),
        sa.Column('dataset_name', sa.String(255), nullable=True),
        sa.Column('ddl_status', sa.String(50), nullable=True),
        sa.Column('ddl_comparison_result', JSONB(), nullable=True),
        sa.Column('row_count_status', sa.String(50), nullable=True),
        sa.Column('row_count_result', JSONB(), nullable=True),
        sa.Column('data_match_status', sa.String(50), nullable=True),
        sa.Column('data_match_result', JSONB(), nullable=True),
        sa.Column('ai_analysis', JSONB(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['run_id'], ['validation_runs.id'], ondelete='CASCADE')
    )

    # Create indexes for validation_table_results
    op.create_index('idx_vtresults_run', 'validation_table_results', ['run_id'])
    op.create_index('idx_vtresults_workspace', 'validation_table_results', ['workspace_id'])
    op.create_index('idx_vtresults_table_name', 'validation_table_results', ['table_name'])
    op.create_index('idx_vtresults_status', 'validation_table_results', ['status'])


def downgrade():
    # Drop tables in reverse order (respecting foreign key constraints)
    op.drop_table('validation_table_results')
    op.drop_table('validation_runs')
