# Audit Logger Service Documentation

## Overview

The `AuditLogger` service provides comprehensive audit logging for security, compliance, and troubleshooting purposes. It logs all authentication events, authorization failures, data modifications, and security-relevant operations to the database for audit trail and compliance requirements.

**Location**: `backend/services/audit_logger.py`

## Purpose

- Log authentication events (login, logout, failed attempts)
- Log authorization failures and permission denials
- Log data modifications and sensitive operations
- Provide audit trail for compliance (SOC 2, GDPR, HIPAA)
- Support security incident investigation
- Track user actions across workspaces

## Dependencies

```python
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
```

**Database Tables**:
- `audit_logs`: Stores all audit log entries

## Audit Log Schema

### audit_logs Table

```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(50) NOT NULL,
    user_id INTEGER REFERENCES users(id),
    username VARCHAR(255),
    workspace_id INTEGER REFERENCES workspaces(id),
    organization_id INTEGER REFERENCES organizations(id),
    ip_address VARCHAR(45),
    user_agent TEXT,
    action VARCHAR(255) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    status VARCHAR(20) NOT NULL,
    details JSONB,
    error_message TEXT
);

CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_event_type ON audit_logs(event_type);
CREATE INDEX idx_audit_logs_workspace_id ON audit_logs(workspace_id);
```

## Event Types

### Authentication Events
- `LOGIN_SUCCESS`: Successful user login
- `LOGIN_FAILURE`: Failed login attempt
- `LOGOUT`: User logout
- `TOKEN_REFRESH`: JWT token refresh
- `ACCOUNT_LOCKED`: Account locked due to failed attempts

### Authorization Events
- `ACCESS_DENIED`: Permission denied
- `ROLE_CHECK_FAILED`: Role check failure
- `WORKSPACE_ACCESS_DENIED`: Workspace access denied

### Data Modification Events
- `USER_CREATED`: New user created
- `USER_UPDATED`: User information updated
- `USER_DELETED`: User deleted
- `PASSWORD_CHANGED`: Password changed
- `ROLE_CHANGED`: User role changed

### Workspace Events
- `WORKSPACE_CREATED`: New workspace created
- `WORKSPACE_SWITCHED`: User switched workspace
- `WORKSPACE_DELETED`: Workspace deleted

### Security Events
- `SUSPICIOUS_ACTIVITY`: Suspicious activity detected
- `BRUTE_FORCE_ATTEMPT`: Brute force attack detected
- `TOKEN_BLACKLISTED`: Token added to blacklist

## Class Definition

```python
class AuditLogger:
    """Service for audit logging"""
    
    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)
```

## Methods

### log_authentication()

Logs authentication events (login, logout, failed attempts).

**Signature**:
```python
def log_authentication(
    self,
    event_type: str,
    username: str,
    user_id: Optional[int] = None,
    status: str = "success",
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    error_message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> None
```

**Parameters**:
- `event_type` (str): Event type (LOGIN_SUCCESS, LOGIN_FAILURE, LOGOUT, etc.)
- `username` (str): Username attempting authentication
- `user_id` (Optional[int]): User ID if known
- `status` (str): "success" or "failure"
- `ip_address` (Optional[str]): Client IP address
- `user_agent` (Optional[str]): Client user agent
- `error_message` (Optional[str]): Error message if failed
- `details` (Optional[Dict]): Additional details as JSON

**Returns**:
- `None`

**Example**:
```python
from backend.services.audit_logger import AuditLogger

# Successful login
audit_logger.log_authentication(
    event_type="LOGIN_SUCCESS",
    username="john_doe",
    user_id=123,
    status="success",
    ip_address="192.168.1.100",
    user_agent="Mozilla/5.0...",
    details={"workspace_id": 5}
)

# Failed login
audit_logger.log_authentication(
    event_type="LOGIN_FAILURE",
    username="john_doe",
    status="failure",
    ip_address="192.168.1.100",
    error_message="Invalid password",
    details={"failed_attempts": 3}
)

# Account locked
audit_logger.log_authentication(
    event_type="ACCOUNT_LOCKED",
    username="john_doe",
    user_id=123,
    status="failure",
    ip_address="192.168.1.100",
    error_message="Account locked due to too many failed attempts",
    details={"locked_until": "2026-01-25T12:00:00Z"}
)
```

---

### log_authorization()

Logs authorization events (access denied, permission checks).

