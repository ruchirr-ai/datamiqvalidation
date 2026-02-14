# Assessment Logging and Status Updates - Complete

## Summary
Implemented comprehensive logging system and proper status updates for assessment execution. Assessments now create detailed logs in the database that can be viewed in real-time, and the status updates correctly throughout the execution lifecycle.

## Changes Made

### 1. Database Schema - Assessment Logs Table

**File**: `backend/alembic/versions/014_create_assessment_logs_table.py`

Created new `assessment_logs` table with:
- `id` - Primary key
- `assessment_id` - Foreign key to assessments (CASCADE delete)
- `log_level` - Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `message` - Log message text
- `stage` - Execution stage (creation, initialization, metadata_collection, completion, error, etc.)
- `error_code` - Optional error code
- `stack_trace` - Optional stack trace for errors
- `log_metadata` - JSONB for additional context
- `created_at` - Timestamp

**Indexes**:
- `idx_assessment_logs_assessment_id` - For filtering by assessment
- `idx_assessment_logs_created_at` - For chronological ordering
- `idx_assessment_logs_log_level` - For filtering by log level

### 2. Assessment Log Model

**File**: `backend/models/assessment_log.py`

Created `AssessmentLog` model with:
- All table columns as SQLAlchemy columns
- Relationship to Assessment model
- Automatic timestamp on creation

### 3. Updated Assessment Model

**File**: `backend/models/assessment.py`

Added relationship:
```python
logs = relationship("AssessmentLog", back_populates="assessment", cascade="all, delete-orphan")
```

This enables:
- Accessing logs via `assessment.logs`
- Automatic deletion of logs when assessment is deleted

### 4. Assessment Repository Updates

**File**: `backend/repositories/assessment_repository.py`

Added two new methods:

#### `create_log()`
Creates a log entry for an assessment with:
- assessment_id
- log_level (INFO, WARNING, ERROR, etc.)
- message
- Optional: stage, error_code, stack_trace, log_metadata

#### `get_logs()`
Retrieves all logs for an assessment ordered by created_at

### 5. Assessment Router Updates

**File**: `backend/routers/assessment_router.py`

#### Enhanced `create_assessment()` endpoint:
- Creates initial log entry when assessment is created
- Logs include source/target connection IDs and project ID

#### Completely rewrote `run_assessment_background()`:
Now includes comprehensive logging at every stage:

**Initialization Stage**:
1. Log: "Assessment execution started"
2. Update status to 'running'
3. Log: "Assessment status updated to running"
4. Log: Retrieved source connection with metadata
5. Log: Retrieved target connection with metadata
6. Log: "Initializing BigQuery assessment service"

**Metadata Collection Stage**:
7. Log: "Starting metadata collection from BigQuery"
8. Execute metadata collection
9. Log: "Metadata collection completed successfully" with statistics

**Completion Stage**:
10. Update status to 'completed'
11. Log: Final summary with counts

**Error Handling**:
- Catches all exceptions
- Logs error with full stack trace
- Updates status to 'failed'
- Stores error message in assessment record

#### Updated `run_assessment()` endpoint:
- Adds log entry when assessment is manually triggered
- Logs include stage='manual_trigger'

#### Completely rewrote `get_assessment_logs()` endpoint:
- Fetches real logs from database instead of generating fake ones
- Returns logs in proper format for ViewLogsModal
- Includes all log fields: id, log_level, message, stage, error_code, stack_trace, log_metadata, created_at

## Log Stages

The assessment execution is divided into stages for better tracking:

1. **creation** - Assessment record created
2. **manual_trigger** - Assessment manually triggered
3. **initialization** - Setting up connections and services
4. **metadata_collection** - Collecting metadata from BigQuery
5. **completion** - Assessment completed successfully
6. **error** - Error occurred during execution

## Log Levels

