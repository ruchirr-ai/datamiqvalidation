# Auth Middleware Documentation

## Overview

The `auth_middleware` module provides FastAPI dependencies for JWT authentication and role-based authorization. It handles token extraction, validation, user verification, and permission checking for protected API endpoints.

**Location**: `backend/shared/middleware/auth_middleware.py`

## Purpose

- Extract and validate JWT tokens from Authorization headers
- Authenticate users and inject user context into requests
- Enforce role-based access control (RBAC)
- Check permissions for specific operations
- Provide optional authentication for public/private endpoints
- Log authentication and authorization failures

## Dependencies

```python
from fastapi import Depends, HTTPException, status, Header
from typing import Optional, Callable
from sqlalchemy.orm import Session
import logging

from database import get_db
from services.jwt_service import JWTService
from services.session_cache import session_cache
from services.rbac_service import RBACService
from services.audit_logger import AuditLogger
from repositories.user_repository import UserRepository
```

## CurrentUser Class

Represents the authenticated user in the request context.

```python
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
```

**Attributes**:
- `user_id` (int): User's database ID
- `username` (str): User's username
- `role` (str): User's role (member, admin, owner)
- `organization_id` (Optional[int]): User's organization ID

## Functions

### extract_token_from_header()

Extracts JWT token from Authorization header.

**Signature**:
```python
def extract_token_from_header(authorization: Optional[str] = Header(None)) -> str
```

**Parameters**:
- `authorization` (Optional[str]): Authorization header value

**Returns**:
- `str`: JWT token

**Raises**:
- `HTTPException 401`: If header is missing or invalid

**Expected Header Format**: `Authorization: Bearer <token>`

**Example**:
```python
# Valid header
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...

# Invalid headers (will raise 401)
Authorization: eyJ0eXAiOiJKV1QiLCJhbGc...  # Missing "Bearer"
Authorization: Bearer   # Empty token
# No Authorization header
```

---

### get_current_user()

Main authentication dependency that validates JWT and returns current user.

**Signature**:
```python
async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> CurrentUser
```

**Parameters**:
- `authorization` (Optional[str]): Authorization header
- `db` (Session): Database session (injected)

**Returns**:
- `CurrentUser`: Authenticated user object

**Raises**:
- `HTTPException 401`: If authentication fails
- `HTTPException 403`: If user account is inactive

**Authentication Flow**:
1. Extract token from Authorization header
2. Check if token is blacklisted (logged out)
3. Validate JWT signature and expiration
4. Verify user exists in database
5. Check if user account is active
6. Return CurrentUser object

**Example Usage**:
```python
from fastapi import APIRouter, Depends
from backend.shared.middleware.auth_middleware import get_current_user, CurrentUser

router = APIRouter()

@router.get("/profile")
async def get_profile(current_user: CurrentUser = Depends(get_current_user)):
    """Protected endpoint - requires authentication"""
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "role": current_user.role
    }

@router.post("/projects")
async def create_project(
    project_data: dict,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Create project - requires authentication"""
    return {
        "message": "Project created",
        "created_by": current_user.username
    }
```

---

### require_role()

Dependency factory that requires a specific role or higher.

**Signature**:
```python
def require_role(required_role: str) -> Callable
```

**Parameters**:
- `required_role` (str): Required role (member, admin, owner)

**Returns**:
- `Callable`: FastAPI dependency function

**Role Hierarchy**: owner > admin > member

**Example Usage**:
```python
from backend.shared.middleware.auth_middleware import require_role, CurrentUser

# Require admin role (admin or owner can access)
@router.post("/admin/settings")
async def update_settings(
    settings: dict,
    current_user: CurrentUser = Depends(require_role("admin"))
):
    """Admin-only endpoint"""
    return {"message": "Settings updated"}

# Require owner role (only owner can access)
@router.delete("/organization")
async def delete_organization(
    current_user: CurrentUser = Depends(require_role("owner"))
):
    """Owner-only endpoint"""
    return {"message": "Organization deleted"}

# Require member role (all authenticated users can access)
@router.get("/dashboard")
async def get_dashboard(
    current_user: CurrentUser = Depends(require_role("member"))
):
    """All authenticated users can access"""
    return {"message": "Dashboard data"}
```

