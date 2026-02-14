# RBAC Service Documentation

## Overview
The RBAC (Role-Based Access Control) Service manages workspace and resource permissions based on user roles. It provides role hierarchy, permission checking, and navigation filtering for multi-tenant workspace isolation.

## Module
`backend/services/rbac_service.py`

## Purpose
Implements role-based access control for DataMIQ's multi-tenant SaaS architecture, ensuring users can only access resources within their permission level.

---

## Role Hierarchy

### Roles (Highest to Lowest)

```
owner (level 3)
  ↓
admin (level 2)
  ↓
member (level 1)
```

### Role Definitions

| Role | Level | Description |
|------|-------|-------------|
| **owner** | 3 | Full workspace control including user management and deletion |
| **admin** | 2 | Can manage resources but not workspace settings |
| **member** | 1 | Read-only access to workspace resources |

---

## Permissions Matrix

### Owner Permissions
- ✅ workspace:read, write, delete, manage_users
- ✅ connection:read, write, delete
- ✅ project:read, write, delete
- ✅ migration:read, write, execute, delete
- ✅ assessment:read, write
- ✅ monitoring:read
- ✅ validation:read, write

### Admin Permissions
- ✅ workspace:read, write
- ✅ connection:read, write, delete
- ✅ project:read, write, delete
- ✅ migration:read, write, execute
- ✅ assessment:read, write
- ✅ monitoring:read
- ✅ validation:read, write
- ❌ workspace:delete, manage_users

### Member Permissions
- ✅ workspace:read
- ✅ connection:read
- ✅ project:read
- ✅ migration:read
- ✅ assessment:read
- ✅ monitoring:read
- ✅ validation:read
- ❌ All write, delete, execute permissions

---

## Class: RBACService

### Purpose
Provides static methods for role-based permission checking and navigation filtering.

### Constants

```python
ROLE_HIERARCHY = {
    "owner": 3,
    "admin": 2,
    "member": 1
}

ROLE_PERMISSIONS = {
    "owner": [...],    # Full permissions
    "admin": [...],    # Admin permissions
    "member": [...]    # Read-only permissions
}
```

---

## Methods

### check_permission

```python
@staticmethod
def check_permission(user_role: str, required_permission: str) -> bool
```

Checks if a user role has a specific permission.

**Parameters**:
- `user_role` (str): User's role (owner, admin, member)
- `required_permission` (str): Required permission (e.g., "project:write")

**Returns**:
- `bool`: True if user has permission, False otherwise

**Permission Format**: `{resource}:{action}`
- Resources: workspace, connection, project, migration, assessment, monitoring, validation
- Actions: read, write, delete, execute, manage_users

**Example**:
```python
# Check if admin can write projects
can_write = RBACService.check_permission("admin", "project:write")
print(can_write)  # True

# Check if member can write projects
can_write = RBACService.check_permission("member", "project:write")
print(can_write)  # False

# Check if owner can manage users
can_manage = RBACService.check_permission("owner", "workspace:manage_users")
print(can_manage)  # True
```

**Use Cases**:
- API endpoint authorization
- UI feature visibility
- Resource operation validation
- Workspace management

---

### has_role_level

```python
@staticmethod
def has_role_level(user_role: str, required_role: str) -> bool
```

Checks if user role meets or exceeds required role level in hierarchy.

**Parameters**:
- `user_role` (str): User's current role
- `required_role` (str): Required role level

**Returns**:
- `bool`: True if user role is sufficient, False otherwise

**Example**:
```python
# Admin meets member requirement
result = RBACService.has_role_level("admin", "member")
print(result)  # True

# Member does not meet admin requirement
result = RBACService.has_role_level("member", "admin")
print(result)  # False

# Owner meets admin requirement
result = RBACService.has_role_level("owner", "admin")
print(result)  # True
```

**Use Cases**:
- Navigation filtering
- Route protection
- Feature gating
- UI component visibility

---

### filter_navigation_items

```python
@staticmethod
def filter_navigation_items(
    user_role: str,
    all_items: List[Dict[str, Any]]
) -> List[Dict[str, Any]]
```

Filters navigation items based on user role, including nested children.

**Parameters**:
- `user_role` (str): User's role
- `all_items` (List[Dict]): List of all navigation items

**Returns**:
- `List[Dict]`: Filtered list of navigation items user can access

