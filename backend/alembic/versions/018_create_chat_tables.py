"""create chat tables

Revision ID: 018
Revises: 017
Create Date: 2026-03-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create conversations, messages, and attachments tables for ChatAgent feature.
    
    This migration adds:
    - conversations: Store chat conversation metadata
    - messages: Store individual chat messages (user and assistant)
    - attachments: Store file attachments for messages
    
    All tables enforce workspace isolation for multi-tenant security.
    """
    
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
    
    # Create indexes for conversations
    op.create_index('idx_conversations_workspace_user', 'conversations', ['workspace_id', 'user_id', 'updated_at'], unique=False, postgresql_ops={'updated_at': 'DESC'})
    op.create_index('idx_conversations_user', 'conversations', ['user_id', 'updated_at'], unique=False, postgresql_ops={'updated_at': 'DESC'})
    op.create_index('idx_conversations_workspace', 'conversations', ['workspace_id', 'updated_at'], unique=False, postgresql_ops={'updated_at': 'DESC'})
    
    print("✓ Created conversations table with indexes")
    
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
    
    # Create indexes for messages
    op.create_index('idx_messages_conversation_created', 'messages', ['conversation_id', 'created_at'], unique=False)
    op.create_index('idx_messages_created', 'messages', ['created_at'], unique=False, postgresql_ops={'created_at': 'DESC'})
    
    # Create full-text search index on messages.content
    op.execute("CREATE INDEX idx_messages_content_fts ON messages USING gin(to_tsvector('english', content))")
    
    print("✓ Created messages table with indexes and full-text search")
    
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
    
    # Create indexes for attachments
    op.create_index('idx_attachments_message', 'attachments', ['message_id'], unique=False)
    op.create_index('idx_attachments_workspace_user', 'attachments', ['workspace_id', 'user_id', 'created_at'], unique=False, postgresql_ops={'created_at': 'DESC'})
    
    print("✓ Created attachments table with indexes")
    print("")
    print("ChatAgent tables created successfully!")
    print("- conversations: Store chat conversation metadata")
    print("- messages: Store chat messages with full-text search")
    print("- attachments: Store file attachments (max 5MB)")
    print("")
    print("All tables enforce workspace isolation for multi-tenant security.")


def downgrade():
    """
    Remove ChatAgent tables.
    
    WARNING: This will delete all chat conversations, messages, and attachments!
    """
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('attachments')
    print("✗ Dropped attachments table")
    
    op.drop_table('messages')
    print("✗ Dropped messages table")
    
    op.drop_table('conversations')
    print("✗ Dropped conversations table")
    
    print("")
    print("⚠️  WARNING: All ChatAgent data has been removed!")
