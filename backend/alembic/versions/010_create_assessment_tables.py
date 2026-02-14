"""create assessment tables

Revision ID: 010_create_assessment_tables
Revises: 009
Create Date: 2026-02-09 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '010_create_assessment_tables'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    # Create assessments table
    op.create_table(
        'assessments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('connection_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('started_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('total_datasets', sa.Integer(), server_default='0'),
        sa.Column('total_tables', sa.Integer(), server_default='0'),
        sa.Column('total_views', sa.Integer(), server_default='0'),
        sa.Column('total_routines', sa.Integer(), server_default='0'),
        sa.Column('total_ml_models', sa.Integer(), server_default='0'),
        sa.Column('total_size_mb', sa.BigInteger(), server_default='0'),
        sa.Column('assessment_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_by', sa.String(255), nullable=True),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['connection_id'], ['connections.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_assessments_connection', 'assessments', ['connection_id'])
    op.create_index('idx_assessments_workspace', 'assessments', ['workspace_id'])
    op.create_index('idx_assessments_status', 'assessments', ['status'])
    
    # Create assessment_datasets table
    op.create_table(
        'assessment_datasets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('dataset_name', sa.String(255), nullable=False),
        sa.Column('creation_time', sa.TIMESTAMP(), nullable=True),
        sa.Column('location', sa.String(100), nullable=True),
        sa.Column('table_count', sa.Integer(), server_default='0'),
        sa.Column('total_size_mb', sa.BigInteger(), server_default='0'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_assessment_datasets_assessment', 'assessment_datasets', ['assessment_id'])
    
    # Create assessment_tables table
    op.create_table(
        'assessment_tables',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.String(255), nullable=False),
        sa.Column('dataset_name', sa.String(255), nullable=False),
        sa.Column('table_name', sa.String(255), nullable=False),
        sa.Column('table_type', sa.String(50), nullable=True),
        sa.Column('creation_time', sa.TIMESTAMP(), nullable=True),
        sa.Column('row_count', sa.BigInteger(), nullable=True),
        sa.Column('size_mb', sa.BigInteger(), nullable=True),
        sa.Column('partitioning_columns', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('clustering_columns', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('has_column_security', sa.Boolean(), server_default='false'),
        sa.Column('has_row_security', sa.Boolean(), server_default='false'),
        sa.Column('is_sharded', sa.Boolean(), server_default='false'),
        sa.Column('shard_group', sa.String(255), nullable=True),
        sa.Column('update_frequency', sa.String(50), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_assessment_tables_assessment', 'assessment_tables', ['assessment_id'])
    op.create_index('idx_assessment_tables_dataset', 'assessment_tables', ['dataset_name'])
    op.create_index('idx_assessment_tables_sharded', 'assessment_tables', ['is_sharded'])
    
    # Create assessment_columns table
    op.create_table(
        'assessment_columns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('table_id', sa.Integer(), nullable=False),
        sa.Column('column_name', sa.String(255), nullable=False),
        sa.Column('data_type', sa.String(100), nullable=False),
        sa.Column('is_nullable', sa.Boolean(), server_default='true'),
        sa.Column('ordinal_position', sa.Integer(), nullable=True),
        sa.Column('is_partitioning_column', sa.Boolean(), server_default='false'),
        sa.Column('clustering_ordinal_position', sa.Integer(), nullable=True),
        sa.Column('policy_tags', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('max_length', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['table_id'], ['assessment_tables.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_assessment_columns_assessment', 'assessment_columns', ['assessment_id'])
    op.create_index('idx_assessment_columns_table', 'assessment_columns', ['table_id'])
    
    # Create assessment_views table
    op.create_table(
        'assessment_views',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('view_name', sa.String(255), nullable=False),
        sa.Column('view_type', sa.String(50), nullable=True),
        sa.Column('view_definition', sa.Text(), nullable=True),
        sa.Column('creation_time', sa.TIMESTAMP(), nullable=True),
        sa.Column('dependencies', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_assessment_views_assessment', 'assessment_views', ['assessment_id'])
    
    # Create assessment_routines table
    op.create_table(
        'assessment_routines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('routine_name', sa.String(255), nullable=False),
        sa.Column('routine_type', sa.String(50), nullable=True),
        sa.Column('return_type', sa.String(100), nullable=True),
        sa.Column('definition', sa.Text(), nullable=True),
        sa.Column('external_language', sa.String(50), nullable=True),
        sa.Column('creation_time', sa.TIMESTAMP(), nullable=True),
        sa.Column('call_frequency', sa.Integer(), server_default='0'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_assessment_routines_assessment', 'assessment_routines', ['assessment_id'])
    
    # Create assessment_query_stats table
    op.create_table(
        'assessment_query_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.String(255), nullable=True),
        sa.Column('execution_time', sa.TIMESTAMP(), nullable=True),
        sa.Column('query_text', sa.Text(), nullable=True),
        sa.Column('bytes_scanned', sa.BigInteger(), nullable=True),
        sa.Column('slot_milliseconds', sa.BigInteger(), nullable=True),
        sa.Column('cache_hit', sa.Boolean(), nullable=True),
        sa.Column('referenced_tables', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('user_email', sa.String(255), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_assessment_query_stats_assessment', 'assessment_query_stats', ['assessment_id'])
    
    # Create assessment_ml_models table
    op.create_table(
        'assessment_ml_models',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(255), nullable=False),
        sa.Column('model_type', sa.String(100), nullable=True),
        sa.Column('dataset_name', sa.String(255), nullable=True),
        sa.Column('creation_time', sa.TIMESTAMP(), nullable=True),
        sa.Column('last_modified_time', sa.TIMESTAMP(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_assessment_ml_models_assessment', 'assessment_ml_models', ['assessment_id'])
    
    # Create assessment_security table
    op.create_table(
        'assessment_security',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('security_type', sa.String(50), nullable=True),
        sa.Column('table_name', sa.String(255), nullable=True),
        sa.Column('policy_name', sa.String(255), nullable=True),
        sa.Column('filter_predicate', sa.Text(), nullable=True),
        sa.Column('grantees', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('creation_time', sa.TIMESTAMP(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_assessment_security_assessment', 'assessment_security', ['assessment_id'])
    op.create_index('idx_assessment_security_type', 'assessment_security', ['security_type'])
    
    # Create assessment_sharded_tables table
    op.create_table(
        'assessment_sharded_tables',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('shard_group', sa.String(255), nullable=False),
        sa.Column('table_prefix', sa.String(255), nullable=False),
        sa.Column('shard_count', sa.Integer(), server_default='0'),
        sa.Column('total_size_mb', sa.BigInteger(), server_default='0'),
        sa.Column('date_range_start', sa.TIMESTAMP(), nullable=True),
        sa.Column('date_range_end', sa.TIMESTAMP(), nullable=True),
        sa.Column('shard_tables', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_assessment_sharded_assessment', 'assessment_sharded_tables', ['assessment_id'])


def downgrade():
    # Drop tables in reverse order
    op.drop_table('assessment_sharded_tables')
    op.drop_table('assessment_security')
    op.drop_table('assessment_ml_models')
    op.drop_table('assessment_query_stats')
    op.drop_table('assessment_routines')
    op.drop_table('assessment_views')
    op.drop_table('assessment_columns')
    op.drop_table('assessment_tables')
    op.drop_table('assessment_datasets')
    op.drop_table('assessments')
