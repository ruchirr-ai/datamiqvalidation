# Design Document: ChatAgent Production Enhancements

## Overview

This design document specifies the architecture and implementation details for enhancing the ChatAgent feature to production-ready status. The enhancements transform ChatAgent from a basic chat interface into an intelligent, context-aware assistant with conversation persistence, real-time data integration, smart suggestions, and file attachment support.

### Goals

1. **Conversation Persistence**: Store all chat conversations in PostgreSQL with full workspace isolation
2. **Context-Aware Responses**: Integrate real user data from assessments, connections, and migrations
3. **Intelligent Suggestions**: Generate dynamic suggested questions based on user context and data state
4. **File Attachment Support**: Enable users to upload logs, screenshots, and JSON files for troubleshooting
5. **Multi-Tenant Security**: Enforce strict workspace isolation across all operations
6. **Performance**: Maintain sub-500ms response times with Redis caching and database optimization
7. **Scalability**: Support 10,000+ messages per user with efficient pagination and indexing

### Key Features

- Automatic conversation saving with message history
- Context gathering from user's workspace data (assessments, connections, migrations)
- Dynamic suggested questions based on page context and data state
- File upload support for .txt, .log, .json, .png, .jpg files (max 5MB)
- Full-text search across conversation history
- Conversation export in JSON and Markdown formats
- Rate limiting and security controls
- Comprehensive audit logging

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  ChatAgent   │  │   Message    │  │  Attachment  │          │
│  │  Component   │  │   Display    │  │   Upload     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ REST API
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Chat Router (API Layer)                      │   │
│  │  - POST /api/chat/message                                 │   │
│  │  - GET /api/chat/conversations                            │   │
│  │  - GET /api/chat/conversations/{id}/messages              │   │
│  │  - POST /api/chat/attachments                             │   │
│  │  - GET /api/chat/suggested-questions                      │   │
│  │  - POST /api/chat/search                                  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                    │
│  ┌───────────────┬──────────┴──────────┬──────────────────┐     │
│  │               │                     │                   │     │
│  ▼               ▼                     ▼                   ▼     │
│ ┌─────────┐  ┌─────────┐  ┌──────────────┐  ┌──────────────┐   │
│ │Conversa-│  │ Context │  │  Attachment  │  │   Claude AI  │   │
│ │  tion   │  │ Service │  │   Service    │  │   Service    │   │
│ │ Service │  │         │  │              │  │  (Bedrock)   │   │
│ └─────────┘  └─────────┘  └──────────────┘  └──────────────┘   │
│      │            │               │                              │
└──────┼────────────┼───────────────┼──────────────────────────────┘
       │            │               │
       ▼            ▼               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Data Layer                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  PostgreSQL  │  │    Redis     │  │  AWS Bedrock │          │
│  │   Database   │  │    Cache     │  │  (Claude AI) │          │
│  │              │  │              │  │              │          │
│  │ - conversa-  │  │ - Context    │  │ - AI         │          │
│  │   tions      │  │   cache      │  │   responses  │          │
│  │ - messages   │  │ - Suggested  │  │ - Vision     │          │
│  │ - attachments│  │   questions  │  │   analysis   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

#### Frontend Components
- **ChatAgent Component**: Main chat interface with message display, input, and controls
- **Message Display**: Renders user and AI messages with markdown support
- **Attachment Upload**: File selection and upload UI with validation
- **Suggested Questions**: Displays context-aware question chips

#### Backend Services
- **Chat Router**: API endpoints for all chat operations with authentication and rate limiting
- **Conversation Service**: Manages conversation and message persistence, retrieval, and search
- **Context Service**: Gathers user-specific data from workspace (assessments, connections, migrations)
- **Attachment Service**: Handles file uploads, validation, storage, and content extraction
- **Claude AI Service**: Integrates with AWS Bedrock for AI-powered responses

#### Data Layer
- **PostgreSQL**: Primary data store for conversations, messages, and attachments
- **Redis**: Cache layer for context data and suggested questions (5-minute TTL)
- **AWS Bedrock**: Claude AI service for generating intelligent responses

## Components and Interfaces

### Database Schema

#### Conversations Table

```sql
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    
    CONSTRAINT fk_conversations_user FOREIGN KEY (user_id) 
        REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_conversations_workspace FOREIGN KEY (workspace_id) 
        REFERENCES workspaces(id) ON DELETE CASCADE
);

-- Indexes for efficient querying
CREATE INDEX idx_conversations_workspace_user 
    ON conversations(workspace_id, user_id, updated_at DESC);
CREATE INDEX idx_conversations_user 
    ON conversations(user_id, updated_at DESC);
CREATE INDEX idx_conversations_workspace 
    ON conversations(workspace_id, updated_at DESC);
```

#### Messages Table

```sql
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    page_context VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_messages_conversation FOREIGN KEY (conversation_id) 
        REFERENCES conversations(id) ON DELETE CASCADE,
    CONSTRAINT chk_messages_role CHECK (role IN ('user', 'assistant'))
);

-- Indexes for efficient retrieval and search
CREATE INDEX idx_messages_conversation_created 
    ON messages(conversation_id, created_at ASC);
CREATE INDEX idx_messages_created 
    ON messages(created_at DESC);

-- Full-text search index
CREATE INDEX idx_messages_content_fts 
    ON messages USING gin(to_tsvector('english', content));
```

#### Attachments Table

```sql
CREATE TABLE attachments (
    id SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_size INTEGER NOT NULL CHECK (file_size > 0 AND file_size <= 5242880),
    mime_type VARCHAR(100) NOT NULL,
    content_text TEXT,
    content_binary BYTEA,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_attachments_message FOREIGN KEY (message_id) 
        REFERENCES messages(id) ON DELETE CASCADE,
    CONSTRAINT fk_attachments_workspace FOREIGN KEY (workspace_id) 
        REFERENCES workspaces(id) ON DELETE CASCADE,
    CONSTRAINT fk_attachments_user FOREIGN KEY (user_id) 
        REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT chk_attachments_size CHECK (file_size > 0 AND file_size <= 5242880),
    CONSTRAINT chk_attachments_content CHECK (
        (content_text IS NOT NULL AND content_binary IS NULL) OR
        (content_text IS NULL AND content_binary IS NOT NULL)
    )
);

-- Indexes for efficient filtering
CREATE INDEX idx_attachments_message 
    ON attachments(message_id);
CREATE INDEX idx_attachments_workspace_user 
    ON attachments(workspace_id, user_id, created_at DESC);
```

### Pydantic Models

#### Conversation Models

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class ConversationBase(BaseModel):
    """Base conversation model"""
    user_id: int
    workspace_id: int

class ConversationCreate(ConversationBase):
    """Conversation creation request"""
    pass

class Conversation(ConversationBase):
    """Conversation database model"""
    id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    
    class Config:
        from_attributes = True

class ConversationInfo(BaseModel):
    """Conversation information for API responses"""
    id: int
    created_at: datetime
    updated_at: datetime
    message_count: int
    last_message_preview: Optional[str] = None
```

#### Message Models

```python
class MessageBase(BaseModel):
    """Base message model"""
    conversation_id: int
    role: str  # 'user' or 'assistant'
    content: str
    page_context: Optional[str] = None

class MessageCreate(MessageBase):
    """Message creation request"""
    metadata: Optional[dict] = {}

class Message(MessageBase):
    """Message database model"""
    id: int
    metadata: dict = {}
    created_at: datetime
    
    class Config:
        from_attributes = True

class MessageWithAttachments(Message):
    """Message with attachment information"""
    attachments: List['AttachmentInfo'] = []
```

#### Attachment Models

```python
class AttachmentBase(BaseModel):
    """Base attachment model"""
    message_id: int
    workspace_id: int
    user_id: int
    filename: str
    file_size: int
    mime_type: str

class AttachmentCreate(AttachmentBase):
    """Attachment creation request"""
    content_text: Optional[str] = None
    content_binary: Optional[bytes] = None

class Attachment(AttachmentBase):
    """Attachment database model"""
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class AttachmentInfo(BaseModel):
    """Attachment information for API responses"""
    id: int
    filename: str
    file_size: int
    mime_type: str
    created_at: datetime
```

#### Chat Request/Response Models

```python
class ChatMessageRequest(BaseModel):
    """Chat message request"""
    message: str
    conversation_id: Optional[int] = None
    page_context: str = "dashboard"
    attachment_ids: Optional[List[int]] = []

class ChatMessageResponse(BaseModel):
    """Chat message response"""
    response: str
    conversation_id: int
    message_id: int
    timestamp: datetime

class SuggestedQuestion(BaseModel):
    """Suggested question model"""
    question_text: str
    category: str
    priority: int

class SuggestedQuestionsResponse(BaseModel):
    """Suggested questions response"""
    questions: List[SuggestedQuestion]

