# Auth Service Documentation

## Overview

The `AuthService` is a core security service that handles password hashing, verification, strength validation, and account locking mechanisms. It uses bcrypt for secure password hashing with a cost factor of 12 and implements account lockout protection against brute-force attacks.

**Location**: `backend/services/auth_service.py`

## Purpose

- Hash passwords securely using bcrypt
- Verify passwords against stored hashes
- Validate password strength requirements
- Implement account locking after failed attempts
- Calculate lockout expiration times

## Dependencies

```python
import bcrypt
import re
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging
```

**External Libraries**:
- `bcrypt`: Password hashing library (install: `uv pip install bcrypt`)

## Configuration

### Password Requirements
- **Minimum Length**: 8 characters
- **Uppercase**: At least 1 uppercase letter (A-Z)
- **Lowercase**: At least 1 lowercase letter (a-z)
- **Numbers**: At least 1 digit (0-9)

### Account Locking Settings
- **Max Failed Attempts**: 5 consecutive failures
- **Lockout Duration**: 30 minutes
- **Bcrypt Cost Factor**: 12 rounds

## Class Definition

```python
class AuthService:
    """Service for authentication operations"""
    
    MIN_PASSWORD_LENGTH = 8
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
```

## Methods

### hash_password()

Hashes a plain text password using bcrypt with cost factor 12.

**Signature**:
```python
@staticmethod
def hash_password(password: str) -> str
```

**Parameters**:
- `password` (str): Plain text password to hash

**Returns**:
- `str`: Bcrypt hashed password

**Algorithm**:
1. Convert password to UTF-8 bytes
2. Generate random salt with 12 rounds
3. Hash password with salt using bcrypt
4. Return hash as UTF-8 string

**Example**:
```python
from backend.services.auth_service import AuthService

# Hash a password
plain_password = "MySecurePass123!"
hashed = AuthService.hash_password(plain_password)

print(hashed)
# Output: $2b$12$abcdefghijklmnopqrstuvwxyz...
```

**Security Notes**:
- Uses bcrypt cost factor 12 (recommended for 2026)
- Each hash includes unique random salt
- Hashing takes ~200-300ms (intentional slowdown)
- Resistant to rainbow table attacks

---

### verify_password()

Verifies a plain text password against a bcrypt hash.

**Signature**:
```python
@staticmethod
def verify_password(plain_password: str, hashed_password: str) -> bool
```

**Parameters**:
- `plain_password` (str): Plain text password to verify
- `hashed_password` (str): Bcrypt hash to compare against

**Returns**:
- `bool`: True if password matches, False otherwise

**Error Handling**:
- Returns False on any exception (logged)
- Never raises exceptions

**Example**:
```python
from backend.services.auth_service import AuthService

# Hash and verify
hashed = AuthService.hash_password("MyPass123!")

# Correct password
is_valid = AuthService.verify_password("MyPass123!", hashed)
print(is_valid)  # True

# Wrong password
is_valid = AuthService.verify_password("WrongPass", hashed)
print(is_valid)  # False
```

**Usage in Authentication**:
```python
# In authentication flow
user = user_repository.get_by_username(username)

if not AuthService.verify_password(password, user.password_hash):
    # Increment failed attempts
    user_repository.increment_failed_attempts(user.id)
    raise AuthenticationError("Invalid credentials")
```

---

### validate_password_strength()

Validates that a password meets strength requirements.

**Signature**:
```python
@staticmethod
def validate_password_strength(password: str) -> None
```

**Parameters**:
- `password` (str): Password to validate

**Returns**:
- `None`: Returns nothing if valid

**Raises**:
- `PasswordValidationError`: If password doesn't meet requirements

**Validation Rules**:
1. Minimum 8 characters
2. At least 1 lowercase letter (a-z)
3. At least 1 uppercase letter (A-Z)
4. At least 1 digit (0-9)

**Example**:
```python
from backend.services.auth_service import AuthService, PasswordValidationError

# Valid password
try:
    AuthService.validate_password_strength("ValidPass123")
    print("Password is strong")
except PasswordValidationError as e:
    print(f"Weak password: {e}")

# Too short
try:
    AuthService.validate_password_strength("Short1")
except PasswordValidationError as e:
    print(e)  # "Password must be at least 8 characters long"

# Missing uppercase
try:
    AuthService.validate_password_strength("lowercase123")
except PasswordValidationError as e:
    print(e)  # "Password must contain at least one uppercase letter"

# Missing number
try:
    AuthService.validate_password_strength("NoNumbers")
except PasswordValidationError as e:
    print(e)  # "Password must contain at least one number"
```

