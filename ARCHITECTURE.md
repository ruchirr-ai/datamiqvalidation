# DataMIQ Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Browser                             │
│                    http://localhost:3000                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS/HTTP
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Frontend (React)                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Login Screen │  │ Dashboard    │  │ UI Library   │          │
│  │              │  │ Pages        │  │ Components   │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ AuthContext (JWT Token Management)                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ REST API (JSON)
                              │ Authorization: Bearer <token>
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI)                              │
│                http://localhost:8000                             │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ CORS Middleware                                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Auth Router (/api/auth/*)                                 │  │
│  │  - POST /login                                            │  │
│  │  - POST /logout                                           │  │
│  │  - GET /me                                                │  │
│  │  - POST /refresh                                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Auth Middleware (JWT Validation)                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Services Layer                                            │  │
│  │  ┌────────────────┐  ┌────────────────┐                  │  │
│  │  │ Authentication │  │ JWT Service    │                  │  │
│  │  │ Service        │  │                │                  │  │
│  │  └────────────────┘  └────────────────┘                  │  │
│  │  ┌────────────────┐  ┌────────────────┐                  │  │
│  │  │ RBAC Service   │  │ Audit Logger   │                  │  │
│  │  │                │  │                │                  │  │
│  │  └────────────────┘  └────────────────┘                  │  │
│  │  ┌────────────────┐  ┌────────────────┐                  │  │
│  │  │ Session Cache  │  │ AWS Secrets    │                  │  │
│  │  │                │  │                │                  │  │
│  │  └────────────────┘  └────────────────┘                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Repository Layer                                          │  │
│  │  ┌────────────────┐                                       │  │
│  │  │ User Repository│                                       │  │
│  │  │                │                                       │  │
│  │  └────────────────┘                                       │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                    │                        │
                    │                        │
                    ▼                        ▼
    ┌───────────────────────┐   ┌───────────────────────┐
    │   PostgreSQL          │   │   Redis Cache         │
    │   34.226.150.199:5432 │   │   34.226.150.199:6379 │
    │                       │   │                       │
    │   Tables:             │   │   Keys:               │
    │   - users             │   │   - session:{token}   │
    │   - sessions          │   │   - blacklist:{token} │
    │   - audit_logs        │   │                       │
    │   - organizations     │   │   Fallback:           │
    │   - workspaces        │   │   → PostgreSQL        │
    │   - user_workspaces   │   │                       │
    └───────────────────────┘   └───────────────────────┘
```

---

## Authentication Flow

```
┌──────┐                                                    ┌──────────┐
│ User │                                                    │ Backend  │
└──┬───┘                                                    └────┬─────┘
   │                                                             │
   │ 1. Enter username/password                                 │
   ├────────────────────────────────────────────────────────────>
   │                                                             │
   │                    2. Validate credentials                 │
   │                       (check database)                     │
   │                                                             │
   │                    3. Check account lock                   │
   │                                                             │
   │                    4. Verify password hash                 │
   │                       (bcrypt)                             │
   │                                                             │
   │                    5. Generate JWT token                   │
   │                       (8-hour expiration)                  │
   │                                                             │
   │                    6. Cache session (Redis)                │
   │                                                             │
   │ 7. Return token + user info                                │
   <────────────────────────────────────────────────────────────┤
   │                                                             │
   │ 8. Store token (localStorage)                              │
   │                                                             │
   │ 9. Include token in requests                               │
   │    Authorization: Bearer <token>                           │
   ├────────────────────────────────────────────────────────────>
   │                                                             │
   │                    10. Validate token                      │
   │                        - Check signature                   │
   │                        - Check expiration                  │
   │                        - Check blacklist                   │
   │                                                             │
   │ 11. Return protected resource                              │
   <────────────────────────────────────────────────────────────┤
   │                                                             │
```

---

## Multi-Tenant Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Organization                            │
│                      (Top Level)                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 1:N
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Workspaces                              │
│                   (Project Containers)                       │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ dev-workspace│  │prod-workspace│  │test-workspace│      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ N:M (via user_workspaces)
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         Users                                │
│                    (with Roles)                              │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ User A       │  │ User B       │  │ User C       │      │
│  │ Role: owner  │  │ Role: admin  │  │ Role: member │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Access Control
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Workspace Resources                       │
│                  (Isolated by workspace_id)                  │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Connections  │  │ Projects     │  │ Migrations   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## Role-Based Access Control (RBAC)

```
┌─────────────────────────────────────────────────────────────┐
│                      Role Hierarchy                          │
└─────────────────────────────────────────────────────────────┘

                    ┌──────────┐
                    │  Owner   │  Level 3
                    │ (Full)   │
                    └────┬─────┘
                         │
                         │ Inherits
                         ▼
                    ┌──────────┐
                    │  Admin   │  Level 2
                    │ (Manage) │
                    └────┬─────┘
                         │
                         │ Inherits
                         ▼
                    ┌──────────┐
                    │  Member  │  Level 1
                    │ (Read)   │
                    └──────────┘

┌─────────────────────────────────────────────────────────────┐
│                    Permissions Matrix                        │
├─────────────────────────────────────────────────────────────┤
│ Resource      │ Owner │ Admin │ Member │                    │
├───────────────┼───────┼───────┼────────┤                    │
│ workspace     │ CRUD  │ RU    │ R      │                    │
│ connections   │ CRUD  │ CRUD  │ R      │                    │
│ projects      │ CRUD  │ CRUD  │ R      │                    │
│ migrations    │ CRUDX │ CRUDX │ R      │                    │
│ users         │ CRUD  │ -     │ -      │                    │
└───────────────┴───────┴───────┴────────┘                    │
                                                               │
