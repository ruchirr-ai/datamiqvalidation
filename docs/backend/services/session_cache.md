# Session Cache Service Documentation

## Overview

The `SessionCache` service manages session data caching using Redis with automatic fallback to database when Redis is unavailable. It implements the cache-aside pattern for session storage, token blacklisting, and provides graceful degradation when Redis is down.

**Location**: `backend/services/session_cache.py`

## Purpose

- Cache user session data in Redis for fast access
- Implement token blacklisting for logout functionality
- Provide database fallback when Redis is unavailable
- Manage session TTL (Time To Live)
- Health check Redis availability

## Dependencies

```python
import os
import json
import logging
from typing import Optional, Dict, Any
import redis
from redis.exceptions import RedisError, ConnectionError
```

**External Libraries**:
- `redis`: Redis client library (install: `uv pip install redis`)

## Configuration

### Environment Variables

Configure Redis connection in `backend/.env`:

```bash
# Redis Configuration
REDIS_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_redis_password
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5
REDIS_MAX_CONNECTIONS=50
```

### Default Values
- **REDIS_ENABLED**: `true` (set to `false` to disable Redis)
- **REDIS_HOST**: `localhost`
- **REDIS_PORT**: `6379`
- **REDIS_DB**: `0`
- **REDIS_SOCKET_TIMEOUT**: `5` seconds
- **REDIS_SOCKET_CONNECT_TIMEOUT**: `5` seconds
- **REDIS_MAX_CONNECTIONS**: `50`
- **Default TTL**: `28800` seconds (8 hours)

## Class Definition

```python
class SessionCache:
    """Service for session caching with Redis"""
    
    def __init__(self):
        self.redis_client = None
        self.redis_enabled = os.getenv('REDIS_ENABLED', 'true').lower() == 'true'
        
        if self.redis_enabled:
            self._initialize_redis()
```

## Initialization

### Constructor

Creates a SessionCache instance and initializes Redis connection if enabled.

**Example**:
```python
from backend.services.session_cache import SessionCache

# Create instance (automatically initializes Redis)
cache = SessionCache()

# Check if Redis is available
if cache.redis_client:
    print("Redis connected")
else:
    print("Redis not available, using database fallback")
```

### Global Instance

A global instance is provided for convenience:

```python
from backend.services.session_cache import session_cache

# Use global instance
session_cache.cache_session(user_id, token, session_data)
```

## Methods

### cache_session()

Caches user session data in Redis with TTL.

**Signature**:
```python
def cache_session(
    self,
    user_id: int,
    token: str,
    session_data: Dict[str, Any],
    ttl: int = 28800  # 8 hours
) -> None
```

**Parameters**:
- `user_id` (int): User ID for logging purposes
- `token` (str): JWT token (used as cache key)
- `session_data` (Dict[str, Any]): Session data to cache
- `ttl` (int, optional): Time to live in seconds (default: 28800 = 8 hours)

**Returns**:
- `None`

**Error Handling**:
- Logs warning if Redis fails
- Does not raise exceptions (graceful degradation)
- Falls back to database on failure

**Cache Key Format**: `session:{token}`

**Example**:
```python
from backend.services.session_cache import session_cache

# Session data to cache
session_data = {
    "user_id": 123,
    "username": "john_doe",
    "role": "admin",
    "organization_id": 1,
    "workspace_id": 5,
    "permissions": ["read", "write", "delete"]
}

# Cache for 8 hours (default)
session_cache.cache_session(
    user_id=123,
    token="eyJ0eXAiOiJKV1QiLCJhbGc...",
    session_data=session_data
)

# Cache for 1 hour
session_cache.cache_session(
    user_id=123,
    token="eyJ0eXAiOiJKV1QiLCJhbGc...",
    session_data=session_data,
    ttl=3600  # 1 hour
)
```

**Usage in Authentication**:
```python
# After successful login
token = jwt_service.create_access_token(user.id, user.username, user.role)

session_data = {
    "user_id": user.id,
    "username": user.username,
    "role": user.role,
    "organization_id": user.organization_id,
    "workspace_id": current_workspace_id
}

# Cache session
session_cache.cache_session(user.id, token, session_data)

return {"access_token": token, "user": session_data}
```

---

### get_session()

Retrieves session data from Redis cache.

**Signature**:
```python
def get_session(self, token: str) -> Optional[Dict[str, Any]]
```

**Parameters**:
- `token` (str): JWT token (cache key)

**Returns**:
- `Dict[str, Any]`: Session data if found in cache
- `None`: If not found or Redis unavailable

**Error Handling**:
- Returns None if Redis fails
- Does not raise exceptions
- Logs warnings on errors

