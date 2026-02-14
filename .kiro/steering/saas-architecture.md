---
inclusion: always
---

# SaaS Multi-Tenant Architecture

## Overview

DataMIQ is a SaaS platform that allows multiple organizations to use the product independently. Each organization operates within isolated workspaces with proper data segregation and security guardrails.

## Multi-Tenancy Model

### Workspace Concept

**Workspace**: A logical container for an organization's migration projects, connections, and resources.

- Each organization has one or more workspaces
- Workspaces provide complete data isolation
- Users belong to workspaces with specific roles
- All resources (connections, projects, jobs) are scoped to workspaces

### Workspace Examples
- `dev-workspace` - Development environment migrations
- `prod-workspace` - Production environment migrations
- `my-data-migration` - Custom named workspace
- `customer-onboarding` - Specific project workspace

### Data Isolation

**CRITICAL**: All database queries MUST include workspace_id filter to ensure data isolation.

```python
# CORRECT - Always filter by workspace_id
projects = db.query(Project).filter(
    Project.workspace_id == current_workspace_id
).all()

# WRONG - Never query without workspace filter
projects = db.query(Project).all()  # Security risk!
```

### Workspace Hierarchy

```
Organization
  └── Workspaces (multiple)
       ├── Users (with roles)
       ├── Database Connections
       ├── Migration Projects
       ├── Migration Jobs
       ├── Assessment Reports
       └── Validation Results
```

## Database Schema for Multi-Tenancy

### Core Tables

#### Organizations Table
```sql
CREATE TABLE organizations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    subscription_tier VARCHAR(50) NOT NULL DEFAULT 'free',
    max_workspaces INTEGER NOT NULL DEFAULT 5
);
```

#### Workspaces Table
```sql
CREATE TABLE workspaces (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE(organization_id, slug)
);

CREATE INDEX idx_workspaces_org_id ON workspaces(organization_id);
CREATE INDEX idx_workspaces_slug ON workspaces(slug);
```

#### User-Workspace Mapping
```sql
CREATE TABLE user_workspaces (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'member',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, workspace_id)
);

CREATE INDEX idx_user_workspaces_user_id ON user_workspaces(user_id);
CREATE INDEX idx_user_workspaces_workspace_id ON user_workspaces(workspace_id);
```

### Resource Tables (All Scoped to Workspace)

All resource tables MUST include `workspace_id`:

```sql
-- Example: Migration Projects
CREATE TABLE migration_projects (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    -- other fields...
    CONSTRAINT unique_project_per_workspace UNIQUE(workspace_id, name)
);

CREATE INDEX idx_projects_workspace_id ON migration_projects(workspace_id);
```

## Microservices Architecture

### Service Decomposition

DataMIQ backend is split into multiple microservices for scalability and maintainability:

#### 1. Auth Service
**Responsibility**: Authentication, authorization, user management
**Port**: 8001
**Endpoints**: `/api/auth/*`
**Database**: Users, sessions, audit_logs, organizations, workspaces

#### 2. Connection Service
**Responsibility**: Database connection management
**Port**: 8002
**Endpoints**: `/api/connections/*`
**Database**: Connections, connection_credentials

#### 3. Assessment Service
**Responsibility**: Migration assessment and reporting
**Port**: 8003
**Endpoints**: `/api/assessments/*`
**Database**: Assessments, assessment_reports

#### 4. Migration Service
**Responsibility**: Migration project and task management
**Port**: 8004
**Endpoints**: `/api/migrations/*`, `/api/projects/*`
**Database**: Migration_projects, migration_tasks

#### 5. Monitoring Service
**Responsibility**: Real-time monitoring and metrics
**Port**: 8005
**Endpoints**: `/api/monitoring/*`
**Database**: Monitoring_metrics, monitoring_events

#### 6. Validation Service
**Responsibility**: Post-migration validation
**Port**: 8006
**Endpoints**: `/api/validation/*`
**Database**: Validation_results, validation_rules

### Service Communication

- **Synchronous**: REST APIs between services
- **Asynchronous**: Message queue (RabbitMQ/AWS SQS) for long-running operations
- **Service Discovery**: Kubernetes service discovery
- **API Gateway**: Single entry point for all services

### Shared Components

- **Database**: Single PostgreSQL instance with logical separation
- **Redis**: Shared Redis cluster for caching
- **AWS Services**: Shared KMS, Secrets Manager, S3

## Deployment Architecture

### Kubernetes Deployment

Each microservice runs as a separate Kubernetes deployment:

```yaml
# Example: Auth Service Deployment
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
        - name: SERVICE_PORT
          value: "8001"
```

### Service Start Commands