**Usage in User Registration**:
```python
# Validate before hashing
try:
    AuthService.validate_password_strength(new_password)
    hashed = AuthService.hash_password(new_password)
    user_repository.create_user(username, hashed, role)
except PasswordValidationError as e:
    return {"error": str(e)}, 400
```

---

### is_account_locked()

Checks if an account is currently locked due to failed login attempts.

**Signature**:
```python
@staticmethod
def is_account_locked(failed_attempts: int, locked_until: Optional[datetime]) -> bool
```

**Parameters**:
- `failed_attempts` (int): Number of consecutive failed login attempts
- `locked_until` (Optional[datetime]): Timestamp when lock expires (None if not locked)

**Returns**:
- `bool`: True if account is locked, False otherwise

**Logic**:
1. If failed_attempts < MAX_FAILED_ATTEMPTS (5): Not locked
2. If locked_until is None: Not locked
3. If current time < locked_until: Locked
4. If current time >= locked_until: Lock expired, not locked

**Example**:
```python
from backend.services.auth_service import AuthService
from datetime import datetime, timedelta

# Account with 5 failed attempts, locked for 10 more minutes
future_lock = datetime.utcnow() + timedelta(minutes=10)
is_locked = AuthService.is_account_locked(5, future_lock)
print(is_locked)  # True

# Account with 5 failed attempts, lock expired 10 minutes ago
past_lock = datetime.utcnow() - timedelta(minutes=10)
is_locked = AuthService.is_account_locked(5, past_lock)
print(is_locked)  # False

# Account with only 3 failed attempts
is_locked = AuthService.is_account_locked(3, None)
print(is_locked)  # False
```

**Usage in Authentication**:
```python
# Check if account is locked before authentication
user = user_repository.get_by_username(username)

if AuthService.is_account_locked(user.failed_login_attempts, user.locked_until):
    raise AuthenticationError("Account is locked. Try again later.")

# Proceed with authentication
if AuthService.verify_password(password, user.password_hash):
    # Reset failed attempts on successful login
    user_repository.reset_failed_attempts(user.id)
    return generate_token(user)
```

---

### calculate_lockout_time()

Calculates when an account lock should expire.

**Signature**:
```python
@staticmethod
def calculate_lockout_time() -> datetime
```

**Parameters**:
- None

**Returns**:
- `datetime`: UTC timestamp when lock expires (current time + 30 minutes)

**Example**:
```python
from backend.services.auth_service import AuthService

# Calculate lockout expiration
lockout_time = AuthService.calculate_lockout_time()
print(lockout_time)
# Output: 2026-01-25 11:00:00 (30 minutes from now)

# Use in failed login handling
if user.failed_login_attempts >= AuthService.MAX_FAILED_ATTEMPTS:
    lockout_time = AuthService.calculate_lockout_time()
    user_repository.lock_account(user.id, lockout_time)
```

**Usage in Failed Login Handler**:
```python
# After failed authentication
user.failed_login_attempts += 1

if user.failed_login_attempts >= AuthService.MAX_FAILED_ATTEMPTS:
    # Lock the account
    lockout_time = AuthService.calculate_lockout_time()
    user_repository.update_user(
        user.id,
        failed_login_attempts=user.failed_login_attempts,
        locked_until=lockout_time
    )
    raise AuthenticationError(
        f"Account locked due to too many failed attempts. "
        f"Try again after {lockout_time.strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )
```

## Exceptions

### PasswordValidationError

Raised when a password doesn't meet strength requirements.

**Usage**:
```python
from backend.services.auth_service import PasswordValidationError

try:
    AuthService.validate_password_strength("weak")
except PasswordValidationError as e:
    print(f"Password validation failed: {e}")
```

### AuthenticationError

Raised when authentication fails (defined but not raised by AuthService directly).

**Usage**:
```python
from backend.services.auth_service import AuthenticationError

if not AuthService.verify_password(password, user.password_hash):
    raise AuthenticationError("Invalid credentials")
```

## Complete Usage Example

### User Registration Flow

