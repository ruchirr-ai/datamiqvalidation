# BigQuery Export Error Message Improvements

## Overview
Enhanced error logging and messaging for BigQuery to GCS export operations to provide detailed, actionable error information to users.

## Changes Made

### 1. Orchestrator Error Logging (`backend/services/bq_redshift_migration/orchestrator.py`)

#### Enhanced `_execute_bigquery_export` Method

**Connection Validation Errors:**
- ✓ Connection not found: Shows connection ID and suggests checking database
- ✓ Missing credentials: Lists available connection params to help debug
- ✓ Invalid credentials format: Shows JSON parse error details

**Configuration Errors:**
- ✓ Missing project ID: Clear message about where to specify it
- ✓ Missing GCS bucket: Prompts user to configure destination
- ✓ No tables selected: Reminds user to select tables

**Client Initialization Errors:**
- ✓ BigQuery client init failure: Shows project ID, error type, and details
- ✓ Logs successful initialization for confirmation

**Export Results Logging:**
- ✓ Successful exports: Logs each table with row count, byte count, file count, and job ID
- ✓ Failed exports: Detailed error per table with helpful hints:
  - Permission errors → Check BigQuery Data Viewer and Storage Object Creator permissions
  - Not found errors → Verify table exists in dataset and project
  - Quota errors → Suggests waiting or requesting quota increase
  - Bucket errors → Check bucket exists and service account has write access

**Summary Logging:**
- ✓ Overall progress: "X/Y tables exported successfully (Z% complete)"
- ✓ Failure summary: Lists all failed tables with error codes

**Exception Handling:**
- ✓ Catches all exceptions with full stack trace
- ✓ Logs exception type, message, and stack trace to database
- ✓ Uses error codes for categorization (e.g., CONNECTION_NOT_FOUND, MISSING_CREDENTIALS)

### 2. BigQuery Exporter Error Handling (`backend/services/bq_redshift_migration/bigquery_exporter.py`)

#### Enhanced `export_table` Method

**Table Access Errors:**
- ✓ Table not found (404): Shows full table path and suggests verification
- ✓ Permission denied (403): Lists required permission (bigquery.tables.get)

**Export Job Errors:**
- ✓ GCS permission errors: Lists required permissions (storage.objects.create, storage.objects.delete)
- ✓ Bucket not found: Suggests creating bucket or verifying name
- ✓ Quota exceeded: Suggests waiting or requesting quota increase
- ✓ Invalid configuration: Shows format and compression settings

#### Enhanced `export_tables` Method

**Progress Tracking:**
- ✓ Shows progress: "[1/5] Exporting table: customers"
- ✓ Success confirmation: "✓ [1/5] Table customers exported successfully"
- ✓ Failure details: "✗ [1/5] Failed to export table customers: [detailed error]"

**Error Capture:**
- ✓ Captures full error message from export_table
- ✓ Includes error_type for categorization
- ✓ Maintains backward compatibility with table_id field

## Error Codes Added

| Error Code | Description | User Action |
|------------|-------------|-------------|
| CONNECTION_NOT_FOUND | Source connection not in database | Verify connection ID |
| MISSING_CREDENTIALS | Service account key not found | Add credentials to connection |
| INVALID_CREDENTIALS_FORMAT | JSON parse error | Fix service account key JSON |
| MISSING_PROJECT_ID | Project ID not specified | Add project_id to config |
| CLIENT_INIT_FAILED | BigQuery client initialization failed | Check credentials and permissions |
| MISSING_GCS_BUCKET | GCS bucket not configured | Specify destination bucket |
| NO_TABLES_SELECTED | No tables to export | Select at least one table |
| TABLE_EXPORT_FAILED | Individual table export failed | See detailed error message |
| PARTIAL_EXPORT_FAILURE | Some tables failed to export | Check failed_tables list |
| EXPORT_EXCEPTION | Unexpected exception | Check stack trace |

## Log Metadata Structure

All error logs now include structured metadata for better debugging:

```json
{
  "connection_id": 123,
  "project_id": "my-project",
  "dataset": "my_dataset",
  "tables": ["table1", "table2"],
  "gcs_bucket": "my-bucket",
  "gcs_path": "exports",
  "format": "AVRO",
  "compression": "NONE",
  "error": "Permission denied",
  "exception_type": "GoogleAPIError",
  "stack_trace": "..."
}
```

## User-Facing Error Messages

### Before:
```
BigQuery export failed - migration cannot continue
```

### After:
```
✗ Table 'customers' export failed: BigQuery export job failed for table 'customers': 403 Permission denied
  → Service account lacks permission to write to GCS bucket 'my-export-bucket'
  → Required permissions: storage.objects.create, storage.objects.delete
  → Check bucket 'my-export-bucket' exists and service account has Storage Object Creator role
```

## How to View Detailed Errors

### 1. Via UI Logs Modal
- Click "View Logs" on migration in Migrations page
- Logs are displayed with level, stage, timestamp, and full message
- Error logs (ERROR, CRITICAL) are highlighted

### 2. Via API
```bash
GET /api/migrations/bq-redshift/{migration_id}/logs?level=ERROR
```

Response includes:
- `log_level`: ERROR, CRITICAL
- `stage`: export, transfer, load
- `message`: Full error message with hints
- `error_code`: Categorization code
- `log_metadata`: Structured context data
- `stack_trace`: Full stack trace for exceptions

### 3. Via Database
```sql
SELECT 
  log_level,
  stage,
  message,
  error_code,
  log_metadata,
  created_at
FROM migration_logs
WHERE migration_id = 123
  AND log_level IN ('ERROR', 'CRITICAL')
ORDER BY created_at DESC;
```

## Testing Recommendations

### Test Scenarios:
1. ✓ Missing service account key
2. ✓ Invalid JSON in service account key
3. ✓ Missing project ID
4. ✓ Table doesn't exist
5. ✓ No permission to read table
6. ✓ GCS bucket doesn't exist
7. ✓ No permission to write to GCS
8. ✓ Quota exceeded
9. ✓ Invalid export format
10. ✓ Network timeout

### Expected Behavior:
- Each error should have a clear, actionable message
- Error should be logged to database with metadata
- User should see helpful hints in UI
- Stack traces should be available for debugging

## Benefits

1. **Faster Debugging**: Users can immediately see what went wrong
2. **Self-Service**: Clear hints help users fix issues without support
3. **Better Monitoring**: Error codes enable alerting and metrics
4. **Audit Trail**: All errors logged with full context
5. **Developer Friendly**: Stack traces and metadata for deep debugging

## Next Steps

1. Test with real BigQuery export failures
2. Verify logs appear correctly in UI
3. Add similar detailed logging to transfer and load stages
4. Create monitoring dashboard for error codes
5. Document common errors in user guide