#### Development (Single Command for All Services)
```bash
# Start all services with one command
./scripts/start-all-services.sh
```

#### Production (Individual Services)
```bash
# Auth Service
uvicorn services.auth.main:app --host 0.0.0.0 --port 8001

# Connection Service
uvicorn services.connections.main:app --host 0.0.0.0 --port 8002

# Assessment Service
uvicorn services.assessment.main:app --host 0.0.0.0 --port 8003

# Migration Service
uvicorn services.migration.main:app --host 0.0.0.0 --port 8004

# Monitoring Service
uvicorn services.monitoring.main:app --host 0.0.0.0 --port 8005

# Validation Service
uvicorn services.validation.main:app --host 0.0.0.0 --port 8006
```

#### EC2 Deployment (Process Manager)
```bash
# Using PM2 or Supervisor to manage all services
pm2 start ecosystem.config.js
```

### Directory Structure

```
backend/
  services/
    auth/
      main.py
      routers/
      services/
      repositories/
    connections/
      main.py
      routers/
      services/
      repositories/
    assessment/
      main.py
      routers/
      services/
      repositories/
    migration/
      main.py
      routers/
      services/
      repositories/
    monitoring/
      main.py
      routers/
      services/
      repositories/
    validation/
      main.py
      routers/
      services/
      repositories/
  shared/
    database.py
    redis_client.py
    aws_client.py
    models/
    utils/
  scripts/
    start-all-services.sh
    stop-all-services.sh
  tests/
  requirements.txt
  ecosystem.config.js  # PM2 configuration
```

## Security Guardrails

### Workspace Isolation

1. **Database Level**: All queries filtered by workspace_id
2. **API Level**: Middleware validates workspace access
3. **Cache Level**: Redis keys include workspace_id
4. **File Storage**: S3 paths include workspace_id

### Access Control

```python
# Middleware to validate workspace access
async def validate_workspace_access(
    workspace_id: int,
    user_id: int,
    required_role: str = "member"
) -> bool:
    # Check if user belongs to workspace
    # Check if user has required role in workspace
    # Return True/False
```

### Rate Limiting

- Per organization rate limits
- Per workspace rate limits
- Per user rate limits

### Resource Quotas

- Max workspaces per organization
- Max projects per workspace
- Max connections per workspace
- Max concurrent migrations per workspace

## API Gateway Pattern

### Single Entry Point

```
Client → API Gateway (Port 8000) → Microservices
```

### Gateway Responsibilities

- Authentication/Authorization
- Request routing
- Rate limiting
- Request/Response transformation
- Logging and monitoring

### Gateway Configuration

```python
# API Gateway routes
routes = {
    "/api/auth/*": "http://auth-service:8001",
    "/api/connections/*": "http://connection-service:8002",
    "/api/assessments/*": "http://assessment-service:8003",
    "/api/migrations/*": "http://migration-service:8004",
    "/api/monitoring/*": "http://monitoring-service:8005",
    "/api/validation/*": "http://validation-service:8006",
}
```

## Workspace Context

### Request Context

Every API request includes workspace context:

```python
class WorkspaceContext:
    workspace_id: int
    workspace_slug: str
    organization_id: int
    user_id: int
    user_role: str
```

### Workspace Switching

Users can switch between workspaces they have access to:

```python
POST /api/auth/switch-workspace
{
    "workspace_id": 123
}
```

## Monitoring & Observability

### Service Health Checks

Each service exposes health check endpoint:
```
GET /health
GET /ready
```

### Distributed Tracing

- Use correlation IDs across services
- Log workspace_id in all logs
- Track request flow across services

### Metrics

- Per-service metrics
- Per-workspace metrics
- Per-organization metrics

## Backup & Disaster Recovery

### Workspace-Level Backups

- Backup data per workspace
- Restore individual workspaces
- Export workspace data

### Multi-Region Deployment

- Deploy across multiple AWS regions
- Workspace data replication
- Failover mechanisms

## Compliance & Audit

### Audit Logging

- Log all workspace operations
- Log cross-workspace access attempts
- Log admin operations
- Retain logs per compliance requirements

### Data Residency

- Support data residency requirements
- Store workspace data in specific regions
- Comply with GDPR, CCPA, etc.

## Best Practices

### DO
- Always filter by workspace_id
- Validate workspace access in middleware
- Use workspace context in all operations
- Implement proper data isolation
- Test cross-workspace access prevention
- Monitor workspace resource usage

### DON'T
- Query across workspaces without authorization
- Share resources between workspaces
- Hardcode workspace IDs
- Skip workspace validation
- Allow direct database access
- Mix workspace data in cache keys