class ConversationSearchRequest(BaseModel):
    """Conversation search request"""
    query: str
    page: int = 1
    page_size: int = 50

class ConversationSearchResult(BaseModel):
    """Search result with context"""
    message: Message
    previous_message: Optional[Message] = None
    next_message: Optional[Message] = None
    relevance_score: float

class ConversationSearchResponse(BaseModel):
    """Search response with pagination"""
    results: List[ConversationSearchResult]
    total_count: int
    page: int
    page_size: int
    has_next_page: bool
```

### API Endpoints

#### POST /api/chat/message

Send a message to ChatAgent and receive an AI response.

**Request Body:**
```json
{
  "message": "How do I create a new assessment?",
  "conversation_id": 123,
  "page_context": "assessments",
  "attachment_ids": [456, 789]
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "response": "To create a new assessment...",
    "conversation_id": 123,
    "message_id": 1001,
    "timestamp": "2026-01-25T10:30:00Z"
  },
  "error": null
}
```

**Error Responses:**
- 400 Bad Request: Invalid message or parameters
- 401 Unauthorized: Missing or invalid authentication
- 403 Forbidden: Workspace access denied
- 429 Too Many Requests: Rate limit exceeded (30 messages/minute)
- 500 Internal Server Error: Server error
- 503 Service Unavailable: Claude AI unavailable

#### GET /api/chat/conversations

Retrieve all conversations for the authenticated user within their workspace.

**Query Parameters:**
- `page` (optional, default: 1): Page number
- `page_size` (optional, default: 50, max: 100): Items per page

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "conversations": [
      {
        "id": 123,
        "created_at": "2026-01-25T10:00:00Z",
        "updated_at": "2026-01-25T10:30:00Z",
        "message_count": 15,
        "last_message_preview": "To create a new assessment..."
      }
    ],
    "total_count": 42,
    "page": 1,
    "page_size": 50,
    "has_next_page": false
  },
  "error": null
}
```

#### GET /api/chat/conversations/{conversation_id}/messages

Retrieve paginated messages for a specific conversation.

**Path Parameters:**
- `conversation_id`: Conversation ID

**Query Parameters:**
- `page` (optional, default: 1): Page number
- `page_size` (optional, default: 50, max: 100): Items per page

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "messages": [
      {
        "id": 1001,
        "conversation_id": 123,
        "role": "user",
        "content": "How do I create a new assessment?",
        "page_context": "assessments",
        "metadata": {},
        "created_at": "2026-01-25T10:30:00Z",
        "attachments": []
      },
      {
        "id": 1002,
        "conversation_id": 123,
        "role": "assistant",
        "content": "To create a new assessment...",
        "page_context": null,
        "metadata": {},
        "created_at": "2026-01-25T10:30:05Z",
        "attachments": []
      }
    ],
    "total_count": 15,
    "page": 1,
    "page_size": 50,
    "has_next_page": false
  },
  "error": null
}
```

#### POST /api/chat/conversations

Create a new conversation.

**Request Body:**
```json
{
  "workspace_id": 1
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "id": 123,
    "user_id": 42,
    "workspace_id": 1,
    "created_at": "2026-01-25T10:00:00Z",
    "updated_at": "2026-01-25T10:00:00Z",
    "is_active": true
  },
  "error": null
}
```

#### DELETE /api/chat/conversations/{conversation_id}

Delete a conversation and all its messages and attachments.

**Path Parameters:**
- `conversation_id`: Conversation ID

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "message": "Conversation deleted successfully"
  },
  "error": null
}
```

#### POST /api/chat/attachments

Upload a file attachment.

**Request:**
- Content-Type: multipart/form-data
- Field: `file` (binary file data)

**Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "id": 456,
    "filename": "error.log",
    "file_size": 2048,
    "mime_type": "text/plain",
    "created_at": "2026-01-25T10:29:00Z"
  },
  "error": null
}
```

**Error Responses:**
- 400 Bad Request: File too large (>5MB) or invalid file type
- 413 Payload Too Large: File exceeds 5MB limit

#### GET /api/chat/suggested-questions

Get context-aware suggested questions.

**Query Parameters:**
- `page_context` (required): Current page (dashboard, assessments, connections, migrations, monitoring, validation)

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "questions": [
      {
        "question_text": "How do I troubleshoot my failed assessment?",
        "category": "troubleshooting",
        "priority": 1
      },
      {
        "question_text": "How do I create a new assessment?",
        "category": "getting_started",
        "priority": 2
      }
    ]
  },
  "error": null
}
```

#### POST /api/chat/search

Search conversation history using full-text search.

**Request Body:**
```json
{
  "query": "schema compatibility",
  "page": 1,
  "page_size": 50
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "results": [
      {
        "message": {
          "id": 1005,
          "conversation_id": 123,
          "role": "assistant",
          "content": "Schema compatibility checks...",
          "created_at": "2026-01-25T10:35:00Z"
        },
        "previous_message": {
          "id": 1004,
          "role": "user",
          "content": "What is schema compatibility?"
        },
        "next_message": null,
        "relevance_score": 0.95
      }
    ],
    "total_count": 3,
    "page": 1,
    "page_size": 50,
    "has_next_page": false
  },
  "error": null
}
```

#### GET /api/chat/conversations/{conversation_id}/export

Export conversation in JSON or Markdown format.

**Path Parameters:**
- `conversation_id`: Conversation ID

**Query Parameters:**
- `format` (optional, default: json): Export format (json, markdown)

**Response (200 OK):**
- Content-Type: application/json or text/markdown
- Content-Disposition: attachment; filename="conversation-123.json"

**JSON Format:**
```json
{
  "conversation_id": 123,
  "created_at": "2026-01-25T10:00:00Z",
  "messages": [
    {
      "id": 1001,
      "role": "user",
      "content": "How do I create a new assessment?",
      "timestamp": "2026-01-25T10:30:00Z"
    }
  ]
}
```

**Markdown Format:**
```markdown
# Conversation Export

**Conversation ID:** 123  
**Created:** 2026-01-25 10:00:00

---

## Message 1
**User** - 2026-01-25 10:30:00

How do I create a new assessment?

---

## Message 2
**Assistant** - 2026-01-25 10:30:05

To create a new assessment...
```

#### GET /api/chat/health

Health check endpoint for monitoring.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected",
  "claude_ai": "available"
}
```

## Data Models

### Context Data Structure

The Context Service gathers user-specific data and formats it for Claude AI:

```python
class UserContext(BaseModel):
    """User context for AI requests"""
    workspace: WorkspaceInfo
    page_context: str
    assessments: List[AssessmentSummary] = []
    connections: List[ConnectionSummary] = []
    migrations: List[MigrationSummary] = []
    has_errors: bool = False
    error_summary: Optional[str] = None

class AssessmentSummary(BaseModel):
    """Assessment summary for context"""
    id: int
    name: str
    status: str
    created_at: datetime

class ConnectionSummary(BaseModel):
    """Connection summary for context"""
    id: int
    name: str
    db_type: str
    status: str

class MigrationSummary(BaseModel):
    """Migration summary for context"""
    id: int
    name: str
    status: str
    progress: int
```

### Suggested Questions by Context

```python
SUGGESTED_QUESTIONS = {
    "dashboard": [
        {
            "question_text": "How do I get started with DataMIQ?",
            "category": "getting_started",
            "priority": 1
        },
        {
            "question_text": "What features are available?",
            "category": "general",
            "priority": 2
        }
    ],
    "assessments": [
        {
            "question_text": "How do I create a new assessment?",
            "category": "getting_started",
            "priority": 1
        },
        {
            "question_text": "What does schema analysis check?",
            "category": "features",
            "priority": 2
        }
    ],
    "connections": [
        {
            "question_text": "How do I connect to BigQuery?",
            "category": "getting_started",
            "priority": 1
        },
        {
            "question_text": "How do I test my connection?",
            "category": "troubleshooting",
            "priority": 2
        }
    ]
}
```

### File Type Validation

```python
ALLOWED_FILE_EXTENSIONS = ['.txt', '.log', '.json', '.png', '.jpg', '.jpeg']
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