```python
from backend.services.auth_service import AuthService, PasswordValidationError
from backend.repositories.user_repository import UserRepository

def register_user(username: str, password: str, role: str = "user"):
    """Register a new user with password validation"""
    
    # Step 1: Validate password strength
    try:
        AuthService.validate_password_strength(password)
    except PasswordValidationError as e:
        return {"error": str(e)}, 400
    
    # Step 2: Hash the password
    password_hash = AuthService.hash_password(password)
    
    # Step 3: Create user in database
    user_repo = UserRepository()
    user = user_repo.create_user(
        username=username,
        password_hash=password_hash,
        role=role
    )
    
    return {"message": "User created successfully", "user_id": user.id}, 201
```

### User Login Flow with Account Locking

```python
from backend.services.auth_service import AuthService, AuthenticationError
from backend.repositories.user_repository import UserRepository
from backend.services.jwt_service import JWTService

def login_user(username: str, password: str):
    """Authenticate user with account locking protection"""
    
    user_repo = UserRepository()
    user = user_repo.get_by_username(username)
    
    if not user:
        raise AuthenticationError("Invalid credentials")
    
    # Step 1: Check if account is locked
    if AuthService.is_account_locked(user.failed_login_attempts, user.locked_until):
        raise AuthenticationError(
            f"Account is locked until {user.locked_until.strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )
    
    # Step 2: Verify password
    if not AuthService.verify_password(password, user.password_hash):
        # Increment failed attempts
        user.failed_login_attempts += 1
        
        # Lock account if threshold reached
        if user.failed_login_attempts >= AuthService.MAX_FAILED_ATTEMPTS:
            lockout_time = AuthService.calculate_lockout_time()
            user_repo.update_user(
                user.id,
                failed_login_attempts=user.failed_login_attempts,
                locked_until=lockout_time
            )
            raise AuthenticationError(
                f"Account locked due to too many failed attempts. "
                f"Try again after {lockout_time.strftime('%Y-%m-%d %H:%M:%S')} UTC"
            )
        else:
            user_repo.update_user(
                user.id,
                failed_login_attempts=user.failed_login_attempts
            )
            raise AuthenticationError("Invalid credentials")
    
    # Step 3: Successful authentication - reset failed attempts
    if user.failed_login_attempts > 0:
        user_repo.reset_failed_attempts(user.id)
    
    # Step 4: Generate JWT token
    jwt_service = JWTService()
    token = jwt_service.create_access_token(user.id, user.username, user.role)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role
        }
    }
```

### Password Change Flow

```python
from backend.services.auth_service import AuthService, PasswordValidationError

def change_password(user_id: int, old_password: str, new_password: str):
    """Change user password with validation"""
    
    user_repo = UserRepository()
    user = user_repo.get_by_id(user_id)
    
    # Step 1: Verify old password
    if not AuthService.verify_password(old_password, user.password_hash):
        raise AuthenticationError("Current password is incorrect")
    
    # Step 2: Validate new password strength
    try:
        AuthService.validate_password_strength(new_password)
    except PasswordValidationError as e:
        return {"error": str(e)}, 400
    
    # Step 3: Hash new password
    new_hash = AuthService.hash_password(new_password)
    
    # Step 4: Update in database
    user_repo.update_user(user_id, password_hash=new_hash)
    
    return {"message": "Password changed successfully"}, 200
```

## Security Considerations

### Password Hashing
- **Bcrypt Cost Factor 12**: Provides strong protection against brute-force attacks
- **Unique Salt**: Each password gets a unique random salt
- **Slow by Design**: ~200-300ms per hash prevents rapid brute-force attempts
- **Future-Proof**: Cost factor can be increased as hardware improves

### Account Locking
- **Brute-Force Protection**: Locks account after 5 failed attempts
- **Temporary Lock**: 30-minute lockout prevents extended attacks
- **Automatic Unlock**: Lock expires automatically after duration
- **Failed Attempt Tracking**: Resets on successful login

### Password Requirements
- **Minimum Complexity**: Enforces strong passwords
- **Multiple Character Types**: Requires mix of upper, lower, and digits
- **Reasonable Length**: 8 characters minimum balances security and usability
- **Clear Error Messages**: Helps users create compliant passwords

### Best Practices
1. **Never Log Passwords**: Never log plain text or hashed passwords
2. **Constant-Time Comparison**: Bcrypt uses constant-time comparison
3. **Secure Random**: Bcrypt uses cryptographically secure random for salts
4. **No Password Hints**: Never store or return password hints
5. **Rate Limiting**: Combine with API rate limiting for additional protection

## Performance Considerations

