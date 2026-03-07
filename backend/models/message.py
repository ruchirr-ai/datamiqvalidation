"""
Message models for ChatAgent feature.

This module defines Pydantic models for chat messages including:
- MessageBase: Base model with common fields
- MessageCreate: Model for creating new messages
- Message: Database model with all fields
- MessageWithAttachments: Message model including attachment information
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, List, Dict, Any


class MessageBase(BaseModel):
    """Base message model with common fields."""
    
    conversation_id: int = Field(..., description="ID of the conversation this message belongs to")
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content text")
    page_context: Optional[str] = Field(None, description="Page context when message was sent")
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate that role is either 'user' or 'assistant'."""
        if v not in ('user', 'assistant'):
            raise ValueError("role must be either 'user' or 'assistant'")
        return v


class MessageCreate(MessageBase):
    """
    Model for creating a new message.
    
    Includes optional metadata field for storing additional information
    about the message (e.g., client info, context data).
    """
    
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional message metadata")


class Message(MessageBase):
    """
    Complete message model matching database schema.
    
    Attributes:
        id: Unique message identifier
        conversation_id: Parent conversation ID
        role: Message role ('user' or 'assistant')
        content: Message text content
        page_context: Page where message was sent from
        metadata: Additional metadata as JSONB
        created_at: Message creation timestamp
    """
    
    id: int = Field(..., description="Unique message identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional message metadata")
    created_at: datetime = Field(..., description="Message creation timestamp")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1001,
                "conversation_id": 123,
                "role": "user",
                "content": "How do I create a new assessment?",
                "page_context": "assessments",
                "metadata": {},
                "created_at": "2026-03-02T10:30:00Z"
            }
        }


class MessageWithAttachments(Message):
    """
    Message model including attachment information.
    
    This model extends Message to include a list of attachments
    for API responses that need to show file information.
    """
    
    attachments: List['AttachmentInfo'] = Field(default_factory=list, description="List of file attachments")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1001,
                "conversation_id": 123,
                "role": "user",
                "content": "Can you analyze this error log?",
                "page_context": "assessments",
                "metadata": {},
                "created_at": "2026-03-02T10:30:00Z",
                "attachments": [
                    {
                        "id": 456,
                        "filename": "error.log",
                        "file_size": 2048,
                        "mime_type": "text/plain",
                        "created_at": "2026-03-02T10:29:00Z"
                    }
                ]
            }
        }


# Forward reference for AttachmentInfo (will be defined in attachment.py)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .attachment import AttachmentInfo
