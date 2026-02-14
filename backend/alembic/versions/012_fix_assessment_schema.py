"""fix assessment schema

Revision ID: 012_fix_assessment_schema
Revises: 011_add_target_connection
Create Date: 2026-02-14 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '012_fix_assessment_schema'
down_revision = '011_add_target_connection'
branch_labels = None
depends_on = None


def upgrade():
    # Rename metadata columns to match model names
    op.alter_column('assessment_datasets', 'metadata', new_column_name='dataset_metadata')
    op.alter_column('assessment_tables', 'metadata', new_column_name='table_metadata')
    op.alter_column('assessment_columns', 'metadata', new_column_name='column_metadata')
    op.alter_column('assessment_views', 'metadata', new_column_name='view_metadata')
    op.alter_column('assessment_routines', 'metadata', new_column_name='routine_metadata')
    op.alter_column('assessment_query_stats', 'metadata', new_column_name='query_metadata')
    op.alter_column('assessment_ml_models', 'metadata', new_column_name='model_metadata')
    op.alter_column('assessment_security', 'metadata', new_column_name='security_metadata')
    op.alter_column('assessment_sharded_tables', 'metadata', new_column_name='shard_metadata')


def downgrade():
    # Revert column names
    op.alter_column('assessment_datasets', 'dataset_metadata', new_column_name='metadata')
    op.alter_column('assessment_tables', 'table_metadata', new_column_name='metadata')
    op.alter_column('assessment_columns', 'column_metadata', new_column_name='metadata')
    op.alter_column('assessment_views', 'view_metadata', new_column_name='metadata')
    op.alter_column('assessment_routines', 'routine_metadata', new_column_name='metadata')
    op.alter_column('assessment_query_stats', 'query_metadata', new_column_name='metadata')
    op.alter_column('assessment_ml_models', 'model_metadata', new_column_name='metadata')
    op.alter_column('assessment_security', 'security_metadata', new_column_name='metadata')
    op.alter_column('assessment_sharded_tables', 'shard_metadata', new_column_name='metadata')
