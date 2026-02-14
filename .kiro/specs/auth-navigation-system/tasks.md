# Implementation Plan: Authentication and Navigation System

## Overview

This implementation plan breaks down the authentication and navigation system into discrete, incremental coding tasks. The plan follows a bottom-up approach: database schema → backend services → API endpoints → frontend components → integration.

## Tasks

- [x] 1. Set up database schema and migrations
  - Create Alembic migration for users, sessions, and audit_logs tables
  - Add indexes for performance optimization
  - Create database initialization script
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [ ]* 1.1 Write unit tests for database schema
  - Test table creation and constraints
  - Test indexes are created correctly
  - _Requirements: 10.1-10.6_

- [x] 2. Implement password hashing and validation service
  - [x] 2.1 Create `auth_service.py` with password hashing methods
    - Implement `hash_password()` using bcrypt with cost factor 12
    - Implement `verify_password()` for password verification
    - Implement `validate_password_strength()` for password requirements
    - _Requirements: 9.1, 9.2, 9.5_
  
  - [ ]* 2.2 Write property test for password hashing round-trip
    - **Property 1: Password Hashing Round-Trip**
    - **Validates: Requirements 1.2, 9.1, 9.2**
  
  - [ ]* 2.3 Write property test for password validation rules
    - **Property 12: Password Validation Rules**
    - **Validates: Requirements 9.5**

- [x] 3. Implement JWT token service
  - [x] 3.1 Create JWT token generation and validation methods
    - Implement `generate_jwt_token()` with 8-hour expiration
    - Implement `validate_jwt_token()` with signature and expiration checks
    - Implement token payload structure (user_id, username, role, exp, iat)
    - _Requirements: 2.2, 2.4, 3.1, 3.3_
  
  - [ ]* 3.2 Write property test for JWT token structure
    - **Property 6: JWT Token Structure and Expiration**
    - **Validates: Requirements 2.2, 2.4, 3.3_
  
  - [ ]* 3.3 Write property test for token validation
    - **Property 8: Token Validation**
    - **Validates: Requirements 3.1**

- [x] 4. Implement user repository
  - [x] 4.1 Create `user_repository.py` with database operations
    - Implement `create_user()` method
    - Implement `get_user_by_username()` method
    - Implement `get_user_by_id()` method
    - Implement `update_last_login()` method
    - Implement `update_failed_attempts()` method
    - Implement `lock_user()` and `unlock_user()` methods
    - _Requirements: 1.3, 2.1, 2.6_
  
  - [ ]* 4.2 Write unit tests for user repository
    - Test user creation
    - Test user retrieval
    - Test account locking/unlocking
    - _Requirements: 1.3, 2.1, 2.6_

- [x] 5. Implement Redis session cache
  - [x] 5.1 Create `session_cache.py` with Redis operations
    - Implement `cache_session()` with TTL
    - Implement `get_session()` with database fallback
    - Implement `invalidate_session()` method
    - Implement `is_token_blacklisted()` method
    - Implement `add_to_blacklist()` method
    - Use cache-aside pattern with error handling
    - _Requirements: 2.5, 3.4, 3.5_
  
  - [ ]* 5.2 Write property test for session caching
    - **Property 7: Session Caching After Authentication**
    - **Validates: Requirements 2.5**
  
  - [ ]* 5.3 Write property test for token blacklisting
    - **Property 9: Logout Token Blacklisting**
    - **Validates: Requirements 3.4, 3.5**
  
  - [ ]* 5.4 Write unit tests for Redis fallback
    - Test session retrieval when Redis is unavailable
    - Test graceful degradation
    - _Requirements: 2.5_

