"""create assessment indexes table

Revision ID: 029
Revises: 028
Create Date: 2026-03-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '029'
down_revision = '028'
branch_labels = None
depends_on = None


def upgrade():
    # Create assessment_indexes table
    op.create_table('assessment_indexes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assessment_id', sa.Integer(), nullable=False),
        sa.Column('table_id', sa.Integer(), nullable=True),
        sa.Column('schema_name', sa.String(length=255), nullable=True),
        sa.Column('table_name', sa.String(length=255), nullable=True),
        sa.Column('index_name', sa.String(length=255), nullable=False),
        sa.Column('index_type', sa.String(length=50), nullable=True),
        sa.Column('is_unique', sa.Boolean(), nullable=True),
        sa.Column('is_primary_key', sa.Boolean(), nullable=True),
        sa.Column('is_clustered', sa.Boolean(), nullable=True),
        sa.Column('key_columns', sa.Text(), nullable=True),
        sa.Column('included_columns', sa.Text(), nullable=True),
        sa.Column('filter_definition', sa.Text(), nullable=True),
        sa.Column('size_mb', sa.Float(), nullable=True),
        sa.Column('row_count', sa.BigInteger(), nullable=True),
        sa.Column('index_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('idx_assessment_indexes_assessment', 'assessment_indexes', ['assessment_id'])
    op.create_index('idx_assessment_indexes_table', 'assessment_indexes', ['table_id'])
    op.create_index('idx_assessment_indexes_name', 'assessment_indexes', ['index_name'])
    op.create_index(op.f('ix_assessment_indexes_id'), 'assessment_indexes', ['id'])


def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_assessment_indexes_id'), table_name='assessment_indexes')
    op.drop_index('idx_assessment_indexes_name', table_name='assessment_indexes')
    op.drop_index('idx_assessment_indexes_table', table_name='assessment_indexes')
    op.drop_index('idx_assessment_indexes_assessment', table_name='assessment_indexes')

    # Drop table
    op.drop_table('assessment_indexes')
