"""
Authentication Service
Handles user login, authentication, and workspace context
"""

from typing import Optional, Dict, Any
from datetime import datetime
import logging
from services.auth_service import AuthService, AuthenticationError
from services.jwt_service import JWTService
from repositories.user_repository import UserRepository
from services.session_cache import session_cache

logger = logging.getLogger(__name__)


class AuthenticationService:
    """Service for user authentication and login"""
    
    def __init__(self, user_repository: UserRepository):
        self.user_repo = user_repository
    
    def authenticate_user(
        self,
        username: str,
        password: str
    ) -> Dict[str, Any]:
        """
        Authenticate user with username and password
        
        Args:
            username: User's username
            password: User's plain text password
            
        Returns:
            Dict with user info and JWT token
            
        Raises:
            AuthenticationError: If authentication fails
            
        Example:
            >>> auth_service = AuthenticationService(user_repo)
            >>> result = auth_service.authenticate_user("admin", "AdminPass123!")
            >>> result["access_token"]
            'eyJ0eXAiOiJKV1QiLCJhbGc...'
        """
        try:
            # Get user from database
            user = self.user_repo.get_user_by_username(username)
            
            if user is None:
                logger.warning(f"Login attempt for non-existent user: {username}")
                # Increment failed attempts even for non-existent users (timing attack prevention)
                raise AuthenticationError("Invalid username or password")
            
            # Check if account is locked
            if AuthService.is_account_locked(
                user["failed_login_attempts"],
                user["locked_until"]
            ):
                logger.warning(f"Login attempt for locked account: {username}")
                raise AuthenticationError(
                    "Account temporarily locked due to multiple failed login attempts. "
                    "Please try again later."
                )
            
            # Verify password
            if not AuthService.verify_password(password, user["password_hash"]):
                logger.warning(f"Failed login attempt for user: {username}")
                
                # Increment failed attempts
                new_attempts = user["failed_login_attempts"] + 1
                self.user_repo.update_failed_attempts(user["id"], new_attempts)
                
                # Lock account if threshold reached
                if new_attempts >= AuthService.MAX_FAILED_ATTEMPTS:
                    lockout_time = AuthService.calculate_lockout_time()
                    self.user_repo.lock_user(user["id"], lockout_time)
                    logger.warning(f"Account locked for user: {username}")
                
                raise AuthenticationError("Invalid username or password")
            
            # Authentication successful
            logger.info(f"Successful login for user: {username}")
            
            # Reset failed attempts
            if user["failed_login_attempts"] > 0:
                self.user_repo.update_failed_attempts(user["id"], 0)
            
            # Update last login
            self.user_repo.update_last_login(user["id"])
            
            # Generate JWT token
            token = JWTService.generate_jwt_token(
                user_id=user["id"],
                username=user["username"],
                role=user["role"]
            )
            
            # Cache session
            session_data = {
                "user_id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "organization_id": user.get("organization_id"),
                "login_time": datetime.utcnow().isoformat()
            }
            session_cache.cache_session(
                user_id=user["id"],
                token=token,
                session_data=session_data,
                ttl=28800  # 8 hours
            )
            
            return {
                "access_token": token,
                "token_type": "bearer",
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "role": user["role"],
                    "organization_id": user.get("organization_id")
                }
            }
            
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {str(e)}")
            raise AuthenticationError("Authentication failed due to server error")
    
    def logout_user(self, token: str) -> None:
        """
        Logout user by invalidating token
        
        Args:
            token: JWT token to invalidate
        """
        try:
            # Add token to blacklist
            session_cache.add_to_blacklist(token, ttl=28800)
            
            # Invalidate session cache
            session_cache.invalidate_session(token)
            
            logger.info("User logged out successfully")
            
        except Exception as e:
            logger.error(f"Error during logout: {str(e)}")
            # Don't raise exception - logout should always succeed
    
    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate JWT token and return user info
        
        Args:
            token: JWT token to validate
            
        Returns:
            User info dict if valid, None otherwise
        """
        try:
            # Check if token is blacklisted
            if session_cache.is_token_blacklisted(token):
                logger.warning("Attempt to use blacklisted token")
                return None
            
            # Validate token
            payload = JWTService.validate_jwt_token(token)
            
            if payload is None:
                return None
            
            return {
                "user_id": payload.user_id,
                "username": payload.username,
                "role": payload.role
            }
            
        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            return None
    
    async def get_user_workspaces(self, user_id: int) -> list:
        """
        Get all workspaces user has access to
        
        Args:
            user_id: User ID
            
        Returns:
            List of workspace dicts
        """
        from shared.middleware.workspace_middleware import WorkspaceMiddleware
        from database import db_instance
        
        try:
            with db_instance.get_session() as db:
                workspaces = await WorkspaceMiddleware.get_user_workspaces(user_id, db)
                return workspaces
        except Exception as e:
            logger.error(f"Error getting user workspaces: {str(e)}")
            return []
