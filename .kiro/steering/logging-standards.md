---
inclusion: always
---

# Logging Standards

## Logging Requirements
Proper logging is REQUIRED throughout the application.

### Logging Levels
- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Warning messages for potentially harmful situations
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical issues requiring immediate attention

### What to Log

#### Application Events
- Application startup/shutdown
- Configuration loading
- Database connections
- API requests (with sanitized data)
- Migration operations (start, progress, completion)
- Validation results
- Error conditions with stack traces

#### Security Events
- Authentication attempts (success/failure)
- Authorization failures
- Encryption/decryption operations (not the data)
- KMS key usage
- Secrets Manager access
- Suspicious activities

#### Performance Metrics
- Request duration
- Database query performance
- Migration throughput
- Resource usage

### What NOT to Log
- Passwords or credentials
- Decrypted connection strings
- Encryption keys
- Personally identifiable information (PII)
- Full database records with sensitive data

### Log Format
Use structured logging (JSON format):
```json
{
  "timestamp": "2026-01-25T10:30:00Z",
  "level": "INFO",
  "module": "connections",
  "message": "Database connection established",
  "context": {
    "connection_id": "conn-123",
    "database_type": "postgresql"
  },
  "request_id": "req-456"
}
```

### Log Storage
- Store logs in PostgreSQL database
- Use separate table for logs with partitioning
- Implement log retention policies
- Archive old logs to S3
- Enable CloudWatch Logs for AWS monitoring

### Log Aggregation
- Send logs to AWS CloudWatch
- Use CloudWatch Insights for querying
- Set up CloudWatch alarms for errors
- Create dashboards for monitoring

### Correlation
- Use request IDs for tracing
- Include user context (sanitized)
- Include migration/task IDs
- Enable distributed tracing

### Python Logging Setup
- Use Python's logging module
- Configure logging in main.py
- Use log handlers for different destinations
- Implement log rotation
- Use context managers for operation logging

### Audit Logging
- Log all data modifications
- Log configuration changes
- Log user actions
- Store audit logs separately
- Implement tamper-proof logging
