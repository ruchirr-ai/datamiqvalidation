# Documentation Standards

## Overview
All code, APIs, database objects, and features MUST be thoroughly documented. Documentation is not optional - it's a critical part of development.

## Documentation Structure

### Location
All documentation must be stored in the `docs/` folder with the following structure:

```
docs/
├── frontend/          # Frontend documentation
│   ├── components/    # Component documentation
│   ├── pages/         # Page documentation
│   ├── services/      # Service documentation
│   └── contexts/      # Context documentation
├── backend/           # Backend documentation
│   ├── services/      # Service documentation
│   ├── repositories/  # Repository documentation
│   ├── middleware/    # Middleware documentation
│   └── models/        # Model documentation
├── api/               # API documentation
│   ├── authentication.md
│   ├── connections.md
│   ├── migrations.md
│   └── ...
└── database/          # Database documentation
    ├── schema/        # Schema documentation
    ├── tables/        # Table documentation
    ├── views/         # View documentation
    ├── triggers/      # Trigger documentation
    └── migrations/    # Migration documentation
```

## What to Document

### 1. API Endpoints
Every API endpoint MUST be documented with:
- **Endpoint**: HTTP method and path
- **Description**: What the endpoint does
- **Authentication**: Required authentication/authorization
- **Request Parameters**: Query params, path params, headers
- **Request Body**: Schema with examples
- **Response**: Success and error responses with examples
- **Status Codes**: All possible status codes
- **Example Usage**: cURL or code examples

**Template**:
```markdown
## POST /api/auth/login

### Description
Authenticates a user with username and password.

### Authentication
None (public endpoint)

### Request Body
```json
{
  "username": "string (required)",
  "password": "string (required)"
}
```

### Example Request
```json
{
  "username": "admin",
  "password": "AdminPass123!"
}
```

### Response (200 OK)
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "role": "admin",
    "organization_id": 1
  }
}
```

### Error Responses
- **400 Bad Request**: Missing username or password
- **401 Unauthorized**: Invalid credentials
- **423 Locked**: Account locked due to failed attempts

### Example Usage
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"AdminPass123!"}'
```
```

### 2. Database Objects

#### Tables
Every table MUST be documented with:
- **Table Name**: Full table name
- **Description**: Purpose of the table
- **Columns**: All columns with types, constraints, defaults
- **Indexes**: All indexes
- **Foreign Keys**: Relationships to other tables
- **Constraints**: Unique constraints, check constraints
- **Example Data**: Sample rows

**Template**:
```markdown
## Table: users

### Description
Stores user account information for authentication and authorization.

### Columns
| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | SERIAL | NO | AUTO | Primary key |
| username | VARCHAR(255) | NO | - | Unique username |
| password_hash | VARCHAR(255) | NO | - | Bcrypt hashed password |
| role | VARCHAR(50) | NO | 'user' | User role (admin, user) |
| organization_id | INTEGER | YES | NULL | Organization FK |
| failed_login_attempts | INTEGER | NO | 0 | Failed login counter |
| locked_until | TIMESTAMP | YES | NULL | Account lock expiry |
| last_login | TIMESTAMP | YES | NULL | Last successful login |
| created_at | TIMESTAMP | NO | NOW() | Record creation time |
| updated_at | TIMESTAMP | NO | NOW() | Record update time |
| is_active | BOOLEAN | NO | TRUE | Account active status |

### Indexes
- `PRIMARY KEY (id)`
- `UNIQUE INDEX idx_users_username (username)`
- `INDEX idx_users_organization (organization_id)`

### Foreign Keys
- `organization_id` → `organizations(id)` ON DELETE SET NULL

### Constraints
- `CHECK (role IN ('admin', 'user', 'owner'))`
- `CHECK (failed_login_attempts >= 0)`

### Example Data
```sql
INSERT INTO users (username, password_hash, role, organization_id)
VALUES ('admin', '$2b$12$...', 'admin', 1);
```
```

#### Views
Document all views with:
- **View Name**
- **Description**
- **SQL Definition**
- **Columns**
- **Usage Examples**

#### Triggers
Document all triggers with:
- **Trigger Name**
- **Table**
- **Event** (BEFORE/AFTER INSERT/UPDATE/DELETE)
- **Description**
- **SQL Definition**
- **Example**

#### Stored Procedures/Functions
Document all procedures with:
- **Name**
- **Parameters**
- **Return Type**
- **Description**
- **SQL Definition**
- **Usage Examples**

### 3. Backend Services

Every service MUST be documented with:
- **Service Name**
- **Purpose**: What the service does
- **Dependencies**: Other services/repositories it uses
- **Methods**: All public methods with parameters and return types
- **Usage Examples**: Code examples
- **Error Handling**: Exceptions thrown