**Example**:
```python
from backend.services.session_cache import session_cache

token = "eyJ0eXAiOiJKV1QiLCJhbGc..."

# Try to get from cache
session_data = session_cache.get_session(token)

if session_data:
    print(f"Cache hit: User {session_data['username']}")
    user_id = session_data['user_id']
    role = session_data['role']
else:
    print("Cache miss: Fetching from database")
    # Fallback to database
    session = session_repository.get_by_token(token)
```

**Usage in Authentication Middleware**:
```python
# Cache-aside pattern with database fallback
async def get_current_user(token: str):
    # Step 1: Try cache first
    session_data = session_cache.get_session(token)
    
    if session_data:
        # Cache hit - return cached data
        return session_data
    
    # Step 2: Cache miss - fetch from database
    session = session_repository.get_by_token(token)
    
    if not session:
        raise AuthenticationError("Invalid token")
    
    # Step 3: Cache for next time
    session_data = {
        "user_id": session.user_id,
        "username": session.user.username,
        "role": session.user.role
    }
    session_cache.cache_session(session.user_id, token, session_data)
    
    return session_data
```

---

### invalidate_session()

Removes session data from Redis cache (used on logout or token refresh).

**Signature**:
```python
def invalidate_session(self, token: str) -> None
```

**Parameters**:
- `token` (str): JWT token (cache key)

**Returns**:
- `None`

**Error Handling**:
- Logs warning if Redis fails
- Does not raise exceptions

**Example**:
```python
from backend.services.session_cache import session_cache

# Invalidate session on logout
token = "eyJ0eXAiOiJKV1QiLCJhbGc..."
session_cache.invalidate_session(token)
print("Session removed from cache")
```

**Usage in Logout**:
```python
async def logout(token: str):
    # Step 1: Invalidate cache
    session_cache.invalidate_session(token)
    
    # Step 2: Add to blacklist
    session_cache.add_to_blacklist(token)
    
    # Step 3: Delete from database
    session_repository.delete_by_token(token)
    
    return {"message": "Logged out successfully"}
```

**Usage in Token Refresh**:
```python
async def refresh_token(old_token: str):
    # Invalidate old token cache
    session_cache.invalidate_session(old_token)
    
    # Generate new token
    new_token = jwt_service.create_access_token(user_id, username, role)
    
    # Cache new session
    session_cache.cache_session(user_id, new_token, session_data)
    
    return {"access_token": new_token}
```

---

### is_token_blacklisted()

Checks if a token has been blacklisted (logged out).

**Signature**:
```python
def is_token_blacklisted(self, token: str) -> bool
```

**Parameters**:
- `token` (str): JWT token to check

**Returns**:
- `bool`: True if blacklisted, False otherwise

**Error Handling**:
- Returns False if Redis fails (fail-open for availability)
- Does not raise exceptions
- Logs warnings on errors

**Cache Key Format**: `blacklist:{token}`

**Example**:
```python
from backend.services.session_cache import session_cache

token = "eyJ0eXAiOiJKV1QiLCJhbGc..."

if session_cache.is_token_blacklisted(token):
    print("Token has been revoked")
    raise AuthenticationError("Token is no longer valid")
else:
    print("Token is valid")
```

**Usage in Authentication Middleware**:
```python
async def verify_token(token: str):
    # Step 1: Check blacklist
    if session_cache.is_token_blacklisted(token):
        raise AuthenticationError("Token has been revoked")
    
    # Step 2: Verify JWT signature
    payload = jwt_service.verify_token(token)
    
    # Step 3: Get user data
    user = await get_current_user(token)
    
    return user
```

---

### add_to_blacklist()

Adds a token to the blacklist (used on logout).

**Signature**:
```python
def add_to_blacklist(self, token: str, ttl: int = 28800) -> None
```

**Parameters**:
- `token` (str): JWT token to blacklist
- `ttl` (int, optional): Time to live in seconds (default: 28800 = 8 hours)

**Returns**:
- `None`

**Error Handling**:
- Logs warning if Redis fails
- Does not raise exceptions

**TTL Recommendation**: Set TTL to match token expiration time to avoid storing expired tokens.

**Example**:
```python
from backend.services.session_cache import session_cache

# Blacklist token for 8 hours (default)
token = "eyJ0eXAiOiJKV1QiLCJhbGc..."
session_cache.add_to_blacklist(token)

# Blacklist token for 1 hour
session_cache.add_to_blacklist(token, ttl=3600)
```

**Usage in Logout**:
```python
async def logout(token: str):
    # Get token expiration from JWT
    payload = jwt_service.decode_token(token)
    exp_timestamp = payload.get('exp')
    
    # Calculate remaining TTL
    import time
    current_time = int(time.time())
    ttl = max(exp_timestamp - current_time, 0)
    
    # Add to blacklist with appropriate TTL
    session_cache.add_to_blacklist(token, ttl=ttl)
    
    # Invalidate cache
    session_cache.invalidate_session(token)
    
    # Delete from database
    session_repository.delete_by_token(token)
    
    return {"message": "Logged out successfully"}
```

