"""create auth tables

Revision ID: 001
Revises: 
Create Date: 2026-01-25 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='user'),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_login', sa.TIMESTAMP(), nullable=True),
        sa.Column('is_locked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )
    
    # Create indexes on users table
    op.create_index('idx_users_username', 'users', ['username'])
    op.create_index('idx_users_role', 'users', ['role'])
    
    # Create sessions table
    op.create_table(
        'sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('expires_at', sa.TIMESTAMP(), nullable=False),
        sa.Column('is_blacklisted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    
    # Create indexes on sessions table
    op.create_index('idx_sessions_token_hash', 'sessions', ['token_hash'])
    op.create_index('idx_sessions_user_id', 'sessions', ['user_id'])
    op.create_index('idx_sessions_expires_at', 'sessions', ['expires_at'])
    
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL')
    )
    
    # Create indexes on audit_logs table
    op.create_index('idx_audit_logs_event_type', 'audit_logs', ['event_type'])
    op.create_index('idx_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_logs_created_at', 'audit_logs', ['created_at'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_audit_logs_created_at', table_name='audit_logs')
    op.drop_index('idx_audit_logs_user_id', table_name='audit_logs')
    op.drop_index('idx_audit_logs_event_type', table_name='audit_logs')
    op.drop_table('audit_logs')
    
    op.drop_index('idx_sessions_expires_at', table_name='sessions')
    op.drop_index('idx_sessions_user_id', table_name='sessions')
    op.drop_index('idx_sessions_token_hash', table_name='sessions')
    op.drop_table('sessions')
    
    op.drop_index('idx_users_role', table_name='users')
    op.drop_index('idx_users_username', table_name='users')
    op.drop_table('users')
