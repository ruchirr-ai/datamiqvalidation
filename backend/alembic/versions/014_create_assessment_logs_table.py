"""create assessment logs table

Revision ID: 014_create_assessment_logs
Revises: 013_add_assessment_name
Create Date: 2026-02-14

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '014_create_assessment_logs'
down_revision = '013_add_assessment_name'
branch_labels = None
depends_on = None


def upgrade():
    # Create assessment_logs table
    op.create_table(
        'assessment_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('log_level', sa.String(20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('stage', sa.String(100), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('stack_trace', sa.Text(), nullable=True),
        sa.Column('log_metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE')
    )
    
    # Create indexes
    op.create_index('idx_assessment_logs_assessment_id', 'assessment_logs', ['assessment_id'])
    op.create_index('idx_assessment_logs_created_at', 'assessment_logs', ['created_at'])
    op.create_index('idx_assessment_logs_log_level', 'assessment_logs', ['log_level'])


def downgrade():
    op.drop_index('idx_assessment_logs_log_level')
    op.drop_index('idx_assessment_logs_created_at')
    op.drop_index('idx_assessment_logs_assessment_id')
    op.drop_table('assessment_logs')
