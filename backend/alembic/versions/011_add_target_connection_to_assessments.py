"""add target connection to assessments

Revision ID: 011_add_target_connection
Revises: 010_create_assessment_tables
Create Date: 2026-02-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '011_add_target_connection'
down_revision = '010_create_assessment_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Rename connection_id to source_connection_id
    op.alter_column('assessments', 'connection_id',
                    new_column_name='source_connection_id',
                    existing_type=sa.Integer(),
                    existing_nullable=False)
    
    # Add target_connection_id column
    op.add_column('assessments',
                  sa.Column('target_connection_id', sa.Integer(), nullable=True))
    
    # Add foreign key constraint for target_connection_id
    op.create_foreign_key('fk_assessments_target_connection',
                         'assessments', 'connections',
                         ['target_connection_id'], ['id'])
    
    # Update index name
    op.drop_index('idx_assessments_connection', 'assessments')
    op.create_index('idx_assessments_source_connection', 'assessments', ['source_connection_id'])
    op.create_index('idx_assessments_target_connection', 'assessments', ['target_connection_id'])


def downgrade():
    # Drop new index and foreign key
    op.drop_index('idx_assessments_target_connection', 'assessments')
    op.drop_index('idx_assessments_source_connection', 'assessments')
    op.drop_constraint('fk_assessments_target_connection', 'assessments', type_='foreignkey')
    
    # Remove target_connection_id column
    op.drop_column('assessments', 'target_connection_id')
    
    # Rename source_connection_id back to connection_id
    op.alter_column('assessments', 'source_connection_id',
                    new_column_name='connection_id',
                    existing_type=sa.Integer(),
                    existing_nullable=False)
    
    # Recreate original index
    op.create_index('idx_assessments_connection', 'assessments', ['connection_id'])
