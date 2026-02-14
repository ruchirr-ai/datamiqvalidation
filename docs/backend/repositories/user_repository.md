# User Repository Documentation

## Overview

The `UserRepository` handles all database operations for user management. It provides CRUD operations, authentication support, and account locking functionality using raw SQL queries with SQLAlchemy for optimal performance and control.

**Location**: `backend/repositories/user_repository.py`

## Purpose

- Create new users in the database
- Retrieve users by username or ID
- Update user login timestamps
- Manage failed login attempts
- Lock and unlock user accounts
- Check user existence

## Dependencies

```python
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
```

**Database Table**: `users`

## Database Schema

The repository interacts with the `users` table:

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMP
);
```

## Class Definition

```python
class UserRepository:
    """Repository for user database operations"""
    
    def __init__(self, db: Session):
        self.db = db
```

**Constructor Parameters**:
- `db` (Session): SQLAlchemy database session

## Methods

### create_user()

Creates a new user in the database.

**Signature**:
```python
def create_user(
    self,
    username: str,
    password_hash: str,
    role: str = "user"
) -> dict
```

**Parameters**:
- `username` (str): Unique username
- `password_hash` (str): Bcrypt hashed password
- `role` (str, optional): User role (default: "user")

**Returns**:
- `dict`: Created user with all fields

**Raises**:
- `Exception`: If username already exists or database error

**Example**:
```python
from backend.repositories.user_repository import UserRepository
from backend.services.auth_service import AuthService

# Create repository instance
user_repo = UserRepository(db)

# Hash password
password_hash = AuthService.hash_password("SecurePass123!")

# Create user
user = user_repo.create_user(
    username="john_doe",
    password_hash=password_hash,
    role="user"
)

print(f"User created: {user['id']} - {user['username']}")
```

**Response Structure**:
```python
{
    "id": 123,
    "username": "john_doe",
    "password_hash": "$2b$12$...",
    "role": "user",
    "created_at": datetime(2026, 1, 25, 10, 0, 0),
    "updated_at": datetime(2026, 1, 25, 10, 0, 0),
    "last_login": None,
    "is_locked": False,
    "failed_login_attempts": 0,
    "locked_until": None
}
```

---

### get_user_by_username()

Retrieves a user by username.

**Signature**:
```python
def get_user_by_username(self, username: str) -> Optional[dict]
```

**Parameters**:
- `username` (str): Username to search for

**Returns**:
- `dict`: User data if found
- `None`: If user not found

**Example**:
```python
# Get user by username
user = user_repo.get_user_by_username("john_doe")

if user:
    print(f"Found user: {user['username']}")
    print(f"Role: {user['role']}")
    print(f"Failed attempts: {user['failed_login_attempts']}")
else:
    print("User not found")
```

**Usage in Authentication**:
```python
def authenticate(username: str, password: str):
    """Authenticate user"""
    
    # Get user from database
    user = user_repo.get_user_by_username(username)
    
    if not user:
        raise AuthenticationError("Invalid credentials")
    
    # Verify password
    if not AuthService.verify_password(password, user['password_hash']):
        raise AuthenticationError("Invalid credentials")
    
    return user
```

---

### get_user_by_id()

Retrieves a user by ID.

**Signature**:
```python
def get_user_by_id(self, user_id: int) -> Optional[dict]
```

**Parameters**:
- `user_id` (int): User ID to search for

**Returns**:
- `dict`: User data if found
- `None`: If user not found

**Example**:
```python
# Get user by ID
user = user_repo.get_user_by_id(123)

if user:
    print(f"User: {user['username']}")
    print(f"Last login: {user['last_login']}")
else:
    print("User not found")
```

**Usage in Token Validation**:
```python
def get_current_user(user_id: int):
    """Get current user from token"""
    
    user = user_repo.get_user_by_id(user_id)
    
    if not user:
        raise AuthenticationError("User not found")
    
    if user['is_locked']:
        raise AuthenticationError("Account is locked")
    
    return user
```

---

### update_last_login()

Updates the user's last login timestamp.

**Signature**:
```python
def update_last_login(self, user_id: int) -> None
```

**Parameters**:
- `user_id` (int): User ID to update

**Returns**:
- `None`

**Raises**:
- `Exception`: If database error

**Example**:
```python
# Update last login after successful authentication
user_repo.update_last_login(user['id'])
print("Last login timestamp updated")
```

**Usage in Login Flow**:
```python
def login(username: str, password: str):
    """Login user"""
    
    # Authenticate
    user = authenticate(username, password)
    
    # Update last login
    user_repo.update_last_login(user['id'])
    
    # Generate token
    token = jwt_service.create_access_token(user['id'], user['username'], user['role'])
    
    return {"access_token": token, "user": user}
