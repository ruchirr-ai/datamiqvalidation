# Authentication API Documentation

## Overview
The Authentication API provides endpoints for user authentication, session management, and token operations.

**Base URL**: `/api/auth`

**Authentication**: Most endpoints require JWT Bearer token in Authorization header (except login)

---

## Endpoints

### POST /api/auth/login

#### Description
Authenticates a user with username and password. Returns a JWT access token and user information.

#### Authentication
None (public endpoint)

#### Request Body
```json
{
  "username": "string (required, 1-255 characters)",
  "password": "string (required, min 1 character)"
}
```

#### Example Request
```json
{
  "username": "admin",
  "password": "AdminPass123!"
}
```

#### Response (200 OK)
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "role": "admin",
    "organization_id": 1
  }
}
```

#### Error Responses

**400 Bad Request**
```json
{
  "detail": "Username and password are required"
}
```

**401 Unauthorized**
```json
{
  "detail": "Invalid username or password"
}
```

**423 Locked**
```json
{
  "detail": "Account temporarily locked due to multiple failed login attempts. Please try again later."
}
```

**500 Internal Server Error**
```json
{
  "detail": "Internal server error"
}
```

#### Example Usage

**cURL**:
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "AdminPass123!"
  }'
```

**Python**:
```python
import requests

response = requests.post(
    'http://localhost:8000/api/auth/login',
    json={
        'username': 'admin',
        'password': 'AdminPass123!'
    }
)

data = response.json()
token = data['access_token']
```

**JavaScript**:
```javascript
const response = await fetch('http://localhost:8000/api/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: 'admin',
    password: 'AdminPass123!'
  })
});

const data = await response.json();
const token = data.access_token;
```

#### Notes
- Account locks after 5 failed login attempts within 15 minutes
- Account automatically unlocks after 30 minutes
- Password must meet strength requirements (8+ chars, uppercase, lowercase, number)
- Token expires after 8 hours

---

### POST /api/auth/logout

#### Description
Logs out the current user by invalidating their JWT token and adding it to the blacklist.

#### Authentication
Required: JWT Bearer token

#### Request Headers
```
Authorization: Bearer <access_token>
```

#### Request Body
None

#### Response (200 OK)
```json
{
  "message": "Successfully logged out"
}
```

#### Error Responses

**401 Unauthorized**
```json
{
  "detail": "Authorization header missing"
}
```

```json
{
  "detail": "Invalid or expired token"
}
```

**500 Internal Server Error**
```json
{
  "detail": "Internal server error"
}
```

#### Example Usage

**cURL**:
```bash
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

**Python**:
```python
import requests

headers = {
    'Authorization': f'Bearer {token}'
}

response = requests.post(
    'http://localhost:8000/api/auth/logout',
    headers=headers
)
```

**JavaScript**:
```javascript
const response = await fetch('http://localhost:8000/api/auth/logout', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  }
});
```

#### Notes
- Token is added to Redis blacklist with 8-hour TTL
- Session cache is invalidated
- Logout always succeeds even if token is already invalid

---

### GET /api/auth/me

#### Description
Returns information about the currently authenticated user and their accessible workspaces.

#### Authentication
Required: JWT Bearer token

#### Request Headers
```
Authorization: Bearer <access_token>
```

#### Response (200 OK)
```json
{
  "user": {
    "id": 1,
    "username": "admin",
    "role": "admin",
    "organization_id": 1
  },
  "workspaces": [
    {
      "id": 1,
      "name": "dev-workspace",
      "slug": "dev-workspace",
      "role": "owner"
    },
    {
      "id": 2,
      "name": "prod-workspace",
      "slug": "prod-workspace",
      "role": "admin"
    }
  ]
}
```

#### Error Responses

**401 Unauthorized**
```json
{
  "detail": "Authorization header missing"
}
```

```json
{
  "detail": "Invalid or expired token"
}
```

**404 Not Found**
```json
{
  "detail": "User not found"
}
```

**500 Internal Server Error**
```json
{
  "detail": "Internal server error"
}
```

#### Example Usage

**cURL**:
```bash
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

**Python**:
```python
import requests

headers = {
    'Authorization': f'Bearer {token}'
}

response = requests.get(
    'http://localhost:8000/api/auth/me',
    headers=headers
)

data = response.json()
user = data['user']
workspaces = data['workspaces']
```

**JavaScript**:
```javascript
const response = await fetch('http://localhost:8000/api/auth/me', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

const data = await response.json();
const user = data.user;
const workspaces = data.workspaces;
```