MIME_TYPE_MAPPING = {
    '.txt': 'text/plain',
    '.log': 'text/plain',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg'
}
```


## Service Layer Architecture

### Conversation Service

**Responsibility**: Manage conversation and message persistence, retrieval, search, and deletion.

**Methods**:

```python
class ConversationService:
    """Service for managing conversations and messages"""
    
    def __init__(self, db: Session, redis_client: Redis):
        self.db = db
        self.redis = redis_client
    
    def create_conversation(
        self, 
        user_id: int, 
        workspace_id: int
    ) -> Conversation:
        """Create a new conversation"""
        pass
    
    def get_conversations(
        self, 
        user_id: int, 
        workspace_id: int,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[ConversationInfo], int]:
        """Get paginated conversations for user in workspace"""
        pass
    
    def get_conversation_messages(
        self,
        conversation_id: int,
        user_id: int,
        workspace_id: int,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[MessageWithAttachments], int]:
        """Get paginated messages for a conversation"""
        pass
    
    def store_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        page_context: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> Message:
        """Store a message in the database"""
        pass
    
    def delete_conversation(
        self,
        conversation_id: int,
        user_id: int,
        workspace_id: int
    ) -> bool:
        """Delete conversation and all associated data"""
        pass
    
    def search_conversations(
        self,
        query: str,
        user_id: int,
        workspace_id: int,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[ConversationSearchResult], int]:
        """Full-text search across conversation history"""
        pass
    
    def export_conversation(
        self,
        conversation_id: int,
        user_id: int,
        workspace_id: int,
        format: str = "json"
    ) -> str:
        """Export conversation in specified format"""
        pass
```

**Key Implementation Details**:
- Always apply workspace_id filtering to prevent cross-workspace access
- Use database indexes for efficient querying
- Implement cursor-based pagination for large result sets
- Cache conversation metadata in Redis (5-minute TTL)
- Log all operations for audit trail

### Context Service

**Responsibility**: Gather user-specific context data from workspace.

**Methods**:

```python
class ContextService:
    """Service for gathering user context data"""
    
    def __init__(
        self, 
        db: Session, 
        redis_client: Redis,
        assessment_repo: AssessmentRepository,
        connection_repo: ConnectionRepository,
        migration_repo: MigrationRepository
    ):
        self.db = db
        self.redis = redis_client
        self.assessment_repo = assessment_repo
        self.connection_repo = connection_repo
        self.migration_repo = migration_repo
    
    def gather_context(
        self,
        user_id: int,
        workspace_id: int,
        page_context: str
    ) -> UserContext:
        """Gather context data based on page and workspace"""
        pass
    
    def get_suggested_questions(
        self,
        user_id: int,
        workspace_id: int,
        page_context: str
    ) -> List[SuggestedQuestion]:
        """Generate context-aware suggested questions"""
        pass
    
    def _get_assessments_context(
        self,
        workspace_id: int
    ) -> List[AssessmentSummary]:
        """Get assessment data for context"""
        pass
    
    def _get_connections_context(
        self,
        workspace_id: int
    ) -> List[ConnectionSummary]:
        """Get connection data for context"""
        pass
    
    def _get_migrations_context(
        self,
        workspace_id: int
    ) -> List[MigrationSummary]:
        """Get migration data for context"""
        pass
    
    def _detect_errors(
        self,
        context: UserContext
    ) -> Tuple[bool, Optional[str]]:
        """Detect if user has errors in their workspace"""
        pass
