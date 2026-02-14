"""
Audit Logger Service
Logs authentication and security events for compliance and monitoring
"""

from typing import Optional, Dict, Any
from datetime import datetime
import logging
import json
from sqlalchemy import text

logger = logging.getLogger(__name__)


class AuditLogger:
    """Service for audit logging"""
    
    def __init__(self, db):
        self.db = db
    
    def log_login_attempt(
        self,
        username: str,
        ip_address: str,
        success: bool,
        user_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log user login attempt
        
        Args:
            username: Username attempting login
            ip_address: IP address of request
            success: Whether login was successful
            user_id: User ID if login successful
            details: Additional details (e.g., failure reason)
        """
        try:
            self._create_audit_log(
                event_type="login_attempt",
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                success=success,
                details=details or {}
            )
            logger.info(f"Logged login attempt for {username}: {'success' if success else 'failure'}")
        except Exception as e:
            logger.error(f"Failed to log login attempt: {str(e)}")
    
    def log_logout(
        self,
        user_id: int,
        username: str,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Log user logout
        
        Args:
            user_id: User ID
            username: Username
            ip_address: IP address of request
        """
        try:
            self._create_audit_log(
                event_type="logout",
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                success=True,
                details={}
            )
            logger.info(f"Logged logout for {username}")
        except Exception as e:
            logger.error(f"Failed to log logout: {str(e)}")
    
    def log_token_validation_failure(
        self,
        token: str,
        reason: str,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Log JWT token validation failure
        
        Args:
            token: Token that failed validation (truncated for security)
            reason: Reason for failure
            ip_address: IP address of request
        """
        try:
            # Truncate token for security
            token_preview = token[:20] + "..." if len(token) > 20 else token
            
            self._create_audit_log(
                event_type="token_validation_failure",
                user_id=None,
                username=None,
                ip_address=ip_address,
                success=False,
                details={
                    "token_preview": token_preview,
                    "reason": reason
                }
            )
            logger.warning(f"Logged token validation failure: {reason}")
        except Exception as e:
            logger.error(f"Failed to log token validation failure: {str(e)}")
    
    def log_account_locked(
        self,
        user_id: int,
        username: str,
        ip_address: Optional[str] = None,
        failed_attempts: int = 0
    ) -> None:
        """
        Log account lock event
        
        Args:
            user_id: User ID
            username: Username
            ip_address: IP address of request
            failed_attempts: Number of failed attempts
        """
        try:
            self._create_audit_log(
                event_type="account_locked",
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                success=True,
                details={
                    "failed_attempts": failed_attempts,
                    "reason": "Multiple failed login attempts"
                }
            )
            logger.warning(f"Logged account lock for {username}")
        except Exception as e:
            logger.error(f"Failed to log account lock: {str(e)}")
    
    def log_permission_denied(
        self,
        user_id: int,
        username: str,
        endpoint: str,
        required_permission: str,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Log permission denied event
        
        Args:
            user_id: User ID
            username: Username
            endpoint: Endpoint that was accessed
            required_permission: Required permission
            ip_address: IP address of request
        """
        try:
            self._create_audit_log(
                event_type="permission_denied",
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                success=False,
                details={
                    "endpoint": endpoint,
                    "required_permission": required_permission
                }
            )
            logger.warning(f"Logged permission denied for {username} on {endpoint}")
        except Exception as e:
            logger.error(f"Failed to log permission denied: {str(e)}")
    
    def log_workspace_access(
        self,
        user_id: int,
        username: str,
        workspace_id: int,
        action: str,
        success: bool,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log workspace access attempt
        
        Args:
            user_id: User ID
            username: Username
            workspace_id: Workspace ID
            action: Action attempted (read, write, delete)
            success: Whether access was granted
            ip_address: IP address of request
            details: Additional details
        """
        try:
            self._create_audit_log(
                event_type="workspace_access",
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                success=success,
                details={
                    "workspace_id": workspace_id,
                    "action": action,
                    **(details or {})
                }
            )
            logger.info(f"Logged workspace access for {username}: workspace {workspace_id}")
        except Exception as e:
            logger.error(f"Failed to log workspace access: {str(e)}")
    
    def log_data_modification(
        self,
        user_id: int,
        username: str,
        workspace_id: int,
        resource_type: str,
        resource_id: int,
        action: str,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Log data modification event
        
        Args:
            user_id: User ID
            username: Username
            workspace_id: Workspace ID
            resource_type: Type of resource (project, connection, etc.)
            resource_id: Resource ID
            action: Action performed (create, update, delete)
            ip_address: IP address of request
        """
        try:
            self._create_audit_log(
                event_type="data_modification",
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                success=True,
                details={
                    "workspace_id": workspace_id,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "action": action
                }
            )
            logger.info(f"Logged data modification: {action} {resource_type} {resource_id}")
        except Exception as e:
            logger.error(f"Failed to log data modification: {str(e)}")
    
    def _create_audit_log(
        self,
        event_type: str,
        user_id: Optional[int],
        username: Optional[str],
        ip_address: Optional[str],
        success: bool,
        details: Dict[str, Any]
    ) -> None:
        """
        Create audit log entry in database
        
        Args:
            event_type: Type of event
            user_id: User ID (if applicable)
            username: Username (if applicable)
            ip_address: IP address
            success: Whether event was successful
            details: Event details as dict
        """
        try:
            query = text("""
                INSERT INTO audit_logs (
                    event_type, user_id, username, ip_address, details, success
                )
                VALUES (
                    :event_type, :user_id, :username, :ip_address, :details, :success
                )
            """)
            
            self.db.execute(
                query,
                {
                    "event_type": event_type,
                    "user_id": user_id,
                    "username": username,
                    "ip_address": ip_address,
                    "details": json.dumps(details),
                    "success": success
                }
            )
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create audit log: {str(e)}")
            raise