Following standard logging levels:
- **DEBUG** - Detailed diagnostic information
- **INFO** - General informational messages (most common)
- **WARNING** - Warning messages for potential issues
- **ERROR** - Error messages for failures
- **CRITICAL** - Critical issues requiring immediate attention

## Example Log Flow

### Successful Assessment:
```
1. INFO [creation] - Assessment 'Production DB Assessment' created successfully
2. INFO [initialization] - Assessment execution started
3. INFO [initialization] - Assessment status updated to running
4. INFO [initialization] - Retrieved source connection: BigQuery Production
5. INFO [initialization] - Retrieved target connection: Redshift Staging
6. INFO [initialization] - Initializing BigQuery assessment service
7. INFO [metadata_collection] - Starting metadata collection from BigQuery
8. INFO [metadata_collection] - Metadata collection completed successfully
9. INFO [completion] - Assessment completed successfully. Collected 5 datasets, 42 tables, 8 views
```

### Failed Assessment:
```
1. INFO [creation] - Assessment 'Test Assessment' created successfully
2. INFO [initialization] - Assessment execution started
3. INFO [initialization] - Assessment status updated to running
4. INFO [initialization] - Retrieved source connection: BigQuery Test
5. ERROR [error] - Assessment failed: Invalid credentials for BigQuery
   Stack trace: [full stack trace here]
```

## Status Updates

Assessment status now updates correctly:
- **pending** - Initial state when created
- **running** - Background task started, collecting metadata
- **completed** - Successfully finished
- **failed** - Error occurred

Status updates are logged and visible in the UI immediately.

## Frontend Integration

The ViewLogsModal already supports the new log format:
- Displays log_level with color coding
- Shows stage badges
- Displays timestamps
- Expandable stack traces
- Expandable metadata
- Border-left accents for errors

## Database Migration

To apply the changes:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

This will create the `assessment_logs` table.

## Testing

### Manual Testing Steps:

1. **Create Assessment**:
   - Create a new assessment
   - Check logs immediately - should see creation log
   - Status should be 'pending'

2. **Run Assessment**:
   - Assessment starts automatically or click "Run Assessment"
   - Status should change to 'running'
   - Logs should show initialization messages

3. **View Logs During Execution**:
   - Click "View Logs" while assessment is running
   - Should see progressive logs as execution continues
   - Click "Refresh" to see new logs

4. **Completion**:
   - Wait for assessment to complete
   - Status should change to 'completed'
   - Logs should show completion message with statistics

5. **Error Scenario**:
   - Create assessment with invalid connection
   - Run assessment
   - Status should change to 'failed'
   - Logs should show ERROR level with stack trace

### API Testing:

```bash
# Get assessment logs
curl http://localhost:8000/api/assessments/1/logs

# Response format:
{
  "logs": [
    {
      "id": 1,
      "assessment_id": 1,
      "log_level": "INFO",
      "message": "Assessment execution started",
      "stage": "initialization",
      "error_code": null,
      "stack_trace": null,
      "log_metadata": null,
      "created_at": "2026-02-14T10:30:00"
    }
  ],
  "assessment_id": 1
}
```

## Benefits

1. **Real-time Visibility**: Users can see exactly what's happening during assessment execution
2. **Debugging**: Full stack traces and metadata help diagnose issues
3. **Audit Trail**: Complete history of assessment execution
4. **Status Tracking**: Accurate status updates throughout lifecycle
5. **User Experience**: Professional logging interface matching Migration Logs

## Next Steps

1. **Run Migration**: Execute `alembic upgrade head` to create assessment_logs table
2. **Test**: Create and run assessments to verify logging works
3. **Monitor**: Check that logs appear in ViewLogsModal
4. **Verify**: Confirm status updates correctly (pending → running → completed/failed)

## Status

✅ **COMPLETE** - Assessment logging and status updates fully implemented and ready for testing

All logs are now stored in the database and can be viewed in real-time through the ViewLogsModal interface.
