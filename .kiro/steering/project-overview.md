---
inclusion: always
---

# Database Migrator Tool - Project Overview

## Product Vision
A comprehensive SaaS database migration platform that enables multiple organizations to seamlessly migrate data from any database to any database with assessment, monitoring, and validation capabilities. Each organization operates within isolated workspaces with complete data segregation.

## Technology Stack
- **Frontend**: React
- **Backend**: Python + FastAPI (Microservices Architecture)
- **Database**: PostgreSQL (application backend - all data stored in DB, no static storage)
- **Cache**: Redis (primary cache layer with database fallback)
- **Cloud**: AWS with security best practices
- **Orchestration**: Kubernetes for microservices deployment
- **Architecture**: Multi-tenant SaaS with workspace isolation

## Core Modules

### 1. Connections
Manages database connections for source and target databases. Supports multiple database types with unified connection interface.

### 2. Assessment & Reports
Analyzes source databases to assess migration complexity, compatibility issues, and generates detailed assessment reports.

### 3. Migration Projects
Organizes migrations into projects with configuration, planning, and execution management.

### 4. Migration Tasks
Breaks down migrations into discrete, trackable tasks with dependencies and execution order.

### 5. Monitoring
Real-time monitoring of migration progress, performance metrics, and error tracking.

### 6. Validation
Post-migration validation to ensure data integrity, completeness, and correctness.

## Development Principles
- Multi-tenant SaaS architecture with workspace isolation
- Microservices design for scalability (Kubernetes deployment)
- Modular architecture for maintainability
- Clear API contracts between frontend and backend
- Comprehensive error handling and logging
- Scalable design for large datasets
- Database-agnostic abstractions for migration sources/targets
- PostgreSQL-powered application backend (no static storage)
- Configuration-driven design using .env files
- Security-first approach with encryption and AWS best practices
- Test-driven development: Create tests for every feature with sample payloads
- Always filter by workspace_id for data isolation
