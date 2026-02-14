# Design Document: Authentication and Navigation System

## Overview

The Authentication and Navigation System provides secure access control and a modern, minimal user interface for DataMIQ. The system consists of three main components:

1. **Backend Authentication Service**: FastAPI-based service handling user authentication, JWT token management, and RBAC
2. **Frontend UI Library**: Reusable React components with TypeScript, following Snowflake-inspired design principles
3. **Database Schema**: PostgreSQL tables for users, sessions, and audit logs

The design emphasizes security (encrypted passwords, JWT tokens, HTTPS), performance (Redis caching for sessions), and user experience (responsive design, clean UI).

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Login Screen │  │ Main Layout  │  │ UI Library   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │ HTTPS/JWT
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Auth Router  │  │ Auth Service │  │ RBAC Service │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
    ┌──────────────────┐        ┌──────────────────┐
    │  PostgreSQL      │        │  Redis Cache     │
    │  - users         │        │  - sessions      │
    │  - sessions      │        │  - blacklist     │
    │  - audit_logs    │        └──────────────────┘
    └──────────────────┘
```

### Authentication Flow

```
User → Login Form → POST /api/auth/login → Validate Credentials
                                          ↓
                                    Generate JWT Token
                                          ↓
                                    Cache Session (Redis)
                                          ↓
                                    Return Token + User Info
                                          ↓
User ← Store Token (localStorage) ← Response
```

### Request Authorization Flow

```
User Request → Extract JWT from Header → Validate Token
                                       ↓
                                  Check Blacklist (Redis)
                                       ↓
                                  Verify Signature
                                       ↓
                                  Check Expiration
                                       ↓
                                  Extract User Info
                                       ↓
                                  Check RBAC Permissions
                                       ↓
                                  Allow/Deny Request
```

## Components and Interfaces

### Backend Components

#### 1. Authentication Service (`auth_service.py`)

**Responsibilities**:
- User credential validation
- Password hashing and verification
- JWT token generation and validation
- Session management
- Account locking logic

**Key Methods**:
```python
class AuthService:
    def authenticate_user(username: str, password: str) -> Optional[User]
    def generate_jwt_token(user: User) -> str
    def validate_jwt_token(token: str) -> Optional[TokenPayload]
    def hash_password(password: str) -> str
    def verify_password(plain_password: str, hashed_password: str) -> bool
    def lock_account(user_id: int) -> None
    def unlock_account(user_id: int) -> None
    def is_account_locked(user_id: int) -> bool
    def increment_failed_attempts(user_id: int) -> int
    def reset_failed_attempts(user_id: int) -> None
```

**Dependencies**:
- `bcrypt` for password hashing
- `python-jose` for JWT operations
- `UserRepository` for database access
- `SessionCache` for Redis operations

#### 2. RBAC Service (`rbac_service.py`)

**Responsibilities**:
- Role-based permission checking
- Navigation item filtering based on roles
- Endpoint access control

**Key Methods**:
```python
class RBACService:
    def check_permission(user_role: str, required_role: str) -> bool
    def filter_navigation_items(user_role: str, all_items: List[NavItem]) -> List[NavItem]
    def get_user_permissions(user_role: str) -> List[str]
    def has_admin_access(user_role: str) -> bool
```

**Role Hierarchy**:
- `admin`: Full access to all features
- `user`: Access to Dashboard, Connections, Migrations, Jobs (read/write)

#### 3. Authentication Router (`auth_router.py`)

**Endpoints**:

```python
POST /api/auth/login
Request: { "username": str, "password": str }
Response: { "access_token": str, "token_type": "bearer", "user": UserInfo }

POST /api/auth/logout
Headers: Authorization: Bearer <token>
Response: { "message": "Logged out successfully" }

GET /api/auth/me
Headers: Authorization: Bearer <token>
Response: { "id": int, "username": str, "role": str }

POST /api/auth/refresh
Headers: Authorization: Bearer <token>
Response: { "access_token": str, "token_type": "bearer" }
```

#### 4. User Repository (`user_repository.py`)

**Responsibilities**:
- Database operations for users table
- User CRUD operations
- Query optimization

**Key Methods**:
```python
class UserRepository:
    def create_user(username: str, password_hash: str, role: str) -> User
    def get_user_by_username(username: str) -> Optional[User]
    def get_user_by_id(user_id: int) -> Optional[User]
    def update_last_login(user_id: int) -> None
    def update_failed_attempts(user_id: int, attempts: int) -> None
    def lock_user(user_id: int) -> None
    def unlock_user(user_id: int) -> None