**Error Response** (403 Forbidden):
```json
{
  "detail": "Insufficient permissions. Required role: admin"
}
```

---

### require_permission()

Dependency factory that requires a specific permission.

**Signature**:
```python
def require_permission(required_permission: str) -> Callable
```

**Parameters**:
- `required_permission` (str): Required permission (e.g., "project:write")

**Returns**:
- `Callable`: FastAPI dependency function

**Permission Format**: `<resource>:<action>`

**Example Usage**:
```python
from backend.shared.middleware.auth_middleware import require_permission, CurrentUser

# Require project write permission
@router.post("/projects")
async def create_project(
    project_data: dict,
    current_user: CurrentUser = Depends(require_permission("project:write"))
):
    """Create project - requires project:write permission"""
    return {"message": "Project created"}

# Require connection delete permission
@router.delete("/connections/{connection_id}")
async def delete_connection(
    connection_id: int,
    current_user: CurrentUser = Depends(require_permission("connection:delete"))
):
    """Delete connection - requires connection:delete permission"""
    return {"message": "Connection deleted"}

# Require user management permission
@router.post("/users")
async def create_user(
    user_data: dict,
    current_user: CurrentUser = Depends(require_permission("user:create"))
):
    """Create user - requires user:create permission"""
    return {"message": "User created"}
```

**Error Response** (403 Forbidden):
```json
{
  "detail": "Insufficient permissions. Required permission: project:write"
}
```

---

### require_admin()

Convenience dependency that requires admin or owner role.

**Signature**:
```python
def require_admin() -> Callable
```

**Returns**:
- `Callable`: FastAPI dependency function

**Example Usage**:
```python
from backend.shared.middleware.auth_middleware import require_admin, CurrentUser

# Admin-only endpoint
@router.get("/admin/users")
async def list_all_users(
    current_user: CurrentUser = Depends(require_admin())
):
    """List all users - admin only"""
    return {"users": [...]}

@router.post("/admin/roles")
async def assign_role(
    user_id: int,
    role: str,
    current_user: CurrentUser = Depends(require_admin())
):
    """Assign role - admin only"""
    return {"message": "Role assigned"}
```

---

### get_current_user_optional()

Optional authentication dependency that doesn't raise exceptions.

**Signature**:
```python
async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[CurrentUser]
```

**Parameters**:
- `authorization` (Optional[str]): Authorization header
- `db` (Session): Database session (injected)

**Returns**:
- `CurrentUser`: If authenticated
- `None`: If not authenticated or authentication fails

**Example Usage**:
```python
from backend.shared.middleware.auth_middleware import get_current_user_optional, CurrentUser
from typing import Optional

# Endpoint with optional authentication
@router.get("/content")
async def get_content(
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional)
):
    """Public endpoint with optional authentication"""
    if current_user:
        # Authenticated user - return personalized content
        return {
            "message": f"Welcome back, {current_user.username}",
            "premium_content": True
        }
    else:
        # Guest user - return public content
        return {
            "message": "Welcome, guest",
            "premium_content": False
        }

# Mixed public/private endpoint
@router.get("/articles")
async def list_articles(
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional)
):
    """List articles - show more to authenticated users"""
    if current_user:
        # Show all articles including drafts
        return {"articles": get_all_articles()}
    else:
        # Show only published articles
        return {"articles": get_published_articles()}
```

## Complete Usage Examples

### Basic Protected Endpoint

```python
from fastapi import APIRouter, Depends
from backend.shared.middleware.auth_middleware import get_current_user, CurrentUser

router = APIRouter(prefix="/api", tags=["protected"])

@router.get("/me")
async def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user)
):
    """Get current user information"""
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "role": current_user.role,
        "organization_id": current_user.organization_id
    }
```

### Role-Based Endpoints

