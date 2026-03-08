"""
DataSync Agent Models

Pydantic models for AWS DataSync agent registry.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, validator


class DataSyncAgentBase(BaseModel):
    """Base model for DataSync agent"""
    vm_ip: str = Field(..., description="Agent VM IP address")
    aws_region: str = Field(..., description="AWS region")
    
    @validator('vm_ip')
    def validate_ip(cls, v):
        """Validate IP address format"""
        parts = v.split('.')
        if len(parts) != 4:
            raise ValueError("Invalid IP address format")
        for part in parts:
            if not part.isdigit() or not 0 <= int(part) <= 255:
                raise ValueError("Invalid IP address format")
        return v


class DataSyncAgentCreate(DataSyncAgentBase):
    """Model for creating DataSync agent"""
    workspace_id: int
    agent_arn: str = Field(..., description="DataSync agent ARN")


class DataSyncAgent(DataSyncAgentBase):
    """Model for DataSync agent with database fields"""
    id: int
    workspace_id: int
    agent_arn: str
    status: str = 'unknown'
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DataSyncAgentResponse(BaseModel):
    """API response model for DataSync agent"""
    id: int
    vm_ip: str
    agent_arn: str
    status: str
    last_used_at: Optional[datetime] = None
    created_at: datetime


class DataSyncAgentListResponse(BaseModel):
    """Response model for agent list"""
    agents: list[DataSyncAgent]
    total: int


class AgentHealthStatus(BaseModel):
    """Model for agent health check result"""
    agent_id: int
    status: str = Field(..., description="Agent status (online, offline, unknown)")
    last_checked: datetime
    error_message: Optional[str] = None