### Hashing Performance
- **Time**: ~200-300ms per hash (intentional)
- **CPU Intensive**: Uses significant CPU during hashing
- **Async Recommended**: Use async/await in FastAPI to prevent blocking

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

async def hash_password_async(password: str) -> str:
    """Hash password asynchronously to avoid blocking"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        executor,
        AuthService.hash_password,
        password
    )
```

### Verification Performance
- **Time**: ~200-300ms per verification (intentional)
- **Sequential**: Verify passwords sequentially, not in parallel
- **Caching**: Never cache password verification results

## Testing

### Unit Tests

```python
import pytest
from backend.services.auth_service import AuthService, PasswordValidationError

def test_hash_password():
    """Test password hashing"""
    password = "TestPass123!"
    hashed = AuthService.hash_password(password)
    
    assert isinstance(hashed, str)
    assert hashed.startswith("$2b$12$")
    assert len(hashed) == 60

def test_verify_password_correct():
    """Test password verification with correct password"""
    password = "TestPass123!"
    hashed = AuthService.hash_password(password)
    
    assert AuthService.verify_password(password, hashed) is True

def test_verify_password_incorrect():
    """Test password verification with incorrect password"""
    password = "TestPass123!"
    hashed = AuthService.hash_password(password)
    
    assert AuthService.verify_password("WrongPass", hashed) is False

def test_validate_password_strength_valid():
    """Test password strength validation with valid password"""
    # Should not raise exception
    AuthService.validate_password_strength("ValidPass123")

def test_validate_password_strength_too_short():
    """Test password strength validation with short password"""
    with pytest.raises(PasswordValidationError) as exc:
        AuthService.validate_password_strength("Short1")
    assert "at least 8 characters" in str(exc.value)

def test_validate_password_strength_no_uppercase():
    """Test password strength validation without uppercase"""
    with pytest.raises(PasswordValidationError) as exc:
        AuthService.validate_password_strength("lowercase123")
    assert "uppercase letter" in str(exc.value)

def test_validate_password_strength_no_number():
    """Test password strength validation without number"""
    with pytest.raises(PasswordValidationError) as exc:
        AuthService.validate_password_strength("NoNumbers")
    assert "number" in str(exc.value)

def test_is_account_locked_not_locked():
    """Test account lock check when not locked"""
    assert AuthService.is_account_locked(3, None) is False

def test_is_account_locked_locked():
    """Test account lock check when locked"""
    from datetime import datetime, timedelta
    future = datetime.utcnow() + timedelta(minutes=10)
    assert AuthService.is_account_locked(5, future) is True

def test_is_account_locked_expired():
    """Test account lock check when lock expired"""
    from datetime import datetime, timedelta
    past = datetime.utcnow() - timedelta(minutes=10)
    assert AuthService.is_account_locked(5, past) is False

def test_calculate_lockout_time():
    """Test lockout time calculation"""
    from datetime import datetime, timedelta
    lockout = AuthService.calculate_lockout_time()
    expected = datetime.utcnow() + timedelta(minutes=30)
    
    # Allow 1 second tolerance
    assert abs((lockout - expected).total_seconds()) < 1
```

## Related Documentation

- [Authentication Service](./authentication_service.md) - Uses AuthService for password operations
- [User Repository](../repositories/user_repository.md) - Stores hashed passwords and failed attempts
- [JWT Service](./jwt_service.md) - Generates tokens after successful authentication
- [Authentication API](../../api/authentication.md) - API endpoints using AuthService
- [Security Standards](../../../.kiro/steering/security-standards.md) - Security guidelines

## Configuration

### Environment Variables

No environment variables required. All configuration is hardcoded as constants:

```python
MIN_PASSWORD_LENGTH = 8
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30
```

To customize, modify the class constants in `auth_service.py`.

## Troubleshooting

### Issue: Hashing is too slow
**Solution**: This is intentional. Bcrypt cost factor 12 takes ~200-300ms. Use async execution to prevent blocking.

### Issue: Account locked unexpectedly
**Solution**: Check `failed_login_attempts` and `locked_until` in database. Lock expires after 30 minutes.

### Issue: Password validation too strict
**Solution**: Modify `MIN_PASSWORD_LENGTH` and `PASSWORD_PATTERN` constants. Ensure changes meet security requirements.

### Issue: Bcrypt import error
**Solution**: Install bcrypt: `uv pip install bcrypt`

---

**Last Updated**: 2026-01-25  
**Version**: 1.0  
**Status**: Production Ready