```python
from fastapi import APIRouter, Depends
from backend.shared.middleware.auth_middleware import (
    get_current_user,
    require_role,
    require_admin,
    CurrentUser
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# All authenticated users
@router.get("/dashboard")
async def get_dashboard(
    current_user: CurrentUser = Depends(require_role("member"))
):
    """Dashboard - all authenticated users"""
    return {"message": "Dashboard data"}

# Admin and owner only
@router.get("/settings")
async def get_settings(
    current_user: CurrentUser = Depends(require_role("admin"))
):
    """Settings - admin and owner only"""
    return {"settings": {...}}

# Owner only
@router.delete("/organization")
async def delete_organization(
    current_user: CurrentUser = Depends(require_role("owner"))
):
    """Delete organization - owner only"""
    return {"message": "Organization deleted"}

# Admin convenience function
@router.get("/users")
async def list_users(
    current_user: CurrentUser = Depends(require_admin())
):
    """List users - admin and owner"""
    return {"users": [...]}
```

### Permission-Based Endpoints

```python
from fastapi import APIRouter, Depends
from backend.shared.middleware.auth_middleware import require_permission, CurrentUser

router = APIRouter(prefix="/api/projects", tags=["projects"])

@router.get("/")
async def list_projects(
    current_user: CurrentUser = Depends(require_permission("project:read"))
):
    """List projects - requires project:read"""
    return {"projects": [...]}

@router.post("/")
async def create_project(
    project_data: dict,
    current_user: CurrentUser = Depends(require_permission("project:write"))
):
    """Create project - requires project:write"""
    return {"message": "Project created"}

@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    current_user: CurrentUser = Depends(require_permission("project:delete"))
):
    """Delete project - requires project:delete"""
    return {"message": "Project deleted"}
```

### Mixed Authentication Endpoint

```python
from fastapi import APIRouter, Depends
from typing import Optional
from backend.shared.middleware.auth_middleware import get_current_user_optional, CurrentUser

router = APIRouter(prefix="/api/public", tags=["public"])

@router.get("/articles")
async def list_articles(
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional)
):
    """List articles - public with optional authentication"""
    
    if current_user:
        # Authenticated - show all articles including drafts
        articles = get_all_articles(user_id=current_user.user_id)
        return {
            "articles": articles,
            "authenticated": True,
            "username": current_user.username
        }
    else:
        # Guest - show only published articles
        articles = get_published_articles()
        return {
            "articles": articles,
            "authenticated": False
        }
```

### Combining Multiple Dependencies

```python
from fastapi import APIRouter, Depends
from backend.shared.middleware.auth_middleware import get_current_user, require_role, CurrentUser
from backend.shared.middleware.workspace_middleware import get_current_workspace

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])

@router.post("/{workspace_id}/projects")
async def create_project_in_workspace(
    workspace_id: int,
    project_data: dict,
    current_user: CurrentUser = Depends(require_role("admin")),
    workspace = Depends(get_current_workspace)
):
    """Create project in workspace - requires admin role and workspace access"""
    
    # Both authentication and workspace validation passed
    return {
        "message": "Project created",
        "workspace_id": workspace.id,
        "created_by": current_user.username
    }
```

## Error Responses

### 401 Unauthorized

**Missing Authorization Header**:
```json
{
  "detail": "Authorization header missing"
}
```

**Invalid Header Format**:
```json
{
  "detail": "Invalid authorization header format. Expected: Bearer <token>"
}
```

**Invalid or Expired Token**:
```json
{
  "detail": "Invalid or expired token"
}
```

**Token Blacklisted**:
```json
{
  "detail": "Token has been revoked"
}
```

**User Not Found**:
```json
{
  "detail": "User not found"
}
```

### 403 Forbidden

**Insufficient Role**:
```json
{
  "detail": "Insufficient permissions. Required role: admin"
}
```

**Insufficient Permission**:
```json
{
  "detail": "Insufficient permissions. Required permission: project:write"
}
```

**Inactive Account**:
```json
{
  "detail": "User account is inactive"
}
```

**Admin Access Required**:
```json
{
  "detail": "Admin access required"
}
```

## Security Considerations