- [x] 6. Implement authentication service
  - [x] 6.1 Create `auth_service.py` with authentication logic
    - Implement `authenticate_user()` method
    - Implement account locking logic (5 attempts in 15 minutes)
    - Implement `is_account_locked()` check
    - Implement `increment_failed_attempts()` and `reset_failed_attempts()`
    - _Requirements: 2.1, 2.3, 2.6_
  
  - [ ]* 6.2 Write property test for valid credentials authentication
    - **Property 4: Valid Credentials Authentication**
    - **Validates: Requirements 2.1**
  
  - [ ]* 6.3 Write property test for invalid credentials rejection
    - **Property 5: Invalid Credentials Rejection**
    - **Validates: Requirements 2.3**
  
  - [ ]* 6.4 Write unit test for account locking
    - Test account locks after 5 failed attempts
    - Test account unlocks after 30 minutes
    - _Requirements: 2.6_

- [x] 7. Implement RBAC service
  - [x] 7.1 Create `rbac_service.py` with role-based access control
    - Implement `check_permission()` method
    - Implement `filter_navigation_items()` method
    - Implement `has_admin_access()` method
    - Define role hierarchy (admin, user)
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  
  - [ ]* 7.2 Write property test for navigation filtering
    - **Property 10: Navigation Filtering by Role**
    - **Validates: Requirements 4.2**
  
  - [ ]* 7.3 Write property test for endpoint authorization
    - **Property 11: Endpoint Authorization**
    - **Validates: Requirements 4.3, 4.4**

- [x] 8. Implement audit logging service
  - [x] 8.1 Create `audit_logger.py` with logging methods
    - Implement `log_login_attempt()` method
    - Implement `log_logout()` method
    - Implement `log_token_validation_failure()` method
    - Implement `log_account_locked()` method
    - Implement `log_permission_denied()` method
    - Store logs in database with structured format
    - _Requirements: 11.1, 11.2, 11.3, 11.4_
  
  - [ ]* 8.2 Write property test for audit logging completeness
    - **Property 13: Audit Logging Completeness**
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.4**

- [x] 9. Checkpoint - Ensure backend services tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement authentication API endpoints
  - [x] 10.1 Create `auth_router.py` with FastAPI endpoints
    - Implement POST /api/auth/login endpoint
    - Implement POST /api/auth/logout endpoint
    - Implement GET /api/auth/me endpoint
    - Implement POST /api/auth/refresh endpoint
    - Add request validation and error handling
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_
  
  - [ ]* 10.2 Write property test for login response format
    - **Property 14: Successful Login Response Format**
    - **Validates: Requirements 12.2**
  
  - [ ]* 10.3 Write property test for token refresh
    - **Property 15: Token Refresh**
    - **Validates: Requirements 12.5**
  
  - [ ]* 10.4 Write property test for error status codes
    - **Property 16: Error Response Status Codes**
    - **Validates: Requirements 12.6**
  
  - [ ]* 10.5 Write unit tests for API endpoints
    - Test POST /api/auth/login with valid credentials
    - Test POST /api/auth/login with invalid credentials
    - Test POST /api/auth/logout
    - Test GET /api/auth/me
    - Test POST /api/auth/refresh
    - _Requirements: 12.1-12.6_

- [x] 11. Implement authentication middleware
  - [x] 11.1 Create FastAPI dependency for JWT authentication
    - Implement `get_current_user()` dependency
    - Implement `require_role()` dependency factory
    - Add token extraction from Authorization header
    - Add token validation and blacklist checking
    - _Requirements: 3.1, 3.2, 4.3_
  
  - [ ]* 11.2 Write unit tests for authentication middleware
    - Test token extraction
    - Test expired token handling
    - Test blacklisted token handling
    - _Requirements: 3.1, 3.2_

- [x] 12. Create admin user setup script
  - [x] 12.1 Create `setup.py` script for admin initialization
    - Read ADMIN_USER and ADMIN_PASSWORD from environment or AWS Secrets Manager
    - Use boto3 to call AWS Secrets Manager API (leveraging IAM role attached to instance)
    - If credentials not in Secrets Manager, read from environment variables
    - Hash password and create admin user in database
    - Implement idempotency (skip if admin exists)
    - Validate admin can authenticate after setup
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, Security standards_
  
  - [ ]* 12.2 Write property test for setup script idempotency
    - **Property 2: Setup Script Idempotency**
    - **Validates: Requirements 1.4**
  
  - [ ]* 12.3 Write property test for admin authentication after setup
    - **Property 3: Admin User Authentication After Setup**
    - **Validates: Requirements 1.5**
  
  - [ ]* 12.4 Write unit tests for setup script
    - Test admin creation from environment variables
    - Test setup with missing environment variables
    - Test setup with existing admin user
    - _Requirements: 1.1-1.5_

