# Production Logging Enhanced - Backend & Frontend Integration

## Overview
Enhanced logging throughout the actual backend implementation (not just test scripts) with database storage and frontend accessibility. All migration logs are now stored in the `migration_logs` table and accessible via the API.

## Backend Enhancements

### 1. **Orchestrator Logging** (`orchestrator.py`)

Added comprehensive database logging throughout the migration lifecycle:

#### Migration Start
```python
self._log(
    migration_id,
    'INFO',
    'migration',
    f"Starting migration execution using Pathway {migration.pathway}",
    log_metadata={
        'pathway': migration.pathway,
        'source_dataset': migration.source_dataset,
        'target_database': migration.target_database
    }
)
```

#### Export Stage
- Logs when export starts with table count
- Logs export completion status
- Logs any export failures with metadata

#### Transfer Stage
- Logs transfer stage initiation
- Logs AWS credential decryption status
- Logs pathway execution start

#### Completion
- Logs successful completion
- Logs failures with exception details

### 2. **Pathway C Logging** (`pathway_c.py`)

Added detailed database logging for GCS to S3 transfer:

#### Transfer Configuration
```python
self._log_to_db(
    migration_id,
    'INFO',
    'transfer',
    f"Transfer configuration: gs://{gcs_bucket}/{gcs_path} → s3://{s3_bucket}/{s3_path}",
    log_metadata={
        'gcs_bucket': gcs_bucket,
        'gcs_path': gcs_path,
        's3_bucket': s3_bucket,
        's3_path': s3_path,
        'delete_source': delete_source
    }
)
```

#### Validation Errors
- Logs missing GCS bucket
- Logs missing S3 bucket
- Logs missing AWS credentials

#### Credential Operations
- Logs AWS credential decryption attempts
- Logs GCP credential loading from database

#### Transfer Progress
- Logs transfer initiation
- Logs transfer completion with statistics:
  - Files transferred
  - Data size
  - Duration
  - Average speed
  - Success rate

#### Example Transfer Completion Log
```python
self._log_to_db(
    migration_id,
    'INFO',
    'transfer',
    f"Transfer completed: 150/150 files (2.45 GB) in 5.2m",
    log_metadata={
        'status': 'SUCCESS',
        'files_found': 150,
        'files_transferred': 150,
        'files_failed': 0,
        'bytes_transferred': 2631475200,
        'duration_seconds': 312,
        'average_speed_bytes_per_sec': 8434856,
        'success_rate_percent': 100.0
    }
)
```

### 3. **GCS to S3 Transfer Service** (`gcs_to_s3_transfer.py`)

Enhanced with detailed console logging (already implemented):
- Per-file progress with emoji indicators
- Real-time statistics after each file
- ETA calculations
- Transfer speed tracking
- Human-readable formatting

## Database Schema

### Migration Logs Table
```sql
CREATE TABLE migration_logs (
    id SERIAL PRIMARY KEY,
    migration_id INTEGER NOT NULL,
    log_level VARCHAR(20) NOT NULL,  -- DEBUG, INFO, WARNING, ERROR, CRITICAL
    stage VARCHAR(50) NOT NULL,      -- export, transfer, load, migration
    message TEXT NOT NULL,
    error_code VARCHAR(50),
    stack_trace TEXT,
    log_metadata JSONB,              -- Additional context data
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

## API Endpoint

### GET `/api/bq-redshift-migrations/{migration_id}/logs`

**Query Parameters:**
- `level` (optional): Filter by log level
- `limit` (optional): Maximum number of logs (default: 1000)

**Response:**
```json
{
  "migration_id": 123,
  "total_logs": 45,
  "logs": [
    {
      "id": 1,
      "migration_id": 123,
      "log_level": "INFO",
      "stage": "transfer",
      "message": "Starting GCS to S3 transfer stage",
      "error_code": null,
      "stack_trace": null,
      "log_metadata": {
        "gcs_bucket": "my-bucket",
        "s3_bucket": "my-s3-bucket"
      },
      "created_at": "2026-02-09T10:30:00Z"
    },
    {
      "id": 2,
      "log_level": "INFO",
      "stage": "transfer",
      "message": "Transfer completed: 150/150 files (2.45 GB) in 5.2m",
      "log_metadata": {
        "files_transferred": 150,
        "bytes_transferred": 2631475200,
        "duration_seconds": 312,
        "average_speed_bytes_per_sec": 8434856
      },
      "created_at": "2026-02-09T10:35:12Z"
    }
  ]
}
```

## Frontend Integration

### Existing Implementation

The frontend already has the infrastructure to display logs:

**MigrationsPage.tsx** - View Logs button in dropdown menu:
```typescript
<button
  className="dropdown-menu-item"
  onClick={() => handleViewLogs(migration)}
>
  <svg>...</svg>
  View Logs