**Signature**:
```python
def log_authorization(
    self,
    event_type: str,
    user_id: int,
    username: str,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    workspace_id: Optional[int] = None,
    status: str = "denied",
    error_message: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> None
```

**Parameters**:
- `event_type` (str): Event type (ACCESS_DENIED, ROLE_CHECK_FAILED, etc.)
- `user_id` (int): User ID
- `username` (str): Username
- `action` (str): Action attempted (read, write, delete, etc.)
- `resource_type` (Optional[str]): Type of resource (project, connection, etc.)
- `resource_id` (Optional[str]): Resource identifier
- `workspace_id` (Optional[int]): Workspace ID
- `status` (str): "denied" or "granted"
- `error_message` (Optional[str]): Error message
- `details` (Optional[Dict]): Additional details

**Returns**:
- `None`

**Example**:
```python
# Access denied
audit_logger.log_authorization(
    event_type="ACCESS_DENIED",
    user_id=123,
    username="john_doe",
    action="delete",
    resource_type="project",
    resource_id="proj-456",
    workspace_id=5,
    status="denied",
    error_message="Insufficient permissions",
    details={"required_role": "admin", "user_role": "member"}
)

# Workspace access denied
audit_logger.log_authorization(
    event_type="WORKSPACE_ACCESS_DENIED",
    user_id=123,
    username="john_doe",
    action="access",
    resource_type="workspace",
    resource_id="10",
    status="denied",
    error_message="User not member of workspace"
)
```

---

### log_data_modification()

Logs data modification events (create, update, delete).

**Signature**:
```python
def log_data_modification(
    self,
    event_type: str,
    user_id: int,
    username: str,
    action: str,
    resource_type: str,
    resource_id: str,
    workspace_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    status: str = "success",
    details: Optional[Dict[str, Any]] = None
) -> None
```

**Parameters**:
- `event_type` (str): Event type (USER_CREATED, USER_UPDATED, etc.)
- `user_id` (int): User ID performing action
- `username` (str): Username performing action
- `action` (str): Action performed (create, update, delete)
- `resource_type` (str): Type of resource modified
- `resource_id` (str): Resource identifier
- `workspace_id` (Optional[int]): Workspace ID
- `organization_id` (Optional[int]): Organization ID
- `status` (str): "success" or "failure"
- `details` (Optional[Dict]): Additional details (changes made)

**Returns**:
- `None`

**Example**:
```python
# User created
audit_logger.log_data_modification(
    event_type="USER_CREATED",
    user_id=1,  # Admin creating the user
    username="admin",
    action="create",
    resource_type="user",
    resource_id="456",
    organization_id=1,
    status="success",
    details={
        "new_username": "new_user",
        "role": "member"
    }
)

# User updated
audit_logger.log_data_modification(
    event_type="USER_UPDATED",
    user_id=1,
    username="admin",
    action="update",
    resource_type="user",
    resource_id="456",
    status="success",
    details={
        "changed_fields": ["role"],
        "old_role": "member",
        "new_role": "admin"
    }
)

# Password changed
audit_logger.log_data_modification(
    event_type="PASSWORD_CHANGED",
    user_id=123,
    username="john_doe",
    action="update",
    resource_type="user",
    resource_id="123",
    status="success",
    details={"changed_by_self": True}
)
```

---

### log_security_event()

Logs security-related events (suspicious activity, brute force attempts).

**Signature**:
```python
def log_security_event(
    self,
    event_type: str,
    action: str,
    ip_address: Optional[str] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None
) -> None
```

**Parameters**:
- `event_type` (str): Event type (SUSPICIOUS_ACTIVITY, BRUTE_FORCE_ATTEMPT, etc.)
- `action` (str): Action description
- `ip_address` (Optional[str]): Source IP address
- `user_id` (Optional[int]): User ID if known
- `username` (Optional[str]): Username if known
- `details` (Optional[Dict]): Additional details
- `error_message` (Optional[str]): Error or alert message

**Returns**:
- `None`

**Example**:
```python
# Brute force attempt detected
audit_logger.log_security_event(
    event_type="BRUTE_FORCE_ATTEMPT",
    action="multiple_failed_logins",
    ip_address="192.168.1.100",
    username="john_doe",
    details={
        "failed_attempts": 10,
        "time_window": "5 minutes",
        "action_taken": "IP temporarily blocked"
    },
    error_message="Possible brute force attack detected"
)

# Suspicious activity
audit_logger.log_security_event(
    event_type="SUSPICIOUS_ACTIVITY",
    action="unusual_access_pattern",
    ip_address="203.0.113.42",
    user_id=123,
    username="john_doe",
    details={
        "reason": "Access from unusual location",
        "previous_location": "US",
        "current_location": "Unknown"
    }
)

# Token blacklisted
audit_logger.log_security_event(
    event_type="TOKEN_BLACKLISTED",
    action="logout",
    user_id=123,
    username="john_doe",
    details={"token_id": "abc123", "reason": "user_logout"}
)
```

