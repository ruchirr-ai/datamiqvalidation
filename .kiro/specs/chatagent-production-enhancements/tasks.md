# Implementation Plan: ChatAgent Production Enhancements

## Overview

This implementation plan transforms the ChatAgent feature from a basic chat interface into a production-ready, intelligent assistant with conversation persistence, context-aware responses, file attachments, and comprehensive testing. The implementation follows a bottom-up approach: database → services → API → frontend → testing.

## Tasks

- [x] 1. Set up database schema and migrations
  - Create Alembic migration for conversations, messages, and attachments tables
  - Add indexes for efficient querying (workspace_id, user_id, created_at)
  - Add full-text search index on messages.content using PostgreSQL GIN
  - Test migration up and down operations
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 5.6, 5.7_

- [x] 2. Create Pydantic models for chat domain
  - [x] 2.1 Create conversation models (ConversationBase, ConversationCreate, Conversation, ConversationInfo)
    - Define models in backend/models/conversation.py
    - Include workspace_id and user_id for multi-tenancy
    - _Requirements: 1.1, 1.4_
  
  - [x] 2.2 Create message models (MessageBase, MessageCreate, Message, MessageWithAttachments)
    - Define models in backend/models/message.py
    - Include role validation (user/assistant)
    - Include page_context and metadata fields
    - _Requirements: 1.2, 1.3_
  
  - [x] 2.3 Create attachment models (AttachmentBase, AttachmentCreate, Attachment, AttachmentInfo)
    - Define models in backend/models/attachment.py
    - Include file size and type validation
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6, 5.7_
  
  - [x] 2.4 Create request/response models (ChatMessageRequest, ChatMessageResponse, SuggestedQuestionsResponse, ConversationSearchRequest)
    - Define models in backend/models/chat_api.py
    - Include pagination models
    - _Requirements: 1.7, 4.1, 4.2, 11.1_

- [-] 3. Implement ConversationService
  - [x] 3.1 Create ConversationService class with database and Redis dependencies
    - Create backend/services/conversation_service.py
    - Initialize with database session and Redis client
    - _Requirements: 1.1_
  
  - [x] 3.2 Implement create_conversation method
    - Accept user_id and workspace_id parameters
    - Create conversation record in database
    - Return Conversation object
    - _Requirements: 1.1, 1.4_
  
  - [x] 3.3 Implement get_conversations method with pagination
    - Filter by user_id and workspace_id
    - Order by updated_at DESC
    - Support page and page_size parameters (max 100)
    - Return tuple of (conversations, total_count)
    - _Requirements: 1.4, 1.7, 7.1, 7.2_
  
  - [ ] 3.4 Implement store_message method
    - Accept conversation_id, role, content, page_context, metadata
    - Validate role is 'user' or 'assistant'
    - Store message in database
    - Update conversation.updated_at timestamp
    - Return Message object
    - _Requirements: 1.1, 1.2, 1.3_
  
  - [ ] 3.5 Implement get_conversation_messages method with pagination
    - Filter by conversation_id
    - Validate workspace access
    - Order by created_at ASC
    - Support cursor-based pagination
    - Include attachments for each message
    - _Requirements: 1.3, 1.4, 1.7, 7.3_
  
  - [ ] 3.6 Implement delete_conversation method
    - Validate user owns conversation
    - Validate workspace access
    - Delete conversation (cascade to messages and attachments)
    - Return success boolean
    - _Requirements: 1.5, 1.8, 5.12_
  
  - [ ] 3.7 Implement search_conversations method with full-text search
    - Use PostgreSQL to_tsvector for full-text search
    - Filter by workspace_id
    - Return messages with context (previous/next messages)
    - Support pagination
    - _Requirements: 11.1, 11.2, 11.3_
  
  - [ ] 3.8 Implement export_conversation method
    - Support JSON and Markdown formats
    - Include all messages with timestamps
    - Validate workspace access
    - Return formatted string
    - _Requirements: 12.1, 12.2, 12.3_