- [x] 13. Checkpoint - Ensure backend implementation is complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13.5 Implement AWS KMS and Secrets Manager integration
  - [x] 13.5.1 Create `aws_secrets.py` service for AWS integration
    - Use boto3 SDK to call AWS Secrets Manager API (no explicit credentials needed - IAM role attached)
    - Implement `get_secret()` method to retrieve secrets from Secrets Manager
    - Use boto3 SDK to call AWS KMS API for encryption/decryption
    - Implement `encrypt_with_kms()` method using KMS data encryption key
    - Implement `decrypt_with_kms()` method for decrypting connection strings
    - Implement envelope encryption pattern (KMS + data keys)
    - Add error handling for AWS API calls
    - _Requirements: Security standards, Configuration management_
  
  - [ ]* 13.5.2 Write unit tests for AWS integration
    - Test secret retrieval from Secrets Manager
    - Test KMS encryption/decryption
    - Test error handling for AWS API failures
    - Mock boto3 calls for testing
    - _Requirements: Security standards_

- [x] 14. Create design tokens and theme configuration
  - [x] 14.1 Create `src/styles/tokens.ts` with design system values
    - Define color palette (Blue 1, Blue 2, Blue 3, Gold, Slate, Off White)
    - Define spacing scale (4px, 8px, 12px, 16px, 24px, 32px, 48px, 64px)
    - Define typography (Google Sans Flex, Google Sans Code)
    - Define border radius and shadow values
    - _Requirements: 8.4, 8.7_
  
  - [x] 14.2 Create global CSS with font imports and base styles
    - Import Google Sans Flex and Google Sans Code fonts
    - Set up CSS custom properties for design tokens
    - Define base styles and resets
    - _Requirements: 8.5_

- [x] 15. Implement reusable UI components
  - [x] 15.1 Create Button component (`src/components/ui/Button.tsx`)
    - Support variants: primary, secondary, outline, ghost
    - Support sizes: sm, md, lg
    - Support disabled and loading states
    - Apply design tokens for styling
    - _Requirements: 8.1, 8.2_
  
  - [x] 15.2 Create Input component (`src/components/ui/Input.tsx`)
    - Support types: text, password, email
    - Support label, placeholder, error states
    - Support icon integration
    - Apply design tokens for styling
    - _Requirements: 8.1, 8.2_
  
  - [x] 15.3 Create Card component (`src/components/ui/Card.tsx`)
    - Support different padding and shadow variants
    - Apply design tokens for styling
    - _Requirements: 8.1, 8.2_
  
  - [x] 15.4 Create Avatar component (`src/components/ui/Avatar.tsx`)
    - Support image and initials display
    - Support different sizes
    - Apply design tokens for styling
    - _Requirements: 8.1, 8.2_
  
  - [x] 15.5 Create Dropdown component (`src/components/ui/Dropdown.tsx`)
    - Support trigger and menu items
    - Support keyboard navigation
    - Apply design tokens for styling
    - _Requirements: 8.1, 8.2_
  
  - [x] 15.6 Create Badge and Alert components
    - Create Badge component for status indicators
    - Create Alert component for messages
    - Apply design tokens for styling
    - _Requirements: 8.1, 8.2_
  
  - [ ]* 15.7 Write unit tests for UI components
    - Test Button component with different variants
    - Test Input component with different types
    - Test Avatar, Dropdown, Badge, Alert components
    - _Requirements: 8.1_