```

#### 5. Session Cache (`session_cache.py`)

**Responsibilities**:
- Redis operations for session management
- Token blacklist management
- Cache fallback to database

**Key Methods**:
```python
class SessionCache:
    def cache_session(user_id: int, token: str, ttl: int) -> None
    def get_session(token: str) -> Optional[SessionData]
    def invalidate_session(token: str) -> None
    def is_token_blacklisted(token: str) -> bool
    def add_to_blacklist(token: str, ttl: int) -> None
```

#### 6. Audit Logger (`audit_logger.py`)

**Responsibilities**:
- Log authentication events
- Store audit trail in database
- Structured logging format

**Key Methods**:
```python
class AuditLogger:
    def log_login_attempt(username: str, ip_address: str, success: bool) -> None
    def log_logout(user_id: int, username: str) -> None
    def log_token_validation_failure(token: str, reason: str) -> None
    def log_account_locked(user_id: int, username: str) -> None
    def log_permission_denied(user_id: int, endpoint: str) -> None
```

### Frontend Components

#### 1. UI Library Structure

```
src/components/ui/
├── Button.tsx
├── Input.tsx
├── Card.tsx
├── Avatar.tsx
├── Dropdown.tsx
├── Badge.tsx
├── Alert.tsx
├── Sidebar.tsx
├── Navigation.tsx
├── Header.tsx
└── index.ts
```

#### 2. Design Tokens (`tokens.ts`)

```typescript
export const colors = {
  blue1: '#0066CC',
  blue2: '#0052A3',
  blue3: '#003D7A',
  gold: '#FFB800',
  slate: '#64748B',
  offWhite: '#F8FAFC',
  white: '#FFFFFF',
  gray100: '#F1F5F9',
  gray200: '#E2E8F0',
  gray300: '#CBD5E1',
  gray700: '#334155',
  gray900: '#0F172A',
  error: '#DC2626',
  success: '#16A34A',
  warning: '#F59E0B',
};

export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  lg: '16px',
  xl: '24px',
  '2xl': '32px',
  '3xl': '48px',
  '4xl': '64px',
};

export const typography = {
  fontFamily: {
    sans: '"Google Sans Flex", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    mono: '"Google Sans Code", "Courier New", monospace',
  },
  fontSize: {
    xs: '12px',
    sm: '14px',
    base: '16px',
    lg: '18px',
    xl: '20px',
    '2xl': '24px',
    '3xl': '30px',
    '4xl': '36px',
  },
  fontWeight: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
  },
};

export const borderRadius = {
  sm: '4px',
  md: '8px',
  lg: '12px',
  full: '9999px',
};

export const shadows = {
  sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
};
```

#### 3. Button Component

```typescript
interface ButtonProps {
  variant: 'primary' | 'secondary' | 'outline' | 'ghost';
  size: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  loading?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode;
  onClick?: () => void;
}
```

#### 4. Input Component

```typescript
interface InputProps {
  type: 'text' | 'password' | 'email';
  label?: string;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  disabled?: boolean;
  icon?: React.ReactNode;
}
```

#### 5. Sidebar Component

```typescript
interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
  navigationItems: NavigationItem[];
  userInfo: UserInfo;
  onNavigate: (path: string) => void;
  currentPath: string;
}

interface NavigationItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  path: string;
  requiredRole?: string;
}
```

#### 6. Login Screen Component

```typescript
interface LoginScreenProps {
  onLogin: (username: string, password: string) => Promise<void>;
  error?: string;
  loading?: boolean;
}
```

#### 7. Main Layout Component

```typescript
interface MainLayoutProps {
  children: React.ReactNode;
  userInfo: UserInfo;
  onLogout: () => void;
}
```

### Authentication Context

```typescript
interface AuthContextValue {
  user: UserInfo | null;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
  loading: boolean;
  error: string | null;
}
```

## Data Models

### Database Schema

#### Users Table

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

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_role ON users(role);
```

#### Sessions Table

```sql
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_blacklisted BOOLEAN NOT NULL DEFAULT FALSE,
    ip_address VARCHAR(45),
    user_agent TEXT
);

CREATE INDEX idx_sessions_token_hash ON sessions(token_hash);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_expires_at ON sessions(expires_at);
```

#### Audit Logs Table

```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username VARCHAR(255),
    ip_address VARCHAR(45),
    details JSONB,
    success BOOLEAN,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
```

