# JWT Service Documentation

## Overview
The JWT Service handles JSON Web Token (JWT) generation, validation, and payload management for authentication and authorization. It provides stateless authentication using signed tokens with expiration.

## Module
`backend/services/jwt_service.py`

## Dependencies
- `jose` - JWT encoding and decoding
- `pydantic` - Data validation and modeling

## Configuration

### Environment Variables
- `JWT_SECRET_KEY` (required): Secret key for signing tokens

### Token Settings
- **Expiration**: 8 hours
- **Algorithm**: HS256 (HMAC with SHA-256)
- **Payload**: user_id, username, role, exp, iat

---

## Class: TokenPayload

### Purpose
Pydantic model representing the JWT token payload structure.

### Fields

```python
class TokenPayload(BaseModel):
    user_id: int        # User's database ID
    username: str       # User's username
    role: str          # User's role (admin, user)
    exp: int           # Expiration timestamp (Unix epoch)
    iat: int           # Issued at timestamp (Unix epoch)
```

### Example
```python
payload = TokenPayload(
    user_id=1,
    username="admin",
    role="admin",
    exp=1706198400,
    iat=1706169600
)
```

---

## Class: JWTService

### Purpose
Provides static methods for JWT token operations including generation, validation, and inspection.

### Constants

```python
TOKEN_EXPIRATION_HOURS = 8    # Token validity period
ALGORITHM = "HS256"            # Signing algorithm
```

---

## Methods

### generate_jwt_token

```python
@staticmethod
def generate_jwt_token(user_id: int, username: str, role: str) -> str
```

Generates a JWT token for a user with 8-hour expiration.

**Parameters**:
- `user_id` (int): User's database ID
- `username` (str): User's username
- `role` (str): User's role (admin, user, owner, member)

**Returns**:
- `str`: Encoded JWT token

**Raises**:
- `ValueError`: If JWT_SECRET_KEY environment variable is not set

**Token Payload**:
```python
{
    "user_id": 1,
    "username": "admin",
    "role": "admin",
    "exp": 1706198400,  # 8 hours from now
    "iat": 1706169600   # Current timestamp
}
```

**Example**:
```python
token = JWTService.generate_jwt_token(
    user_id=1,
    username="admin",
    role="admin"
)
print(f"Generated token: {token[:20]}...")
# Output: Generated token: eyJ0eXAiOiJKV1QiLCJh...
```

**Token Format**:
```
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6ImFkbWluIiwicm9sZSI6ImFkbWluIiwiZXhwIjoxNzA2MTk4NDAwLCJpYXQiOjE3MDYxNjk2MDB9.signature
```

**Parts**:
1. Header: `{"typ":"JWT","alg":"HS256"}`
2. Payload: `{"user_id":1,"username":"admin","role":"admin","exp":1706198400,"iat":1706169600}`
3. Signature: HMAC-SHA256(header + payload, secret_key)

---

### validate_jwt_token

```python
@staticmethod
def validate_jwt_token(token: str) -> Optional[TokenPayload]
```

Validates and decodes a JWT token, checking signature and expiration.

**Parameters**:
- `token` (str): JWT token string to validate

**Returns**:
- `TokenPayload`: Decoded and validated payload if valid
- `None`: If token is invalid, expired, or malformed

**Validation Checks**:
1. Token signature is valid
2. Token is not expired
3. Payload structure matches TokenPayload model
4. All required fields are present

**Example**:
```python
payload = JWTService.validate_jwt_token(token)

if payload:
    print(f"Valid token for user: {payload.username}")
    print(f"Role: {payload.role}")
    print(f"Expires at: {datetime.fromtimestamp(payload.exp)}")
else:
    print("Invalid or expired token")
```

**Error Handling**:
- Invalid signature → Returns None, logs error
- Expired token → Returns None, logs warning
- Malformed token → Returns None, logs error
- Missing fields → Returns None, logs error

---

### decode_token_without_validation

