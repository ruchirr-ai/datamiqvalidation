"""
Workspace Middleware
Validates workspace access and injects workspace context into requests
"""

from fastapi import Request, HTTPException, status
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class WorkspaceMiddleware:
    """Middleware to validate workspace access"""
    
    @staticmethod
    async def validate_workspace_access(
        workspace_id: int,
        user_id: int,
        db,
        required_role: str = "member"
    ) -> bool:
        """
        Validate if user has access to workspace with required role
        
        Args:
            workspace_id: Workspace ID to check
            user_id: User ID to check
            db: Database session
            required_role: Required role (member, admin, owner)
            
        Returns:
            True if user has access, raises HTTPException otherwise
        """
        from sqlalchemy import text
        
        try:
            # Check if user belongs to workspace
            query = text("""
                SELECT role FROM user_workspaces
                WHERE user_id = :user_id AND workspace_id = :workspace_id
            """)
            
            result = db.execute(
                query,
                {"user_id": user_id, "workspace_id": workspace_id}
            )
            row = result.fetchone()
            
            if row is None:
                logger.warning(
                    f"User {user_id} attempted to access workspace {workspace_id} without permission"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this workspace"
                )
            
            user_role = row[0]
            
            # Check role hierarchy: owner > admin > member
            role_hierarchy = {"owner": 3, "admin": 2, "member": 1}
            
            if role_hierarchy.get(user_role, 0) < role_hierarchy.get(required_role, 0):
                logger.warning(
                    f"User {user_id} has insufficient role {user_role} for workspace {workspace_id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions. Required role: {required_role}"
                )
            
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error validating workspace access: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error validating workspace access"
            )
    
    @staticmethod
    async def get_user_workspaces(user_id: int, db) -> list:
        """
        Get all workspaces user has access to
        
        Args:
            user_id: User ID
            db: Database session
            
        Returns:
            List of workspace dicts (empty list if workspaces table doesn't exist)
        """
        from sqlalchemy import text
        
        try:
            query = text("""
                SELECT w.id, w.name, w.slug, w.organization_id, uw.role
                FROM workspaces w
                JOIN user_workspaces uw ON w.id = uw.workspace_id
                WHERE uw.user_id = :user_id AND w.is_active = TRUE
                ORDER BY w.name
            """)
            
            result = db.execute(query, {"user_id": user_id})
            rows = result.fetchall()
            
            return [
                {
                    "id": row[0],
                    "name": row[1],
                    "slug": row[2],
                    "organization_id": row[3],
                    "role": row[4]
                }
                for row in rows
            ]
            
        except Exception as e:
            logger.error(f"Error getting user workspaces: {str(e)}")
            # Return empty list if workspaces table doesn't exist (for backward compatibility)
            # This allows the app to work without multi-tenancy features
            return []
    
    @staticmethod
    def extract_workspace_id(request: Request) -> Optional[int]:
        """
        Extract workspace_id from request headers or query params
        
        Args:
            request: FastAPI request object
            
        Returns:
            Workspace ID if found, None otherwise
        """
        # Try header first
        workspace_id = request.headers.get("X-Workspace-ID")
        
        # Try query param
        if not workspace_id:
            workspace_id = request.query_params.get("workspace_id")
        
        # Try path param (if available in request state)
        if not workspace_id and hasattr(request.state, "workspace_id"):
            workspace_id = request.state.workspace_id
        
        if workspace_id:
            try:
                return int(workspace_id)
            except ValueError:
                return None
        
        return None