```

---

### update_failed_attempts()

Updates the user's failed login attempts count.

**Signature**:
```python
def update_failed_attempts(self, user_id: int, attempts: int) -> None
```

**Parameters**:
- `user_id` (int): User ID to update
- `attempts` (int): New failed attempts count

**Returns**:
- `None`

**Raises**:
- `Exception`: If database error

**Example**:
```python
# Increment failed attempts
user = user_repo.get_user_by_username("john_doe")
new_attempts = user['failed_login_attempts'] + 1

user_repo.update_failed_attempts(user['id'], new_attempts)
print(f"Failed attempts: {new_attempts}")
```

**Usage in Failed Login**:
```python
def handle_failed_login(user_id: int, current_attempts: int):
    """Handle failed login attempt"""
    
    new_attempts = current_attempts + 1
    
    # Update failed attempts
    user_repo.update_failed_attempts(user_id, new_attempts)
    
    # Check if should lock account
    if new_attempts >= 5:
        lockout_time = datetime.utcnow() + timedelta(minutes=30)
        user_repo.lock_user(user_id, lockout_time)
        raise AuthenticationError("Account locked due to too many failed attempts")
```

---

### lock_user()

Locks a user account until a specified time.

**Signature**:
```python
def lock_user(self, user_id: int, locked_until: datetime) -> None
```

**Parameters**:
- `user_id` (int): User ID to lock
- `locked_until` (datetime): Timestamp when lock expires

**Returns**:
- `None`

**Raises**:
- `Exception`: If database error

**Example**:
```python
from datetime import datetime, timedelta

# Lock user for 30 minutes
lockout_time = datetime.utcnow() + timedelta(minutes=30)
user_repo.lock_user(user['id'], lockout_time)

print(f"User locked until {lockout_time}")
```

**Usage in Account Locking**:
```python
def lock_account_after_failed_attempts(user_id: int):
    """Lock account after too many failed attempts"""
    
    # Calculate lockout time (30 minutes)
    lockout_time = datetime.utcnow() + timedelta(minutes=30)
    
    # Lock user
    user_repo.lock_user(user_id, lockout_time)
    
    # Log event
    audit_logger.log_authentication(
        event_type="ACCOUNT_LOCKED",
        user_id=user_id,
        status="failure",
        error_message=f"Account locked until {lockout_time}"
    )
```

---

### unlock_user()

Unlocks a user account and resets failed attempts.

**Signature**:
```python
def unlock_user(self, user_id: int) -> None
```

**Parameters**:
- `user_id` (int): User ID to unlock

**Returns**:
- `None`

**Raises**:
- `Exception`: If database error

**Example**:
```python
# Unlock user account
user_repo.unlock_user(user['id'])
print("User account unlocked")
```

**Usage in Admin Operations**:
```python
def admin_unlock_account(admin_user_id: int, target_user_id: int):
    """Admin unlocks a user account"""
    
    # Check admin permissions
    admin = user_repo.get_user_by_id(admin_user_id)
    if admin['role'] != 'admin':
        raise PermissionError("Only admins can unlock accounts")
    
    # Unlock user
    user_repo.unlock_user(target_user_id)
    
    # Log event
    audit_logger.log_data_modification(
        event_type="USER_UNLOCKED",
        user_id=admin_user_id,
        username=admin['username'],
        action="unlock",
        resource_type="user",
        resource_id=str(target_user_id),
        status="success"
    )
```

**Usage in Successful Login**:
```python
def reset_failed_attempts_on_success(user_id: int, failed_attempts: int):
    """Reset failed attempts after successful login"""
    
    if failed_attempts > 0:
        # Unlock and reset
        user_repo.unlock_user(user_id)
```

---

### user_exists()

Checks if a user exists by username.

**Signature**:
```python
def user_exists(self, username: str) -> bool
```

**Parameters**:
- `username` (str): Username to check

**Returns**:
- `bool`: True if user exists, False otherwise

**Example**:
```python
# Check if username is taken
if user_repo.user_exists("john_doe"):
    print("Username already taken")
else:
    print("Username available")
```

**Usage in Registration**:
```python
def register_user(username: str, password: str):
    """Register new user"""
    
    # Check if username exists
    if user_repo.user_exists(username):
        raise ValidationError("Username already taken")
    
    # Validate password
    AuthService.validate_password_strength(password)
    
    # Hash password
    password_hash = AuthService.hash_password(password)
    
    # Create user
    user = user_repo.create_user(username, password_hash, role="user")
    
    return user
```

## Complete Usage Examples

### User Registration Flow

```python
from backend.repositories.user_repository import UserRepository
from backend.services.auth_service import AuthService, PasswordValidationError