---

### health_check()

Checks if Redis is available and responding.

**Signature**:
```python
def health_check(self) -> bool
```

**Parameters**:
- None

**Returns**:
- `bool`: True if Redis is healthy, False otherwise

**Example**:
```python
from backend.services.session_cache import session_cache

if session_cache.health_check():
    print("Redis is healthy")
else:
    print("Redis is down - using database fallback")
```

**Usage in Health Endpoint**:
```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "redis": session_cache.health_check(),
        "database": database.health_check()
    }
```

## Cache-Aside Pattern

The SessionCache implements the cache-aside (lazy loading) pattern:

### Read Flow

```python
def get_user_session(token: str):
    # 1. Check cache first
    session_data = session_cache.get_session(token)
    
    if session_data:
        # Cache hit - return immediately
        return session_data
    
    # 2. Cache miss - fetch from database
    session = session_repository.get_by_token(token)
    
    if not session:
        raise AuthenticationError("Invalid token")
    
    # 3. Populate cache for next time
    session_data = {
        "user_id": session.user_id,
        "username": session.user.username,
        "role": session.user.role
    }
    session_cache.cache_session(session.user_id, token, session_data)
    
    return session_data
```

### Write Flow

```python
def create_session(user_id: int, token: str, session_data: Dict):
    # 1. Write to database (source of truth)
    session_repository.create_session(user_id, token, session_data)
    
    # 2. Cache for fast access
    session_cache.cache_session(user_id, token, session_data)
    
    return session_data
```

### Invalidation Flow

```python
def delete_session(token: str):
    # 1. Invalidate cache
    session_cache.invalidate_session(token)
    
    # 2. Add to blacklist
    session_cache.add_to_blacklist(token)
    
    # 3. Delete from database
    session_repository.delete_by_token(token)
```

## Complete Usage Example

### Authentication Flow with Caching

```python
from backend.services.session_cache import session_cache
from backend.services.jwt_service import JWTService
from backend.repositories.user_repository import UserRepository
from backend.repositories.session_repository import SessionRepository

async def login(username: str, password: str):
    """Login with session caching"""
    
    # Step 1: Authenticate user
    user_repo = UserRepository()
    user = user_repo.get_by_username(username)
    
    if not user or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid credentials")
    
    # Step 2: Generate JWT token
    jwt_service = JWTService()
    token = jwt_service.create_access_token(user.id, user.username, user.role)
    
    # Step 3: Create session in database
    session_repo = SessionRepository()
    session = session_repo.create_session(
        user_id=user.id,
        token=token,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    
    # Step 4: Cache session data
    session_data = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "organization_id": user.organization_id,
        "workspace_id": user.default_workspace_id
    }
    session_cache.cache_session(user.id, token, session_data)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": session_data
    }

async def get_current_user(token: str):
    """Get current user with cache-aside pattern"""
    
    # Step 1: Check if token is blacklisted
    if session_cache.is_token_blacklisted(token):
        raise AuthenticationError("Token has been revoked")
    
    # Step 2: Try cache first
    session_data = session_cache.get_session(token)
    
    if session_data:
        return session_data
    
    # Step 3: Cache miss - fetch from database
    session_repo = SessionRepository()
    session = session_repo.get_by_token(token)
    
    if not session:
        raise AuthenticationError("Invalid token")
    
    # Step 4: Cache for next time
    session_data = {
        "user_id": session.user_id,
        "username": session.user.username,
        "role": session.user.role,
        "organization_id": session.user.organization_id
    }
    session_cache.cache_session(session.user_id, token, session_data, ttl=3600)
    
    return session_data

async def logout(token: str):
    """Logout with cache invalidation and blacklisting"""
    
    # Step 1: Get token expiration
    jwt_service = JWTService()
    payload = jwt_service.decode_token(token)
    exp_timestamp = payload.get('exp')
    
    # Calculate remaining TTL
    import time
    current_time = int(time.time())
    ttl = max(exp_timestamp - current_time, 0)
    
    # Step 2: Invalidate cache
    session_cache.invalidate_session(token)
    
    # Step 3: Add to blacklist
    session_cache.add_to_blacklist(token, ttl=ttl)
    
    # Step 4: Delete from database
    session_repo = SessionRepository()
    session_repo.delete_by_token(token)
    
    return {"message": "Logged out successfully"}
```

## Security Considerations

### Token Blacklisting
- **Logout Protection**: Prevents reuse of logged-out tokens
- **TTL Matching**: Blacklist TTL should match token expiration
- **Fail-Open**: Returns False if Redis is down (availability over security)