**Navigation Item Structure**:
```python
{
    "id": "dashboard",
    "label": "Dashboard",
    "path": "/dashboard",
    "icon": "...",
    "required_role": "member",  # Optional, defaults to "member"
    "children": [...]           # Optional nested items
}
```

**Example**:
```python
all_items = [
    {
        "id": "dashboard",
        "label": "Dashboard",
        "required_role": "member"
    },
    {
        "id": "connections",
        "label": "Connections",
        "required_role": "member"
    },
    {
        "id": "admin",
        "label": "Administration",
        "required_role": "admin",
        "children": [
            {
                "id": "users",
                "label": "User Management",
                "required_role": "owner"
            }
        ]
    }
]

# Filter for member role
member_items = RBACService.filter_navigation_items("member", all_items)
# Returns: [dashboard, connections]

# Filter for admin role
admin_items = RBACService.filter_navigation_items("admin", all_items)
# Returns: [dashboard, connections, admin (without children)]

# Filter for owner role
owner_items = RBACService.filter_navigation_items("owner", all_items)
# Returns: [dashboard, connections, admin (with children)]
```

**Behavior**:
- Recursively filters nested children
- Removes items user cannot access
- Preserves item structure
- Defaults to "member" if no required_role specified

---

### get_user_permissions

```python
@staticmethod
def get_user_permissions(user_role: str) -> List[str]
```

Returns all permissions for a user role.

**Parameters**:
- `user_role` (str): User's role

**Returns**:
- `List[str]`: List of permission strings

**Example**:
```python
# Get admin permissions
perms = RBACService.get_user_permissions("admin")
print(perms)
# ['workspace:read', 'workspace:write', 'connection:read', ...]

# Check if specific permission exists
has_write = "project:write" in perms
print(has_write)  # True for admin
```

**Use Cases**:
- Permission auditing
- UI feature discovery
- API capability listing
- Role comparison

---

### has_admin_access

```python
@staticmethod
def has_admin_access(user_role: str) -> bool
```

Checks if user has admin-level access (admin or owner).

**Parameters**:
- `user_role` (str): User's role

**Returns**:
- `bool`: True if user is admin or owner, False otherwise

**Example**:
```python
# Check admin access
is_admin = RBACService.has_admin_access("admin")
print(is_admin)  # True

is_admin = RBACService.has_admin_access("member")
print(is_admin)  # False

is_admin = RBACService.has_admin_access("owner")
print(is_admin)  # True
```

**Use Cases**:
- Admin panel access
- System settings visibility
- Audit log access
- User management features

---

### can_manage_workspace

```python
@staticmethod
def can_manage_workspace(user_role: str) -> bool
```

Checks if user can manage workspace settings and users.

**Parameters**:
- `user_role` (str): User's role

**Returns**:
- `bool`: True if user can manage workspace (owner only)

**Example**:
```python
can_manage = RBACService.can_manage_workspace("owner")
print(can_manage)  # True

can_manage = RBACService.can_manage_workspace("admin")
print(can_manage)  # False
```

**Use Cases**:
- Workspace settings access
- User invitation/removal
- Workspace deletion
- Billing management

---

### can_execute_migration

```python
@staticmethod
def can_execute_migration(user_role: str) -> bool
```

Checks if user can execute migrations.

**Parameters**:
- `user_role` (str): User's role

**Returns**:
- `bool`: True if user can execute migrations (admin or owner)

**Example**:
```python
can_execute = RBACService.can_execute_migration("admin")
print(can_execute)  # True

can_execute = RBACService.can_execute_migration("member")
print(can_execute)  # False
```

**Use Cases**:
- Migration execution button visibility
- Migration start/stop controls
- Dangerous operation protection

---

## Usage Examples

### API Endpoint Authorization

```python
from services.rbac_service import RBACService
from fastapi import HTTPException

def check_project_write_permission(user_role: str):
    """Middleware to check project write permission"""
    if not RBACService.check_permission(user_role, "project:write"):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to modify projects"
        )

@app.post("/api/projects")
async def create_project(current_user: User):
    check_project_write_permission(current_user.role)
    # Create project logic
```

### Navigation Filtering

```python
from services.rbac_service import RBACService

def get_user_navigation(user_role: str):
    """Get navigation items for user"""
    all_items = [
        {"id": "dashboard", "label": "Dashboard", "required_role": "member"},
        {"id": "connections", "label": "Connections", "required_role": "member"},
        {"id": "migrations", "label": "Migrations", "required_role": "member"},
        {"id": "admin", "label": "Administration", "required_role": "admin"}
    ]
    
    return RBACService.filter_navigation_items(user_role, all_items)

# Get navigation for member
nav = get_user_navigation("member")
# Returns: [dashboard, connections, migrations]

# Get navigation for admin
nav = get_user_navigation("admin")
# Returns: [dashboard, connections, migrations, admin]
```