def register_user(db: Session, username: str, password: str, role: str = "user"):
    """Complete user registration flow"""
    
    user_repo = UserRepository(db)
    
    # Step 1: Check if username exists
    if user_repo.user_exists(username):
        return {"error": "Username already taken"}, 400
    
    # Step 2: Validate password strength
    try:
        AuthService.validate_password_strength(password)
    except PasswordValidationError as e:
        return {"error": str(e)}, 400
    
    # Step 3: Hash password
    password_hash = AuthService.hash_password(password)
    
    # Step 4: Create user
    try:
        user = user_repo.create_user(username, password_hash, role)
        
        # Remove password hash from response
        user.pop('password_hash')
        
        return {"message": "User created successfully", "user": user}, 201
        
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        return {"error": "Registration failed"}, 500
```

### User Login Flow with Account Locking

```python
from backend.repositories.user_repository import UserRepository
from backend.services.auth_service import AuthService
from backend.services.jwt_service import JWTService
from datetime import datetime, timedelta

def login_user(db: Session, username: str, password: str):
    """Complete login flow with account locking"""
    
    user_repo = UserRepository(db)
    jwt_service = JWTService()
    
    # Step 1: Get user
    user = user_repo.get_user_by_username(username)
    
    if not user:
        return {"error": "Invalid credentials"}, 401
    
    # Step 2: Check if account is locked
    if user['is_locked'] and user['locked_until']:
        if datetime.utcnow() < user['locked_until']:
            return {
                "error": f"Account locked until {user['locked_until'].isoformat()}"
            }, 423
        else:
            # Lock expired, unlock user
            user_repo.unlock_user(user['id'])
            user = user_repo.get_user_by_id(user['id'])
    
    # Step 3: Verify password
    if not AuthService.verify_password(password, user['password_hash']):
        # Increment failed attempts
        new_attempts = user['failed_login_attempts'] + 1
        user_repo.update_failed_attempts(user['id'], new_attempts)
        
        # Lock account if threshold reached
        if new_attempts >= 5:
            lockout_time = datetime.utcnow() + timedelta(minutes=30)
            user_repo.lock_user(user['id'], lockout_time)
            return {
                "error": f"Account locked until {lockout_time.isoformat()}"
            }, 423
        
        return {"error": "Invalid credentials"}, 401
    
    # Step 4: Successful login
    # Reset failed attempts if any
    if user['failed_login_attempts'] > 0:
        user_repo.unlock_user(user['id'])
    
    # Update last login
    user_repo.update_last_login(user['id'])
    
    # Generate token
    token = jwt_service.create_access_token(
        user['id'],
        user['username'],
        user['role']
    )
    
    # Remove sensitive data
    user.pop('password_hash')
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }, 200
```

### Get Current User from Token

```python
def get_current_user(db: Session, user_id: int):
    """Get current user from JWT token"""
    
    user_repo = UserRepository(db)
    
    # Get user
    user = user_repo.get_user_by_id(user_id)
    
    if not user:
        raise AuthenticationError("User not found")
    
    # Check if locked
    if user['is_locked'] and user['locked_until']:
        if datetime.utcnow() < user['locked_until']:
            raise AuthenticationError("Account is locked")
        else:
            # Lock expired, unlock
            user_repo.unlock_user(user_id)
            user = user_repo.get_user_by_id(user_id)
    
    # Remove sensitive data
    user.pop('password_hash')
    
    return user
```

### Admin Unlock User Account

```python
def admin_unlock_user(db: Session, admin_id: int, target_user_id: int):
    """Admin unlocks a user account"""
    
    user_repo = UserRepository(db)
    
    # Verify admin permissions
    admin = user_repo.get_user_by_id(admin_id)
    if not admin or admin['role'] != 'admin':
        return {"error": "Unauthorized"}, 403
    
    # Get target user
    target_user = user_repo.get_user_by_id(target_user_id)
    if not target_user:
        return {"error": "User not found"}, 404
    
    # Unlock user
    user_repo.unlock_user(target_user_id)
    
    return {"message": "User account unlocked successfully"}, 200
```

## Error Handling

### Database Errors

```python
try:
    user = user_repo.create_user("john_doe", password_hash, "user")
except Exception as e:
    if "duplicate key" in str(e).lower():
        return {"error": "Username already exists"}, 400
    else:
        logger.error(f"Database error: {str(e)}")
        return {"error": "Internal server error"}, 500
```

### Transaction Rollback

All write operations automatically rollback on error:

```python
def update_failed_attempts(self, user_id: int, attempts: int) -> None:
    try:
        # Execute update
        self.db.execute(query, params)
        self.db.commit()
    except Exception as e:
        self.db.rollback()  # Automatic rollback
        logger.error(f"Error: {str(e)}")
        raise