---

### query_logs()

Queries audit logs with filters.

**Signature**:
```python
def query_logs(
    self,
    user_id: Optional[int] = None,
    workspace_id: Optional[int] = None,
    event_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100
) -> List[Dict[str, Any]]
```

**Parameters**:
- `user_id` (Optional[int]): Filter by user ID
- `workspace_id` (Optional[int]): Filter by workspace ID
- `event_type` (Optional[str]): Filter by event type
- `start_date` (Optional[datetime]): Filter by start date
- `end_date` (Optional[datetime]): Filter by end date
- `limit` (int): Maximum number of results (default: 100)

**Returns**:
- `List[Dict[str, Any]]`: List of audit log entries

**Example**:
```python
from datetime import datetime, timedelta

# Get all logs for a user
logs = audit_logger.query_logs(user_id=123, limit=50)

# Get failed login attempts in last 24 hours
yesterday = datetime.utcnow() - timedelta(days=1)
failed_logins = audit_logger.query_logs(
    event_type="LOGIN_FAILURE",
    start_date=yesterday,
    limit=100
)

# Get workspace activity
workspace_logs = audit_logger.query_logs(
    workspace_id=5,
    start_date=datetime(2026, 1, 1),
    end_date=datetime(2026, 1, 31)
)

# Process results
for log in logs:
    print(f"{log['timestamp']}: {log['action']} by {log['username']}")
```

## Complete Usage Examples

### Login Flow with Audit Logging

```python
from backend.services.audit_logger import AuditLogger
from backend.services.auth_service import AuthService
from backend.repositories.user_repository import UserRepository

async def login(username: str, password: str, ip_address: str, user_agent: str):
    """Login with comprehensive audit logging"""
    
    audit_logger = AuditLogger(db)
    user_repo = UserRepository(db)
    
    try:
        # Get user
        user = user_repo.get_by_username(username)
        
        if not user:
            # Log failed login - user not found
            audit_logger.log_authentication(
                event_type="LOGIN_FAILURE",
                username=username,
                status="failure",
                ip_address=ip_address,
                user_agent=user_agent,
                error_message="User not found"
            )
            raise AuthenticationError("Invalid credentials")
        
        # Check if account is locked
        if AuthService.is_account_locked(user.failed_login_attempts, user.locked_until):
            # Log locked account attempt
            audit_logger.log_authentication(
                event_type="ACCOUNT_LOCKED",
                username=username,
                user_id=user.id,
                status="failure",
                ip_address=ip_address,
                user_agent=user_agent,
                error_message=f"Account locked until {user.locked_until}",
                details={"locked_until": user.locked_until.isoformat()}
            )
            raise AuthenticationError("Account is locked")
        
        # Verify password
        if not AuthService.verify_password(password, user.password_hash):
            # Increment failed attempts
            user.failed_login_attempts += 1
            
            # Check if should lock account
            if user.failed_login_attempts >= AuthService.MAX_FAILED_ATTEMPTS:
                lockout_time = AuthService.calculate_lockout_time()
                user_repo.update_user(user.id, locked_until=lockout_time)
                
                # Log account locked
                audit_logger.log_authentication(
                    event_type="ACCOUNT_LOCKED",
                    username=username,
                    user_id=user.id,
                    status="failure",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message="Account locked due to too many failed attempts",
                    details={
                        "failed_attempts": user.failed_login_attempts,
                        "locked_until": lockout_time.isoformat()
                    }
                )
            else:
                # Log failed login
                audit_logger.log_authentication(
                    event_type="LOGIN_FAILURE",
                    username=username,
                    user_id=user.id,
                    status="failure",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    error_message="Invalid password",
                    details={"failed_attempts": user.failed_login_attempts}
                )
            
            user_repo.update_user(user.id, failed_login_attempts=user.failed_login_attempts)
            raise AuthenticationError("Invalid credentials")
        
        # Successful login - reset failed attempts
        if user.failed_login_attempts > 0:
            user_repo.reset_failed_attempts(user.id)
        
        # Generate token
        token = jwt_service.create_access_token(user.id, user.username, user.role)
        
        # Log successful login
        audit_logger.log_authentication(
            event_type="LOGIN_SUCCESS",
            username=username,
            user_id=user.id,
            status="success",
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "workspace_id": user.default_workspace_id,
                "organization_id": user.organization_id
            }
        )
        
        return {"access_token": token, "user": user}
        
    except Exception as e:
        # Log unexpected error
        audit_logger.log_authentication(
            event_type="LOGIN_FAILURE",
            username=username,
            status="failure",
            ip_address=ip_address,
            error_message=str(e)
        )
        raise
```

