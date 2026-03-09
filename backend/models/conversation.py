"""
Conversation models for ChatAgent feature.

This module defines Pydantic models for chat conversations including:
- ConversationBase: Base model with common fields
- ConversationCreate: Model for creating new conversations
- Conversation: Database model with all fields
- ConversationInfo: API response model with summary information
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ConversationBase(BaseModel):
    """Base conversation model with common fields."""
    
    user_id: int = Field(..., description="ID of the user who owns this conversation")
    workspace_id: int = Field(..., description="ID of the workspace this conversation belongs to")


class ConversationCreate(ConversationBase):
    """Model for creating a new conversation."""
    pass


class Conversation(ConversationBase):
    """
    Complete conversation model matching database schema.
    
    Attributes:
        id: Unique conversation identifier
        user_id: Owner user ID
        workspace_id: Workspace ID for multi-tenant isolation
        created_at: Timestamp when conversation was created
        updated_at: Timestamp when conversation was last updated
        is_active: Whether the conversation is active
    """
    
    id: int = Field(..., description="Unique conversation identifier")
    created_at: datetime = Field(..., description="Conversation creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    is_active: bool = Field(default=True, description="Whether conversation is active")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 123,
                "user_id": 1,
                "workspace_id": 1,
                "created_at": "2026-03-02T10:00:00Z",
                "updated_at": "2026-03-02T10:30:00Z",
                "is_active": True
            }
        }


class ConversationInfo(BaseModel):
    """
    Conversation summary information for API responses.
    
    This model provides a lightweight view of conversations including
    message count and preview for list endpoints.
    """
    
    id: int = Field(..., description="Unique conversation identifier")
    created_at: datetime = Field(..., description="Conversation creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    message_count: int = Field(..., description="Total number of messages in conversation")
    last_message_preview: Optional[str] = Field(None, description="Preview of last message (first 100 chars)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 123,
                "created_at": "2026-03-02T10:00:00Z",
                "updated_at": "2026-03-02T10:30:00Z",
                "message_count": 15,
                "last_message_preview": "To create a new assessment, navigate to the Assessments page and click..."
            }
        }
