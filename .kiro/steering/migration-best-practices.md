---
inclusion: always
---

# Database Migration Best Practices

## Assessment Phase
- Analyze schema compatibility
- Identify data type mappings
- Detect potential data loss scenarios
- Estimate migration time and resources
- Generate comprehensive assessment reports

## Migration Planning
- Break large migrations into smaller batches
- Plan for rollback scenarios
- Consider downtime requirements
- Identify dependencies between tables
- Plan validation checkpoints

## Execution
- Implement idempotent operations
- Use transactions where possible
- Implement retry logic for transient failures
- Log all operations for audit trail
- Support pause/resume functionality

## Monitoring
- Track progress in real-time
- Monitor resource usage (CPU, memory, network)
- Alert on errors and anomalies
- Provide ETA calculations
- Log performance metrics

## Validation
- Compare row counts
- Validate data integrity with checksums
- Sample data comparison
- Verify constraints and indexes
- Test application functionality post-migration

## Error Handling
- Categorize errors (transient vs permanent)
- Implement automatic retry for transient errors
- Provide clear error messages
- Support manual intervention for complex issues
- Maintain error logs for troubleshooting