### Token Validation
- **Signature Verification**: JWT signature is verified using secret key
- **Expiration Check**: Expired tokens are rejected
- **Blacklist Check**: Logged-out tokens are rejected
- **User Verification**: User existence is verified in database

### Authorization
- **Role Hierarchy**: Enforced through RBACService
- **Permission Checks**: Fine-grained permission validation
- **Audit Logging**: All authorization failures are logged

### Best Practices
- **Always Use HTTPS**: Tokens should only be transmitted over HTTPS
- **Short Token Lifetime**: Use short-lived tokens (8 hours default)
- **Token Refresh**: Implement token refresh mechanism
- **Blacklist on Logout**: Add tokens to blacklist on logout

## Performance Considerations

### Caching
- **Session Cache**: User data can be cached in Redis
- **Token Validation**: JWT validation is fast (cryptographic operation)
- **Database Queries**: Minimize database queries with caching

### Optimization
```python
# Cache user data after first lookup
@lru_cache(maxsize=1000)
def get_cached_user(user_id: int):
    """Cache user data for 5 minutes"""
    return user_repo.get_user_by_id(user_id)
```

## Testing

### Unit Tests

```python
import pytest
from fastapi import HTTPException
from backend.shared.middleware.auth_middleware import (
    extract_token_from_header,
    get_current_user,
    require_role
)

def test_extract_token_valid():
    """Test extracting valid token"""
    token = extract_token_from_header("Bearer abc123")
    assert token == "abc123"

def test_extract_token_missing():
    """Test missing authorization header"""
    with pytest.raises(HTTPException) as exc:
        extract_token_from_header(None)
    assert exc.value.status_code == 401

def test_extract_token_invalid_format():
    """Test invalid header format"""
    with pytest.raises(HTTPException) as exc:
        extract_token_from_header("abc123")  # Missing "Bearer"
    assert exc.value.status_code == 401

@pytest.mark.asyncio
async def test_get_current_user_valid(mock_db, valid_token):
    """Test getting current user with valid token"""
    current_user = await get_current_user(f"Bearer {valid_token}", mock_db)
    assert current_user.user_id == 1
    assert current_user.username == "testuser"

@pytest.mark.asyncio
async def test_get_current_user_invalid_token(mock_db):
    """Test getting current user with invalid token"""
    with pytest.raises(HTTPException) as exc:
        await get_current_user("Bearer invalid_token", mock_db)
    assert exc.value.status_code == 401

@pytest.mark.asyncio
async def test_require_role_authorized(mock_current_user):
    """Test role requirement with authorized user"""
    checker = require_role("member")
    result = await checker(mock_current_user)
    assert result == mock_current_user

@pytest.mark.asyncio
async def test_require_role_unauthorized(mock_current_user):
    """Test role requirement with unauthorized user"""
    mock_current_user.role = "member"
    checker = require_role("admin")
    
    with pytest.raises(HTTPException) as exc:
        await checker(mock_current_user)
    assert exc.value.status_code == 403
```

## Related Documentation

- [JWT Service](../services/jwt_service.md) - Token generation and validation
- [RBAC Service](../services/rbac_service.md) - Role and permission checking
- [Session Cache](../services/session_cache.md) - Token blacklisting
- [Audit Logger](../services/audit_logger.md) - Authorization logging
- [User Repository](../repositories/user_repository.md) - User data access
- [Authentication API](../../api/authentication.md) - API endpoints

## Troubleshooting

### Issue: "Authorization header missing"
**Solution**: Ensure client sends `Authorization: Bearer <token>` header.

### Issue: "Invalid or expired token"
**Solution**: Token may be expired or invalid. Refresh token or re-authenticate.

### Issue: "Token has been revoked"
**Solution**: Token was blacklisted (logged out). User must log in again.

### Issue: "Insufficient permissions"
**Solution**: User doesn't have required role or permission. Check RBAC configuration.

### Issue: Authentication works but user data is stale
**Solution**: Clear session cache or reduce cache TTL.

---

**Last Updated**: 2026-01-25  
**Version**: 1.0  
**Status**: Production Ready