### Session Data
- **No Sensitive Data**: Never cache passwords or sensitive credentials
- **Minimal Data**: Cache only what's needed for authorization
- **TTL Management**: Set appropriate TTL based on security requirements

### Redis Security
- **Password Protection**: Always use Redis password in production
- **Network Isolation**: Run Redis in private network
- **TLS/SSL**: Enable encryption in transit for production
- **Access Control**: Use Redis ACLs to limit access

## Performance Considerations

### Connection Pooling
- **Max Connections**: 50 (configurable via REDIS_MAX_CONNECTIONS)
- **Reuse Connections**: Connection pool reuses connections
- **Timeout Settings**: 5-second timeouts prevent hanging

### Caching Strategy
- **Cache Hit Rate**: Monitor cache hit/miss ratio
- **TTL Optimization**: Balance between freshness and performance
- **Memory Usage**: Monitor Redis memory usage

### Fallback Performance
- **Graceful Degradation**: Application works without Redis
- **Database Load**: Database handles load when Redis is down
- **No Blocking**: Redis failures don't block requests

## Error Handling

### Redis Unavailable
```python
# Application continues to work
session_data = session_cache.get_session(token)

if session_data is None:
    # Fallback to database
    session = session_repository.get_by_token(token)
```

### Connection Timeout
```python
# Timeouts are configured
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5

# Operations fail fast and fallback to database
```

### Serialization Errors
```python
# JSON serialization handles most Python types
# Complex objects should be converted to dicts before caching
```

## Testing

### Unit Tests

```python
import pytest
from backend.services.session_cache import SessionCache

@pytest.fixture
def cache():
    """Create SessionCache instance for testing"""
    return SessionCache()

def test_cache_and_get_session(cache):
    """Test caching and retrieving session"""
    token = "test_token_123"
    session_data = {
        "user_id": 1,
        "username": "testuser",
        "role": "admin"
    }
    
    # Cache session
    cache.cache_session(1, token, session_data, ttl=60)
    
    # Retrieve session
    retrieved = cache.get_session(token)
    
    assert retrieved is not None
    assert retrieved["user_id"] == 1
    assert retrieved["username"] == "testuser"

def test_get_nonexistent_session(cache):
    """Test retrieving non-existent session"""
    result = cache.get_session("nonexistent_token")
    assert result is None

def test_invalidate_session(cache):
    """Test session invalidation"""
    token = "test_token_456"
    session_data = {"user_id": 2, "username": "user2"}
    
    # Cache and then invalidate
    cache.cache_session(2, token, session_data)
    cache.invalidate_session(token)
    
    # Should return None after invalidation
    result = cache.get_session(token)
    assert result is None

def test_token_blacklist(cache):
    """Test token blacklisting"""
    token = "test_token_789"
    
    # Initially not blacklisted
    assert cache.is_token_blacklisted(token) is False
    
    # Add to blacklist
    cache.add_to_blacklist(token, ttl=60)
    
    # Should be blacklisted now
    assert cache.is_token_blacklisted(token) is True

def test_health_check(cache):
    """Test Redis health check"""
    is_healthy = cache.health_check()
    # Result depends on Redis availability
    assert isinstance(is_healthy, bool)

def test_redis_disabled():
    """Test behavior when Redis is disabled"""
    import os
    os.environ['REDIS_ENABLED'] = 'false'
    
    cache = SessionCache()
    
    # Should not have Redis client
    assert cache.redis_client is None
    
    # Operations should not fail
    cache.cache_session(1, "token", {"user_id": 1})
    result = cache.get_session("token")
    assert result is None
```

## Related Documentation

- [Authentication Service](./authentication_service.md) - Uses SessionCache for session management
- [JWT Service](./jwt_service.md) - Generates tokens cached by SessionCache
- [Authentication API](../../api/authentication.md) - API endpoints using SessionCache
- [Caching Strategy](../../../.kiro/steering/caching-strategy.md) - Caching guidelines
- [Redis Configuration](../../../backend/.env) - Redis environment variables

## Troubleshooting

### Issue: Redis connection fails
**Solution**: Check Redis is running, verify host/port/password in `.env`, check network connectivity.

### Issue: Sessions not cached
**Solution**: Check `REDIS_ENABLED=true` in `.env`, verify Redis health with `health_check()`.

### Issue: Cache always returns None
**Solution**: Check Redis is running, verify TTL hasn't expired, check Redis memory limits.

### Issue: Blacklist not working
**Solution**: Verify Redis is available, check TTL is set correctly, ensure token format matches.

### Issue: High memory usage
**Solution**: Reduce TTL values, implement cache eviction policy, increase Redis memory limit.

---

**Last Updated**: 2026-01-25  
**Version**: 1.0  
**Status**: Production Ready