</button>
```

**handleViewLogs Function:**
```typescript
const handleViewLogs = async (migration: Migration) => {
  setOpenMenuId(null);
  setLoadingLogs(true);
  setShowLogsModal(true);
  setLogsData(null);
  
  try {
    const logs = await bqRedshiftApi.getMigrationLogs(parseInt(migration.id));
    
    setLogsData({
      migrationName: migration.name,
      migrationId: migration.id,
      ...logs
    });
  } catch (error: any) {
    setLogsData({
      migrationName: migration.name,
      migrationId: migration.id,
      error: error.message,
      logs: []
    });
  } finally {
    setLoadingLogs(false);
  }
};
```

**Logs Modal:**
- Shows loading spinner while fetching
- Displays logs in a scrollable container
- Shows log level, stage, message, and timestamp
- Color-codes log levels (INFO, WARNING, ERROR)

### Enhanced Log Display

The logs modal now shows:
- **Transfer progress**: "Starting GCS to S3 transfer stage"
- **Configuration**: GCS and S3 bucket details
- **Credentials**: Decryption status
- **Transfer stats**: Files, data size, duration, speed
- **Errors**: Detailed error messages with context

## Log Levels and Stages

### Log Levels
- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages (most common)
- **WARNING**: Warning messages for non-critical issues
- **ERROR**: Error messages for failures
- **CRITICAL**: Critical issues requiring immediate attention

### Stages
- **migration**: Overall migration lifecycle
- **export**: BigQuery to GCS export
- **transfer**: GCS to S3 transfer
- **load**: S3 to Redshift load

## Benefits

### For Users
1. **Real-time visibility**: See what's happening during migration
2. **Progress tracking**: Know which stage is running
3. **Error diagnosis**: Clear error messages with context
4. **Performance metrics**: See transfer speeds and durations
5. **Historical logs**: Review past migrations

### For Developers
1. **Debugging**: Detailed logs for troubleshooting
2. **Monitoring**: Track migration health
3. **Performance analysis**: Identify bottlenecks
4. **Error tracking**: Categorize and analyze failures

### For Operations
1. **Monitoring**: Real-time migration status
2. **Alerting**: Identify issues quickly
3. **Reporting**: Generate migration reports
4. **Audit trail**: Complete history of operations

## Example Log Flow

### Successful Migration
```
1. [INFO] [migration] Starting migration execution using Pathway C
2. [INFO] [export] Starting BigQuery export: 5 tables from my_dataset
3. [INFO] [export] BigQuery export completed successfully - proceeding to transfer stage
4. [INFO] [transfer] Starting Pathway C transfer and load stages
5. [INFO] [transfer] Decrypting AWS credentials for S3 access
6. [INFO] [transfer] Starting GCS to S3 transfer stage
7. [INFO] [transfer] Transfer configuration: gs://my-bucket/export → s3://my-s3/data
8. [INFO] [transfer] AWS credentials decrypted successfully
9. [INFO] [transfer] GCP credentials loaded successfully
10. [INFO] [transfer] Initializing GCS to S3 transfer service
11. [INFO] [transfer] Starting file transfer from GCS to S3 - this may take several minutes
12. [INFO] [transfer] Transfer completed: 150/150 files (2.45 GB) in 5.2m
13. [INFO] [transfer] Transfer checkpoint saved - proceeding to load stage
14. [INFO] [load] Pathway C execution completed successfully - migration finished
```

### Failed Migration
```
1. [INFO] [migration] Starting migration execution using Pathway C
2. [INFO] [export] Starting BigQuery export: 5 tables from my_dataset
3. [INFO] [export] BigQuery export completed successfully - proceeding to transfer stage
4. [INFO] [transfer] Starting Pathway C transfer and load stages
5. [INFO] [transfer] Decrypting AWS credentials for S3 access
6. [ERROR] [transfer] Failed to decrypt AWS credentials: Invalid encryption key
7. [ERROR] [load] Pathway C execution failed - check logs for details
```

## Testing

### View Logs in UI
1. Navigate to http://localhost:3000/migrations
2. Click the three-dot menu on any migration
3. Click "View Logs"
4. See all logs with timestamps, levels, and messages

### API Testing
```bash
# Get logs for migration ID 123
curl -X GET "http://localhost:8000/api/bq-redshift-migrations/123/logs" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Filter by log level
curl -X GET "http://localhost:8000/api/bq-redshift-migrations/123/logs?level=ERROR" \
  -H "Authorization: Bearer YOUR_TOKEN"

# Limit results
curl -X GET "http://localhost:8000/api/bq-redshift-migrations/123/logs?limit=50" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Files Modified

1. **backend/services/bq_redshift_migration/orchestrator.py**
   - Enhanced `_execute_migration()` with database logging
   - Added logs for each stage transition
   - Added error logging with metadata

2. **backend/services/bq_redshift_migration/pathway_c.py**
   - Added `_log_to_db()` helper method
   - Enhanced `_execute_transfer_stage()` with detailed logging
   - Added validation error logging
   - Added transfer statistics logging

3. **backend/services/bq_redshift_migration/gcs_to_s3_transfer.py**
   - Already enhanced with detailed console logging
   - Per-file progress tracking
   - Real-time statistics
   - Human-readable formatting

## Future Enhancements

1. **Real-time log streaming**: WebSocket support for live log updates
2. **Log filtering**: Filter by stage, level, time range in UI
3. **Log export**: Download logs as CSV or JSON
4. **Log search**: Full-text search across log messages
5. **Log aggregation**: Summary statistics and charts
6. **Alerting**: Email/Slack notifications for errors

## Conclusion

The production logging system now provides comprehensive visibility into migration operations with:
- ✅ Database storage for all logs
- ✅ API endpoint for log retrieval
- ✅ Frontend UI for log viewing
- ✅ Detailed transfer progress tracking
- ✅ Error diagnosis with context
- ✅ Performance metrics
- ✅ Complete audit trail

Users can now monitor migrations in real-time and troubleshoot issues effectively through the UI.
