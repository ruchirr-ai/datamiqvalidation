"""create field_configurations table

Revision ID: 005
Revises: 004
Create Date: 2026-02-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'field_configurations',
        sa.Column('id', sa.String(255), primary_key=True),
        sa.Column('database_type', sa.String(50), nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('label', sa.String(255), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('required', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('default_value', sa.String(255), nullable=True),
        sa.Column('placeholder', sa.String(255), nullable=True),
        sa.Column('help_text', sa.Text(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('validation', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('options', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Create index on database_type for faster queries
    op.create_index('idx_field_configs_db_type', 'field_configurations', ['database_type'])


def downgrade():
    op.drop_index('idx_field_configs_db_type', table_name='field_configurations')
    op.drop_table('field_configurations')
