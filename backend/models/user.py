"""
User model
Pydantic models for user data
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class User(BaseModel):
    """User database model"""
    id: int
    username: str
    password_hash: str
    role: str
    organization_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    is_locked: bool = False
    failed_login_attempts: int = 0
    locked_until: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UserInfo(BaseModel):
    """User information (without sensitive data)"""
    id: int
    username: str
    role: str
    organization_id: Optional[int] = None
    last_login: Optional[datetime] = None


class UserCreate(BaseModel):
    """User creation request"""
    username: str
    password: str
    role: str = "user"
    organization_id: Optional[int] = None


class UserInDB(BaseModel):
    """User as stored in database"""
    id: int
    username: str
    password_hash: str
    role: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    is_locked: bool
    failed_login_attempts: int
    locked_until: Optional[datetime]
