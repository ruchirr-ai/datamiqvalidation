# Database Schema Overview

## Database: DataMIQ

### Description
PostgreSQL database for the DataMIQ database migration platform. Supports multi-tenant SaaS architecture with organizations and workspaces.

### Version
1.0.0

### Database Engine
PostgreSQL 12+

---

## Schema Organization

The database is organized into logical groups:

### 1. Authentication & Authorization
- `users` - User accounts
- `sessions` - Active user sessions
- `audit_logs` - Security audit trail

### 2. Multi-Tenancy
- `organizations` - Top-level organizations
- `workspaces` - Workspace containers for projects
- `user_workspaces` - User-workspace membership

### 3. Connections (Future)
- `connections` - Database connections
- `connection_credentials` - Encrypted credentials

### 4. Migrations (Future)
- `migration_projects` - Migration projects
- `migration_tasks` - Individual migration tasks
- `migration_jobs` - Job execution records

### 5. Monitoring (Future)
- `monitoring_metrics` - Performance metrics
- `monitoring_events` - System events

### 6. Validation (Future)
- `validation_results` - Validation outcomes
- `validation_rules` - Validation rule definitions

---

## Entity Relationship Diagram

```
organizations
    ↓ (1:N)
workspaces
    ↓ (N:M via user_workspaces)
users
    ↓ (1:N)
sessions
    ↓ (1:N)
audit_logs
```

---

## Tables Summary

| Table | Purpose | Row Estimate | Critical |
|-------|---------|--------------|----------|
| users | User accounts | 1K-100K | Yes |
| organizations | Organizations | 100-10K | Yes |
| workspaces | Workspaces | 1K-100K | Yes |
| user_workspaces | User-workspace mapping | 10K-1M | Yes |
| sessions | Active sessions | 1K-10K | No |
| audit_logs | Security logs | 100K-10M | Yes |

---

## Indexes Summary

### Primary Indexes
- All tables have primary key on `id` column (SERIAL)

### Unique Indexes
- `users.username` - Unique username constraint
- `organizations.slug` - Unique organization slug
- `workspaces(organization_id, slug)` - Unique workspace per org
- `user_workspaces(user_id, workspace_id)` - Unique membership

### Performance Indexes
- `users.organization_id` - Organization lookup
- `workspaces.organization_id` - Workspace by organization
- `user_workspaces.user_id` - User's workspaces
- `user_workspaces.workspace_id` - Workspace members
- `sessions.user_id` - User sessions
- `sessions.token_hash` - Token lookup
- `audit_logs.user_id` - User audit trail
- `audit_logs.event_type` - Event filtering
- `audit_logs.created_at` - Time-based queries

---

## Foreign Key Relationships

### users table
- `organization_id` → `organizations(id)` ON DELETE SET NULL

### workspaces table
- `organization_id` → `organizations(id)` ON DELETE CASCADE

### user_workspaces table
- `user_id` → `users(id)` ON DELETE CASCADE
- `workspace_id` → `workspaces(id)` ON DELETE CASCADE

### sessions table
- `user_id` → `users(id)` ON DELETE CASCADE

### audit_logs table
- `user_id` → `users(id)` ON DELETE SET NULL

---

## Data Isolation Strategy

### Multi-Tenant Isolation
All resource tables include `workspace_id` for data isolation:
- Connections: `workspace_id`
- Projects: `workspace_id`
- Tasks: `workspace_id`
- Jobs: `workspace_id`

### Query Pattern
**CRITICAL**: All queries MUST filter by `workspace_id`:

```sql
-- CORRECT
SELECT * FROM migration_projects 
WHERE workspace_id = :workspace_id;

-- WRONG - Security Risk!
SELECT * FROM migration_projects;
```

---

## Naming Conventions

### Tables
- Lowercase with underscores: `user_workspaces`
- Plural nouns: `users`, `organizations`
- Descriptive names: `migration_projects` not `projects`

### Columns
- Lowercase with underscores: `created_at`
- Descriptive names: `failed_login_attempts`
- Foreign keys: `{table}_id` (e.g., `organization_id`)
- Timestamps: `created_at`, `updated_at`
- Booleans: `is_active`, `is_deleted`

### Indexes
- Format: `idx_{table}_{column(s)}`
- Example: `idx_users_username`
- Unique: `idx_users_username` (UNIQUE)

### Constraints
- Format: `{table}_{column}_{type}`
- Example: `users_role_check`
- Foreign keys: `fk_{table}_{ref_table}`

---

## Data Types

