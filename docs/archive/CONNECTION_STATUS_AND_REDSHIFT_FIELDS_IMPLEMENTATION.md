# Connection Status & Redshift Fields Implementation

## Summary

This document outlines the implementation plan for:
1. Fixing connection status display issues
2. Ensuring "Last Tested At" shows correct values
3. Adding comprehensive AWS DMS Redshift connection fields

## Issue 1: Connection Status Display

### Problem
- BigQuery connection test shows "connection successful" but UI displays "disconnected"
- Status and Last Tested At values not reflecting actual test results

### Root Cause
The connection status is likely being set correctly in the backend during testing, but:
1. The status might not be persisted to the database after testing
2. The frontend might be caching old status values
3. The test connection endpoint might not be updating the connection record

### Solution

#### Backend Changes Required

1. **Update Test Connection Endpoint** (`backend/routers/connections_router.py`)
   ```python
   @router.post("/{connection_id}/test")
   async def test_connection_endpoint(
       connection_id: int,
       db: Session = Depends(get_db)
   ):
       connection = db.query(Connection).filter(Connection.id == connection_id).first()
       if not connection:
           raise HTTPException(status_code=404, detail="Connection not found")
       
       try:
           # Test the connection
           result = await test_connection(connection)
           
           # CRITICAL: Update status and last_tested_at in database
           connection.status = 'connected' if result['success'] else 'disconnected'
           connection.last_tested_at = datetime.utcnow()
           db.commit()
           db.refresh(connection)
           
           # Invalidate Redis cache
           redis_client.delete(f"connections:metadata:{connection_id}")
           
           return {
               "success": result['success'],
               "message": result['message'],
               "status": connection.status,
               "last_tested_at": connection.last_tested_at
           }
       except Exception as e:
           # Update status to disconnected on error
           connection.status = 'disconnected'
           connection.last_tested_at = datetime.utcnow()
           db.commit()
           
           raise HTTPException(status_code=500, detail=str(e))
   ```

2. **Update Connection Model** (`backend/models/connection.py`)
   - Ensure `status` field accepts: 'connected', 'disconnected', 'testing', 'error'
   - Ensure `last_tested_at` is properly indexed for performance
   - Add validation for status values

3. **Cache Invalidation**
   - Invalidate Redis cache after status update
   - Ensure frontend refetches connection list after testing

#### Frontend Changes Required

1. **Update ConnectionsPage** (`frontend/src/pages/ConnectionsPage.tsx`)
   ```typescript
   const handleTestConnection = async (connectionId: number) => {
     try {
       setTestingId(connectionId);
       
       // Call test endpoint
       const result = await testConnection(connectionId);
       
       // Immediately update local state with new status
       setConnections(prev => prev.map(conn => 
         conn.id === connectionId 
           ? { 
               ...conn, 
               status: result.status,
               last_tested_at: result.last_tested_at 
             }
           : conn
       ));
       
       // Show success message
       showToast('Connection test successful', 'success');
     } catch (error) {
       // Update status to disconnected on error
       setConnections(prev => prev.map(conn => 
         conn.id === connectionId 
           ? { 
               ...conn, 
               status: 'disconnected',
               last_tested_at: new Date().toISOString()
             }
           : conn
       ));
       
       showToast('Connection test failed', 'error');
     } finally {
       setTestingId(null);
     }
   };
   ```

2. **Status Badge Component**
   - Ensure status badge reflects actual status value
   - Use consistent color coding:
     - `connected`: Green
     - `disconnected`: Red
     - `testing`: Yellow
     - `error`: Red

3. **Last Tested At Display**
   - Format timestamp consistently
   - Show relative time (e.g., "2 hours ago")
   - Show full timestamp on hover

### Testing Checklist

- [ ] Test BigQuery connection and verify status updates to "connected"
- [ ] Test with invalid credentials and verify status updates to "disconnected"
- [ ] Verify "Last Tested At" timestamp updates after each test
- [ ] Verify status persists after page refresh
- [ ] Verify status badge color matches actual status
- [ ] Test with Redis unavailable (should fallback to database)

## Issue 2: AWS DMS Redshift Fields

### Current State
- Basic Redshift fields exist (host, port, database, username, password, schema, SSL)
- Missing AWS DMS-specific fields required for migrations

### Required AWS DMS Fields

#### Phase 1: Essential DMS Fields (Immediate)

Add these fields to Redshift configuration:

1. **S3 Bucket Name** (Required for DMS)
   - Field: `s3_bucket_name`
   - Type: text
   - Required: Yes
   - Help: "S3 bucket for staging .csv files (required for AWS DMS)"

2. **S3 Bucket Folder** (Optional)
   - Field: `s3_bucket_folder`
   - Type: text
   - Required: No
   - Help: "S3 folder path for staging files"

3. **Service Access Role ARN** (Required for DMS)
   - Field: `service_access_role_arn`
   - Type: text
   - Required: Yes
   - Help: "IAM role ARN with S3 and Redshift access permissions"
   - Validation: Must match ARN format

4. **Encryption Mode** (Optional)
   - Field: `encryption_mode`
   - Type: select
   - Options: `sse-s3` (default), `sse-kms`
   - Required: No
   - Help: "S3 server-side encryption type"

5. **KMS Key ID** (Conditional)
   - Field: `kms_key_id`
   - Type: text
   - Required: Only if encryption_mode = sse-kms
   - Help: "AWS KMS key ID for encryption"

#### Phase 2: Performance & Optimization (Next)

6. **Connection Timeout**
   - Field: `connection_timeout`
   - Type: number
   - Default: 60000
   - Help: "Connection timeout in milliseconds"

7. **Load Timeout**
   - Field: `load_timeout`
   - Type: number
   - Default: 1200000
   - Help: "Timeout for COPY, INSERT, DELETE, UPDATE operations"

8. **Max File Size**
   - Field: `max_file_size`
   - Type: number
   - Default: 1048576
   - Help: "Maximum .csv file size for S3 upload (KB)"

9. **File Transfer Upload Streams**
   - Field: `file_transfer_upload_streams`
   - Type: number
   - Range: 1-64
   - Default: 10
   - Help: "Number of parallel streams for S3 multipart upload"

#### Phase 3: Data Handling (Future)

10. **Date Format**
11. **Time Format**
12. **Empty As Null**
13. **Trim Blanks**
14. **Comp Update**
15. **Case Sensitive Names**

### Implementation Steps

#### Step 1: Update Backend Field Configurations

File: `backend/constants/default_field_configs.py`

Status: ✅ **COMPLETED** - Added comprehensive Redshift DMS fields

#### Step 2: Update Frontend Field Configurations

File: `frontend/src/constants/defaultFieldConfigs.ts`

Current Status: Has basic fields, needs DMS-specific fields

Action Required:
```typescript
export const REDSHIFT_DEFAULT_FIELDS: FieldConfiguration[] = [
  // Existing basic fields...
  
  // Add DMS-specific fields
  {
    id: 'redshift-s3-bucket',
    name: 's3_bucket_name',
    label: 'S3 Bucket Name (DMS)',
    type: 'text',
    enabled: true,
    required: true,
    placeholder: 'my-dms-staging-bucket',
    helpText: 'S3 bucket for staging .csv files (required for AWS DMS)',
    displayOrder: 8,
    databaseType: 'redshift',
  },
  {
    id: 'redshift-s3-folder',
    name: 's3_bucket_folder',
    label: 'S3 Bucket Folder',
    type: 'text',
    enabled: true,
    required: false,
    placeholder: 'dms-staging/redshift',
    helpText: 'S3 folder path for staging files',
    displayOrder: 9,
    databaseType: 'redshift',
  },
  {
    id: 'redshift-service-role-arn',
    name: 'service_access_role_arn',
    label: 'Service Access Role ARN',
    type: 'text',
    enabled: true,
    required: true,
    placeholder: 'arn:aws:iam::123456789012:role/dms-redshift-role',
    helpText: 'IAM role ARN with S3 and Redshift access',
    displayOrder: 10,
    databaseType: 'redshift',
  },
  // Add more DMS fields...
];
```

#### Step 3: Update Connection Form UI

File: `frontend/src/components/connections/CreateConnectionModal.tsx`

Add field grouping for better UX:
- **Group 1: Basic Connection** (host, port, database, username, password)
- **Group 2: AWS DMS Configuration** (S3 bucket, IAM role, encryption)
- **Group 3: Advanced Settings** (timeouts, performance tuning)

#### Step 4: Update Database Migration

Create new Alembic migration to add DMS fields to connections table:

```python
# backend/alembic/versions/006_add_redshift_dms_fields.py

def upgrade():
    # Add new columns for Redshift DMS configuration
    op.add_column('connections', sa.Column('s3_bucket_name', sa.String(255), nullable=True))
    op.add_column('connections', sa.Column('s3_bucket_folder', sa.String(255), nullable=True))
    op.add_column('connections', sa.Column('service_access_role_arn', sa.String(512), nullable=True))
    op.add_column('connections', sa.Column('encryption_mode', sa.String(50), nullable=True))
    op.add_column('connections', sa.Column('kms_key_id', sa.String(512), nullable=True))
    op.add_column('connections', sa.Column('connection_timeout', sa.Integer, nullable=True))
    op.add_column('connections', sa.Column('load_timeout', sa.Integer, nullable=True))
    op.add_column('connections', sa.Column('max_file_size', sa.Integer, nullable=True))
```

#### Step 5: Update Connection Model

File: `backend/models/connection.py`

Add new fields to Connection model:
```python
class Connection(Base):
    __tablename__ = "connections"
    
    # Existing fields...
    
    # AWS DMS Redshift fields
    s3_bucket_name = Column(String(255), nullable=True)
    s3_bucket_folder = Column(String(255), nullable=True)
    service_access_role_arn = Column(String(512), nullable=True)
    encryption_mode = Column(String(50), nullable=True)
    kms_key_id = Column(String(512), nullable=True)
    connection_timeout = Column(Integer, nullable=True)
    load_timeout = Column(Integer, nullable=True)
    max_file_size = Column(Integer, nullable=True)
```

#### Step 6: Update Validation

Add validation for DMS-specific fields:
- ARN format validation for `service_access_role_arn`
- S3 bucket name format validation
- Conditional validation: KMS Key ID required if encryption_mode = sse-kms

### Migration Status Alignment

To ensure migration status and connection status use the same values:

#### Standardized Status Values

```python
# Shared status enum
class ConnectionStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    TESTING = "testing"
    ERROR = "error"

class MigrationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
```

#### Status Badge Component

Create shared status badge component:
```typescript
// frontend/src/components/ui/StatusBadge.tsx
export const StatusBadge: React.FC<{ status: string }> = ({ status }) => {
  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'connected':
      case 'completed':
        return 'success';
      case 'disconnected':
      case 'failed':
      case 'error':
        return 'error';
      case 'testing':
      case 'running':
      case 'pending':
        return 'warning';
      case 'paused':
        return 'info';
      default:
        return 'default';
    }
  };
  
  return (
    <Badge variant={getStatusColor(status)}>
      {status}
    </Badge>
  );
};
```

## Implementation Priority

### Immediate (This Sprint)
1. ✅ Add comprehensive Redshift DMS fields to backend constants
2. ⏳ Fix connection status persistence after testing
3. ⏳ Update frontend to show correct status and last_tested_at
4. ⏳ Add essential DMS fields to frontend (S3 bucket, IAM role)

### Next Sprint
5. Create database migration for new DMS fields
6. Update Connection model with DMS fields
7. Add field validation (ARN format, S3 bucket name)
8. Update CreateConnectionModal with field grouping

### Future
9. Add Phase 2 DMS fields (performance tuning)
10. Add Phase 3 DMS fields (data handling options)
11. Implement connection testing for DMS-specific fields
12. Add DMS configuration validation

## Testing Requirements

### Connection Status Testing
- [ ] Test BigQuery connection with valid credentials
- [ ] Test BigQuery connection with invalid credentials
- [ ] Verify status updates immediately in UI
- [ ] Verify status persists after page refresh
- [ ] Test with Redis cache enabled
- [ ] Test with Redis cache disabled (fallback to DB)

### Redshift DMS Fields Testing
- [ ] Create Redshift connection with DMS fields
- [ ] Validate ARN format for IAM role
- [ ] Validate S3 bucket name format
- [ ] Test conditional KMS Key ID requirement
- [ ] Verify fields save correctly to database
- [ ] Test connection with DMS configuration

## Documentation Updates

- [ ] Update API documentation with new Redshift fields
- [ ] Document connection status lifecycle
- [ ] Create user guide for AWS DMS Redshift setup
- [ ] Document IAM role permissions required
- [ ] Add troubleshooting guide for connection issues

## References

- [AWS DMS RedshiftSettings API](https://docs.aws.amazon.com/dms/latest/APIReference/API_RedshiftSettings.html)
- [AWS DMS Redshift as Target](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_Target.Redshift.html)
- [Redshift COPY Command](https://docs.aws.amazon.com/redshift/latest/dg/r_COPY.html)
- `AWS_DMS_REDSHIFT_FIELDS.md` - Complete field reference
