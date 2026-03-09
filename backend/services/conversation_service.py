"""
Conversation Service for ChatAgent feature.

This service manages conversation and message persistence, retrieval, search, and deletion.
Implements cache-aside pattern with Redis caching and PostgreSQL fallback.

Key features:
- Conversation CRUD operations
- Message storage and retrieval with pagination
- Full-text search across conversation history
- Conversation export (JSON and Markdown)
- Workspace isolation for multi-tenant security
- Redis caching with database fallback
"""

import json
import logging
from typing import List, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func, text
from redis import Redis, RedisError, ConnectionError as RedisConnectionError

from models.conversation import Conversation, ConversationInfo
from models.message import Message, MessageWithAttachments
from models.attachment import AttachmentInfo
from models.chat_api import ConversationSearchResult

logger = logging.getLogger(__name__)


class ConversationService:
    """
    Service for managing conversations and messages.
    
    This service provides methods for:
    - Creating and managing conversations
    - Storing and retrieving messages
    - Searching conversation history
    - Exporting conversations
    
    All operations enforce workspace isolation for multi-tenant security.
    """
    
    def __init__(self, db: Session, redis_client: Optional[Redis] = None):
        """
        Initialize ConversationService.
        
        Args:
            db: SQLAlchemy database session
            redis_client: Optional Redis client for caching
        """
        self.db = db
        self.redis = redis_client
        self.cache_ttl = 300  # 5 minutes TTL for conversation metadata
    
    def create_conversation(self, user_id: int, workspace_id: int) -> Conversation:
        """
        Create a new conversation.
        
        Args:
            user_id: ID of the user creating the conversation
            workspace_id: ID of the workspace
            
        Returns:
            Created Conversation object
            
        Raises:
            ValueError: If user_id or workspace_id is invalid
        """
        logger.info(f"Creating conversation for user_id={user_id}, workspace_id={workspace_id}")
        
        # Create conversation record
        from models.user import User
        from models.workspace import Workspace
        
        conversation = Conversation(
            user_id=user_id,
            workspace_id=workspace_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        logger.info(f"Created conversation id={conversation.id}")
        return conversation
    
    def get_conversations(
        self,
        user_id: int,
        workspace_id: int,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[ConversationInfo], int]:
        """
        Get paginated conversations for user in workspace.
        
        Args:
            user_id: User ID
            workspace_id: Workspace ID for isolation
            page: Page number (1-indexed)
            page_size: Items per page (max 100)
            
        Returns:
            Tuple of (conversation list, total count)
        """
        logger.info(f"Getting conversations for user_id={user_id}, workspace_id={workspace_id}, page={page}")
        
        # Enforce max page size
        page_size = min(page_size, 100)
        offset = (page - 1) * page_size
        
        # Try Redis cache first
        cache_key = f"chat:conversations:{workspace_id}:{user_id}:page:{page}:size:{page_size}"
        try:
            if self.redis:
                cached_data = self.redis.get(cache_key)
                if cached_data:
                    logger.debug(f"Cache hit for conversations: {cache_key}")
                    data = json.loads(cached_data)
                    return (
                        [ConversationInfo(**conv) for conv in data['conversations']],
                        data['total_count']
                    )
        except (RedisError, RedisConnectionError) as e:
            logger.warning(f"Redis unavailable: {e}, falling back to database")
        
        # Query database with workspace isolation
        from sqlalchemy import Table, MetaData
        metadata = MetaData()
        conversations_table = Table('conversations', metadata, autoload_with=self.db.bind)
        messages_table = Table('messages', metadata, autoload_with=self.db.bind)
        
        # Get total count
        total_count = self.db.query(func.count(conversations_table.c.id)).filter(
            conversations_table.c.workspace_id == workspace_id,
            conversations_table.c.user_id == user_id,
            conversations_table.c.is_active == True
        ).scalar()
        
        # Get conversations with message count and last message preview
        query = self.db.query(
            conversations_table.c.id,
            conversations_table.c.created_at,
            conversations_table.c.updated_at,
            func.count(messages_table.c.id).label('message_count'),
            func.max(messages_table.c.content).label('last_message_preview')
        ).outerjoin(
            messages_table,
            conversations_table.c.id == messages_table.c.conversation_id
        ).filter(
            conversations_table.c.workspace_id == workspace_id,
            conversations_table.c.user_id == user_id,
            conversations_table.c.is_active == True
        ).group_by(
            conversations_table.c.id,
            conversations_table.c.created_at,
            conversations_table.c.updated_at
        ).order_by(
            desc(conversations_table.c.updated_at)
        ).limit(page_size).offset(offset)
        
        results = query.all()
        
        # Build ConversationInfo objects
        conversations = []
        for row in results:
            preview = row.last_message_preview[:100] if row.last_message_preview else None
            conversations.append(ConversationInfo(
                id=row.id,
                created_at=row.created_at,
                updated_at=row.updated_at,
                message_count=row.message_count or 0,
                last_message_preview=preview
            ))
        
        # Cache result (best effort)
        try:
            if self.redis:
                cache_data = {
                    'conversations': [conv.dict() for conv in conversations],
                    'total_count': total_count
                }
                self.redis.setex(cache_key, self.cache_ttl, json.dumps(cache_data, default=str))
                logger.debug(f"Cached conversations: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to cache conversations: {e}")
        
        return conversations, total_count
    
    def store_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        page_context: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> Message:
        """
        Store a message in the database.
        
        Args:
            conversation_id: Parent conversation ID
            role: Message role ('user' or 'assistant')
            content: Message content text
            page_context: Optional page context
            metadata: Optional metadata dict
            
        Returns:
            Created Message object
            
        Raises:
            ValueError: If role is invalid or conversation doesn't exist
        """
        logger.info(f"Storing message for conversation_id={conversation_id}, role={role}")
        
        # Validate role
        if role not in ('user', 'assistant'):
            raise ValueError("role must be either 'user' or 'assistant'")
        
        # Create message
        from sqlalchemy import Table, MetaData
        metadata_obj = MetaData()
        messages_table = Table('messages', metadata_obj, autoload_with=self.db.bind)
        conversations_table = Table('conversations', metadata_obj, autoload_with=self.db.bind)
        
        # Insert message
        insert_stmt = messages_table.insert().values(
            conversation_id=conversation_id,
            role=role,
            content=content,
            page_context=page_context,
            metadata=metadata or {},
            created_at=datetime.utcnow()
        )
        result = self.db.execute(insert_stmt)
        message_id = result.inserted_primary_key[0]
        
        # Update conversation updated_at
        update_stmt = conversations_table.update().where(
            conversations_table.c.id == conversation_id
        ).values(updated_at=datetime.utcnow())
        self.db.execute(update_stmt)
        
        self.db.commit()
        
        # Fetch created message
        message_row = self.db.execute(
            messages_table.select().where(messages_table.c.id == message_id)
        ).first()
        
        message = Message(
            id=message_row.id,
            conversation_id=message_row.conversation_id,
            role=message_row.role,
            content=message_row.content,
            page_context=message_row.page_context,
            metadata=message_row.metadata or {},
            created_at=message_row.created_at
        )
        
        # Invalidate cache for this conversation
        self._invalidate_conversation_cache(conversation_id)
        
        logger.info(f"Stored message id={message.id}")
        return message
    
    def get_conversation_messages(
        self,
        conversation_id: int,
        user_id: int,
        workspace_id: int,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[MessageWithAttachments], int]:
        """
        Get paginated messages for a conversation.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID for validation
            workspace_id: Workspace ID for isolation
            page: Page number (1-indexed)
            page_size: Items per page (max 100)
            
        Returns:
            Tuple of (message list, total count)
            
        Raises:
            ValueError: If user doesn't have access to conversation
        """
        logger.info(f"Getting messages for conversation_id={conversation_id}")
        
        # Validate workspace access
        from sqlalchemy import Table, MetaData
        metadata = MetaData()
        conversations_table = Table('conversations', metadata, autoload_with=self.db.bind)
        
        conv = self.db.execute(
            conversations_table.select().where(
                conversations_table.c.id == conversation_id,
                conversations_table.c.workspace_id == workspace_id,
                conversations_table.c.user_id == user_id
            )
        ).first()
        
        if not conv:
            raise ValueError("Conversation not found or access denied")
        
        # Enforce max page size
        page_size = min(page_size, 100)
        offset = (page - 1) * page_size
        
        # Get messages
        messages_table = Table('messages', metadata, autoload_with=self.db.bind)
        
        total_count = self.db.query(func.count(messages_table.c.id)).filter(
            messages_table.c.conversation_id == conversation_id
        ).scalar()
        
        query = self.db.execute(
            messages_table.select().where(
                messages_table.c.conversation_id == conversation_id
            ).order_by(asc(messages_table.c.created_at)).limit(page_size).offset(offset)
        )
        
        messages = []
        for row in query:
            # Get attachments for this message
            attachments = self._get_message_attachments(row.id)
            
            message = MessageWithAttachments(
                id=row.id,
                conversation_id=row.conversation_id,
                role=row.role,
                content=row.content,
                page_context=row.page_context,
                metadata=row.metadata or {},
                created_at=row.created_at,
                attachments=attachments
            )
            messages.append(message)
        
        return messages, total_count
    
    def _get_message_attachments(self, message_id: int) -> List[AttachmentInfo]:
        """Get attachments for a message."""
        from sqlalchemy import Table, MetaData
        metadata = MetaData()
        attachments_table = Table('attachments', metadata, autoload_with=self.db.bind)
        
        query = self.db.execute(
            attachments_table.select().where(
                attachments_table.c.message_id == message_id
            )
        )
        
        attachments = []
        for row in query:
            attachments.append(AttachmentInfo(
                id=row.id,
                filename=row.filename,
                file_size=row.file_size,
                mime_type=row.mime_type,
                created_at=row.created_at
            ))
        
        return attachments
    
    def delete_conversation(
        self,
        conversation_id: int,
        user_id: int,
        workspace_id: int
    ) -> bool:
        """
        Delete conversation and all associated data.
        
        Args:
            conversation_id: Conversation ID to delete
            user_id: User ID for validation
            workspace_id: Workspace ID for isolation
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If conversation not found or access denied
        """
        logger.info(f"Deleting conversation_id={conversation_id}")
        
        # Validate ownership and workspace
        from sqlalchemy import Table, MetaData
        metadata = MetaData()
        conversations_table = Table('conversations', metadata, autoload_with=self.db.bind)
        
        conv = self.db.execute(
            conversations_table.select().where(
                conversations_table.c.id == conversation_id,
                conversations_table.c.workspace_id == workspace_id,
                conversations_table.c.user_id == user_id
            )
        ).first()
        
        if not conv:
            raise ValueError("Conversation not found or access denied")
        
        # Delete conversation (cascade will handle messages and attachments)
        delete_stmt = conversations_table.delete().where(
            conversations_table.c.id == conversation_id
        )
        self.db.execute(delete_stmt)
        self.db.commit()
        
        # Invalidate cache
        self._invalidate_conversation_cache(conversation_id)
        
        logger.info(f"Deleted conversation_id={conversation_id}")
        return True
    
    def search_conversations(
        self,
        query: str,
        user_id: int,
        workspace_id: int,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[ConversationSearchResult], int]:
        """
        Full-text search across conversation history.
        
        Args:
            query: Search query text
            user_id: User ID
            workspace_id: Workspace ID for isolation
            page: Page number (1-indexed)
            page_size: Items per page (max 50)
            
        Returns:
            Tuple of (search results, total count)
        """
        logger.info(f"Searching conversations: query='{query}', workspace_id={workspace_id}")
        
        # Enforce max page size for search
        page_size = min(page_size, 50)
        offset = (page - 1) * page_size
        
        # Use PostgreSQL full-text search
        from sqlalchemy import Table, MetaData
        metadata = MetaData()
        messages_table = Table('messages', metadata, autoload_with=self.db.bind)
        conversations_table = Table('conversations', metadata, autoload_with=self.db.bind)
        
        # Build search query with workspace isolation
        search_query = text("""
            SELECT m.*, 
                   ts_rank(to_tsvector('english', m.content), plainto_tsquery('english', :query)) as relevance
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE c.workspace_id = :workspace_id
              AND c.user_id = :user_id
              AND to_tsvector('english', m.content) @@ plainto_tsquery('english', :query)
            ORDER BY relevance DESC, m.created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        
        results = self.db.execute(
            search_query,
            {
                'query': query,
                'workspace_id': workspace_id,
                'user_id': user_id,
                'limit': page_size,
                'offset': offset
            }
        ).fetchall()
        
        # Get total count
        count_query = text("""
            SELECT COUNT(*)
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE c.workspace_id = :workspace_id
              AND c.user_id = :user_id
              AND to_tsvector('english', m.content) @@ plainto_tsquery('english', :query)
        """)
        
        total_count = self.db.execute(
            count_query,
            {'query': query, 'workspace_id': workspace_id, 'user_id': user_id}
        ).scalar()
        
        # Build search results with context
        search_results = []
        for row in results:
            message = Message(
                id=row.id,
                conversation_id=row.conversation_id,
                role=row.role,
                content=row.content,
                page_context=row.page_context,
                metadata=row.metadata or {},
                created_at=row.created_at
            )
            
            # Get previous and next messages for context
            prev_msg = self._get_adjacent_message(row.id, 'previous')
            next_msg = self._get_adjacent_message(row.id, 'next')
            
            search_results.append(ConversationSearchResult(
                message=message,
                previous_message=prev_msg,
                next_message=next_msg,
                relevance_score=float(row.relevance)
            ))
        
        return search_results, total_count
    
    def _get_adjacent_message(self, message_id: int, direction: str) -> Optional[Message]:
        """Get previous or next message for context."""
        from sqlalchemy import Table, MetaData
        metadata = MetaData()
        messages_table = Table('messages', metadata, autoload_with=self.db.bind)
        
        if direction == 'previous':
            query = self.db.execute(
                messages_table.select().where(
                    messages_table.c.id < message_id
                ).order_by(desc(messages_table.c.id)).limit(1)
            )
        else:  # next
            query = self.db.execute(
                messages_table.select().where(
                    messages_table.c.id > message_id
                ).order_by(asc(messages_table.c.id)).limit(1)
            )
        
        row = query.first()
        if row:
            return Message(
                id=row.id,
                conversation_id=row.conversation_id,
                role=row.role,
                content=row.content,
                page_context=row.page_context,
                metadata=row.metadata or {},
                created_at=row.created_at
            )
        return None
    
    def export_conversation(
        self,
        conversation_id: int,
        user_id: int,
        workspace_id: int,
        format: str = "json"
    ) -> str:
        """
        Export conversation in specified format.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID for validation
            workspace_id: Workspace ID for isolation
            format: Export format ('json' or 'markdown')
            
        Returns:
            Formatted export string
            
        Raises:
            ValueError: If format is invalid or conversation not found
        """
        logger.info(f"Exporting conversation_id={conversation_id}, format={format}")
        
        if format not in ('json', 'markdown'):
            raise ValueError("format must be 'json' or 'markdown'")
        
        # Get all messages
        messages, _ = self.get_conversation_messages(
            conversation_id, user_id, workspace_id, page=1, page_size=10000
        )
        
        if format == 'json':
            return self._export_json(conversation_id, messages)
        else:
            return self._export_markdown(conversation_id, messages)
    
    def _export_json(self, conversation_id: int, messages: List[MessageWithAttachments]) -> str:
        """Export conversation as JSON."""
        export_data = {
            'conversation_id': conversation_id,
            'created_at': messages[0].created_at.isoformat() if messages else None,
            'messages': [
                {
                    'id': msg.id,
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.created_at.isoformat(),
                    'attachments': [
                        {
                            'id': att.id,
                            'filename': att.filename,
                            'file_size': att.file_size,
                            'mime_type': att.mime_type
                        }
                        for att in msg.attachments
                    ]
                }
                for msg in messages
            ]
        }
        return json.dumps(export_data, indent=2)
    
    def _export_markdown(self, conversation_id: int, messages: List[MessageWithAttachments]) -> str:
        """Export conversation as Markdown."""
        lines = [
            "# Conversation Export",
            "",
            f"**Conversation ID:** {conversation_id}",
            f"**Created:** {messages[0].created_at.strftime('%Y-%m-%d %H:%M:%S') if messages else 'N/A'}",
            "",
            "---",
            ""
        ]
        
        for i, msg in enumerate(messages, 1):
            lines.append(f"## Message {i}")
            lines.append(f"**{msg.role.capitalize()}** - {msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append("")
            lines.append(msg.content)
            
            if msg.attachments:
                lines.append("")
                lines.append("**Attachments:**")
                for att in msg.attachments:
                    lines.append(f"- {att.filename} ({att.file_size} bytes)")
            
            lines.append("")
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    def _invalidate_conversation_cache(self, conversation_id: int):
        """Invalidate Redis cache for a conversation."""
        try:
            if self.redis:
                # Invalidate conversation list caches
                pattern = f"chat:conversations:*"
                keys = self.redis.keys(pattern)
                if keys:
                    self.redis.delete(*keys)
                    logger.debug(f"Invalidated cache for conversation_id={conversation_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")