- [x] 16. Implement navigation components
  - [x] 16.1 Create Sidebar component (`src/components/ui/Sidebar.tsx`)
    - Support collapsed and expanded states
    - Support navigation items with icons (Lucide React)
    - Support user profile section at bottom
    - Apply design tokens for styling
    - _Requirements: 7.1, 7.4, 7.5, 8.3_
  
  - [x] 16.2 Create Navigation component (`src/components/ui/Navigation.tsx`)
    - Render navigation items with active state highlighting
    - Support role-based filtering
    - Support nested items (Administration menu)
    - Handle navigation clicks
    - _Requirements: 7.1, 7.2, 7.3, 7.6, 7.7_
  
  - [x] 16.3 Create Header component (`src/components/ui/Header.tsx`)
    - Display DataMIQ logo on left side
    - Support hamburger menu for mobile
    - Apply design tokens for styling
    - _Requirements: 6.2_
  
  - [ ]* 16.4 Write unit tests for navigation components
    - Test Sidebar collapse/expand
    - Test Navigation item rendering and highlighting
    - Test Header logo display
    - _Requirements: 6.2, 7.1-7.7_

- [x] 17. Implement responsive layout
  - [x] 17.1 Create MainLayout component (`src/components/layout/MainLayout.tsx`)
    - Implement header, sidebar, and content area layout
    - Implement responsive breakpoints (mobile < 768px, tablet 768-1024px, desktop > 1024px)
    - Collapse sidebar on mobile with hamburger menu
    - Show icon-only sidebar on tablet
    - Show full sidebar on desktop
    - _Requirements: 6.1, 6.3, 6.4, 6.5, 6.6, 6.7_
  
  - [ ]* 17.2 Write unit tests for responsive layout
    - Test layout renders with all sections
    - Test sidebar collapse on mobile
    - Test sidebar condensed on tablet
    - Test full sidebar on desktop
    - _Requirements: 6.1-6.7_

- [x] 18. Implement authentication context and hooks
  - [x] 18.1 Create AuthContext (`src/contexts/AuthContext.tsx`)
    - Implement authentication state management
    - Implement login, logout, refreshToken methods
    - Store JWT token in localStorage
    - Provide user information to components
    - Handle token expiration
    - _Requirements: 2.1, 2.2, 3.4_
  
  - [x] 18.2 Create useAuth hook for consuming auth context
    - Provide convenient access to auth state and methods
    - _Requirements: 2.1, 2.2_
  
  - [ ]* 18.3 Write unit tests for AuthContext
    - Test login updates state
    - Test logout clears state
    - Test token refresh
    - Test session expiration handling
    - _Requirements: 2.1, 2.2, 3.4_

- [x] 19. Implement API client service
  - [x] 19.1 Create API client (`src/services/api.ts`)
    - Implement axios instance with base URL
    - Add request interceptor to attach JWT token
    - Add response interceptor for error handling
    - Implement automatic token refresh on 401
    - Implement retry logic with exponential backoff
    - _Requirements: 12.1-12.6_
  
  - [x] 19.2 Create auth API methods (`src/services/authApi.ts`)
    - Implement `login(username, password)` method
    - Implement `logout()` method
    - Implement `getCurrentUser()` method
    - Implement `refreshToken()` method
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [x] 20. Implement login screen
  - [x] 20.1 Create LoginScreen component (`src/pages/LoginScreen.tsx`)
    - Use Input components for username and password
    - Use Button component for login action
    - Display DataMIQ branding
    - Show error messages on login failure
    - Redirect to dashboard on success
    - Center form on screen with minimal design
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [ ]* 20.2 Write unit tests for login screen
    - Test form renders correctly
    - Test password field is masked
    - Test error message display
    - Test successful login redirects
    - _Requirements: 5.1-5.5_

- [x] 21. Implement protected routes and navigation
  - [x] 21.1 Create ProtectedRoute component
    - Check authentication status
    - Redirect to login if not authenticated
    - Verify user role for protected routes
    - _Requirements: 4.3, 4.4_
  
  - [x] 21.2 Set up React Router with routes
    - Define routes: /login, /dashboard, /connections, /migrations, /jobs, /admin
    - Wrap protected routes with ProtectedRoute
    - Implement role-based route protection
    - _Requirements: 4.3, 7.1_
  
  - [ ]* 21.3 Write unit tests for protected routes
    - Test unauthenticated users are redirected
    - Test authenticated users can access routes
    - Test role-based access control
    - _Requirements: 4.3, 4.4_

