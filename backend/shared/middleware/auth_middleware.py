"""
Authentication Middleware
FastAPI dependencies for JWT authentication and authorization
"""

from fastapi import Depends, HTTPException, status, Header
from typing import Optional, Callable
from sqlalchemy.orm import Session
import logging

from database import get_db
from services.jwt_service import JWTService, TokenPayload
from services.session_cache import session_cache
from services.rbac_service import RBACService
from services.audit_logger import AuditLogger
from repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class CurrentUser:
    """Current authenticated user information"""
    
    def __init__(
        self,
        user_id: int,
        username: str,
        role: str,
        organization_id: Optional[int] = None
    ):
        self.user_id = user_id
        self.username = username
        self.role = role
        self.organization_id = organization_id
    
    def __repr__(self):
        return f"CurrentUser(user_id={self.user_id}, username={self.username}, role={self.role})"


def extract_token_from_header(authorization: Optional[str] = Header(None)) -> str:
    """
    Extract JWT token from Authorization header
    
    Args:
        authorization: Authorization header value
        
    Returns:
        JWT token string
        
    Raises:
        HTTPException: If header is missing or invalid
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = authorization.replace("Bearer ", "").strip()
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is empty",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    return token


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> CurrentUser:
    """
    Get current authenticated user from JWT token
    
    This is a FastAPI dependency that:
    1. Extracts JWT token from Authorization header
    2. Validates token signature and expiration
    3. Checks if token is blacklisted
    4. Returns current user information
    
    Args:
        authorization: Authorization header with Bearer token
        db: Database session
        
    Returns:
        CurrentUser object with user information
        
    Raises:
        HTTPException: If authentication fails
        
    Example:
        @router.get("/protected")
        async def protected_route(current_user: CurrentUser = Depends(get_current_user)):
            return {"user": current_user.username}
    """
    try:
        logger.info(f"get_current_user called - Authorization header present: {authorization is not None}")
        
        # Extract token from header
        token = extract_token_from_header(authorization)
        logger.info(f"Token extracted successfully")
        
        # Check if token is blacklisted
        if session_cache.is_token_blacklisted(token):
            logger.warning("Attempt to use blacklisted token")
            try:
                audit_logger = AuditLogger(db)
                audit_logger.log_token_validation_failure(
                    token=token,
                    reason="Token is blacklisted",
                    ip_address="0.0.0.0"  # TODO: Extract from request
                )
            except Exception as e:
                logger.error(f"Failed to log blacklisted token attempt: {e}")
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        logger.info("Token not blacklisted, validating...")
        
        # Validate token
        payload = JWTService.validate_jwt_token(token)
        
        if not payload:
            logger.warning("Invalid or expired token")
            try:
                audit_logger = AuditLogger(db)
                audit_logger.log_token_validation_failure(
                    token=token,
                    reason="Invalid or expired token",
                    ip_address="0.0.0.0"  # TODO: Extract from request
                )
            except Exception as e:
                logger.error(f"Failed to log token validation failure: {e}")
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        logger.info(f"Token validated successfully for user_id: {payload.user_id}")
        
        # Verify user still exists in database
        user_repo = UserRepository(db)
        user = user_repo.get_user_by_id(payload.user_id)
        
        if not user:
            logger.warning(f"User not found for token: user_id={payload.user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        logger.info(f"User found: {user['username']}")
        
        # Check if user account is active
        if not user.get("is_active", True):
            logger.warning(f"Inactive user attempted access: {user['username']}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        logger.info(f"Returning CurrentUser object for {user['username']}")
        
        # Return current user
        return CurrentUser(
            user_id=user["id"],
            username=user["username"],
            role=user["role"],
            organization_id=user.get("organization_id")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in authentication: {str(e)}")
        logger.error(f"Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error"
        )


def require_role(required_role: str) -> Callable:
    """
    Create a dependency that requires a specific role
    
    This is a dependency factory that creates a FastAPI dependency
    requiring the user to have a specific role or higher.
    
    Args:
        required_role: Required role (member, admin, owner)
        
    Returns:
        FastAPI dependency function
        
    Example:
        @router.post("/admin-only")
        async def admin_route(current_user: CurrentUser = Depends(require_role("admin"))):
            return {"message": "Admin access granted"}
    """
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        """Check if user has required role"""
        
        if not RBACService.has_role_level(current_user.role, required_role):
            logger.warning(
                f"Permission denied: user {current_user.username} "
                f"(role: {current_user.role}) attempted to access "
                f"resource requiring role: {required_role}"
            )
            
            # Log permission denied
            AuditLogger.log_permission_denied(
                user_id=current_user.user_id,
                username=current_user.username,
                required_role=required_role,
                user_role=current_user.role,
                resource="endpoint"
            )
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )
        
        return current_user
    
    return role_checker


def require_permission(required_permission: str) -> Callable:
    """
    Create a dependency that requires a specific permission
    
    This is a dependency factory that creates a FastAPI dependency
    requiring the user to have a specific permission.
    
    Args:
        required_permission: Required permission (e.g., "project:write")
        
    Returns:
        FastAPI dependency function
        
    Example:
        @router.post("/projects")
        async def create_project(
            current_user: CurrentUser = Depends(require_permission("project:write"))
        ):
            return {"message": "Project created"}
    """
    async def permission_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        """Check if user has required permission"""
        
        if not RBACService.check_permission(current_user.role, required_permission):
            logger.warning(
                f"Permission denied: user {current_user.username} "
                f"(role: {current_user.role}) attempted to access "
                f"resource requiring permission: {required_permission}"
            )
            
            # Log permission denied
            AuditLogger.log_permission_denied(
                user_id=current_user.user_id,
                username=current_user.username,
                required_permission=required_permission,
                user_role=current_user.role,
                resource="endpoint"
            )
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required permission: {required_permission}"
            )
        
        return current_user
    
    return permission_checker


def require_admin() -> Callable:
    """
    Create a dependency that requires admin access
    
    Convenience function for requiring admin or owner role.
    
    Returns:
        FastAPI dependency function
        
    Example:
        @router.get("/admin/users")
        async def list_users(current_user: CurrentUser = Depends(require_admin())):
            return {"users": [...]}
    """
    async def admin_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        """Check if user has admin access"""
        
        if not RBACService.has_admin_access(current_user.role):
            logger.warning(
                f"Admin access denied: user {current_user.username} "
                f"(role: {current_user.role})"
            )
            
            # Log permission denied
            AuditLogger.log_permission_denied(
                user_id=current_user.user_id,
                username=current_user.username,
                required_role="admin",
                user_role=current_user.role,
                resource="admin_endpoint"
            )
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        return current_user
    
    return admin_checker


# Optional: Get current user without raising exception
async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[CurrentUser]:
    """
    Get current user if authenticated, None otherwise
    
    This dependency does not raise an exception if authentication fails.
    Useful for endpoints that have optional authentication.
    
    Args:
        authorization: Authorization header with Bearer token
        db: Database session
        
    Returns:
        CurrentUser object if authenticated, None otherwise
        
    Example:
        @router.get("/public-or-private")
        async def mixed_route(
            current_user: Optional[CurrentUser] = Depends(get_current_user_optional)
        ):
            if current_user:
                return {"message": f"Hello {current_user.username}"}
            return {"message": "Hello guest"}
    """
    try:
        return await get_current_user(authorization, db)
    except HTTPException:
        return None
    except Exception as e:
        logger.error(f"Error in optional authentication: {str(e)}")
        return None
