# Authentication Service Documentation

## Overview
The Authentication Service handles user login, authentication, token generation, and workspace context management. It orchestrates the authentication flow by coordinating between the user repository, password verification, JWT token generation, and session caching.

## Module
`backend/services/authentication_service.py`

## Dependencies
- `services.auth_service.AuthService` - Password hashing and verification
- `services.jwt_service.JWTService` - JWT token operations
- `repositories.user_repository.UserRepository` - Database operations
- `services.session_cache.session_cache` - Redis session caching

## Class: AuthenticationService

### Purpose
Provides high-level authentication operations including login, logout, token validation, and workspace access management.

### Constructor

```python
def __init__(self, user_repository: UserRepository)
```

**Parameters**:
- `user_repository` (UserRepository): Repository for user database operations

**Example**:
```python
from repositories.user_repository import UserRepository
from services.authentication_service import AuthenticationService

user_repo = UserRepository(db_session)
auth_service = AuthenticationService(user_repo)
```

---

## Methods

### authenticate_user

```python
def authenticate_user(username: str, password: str) -> Dict[str, Any]
```

Authenticates a user with username and password, generates JWT token, and caches session.

**Parameters**:
- `username` (str): User's username
- `password` (str): User's plain text password

**Returns**:
- `Dict[str, Any]`: Dictionary containing:
  - `access_token` (str): JWT token
  - `token_type` (str): Always "bearer"
  - `user` (dict): User information
    - `id` (int): User ID
    - `username` (str): Username
    - `role` (str): User role
    - `organization_id` (int): Organization ID

**Raises**:
- `AuthenticationError`: If authentication fails for any reason:
  - Invalid username or password
  - Account locked due to failed attempts
  - Server error

**Behavior**:
1. Retrieves user from database by username
2. Checks if account is locked
3. Verifies password against stored hash
4. Increments failed attempts on password mismatch
5. Locks account after 5 failed attempts
6. Resets failed attempts on successful login
7. Updates last login timestamp
8. Generates JWT token
9. Caches session in Redis
10. Returns token and user info

**Example**:
```python
try:
    result = auth_service.authenticate_user("admin", "AdminPass123!")
    token = result["access_token"]
    user = result["user"]
    print(f"Login successful for {user['username']}")
except AuthenticationError as e:
    print(f"Login failed: {str(e)}")
```

**Error Messages**:
- `"Invalid username or password"` - Generic error for invalid credentials
- `"Account temporarily locked due to multiple failed login attempts. Please try again later."` - Account locked
- `"Authentication failed due to server error"` - Unexpected error

---

### logout_user

```python
def logout_user(token: str) -> None
```

Logs out a user by invalidating their JWT token and session cache.

**Parameters**:
- `token` (str): JWT token to invalidate

**Returns**:
- None

**Raises**:
- None (errors are logged but not raised)

**Behavior**:
1. Adds token to Redis blacklist with 8-hour TTL
2. Invalidates session cache entry
3. Logs successful logout
4. Never raises exceptions (logout always succeeds)

**Example**:
```python
auth_service.logout_user(token)
print("User logged out successfully")
```

**Notes**:
- Logout always succeeds even if token is invalid
- Token remains blacklisted for 8 hours (token expiration time)
- Session cache is cleared immediately

---

### validate_token

```python
def validate_token(token: str) -> Optional[Dict[str, Any]]
```

Validates a JWT token and returns user information if valid.

**Parameters**:
- `token` (str): JWT token to validate

**Returns**:
- `Dict[str, Any]` if valid: User information dictionary
  - `user_id` (int): User ID
  - `username` (str): Username
  - `role` (str): User role
- `None` if invalid: Token is blacklisted, expired, or malformed

**Raises**:
- None (errors are logged but not raised)

**Behavior**:
1. Checks if token is in blacklist
2. Validates token signature and expiration
3. Extracts user information from payload
4. Returns user info or None

**Example**:
```python
user_info = auth_service.validate_token(token)
if user_info:
    print(f"Valid token for user: {user_info['username']}")
else:
    print("Invalid or expired token")
```

**Validation Checks**:
- Token not in blacklist
- Valid signature
- Not expired
- Valid payload structure

---

### get_user_workspaces

```python
def get_user_workspaces(user_id: int) -> list
```

Retrieves all workspaces a user has access to.

**Parameters**:
- `user_id` (int): User ID

**Returns**:
- `list`: List of workspace dictionaries, each containing:
  - `id` (int): Workspace ID
  - `name` (str): Workspace name
  - `slug` (str): Workspace slug
  - `role` (str): User's role in workspace (owner, admin, member)
  - `organization_id` (int): Organization ID

**Raises**:
- None (errors are logged, empty list returned)

**Example**:
```python
workspaces = auth_service.get_user_workspaces(user_id=1)
for workspace in workspaces:
    print(f"Workspace: {workspace['name']} (Role: {workspace['role']})")
```

**Notes**:
- Returns empty list if user has no workspaces
- Returns empty list on error
- Workspaces are filtered by user membership

---

## Authentication Flow

### Login Flow

```
1. User submits credentials
   ↓
2. Retrieve user from database
   ↓
3. Check account lock status
   ↓
4. Verify password
   ↓
5. Update failed attempts (if password wrong)
   ↓
6. Lock account (if threshold reached)
   ↓
7. Reset failed attempts (if password correct)
   ↓
8. Update last login timestamp
   ↓
9. Generate JWT token
   ↓
10. Cache session in Redis
   ↓
11. Return token and user info
```