- [ ] 4. Checkpoint - Ensure ConversationService tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement ContextService
  - [ ] 5.1 Create ContextService class with repository dependencies
    - Create backend/services/context_service.py
    - Initialize with database session, Redis client, and repositories
    - _Requirements: 3.1_
  
  - [ ] 5.2 Implement gather_context method with Redis caching
    - Check Redis cache first (key: chat:context:{workspace_id}:{page_context})
    - If cache miss, execute parallel queries for assessments, connections, migrations
    - Limit to 20 most recent items per category
    - Handle partial failures gracefully
    - Mask sensitive data (passwords, API keys)
    - Cache result in Redis with 5-minute TTL
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.9, 13.2, 13.3_
  
  - [ ] 5.3 Implement get_suggested_questions method
    - Check Redis cache first (key: chat:suggestions:{workspace_id}:{page_context})
    - Generate context-aware questions based on page_context
    - Detect errors in user's workspace data
    - Prioritize troubleshooting questions if errors exist
    - Return exactly 4 questions with category and priority
    - Cache result in Redis with 5-minute TTL
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  
  - [ ] 5.4 Implement private helper methods (_get_assessments_context, _get_connections_context, _get_migrations_context)
    - Filter by workspace_id
    - Order by created_at DESC
    - Limit to 20 items
    - Return summary objects
    - _Requirements: 3.2, 3.3, 3.4, 3.7_
  
  - [ ] 5.5 Implement _detect_errors method
    - Check for failed assessments
    - Check for failed connections
    - Check for failed migrations
    - Return tuple of (has_errors, error_summary)
    - _Requirements: 4.4_

- [ ] 6. Implement AttachmentService
  - [ ] 6.1 Create AttachmentService class
    - Create backend/services/attachment_service.py
    - Initialize with database session
    - _Requirements: 5.1_
  
  - [ ] 6.2 Implement validate_file method
    - Check file extension against allowed list ['.txt', '.log', '.json', '.png', '.jpg', '.jpeg']
    - Check file size (max 5MB, min 1 byte)
    - Return tuple of (is_valid, error_message)
    - _Requirements: 5.1, 5.2, 5.3, 5.4_
  
  - [ ] 6.3 Implement upload_attachment method
    - Validate file using validate_file
    - Determine storage type (text vs binary)
    - Extract text content for text files
    - Store binary content for images
    - Create attachment record with workspace_id and user_id
    - Return Attachment object
    - _Requirements: 5.5, 5.6, 5.7, 5.8, 5.11_
  
  - [ ] 6.4 Implement extract_content method
    - Read text from .txt, .log files
    - Parse and format JSON from .json files
    - Return extracted text
    - _Requirements: 5.8_
  
  - [ ] 6.5 Implement encode_image method
    - Read binary content from attachment
    - Encode as base64 string
    - Return base64 string for Claude AI vision
    - _Requirements: 5.9_
  
  - [ ] 6.6 Implement get_attachments_by_ids method
    - Filter by attachment IDs and workspace_id
    - Return list of Attachment objects
    - _Requirements: 5.10, 5.11_
  
  - [ ] 6.7 Implement delete_attachment method
    - Validate user owns attachment
    - Validate workspace access
    - Delete attachment record
    - Return success boolean
    - _Requirements: 5.12_

