"""
Authentication API Router
FastAPI endpoints for authentication operations
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import logging

from database import get_db
from services.authentication_service import AuthenticationService
from services.auth_service import AuthenticationError
from repositories.user_repository import UserRepository
from services.jwt_service import JWTService
from services.audit_logger import AuditLogger

logger = logging.getLogger(__name__)
security = HTTPBearer()


# Request/Response Models
class LoginRequest(BaseModel):
    """Login request payload"""
    username: str = Field(..., min_length=1, max_length=255, description="Username")
    password: str = Field(..., min_length=1, description="Password")
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "admin",
                "password": "AdminPass123!"
            }
        }


class LoginResponse(BaseModel):
    """Login response payload"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    user: Dict[str, Any] = Field(..., description="User information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "token_type": "bearer",
                "user": {
                    "id": 1,
                    "username": "admin",
                    "role": "admin",
                    "organization_id": 1
                }
            }
        }


class LogoutResponse(BaseModel):
    """Logout response payload"""
    message: str = Field(..., description="Logout status message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Successfully logged out"
            }
        }


class UserInfoResponse(BaseModel):
    """User information response"""
    user: Dict[str, Any] = Field(..., description="User information")
    workspaces: List[Dict[str, Any]] = Field(..., description="User's workspaces")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user": {
                    "id": 1,
                    "username": "admin",
                    "role": "admin",
                    "organization_id": 1
                },
                "workspaces": [
                    {
                        "id": 1,
                        "name": "dev-workspace",
                        "slug": "dev-workspace",
                        "role": "owner"
                    }
                ]
            }
        }


class RefreshTokenResponse(BaseModel):
    """Token refresh response"""
    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "token_type": "bearer"
            }
        }


class ErrorResponse(BaseModel):
    """Error response payload"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Invalid credentials",
                "detail": "Username or password is incorrect"
            }
        }


# Create router
router = APIRouter(
    prefix="/api/auth",
    tags=["authentication"]
)


# Helper function to extract token from header
def get_token_from_header(
    authorization: Optional[str] = Header(None)
) -> str:
    """Extract JWT token from Authorization header"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )
    
    return authorization.replace("Bearer ", "")


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Login successful"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        423: {"model": ErrorResponse, "description": "Account locked"}
    }
)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token
    
    - **username**: User's username
    - **password**: User's password
    
    Returns JWT access token and user information on success.
    """
    try:
        # Validate request
        if not request.username or not request.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username and password are required"
            )
        
        # Create authentication service
        user_repo = UserRepository(db)
        auth_service = AuthenticationService(user_repo)
        
        # Authenticate user
        result = auth_service.authenticate_user(
            username=request.username,
            password=request.password
        )
        
        # Log successful login
        audit_logger = AuditLogger(db)
        audit_logger.log_login_attempt(
            user_id=result["user"]["id"],
            username=result["user"]["username"],
            ip_address="0.0.0.0",  # TODO: Extract from request
            success=True
        )
        
        return LoginResponse(**result)
        
    except AuthenticationError as e:
        # Log failed login attempt
        audit_logger = AuditLogger(db)
        audit_logger.log_login_attempt(
            username=request.username,
            ip_address="0.0.0.0",  # TODO: Extract from request
            success=False,
            user_id=None,
            details={"failure_reason": str(e)}
        )
        
        # Determine status code based on error message
        if "locked" in str(e).lower():
            status_code = status.HTTP_423_LOCKED
        else:
            status_code = status.HTTP_401_UNAUTHORIZED
        
        raise HTTPException(
            status_code=status_code,
            detail=str(e)
        )
    
    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Logout successful"},
        401: {"model": ErrorResponse, "description": "Unauthorized"}
    }
)
async def logout(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Logout user by invalidating JWT token
    
    Requires valid JWT token in Authorization header.
    """
    try:
        # Extract token
        token = get_token_from_header(authorization)
        
        # Validate token first
        payload = JWTService.validate_jwt_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Create authentication service
        user_repo = UserRepository(db)
        auth_service = AuthenticationService(user_repo)
        
        # Logout user
        auth_service.logout_user(token)
        
        # Log logout
        audit_logger = AuditLogger(db)
        audit_logger.log_logout(
            user_id=payload.user_id,
            username=payload.username
        )
        
        return LogoutResponse(message="Successfully logged out")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during logout: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get(
    "/me",
    response_model=UserInfoResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "User information retrieved"},
        401: {"model": ErrorResponse, "description": "Unauthorized"}
    }
)
async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user information
    
    Requires valid JWT token in Authorization header.
    Returns user information and accessible workspaces.
    """
    try:
        # Extract token
        token = get_token_from_header(authorization)
        
        # Validate token
        payload = JWTService.validate_jwt_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Get user information
        user_repo = UserRepository(db)
        user = user_repo.get_user_by_id(payload.user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get user workspaces
        auth_service = AuthenticationService(user_repo)
        workspaces = await auth_service.get_user_workspaces(payload.user_id)
        
        return UserInfoResponse(
            user={
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "organization_id": user.get("organization_id")
            },
            workspaces=workspaces
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting user info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Token refreshed successfully"},
        401: {"model": ErrorResponse, "description": "Unauthorized"}
    }
)
async def refresh_token(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Refresh JWT token
    
    Requires valid JWT token in Authorization header.
    Returns a new JWT token with extended expiration.
    """
    try:
        # Extract token
        token = get_token_from_header(authorization)
        
        # Validate current token
        payload = JWTService.validate_jwt_token(token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Verify user still exists
        user_repo = UserRepository(db)
        user = user_repo.get_user_by_id(payload.user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Generate new token
        new_token = JWTService.generate_jwt_token(
            user_id=user["id"],
            username=user["username"],
            role=user["role"]
        )
        
        # Invalidate old token
        auth_service = AuthenticationService(user_repo)
        auth_service.logout_user(token)
        
        logger.info(f"Token refreshed for user: {user['username']}")
        
        return RefreshTokenResponse(
            access_token=new_token,
            token_type="bearer"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error refreshing token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get(
    "/health",
    status_code=status.HTTP_200_OK
)
async def health_check():
    """
    Health check endpoint
    
    Returns service health status.
    """
    return {
        "status": "healthy",
        "service": "auth-service"
    }
