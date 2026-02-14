"""add unique constraints to assessment tables

Revision ID: 015
Revises: 014
Create Date: 2026-02-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '015_add_unique_constraints'
down_revision = '014_create_assessment_logs'
branch_labels = None
depends_on = None


def upgrade():
    """Add unique constraints to prevent duplicate records"""
    
    # Add unique constraint to assessment_datasets
    op.create_index(
        'idx_assessment_datasets_unique',
        'assessment_datasets',
        ['assessment_id', 'dataset_name'],
        unique=True
    )
    
    # Add unique constraint to assessment_tables
    op.create_index(
        'idx_assessment_tables_unique',
        'assessment_tables',
        ['assessment_id', 'dataset_name', 'table_name'],
        unique=True
    )
    
    # Add unique constraint to assessment_columns
    op.create_index(
        'idx_assessment_columns_unique',
        'assessment_columns',
        ['assessment_id', 'table_id', 'column_name'],
        unique=True
    )
    
    # Add unique constraint to assessment_views
    op.create_index(
        'idx_assessment_views_unique',
        'assessment_views',
        ['assessment_id', 'view_name'],
        unique=True
    )
    
    # Add unique constraint to assessment_routines
    op.create_index(
        'idx_assessment_routines_unique',
        'assessment_routines',
        ['assessment_id', 'routine_name'],
        unique=True
    )
    
    # Add unique constraint to assessment_query_stats
    op.create_index(
        'idx_assessment_query_stats_unique',
        'assessment_query_stats',
        ['assessment_id', 'job_id'],
        unique=True
    )
    
    # Add unique constraint to assessment_ml_models
    op.create_index(
        'idx_assessment_ml_models_unique',
        'assessment_ml_models',
        ['assessment_id', 'model_name'],
        unique=True
    )
    
    # Add unique constraint to assessment_sharded_tables
    op.create_index(
        'idx_assessment_sharded_unique',
        'assessment_sharded_tables',
        ['assessment_id', 'shard_group'],
        unique=True
    )


def downgrade():
    """Remove unique constraints"""
    
    op.drop_index('idx_assessment_datasets_unique', table_name='assessment_datasets')
    op.drop_index('idx_assessment_tables_unique', table_name='assessment_tables')
    op.drop_index('idx_assessment_columns_unique', table_name='assessment_columns')
    op.drop_index('idx_assessment_views_unique', table_name='assessment_views')
    op.drop_index('idx_assessment_routines_unique', table_name='assessment_routines')
    op.drop_index('idx_assessment_query_stats_unique', table_name='assessment_query_stats')
    op.drop_index('idx_assessment_ml_models_unique', table_name='assessment_ml_models')
    op.drop_index('idx_assessment_sharded_unique', table_name='assessment_sharded_tables')