```python
@staticmethod
def decode_token_without_validation(token: str) -> Optional[Dict[str, Any]]
```

Decodes a token without validating signature or expiration. **Use only for debugging or inspection.**

**Parameters**:
- `token` (str): JWT token string

**Returns**:
- `Dict[str, Any]`: Decoded payload dictionary
- `None`: If token is malformed

**Warning**:
⚠️ This method does NOT validate the token signature or expiration. Never use for authentication or authorization decisions.

**Example**:
```python
# For debugging only
payload = JWTService.decode_token_without_validation(token)
if payload:
    print(f"Token claims: {payload}")
    print(f"User ID: {payload.get('user_id')}")
```

**Use Cases**:
- Debugging token issues
- Inspecting token contents
- Logging token information
- Testing token generation

---

### get_token_expiration

```python
@staticmethod
def get_token_expiration(token: str) -> Optional[datetime]
```

Extracts the expiration time from a token without full validation.

**Parameters**:
- `token` (str): JWT token string

**Returns**:
- `datetime`: Expiration datetime
- `None`: If token is malformed or missing exp claim

**Example**:
```python
expiration = JWTService.get_token_expiration(token)
if expiration:
    print(f"Token expires at: {expiration}")
    time_left = expiration - datetime.utcnow()
    print(f"Time remaining: {time_left}")
```

**Use Cases**:
- Checking token expiration before making request
- Implementing token refresh logic
- Displaying expiration time to user

---

### is_token_expired

```python
@staticmethod
def is_token_expired(token: str) -> bool
```

Checks if a token is expired without full validation.

**Parameters**:
- `token` (str): JWT token string

**Returns**:
- `bool`: True if expired or malformed, False if still valid

**Example**:
```python
if JWTService.is_token_expired(token):
    print("Token has expired, please refresh")
    # Trigger token refresh
else:
    print("Token is still valid")
    # Continue using token
```

**Use Cases**:
- Pre-flight expiration check
- Token refresh decision
- Client-side token management

---

## Token Lifecycle

### Generation Flow

```
User Authentication
   ↓
Generate Payload
   ↓
Set Expiration (8 hours)
   ↓
Set Issued At (now)
   ↓
Encode with Secret Key
   ↓
Return Token String
```

### Validation Flow

```
Receive Token
   ↓
Decode Header
   ↓
Verify Signature
   ↓
Decode Payload
   ↓
Check Expiration
   ↓
Validate Structure
   ↓
Return Payload or None
```

---

## Security Considerations

### Secret Key Management
- **Storage**: Environment variable (JWT_SECRET_KEY)
- **Length**: Minimum 32 characters recommended
- **Rotation**: Rotate periodically (invalidates all tokens)
- **Security**: Never commit to version control

### Token Security
- **Algorithm**: HS256 (symmetric signing)
- **Expiration**: 8 hours (configurable)
- **Signature**: HMAC-SHA256 prevents tampering
- **Payload**: No sensitive data (passwords, secrets)

### Best Practices
- ✅ Use HTTPS for token transmission
- ✅ Store tokens securely (httpOnly cookies)
- ✅ Implement token refresh before expiration
- ✅ Blacklist tokens on logout
- ✅ Use short expiration times
- ❌ Never store passwords in tokens
- ❌ Never log tokens in plain text
- ❌ Never share secret key

---

## Token Structure

### Header
```json
{
  "typ": "JWT",
  "alg": "HS256"
}
```

### Payload
```json
{
  "user_id": 1,
  "username": "admin",
  "role": "admin",
  "exp": 1706198400,
  "iat": 1706169600
}
```

### Signature
```
HMACSHA256(
  base64UrlEncode(header) + "." +
  base64UrlEncode(payload),
  secret_key
)
```

### Complete Token
```
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9
.
eyJ1c2VyX2lkIjoxLCJ1c2VybmFtZSI6ImFkbWluIiwicm9sZSI6ImFkbWluIiwiZXhwIjoxNzA2MTk4NDAwLCJpYXQiOjE3MDYxNjk2MDB9
.
signature_hash
```