Legend: C=Create, R=Read, U=Update, D=Delete, X=Execute       │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Login Request
```
Browser → Frontend → API (/api/auth/login)
                          ↓
                    Auth Router
                          ↓
                Authentication Service
                          ↓
                    User Repository
                          ↓
                    PostgreSQL
                          ↓
                    JWT Service (generate token)
                          ↓
                    Session Cache (Redis)
                          ↓
                    Response (token + user)
                          ↓
                    Frontend (store token)
                          ↓
                    Browser (localStorage)
```

### Authenticated Request
```
Browser → Frontend (add token to header)
                          ↓
                    API Request
                          ↓
                    Auth Middleware
                          ↓
                    JWT Service (validate)
                          ↓
                    Session Cache (check blacklist)
                          ↓
                    RBAC Service (check permissions)
                          ↓
                    Route Handler
                          ↓
                    Service Layer
                          ↓
                    Repository Layer
                          ↓
                    PostgreSQL
                          ↓
                    Response
                          ↓
                    Frontend
                          ↓
                    Browser (display)
```

---

## Caching Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    Cache-Aside Pattern                       │
└─────────────────────────────────────────────────────────────┘

Read Flow:
    Request → Check Redis → Hit? → Return from Redis
                    │
                    │ Miss
                    ▼
              Query PostgreSQL → Cache in Redis → Return

Write Flow:
    Request → Write to PostgreSQL → Invalidate Redis → Return

Fallback:
    Redis Down → Skip Redis → Query PostgreSQL → Return
```

---

## Security Layers

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: Network Security                                    │
│  - HTTPS/TLS encryption                                      │
│  - CORS configuration                                        │
│  - Rate limiting (future)                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Authentication                                      │
│  - JWT token validation                                      │
│  - Token expiration (8 hours)                                │
│  - Token blacklist on logout                                 │
│  - Account locking (5 attempts)                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Authorization                                       │
│  - Role-based access control                                 │
│  - Workspace membership validation                           │
│  - Permission checking                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Data Security                                       │
│  - Password hashing (bcrypt)                                 │
│  - Workspace isolation (workspace_id filter)                 │
│  - Audit logging                                             │
│  - AWS KMS encryption                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### Frontend
- **Framework**: React 18
- **Language**: TypeScript
- **Routing**: React Router v6
- **HTTP Client**: Axios
- **Icons**: Lucide React
- **Styling**: CSS Modules + Design Tokens
- **Fonts**: Google Sans Flex, Google Sans Code

### Backend
- **Framework**: FastAPI 0.109
- **Language**: Python 3.9+
- **ASGI Server**: Uvicorn
- **Validation**: Pydantic v2
- **ORM**: SQLAlchemy 2.0
- **Migrations**: Alembic
- **Authentication**: python-jose (JWT)
- **Password Hashing**: passlib + bcrypt

### Database
- **Primary**: PostgreSQL 12+
- **Cache**: Redis 6+
- **Connection Pool**: SQLAlchemy + pgbouncer

### Cloud Services (Optional)
- **Encryption**: AWS KMS
- **Secrets**: AWS Secrets Manager
- **Logging**: AWS CloudWatch
- **Storage**: AWS S3 (backups)

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Load Balancer                           │
│                    (AWS ALB / Nginx)                         │
└─────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                │                           │
                ▼                           ▼
┌───────────────────────┐   ┌───────────────────────┐
│   Frontend Server     │   │   Backend Server      │
│   (Static Files)      │   │   (FastAPI)           │
│   - React Build       │   │   - Python App        │
│   - Nginx/CDN         │   │   - Uvicorn           │
└───────────────────────┘   └───────────────────────┘
                                        │
                        ┌───────────────┴───────────────┐
                        │                               │
                        ▼                               ▼
            ┌───────────────────┐       ┌───────────────────┐
            │   PostgreSQL      │       │   Redis           │
            │   (RDS)           │       │   (ElastiCache)   │
            │   - Multi-AZ      │       │   - Cluster Mode  │
            │   - Automated     │       │   - Replication   │
            │     Backups       │       │                   │
            └───────────────────┘       └───────────────────┘
```

---

## Performance Characteristics

### Response Times (Target)
- **Login**: < 200ms
- **Token Validation**: < 50ms
- **API Requests**: < 100ms
- **Database Queries**: < 50ms
- **Redis Operations**: < 10ms

### Scalability
- **Concurrent Users**: 1,000+
- **Requests/Second**: 100+
- **Database Connections**: 20 (pool)
- **Redis Connections**: 50 (pool)

### Availability
- **Target Uptime**: 99.9%
- **RTO**: 1 hour
- **RPO**: 5 minutes

---

## Monitoring Points

```
Frontend → Metrics
  - Page load time
  - API response time
  - Error rate
  - User sessions

Backend → Metrics
  - Request rate
  - Response time
  - Error rate
  - CPU/Memory usage

Database → Metrics
  - Connection pool usage
  - Query performance
  - Disk usage
  - Replication lag

Redis → Metrics
  - Hit/miss ratio
  - Memory usage
  - Connection count
  - Eviction rate
```

---

**Last Updated**: 2026-01-25
**Version**: 1.0.0
