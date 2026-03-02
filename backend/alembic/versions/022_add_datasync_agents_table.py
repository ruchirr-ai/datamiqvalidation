"""Add datasync_agents table for agent registry

Revision ID: 022
Revises: 021
Create Date: 2026-03-02
"""
from alembic import op
import sqlalchemy as sa

revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'datasync_agents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('vm_ip', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('agent_arn', sa.String(512), nullable=False),
        sa.Column('aws_region', sa.String(50), nullable=False, server_default='us-east-1'),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('datasync_agents')