---

## Usage Examples

### Generate Token

```python
from services.jwt_service import JWTService

# Generate token for user
token = JWTService.generate_jwt_token(
    user_id=1,
    username="admin",
    role="admin"
)

print(f"Token: {token}")
```

### Validate Token

```python
# Validate token
payload = JWTService.validate_jwt_token(token)

if payload:
    print(f"User ID: {payload.user_id}")
    print(f"Username: {payload.username}")
    print(f"Role: {payload.role}")
    print(f"Expires: {datetime.fromtimestamp(payload.exp)}")
else:
    print("Invalid token")
```

### Check Expiration

```python
# Check if token is expired
if JWTService.is_token_expired(token):
    print("Token expired, refreshing...")
    # Refresh token logic
else:
    print("Token still valid")
```

### Inspect Token (Debugging)

```python
# Decode without validation (debugging only)
payload = JWTService.decode_token_without_validation(token)
print(f"Token payload: {payload}")
```

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| ValueError | JWT_SECRET_KEY not set | Set environment variable |
| JWTError | Invalid signature | Token tampered or wrong key |
| JWTError | Expired token | Refresh token |
| JWTError | Malformed token | Generate new token |

### Error Logging

```python
# Validation errors are logged
logger.error(f"JWT validation error: {str(e)}")
logger.warning("Token has expired")
```

---

## Testing

### Unit Tests

```python
def test_generate_token():
    """Test token generation"""
    token = JWTService.generate_jwt_token(1, "testuser", "user")
    assert isinstance(token, str)
    assert len(token) > 0

def test_validate_token():
    """Test token validation"""
    token = JWTService.generate_jwt_token(1, "testuser", "user")
    payload = JWTService.validate_jwt_token(token)
    assert payload is not None
    assert payload.user_id == 1
    assert payload.username == "testuser"
    assert payload.role == "user"

def test_expired_token():
    """Test expired token rejection"""
    # Create token with past expiration
    # Verify validation returns None

def test_invalid_signature():
    """Test invalid signature rejection"""
    # Tamper with token
    # Verify validation returns None
```

### Property-Based Tests

```python
from hypothesis import given
from hypothesis.strategies import integers, text

@given(
    user_id=integers(min_value=1),
    username=text(min_size=1, max_size=255),
    role=text(min_size=1, max_size=50)
)
def test_token_round_trip(user_id, username, role):
    """Property: Generated tokens should validate correctly"""
    token = JWTService.generate_jwt_token(user_id, username, role)
    payload = JWTService.validate_jwt_token(token)
    
    assert payload is not None
    assert payload.user_id == user_id
    assert payload.username == username
    assert payload.role == role
```

---

## Performance Considerations

### Token Size
- Header: ~20 bytes (base64)
- Payload: ~100-200 bytes (base64)
- Signature: ~43 bytes (base64)
- **Total**: ~200-300 bytes per token

### Validation Performance
- Signature verification: ~0.1ms
- Payload decoding: ~0.01ms
- Expiration check: ~0.001ms
- **Total**: ~0.2ms per validation

### Optimization
- Cache decoded tokens (with expiration)
- Use connection pooling for database
- Implement token refresh before expiration
- Use Redis for token blacklist

---

## Configuration Examples

### Development

```bash
# .env
JWT_SECRET_KEY=dev-secret-key-change-in-production
```

### Production

```bash
# .env
JWT_SECRET_KEY=<strong-random-key-32-chars-minimum>
```

### Generate Secret Key

```python
import secrets

# Generate secure random key
secret_key = secrets.token_urlsafe(32)
print(f"JWT_SECRET_KEY={secret_key}")
```

---

## Related Documentation
- [Authentication Service](./authentication_service.md)
- [Session Cache](./session_cache.md)
- [Authentication API](../../api/authentication.md)
- [Auth Middleware](../middleware/auth_middleware.md)
