"""Add dependency fields to views and routines

Revision ID: 016_add_dependency_fields
Revises: 015
Create Date: 2026-02-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '016_add_dependency_fields'
down_revision = '015_add_unique_constraints'  # Update this to your latest migration
branch_labels = None
depends_on = None


def upgrade():
    # Add dependency fields to assessment_views
    op.add_column('assessment_views', 
        sa.Column('dependent_tables', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('assessment_views', 
        sa.Column('dependent_views', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('assessment_views', 
        sa.Column('dependent_functions', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('assessment_views', 
        sa.Column('dependency_depth', sa.Integer(), nullable=True))
    
    # Add dependency fields to assessment_routines
    op.add_column('assessment_routines', 
        sa.Column('dependent_tables', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('assessment_routines', 
        sa.Column('dependent_views', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('assessment_routines', 
        sa.Column('dependent_functions', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('assessment_routines', 
        sa.Column('calls_procedures', postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column('assessment_routines', 
        sa.Column('dependency_depth', sa.Integer(), nullable=True))


def downgrade():
    # Remove dependency fields from assessment_routines
    op.drop_column('assessment_routines', 'dependency_depth')
    op.drop_column('assessment_routines', 'calls_procedures')
    op.drop_column('assessment_routines', 'dependent_functions')
    op.drop_column('assessment_routines', 'dependent_views')
    op.drop_column('assessment_routines', 'dependent_tables')
    
    # Remove dependency fields from assessment_views
    op.drop_column('assessment_views', 'dependency_depth')
    op.drop_column('assessment_views', 'dependent_functions')
    op.drop_column('assessment_views', 'dependent_views')
    op.drop_column('assessment_views', 'dependent_tables')
