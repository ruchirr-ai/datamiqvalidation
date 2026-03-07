"""
Attachment models for ChatAgent feature.

This module defines Pydantic models for file attachments including:
- AttachmentBase: Base model with common fields
- AttachmentCreate: Model for creating new attachments
- Attachment: Database model with all fields
- AttachmentInfo: API response model with summary information
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional


class AttachmentBase(BaseModel):
    """Base attachment model with common fields."""
    
    message_id: int = Field(..., description="ID of the message this attachment belongs to")
    workspace_id: int = Field(..., description="ID of the workspace for multi-tenant isolation")
    user_id: int = Field(..., description="ID of the user who uploaded this attachment")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type of the file")
    
    @field_validator('file_size')
    @classmethod
    def validate_file_size(cls, v: int) -> int:
        """Validate file size is between 1 byte and 5MB."""
        if v <= 0:
            raise ValueError("file_size must be greater than 0")
        if v > 5242880:  # 5MB in bytes
            raise ValueError("file_size must not exceed 5MB (5242880 bytes)")
        return v
    
    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """Validate filename is not empty."""
        if not v or not v.strip():
            raise ValueError("filename cannot be empty")
        return v


class AttachmentCreate(AttachmentBase):
    """
    Model for creating a new attachment.
    
    Includes content fields for storing either text or binary data.
    Only one of content_text or content_binary should be populated.
    """
    
    content_text: Optional[str] = Field(None, description="Text content for .txt, .log, .json files")
    content_binary: Optional[bytes] = Field(None, description="Binary content for image files")
    
    @field_validator('content_binary')
    @classmethod
    def validate_content_exclusivity(cls, v: Optional[bytes], info) -> Optional[bytes]:
        """Ensure only one of content_text or content_binary is set."""
        content_text = info.data.get('content_text')
        if content_text is not None and v is not None:
            raise ValueError("Only one of content_text or content_binary can be set")
        if content_text is None and v is None:
            raise ValueError("Either content_text or content_binary must be set")
        return v


class Attachment(AttachmentBase):
    """
    Complete attachment model matching database schema.
    
    Attributes:
        id: Unique attachment identifier
        message_id: Parent message ID
        workspace_id: Workspace ID for multi-tenant isolation
        user_id: Owner user ID
        filename: Original filename
        file_size: File size in bytes (1 to 5242880)
        mime_type: MIME type
        created_at: Upload timestamp
    """
    
    id: int = Field(..., description="Unique attachment identifier")
    created_at: datetime = Field(..., description="Attachment upload timestamp")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 456,
                "message_id": 1001,
                "workspace_id": 1,
                "user_id": 1,
                "filename": "error.log",
                "file_size": 2048,
                "mime_type": "text/plain",
                "created_at": "2026-03-02T10:29:00Z"
            }
        }


class AttachmentInfo(BaseModel):
    """
    Attachment summary information for API responses.
    
    This model provides a lightweight view of attachments without
    including the actual file content.
    """
    
    id: int = Field(..., description="Unique attachment identifier")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type of the file")
    created_at: datetime = Field(..., description="Attachment upload timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": 456,
                "filename": "error.log",
                "file_size": 2048,
                "mime_type": "text/plain",
                "created_at": "2026-03-02T10:29:00Z"
            }
        }