```

**Key Implementation Details**:
- Execute data queries in parallel using asyncio for performance
- Limit results to 20 most recent items per category
- Cache context data in Redis with 5-minute TTL
- Mask sensitive data (passwords, API keys) before including in context
- Continue with partial context if any data source fails
- Apply workspace_id filtering to all queries

### Attachment Service

**Responsibility**: Handle file uploads, validation, storage, and content extraction.

**Methods**:

```python
class AttachmentService:
    """Service for managing file attachments"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def upload_attachment(
        self,
        file: UploadFile,
        user_id: int,
        workspace_id: int
    ) -> Attachment:
        """Upload and store a file attachment"""
        pass
    
    def validate_file(
        self,
        file: UploadFile
    ) -> Tuple[bool, Optional[str]]:
        """Validate file size and type"""
        pass
    
    def extract_content(
        self,
        attachment: Attachment
    ) -> str:
        """Extract text content from attachment"""
        pass
    
    def encode_image(
        self,
        attachment: Attachment
    ) -> str:
        """Encode image as base64 for Claude AI"""
        pass
    
    def get_attachments(
        self,
        message_id: int,
        workspace_id: int
    ) -> List[Attachment]:
        """Get attachments for a message"""
        pass
    
    def delete_attachment(
        self,
        attachment_id: int,
        user_id: int,
        workspace_id: int
    ) -> bool:
        """Delete an attachment"""
        pass
```

**Key Implementation Details**:
- Validate file extension against allowed list
- Validate file size (max 5MB)
- Store text files in content_text column
- Store binary files in content_binary column
- Extract text from .txt, .log, .json files
- Encode images as base64 for Claude AI vision
- Apply workspace_id filtering to prevent unauthorized access
- Scan for potential credentials in uploaded files

### Claude AI Service

**Responsibility**: Integrate with AWS Bedrock for AI-powered responses.

**Methods**:

```python
class ClaudeAIService:
    """Service for Claude AI integration via AWS Bedrock"""
    
    def __init__(self, bedrock_client: BedrockRuntime):
        self.bedrock = bedrock_client
        self.model_id = os.getenv("CLAUDE_MODEL_ID")
        self.max_tokens = int(os.getenv("CLAUDE_MAX_TOKENS", "4096"))
        self.temperature = float(os.getenv("CLAUDE_TEMPERATURE", "0.7"))
    
    def generate_response(
        self,
        message: str,
        context: UserContext,
        conversation_history: List[Message],
        attachments: List[Attachment] = []
    ) -> str:
        """Generate AI response with context"""
        pass
    
    def _build_system_prompt(
        self,
        context: UserContext
    ) -> str:
        """Build system prompt with user context"""
        pass
    
    def _format_conversation_history(
        self,
        messages: List[Message]
    ) -> List[dict]:
        """Format conversation history for Claude AI"""
        pass
    
    def _include_attachments(
        self,
        attachments: List[Attachment]
    ) -> List[dict]:
        """Format attachments for Claude AI request"""
        pass
```

**Key Implementation Details**:
- Use AWS Bedrock runtime client
- Include user context in system prompt
- Limit conversation history to last 10 messages
- Format attachments appropriately (text vs images)
- Implement timeout (30 seconds)
- Implement retry logic with exponential backoff (max 3 retries)
- Log all API calls with token count and response time


## Data Flow Diagrams

### Message Send Flow

```
User sends message
       │
       ▼
┌─────────────────┐
│  Chat Router    │ ← Validate authentication & workspace access
└─────────────────┘
       │
       ├──────────────────────────────────────┐
       │                                      │
       ▼                                      ▼
┌─────────────────┐                  ┌─────────────────┐
│ Context Service │                  │ Attachment      │
│                 │                  │ Service         │
│ - Gather user   │                  │                 │
│   assessments   │                  │ - Retrieve      │
│ - Gather        │                  │   attachments   │
│   connections   │                  │ - Extract       │
│ - Gather        │                  │   content       │
│   migrations    │                  │                 │
│ - Check Redis   │                  └─────────────────┘
│   cache         │                           │
└─────────────────┘                           │
       │                                      │
       │                                      │
       └──────────────┬───────────────────────┘
                      │
                      ▼
              ┌─────────────────┐
              │ Conversation    │
              │ Service         │
              │                 │
              │ - Store user    │
              │   message       │
              │ - Get history   │
              └─────────────────┘
                      │
                      ▼
              ┌─────────────────┐
              │ Claude AI       │
              │ Service         │
              │                 │
              │ - Build prompt  │
              │ - Include       │
              │   context       │
              │ - Include       │
              │   attachments   │
              │ - Call Bedrock  │
              └─────────────────┘
                      │
                      ▼
              ┌─────────────────┐
              │ Conversation    │
              │ Service         │
              │                 │
              │ - Store AI      │
              │   response      │
              └─────────────────┘
                      │
                      ▼
              ┌─────────────────┐
              │  Chat Router    │
              │                 │
              │ - Return        │
              │   response      │
              └─────────────────┘
                      │
                      ▼
                   User
```

### Context Gathering Flow

```
Context Service receives request
       │
       ▼
┌─────────────────────────────────────┐
│ Check Redis Cache                   │
│ Key: context:{workspace_id}:{page}  │
└─────────────────────────────────────┘
       │
       ├─── Cache Hit ──────────────────┐
       │                                 │
       │                                 ▼
       │                         Return cached context
       │
       └─── Cache Miss
              │
              ▼
┌─────────────────────────────────────┐
│ Execute Parallel Queries            │
│                                     │
│ ┌─────────────────────────────────┐│
│ │ Query 1: Assessments            ││
│ │ - Filter by workspace_id        ││
│ │ - Order by created_at DESC      ││
│ │ - Limit 20                      ││
│ └─────────────────────────────────┘│
│                                     │
│ ┌─────────────────────────────────┐│
│ │ Query 2: Connections            ││
│ │ - Filter by workspace_id        ││
│ │ - Order by created_at DESC      ││
│ │ - Limit 20                      ││
│ └─────────────────────────────────┘│
│                                     │
│ ┌─────────────────────────────────┐│
│ │ Query 3: Migrations             ││
│ │ - Filter by workspace_id        ││
│ │ - Order by created_at DESC      ││
│ │ - Limit 20                      ││
│ └─────────────────────────────────┘│
└─────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Handle Partial Failures             │
│ - Continue with available data      │
│ - Log errors                        │
└─────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Format Context Data                 │
│ - Mask sensitive fields             │
│ - Detect errors                     │
│ - Build UserContext object          │
└─────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────┐
│ Cache in Redis                      │
│ - TTL: 5 minutes                    │
│ - Best effort (don't fail)          │
└─────────────────────────────────────┘
       │
       ▼
Return context to caller
```

### File Upload Flow

```
User uploads file
       │
       ▼
┌─────────────────┐
│  Chat Router    │
│                 │
│ - Validate auth │
│ - Check         │
│   workspace     │
└─────────────────┘
       │
       ▼
┌─────────────────┐
│ Attachment      │
│ Service         │
│                 │
│ Validate File   │
└─────────────────┘
       │
       ├─── Valid ──────────────────────┐
       │                                 │
       │                                 ▼
       │                         ┌─────────────────┐
       │                         │ Determine       │
       │                         │ Storage Type    │
       │                         └─────────────────┘
       │                                 │
       │                                 │
       │                    ┌────────────┴────────────┐
       │                    │                         │
       │                    ▼                         ▼
       │            ┌──────────────┐         ┌──────────────┐
       │            │ Text File    │         │ Binary File  │
       │            │              │         │              │
       │            │ - Extract    │         │ - Store as   │
       │            │   text       │         │   BYTEA      │
       │            │ - Store in   │         │              │
       │            │   content_   │         │              │
       │            │   text       │         │              │
       │            └──────────────┘         └──────────────┘
       │                    │                         │
       │                    └────────────┬────────────┘
       │                                 │
       │                                 ▼
       │                         ┌─────────────────┐
       │                         │ Store in        │
       │                         │ Database        │
       │                         │                 │
       │                         │ - workspace_id  │
       │                         │ - user_id       │
       │                         │ - metadata      │
       │                         └─────────────────┘
       │                                 │
       │                                 ▼
       │                         Return attachment_id
       │
       └─── Invalid
              │
              ▼
       Return error (400)
```

## Security Design

### Workspace Isolation

**Critical Security Requirement**: All database queries MUST include workspace_id filtering.

**Implementation Pattern**:

```python
# CORRECT - Always filter by workspace_id
def get_conversations(user_id: int, workspace_id: int):
    return db.query(Conversation).filter(
        Conversation.user_id == user_id,
        Conversation.workspace_id == workspace_id
    ).all()

# WRONG - Never query without workspace filter
def get_conversations(user_id: int):
    return db.query(Conversation).filter(
        Conversation.user_id == user_id
    ).all()  # Security risk!
```

**Enforcement Mechanisms**:
1. Database foreign key constraints
2. Application-level validation in all service methods
3. Middleware to validate workspace access
4. Audit logging for all workspace access
5. Security tests to verify isolation

### Authentication & Authorization

**Middleware Flow**:

```python
async def validate_workspace_access(
    request: Request,
    workspace_id: int,
    user_id: int
) -> bool:
    """Validate user has access to workspace"""
    
    # Check if user belongs to workspace
    user_workspace = db.query(UserWorkspace).filter(
        UserWorkspace.user_id == user_id,
        UserWorkspace.workspace_id == workspace_id
    ).first()
    
    if not user_workspace:
        logger.warning(
            f"Workspace access denied: user={user_id}, workspace={workspace_id}"
        )
        raise HTTPException(status_code=403, detail="Workspace access denied")
    
    return True
```

### Data Masking

**Sensitive Data Protection**:

```python
def mask_sensitive_data(context: UserContext) -> UserContext:
    """Mask sensitive fields before sending to Claude AI"""
    
    # Mask connection passwords
    for conn in context.connections:
        if hasattr(conn, 'password'):
            conn.password = "***MASKED***"
        if hasattr(conn, 'connection_string'):
            conn.connection_string = mask_connection_string(conn.connection_string)
    
    # Mask API keys in metadata
    if context.metadata:
        for key in ['api_key', 'secret_key', 'token', 'password']:
            if key in context.metadata:
                context.metadata[key] = "***MASKED***"
    
    return context
```

### File Validation

**Security Checks**:

```python
def validate_file_security(file: UploadFile) -> Tuple[bool, Optional[str]]:
    """Validate file for security issues"""
    
    # Check file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_FILE_EXTENSIONS:
        return False, f"File type {ext} not allowed"
    
    # Check file size
    if file.size > MAX_FILE_SIZE:
        return False, f"File size exceeds {MAX_FILE_SIZE} bytes"
    
    # Check for executable content (basic validation)
    if ext in ['.txt', '.log', '.json']:
        content = file.file.read(1024)  # Read first 1KB
        file.file.seek(0)  # Reset file pointer
        
        # Check for suspicious patterns
        suspicious_patterns = [
            b'#!/bin/',  # Shebang
            b'<?php',    # PHP
            b'<script',  # JavaScript
        ]
        
        for pattern in suspicious_patterns:
            if pattern in content:
                return False, "File contains suspicious content"
    
    return True, None
```

### Rate Limiting

**Implementation**:

```python
from fastapi import Request
from fastapi.responses import JSONResponse
import time

# In-memory rate limiter (use Redis for production)
rate_limit_store = {}

async def rate_limit_middleware(request: Request, call_next):
    """Rate limit middleware - 30 messages per minute per user"""
    
    user_id = request.state.user_id
    current_time = time.time()
    
    # Get user's request history
    if user_id not in rate_limit_store:
        rate_limit_store[user_id] = []
    
    # Remove requests older than 1 minute
    rate_limit_store[user_id] = [
        t for t in rate_limit_store[user_id]
        if current_time - t < 60
    ]
    
    # Check rate limit
    if len(rate_limit_store[user_id]) >= 30:
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "error": "Rate limit exceeded. Maximum 30 messages per minute."
            }
        )
    
    # Add current request
    rate_limit_store[user_id].append(current_time)
    
    response = await call_next(request)
    return response
```


## Performance Optimizations

### Database Indexing Strategy

**Conversations Table**:
- Composite index on (workspace_id, user_id, updated_at DESC) for efficient filtering
- Index on (user_id, updated_at DESC) for user-specific queries
- Index on (workspace_id, updated_at DESC) for workspace-wide queries

**Messages Table**:
- Composite index on (conversation_id, created_at ASC) for message retrieval
- Full-text search index on content using PostgreSQL GIN index
- Index on created_at for time-based queries

**Attachments Table**:
- Index on message_id for attachment retrieval
- Composite index on (workspace_id, user_id, created_at DESC) for filtering

### Caching Strategy

**Redis Cache Keys**:
```
chat:context:{workspace_id}:{page_context}  # TTL: 5 minutes
chat:suggestions:{workspace_id}:{page_context}  # TTL: 5 minutes
chat:conversation:{conversation_id}:metadata  # TTL: 5 minutes
```

**Cache-Aside Pattern Implementation**:

```python
def get_context_with_cache(
    workspace_id: int,
    page_context: str
) -> UserContext:
    """Get context with Redis caching"""
    
    cache_key = f"chat:context:{workspace_id}:{page_context}"
    
    # Try Redis first
    try:
        cached = redis_client.get(cache_key)
        if cached:
            logger.debug(f"Cache hit: {cache_key}")
            return UserContext.parse_raw(cached)
    except (RedisError, ConnectionError) as e:
        logger.warning(f"Redis unavailable: {e}, falling back to database")
    
    # Fallback to database
    context = gather_context_from_db(workspace_id, page_context)
    
    # Try to cache (best effort)
    try:
        redis_client.setex(
            cache_key,
            300,  # 5 minutes
            context.json()
        )
    except Exception as e:
        logger.warning(f"Failed to cache context: {e}")
    
    return context
```

### Pagination Optimization

**Cursor-Based Pagination** for large result sets:

```python
def get_messages_cursor_based(
    conversation_id: int,
    cursor: Optional[int] = None,
    limit: int = 50
) -> Tuple[List[Message], Optional[int]]:
    """Get messages using cursor-based pagination"""
    
    query = db.query(Message).filter(
        Message.conversation_id == conversation_id
    )
    
    if cursor:
        query = query.filter(Message.id > cursor)
    
    messages = query.order_by(Message.id.asc()).limit(limit + 1).all()
    
    # Check if there are more results
    has_more = len(messages) > limit
    if has_more:
        messages = messages[:limit]
    
    # Next cursor is the last message ID
    next_cursor = messages[-1].id if has_more else None
    
    return messages, next_cursor
```

### Parallel Query Execution

**Async Context Gathering**:

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def gather_context_parallel(
    workspace_id: int,
    page_context: str
) -> UserContext:
    """Gather context data in parallel"""
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        loop = asyncio.get_event_loop()
        
        # Execute queries in parallel
        assessments_future = loop.run_in_executor(
            executor,
            get_assessments_context,
            workspace_id
        )
        
        connections_future = loop.run_in_executor(
            executor,
            get_connections_context,
            workspace_id
        )
        
        migrations_future = loop.run_in_executor(
            executor,
            get_migrations_context,
            workspace_id
        )
        
        # Wait for all queries to complete
        assessments, connections, migrations = await asyncio.gather(
            assessments_future,
            connections_future,
            migrations_future,
            return_exceptions=True
        )
        
        # Handle partial failures
        if isinstance(assessments, Exception):
            logger.error(f"Failed to get assessments: {assessments}")
            assessments = []
        
        if isinstance(connections, Exception):
            logger.error(f"Failed to get connections: {connections}")
            connections = []
        
        if isinstance(migrations, Exception):
            logger.error(f"Failed to get migrations: {migrations}")
            migrations = []
        
        return UserContext(
            workspace_id=workspace_id,
            page_context=page_context,
            assessments=assessments,
            connections=connections,
            migrations=migrations
        )
```

### Database Connection Pooling

**Configuration** (in database.py):

```python
engine = create_engine(
    database_url,
    poolclass=QueuePool,
    pool_size=20,  # Number of connections to maintain
    max_overflow=10,  # Additional connections when pool is full
    pool_timeout=30,  # Timeout waiting for connection
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600  # Recycle connections after 1 hour
)
```

### Message Table Partitioning

**For Large Datasets** (>1 million messages):

```sql
-- Partition messages table by month
CREATE TABLE messages_2026_01 PARTITION OF messages
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE TABLE messages_2026_02 PARTITION OF messages
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

-- Create partitions automatically
CREATE OR REPLACE FUNCTION create_message_partition()
RETURNS void AS $$
DECLARE
    partition_date DATE;
    partition_name TEXT;
    start_date TEXT;
    end_date TEXT;
BEGIN
    partition_date := DATE_TRUNC('month', CURRENT_DATE);
    partition_name := 'messages_' || TO_CHAR(partition_date, 'YYYY_MM');
    start_date := TO_CHAR(partition_date, 'YYYY-MM-DD');
    end_date := TO_CHAR(partition_date + INTERVAL '1 month', 'YYYY-MM-DD');
    
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF messages FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date
    );
END;
$$ LANGUAGE plpgsql;
```

## Error Handling

### Error Response Format

**Consistent Error Structure**:

```python
class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    data: None = None
    error: str
    error_code: Optional[str] = None
    details: Optional[dict] = None

# Example usage
@router.post("/api/chat/message")
async def send_message(request: ChatMessageRequest):
    try:
        # Process message
        pass
    except ValidationError as e:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error="Invalid request data",
                error_code="VALIDATION_ERROR",
                details={"fields": e.errors()}
            ).dict()
        )
    except WorkspaceAccessDenied as e:
        return JSONResponse(
            status_code=403,
            content=ErrorResponse(
                error="Workspace access denied",
                error_code="WORKSPACE_ACCESS_DENIED"
            ).dict()
        )
```

### Claude AI Error Handling

**Retry Logic with Exponential Backoff**:

```python
import time
from botocore.exceptions import ClientError

def call_claude_with_retry(
    request_body: dict,
    max_retries: int = 3
) -> dict:
    """Call Claude AI with retry logic"""
    
    for attempt in range(max_retries):
        try:
            response = bedrock_runtime.invoke_model(
                modelId=CLAUDE_MODEL_ID,
                body=json.dumps(request_body)
            )
            return json.loads(response['body'].read())
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            # Don't retry on client errors
            if error_code in ['ValidationException', 'AccessDeniedException']:
                raise
            
            # Retry on throttling or server errors
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                logger.warning(
                    f"Claude AI error (attempt {attempt + 1}/{max_retries}): {e}. "
                    f"Retrying in {wait_time:.2f}s"
                )
                time.sleep(wait_time)
            else:
                logger.error(f"Claude AI failed after {max_retries} attempts: {e}")
                raise
        
        except Exception as e:
            logger.error(f"Unexpected error calling Claude AI: {e}")
            raise
```

### Partial Failure Handling

**Graceful Degradation**:

```python
def gather_context_with_fallback(
    workspace_id: int,
    page_context: str
) -> UserContext:
    """Gather context with graceful degradation"""
    
    context = UserContext(
        workspace_id=workspace_id,
        page_context=page_context
    )
    
    # Try to get assessments
    try:
        context.assessments = get_assessments_context(workspace_id)
    except Exception as e:
        logger.error(f"Failed to get assessments context: {e}")
        context.assessments = []
    
    # Try to get connections
    try:
        context.connections = get_connections_context(workspace_id)
    except Exception as e:
        logger.error(f"Failed to get connections context: {e}")
        context.connections = []
    
    # Try to get migrations
    try:
        context.migrations = get_migrations_context(workspace_id)
    except Exception as e:
        logger.error(f"Failed to get migrations context: {e}")
        context.migrations = []
    
    # Continue even if all context gathering failed
    return context
```

### Database Transaction Management

**Atomic Operations**:

```python
from sqlalchemy.exc import SQLAlchemyError

def store_message_with_attachments(
    conversation_id: int,
    role: str,
    content: str,
    attachments: List[Attachment]
) -> Message:
    """Store message and attachments atomically"""
    
    try:
        # Start transaction
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )
        db.add(message)
        db.flush()  # Get message ID
        
        # Store attachments
        for attachment in attachments:
            attachment.message_id = message.id
            db.add(attachment)
        
        # Commit transaction
        db.commit()
        db.refresh(message)
        
        return message
        
    except SQLAlchemyError as e:
        # Rollback on error
        db.rollback()
        logger.error(f"Failed to store message with attachments: {e}")
        raise
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, I identified the following redundancies:

**Redundant Properties**:
- Requirements 1.4 and 1.8 both test workspace isolation - can be combined
- Requirements 3.8, 5.11 also test workspace isolation - same property
- Requirements 5.1 and 5.3 both test file extension validation - can be combined
- Requirements 5.2 and 5.4 both test file size validation - can be combined
- Requirements 1.5 and 5.12 both test cascade deletion - can be combined

**Combined Properties**:
- Single comprehensive workspace isolation property covering all operations
- Single file validation property covering both size and extension
- Single cascade deletion property covering conversations and attachments

### Property 1: Message Storage Completeness

*For any* user message with valid content, workspace_id, user_id, and page_context, storing the message in the database should result in a record containing all provided fields with matching values and a generated timestamp.

**Validates: Requirements 1.1**

### Property 2: Response Linkage

*For any* stored user message, when an AI response is generated and stored, the response message should have the same conversation_id as the user message and a role of 'assistant'.

**Validates: Requirements 1.2**

### Property 3: Message Ordering

*For any* conversation, retrieving messages should return them ordered by created_at timestamp in ascending order, with earlier messages appearing before later messages.

**Validates: Requirements 1.3**

### Property 4: Workspace Isolation

*For any* two different workspace_ids, querying conversations, messages, or attachments with one workspace_id should never return data associated with the other workspace_id.

**Validates: Requirements 1.4, 1.8, 3.8, 5.11, 13.1**

### Property 5: Cascade Deletion

*For any* conversation, deleting the conversation should result in all associated messages and attachments being deleted from the database.

**Validates: Requirements 1.5, 5.12**

### Property 6: Pagination Bounds

*For any* pagination request with page_size parameter, the returned results should contain at most min(page_size, 100) items, enforcing the maximum page size limit.

**Validates: Requirements 1.7**

### Property 7: Context Data Limiting

*For any* context gathering operation, the returned context should contain at most 20 items per category (assessments, connections, migrations).

**Validates: Requirements 3.7**

### Property 8: Context Resilience

*For any* context gathering operation where one data source fails, the operation should still return a UserContext object with available data from successful sources and empty lists for failed sources.

**Validates: Requirements 3.9**

### Property 9: Suggested Questions Format

*For any* page_context value, the suggested questions endpoint should return exactly 4 questions, each with question_text, category, and priority fields.

**Validates: Requirements 4.1, 4.2, 4.3**

### Property 10: File Extension Validation

*For any* uploaded file, the file should be accepted if and only if its extension is in the allowed list ['.txt', '.log', '.json', '.png', '.jpg', '.jpeg'].

**Validates: Requirements 5.1, 5.3, 5.4**

### Property 11: File Size Validation

*For any* uploaded file, the file should be accepted if and only if its size is greater than 0 bytes and less than or equal to 5,242,880 bytes (5MB).

**Validates: Requirements 5.2, 5.4**

### Property 12: Attachment Storage Separation

*For any* uploaded file, if the file is a text file (.txt, .log, .json), it should be stored in content_text column with content_binary as NULL; if the file is a binary file (.png, .jpg, .jpeg), it should be stored in content_binary column with content_text as NULL.

**Validates: Requirements 5.7**

### Property 13: Text Content Extraction

*For any* text file attachment (.txt, .log, .json), extracting content should return the file's text content as a string.

**Validates: Requirements 5.8**

### Property 14: Image Base64 Encoding

*For any* image attachment (.png, .jpg, .jpeg), encoding the image should return a valid base64 string that can be decoded back to the original binary content.

**Validates: Requirements 5.9**

### Property 15: Attachment ID Uniqueness

*For any* two different uploaded files, they should be assigned different attachment_id values.

**Validates: Requirements 5.6**

### Property 16: Conversation Export Round-Trip

*For any* conversation, exporting to JSON format and then parsing the JSON should produce a data structure containing all messages with matching content, roles, and timestamps.

**Validates: Requirements 12.1, 12.2, 12.3**

### Property 17: Sensitive Data Masking

*For any* context data containing connection objects with password or connection_string fields, the masked context should have these fields replaced with "***MASKED***" or equivalent masked values.

**Validates: Requirements 13.2, 13.3**

### Property 18: Search Result Relevance

*For any* search query, all returned messages should contain the search query text (case-insensitive) in their content field.

**Validates: Requirements 11.1, 11.2**

### Property 19: Pagination Consistency

*For any* paginated query with page=1 and page=2, the union of results from both pages should contain no duplicate items, and items should appear in consistent order.

**Validates: Requirements 1.7, 7.9**

### Property 20: Context JSON Serialization

*For any* UserContext object, serializing to JSON and then deserializing should produce an equivalent UserContext object with matching field values.

**Validates: Requirements 3.6**


## Testing Strategy

### Dual Testing Approach

This feature requires both unit tests and property-based tests for comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, API endpoints, and error conditions
- **Property tests**: Verify universal properties across all inputs using randomization

Both testing approaches are complementary and necessary. Unit tests catch concrete bugs and validate specific scenarios, while property tests verify general correctness across a wide range of inputs.

### Property-Based Testing Configuration

**Library**: Use `hypothesis` for Python property-based testing

**Configuration**:
```python
from hypothesis import given, settings, strategies as st

# Configure for CI/CD
settings.register_profile("ci", max_examples=100, deadline=None)
settings.register_profile("dev", max_examples=20, deadline=None)
settings.load_profile("ci" if os.getenv("CI") else "dev")
```

**Minimum Iterations**: 100 iterations per property test (due to randomization)

**Test Tagging**: Each property test must reference its design document property

```python
@given(
    workspace_id=st.integers(min_value=1, max_value=1000),
    user_id=st.integers(min_value=1, max_value=1000),
    message_content=st.text(min_size=1, max_size=1000)
)
@settings(max_examples=100)
def test_message_storage_completeness(workspace_id, user_id, message_content):
    """
    Feature: chatagent-production-enhancements
    Property 1: For any user message with valid content, workspace_id, user_id,
    and page_context, storing the message in the database should result in a
    record containing all provided fields with matching values.
    """
    # Test implementation
    pass
```

### Unit Testing Strategy

**Focus Areas**:
1. API endpoints with sample payloads (success, validation errors, auth errors)
2. Specific edge cases (empty workspace, failed assessments, large files)
3. Error conditions (database failures, Redis unavailable, Claude AI timeout)
4. Integration points between services

**Sample Payloads Repository**:

```python
# tests/fixtures/chat_payloads.py

# Valid chat message
VALID_CHAT_MESSAGE = {
    "message": "How do I create a new assessment?",
    "conversation_id": 123,
    "page_context": "assessments",
    "attachment_ids": []
}

# Invalid chat message - empty
INVALID_CHAT_MESSAGE_EMPTY = {
    "message": "",
    "page_context": "dashboard"
}

# Invalid chat message - missing required field
INVALID_CHAT_MESSAGE_MISSING_FIELD = {
    "page_context": "assessments"
}

# Valid file upload
VALID_TEXT_FILE = {
    "filename": "error.log",
    "content": b"Error: Connection timeout\nStack trace...",
    "mime_type": "text/plain",
    "size": 1024
}

# Invalid file upload - too large
INVALID_FILE_TOO_LARGE = {
    "filename": "large.log",
    "content": b"x" * (6 * 1024 * 1024),  # 6MB
    "mime_type": "text/plain",
    "size": 6 * 1024 * 1024
}

# Invalid file upload - wrong extension
INVALID_FILE_WRONG_EXTENSION = {
    "filename": "script.exe",
    "content": b"MZ\x90\x00",
    "mime_type": "application/x-msdownload",
    "size": 1024
}

# Valid conversation search
VALID_SEARCH_REQUEST = {
    "query": "schema compatibility",
    "page": 1,
    "page_size": 50
}

# Valid suggested questions request
VALID_SUGGESTED_QUESTIONS_REQUEST = {
    "page_context": "assessments"
}
```

### Test Organization

```
backend/tests/
├── unit/
│   ├── test_conversation_service.py
│   ├── test_context_service.py
│   ├── test_attachment_service.py
│   └── test_claude_ai_service.py
├── integration/
│   ├── test_chat_endpoints.py
│   ├── test_conversation_endpoints.py
│   ├── test_attachment_endpoints.py
│   └── test_search_endpoints.py
├── property/
│   ├── test_workspace_isolation.py
│   ├── test_message_storage.py
│   ├── test_file_validation.py
│   ├── test_pagination.py
│   └── test_export_roundtrip.py
├── fixtures/
│   ├── chat_payloads.py
│   ├── test_data.py
│   └── mock_responses.py
└── conftest.py
```

### Example Unit Tests

**API Endpoint Test**:

```python
def test_send_message_success(client, auth_headers, db_session):
    """Test POST /api/chat/message with valid payload"""
    
    payload = {
        "message": "How do I create a new assessment?",
        "page_context": "assessments"
    }
    
    response = client.post(
        "/api/chat/message",
        json=payload,
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "response" in data["data"]
    assert "conversation_id" in data["data"]
    assert "message_id" in data["data"]

def test_send_message_empty_content(client, auth_headers):
    """Test POST /api/chat/message with empty message"""
    
    payload = {
        "message": "",
        "page_context": "dashboard"
    }
    
    response = client.post(
        "/api/chat/message",
        json=payload,
        headers=auth_headers
    )
    
    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "empty" in data["error"].lower()

def test_send_message_workspace_access_denied(client, auth_headers):
    """Test POST /api/chat/message with unauthorized workspace"""
    
    payload = {
        "message": "Test message",
        "page_context": "dashboard"
    }
    
    # Use headers with different workspace_id
    invalid_headers = {**auth_headers, "X-Workspace-ID": "999"}
    
    response = client.post(
        "/api/chat/message",
        json=payload,
        headers=invalid_headers
    )
    
    assert response.status_code == 403
    data = response.json()
    assert data["success"] is False
    assert "workspace" in data["error"].lower()
```

### Example Property Tests

**Workspace Isolation Property**:

```python
from hypothesis import given, strategies as st

@given(
    workspace_id_1=st.integers(min_value=1, max_value=100),
    workspace_id_2=st.integers(min_value=101, max_value=200),
    user_id=st.integers(min_value=1, max_value=1000)
)
@settings(max_examples=100)
def test_workspace_isolation_property(
    workspace_id_1,
    workspace_id_2,
    user_id,
    conversation_service
):
    """
    Feature: chatagent-production-enhancements
    Property 4: For any two different workspace_ids, querying conversations
    with one workspace_id should never return data associated with the other.
    """
    
    # Create conversations in both workspaces
    conv1 = conversation_service.create_conversation(user_id, workspace_id_1)
    conv2 = conversation_service.create_conversation(user_id, workspace_id_2)
    
    # Query workspace 1
    convs_ws1 = conversation_service.get_conversations(user_id, workspace_id_1)
    
    # Query workspace 2
    convs_ws2 = conversation_service.get_conversations(user_id, workspace_id_2)
    
    # Assert no overlap
    conv_ids_ws1 = {c.id for c in convs_ws1}
    conv_ids_ws2 = {c.id for c in convs_ws2}
    
    assert conv1.id in conv_ids_ws1
    assert conv1.id not in conv_ids_ws2
    assert conv2.id in conv_ids_ws2
    assert conv2.id not in conv_ids_ws1
```

**File Validation Property**:

```python
@given(
    file_size=st.integers(min_value=0, max_value=10 * 1024 * 1024),
    file_extension=st.sampled_from([
        '.txt', '.log', '.json', '.png', '.jpg', '.jpeg',
        '.exe', '.sh', '.bat', '.pdf', '.doc'
    ])
)
@settings(max_examples=100)
def test_file_validation_property(file_size, file_extension, attachment_service):
    """
    Feature: chatagent-production-enhancements
    Property 10 & 11: File should be accepted if and only if extension is
    allowed AND size is between 0 and 5MB.
    """
    
    allowed_extensions = ['.txt', '.log', '.json', '.png', '.jpg', '.jpeg']
    max_size = 5 * 1024 * 1024
    
    is_valid_extension = file_extension in allowed_extensions
    is_valid_size = 0 < file_size <= max_size
    should_accept = is_valid_extension and is_valid_size
    
    # Create mock file
    mock_file = MockUploadFile(
        filename=f"test{file_extension}",
        content=b"x" * file_size,
        size=file_size
    )
    
    is_valid, error = attachment_service.validate_file(mock_file)
    
    assert is_valid == should_accept
    if not should_accept:
        assert error is not None
```

**Export Round-Trip Property**:

```python
@given(
    num_messages=st.integers(min_value=1, max_value=50),
    message_content=st.text(min_size=1, max_size=500)
)
@settings(max_examples=100)
def test_export_roundtrip_property(
    num_messages,
    message_content,
    conversation_service
):
    """
    Feature: chatagent-production-enhancements
    Property 16: For any conversation, exporting to JSON and parsing should
    produce equivalent data with matching content, roles, and timestamps.
    """
    
    # Create conversation with messages
    conversation = create_test_conversation()
    for i in range(num_messages):
        role = "user" if i % 2 == 0 else "assistant"
        conversation_service.store_message(
            conversation.id,
            role,
            f"{message_content}_{i}"
        )
    
    # Export to JSON
    exported_json = conversation_service.export_conversation(
        conversation.id,
        format="json"
    )
    
    # Parse JSON
    parsed_data = json.loads(exported_json)
    
    # Verify equivalence
    assert parsed_data["conversation_id"] == conversation.id
    assert len(parsed_data["messages"]) == num_messages
    
    for i, msg in enumerate(parsed_data["messages"]):
        assert msg["role"] in ["user", "assistant"]
        assert f"{message_content}_{i}" in msg["content"]
        assert "timestamp" in msg
```

### Integration Testing

**End-to-End Flow Test**:

```python
def test_complete_chat_flow(client, auth_headers, db_session):
    """Test complete chat flow from message send to retrieval"""
    
    # 1. Send first message
    response1 = client.post(
        "/api/chat/message",
        json={"message": "How do I create an assessment?", "page_context": "assessments"},
        headers=auth_headers
    )
    assert response1.status_code == 200
    conversation_id = response1.json()["data"]["conversation_id"]
    
    # 2. Send follow-up message
    response2 = client.post(
        "/api/chat/message",
        json={
            "message": "What about schema analysis?",
            "conversation_id": conversation_id,
            "page_context": "assessments"
        },
        headers=auth_headers
    )
    assert response2.status_code == 200
    
    # 3. Retrieve conversation history
    response3 = client.get(
        f"/api/chat/conversations/{conversation_id}/messages",
        headers=auth_headers
    )
    assert response3.status_code == 200
    messages = response3.json()["data"]["messages"]
    assert len(messages) >= 4  # 2 user + 2 assistant
    
    # 4. Search conversation
    response4 = client.post(
        "/api/chat/search",
        json={"query": "assessment"},
        headers=auth_headers
    )
    assert response4.status_code == 200
    results = response4.json()["data"]["results"]
    assert len(results) > 0
    
    # 5. Export conversation
    response5 = client.get(
        f"/api/chat/conversations/{conversation_id}/export?format=json",
        headers=auth_headers
    )
    assert response5.status_code == 200
    assert response5.headers["content-type"] == "application/json"
```

### Performance Testing

**Load Test Example**:

```python
import time

def test_context_gathering_performance(context_service, workspace_id):
    """Test context gathering completes within 500ms"""
    
    start_time = time.time()
    context = context_service.gather_context(
        user_id=1,
        workspace_id=workspace_id,
        page_context="assessments"
    )
    end_time = time.time()
    
    elapsed_ms = (end_time - start_time) * 1000
    assert elapsed_ms < 500, f"Context gathering took {elapsed_ms}ms, expected <500ms"
```

### Test Coverage Goals

- **Backend Services**: Minimum 80% code coverage
- **API Endpoints**: 100% endpoint coverage with sample payloads
- **Property Tests**: All 20 correctness properties implemented
- **Critical Paths**: 100% coverage for workspace isolation and security


## Integration with Existing ChatAgent Component

### Frontend Integration

**Current ChatAgent Component** (frontend/src/components/ChatAgent/ChatAgent.tsx):

The existing component provides:
- Modal-based chat interface
- Message display with markdown rendering
- Suggested questions UI
- Loading states and error handling
- Conversation history display

**Required Enhancements**:

1. **Add File Upload UI**:
```tsx
// Add to ChatAgent component
const [attachments, setAttachments] = useState<File[]>([]);
const fileInputRef = useRef<HTMLInputElement>(null);

const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
  const files = Array.from(e.target.files || []);
  
  // Validate files
  const validFiles = files.filter(file => {
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    const allowedExts = ['.txt', '.log', '.json', '.png', '.jpg', '.jpeg'];
    const maxSize = 5 * 1024 * 1024; // 5MB
    
    if (!allowedExts.includes(ext)) {
      alert(`File type ${ext} not allowed`);
      return false;
    }
    
    if (file.size > maxSize) {
      alert(`File ${file.name} exceeds 5MB limit`);
      return false;
    }
    
    return true;
  });
  
  setAttachments(prev => [...prev, ...validFiles]);
};

const uploadAttachments = async (files: File[]): Promise<number[]> => {
  const attachmentIds: number[] = [];
  
  for (const file of files) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch('/api/chat/attachments', {
      method: 'POST',
      body: formData,
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      attachmentIds.push(data.data.id);
    }
  }
  
  return attachmentIds;
};
```

2. **Update Message Send Logic**:
```tsx
const handleSendMessage = async (messageText?: string) => {
  const text = messageText || inputValue.trim();
  if (!text || isLoading) return;

  // Upload attachments first
  let attachmentIds: number[] = [];
  if (attachments.length > 0) {
    attachmentIds = await uploadAttachments(attachments);
    setAttachments([]); // Clear after upload
  }

  const userMessage: Message = {
    id: Date.now().toString(),
    text,
    sender: 'user',
    timestamp: new Date()
  };
  
  setMessages(prev => [...prev, userMessage]);
  setInputValue('');
  setIsLoading(true);

  try {
    const response = await fetch('/api/chat/message', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        message: text,
        conversation_id: currentConversationId,
        page_context: currentPage,
        attachment_ids: attachmentIds
      })
    });

    if (!response.ok) {
      throw new Error('Failed to get response');
    }

    const data = await response.json();
    
    // Update conversation ID if new conversation
    if (!currentConversationId) {
      setCurrentConversationId(data.data.conversation_id);
    }

    const aiMessage: Message = {
      id: data.data.message_id.toString(),
      text: data.data.response,
      sender: 'ai',
      timestamp: new Date(data.data.timestamp)
    };

    setMessages(prev => [...prev, aiMessage]);
  } catch (error) {
    console.error('ChatAgent error:', error);
    // Error handling...
  } finally {
    setIsLoading(false);
  }
};
```

3. **Add Conversation History Loading**:
```tsx
useEffect(() => {
  if (isOpen) {
    loadConversationHistory();
  }
}, [isOpen]);

const loadConversationHistory = async () => {
  try {
    const response = await fetch('/api/chat/conversations', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      const conversations = data.data.conversations;
      
      // Load most recent conversation
      if (conversations.length > 0) {
        const latestConv = conversations[0];
        setCurrentConversationId(latestConv.id);
        loadMessages(latestConv.id);
      }
    }
  } catch (error) {
    console.error('Failed to load conversation history:', error);
  }
};

const loadMessages = async (conversationId: number) => {
  try {
    const response = await fetch(
      `/api/chat/conversations/${conversationId}/messages`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );
    
    if (response.ok) {
      const data = await response.json();
      const loadedMessages = data.data.messages.map((msg: any) => ({
        id: msg.id.toString(),
        text: msg.content,
        sender: msg.role === 'user' ? 'user' : 'ai',
        timestamp: new Date(msg.created_at)
      }));
      
      setMessages(loadedMessages);
    }
  } catch (error) {
    console.error('Failed to load messages:', error);
  }
};
```

4. **Update Suggested Questions to Use API**:
```tsx
useEffect(() => {
  if (isOpen && showHomeView) {
    loadSuggestedQuestions();
  }
}, [isOpen, showHomeView, currentPage]);

const loadSuggestedQuestions = async () => {
  try {
    const response = await fetch(
      `/api/chat/suggested-questions?page_context=${currentPage}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );
    
    if (response.ok) {
      const data = await response.json();
      setSuggestedQuestions(data.data.questions.map((q: any) => q.question_text));
    }
  } catch (error) {
    console.error('Failed to load suggested questions:', error);
    // Fall back to static questions
  }
};
```

5. **Add Search Functionality**:
```tsx
const [searchQuery, setSearchQuery] = useState('');
const [searchResults, setSearchResults] = useState<Message[]>([]);

const handleSearch = async (query: string) => {
  if (!query.trim()) return;
  
  try {
    const response = await fetch('/api/chat/search', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        query: query,
        page: 1,
        page_size: 50
      })
    });
    
    if (response.ok) {
      const data = await response.json();
      const results = data.data.results.map((r: any) => ({
        id: r.message.id.toString(),
        text: r.message.content,
        sender: r.message.role === 'user' ? 'user' : 'ai',
        timestamp: new Date(r.message.created_at)
      }));
      
      setSearchResults(results);
    }
  } catch (error) {
    console.error('Search failed:', error);
  }
};
```

### Backend Integration

**Current Router** (backend/routers/chatagent_router.py):

The existing router provides:
- POST /api/chatagent endpoint
- Claude AI integration via Bedrock
- Basic conversation handling

**Required Changes**:

1. **Rename and Restructure Router**:
```python
# Rename from chatagent_router.py to chat_router.py
router = APIRouter(prefix="/api/chat", tags=["chat"])
```

2. **Add Service Dependencies**:
```python
from services.conversation_service import ConversationService
from services.context_service import ContextService
from services.attachment_service import AttachmentService
from services.claude_ai_service import ClaudeAIService

def get_conversation_service(db: Session = Depends(get_db)):
    redis_client = get_redis_client()
    return ConversationService(db, redis_client)

def get_context_service(db: Session = Depends(get_db)):
    redis_client = get_redis_client()
    return ContextService(db, redis_client)

def get_attachment_service(db: Session = Depends(get_db)):
    return AttachmentService(db)

def get_claude_service():
    bedrock_client = get_bedrock_client()
    return ClaudeAIService(bedrock_client)
```

3. **Update Main Endpoint**:
```python
@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
    conversation_service: ConversationService = Depends(get_conversation_service),
    context_service: ContextService = Depends(get_context_service),
    attachment_service: AttachmentService = Depends(get_attachment_service),
    claude_service: ClaudeAIService = Depends(get_claude_service)
):
    """Send a message to ChatAgent and receive AI response"""
    
    try:
        # Validate workspace access
        await validate_workspace_access(current_user.id, workspace_id)
        
        # Get or create conversation
        if request.conversation_id:
            conversation = conversation_service.get_conversation(
                request.conversation_id,
                current_user.id,
                workspace_id
            )
        else:
            conversation = conversation_service.create_conversation(
                current_user.id,
                workspace_id
            )
        
        # Store user message
        user_message = conversation_service.store_message(
            conversation.id,
            "user",
            request.message,
            request.page_context
        )
        
        # Gather context
        context = await context_service.gather_context(
            current_user.id,
            workspace_id,
            request.page_context
        )
        
        # Get attachments
        attachments = []
        if request.attachment_ids:
            attachments = attachment_service.get_attachments_by_ids(
                request.attachment_ids,
                workspace_id
            )
        
        # Get conversation history
        history = conversation_service.get_recent_messages(
            conversation.id,
            limit=10
        )
        
        # Generate AI response
        ai_response = await claude_service.generate_response(
            request.message,
            context,
            history,
            attachments
        )
        
        # Store AI response
        ai_message = conversation_service.store_message(
            conversation.id,
            "assistant",
            ai_response
        )
        
        return ChatMessageResponse(
            response=ai_response,
            conversation_id=conversation.id,
            message_id=ai_message.id,
            timestamp=ai_message.created_at
        )
        
    except Exception as e:
        logger.error(f"Error in send_message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

4. **Add New Endpoints**:
```python
@router.get("/conversations", response_model=ConversationListResponse)
async def get_conversations(
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Get all conversations for user in workspace"""
    # Implementation...

