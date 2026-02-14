"""create connections table

Revision ID: 004
Revises: 003
Create Date: 2026-02-08 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    """Create connections table"""
    op.create_table(
        'connections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('database', sa.String(length=100), nullable=False),
        sa.Column('connection_params', JSON, nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=False, server_default='system'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='disconnected'),
        sa.Column('last_tested_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('idx_connections_type', 'connections', ['type'])
    op.create_index('idx_connections_database', 'connections', ['database'])
    op.create_index('idx_connections_created_by', 'connections', ['created_by'])
    op.create_index('idx_connections_status', 'connections', ['status'])
    op.create_index('idx_connections_is_active', 'connections', ['is_active'])


def downgrade():
    """Drop connections table"""
    op.drop_index('idx_connections_is_active', table_name='connections')
    op.drop_index('idx_connections_status', table_name='connections')
    op.drop_index('idx_connections_created_by', table_name='connections')
    op.drop_index('idx_connections_database', table_name='connections')
    op.drop_index('idx_connections_type', table_name='connections')
    op.drop_table('connections')