#### Notes
- Returns user's current information from database
- Includes all workspaces user has access to
- Workspace role indicates user's permission level in that workspace

---

### POST /api/auth/refresh

#### Description
Refreshes the JWT token, generating a new token with extended expiration. The old token is invalidated.

#### Authentication
Required: JWT Bearer token

#### Request Headers
```
Authorization: Bearer <access_token>
```

#### Request Body
None

#### Response (200 OK)
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

#### Error Responses

**401 Unauthorized**
```json
{
  "detail": "Authorization header missing"
}
```

```json
{
  "detail": "Invalid or expired token"
}
```

**404 Not Found**
```json
{
  "detail": "User not found"
}
```

**500 Internal Server Error**
```json
{
  "detail": "Internal server error"
}
```

#### Example Usage

**cURL**:
```bash
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

**Python**:
```python
import requests

headers = {
    'Authorization': f'Bearer {old_token}'
}

response = requests.post(
    'http://localhost:8000/api/auth/refresh',
    headers=headers
)

data = response.json()
new_token = data['access_token']
```

**JavaScript**:
```javascript
const response = await fetch('http://localhost:8000/api/auth/refresh', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${oldToken}`
  }
});

const data = await response.json();
const newToken = data.access_token;
```

#### Notes
- Old token is invalidated (added to blacklist)
- New token has fresh 8-hour expiration
- User must exist and be active
- Useful for maintaining long sessions

---

### GET /api/auth/health

#### Description
Health check endpoint for the authentication service.

#### Authentication
None (public endpoint)

#### Response (200 OK)
```json
{
  "status": "healthy",
  "service": "auth-service"
}
```

#### Example Usage

**cURL**:
```bash
curl -X GET http://localhost:8000/api/auth/health
```

---

## Authentication Flow

### Login Flow
1. User submits username and password to `/api/auth/login`
2. Server validates credentials
3. Server checks account lock status
4. Server generates JWT token
5. Server caches session in Redis
6. Server returns token and user info
7. Client stores token (localStorage/sessionStorage)
8. Client includes token in subsequent requests

### Authenticated Request Flow
1. Client includes token in Authorization header
2. Server extracts and validates token
3. Server checks token blacklist
4. Server verifies user exists and is active
5. Server processes request
6. Server returns response

### Logout Flow
1. Client sends logout request with token
2. Server adds token to blacklist
3. Server invalidates session cache
4. Server returns success
5. Client removes token from storage

### Token Refresh Flow
1. Client detects token near expiration
2. Client sends refresh request with current token
3. Server validates current token
4. Server generates new token
5. Server invalidates old token
6. Server returns new token
7. Client replaces old token with new token

---

## Security Considerations

### Password Requirements
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number

### Account Locking
- Account locks after 5 failed login attempts
- Lock duration: 30 minutes
- Failed attempts reset on successful login

### Token Security
- Tokens expire after 8 hours
- Tokens are signed with HS256 algorithm
- Tokens include user_id, username, role, exp, iat
- Logged out tokens are blacklisted

### Best Practices
- Always use HTTPS in production
- Store tokens securely (httpOnly cookies recommended)
- Implement token refresh before expiration
- Clear tokens on logout
- Validate tokens on every request
- Use strong JWT secret key

---

## Error Handling

### Common Error Codes
- **400**: Bad request (missing/invalid parameters)
- **401**: Unauthorized (invalid/missing token)
- **403**: Forbidden (insufficient permissions)
- **404**: Not found (user/resource doesn't exist)
- **423**: Locked (account locked)
- **500**: Internal server error

### Error Response Format
All errors follow this format:
```json
{
  "detail": "Error message describing what went wrong"
}
```

---

## Rate Limiting

Currently not implemented. Consider adding:
- Login attempts: 10 per minute per IP
- Token refresh: 5 per minute per user
- General API: 100 per minute per user

---

## Testing

### Test Credentials
Set via environment variables:
- `ADMIN_USER`: Admin username
- `ADMIN_PASSWORD`: Admin password

### Test Endpoints
```bash
# Test login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"AdminPass123!"}'

# Test authenticated endpoint
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <token>"

# Test logout
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer <token>"
```

---

## Changelog

### Version 1.0.0 (2026-01-25)
- Initial implementation
- Login, logout, me, refresh endpoints
- JWT token authentication
- Account locking mechanism
- Session caching with Redis
- Multi-tenant workspace support
