"""
Workspace and Organization models
Pydantic models for multi-tenant data
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List


class Organization(BaseModel):
    """Organization model"""
    id: int
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    subscription_tier: str = "free"
    max_workspaces: int = 5
    
    class Config:
        from_attributes = True


class OrganizationCreate(BaseModel):
    """Organization creation request"""
    name: str
    slug: str
    subscription_tier: str = "free"
    max_workspaces: int = 5


class Workspace(BaseModel):
    """Workspace model"""
    id: int
    organization_id: int
    name: str
    slug: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    
    class Config:
        from_attributes = True


class WorkspaceCreate(BaseModel):
    """Workspace creation request"""
    organization_id: int
    name: str
    slug: str
    description: Optional[str] = None


class WorkspaceInfo(BaseModel):
    """Workspace information"""
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    organization_id: int


class UserWorkspace(BaseModel):
    """User-Workspace mapping"""
    id: int
    user_id: int
    workspace_id: int
    role: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserWorkspaceCreate(BaseModel):
    """User-Workspace mapping creation"""
    user_id: int
    workspace_id: int
    role: str = "member"


class WorkspaceContext(BaseModel):
    """Workspace context for requests"""
    workspace_id: int
    workspace_slug: str
    organization_id: int
    user_id: int
    user_role: str
