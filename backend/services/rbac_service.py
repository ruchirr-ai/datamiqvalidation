"""
RBAC Service
Role-Based Access Control for workspace and resource permissions
"""

from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class RBACService:
    """Service for role-based access control"""
    
    # Role hierarchy: owner > admin > member
    ROLE_HIERARCHY = {
        "owner": 3,
        "admin": 2,
        "member": 1
    }
    
    # Permissions by role
    ROLE_PERMISSIONS = {
        "owner": [
            "workspace:read",
            "workspace:write",
            "workspace:delete",
            "workspace:manage_users",
            "connection:read",
            "connection:write",
            "connection:delete",
            "project:read",
            "project:write",
            "project:delete",
            "migration:read",
            "migration:write",
            "migration:execute",
            "migration:delete",
            "assessment:read",
            "assessment:write",
            "monitoring:read",
            "validation:read",
            "validation:write"
        ],
        "admin": [
            "workspace:read",
            "workspace:write",
            "connection:read",
            "connection:write",
            "connection:delete",
            "project:read",
            "project:write",
            "project:delete",
            "migration:read",
            "migration:write",
            "migration:execute",
            "assessment:read",
            "assessment:write",
            "monitoring:read",
            "validation:read",
            "validation:write"
        ],
        "member": [
            "workspace:read",
            "connection:read",
            "project:read",
            "migration:read",
            "assessment:read",
            "monitoring:read",
            "validation:read"
        ]
    }
    
    @staticmethod
    def check_permission(user_role: str, required_permission: str) -> bool:
        """
        Check if user role has required permission
        
        Args:
            user_role: User's role (owner, admin, member)
            required_permission: Required permission (e.g., "project:write")
            
        Returns:
            True if user has permission, False otherwise
            
        Example:
            >>> RBACService.check_permission("admin", "project:write")
            True
            >>> RBACService.check_permission("member", "project:write")
            False
        """
        permissions = RBACService.ROLE_PERMISSIONS.get(user_role, [])
        return required_permission in permissions
    
    @staticmethod
    def has_role_level(user_role: str, required_role: str) -> bool:
        """
        Check if user role meets or exceeds required role level
        
        Args:
            user_role: User's current role
            required_role: Required role level
            
        Returns:
            True if user role is sufficient, False otherwise
            
        Example:
            >>> RBACService.has_role_level("admin", "member")
            True
            >>> RBACService.has_role_level("member", "admin")
            False
        """
        user_level = RBACService.ROLE_HIERARCHY.get(user_role, 0)
        required_level = RBACService.ROLE_HIERARCHY.get(required_role, 0)
        return user_level >= required_level
    
    @staticmethod
    def filter_navigation_items(
        user_role: str,
        all_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Filter navigation items based on user role
        
        Args:
            user_role: User's role
            all_items: List of all navigation items
            
        Returns:
            Filtered list of navigation items user can access
            
        Example:
            >>> items = [
            ...     {"id": "dashboard", "label": "Dashboard", "required_role": "member"},
            ...     {"id": "admin", "label": "Administration", "required_role": "admin"}
            ... ]
            >>> RBACService.filter_navigation_items("member", items)
            [{'id': 'dashboard', 'label': 'Dashboard', 'required_role': 'member'}]
        """
        filtered_items = []
        
        for item in all_items:
            required_role = item.get("required_role", "member")
            
            if RBACService.has_role_level(user_role, required_role):
                # Filter children if present
                if "children" in item and item["children"]:
                    item["children"] = RBACService.filter_navigation_items(
                        user_role,
                        item["children"]
                    )
                
                filtered_items.append(item)
        
        return filtered_items
    
    @staticmethod
    def get_user_permissions(user_role: str) -> List[str]:
        """
        Get all permissions for a user role
        
        Args:
            user_role: User's role
            
        Returns:
            List of permission strings
            
        Example:
            >>> perms = RBACService.get_user_permissions("admin")
            >>> "project:write" in perms
            True
        """
        return RBACService.ROLE_PERMISSIONS.get(user_role, [])
    
    @staticmethod
    def has_admin_access(user_role: str) -> bool:
        """
        Check if user has admin-level access
        
        Args:
            user_role: User's role
            
        Returns:
            True if user is admin or owner, False otherwise
            
        Example:
            >>> RBACService.has_admin_access("admin")
            True
            >>> RBACService.has_admin_access("member")
            False
        """
        return user_role in ["admin", "owner"]
    
    @staticmethod
    def can_manage_workspace(user_role: str) -> bool:
        """
        Check if user can manage workspace settings
        
        Args:
            user_role: User's role
            
        Returns:
            True if user can manage workspace, False otherwise
        """
        return RBACService.check_permission(user_role, "workspace:manage_users")
    
    @staticmethod
    def can_execute_migration(user_role: str) -> bool:
        """
        Check if user can execute migrations
        
        Args:
            user_role: User's role
            
        Returns:
            True if user can execute migrations, False otherwise
        """
        return RBACService.check_permission(user_role, "migration:execute")