- [ ] 7. Implement ClaudeAIService
  - [ ] 7.1 Create ClaudeAIService class with Bedrock client
    - Create backend/services/claude_ai_service.py
    - Initialize with AWS Bedrock runtime client
    - Load configuration from environment variables
    - _Requirements: 2.1_
  
  - [ ] 7.2 Implement _build_system_prompt method
    - Include user context (assessments, connections, migrations)
    - Include page context
    - Include error information if present
    - Format as clear instructions for Claude
    - _Requirements: 2.2, 3.1, 3.5_
  
  - [ ] 7.3 Implement _format_conversation_history method
    - Limit to last 10 messages
    - Format as Claude API message format
    - Include role and content for each message
    - _Requirements: 2.3_
  
  - [ ] 7.4 Implement _include_attachments method
    - Format text attachments as text content
    - Format image attachments as base64 with media type
    - Return list of content blocks for Claude API
    - _Requirements: 5.10_
  
  - [ ] 7.5 Implement generate_response method with retry logic
    - Build system prompt with context
    - Format conversation history
    - Include attachments if present
    - Call Bedrock API with retry logic (max 3 retries, exponential backoff)
    - Implement 30-second timeout
    - Log API calls with token count and response time
    - Return AI response text
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [ ] 8. Checkpoint - Ensure all services are implemented and unit tested
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement chat API endpoints
  - [ ] 9.1 Create chat router with authentication middleware
    - Create backend/routers/chat_router.py
    - Set prefix to /api/chat
    - Add authentication dependency
    - Add workspace validation middleware
    - _Requirements: 13.1_
  
  - [ ] 9.2 Implement POST /api/chat/message endpoint
    - Accept ChatMessageRequest
    - Validate authentication and workspace access
    - Get or create conversation
    - Store user message
    - Gather context using ContextService
    - Get attachments if provided
    - Get conversation history (last 10 messages)
    - Generate AI response using ClaudeAIService
    - Store AI response
    - Return ChatMessageResponse
    - Implement rate limiting (30 messages per minute)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 14.1_
  
  - [ ] 9.3 Implement GET /api/chat/conversations endpoint
    - Accept pagination parameters (page, page_size)
    - Validate authentication and workspace access
    - Call ConversationService.get_conversations
    - Return paginated conversation list with metadata
    - _Requirements: 7.1, 7.2, 7.9_
  
  - [ ] 9.4 Implement GET /api/chat/conversations/{conversation_id}/messages endpoint
    - Accept conversation_id path parameter
    - Accept pagination parameters
    - Validate authentication and workspace access
    - Call ConversationService.get_conversation_messages
    - Return paginated messages with attachments
    - _Requirements: 7.3, 7.4, 7.5, 7.9_
  
  - [ ] 9.5 Implement POST /api/chat/conversations endpoint
    - Accept workspace_id in request body
    - Validate authentication and workspace access
    - Call ConversationService.create_conversation
    - Return created conversation
    - _Requirements: 7.6_
  
  - [ ] 9.6 Implement DELETE /api/chat/conversations/{conversation_id} endpoint
    - Accept conversation_id path parameter
    - Validate authentication and workspace access
    - Call ConversationService.delete_conversation
    - Return success response
    - _Requirements: 7.7, 7.8_
  
  - [ ] 9.7 Implement POST /api/chat/attachments endpoint
    - Accept multipart/form-data file upload
    - Validate authentication and workspace access
    - Call AttachmentService.upload_attachment
    - Return attachment metadata
    - Handle 413 Payload Too Large error
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  
  - [ ] 9.8 Implement GET /api/chat/suggested-questions endpoint
    - Accept page_context query parameter
    - Validate authentication and workspace access
    - Call ContextService.get_suggested_questions
    - Return list of suggested questions
    - _Requirements: 9.1, 9.2, 9.3_
  
  - [ ] 9.9 Implement POST /api/chat/search endpoint
    - Accept ConversationSearchRequest
    - Validate authentication and workspace access
    - Call ConversationService.search_conversations
    - Return search results with pagination
    - _Requirements: 11.1, 11.2, 11.3, 11.4_
  
  - [ ] 9.10 Implement GET /api/chat/conversations/{conversation_id}/export endpoint
    - Accept conversation_id path parameter
    - Accept format query parameter (json or markdown)
    - Validate authentication and workspace access
    - Call ConversationService.export_conversation
    - Set appropriate Content-Type and Content-Disposition headers
    - Return formatted export
    - _Requirements: 12.1, 12.2, 12.3_
  
  - [ ] 9.11 Implement GET /api/chat/health endpoint
    - Check database connection
    - Check Redis connection
    - Check Claude AI availability
    - Return health status
    - _Requirements: 10.1, 10.2_

