# Assessment Creation Fix - Complete

## Issue
When creating a new assessment, the system was throwing an error:
```
'ConnectionRepository' object has no attribute 'get_decrypted_connection_string'
```

## Root Cause
The `create_assessment` endpoint in `backend/routers/assessment_router.py` was trying to call a method that doesn't exist in the `ConnectionRepository` class:

```python
connection_string = connection_repo.get_decrypted_connection_string(source_conn.id)
```

The `ConnectionRepository` only has these methods:
- `get_by_id(connection_id)`
- `list_connections()`
- `get_by_type(connection_type)`
- `get_by_database(database)`

## Solution
Removed the unnecessary call to `get_decrypted_connection_string` since:
1. We don't need the decrypted connection string at assessment creation time
2. The connection parameters are already available in `source_conn.connection_params`
3. The background task uses `connection_params` directly when initializing the BigQuery service

### Code Change
**File**: `backend/routers/assessment_router.py`

**Before**:
```python
# Get connection details for BigQuery
# Note: This works for any source database, but BigQuery is the primary use case
connection_string = connection_repo.get_decrypted_connection_string(source_conn.id)

# Parse project ID or database name from connection
project_id = source_conn.database  # Use database name as project identifier
```

**After**:
```python
# Get project ID from source connection
# For BigQuery, the database field contains the project ID
# For other databases, use the database name as identifier
project_id = source_conn.database or f"connection-{source_conn.id}"
```

## Verification

### Test Assessment Creation
```bash
curl -X POST http://localhost:8000/api/assessments/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test" \
  -d '{"source_connection_id": 6, "target_connection_id": 7}'
```

### Response
```json
{
  "id": 4,
  "source_connection_id": 6,
  "target_connection_id": 7,
  "project_id": "bigquery",
  "status": "pending",
  "started_at": "2026-02-14T10:49:56.019161",
  "completed_at": null,
  "error_message": null,
  "total_datasets": 0,
  "total_tables": 0,
  "total_views": 0,
  "total_routines": 0,
  "total_ml_models": 0,
  "total_size_mb": 0.0,
  "created_by": "current_user",
  "workspace_id": 1
}
```

✅ Assessment created successfully!

## How It Works Now

### 1. Assessment Creation (Synchronous)
```python
@router.post("/", response_model=AssessmentResponse)
async def create_assessment(request, background_tasks, db):
    # Validate connections exist
    source_conn = connection_repo.get_by_id(request.source_connection_id)
    target_conn = connection_repo.get_by_id(request.target_connection_id)
    
    # Get project ID from connection
    project_id = source_conn.database or f"connection-{source_conn.id}"
    
    # Create assessment record with 'pending' status
    assessment = assessment_repo.create_assessment(...)
    
    # Start background task
    background_tasks.add_task(run_assessment_background, ...)
    
    # Return immediately
    return assessment
```

### 2. Background Metadata Collection (Asynchronous)
```python
async def run_assessment_background(assessment_id, source_connection_id, target_connection_id):
    # Get connection with parameters
    source_conn = connection_repo.get_by_id(source_connection_id)
    
    # Initialize BigQuery service with connection params
    bq_service = BigQueryAssessmentService(source_conn.connection_params)
    
    # Run full assessment (collects all 13 metadata categories)
    await bq_service.run_full_assessment(assessment_id, db)
```

## Files Modified
1. ✅ `backend/routers/assessment_router.py` - Removed invalid method call

## Status
✅ **COMPLETE** - Assessment creation now works correctly

## Next Steps
1. Test assessment creation via UI
2. Monitor background task execution
3. Verify metadata collection completes successfully
4. Check assessment status updates from 'pending' → 'running' → 'completed'

## Notes
- Assessment creation is now synchronous (returns immediately)
- Metadata collection runs in background
- Status updates: pending → running → completed/failed
- Connection parameters are used directly (no decryption needed at this stage)
- Project ID is extracted from the connection's database field