**Template**:
```markdown
## AuthenticationService

### Purpose
Handles user authentication, login, logout, and session management.

### Dependencies
- `UserRepository`: Database operations for users
- `AuthService`: Password hashing and validation
- `JWTService`: Token generation and validation
- `SessionCache`: Redis session caching

### Methods

#### authenticate_user(username: str, password: str) -> Dict[str, Any]
Authenticates a user with username and password.

**Parameters**:
- `username` (str): User's username
- `password` (str): User's plain text password

**Returns**:
- Dict containing access_token, token_type, and user info

**Raises**:
- `AuthenticationError`: If authentication fails

**Example**:
```python
auth_service = AuthenticationService(user_repo)
result = auth_service.authenticate_user("admin", "AdminPass123!")
print(result["access_token"])
```
```

### 4. Frontend Components

Every component MUST be documented with:
- **Component Name**
- **Purpose**: What the component does
- **Props**: All props with types and descriptions
- **Usage Examples**: Code examples
- **Styling**: CSS classes used
- **Accessibility**: ARIA labels, keyboard navigation

**Template**:
```markdown
## Button Component

### Purpose
Reusable button component with multiple variants and states.

### Props
| Prop | Type | Default | Description |
|------|------|---------|-------------|
| children | ReactNode | required | Button content |
| variant | 'primary' \| 'secondary' \| 'outline' \| 'ghost' | 'primary' | Button style variant |
| size | 'sm' \| 'md' \| 'lg' | 'md' | Button size |
| loading | boolean | false | Show loading spinner |
| disabled | boolean | false | Disable button |
| fullWidth | boolean | false | Full width button |
| onClick | () => void | - | Click handler |

### Usage Example
```tsx
import { Button } from '@/components/ui/Button';

<Button variant="primary" size="lg" onClick={handleClick}>
  Click Me
</Button>

<Button variant="outline" loading={isLoading}>
  Submit
</Button>
```

### Accessibility
- Uses semantic `<button>` element
- Supports keyboard navigation
- Disabled state prevents interaction
- Loading state shows spinner with aria-hidden
```

### 5. Migrations

Every database migration MUST be documented with:
- **Migration ID/Name**
- **Date Created**
- **Description**: What changes are made
- **Up Migration**: SQL to apply changes
- **Down Migration**: SQL to rollback changes
- **Dependencies**: Previous migrations required

## Documentation Requirements

### When to Document
- **Immediately**: Document as you code, not after
- **Before PR**: All code must be documented before pull request
- **On Change**: Update documentation when code changes

### Documentation Quality
- **Clear**: Use simple, clear language
- **Complete**: Cover all parameters, return values, errors
- **Examples**: Always include usage examples
- **Accurate**: Keep documentation in sync with code
- **Formatted**: Use proper markdown formatting

### Code Comments
In addition to external documentation:
- **Docstrings**: All functions/methods must have docstrings
- **Inline Comments**: Complex logic must have inline comments
- **TODO Comments**: Mark incomplete work with TODO
- **Type Hints**: Use type hints in Python and TypeScript

## Documentation Review

### Checklist
Before marking any feature complete, verify:
- [ ] API endpoints documented in `docs/api/`
- [ ] Database objects documented in `docs/database/`
- [ ] Backend services documented in `docs/backend/`
- [ ] Frontend components documented in `docs/frontend/`
- [ ] Code has proper docstrings and comments
- [ ] Examples are tested and working
- [ ] Documentation is formatted correctly

### Maintenance
- Review documentation quarterly
- Update when features change
- Remove documentation for deprecated features
- Keep examples up to date

## Tools

### Recommended Tools
- **API Documentation**: Swagger/OpenAPI for FastAPI
- **Database Documentation**: dbdocs.io or SchemaSpy
- **Code Documentation**: Sphinx for Python, JSDoc for TypeScript
- **Diagrams**: Mermaid for architecture diagrams

### Auto-Generation
Where possible, use auto-generated documentation:
- FastAPI automatically generates OpenAPI docs
- TypeScript interfaces can generate prop tables
- Database schema can be exported to documentation

## Best Practices

### DO
- Write documentation as you code
- Include real, working examples
- Use consistent formatting
- Keep documentation close to code
- Update documentation with code changes
- Review documentation in code reviews

### DON'T
- Leave documentation for later
- Copy-paste without updating
- Use vague descriptions
- Skip error documentation
- Forget to document breaking changes
- Let documentation become stale

## Example Documentation Files

See the `docs/` folder for examples of well-documented:
- API endpoints
- Database tables
- Backend services
- Frontend components

All new code must follow these documentation standards.
