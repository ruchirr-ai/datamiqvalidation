"""
Conversion Batch Models

Pydantic models for batch SQL code conversions.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ConversionBatchBase(BaseModel):
    """Base model for conversion batch"""
    source_connection_id: int = Field(..., description="Source database connection ID")
    target_connection_id: int = Field(..., description="Target database connection ID")
    bedrock_model: Optional[str] = Field(None, description="AWS Bedrock model ID")
    use_sqlglot: bool = Field(True, description="Whether to attempt SQLGlot first")
    max_retries: int = Field(3, description="Maximum retry attempts per job")
    prompt_template_path: Optional[str] = Field(None, description="Custom prompt template path")


class ConversionBatchCreate(ConversionBatchBase):
    """Model for creating a conversion batch"""
    workspace_id: int
    migration_project_id: Optional[int] = None
    asset_list: List[Dict[str, Any]] = Field(..., description="List of assets to convert")
    created_by: Optional[int] = None


class ConversionBatch(ConversionBatchBase):
    """Model for conversion batch with database fields"""
    id: int
    workspace_id: int
    migration_project_id: Optional[int] = None
    aws_region: Optional[str] = None
    status: str = 'pending'
    total_assets: int = 0
    completed_assets: int = 0
    failed_assets: int = 0
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ConversionBatchResponse(BaseModel):
    """API response model for conversion batch"""
    batch_id: int
    status: str
    total_assets: int
    completed_assets: int
    failed_assets: int
    created_at: datetime


class ConversionBatchDetailResponse(ConversionBatch):
    """Detailed API response for conversion batch"""
    pass


class BatchConversionRequest(BaseModel):
    """Request model for batch conversion"""
    source_connection_id: int
    target_connection_id: int
    asset_list: List[Dict[str, Any]] = Field(..., description="List of assets with asset_type, asset_name, source_code")
    bedrock_model: Optional[str] = None
    use_sqlglot: bool = True
    max_retries: int = 3
    prompt_template_path: Optional[str] = None


class ConversionJobListResponse(BaseModel):
    """Response model for paginated job list"""
    jobs: List[Any]  # Will be ConversionJob
    total: int
    page: int
    page_size: int
