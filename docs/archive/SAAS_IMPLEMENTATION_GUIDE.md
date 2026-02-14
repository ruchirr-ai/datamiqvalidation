# DataMIQ SaaS Implementation Guide

## 🎯 Project Overview

**DataMIQ** is a multi-tenant SaaS platform for database migration with workspace isolation, microservices architecture, and comprehensive security.

## ✅ Completed Implementation (Tasks 1-7)

### Core Infrastructure

#### 1. Database Schema with Multi-Tenancy ✓
- **Users** table with organization_id
- **Organizations** table for tenant isolation
- **Workspaces** table for project grouping (dev, prod, custom)
- **User-Workspaces** mapping with roles (owner, admin, member)
- **Sessions** table for JWT management
- **Audit Logs** table for security events
- All tables indexed for performance

#### 2. Authentication & Security ✓
- **Password Hashing**: Bcrypt with cost factor 12
- **Password Validation**: 8+ chars, uppercase, lowercase, number
- **Account Locking**: 5 failed attempts, 30-minute lockout
- **JWT Tokens**: 8-hour expiration with signature validation
- **Session Caching**: Redis with database fallback
- **Token Blacklist**: Logout invalidation

#### 3. Multi-Tenant Architecture ✓
- **Workspace Middleware**: Validates workspace access
- **Role Hierarchy**: owner > admin > member
- **Permission System**: Granular permissions per role
- **Data Isolation**: All queries filtered by workspace_id
- **Workspace Context**: Injected into all requests

#### 4. Microservices Structure ✓
- **Auth Service** (Port 8001): Authentication & user management
- **Connection Service** (Port 8002): Database connections
- **Assessment Service** (Port 8003): Migration assessments
- **Migration Service** (Port 8004): Projects & tasks
- **Monitoring Service** (Port 8005): Real-time monitoring
- **Validation Service** (Port 8006): Post-migration validation

## 📁 Project Structure

```
backend/
├── services/
│   ├── auth_service.py              # Password hashing & validation
│   ├── authentication_service.py    # Login & authentication logic
│   ├── jwt_service.py               # JWT token management
│   ├── rbac_service.py              # Role-based access control
│   └── session_cache.py             # Redis session caching
├── repositories/
│   └── user_repository.py           # User database operations
├── models/
│   ├── user.py                      # User models
│   └── workspace.py                 # Workspace & organization models
├── shared/
│   ├── middleware/
│   │   └── workspace_middleware.py  # Workspace validation
│   └── database.py                  # Database connection
├── alembic/
│   └── versions/
│       ├── 001_create_auth_tables.py
│       └── 002_add_multi_tenancy.py
├── scripts/
│   ├── start-all-services.sh        # Start all microservices
│   ├── stop-all-services.sh         # Stop all microservices
│   └── init_db.py                   # Database initialization
├── tests/
│   ├── unit/
│   │   ├── test_auth_service.py
│   │   └── test_jwt_service.py
│   └── fixtures/
│       └── sample_payloads.py       # Test data
├── ecosystem.config.js              # PM2 configuration
└── requirements.txt                 # Python dependencies
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Initialize Database
```bash
python scripts/init_db.py
```

### 4. Start All Services (Single Command)
```bash
# Development
./scripts/start-all-services.sh

# Production (PM2)
pm2 start ecosystem.config.js
```

### 5. Individual Service Start
```bash
# Auth Service
uvicorn services.auth.main:app --host 0.0.0.0 --port 8001

# Connection Service
uvicorn services.connections.main:app --host 0.0.0.0 --port 8002

# ... (other services)
```

## 🔐 Security Features

### Multi-Tenant Isolation
```python
# CRITICAL: Always filter by workspace_id
projects = db.query(Project).filter(
    Project.workspace_id == current_workspace_id
).all()

# WRONG - Security risk!
projects = db.query(Project).all()
```

### Workspace Access Validation
```python
from shared.middleware.workspace_middleware import WorkspaceMiddleware

# Validate user has access to workspace
await WorkspaceMiddleware.validate_workspace_access(
    workspace_id=123,
    user_id=456,
    db=db,
    required_role="admin"
)
```

### Role-Based Permissions
```python
from services.rbac_service import RBACService

# Check permission
if RBACService.check_permission(user_role, "project:write"):
    # Allow action
    pass

# Filter navigation by role
nav_items = RBACService.filter_navigation_items(user_role, all_items)
```

## 📊 Database Schema

### Organizations
```sql
CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    subscription_tier VARCHAR(50) DEFAULT 'free',
    max_workspaces INTEGER DEFAULT 5
);
```

### Workspaces
```sql
CREATE TABLE workspaces (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations(id),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    UNIQUE(organization_id, slug)
);
```

### User-Workspace Mapping
```sql
CREATE TABLE user_workspaces (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    workspace_id INTEGER REFERENCES workspaces(id),
    role VARCHAR(50) DEFAULT 'member',
    UNIQUE(user_id, workspace_id)
);
```

## 🧪 Testing

### Run Tests
```bash
# All tests
pytest

