"""
Conversion Job Models

Pydantic models for SQL code conversion jobs.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator


class ConversionJobBase(BaseModel):
    """Base model for conversion job"""
    source_code: str = Field(..., description="Source SQL code to convert")
    source_dialect: str = Field(..., description="Source database dialect")
    target_dialect: str = Field(..., description="Target database dialect")
    asset_type: str = Field(..., description="Type of asset (view, stored_procedure, function, trigger, table_ddl)")
    asset_name: Optional[str] = Field(None, description="Name of the asset")
    bedrock_model: Optional[str] = Field(None, description="AWS Bedrock model ID")
    use_sqlglot: bool = Field(True, description="Whether to attempt SQLGlot first")
    prompt_template_path: Optional[str] = Field(None, description="Custom prompt template path")
    
    @validator('asset_type')
    def validate_asset_type(cls, v):
        """Validate asset type"""
        valid_types = ['view', 'stored_procedure', 'function', 'trigger', 'table_ddl', 'other']
        if v not in valid_types:
            raise ValueError(f"asset_type must be one of {valid_types}")
        return v
    
    @validator('source_dialect', 'target_dialect')
    def validate_dialect(cls, v):
        """Validate dialect"""
        valid_dialects = ['bigquery', 'redshift', 'postgres', 'mysql', 'snowflake', 'oracle', 'mssql']
        if v.lower() not in valid_dialects:
            raise ValueError(f"dialect must be one of {valid_dialects}")
        return v.lower()


class ConversionJobCreate(ConversionJobBase):
    """Model for creating a conversion job"""
    workspace_id: int
    batch_id: Optional[int] = None
    created_by: Optional[int] = None


class ConversionJob(ConversionJobBase):
    """Model for conversion job with database fields"""
    id: int
    workspace_id: int
    batch_id: Optional[int] = None
    target_code: Optional[str] = None
    aws_region: Optional[str] = None
    sqlglot_success: Optional[bool] = None
    status: str = 'pending'
    error_message: Optional[str] = None
    retry_count: int = 0
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ConversionJobResponse(BaseModel):
    """API response model for conversion job"""
    job_id: int
    status: str
    target_code: Optional[str] = None
    sqlglot_success: Optional[bool] = None
    error_message: Optional[str] = None
    created_at: datetime


class ConversionJobDetailResponse(ConversionJob):
    """Detailed API response for conversion job"""
    pass


class StandaloneConversionRequest(ConversionJobBase):
    """Request model for standalone conversion"""
    pass