- [x] 22. Implement main application with layout
  - [x] 22.1 Create App component with routing and layout
    - Wrap app with AuthContext provider
    - Implement routing with React Router
    - Use MainLayout for authenticated routes
    - Define navigation items with role requirements
    - _Requirements: 6.1, 7.1, 7.6_
  
  - [x] 22.2 Create placeholder pages for navigation items
    - Create Dashboard page
    - Create Connections page
    - Create Migrations page
    - Create Jobs page
    - Create Administration page (admin only)
    - _Requirements: 7.1, 7.6_

- [x] 23. Implement error handling and user feedback
  - [x] 23.1 Add error boundary component
    - Catch and display React errors gracefully
    - Log errors for debugging
    - _Requirements: General error handling_
  
  - [x] 23.2 Add toast notification system
    - Display success messages (login, logout)
    - Display error messages (network errors, auth errors)
    - Use Alert component for notifications
    - _Requirements: 5.4_
  
  - [x] 23.3 Handle session expiration
    - Detect 401 responses
    - Clear token and redirect to login
    - Show "Session expired" message
    - _Requirements: 3.2_

- [x] 24. Checkpoint - Ensure frontend implementation is complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 25. Integration and configuration
  - [x] 25.1 Create environment configuration files
    - Create `.env.example` with all required variables
    - Document AWS_REGION, KMS_KEY_ID, SECRET_MANAGER_SECRET_NAME
    - Document database connection settings (will be encrypted using KMS)
    - Document Redis connection settings
    - Document JWT secret key (store in AWS Secrets Manager)
    - Note: Use boto3 SDK to call AWS KMS and Secrets Manager APIs (IAM role attached to instance)
    - _Requirements: 1.1, Configuration management, Security standards_
  
  - [x] 25.2 Create backend main.py with FastAPI app
    - Initialize FastAPI application
    - Register authentication router
    - Add CORS middleware for frontend
    - Add error handlers
    - Configure logging
    - _Requirements: 12.1-12.6_
  
  - [x] 25.3 Create database connection and session management
    - Set up SQLAlchemy engine and session
    - Use boto3 to retrieve encrypted database connection string from AWS Secrets Manager
    - Use boto3 to call AWS KMS API to decrypt connection string (IAM role attached to instance)
    - Implement connection pooling
    - Add database health check endpoint
    - _Requirements: Database architecture, Security standards_
  
  - [x] 25.4 Create Redis connection and client
    - Set up Redis client with connection pooling
    - Implement fallback logic
    - Add Redis health check
    - _Requirements: Caching strategy_

- [ ]* 26. Write integration tests
  - [ ]* 26.1 Write end-to-end authentication flow test
    - Test complete login flow from form to dashboard
    - Test logout flow
    - Test session expiration and re-authentication
    - _Requirements: 2.1, 2.2, 3.4_
  
  - [ ]* 26.2 Write RBAC integration tests
    - Test admin user can access all features
    - Test regular user cannot access admin features
    - Test navigation filtering based on role
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  
  - [ ]* 26.3 Write error handling integration tests
    - Test network error handling
    - Test authentication error handling
    - Test authorization error handling
    - _Requirements: Error handling_

- [x] 27. Final checkpoint - Ensure all tests pass and system is integrated
  - Run all backend tests (unit and property tests)
  - Run all frontend tests
  - Run integration tests
  - Verify setup script works correctly
  - Verify login and navigation work end-to-end
  - Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties with minimum 100 iterations
- Unit tests validate specific examples, edge cases, and UI components
- Checkpoints ensure incremental validation at key milestones
- Backend uses Python + FastAPI with pytest and hypothesis for testing
- Frontend uses React + TypeScript with Jest and React Testing Library
- All configuration is managed via .env files following configuration management standards
- Redis caching implements cache-aside pattern with database fallback
- Security follows AWS best practices with encryption and proper key management