### Logout Flow

```
1. Receive logout request with token
   ↓
2. Add token to blacklist (Redis)
   ↓
3. Invalidate session cache
   ↓
4. Log logout event
   ↓
5. Return success
```

### Token Validation Flow

```
1. Receive token
   ↓
2. Check blacklist (Redis)
   ↓
3. Validate signature
   ↓
4. Check expiration
   ↓
5. Extract user info
   ↓
6. Return user info or None
```

---

## Account Locking

### Locking Rules
- **Threshold**: 5 failed login attempts
- **Window**: 15 minutes
- **Lockout Duration**: 30 minutes
- **Reset**: Failed attempts reset on successful login

### Lock Behavior
- Failed attempts are tracked per user
- Account locks after 5 consecutive failures
- Lock expires automatically after 30 minutes
- Locked accounts cannot authenticate
- Lock status checked before password verification

---

## Session Caching

### Cache Strategy
- **Cache Layer**: Redis (primary)
- **Fallback**: Database (if Redis unavailable)
- **TTL**: 8 hours (matches token expiration)
- **Pattern**: Cache-aside

### Cached Data
```python
{
    "user_id": 1,
    "username": "admin",
    "role": "admin",
    "organization_id": 1,
    "login_time": "2026-01-25T10:30:00"
}
```

### Cache Operations
- **Set**: On successful login
- **Get**: On token validation (optional)
- **Delete**: On logout
- **Blacklist**: On logout (token blacklist)

---

## Error Handling

### Authentication Errors

| Error | Status Code | Message |
|-------|-------------|---------|
| Invalid credentials | 401 | "Invalid username or password" |
| Account locked | 423 | "Account temporarily locked..." |
| Server error | 500 | "Authentication failed due to server error" |

### Error Logging
- All authentication failures are logged
- Account locks are logged with username
- Server errors are logged with stack trace
- Successful logins are logged

---

## Security Considerations

### Password Security
- Passwords never logged or displayed
- Generic error messages (no username/password hints)
- Bcrypt hashing with cost factor 12
- Password verification timing-safe

### Token Security
- Tokens expire after 8 hours
- Logged out tokens are blacklisted
- Token validation checks blacklist first
- Tokens include user_id, username, role

### Account Protection
- Account locking after failed attempts
- Lockout duration prevents brute force
- Failed attempts tracked per user
- Lock status persisted in database

### Timing Attack Prevention
- Failed attempts incremented for non-existent users
- Password verification always performed
- Generic error messages
- Consistent response times

---

## Usage Examples

### Complete Login Flow

```python
from repositories.user_repository import UserRepository
from services.authentication_service import AuthenticationService
from services.auth_service import AuthenticationError

# Initialize service
user_repo = UserRepository(db_session)
auth_service = AuthenticationService(user_repo)

# Attempt login
try:
    result = auth_service.authenticate_user(
        username="admin",
        password="AdminPass123!"
    )
    
    # Store token
    token = result["access_token"]
    user = result["user"]
    
    print(f"Login successful!")
    print(f"User: {user['username']}")
    print(f"Role: {user['role']}")
    print(f"Token: {token[:20]}...")
    
except AuthenticationError as e:
    print(f"Login failed: {str(e)}")
```

### Token Validation

```python
# Validate token
user_info = auth_service.validate_token(token)

if user_info:
    print(f"Valid token for user: {user_info['username']}")
    print(f"Role: {user_info['role']}")
else:
    print("Invalid or expired token")
```

### Logout

```python
# Logout user
auth_service.logout_user(token)
print("User logged out successfully")

# Verify token is now invalid
user_info = auth_service.validate_token(token)
assert user_info is None, "Token should be invalid after logout"
```

### Get User Workspaces

```python
# Get workspaces
workspaces = auth_service.get_user_workspaces(user_id=1)

print(f"User has access to {len(workspaces)} workspaces:")
for workspace in workspaces:
    print(f"  - {workspace['name']} ({workspace['role']})")
```

---

## Testing

### Unit Tests
- Test successful authentication
- Test invalid credentials
- Test account locking
- Test logout
- Test token validation
- Test workspace retrieval

### Integration Tests
- Test complete login flow
- Test session caching
- Test token blacklisting
- Test Redis fallback

### Property-Based Tests
- Test authentication with random valid credentials
- Test authentication with random invalid credentials
- Test token validation with random tokens

---

## Performance Considerations

### Optimization
- Redis caching reduces database load
- Session data cached for 8 hours
- Token validation uses cache when available
- Database queries optimized with indexes

### Scalability
- Stateless authentication (JWT)
- Redis cluster for high availability
- Connection pooling for database
- Horizontal scaling supported

---

## Logging

### Log Levels
- **INFO**: Successful logins, logouts
- **WARNING**: Failed login attempts, account locks, blacklisted tokens
- **ERROR**: Server errors, unexpected exceptions

### Log Format
```
2026-01-25 10:30:00 INFO Successful login for user: admin
2026-01-25 10:31:00 WARNING Failed login attempt for user: admin
2026-01-25 10:32:00 WARNING Account locked for user: admin
2026-01-25 10:33:00 ERROR Unexpected error during authentication: ...
```

---

## Related Documentation
- [JWT Service](./jwt_service.md)
- [Auth Service](./auth_service.md)
- [User Repository](../repositories/user_repository.md)
- [Session Cache](./session_cache.md)
- [Authentication API](../../api/authentication.md)
