"""
Conversion Log Models

Pydantic models for conversion operation logs.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ConversionLogBase(BaseModel):
    """Base model for conversion log"""
    step_name: str = Field(..., description="Processing step name")
    message: Optional[str] = Field(None, description="Log message")
    log_level: str = Field('INFO', description="Log level (DEBUG, INFO, WARNING, ERROR)")
    duration_ms: Optional[int] = Field(None, description="Step duration in milliseconds")


class ConversionLogCreate(ConversionLogBase):
    """Model for creating a conversion log"""
    job_id: int
    workspace_id: int


class ConversionLog(ConversionLogBase):
    """Model for conversion log with database fields"""
    id: int
    job_id: int
    workspace_id: int
    timestamp: datetime
    
    class Config:
        from_attributes = True


class ConversionLogListResponse(BaseModel):
    """Response model for conversion logs"""
    logs: list[ConversionLog]
    total: int