### Python Models

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class User(BaseModel):
    id: int
    username: str
    password_hash: str
    role: str
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    is_locked: bool
    failed_login_attempts: int
    locked_until: Optional[datetime]

class UserInfo(BaseModel):
    id: int
    username: str
    role: str
    last_login: Optional[datetime]

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserInfo

class TokenPayload(BaseModel):
    user_id: int
    username: str
    role: str
    exp: int
    iat: int

class Session(BaseModel):
    id: int
    user_id: int
    token_hash: str
    created_at: datetime
    expires_at: datetime
    is_blacklisted: bool
    ip_address: Optional[str]
    user_agent: Optional[str]

class AuditLog(BaseModel):
    id: int
    event_type: str
    user_id: Optional[int]
    username: Optional[str]
    ip_address: Optional[str]
    details: dict
    success: bool
    created_at: datetime
```

### TypeScript Models

```typescript
export interface User {
  id: number;
  username: string;
  role: string;
  lastLogin?: string;
}

export interface LoginCredentials {
  username: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface NavigationItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  path: string;
  requiredRole?: string;
  children?: NavigationItem[];
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

Before writing the correctness properties, let me analyze the acceptance criteria for testability:

<parameter name="text">


### Property 1: Password Hashing Round-Trip
*For any* valid password string, hashing the password and then verifying it against the hash should succeed, and verifying any different password against the same hash should fail.
**Validates: Requirements 1.2, 9.1, 9.2**

### Property 2: Setup Script Idempotency
*For any* admin user configuration, running the setup script multiple times should result in exactly one admin user in the database with the correct credentials.
**Validates: Requirements 1.4**

### Property 3: Admin User Authentication After Setup
*For any* admin credentials provided via environment variables, after the setup script completes, authenticating with those credentials should succeed and return an admin role.
**Validates: Requirements 1.5**

### Property 4: Valid Credentials Authentication
*For any* user in the database with valid credentials, submitting correct username and password should result in successful authentication and return a JWT token.
**Validates: Requirements 2.1**

### Property 5: Invalid Credentials Rejection
*For any* username and password combination where either the username doesn't exist or the password is incorrect, authentication should fail with a generic error message.
**Validates: Requirements 2.3**

### Property 6: JWT Token Structure and Expiration
*For any* authenticated user, the generated JWT token should decode to reveal user ID, username, role, and an expiration time exactly 8 hours from creation.
**Validates: Requirements 2.2, 2.4, 3.3**

### Property 7: Session Caching After Authentication
*For any* successful authentication, the user's session data should be retrievable from Redis cache immediately after login.
**Validates: Requirements 2.5**

### Property 8: Token Validation
*For any* valid JWT token that has not expired and is not blacklisted, token validation should succeed and extract correct user information.
**Validates: Requirements 3.1**

### Property 9: Logout Token Blacklisting
*For any* valid JWT token, after logout is called with that token, subsequent requests using the same token should be rejected as blacklisted.
**Validates: Requirements 3.4, 3.5**

### Property 10: Navigation Filtering by Role
*For any* user role and set of navigation items with role requirements, the filtered navigation should only include items where the user's role meets or exceeds the required role.
**Validates: Requirements 4.2**

### Property 11: Endpoint Authorization
*For any* protected endpoint with a required role, requests from users without that role should be rejected with a 403 Forbidden status code.
**Validates: Requirements 4.3, 4.4**

### Property 12: Password Validation Rules
*For any* password string that doesn't meet the requirements (minimum 8 characters, 1 uppercase, 1 lowercase, 1 number), user creation should fail with a validation error.
**Validates: Requirements 9.5**

### Property 13: Audit Logging Completeness
*For any* authentication event (login attempt, logout, token validation failure, account lock), an audit log entry should be created in the database with timestamp, username, and event details.
**Validates: Requirements 11.1, 11.2, 11.3, 11.4**

### Property 14: Successful Login Response Format
*For any* successful authentication, the API response should contain an access_token field, token_type field set to "bearer", and a user object with id, username, and role.
**Validates: Requirements 12.2**

### Property 15: Token Refresh
*For any* valid JWT token that is not expired, calling the refresh endpoint should return a new JWT token with a new 8-hour expiration.
**Validates: Requirements 12.5**

### Property 16: Error Response Status Codes
*For any* authentication error condition (invalid credentials, expired token, missing token, insufficient permissions), the API should return the appropriate HTTP status code (401 for authentication errors, 403 for authorization errors, 400 for bad requests).
**Validates: Requirements 12.6**

## Error Handling

### Backend Error Handling

#### Authentication Errors
- **Invalid Credentials**: Return 401 with generic message "Invalid username or password"
- **Account Locked**: Return 403 with message "Account temporarily locked due to multiple failed login attempts"
- **Expired Token**: Return 401 with message "Token has expired, please log in again"
- **Invalid Token**: Return 401 with message "Invalid authentication token"
- **Blacklisted Token**: Return 401 with message "Token has been invalidated"

#### Authorization Errors
- **Insufficient Permissions**: Return 403 with message "You do not have permission to access this resource"
- **Missing Role**: Return 403 with message "Required role not found"

#### Validation Errors
- **Missing Fields**: Return 400 with message "Required field missing: {field_name}"
- **Invalid Password Format**: Return 400 with message "Password must be at least 8 characters with 1 uppercase, 1 lowercase, and 1 number"
- **Username Already Exists**: Return 409 with message "Username already exists"

#### System Errors
- **Database Connection Error**: Return 503 with message "Service temporarily unavailable"
- **Redis Connection Error**: Log warning, fallback to database, continue operation
- **KMS Error**: Return 500 with message "Encryption service error"

### Frontend Error Handling

#### Network Errors
- Display user-friendly message: "Unable to connect to server. Please check your internet connection."
- Implement retry logic with exponential backoff
- Show retry button for manual retry

#### Authentication Errors
- Display error message below login form
- Clear password field on error
- Focus username field for retry
- Show account locked message with countdown timer

#### Session Expiration
- Detect 401 responses
- Clear stored token
- Redirect to login screen
- Show message: "Your session has expired. Please log in again."

#### Validation Errors
- Display inline error messages below form fields
- Highlight invalid fields with red border
- Prevent form submission until errors are resolved

### Error Logging

All errors should be logged with:
- Timestamp
- Error type and message
- User context (if available)
- Request ID for tracing
- Stack trace (for server errors)
- IP address (for security events)

## Testing Strategy

### Dual Testing Approach

The authentication and navigation system requires both unit tests and property-based tests for comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, UI component rendering, and API endpoint contracts
- **Property tests**: Verify universal properties across all inputs, especially for authentication logic, token handling, and RBAC

### Backend Testing

#### Property-Based Tests (Minimum 100 iterations each)

1. **Password Hashing Round-Trip** (Property 1)
   - Generate random passwords
   - Hash and verify each password
   - Verify different passwords fail verification
   - Tag: **Feature: auth-navigation-system, Property 1: Password hashing round-trip**

2. **Setup Script Idempotency** (Property 2)
   - Run setup script multiple times
   - Verify only one admin user exists
   - Tag: **Feature: auth-navigation-system, Property 2: Setup script idempotency**

3. **Valid Credentials Authentication** (Property 4)
   - Generate random valid users
   - Authenticate with correct credentials
   - Verify JWT token is returned
   - Tag: **Feature: auth-navigation-system, Property 4: Valid credentials authentication**

4. **Invalid Credentials Rejection** (Property 5)
   - Generate random invalid username/password combinations
   - Verify authentication fails
   - Verify error message is generic
   - Tag: **Feature: auth-navigation-system, Property 5: Invalid credentials rejection**

5. **JWT Token Structure** (Property 6)
   - Generate random users
   - Create JWT tokens
   - Decode and verify structure and expiration
   - Tag: **Feature: auth-navigation-system, Property 6: JWT token structure and expiration**

6. **Session Caching** (Property 7)
   - Authenticate random users
   - Verify session data in Redis
   - Tag: **Feature: auth-navigation-system, Property 7: Session caching after authentication**

7. **Token Validation** (Property 8)
   - Generate random valid tokens
   - Validate tokens
   - Verify user info extraction
   - Tag: **Feature: auth-navigation-system, Property 8: Token validation**

8. **Logout Token Blacklisting** (Property 9)
   - Authenticate random users
   - Logout
   - Verify tokens are blacklisted
   - Tag: **Feature: auth-navigation-system, Property 9: Logout token blacklisting**

9. **Navigation Filtering** (Property 10)
   - Generate random user roles and navigation items
   - Filter navigation
   - Verify only authorized items are included
   - Tag: **Feature: auth-navigation-system, Property 10: Navigation filtering by role**

10. **Endpoint Authorization** (Property 11)
    - Generate random users with different roles
    - Attempt to access protected endpoints
    - Verify authorization checks
    - Tag: **Feature: auth-navigation-system, Property 11: Endpoint authorization**

11. **Password Validation** (Property 12)
    - Generate random invalid passwords
    - Verify validation fails
    - Tag: **Feature: auth-navigation-system, Property 12: Password validation rules**

12. **Audit Logging** (Property 13)
    - Perform random authentication events
    - Verify audit logs are created
    - Tag: **Feature: auth-navigation-system, Property 13: Audit logging completeness**

13. **Login Response Format** (Property 14)
    - Authenticate random users
    - Verify response structure
    - Tag: **Feature: auth-navigation-system, Property 14: Successful login response format**

14. **Token Refresh** (Property 15)
    - Generate random valid tokens
    - Refresh tokens
    - Verify new tokens are valid
    - Tag: **Feature: auth-navigation-system, Property 15: Token refresh**

15. **Error Status Codes** (Property 16)
    - Generate random error conditions
    - Verify correct HTTP status codes
    - Tag: **Feature: auth-navigation-system, Property 16: Error response status codes**

#### Unit Tests

1. **Setup Script Tests**
   - Test admin user creation from environment variables
   - Test setup script with missing environment variables
   - Test setup script with existing admin user

2. **Account Locking Tests**
   - Test account locks after 5 failed attempts
   - Test account unlocks after 30 minutes
   - Test failed attempt counter reset on successful login

3. **Token Expiration Tests**
   - Test expired token rejection
   - Test token expiration edge cases (exactly at expiration time)

4. **Redis Fallback Tests**
   - Test session retrieval when Redis is unavailable
   - Test blacklist check when Redis is unavailable
   - Test graceful degradation

5. **API Endpoint Tests**
   - Test POST /api/auth/login with valid credentials
   - Test POST /api/auth/login with invalid credentials
   - Test POST /api/auth/logout
   - Test GET /api/auth/me
   - Test POST /api/auth/refresh

### Frontend Testing

#### Unit Tests

1. **Login Screen Tests**
   - Test login form renders correctly
   - Test username and password inputs are present
   - Test password field masks input
   - Test error message display
   - Test successful login redirects to dashboard

2. **Main Layout Tests**
   - Test layout renders with header, sidebar, and content area
   - Test DataMIQ logo is displayed in header
   - Test sidebar contains navigation items
   - Test user profile section is displayed

3. **Responsive Design Tests**
   - Test sidebar collapses on mobile (< 768px)
   - Test sidebar shows icons only on tablet (768px - 1024px)
   - Test sidebar shows full labels on desktop (> 1024px)

4. **Navigation Tests**
   - Test navigation items are displayed
   - Test clicking navigation item changes route
   - Test active navigation item is highlighted
   - Test admin menu is shown for admin users
   - Test admin menu is hidden for regular users

5. **UI Component Tests**
   - Test Button component with different variants
   - Test Input component with different types
   - Test Avatar component displays correctly
   - Test Dropdown component expands and collapses

6. **Authentication Context Tests**
   - Test login updates authentication state
   - Test logout clears authentication state
   - Test token refresh updates token
   - Test session expiration redirects to login

### Integration Tests

1. **End-to-End Authentication Flow**
   - Test complete login flow from form submission to dashboard
   - Test logout flow from authenticated state to login screen
   - Test session expiration and re-authentication

2. **RBAC Integration**
   - Test admin user can access all features
   - Test regular user cannot access admin features
   - Test navigation filtering based on role

3. **Error Handling Integration**
   - Test network error handling
   - Test authentication error handling
   - Test authorization error handling

### Testing Tools

- **Backend**: pytest, pytest-asyncio, hypothesis (for property-based testing)
- **Frontend**: Jest, React Testing Library, @testing-library/user-event
- **Integration**: Playwright or Cypress for E2E tests
- **API Testing**: httpx for async HTTP testing

### Test Configuration

All property-based tests should be configured to run a minimum of 100 iterations to ensure comprehensive input coverage through randomization.

Example pytest configuration:
```python
# conftest.py
from hypothesis import settings

settings.register_profile("ci", max_examples=100)
settings.load_profile("ci")
```

Example test with Hypothesis:
```python
from hypothesis import given
from hypothesis.strategies import text

@given(password=text(min_size=8, max_size=128))
def test_password_hashing_round_trip(password):
    """Feature: auth-navigation-system, Property 1: Password hashing round-trip"""
    hashed = auth_service.hash_password(password)
    assert auth_service.verify_password(password, hashed)
    assert not auth_service.verify_password(password + "wrong", hashed)
```