### Authorization Check with Audit Logging

```python
async def check_permission(user_id: int, action: str, resource_type: str, resource_id: str):
    """Check permission with audit logging"""
    
    audit_logger = AuditLogger(db)
    rbac_service = RBACService(db)
    
    user = user_repo.get_by_id(user_id)
    
    # Check permission
    has_permission = rbac_service.check_permission(user.role, action, resource_type)
    
    if not has_permission:
        # Log access denied
        audit_logger.log_authorization(
            event_type="ACCESS_DENIED",
            user_id=user_id,
            username=user.username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            workspace_id=user.current_workspace_id,
            status="denied",
            error_message=f"User role '{user.role}' lacks permission for '{action}' on '{resource_type}'",
            details={
                "required_permission": f"{action}:{resource_type}",
                "user_role": user.role
            }
        )
        raise PermissionError("Access denied")
    
    return True
```

## Security Considerations

### Data Privacy
- **No Sensitive Data**: Never log passwords, tokens, or sensitive credentials
- **PII Protection**: Be careful with personally identifiable information
- **Data Masking**: Mask sensitive fields in details JSON

### Retention Policy
- **Compliance Requirements**: Retain logs per compliance requirements (SOC 2, GDPR, etc.)
- **Storage Management**: Implement log rotation and archival
- **Partitioning**: Partition audit_logs table by date for performance

### Access Control
- **Read Access**: Restrict audit log access to admins only
- **Tamper-Proof**: Audit logs should be append-only
- **Integrity**: Consider cryptographic signatures for critical logs

## Performance Considerations

### Async Logging
```python
import asyncio

async def log_async(audit_logger, event_type, **kwargs):
    """Log asynchronously to avoid blocking"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        audit_logger.log_authentication,
        event_type,
        **kwargs
    )
```

### Batch Logging
```python
# For high-volume operations, batch insert logs
logs_batch = []
for item in items:
    logs_batch.append({
        "event_type": "DATA_PROCESSED",
        "user_id": user_id,
        "resource_id": item.id
    })

audit_logger.batch_insert(logs_batch)
```

### Table Partitioning
```sql
-- Partition by month for better performance
CREATE TABLE audit_logs_2026_01 PARTITION OF audit_logs
FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```

## Testing

### Unit Tests

```python
import pytest
from backend.services.audit_logger import AuditLogger

def test_log_authentication_success(db_session):
    """Test logging successful authentication"""
    audit_logger = AuditLogger(db_session)
    
    audit_logger.log_authentication(
        event_type="LOGIN_SUCCESS",
        username="testuser",
        user_id=1,
        status="success",
        ip_address="127.0.0.1"
    )
    
    # Verify log was created
    logs = audit_logger.query_logs(user_id=1, event_type="LOGIN_SUCCESS")
    assert len(logs) == 1
    assert logs[0]["username"] == "testuser"

def test_log_authorization_denied(db_session):
    """Test logging authorization denial"""
    audit_logger = AuditLogger(db_session)
    
    audit_logger.log_authorization(
        event_type="ACCESS_DENIED",
        user_id=1,
        username="testuser",
        action="delete",
        resource_type="project",
        resource_id="123",
        status="denied"
    )
    
    logs = audit_logger.query_logs(event_type="ACCESS_DENIED")
    assert len(logs) == 1
    assert logs[0]["action"] == "delete"
```

## Related Documentation

- [Authentication Service](./authentication_service.md) - Uses AuditLogger for auth events
- [RBAC Service](./rbac_service.md) - Uses AuditLogger for authorization events
- [Authentication API](../../api/authentication.md) - API endpoints with audit logging
- [Logging Standards](../../../.kiro/steering/logging-standards.md) - Logging guidelines
- [Security Standards](../../../.kiro/steering/security-standards.md) - Security requirements

---

**Last Updated**: 2026-01-25  
**Version**: 1.0  
**Status**: Production Ready
