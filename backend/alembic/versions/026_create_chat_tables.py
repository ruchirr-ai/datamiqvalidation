"""create chat tables

Revision ID: 026
Revises: 025
Create Date: 2026-03-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '026'
down_revision = '025'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create conversations, messages, and attachments tables for ChatAgent feature.
    """
    # Tables may already exist from a previous branch migration — skip if so
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT tablename FROM pg_tables WHERE tablename='conversations'"
    ))
    if result.fetchone() is not None:
        return
    
    # Create conversations table
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_conversations_user', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_conversations_workspace', ondelete='CASCADE')
    )
    
    op.create_index('idx_conversations_workspace_user', 'conversations', ['workspace_id', 'user_id', 'updated_at'], unique=False)
    op.create_index('idx_conversations_user', 'conversations', ['user_id', 'updated_at'], unique=False)
    op.create_index('idx_conversations_workspace', 'conversations', ['workspace_id', 'updated_at'], unique=False)
    
    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('page_context', sa.String(50), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], name='fk_messages_conversation', ondelete='CASCADE'),
        sa.CheckConstraint("role IN ('user', 'assistant')", name='chk_messages_role')
    )
    
    op.create_index('idx_messages_conversation_created', 'messages', ['conversation_id', 'created_at'], unique=False)
    op.create_index('idx_messages_created', 'messages', ['created_at'], unique=False)
    op.execute("CREATE INDEX idx_messages_content_fts ON messages USING gin(to_tsvector('english', content))")
    
    # Create attachments table
    op.create_table(
        'attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('content_binary', postgresql.BYTEA(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], name='fk_attachments_message', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], name='fk_attachments_workspace', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_attachments_user', ondelete='CASCADE'),
        sa.CheckConstraint('file_size > 0 AND file_size <= 5242880', name='chk_attachments_size'),
        sa.CheckConstraint(
            '(content_text IS NOT NULL AND content_binary IS NULL) OR (content_text IS NULL AND content_binary IS NOT NULL)',
            name='chk_attachments_content'
        )
    )
    
    op.create_index('idx_attachments_message', 'attachments', ['message_id'], unique=False)
    op.create_index('idx_attachments_workspace_user', 'attachments', ['workspace_id', 'user_id', 'created_at'], unique=False)


def downgrade():
    op.drop_table('attachments')
    op.drop_table('messages')
    op.drop_table('conversations')
