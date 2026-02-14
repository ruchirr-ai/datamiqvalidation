---
inclusion: always
---

# Database Architecture

## PostgreSQL as Application Backend

### Core Principle
Everything is powered by PostgreSQL. No static file storage. All application data, configuration, state, and metadata stored in the database.

### Database Design
- Use proper normalization
- Implement foreign key constraints
- Use indexes strategically
- Implement database-level validation
- Use transactions for data consistency

### Schema Organization
- Separate schemas for different modules:
  - `connections` - Database connection metadata
  - `assessment` - Assessment results and reports
  - `projects` - Migration project data
  - `tasks` - Migration task definitions and state
  - `monitoring` - Metrics and monitoring data
  - `validation` - Validation results
  - `audit` - Audit logs

### Data Storage
- Store encrypted connection strings in database
- Store assessment reports as JSONB
- Store migration configurations as JSONB
- Store logs in database tables (with retention policies)
- Store metrics and monitoring data
- Store validation results

### Performance Considerations
- Use connection pooling (pgbouncer or SQLAlchemy pool)
- Implement proper indexing strategy
- Use JSONB for flexible schema data
- Partition large tables (logs, metrics)
- Implement data retention policies
- Use materialized views for reporting

### Backup & Recovery
- Implement automated backups
- Test restore procedures
- Use point-in-time recovery
- Store backups in S3
- Implement backup encryption

### Database Security
- Enable SSL/TLS for connections
- Use strong passwords
- Implement row-level security if needed
- Audit database access
- Encrypt sensitive columns
- Use read replicas for reporting

### Migration Management
- Use Alembic or similar for schema migrations
- Version control all schema changes
- Test migrations in non-prod first
- Implement rollback procedures
- Document schema changes
