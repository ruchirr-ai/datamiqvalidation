"""add assessment name

Revision ID: 013_add_assessment_name
Revises: 012_fix_assessment_schema
Create Date: 2026-02-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '013_add_assessment_name'
down_revision = '012_fix_assessment_schema'
branch_labels = None
depends_on = None


def upgrade():
    # Add name column to assessments table
    op.add_column('assessments',
                  sa.Column('name', sa.String(255), nullable=True))
    
    # Update existing assessments with a default name
    op.execute("UPDATE assessments SET name = 'Assessment ' || id WHERE name IS NULL")
    
    # Make name column non-nullable after setting defaults
    op.alter_column('assessments', 'name', nullable=False)
    
    # Add index on name for searching
    op.create_index('idx_assessments_name', 'assessments', ['name'])


def downgrade():
    # Drop index and column
    op.drop_index('idx_assessments_name', 'assessments')
    op.drop_column('assessments', 'name')