# Unit tests only
pytest tests/unit -v

# With coverage
pytest --cov=services --cov=repositories --cov-report=html
```

### Test Structure
- **Unit Tests**: Individual functions with sample payloads
- **Property Tests**: 100 iterations for critical paths
- **Integration Tests**: API endpoints and workflows
- **Sample Payloads**: Centralized in `tests/fixtures/sample_payloads.py`

## 🎨 Design System

### Brand Colors
- **Blue 1**: #003087 (Dark Blue)
- **Blue 2**: #0070E0 (Primary Blue)
- **Blue 3**: #001C64 (Darkest Blue)
- **Gold**: #FFD140 (Accent)
- **Slate**: #001435 (Text)
- **Off White**: #FAF8F5 (Background)

### Typography
- **UI Text**: Google Sans Flex
- **Code**: Google Sans Code

### Icons
- **Library**: Lucide React (outline style)
- **NO EMOJIS**: Use icon packages only

## 📋 Remaining Tasks (8-27)

### Backend (8-13)
- [ ] 8. Audit logging service
- [ ] 9. Checkpoint - backend services tests
- [ ] 10. Authentication API endpoints
- [ ] 11. Authentication middleware
- [ ] 12. Admin user setup script
- [ ] 13. Checkpoint - backend complete
- [ ] 13.5. AWS KMS and Secrets Manager integration

### Frontend (14-24)
- [ ] 14. Design tokens and theme
- [ ] 15. Reusable UI components
- [ ] 16. Navigation components
- [ ] 17. Responsive layout
- [ ] 18. Authentication context
- [ ] 19. API client service
- [ ] 20. Login screen
- [ ] 21. Protected routes
- [ ] 22. Main application
- [ ] 23. Error handling
- [ ] 24. Checkpoint - frontend complete

### Integration (25-27)
- [ ] 25. Integration and configuration
- [ ] 26. Integration tests
- [ ] 27. Final checkpoint

## 🔧 Configuration

### Environment Variables
```bash
# Database
APP_DB_HOST=localhost
APP_DB_PORT=5432
APP_DB_NAME=datamiq
APP_DB_USER=datamiq_user
APP_DB_PASSWORD=secure_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_ENABLED=true

# JWT
JWT_SECRET_KEY=your_secret_key_here

# AWS
AWS_REGION=us-east-1
KMS_KEY_ID=your_kms_key_id
SECRET_MANAGER_SECRET_NAME=datamiq/secrets

# Microservices
AUTH_SERVICE_URL=http://localhost:8001
CONNECTION_SERVICE_URL=http://localhost:8002
ASSESSMENT_SERVICE_URL=http://localhost:8003
MIGRATION_SERVICE_URL=http://localhost:8004
MONITORING_SERVICE_URL=http://localhost:8005
VALIDATION_SERVICE_URL=http://localhost:8006
```

## 🐳 Kubernetes Deployment

### Service Deployment Example
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: auth-service
  template:
    metadata:
      labels:
        app: auth-service
    spec:
      containers:
      - name: auth-service
        image: datamiq/auth-service:latest
        ports:
        - containerPort: 8001
        env:
        - name: SERVICE_NAME
          value: "auth-service"
```

## 📚 Key Documentation

- **Steering Files**: `.kiro/steering/`
  - `saas-architecture.md` - Multi-tenant architecture
  - `security-standards.md` - Security best practices
  - `testing-standards.md` - Testing requirements
  - `aws-deployment.md` - AWS deployment guide
  - `caching-strategy.md` - Redis caching patterns

- **Spec Files**: `.kiro/specs/auth-navigation-system/`
  - `requirements.md` - Feature requirements
  - `design.md` - Technical design
  - `tasks.md` - Implementation tasks

## 🎯 Next Steps

1. **Complete Backend Services** (Tasks 8-13)
   - Implement audit logging
   - Create FastAPI endpoints
   - Add authentication middleware
   - Build admin setup script with AWS integration

2. **Build Frontend** (Tasks 14-24)
   - Set up design system
   - Create UI component library
   - Build login and navigation
   - Implement workspace switching

3. **Integration & Testing** (Tasks 25-27)
   - Configure all services
   - Write integration tests
   - Test end-to-end flows

## 🔗 Useful Commands

```bash
# Database migrations
alembic upgrade head
alembic downgrade -1

# Start services
./scripts/start-all-services.sh

# Stop services
./scripts/stop-all-services.sh

# Run tests
pytest tests/ -v

# Check code coverage
pytest --cov=services --cov-report=html

# PM2 management
pm2 start ecosystem.config.js
pm2 stop all
pm2 logs
pm2 status
```

## 📞 Support

For issues or questions, refer to:
- Implementation Status: `IMPLEMENTATION_STATUS.md`
- Architecture Guide: `.kiro/steering/saas-architecture.md`
- Task List: `.kiro/specs/auth-navigation-system/tasks.md`