@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: int,
    page: int = 1,
    page_size: int = 50,
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Get messages for a conversation"""
    # Implementation...

@router.post("/attachments", response_model=AttachmentResponse)
async def upload_attachment(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
    attachment_service: AttachmentService = Depends(get_attachment_service)
):
    """Upload a file attachment"""
    # Implementation...

@router.get("/suggested-questions")
async def get_suggested_questions(
    page_context: str,
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
    context_service: ContextService = Depends(get_context_service)
):
    """Get context-aware suggested questions"""
    # Implementation...

@router.post("/search")
async def search_conversations(
    request: ConversationSearchRequest,
    current_user: User = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
    conversation_service: ConversationService = Depends(get_conversation_service)
):
    """Search conversation history"""
    # Implementation...
```

### Database Migration

**Alembic Migration Script**:

```python
"""Add chat tables for conversation persistence

Revision ID: add_chat_tables
Revises: previous_revision
Create Date: 2026-01-25 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_chat_tables'
down_revision = 'previous_revision'
branch_labels = None
depends_on = None

def upgrade():
    # Create conversations table
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for conversations
    op.create_index('idx_conversations_workspace_user', 'conversations', ['workspace_id', 'user_id', 'updated_at'], postgresql_ops={'updated_at': 'DESC'})
    op.create_index('idx_conversations_user', 'conversations', ['user_id', 'updated_at'], postgresql_ops={'updated_at': 'DESC'})
    op.create_index('idx_conversations_workspace', 'conversations', ['workspace_id', 'updated_at'], postgresql_ops={'updated_at': 'DESC'})
    
    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('page_context', sa.String(50), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name='chk_messages_role'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for messages
    op.create_index('idx_messages_conversation_created', 'messages', ['conversation_id', 'created_at'])
    op.create_index('idx_messages_created', 'messages', ['created_at'], postgresql_ops={'created_at': 'DESC'})
    
    # Create full-text search index
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
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint('file_size > 0 AND file_size <= 5242880', name='chk_attachments_size'),
        sa.CheckConstraint(
            "(content_text IS NOT NULL AND content_binary IS NULL) OR (content_text IS NULL AND content_binary IS NOT NULL)",
            name='chk_attachments_content'
        ),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for attachments
    op.create_index('idx_attachments_message', 'attachments', ['message_id'])
    op.create_index('idx_attachments_workspace_user', 'attachments', ['workspace_id', 'user_id', 'created_at'], postgresql_ops={'created_at': 'DESC'})

def downgrade():
    op.drop_table('attachments')
    op.drop_table('messages')
    op.drop_table('conversations')
```

### Configuration Updates

**Environment Variables** (.env):

```bash
# Existing Claude AI configuration
CLAUDE_USE_BEDROCK=true
CLAUDE_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
CLAUDE_MAX_TOKENS=4096
CLAUDE_TEMPERATURE=0.7
AWS_REGION=us-east-1

# New chat-specific configuration
CHAT_RATE_LIMIT_PER_MINUTE=30
CHAT_MAX_ATTACHMENT_SIZE=5242880
CHAT_CONTEXT_CACHE_TTL=300
CHAT_SUGGESTED_QUESTIONS_CACHE_TTL=300
CHAT_MAX_CONTEXT_ITEMS=20
CHAT_MAX_CONVERSATION_HISTORY=10
```

## Deployment Considerations

### Database Setup

1. Run Alembic migration to create tables
2. Create database indexes
3. Verify foreign key constraints
4. Test cascade deletion behavior

### Redis Configuration

1. Configure Redis connection in .env
2. Set up Redis cache keys with appropriate TTLs
3. Test fallback to database when Redis unavailable
4. Monitor cache hit/miss ratios

### AWS Bedrock Setup

1. Verify AWS credentials and IAM permissions
2. Test Bedrock API connectivity
3. Configure timeout and retry settings
4. Monitor API usage and costs

### Monitoring Setup

1. Configure CloudWatch metrics for chat operations
2. Set up alarms for high error rates
3. Monitor Claude AI API latency
4. Track conversation and message counts
5. Monitor attachment storage usage

### Security Checklist

- [ ] Workspace isolation tested and verified
- [ ] File upload validation implemented
- [ ] Rate limiting configured
- [ ] Sensitive data masking implemented
- [ ] Audit logging enabled
- [ ] HTTPS enforced for all endpoints
- [ ] Authentication required for all endpoints
- [ ] SQL injection prevention verified
- [ ] XSS prevention in frontend