### Standard Types
- **IDs**: `SERIAL` (auto-incrementing integer)
- **Strings**: `VARCHAR(n)` with appropriate length
- **Text**: `TEXT` for unlimited length
- **Numbers**: `INTEGER`, `BIGINT`, `DECIMAL`
- **Booleans**: `BOOLEAN`
- **Timestamps**: `TIMESTAMP` (UTC)
- **JSON**: `JSONB` for structured data

### Type Guidelines
- Use `VARCHAR` with length limits for indexed columns
- Use `TEXT` for long-form content
- Use `JSONB` for flexible schema data
- Always use `TIMESTAMP` (not `DATE` or `TIME`)
- Store all timestamps in UTC

---

## Timestamps

### Standard Timestamp Columns
All tables include:
- `created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP`
- `updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP`

### Timestamp Triggers
Update `updated_at` automatically:

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

---

## Soft Deletes

### Implementation
Some tables use soft deletes:
- Add `is_deleted BOOLEAN NOT NULL DEFAULT FALSE`
- Add `deleted_at TIMESTAMP NULL`
- Filter queries: `WHERE is_deleted = FALSE`

### Tables with Soft Deletes
- `users` - Preserve audit trail
- `organizations` - Preserve relationships
- `workspaces` - Preserve project history

---

## Partitioning Strategy

### Current Partitioning
None (single database)

### Future Partitioning
Consider partitioning for:
- `audit_logs` - By month (time-based)
- `monitoring_metrics` - By month (time-based)
- `migration_jobs` - By workspace_id (hash)

---

## Backup Strategy

### Backup Schedule
- **Full Backup**: Daily at 2 AM UTC
- **Incremental**: Every 6 hours
- **WAL Archiving**: Continuous

### Retention Policy
- Daily backups: 30 days
- Weekly backups: 12 weeks
- Monthly backups: 12 months

### Backup Location
- Primary: AWS S3 bucket
- Secondary: Cross-region replication

---

## Performance Considerations

### Connection Pooling
- Pool size: 20 connections
- Max overflow: 10 connections
- Timeout: 30 seconds

### Query Optimization
- All foreign keys are indexed
- Composite indexes for common queries
- EXPLAIN ANALYZE for slow queries
- Query timeout: 30 seconds

### Maintenance
- VACUUM ANALYZE: Weekly
- REINDEX: Monthly
- Statistics update: Daily

---

## Security

### Encryption
- Encryption at rest: AWS RDS encryption
- Encryption in transit: SSL/TLS required
- Sensitive data: Encrypted with AWS KMS

### Access Control
- Application user: Limited permissions
- Admin user: Full permissions (emergency only)
- Read-only user: SELECT only (reporting)

### Audit Trail
- All authentication events logged
- All data modifications logged
- Log retention: 1 year

---

## Migration Management

### Tool
Alembic for Python/SQLAlchemy

### Migration Files
Location: `backend/alembic/versions/`

### Migration Naming
Format: `{revision}_{description}.py`
Example: `001_create_auth_tables.py`

### Migration Process
1. Create migration: `alembic revision -m "description"`
2. Edit migration file
3. Test in development
4. Review in staging
5. Apply to production: `alembic upgrade head`

---

## Monitoring

### Key Metrics
- Connection pool usage
- Query execution time
- Table sizes
- Index usage
- Lock contention
- Replication lag

### Alerts
- Connection pool > 80%
- Query time > 5 seconds
- Disk usage > 80%
- Replication lag > 1 minute

---

## Disaster Recovery

### RTO (Recovery Time Objective)
- Target: 1 hour
- Maximum: 4 hours

### RPO (Recovery Point Objective)
- Target: 5 minutes
- Maximum: 1 hour

### Recovery Procedures
1. Restore from latest backup
2. Apply WAL logs
3. Verify data integrity
4. Update DNS/connection strings
5. Resume operations

---

## Database Maintenance

### Daily
- Backup verification
- Log review
- Performance monitoring

### Weekly
- VACUUM ANALYZE
- Index usage review
- Slow query analysis

### Monthly
- REINDEX
- Statistics update
- Capacity planning
- Security audit

---

## Future Enhancements

### Planned Features
- Read replicas for reporting
- Partitioning for large tables
- Materialized views for dashboards
- Full-text search indexes
- Time-series data optimization

### Scalability
- Horizontal scaling with read replicas
- Vertical scaling for write performance
- Sharding by organization_id (if needed)
- Caching layer (Redis) for hot data

---

## References

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [AWS RDS Best Practices](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_BestPractices.html)

---

## Changelog

### Version 1.0.0 (2026-01-25)
- Initial schema design
- Authentication tables
- Multi-tenancy tables
- Audit logging
- Indexes and constraints