- [ ] 10. Checkpoint - Ensure all API endpoints work correctly
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Update frontend ChatAgent component
  - [ ] 11.1 Add file upload UI to ChatAgent component
    - Add file input element with ref
    - Add file selection handler with validation
    - Display selected files with remove option
    - Show file size and type
    - _Requirements: 8.1, 8.2_
  
  - [ ] 11.2 Implement uploadAttachments function
    - Upload files to POST /api/chat/attachments
    - Handle upload progress
    - Return array of attachment IDs
    - Handle errors (file too large, invalid type)
    - _Requirements: 8.3, 8.4, 8.5_
  
  - [ ] 11.3 Update handleSendMessage to include attachments
    - Upload attachments before sending message
    - Include attachment_ids in message request
    - Clear attachments after successful send
    - _Requirements: 6.1, 8.1_
  
  - [ ] 11.4 Implement loadConversationHistory function
    - Call GET /api/chat/conversations on component mount
    - Load most recent conversation messages
    - Set currentConversationId state
    - _Requirements: 7.1, 7.3_
  
  - [ ] 11.5 Implement loadMessages function
    - Call GET /api/chat/conversations/{id}/messages
    - Transform API response to component message format
    - Update messages state
    - _Requirements: 7.3, 7.4, 7.5_
  
  - [ ] 11.6 Update loadSuggestedQuestions to use API
    - Call GET /api/chat/suggested-questions with page_context
    - Update suggested questions state
    - Fall back to static questions on error
    - _Requirements: 9.1, 9.2, 9.3_
  
  - [ ] 11.7 Implement search functionality
    - Add search input UI
    - Call POST /api/chat/search
    - Display search results
    - Allow navigation to conversation from results
    - _Requirements: 11.1, 11.2, 11.3_
  
  - [ ] 11.8 Add conversation export functionality
    - Add export button to conversation UI
    - Call GET /api/chat/conversations/{id}/export
    - Download file with appropriate name
    - Support JSON and Markdown formats
    - _Requirements: 12.1, 12.2, 12.3_
  
  - [ ] 11.9 Add error handling for rate limiting
    - Display user-friendly message when rate limited
    - Show countdown timer until rate limit resets
    - _Requirements: 14.1_

- [ ] 12. Update environment configuration
  - Add CHAT_RATE_LIMIT_PER_MINUTE=30 to .env
  - Add CHAT_MAX_ATTACHMENT_SIZE=5242880 to .env
  - Add CHAT_CONTEXT_CACHE_TTL=300 to .env
  - Add CHAT_SUGGESTED_QUESTIONS_CACHE_TTL=300 to .env
  - Add CHAT_MAX_CONTEXT_ITEMS=20 to .env
  - Add CHAT_MAX_CONVERSATION_HISTORY=10 to .env
  - Update .env.example with new variables
  - _Requirements: 3.7, 4.5, 5.4, 14.1_

- [ ] 13. Implement unit tests for services
  - [ ]* 13.1 Write unit tests for ConversationService
    - Test create_conversation with valid data
    - Test get_conversations with pagination
    - Test store_message with valid data
    - Test get_conversation_messages with pagination
    - Test delete_conversation with cascade
    - Test search_conversations with query
    - Test export_conversation in JSON and Markdown formats
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 7.1, 7.3, 11.1, 12.1_
  
  - [ ]* 13.2 Write unit tests for ContextService
    - Test gather_context with cache hit
    - Test gather_context with cache miss
    - Test gather_context with partial failures
    - Test get_suggested_questions for each page_context
    - Test sensitive data masking
    - _Requirements: 3.1, 3.6, 3.9, 4.1, 4.2, 13.2, 13.3_
  
  - [ ]* 13.3 Write unit tests for AttachmentService
    - Test validate_file with valid extensions
    - Test validate_file with invalid extensions
    - Test validate_file with valid sizes
    - Test validate_file with invalid sizes
    - Test upload_attachment for text files
    - Test upload_attachment for image files
    - Test extract_content for different file types
    - Test encode_image for images
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.7, 5.8, 5.9_
  
  - [ ]* 13.4 Write unit tests for ClaudeAIService
    - Test generate_response with context
    - Test generate_response with attachments
    - Test retry logic on transient failures
    - Test timeout handling
    - Test system prompt building
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [ ] 14. Implement integration tests for API endpoints
  - [ ]* 14.1 Write integration tests for POST /api/chat/message
    - Test with valid message and no conversation_id (creates new conversation)
    - Test with valid message and existing conversation_id
    - Test with attachments
    - Test with invalid workspace access (403)
    - Test with rate limiting (429)
    - Test with empty message (400)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 14.1_
  
  - [ ]* 14.2 Write integration tests for conversation endpoints
    - Test GET /api/chat/conversations with pagination
    - Test GET /api/chat/conversations/{id}/messages with pagination
    - Test POST /api/chat/conversations
    - Test DELETE /api/chat/conversations/{id}
    - Test workspace isolation (403 for wrong workspace)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9_
  
  - [ ]* 14.3 Write integration tests for attachment endpoints
    - Test POST /api/chat/attachments with valid text file
    - Test POST /api/chat/attachments with valid image file
    - Test POST /api/chat/attachments with file too large (413)
    - Test POST /api/chat/attachments with invalid extension (400)
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  
  - [ ]* 14.4 Write integration tests for suggested questions endpoint
    - Test GET /api/chat/suggested-questions for each page_context
    - Test response format (4 questions with category and priority)
    - Test caching behavior
    - _Requirements: 9.1, 9.2, 9.3_
  
  - [ ]* 14.5 Write integration tests for search endpoint
    - Test POST /api/chat/search with valid query
    - Test search results contain query text
    - Test pagination
    - Test workspace isolation
    - _Requirements: 11.1, 11.2, 11.3, 11.4_
  
  - [ ]* 14.6 Write integration tests for export endpoint
    - Test GET /api/chat/conversations/{id}/export with JSON format
    - Test GET /api/chat/conversations/{id}/export with Markdown format
    - Test Content-Type and Content-Disposition headers
    - Test workspace isolation
    - _Requirements: 12.1, 12.2, 12.3_

