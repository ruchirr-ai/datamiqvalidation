"""
Task History Models

Pydantic models for AWS DataSync task tracking.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class TaskHistoryBase(BaseModel):
    """Base model for task history"""
    migration_id: int = Field(..., description="Migration identifier")
    migration_name: Optional[str] = Field(None, description="Migration name")
    task_arn: str = Field(..., description="DataSync task ARN")
    agent_arn: str = Field(..., description="DataSync agent ARN")
    agent_ip: str = Field(..., description="Agent VM IP address")
    source_uri: str = Field(..., description="GCS source URI")
    dest_uri: str = Field(..., description="S3 destination URI")
    task_name: Optional[str] = Field(None, description="Task name")
    task_type: Optional[str] = Field(None, description="Task type")
    table_name: Optional[str] = Field(None, description="Table name")
    execution_arn: Optional[str] = Field(None, description="Execution ARN")
    source_location_arn: Optional[str] = Field(None, description="Source location ARN")
    dest_location_arn: Optional[str] = Field(None, description="Destination location ARN")


class TaskHistoryCreate(TaskHistoryBase):
    """Model for creating task history"""
    status: str = 'running'


class TaskHistory(TaskHistoryBase):
    """Model for task history with database fields"""
    id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    files_transferred: Optional[int] = None
    bytes_transferred: Optional[int] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    raw_result: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class TaskHistoryResponse(BaseModel):
    """API response model for task history"""
    id: int
    migration_id: int
    task_name: Optional[str] = None
    agent_ip: str
    status: str
    started_at: datetime
    duration_seconds: Optional[int] = None
    files_transferred: Optional[int] = None
    bytes_transferred: Optional[int] = None


class TaskHistoryListResponse(BaseModel):
    """Response model for paginated task history list"""
    records: list[TaskHistory]
    total: int
    page: int
    page_size: int
    summary: Dict[str, Any] = Field(..., description="Summary statistics")
