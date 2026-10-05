"""Increase VARCHAR limits for columns that can overflow

Revision ID: 035
Revises: 034
"""
from alembic import op
import sqlalchemy as sa

revision = '035b'
down_revision = '035'
branch_labels = None
depends_on = None


def upgrade():
    # data_type can be very long for nested STRUCT/ARRAY types in BigQuery
    op.alter_column('assessment_columns', 'data_type', type_=sa.String(500), existing_type=sa.String(100))
    # location can be long region names
    op.alter_column('assessment_datasets', 'location', type_=sa.String(255), existing_type=sa.String(100))
    # return_type can be complex
    op.alter_column('assessment_routines', 'return_type', type_=sa.String(500), existing_type=sa.String(100))
    # model_type
    op.alter_column('assessment_ml_models', 'model_type', type_=sa.String(255), existing_type=sa.String(100))


def downgrade():
    op.alter_column('assessment_columns', 'data_type', type_=sa.String(100), existing_type=sa.String(500))
    op.alter_column('assessment_datasets', 'location', type_=sa.String(100), existing_type=sa.String(255))
    op.alter_column('assessment_routines', 'return_type', type_=sa.String(100), existing_type=sa.String(500))
    op.alter_column('assessment_ml_models', 'model_type', type_=sa.String(100), existing_type=sa.String(255))