- [ ] 15. Implement property-based tests
  - [ ]* 15.1 Write property test for message storage completeness
    - **Property 1: Message Storage Completeness**
    - **Validates: Requirements 1.1**
    - Generate random workspace_id, user_id, message content
    - Store message and verify all fields match
    - _Requirements: 1.1_
  
  - [ ]* 15.2 Write property test for response linkage
    - **Property 2: Response Linkage**
    - **Validates: Requirements 1.2**
    - Generate user message, store AI response
    - Verify same conversation_id and role='assistant'
    - _Requirements: 1.2_
  
  - [ ]* 15.3 Write property test for message ordering
    - **Property 3: Message Ordering**
    - **Validates: Requirements 1.3**
    - Generate random number of messages
    - Verify retrieval order matches created_at ASC
    - _Requirements: 1.3_
  
  - [ ]* 15.4 Write property test for workspace isolation
    - **Property 4: Workspace Isolation**
    - **Validates: Requirements 1.4, 1.8, 3.8, 5.11, 13.1**
    - Generate two different workspace_ids
    - Create data in both workspaces
    - Verify queries never return cross-workspace data
    - _Requirements: 1.4, 1.8, 3.8, 5.11, 13.1_
  
  - [ ]* 15.5 Write property test for cascade deletion
    - **Property 5: Cascade Deletion**
    - **Validates: Requirements 1.5, 5.12**
    - Create conversation with messages and attachments
    - Delete conversation
    - Verify all associated data deleted
    - _Requirements: 1.5, 5.12_
  
  - [ ]* 15.6 Write property test for pagination bounds
    - **Property 6: Pagination Bounds**
    - **Validates: Requirements 1.7**
    - Generate random page_size values
    - Verify returned results <= min(page_size, 100)
    - _Requirements: 1.7_
  
  - [ ]* 15.7 Write property test for context data limiting
    - **Property 7: Context Data Limiting**
    - **Validates: Requirements 3.7**
    - Create more than 20 items per category
    - Verify context returns at most 20 items per category
    - _Requirements: 3.7_
  
  - [ ]* 15.8 Write property test for context resilience
    - **Property 8: Context Resilience**
    - **Validates: Requirements 3.9**
    - Simulate data source failures
    - Verify context still returns with available data
    - _Requirements: 3.9_
  
  - [ ]* 15.9 Write property test for suggested questions format
    - **Property 9: Suggested Questions Format**
    - **Validates: Requirements 4.1, 4.2, 4.3**
    - Test all page_context values
    - Verify exactly 4 questions with required fields
    - _Requirements: 4.1, 4.2, 4.3_
  
  - [ ]* 15.10 Write property test for file extension validation
    - **Property 10: File Extension Validation**
    - **Validates: Requirements 5.1, 5.3, 5.4**
    - Generate random file extensions
    - Verify acceptance matches allowed list
    - _Requirements: 5.1, 5.3, 5.4_
  
  - [ ]* 15.11 Write property test for file size validation
    - **Property 11: File Size Validation**
    - **Validates: Requirements 5.2, 5.4**
    - Generate random file sizes
    - Verify acceptance for 0 < size <= 5MB
    - _Requirements: 5.2, 5.4_
  
  - [ ]* 15.12 Write property test for attachment storage separation
    - **Property 12: Attachment Storage Separation**
    - **Validates: Requirements 5.7**
    - Upload text and binary files
    - Verify correct column usage (content_text vs content_binary)
    - _Requirements: 5.7_
  
  - [ ]* 15.13 Write property test for text content extraction
    - **Property 13: Text Content Extraction**
    - **Validates: Requirements 5.8**
    - Generate random text content
    - Upload as text file and verify extraction
    - _Requirements: 5.8_
  
  - [ ]* 15.14 Write property test for image base64 encoding
    - **Property 14: Image Base64 Encoding**
    - **Validates: Requirements 5.9**
    - Generate random binary content
    - Encode and decode, verify round-trip
    - _Requirements: 5.9_
  
  - [ ]* 15.15 Write property test for attachment ID uniqueness
    - **Property 15: Attachment ID Uniqueness**
    - **Validates: Requirements 5.6**
    - Upload multiple files
    - Verify all attachment_ids are unique
    - _Requirements: 5.6_
  
  - [ ]* 15.16 Write property test for conversation export round-trip
    - **Property 16: Conversation Export Round-Trip**
    - **Validates: Requirements 12.1, 12.2, 12.3**
    - Create conversation with messages
    - Export to JSON and parse
    - Verify all data matches
    - _Requirements: 12.1, 12.2, 12.3_
  
  - [ ]* 15.17 Write property test for sensitive data masking
    - **Property 17: Sensitive Data Masking**
    - **Validates: Requirements 13.2, 13.3**
    - Create context with sensitive fields
    - Verify masking replaces sensitive values
    - _Requirements: 13.2, 13.3_
  
  - [ ]* 15.18 Write property test for search result relevance
    - **Property 18: Search Result Relevance**
    - **Validates: Requirements 11.1, 11.2**
    - Generate random search queries
    - Verify all results contain query text
    - _Requirements: 11.1, 11.2_
  
  - [ ]* 15.19 Write property test for pagination consistency
    - **Property 19: Pagination Consistency**
    - **Validates: Requirements 1.7, 7.9**
    - Query page 1 and page 2
    - Verify no duplicates and consistent order
    - _Requirements: 1.7, 7.9_
  
  - [ ]* 15.20 Write property test for context JSON serialization
    - **Property 20: Context JSON Serialization**
    - **Validates: Requirements 3.6**
    - Create UserContext object
    - Serialize to JSON and deserialize
    - Verify equivalence
    - _Requirements: 3.6_

- [ ] 16. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 17. Create API documentation
  - Document all endpoints in docs/api/chat.md
  - Include request/response examples with sample payloads
  - Document error codes and responses
  - Document rate limiting behavior
  - _Requirements: All API endpoints_

- [ ] 18. Create database documentation
  - Document conversations table in docs/database/tables/conversations.md
  - Document messages table in docs/database/tables/messages.md
  - Document attachments table in docs/database/tables/attachments.md
  - Include schema, indexes, constraints, and example data
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 5.6, 5.7_

- [ ] 19. Final integration and testing
  - Run full test suite (unit + integration + property tests)
  - Test complete user flow: send message → upload file → search → export
  - Verify workspace isolation across all operations
  - Test Redis fallback when cache unavailable
  - Test rate limiting enforcement
  - Verify all 20 correctness properties pass
  - _Requirements: All requirements_

- [ ] 20. Final checkpoint - Production readiness verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- All database queries MUST filter by workspace_id for multi-tenant security
- Redis caching uses cache-aside pattern with database fallback
- File uploads limited to 5MB with specific allowed extensions
- Rate limiting enforced at 30 messages per minute per user
- Claude AI integration uses AWS Bedrock with retry logic and timeout