### Feature Gating

```python
from services.rbac_service import RBACService

def render_migration_controls(user_role: str):
    """Render migration controls based on role"""
    can_execute = RBACService.can_execute_migration(user_role)
    
    if can_execute:
        return {
            "show_start_button": True,
            "show_stop_button": True,
            "show_delete_button": True
        }
    else:
        return {
            "show_start_button": False,
            "show_stop_button": False,
            "show_delete_button": False
        }
```

### Role Comparison

```python
from services.rbac_service import RBACService

def compare_roles(role1: str, role2: str):
    """Compare two roles"""
    level1 = RBACService.ROLE_HIERARCHY.get(role1, 0)
    level2 = RBACService.ROLE_HIERARCHY.get(role2, 0)
    
    if level1 > level2:
        return f"{role1} has higher privileges than {role2}"
    elif level1 < level2:
        return f"{role2} has higher privileges than {role1}"
    else:
        return f"{role1} and {role2} have equal privileges"

print(compare_roles("admin", "member"))
# Output: admin has higher privileges than member
```

---

## Multi-Tenant Workspace Context

### Workspace Roles
Each user has a role **per workspace**:
- User can be **owner** in workspace A
- Same user can be **member** in workspace B
- Role is determined by `user_workspaces` table

### Permission Checking Flow

```
1. Identify current workspace
   ↓
2. Get user's role in workspace
   ↓
3. Check permission for role
   ↓
4. Allow or deny access
```

### Example

```python
# User has different roles in different workspaces
user_workspaces = [
    {"workspace_id": 1, "role": "owner"},
    {"workspace_id": 2, "role": "member"}
]

# In workspace 1 (owner)
can_delete = RBACService.check_permission("owner", "project:delete")
# True

# In workspace 2 (member)
can_delete = RBACService.check_permission("member", "project:delete")
# False
```

---

## Security Considerations

### Permission Enforcement
- **Backend**: Always check permissions in API endpoints
- **Frontend**: Hide UI elements user cannot access
- **Database**: Filter queries by workspace_id
- **Middleware**: Validate permissions before processing

### Best Practices
- ✅ Check permissions on every API request
- ✅ Filter navigation based on role
- ✅ Validate workspace membership
- ✅ Log permission denials
- ✅ Use role hierarchy for comparisons
- ❌ Never trust client-side permission checks
- ❌ Never skip permission validation
- ❌ Never expose admin features to non-admins

---

## Testing

### Unit Tests

```python
def test_check_permission():
    """Test permission checking"""
    assert RBACService.check_permission("admin", "project:write") == True
    assert RBACService.check_permission("member", "project:write") == False

def test_has_role_level():
    """Test role level checking"""
    assert RBACService.has_role_level("admin", "member") == True
    assert RBACService.has_role_level("member", "admin") == False

def test_filter_navigation():
    """Test navigation filtering"""
    items = [
        {"id": "dashboard", "required_role": "member"},
        {"id": "admin", "required_role": "admin"}
    ]
    
    member_nav = RBACService.filter_navigation_items("member", items)
    assert len(member_nav) == 1
    assert member_nav[0]["id"] == "dashboard"
    
    admin_nav = RBACService.filter_navigation_items("admin", items)
    assert len(admin_nav) == 2
```

### Property-Based Tests

```python
from hypothesis import given
from hypothesis.strategies import sampled_from

roles = sampled_from(["owner", "admin", "member"])

@given(user_role=roles, required_role=roles)
def test_role_hierarchy_property(user_role, required_role):
    """Property: Higher roles should have access to lower role features"""
    user_level = RBACService.ROLE_HIERARCHY[user_role]
    required_level = RBACService.ROLE_HIERARCHY[required_role]
    
    result = RBACService.has_role_level(user_role, required_role)
    expected = user_level >= required_level
    
    assert result == expected
```

---

## Related Documentation
- [Authentication Service](./authentication_service.md)
- [Workspace Middleware](../middleware/workspace_middleware.md)
- [Auth Middleware](../middleware/auth_middleware.md)
- [SaaS Architecture](../../../.kiro/steering/saas-architecture.md)
