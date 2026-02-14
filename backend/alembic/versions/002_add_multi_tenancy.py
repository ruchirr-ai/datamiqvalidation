"""add multi-tenancy support

Revision ID: 002
Revises: 001
Create Date: 2026-01-25 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('subscription_tier', sa.String(length=50), nullable=False, server_default='free'),
        sa.Column('max_workspaces', sa.Integer(), nullable=False, server_default='5'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )
    
    op.create_index('idx_organizations_slug', 'organizations', ['slug'])
    
    # Create workspaces table
    op.create_table(
        'workspaces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('organization_id', 'slug', name='uq_workspace_org_slug')
    )
    
    op.create_index('idx_workspaces_org_id', 'workspaces', ['organization_id'])
    op.create_index('idx_workspaces_slug', 'workspaces', ['slug'])
    
    # Create user_workspaces mapping table
    op.create_table(
        'user_workspaces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='member'),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'workspace_id', name='uq_user_workspace')
    )
    
    op.create_index('idx_user_workspaces_user_id', 'user_workspaces', ['user_id'])
    op.create_index('idx_user_workspaces_workspace_id', 'user_workspaces', ['workspace_id'])
    
    # Add organization_id to users table
    op.add_column('users', sa.Column('organization_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_users_organization', 'users', 'organizations', ['organization_id'], ['id'], ondelete='CASCADE')
    op.create_index('idx_users_organization_id', 'users', ['organization_id'])


def downgrade() -> None:
    # Drop in reverse order
    op.drop_index('idx_users_organization_id', table_name='users')
    op.drop_constraint('fk_users_organization', 'users', type_='foreignkey')
    op.drop_column('users', 'organization_id')
    
    op.drop_index('idx_user_workspaces_workspace_id', table_name='user_workspaces')
    op.drop_index('idx_user_workspaces_user_id', table_name='user_workspaces')
    op.drop_table('user_workspaces')
    
    op.drop_index('idx_workspaces_slug', table_name='workspaces')
    op.drop_index('idx_workspaces_org_id', table_name='workspaces')
    op.drop_table('workspaces')
    
    op.drop_index('idx_organizations_slug', table_name='organizations')
    op.drop_table('organizations')