```

## Security Considerations

### Password Handling
- **Never Return Password Hash**: Always remove `password_hash` from responses
- **Use Bcrypt**: Always hash passwords with AuthService before storing
- **Validate Strength**: Validate password strength before hashing

### SQL Injection Prevention
- **Parameterized Queries**: All queries use parameterized statements
- **No String Concatenation**: Never concatenate user input into SQL

### Account Locking
- **Brute Force Protection**: Lock after 5 failed attempts
- **Automatic Unlock**: Lock expires after 30 minutes
- **Admin Override**: Admins can manually unlock accounts

## Performance Considerations

### Database Indexes

Ensure these indexes exist for optimal performance:

```sql
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_id ON users(id);
CREATE INDEX idx_users_locked_until ON users(locked_until);
```

### Connection Pooling

Use SQLAlchemy connection pooling:

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    connection_string,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=10
)
```

### Query Optimization

- **Select Specific Columns**: Only select needed columns
- **Use Indexes**: Queries use indexed columns (username, id)
- **Avoid N+1**: Fetch related data in single query when possible

## Testing

### Unit Tests

```python
import pytest
from backend.repositories.user_repository import UserRepository
from backend.services.auth_service import AuthService

@pytest.fixture
def user_repo(db_session):
    """Create UserRepository instance"""
    return UserRepository(db_session)

def test_create_user(user_repo):
    """Test user creation"""
    password_hash = AuthService.hash_password("TestPass123!")
    
    user = user_repo.create_user("testuser", password_hash, "user")
    
    assert user['id'] is not None
    assert user['username'] == "testuser"
    assert user['role'] == "user"
    assert user['failed_login_attempts'] == 0

def test_get_user_by_username(user_repo):
    """Test getting user by username"""
    # Create user
    password_hash = AuthService.hash_password("TestPass123!")
    created_user = user_repo.create_user("testuser", password_hash)
    
    # Get user
    user = user_repo.get_user_by_username("testuser")
    
    assert user is not None
    assert user['id'] == created_user['id']
    assert user['username'] == "testuser"

def test_user_not_found(user_repo):
    """Test getting non-existent user"""
    user = user_repo.get_user_by_username("nonexistent")
    assert user is None

def test_update_failed_attempts(user_repo):
    """Test updating failed attempts"""
    # Create user
    password_hash = AuthService.hash_password("TestPass123!")
    user = user_repo.create_user("testuser", password_hash)
    
    # Update failed attempts
    user_repo.update_failed_attempts(user['id'], 3)
    
    # Verify
    updated_user = user_repo.get_user_by_id(user['id'])
    assert updated_user['failed_login_attempts'] == 3

def test_lock_unlock_user(user_repo):
    """Test locking and unlocking user"""
    from datetime import datetime, timedelta
    
    # Create user
    password_hash = AuthService.hash_password("TestPass123!")
    user = user_repo.create_user("testuser", password_hash)
    
    # Lock user
    lockout_time = datetime.utcnow() + timedelta(minutes=30)
    user_repo.lock_user(user['id'], lockout_time)
    
    # Verify locked
    locked_user = user_repo.get_user_by_id(user['id'])
    assert locked_user['is_locked'] is True
    assert locked_user['locked_until'] is not None
    
    # Unlock user
    user_repo.unlock_user(user['id'])
    
    # Verify unlocked
    unlocked_user = user_repo.get_user_by_id(user['id'])
    assert unlocked_user['is_locked'] is False
    assert unlocked_user['locked_until'] is None
    assert unlocked_user['failed_login_attempts'] == 0

def test_user_exists(user_repo):
    """Test checking user existence"""
    # Create user
    password_hash = AuthService.hash_password("TestPass123!")
    user_repo.create_user("testuser", password_hash)
    
    # Check existence
    assert user_repo.user_exists("testuser") is True
    assert user_repo.user_exists("nonexistent") is False
```

## Related Documentation

- [Auth Service](../services/auth_service.md) - Password hashing and validation
- [Authentication Service](../services/authentication_service.md) - Uses UserRepository for authentication
- [Users Table](../../database/tables/users.md) - Database schema documentation
- [Authentication API](../../api/authentication.md) - API endpoints using UserRepository

## Troubleshooting

### Issue: "duplicate key" error
**Solution**: Username already exists. Check with `user_exists()` before creating.

### Issue: User not found after creation
**Solution**: Ensure transaction is committed. Check database connection.

### Issue: Lock not expiring
**Solution**: Check `locked_until` timestamp. Ensure server time is correct.

### Issue: Failed attempts not resetting
**Solution**: Call `unlock_user()` after successful login to reset attempts.

---

**Last Updated**: 2026-01-25  
**Version**: 1.0  
**Status**: Production Ready
