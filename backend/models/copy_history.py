"""
Copy History Models

Pydantic models for Redshift COPY command tracking.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class CopyHistoryBase(BaseModel):
    """Base model for copy history"""
    migration_id: int = Field(..., description="Migration identifier")
    migration_name: Optional[str] = Field(None, description="Migration name")
    schema_name: Optional[str] = Field(None, description="Target schema name")
    table_name: str = Field(..., description="Target table name")
    copy_command: str = Field(..., description="Full COPY command text")
    source_uri: str = Field(..., description="S3 source URI")
    file_format: Optional[str] = Field(None, description="File format (CSV, JSON, PARQUET)")
    compression: Optional[str] = Field(None, description="Compression type (GZIP, BZIP2)")
    iam_role_arn: Optional[str] = Field(None, description="IAM role ARN for COPY")


class CopyHistoryCreate(CopyHistoryBase):
    """Model for creating copy history"""
    status: str = 'running'


class CopyHistory(CopyHistoryBase):
    """Model for copy history with database fields"""
    id: int
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    rows_loaded: Optional[int] = None
    bytes_loaded: Optional[int] = None
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class CopyHistoryResponse(BaseModel):
    """API response model for copy history"""
    id: int
    migration_id: int
    table_name: str
    status: str
    started_at: datetime
    duration_seconds: Optional[int] = None
    rows_loaded: Optional[int] = None
    bytes_loaded: Optional[int] = None


class CopyHistoryListResponse(BaseModel):
    """Response model for paginated copy history list"""
    records: list[CopyHistory]
    total: int
    page: int
    page_size: int
    summary: Dict[str, Any] = Field(..., description="Summary statistics")
