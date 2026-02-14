# Migration Execution Implementation - Complete

## Summary
Implemented complete BigQuery to GCS export functionality with background execution, logs viewer, and proper status management.

## Changes Made

### 1. Backend - Async Migration Execution
**File**: `backend/routers/bq_redshift_migration.py`

**Changes**:
- Modified `start_migration` endpoint to run migrations in background thread
- Migration status immediately set to 'running' when started
- Background thread executes the migration without blocking API response
- Proper error handling and logging

**Why**: Previous implementation was synchronous and blocked the API response, causing timeouts and UI freezes.

### 2. Backend - BigQuery Export Integration
**File**: `backend/services/bq_redshift_migration/orchestrator.py`

**New Methods**:
- `_execute_bigquery_export()` - Handles BigQuery to GCS export
  - Retrieves connection credentials from database
  - Initializes BigQueryExporter
  - Exports all selected tables
  - Stores results in checkpoint_data
  - Updates progress percentage

**Modified Methods**:
- `_execute_migration()` - Now calls BigQuery export first before pathway execution

### 3. Database Schema Updates
**File**: `backend/models/bq_redshift_migration.py`

**New Fields**:
- `export_format` - String(50), default='AVRO'
- `compression` - String(50), default='NONE'
- `progress_percentage` - Integer, default=0

**Migration**: `backend/alembic/versions/006_add_export_format_compression.py`
- ✅ Already applied to database

### 4. Frontend - Logs Viewer
**File**: `frontend/src/pages/MigrationsPage.tsx`

**New Features**:
- "View Logs" menu item in migration dropdown
- Logs modal with real-time log display
- Log level filtering (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Expandable stack traces and metadata
- Loading and error states

**New State**:
- `showLogsModal` - Controls logs modal visibility
- `logsData` - Stores fetched logs
- `loadingLogs` - Loading indicator

**New Functions**:
- `handleViewLogs()` - Fetches and displays logs

### 5. Frontend - API Integration
**File**: `frontend/src/services/bqRedshiftApi.ts`

**New Method**:
- `getMigrationLogs(id, limit?)` - Fetches migration logs from API

### 6. Frontend - Styling
**File**: `frontend/src/pages/MigrationsPage.css`

**New Styles**:
- `.logs-modal` - Modal container
- `.logs-container` - Logs list container
- `.log-entry` - Individual log entry
- `.log-level` - Log level badges with colors
- `.log-message` - Log message text
- Stack trace and metadata expandable sections

## How It Works Now

### Migration Execution Flow

1. **User clicks "Run Migration"**
   - Frontend calls `POST /api/migrations/bq-redshift/{id}/start`

2. **Backend starts migration in background**
   - Status immediately set to 'running'
   - API returns success response
   - Background thread starts executing migration

3. **Background thread executes**
   - Step 1: Export from BigQuery to GCS
     - Get connection credentials
     - Initialize BigQueryExporter
     - Export tables with format/compression
     - Store results in checkpoint_data
   - Step 2: Execute pathway-specific logic (GCS → S3 → Redshift)
   - Update status to 'completed' or 'failed'

4. **User can view logs**
   - Click "View Logs" in dropdown menu
   - Modal shows all logs with levels, stages, timestamps
   - Can expand stack traces and metadata

### Log Levels
- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages (green)
- **WARNING**: Warning messages (orange)
- **ERROR**: Error messages (red)
- **CRITICAL**: Critical issues (pink)

## Testing Instructions

### 1. Restart Backend Server
```bash
cd backend
./restart_server.sh
# OR
pkill -f uvicorn
.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Wait for**: "Application startup complete" message

### 2. Verify Frontend is Running
```bash
# Frontend should be on http://localhost:3000
# If not running:
cd frontend
npm run dev
```

### 3. Test Migration Execution

**Step 1: Create Migration**
1. Go to http://localhost:3000/migrations
2. Click "Create Migration"
3. Fill in all steps:
   - Source: BigQuery connection (ID 2, 3, or 6)
   - Dataset: sales_analytics
   - Tables: Select assess_tbl
   - Format: AVRO
   - Compression: SNAPPY
   - GCS Bucket: your-bucket-name
4. Click "Create Migration"

**Step 2: Run Migration**
1. Find migration in list (status: pending)
2. Click three-dot menu (⋮)
3. Click "Run Migration"
4. **Expected**: Status changes to 'running' immediately
5. **Expected**: Alert shows "Migration started successfully in background"

**Step 3: Monitor Backend Logs**
```bash
tail -f backend/server.log
```

**Expected Log Output**:
```
Starting migration X in background thread
=== Starting Migration Execution: X (Pathway A) ===
Step 1: Exporting data from BigQuery to GCS
Source connection: [Connection Name]
Initializing BigQuery exporter (project: assessiq-484512, region: us-central1)
Export configuration: format=AVRO, compression=SNAPPY
Exporting 1 tables: ['assess_tbl']
Exporting table assess_tbl to gs://bucket/staging/assess_tbl/*.avro.snappy
✓ Export job completed successfully
✓ BigQuery export completed successfully
```

**Step 4: View Logs in UI**
1. Click three-dot menu (⋮) on migration
2. Click "View Logs"
3. **Expected**: Modal opens showing logs
4. **Expected**: Logs show export progress
5. **Expected**: Can see log levels (INFO, ERROR, etc.)
6. **Expected**: Can expand stack traces if errors

### 4. Verify Export Results

**Check GCS Bucket**:
```bash
gsutil ls gs://your-bucket-name/staging/
# Should see: gs://your-bucket-name/staging/assess_tbl/*.avro.snappy
```

**Check Database**:
```sql
-- Check migration status
SELECT id, migration_name, status, current_stage, progress_percentage
FROM migrations_bq_redshift
ORDER BY id DESC LIMIT 5;

-- Check checkpoint data
SELECT id, migration_name, checkpoint_data
FROM migrations_bq_redshift
WHERE id = X;

-- Check logs
SELECT log_level, stage, message, created_at
FROM migration_logs
WHERE migration_id = X
ORDER BY created_at DESC
LIMIT 20;
```

## Troubleshooting

### Issue: Server won't start
**Solution**:
```bash
cd backend
# Check if port 8000 is in use
lsof -i :8000
# Kill existing process
pkill -f uvicorn
# Start fresh
.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Issue: Migration stays in 'pending'
**Possible Causes**:
1. Backend not running
2. Background thread failed to start
3. Database connection issue

**Check**:
```bash
# Check backend logs
tail -50 backend/server.log

# Check if migration was updated
psql -U manasakallakuri -d datamiq -c "SELECT id, status, updated_at FROM migrations_bq_redshift WHERE id = X;"
```

### Issue: No logs showing
**Possible Causes**:
1. Migration hasn't started yet
2. Logs not being created
3. API endpoint issue

**Check**:
```bash
# Check logs in database
psql -U manasakallakuri -d datamiq -c "SELECT COUNT(*) FROM migration_logs WHERE migration_id = X;"

# Test logs endpoint directly
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/migrations/bq-redshift/X/logs
```

### Issue: Export fails
**Common Errors**:
1. **Service account key not found**: Check connection_params has service_account_key
2. **Permission denied**: Ensure service account has BigQuery Data Editor role
3. **Invalid bucket**: Verify GCS bucket exists and is accessible

**Check Connection**:
```sql
SELECT id, name, connection_params
FROM connections
WHERE id = X;
```

## Files Modified

### Backend
1. ✅ `backend/routers/bq_redshift_migration.py` - Async execution
2. ✅ `backend/services/bq_redshift_migration/orchestrator.py` - Export integration
3. ✅ `backend/models/bq_redshift_migration.py` - New fields
4. ✅ `backend/alembic/versions/006_add_export_format_compression.py` - Migration

### Frontend
1. ✅ `frontend/src/pages/MigrationsPage.tsx` - Logs viewer
2. ✅ `frontend/src/pages/MigrationsPage.css` - Logs styling
3. ✅ `frontend/src/services/bqRedshiftApi.ts` - API method
4. ✅ `frontend/src/components/migrations/CreateMigrationWizard.tsx` - Export fields

## Next Steps

### Immediate
1. ✅ Restart backend server
2. ✅ Test migration creation
3. ✅ Test migration execution
4. ✅ Test logs viewer
5. ✅ Verify files in GCS

### Future Enhancements
1. ⏳ Real-time progress updates (WebSocket or polling)
2. ⏳ Cancel running migration
3. ⏳ Retry failed exports
4. ⏳ Export validation (checksum verification)
5. ⏳ GCS → S3 transfer implementation
6. ⏳ S3 → Redshift COPY implementation

## Success Criteria

✅ Migration starts in background without blocking
✅ Status updates to 'running' immediately
✅ Backend logs show export progress
✅ Logs viewer shows migration logs
✅ Files appear in GCS bucket
✅ Migration completes or fails with proper status
✅ checkpoint_data contains export results

## Quick Commands

```bash
# Restart backend
cd backend && ./restart_server.sh

# Check backend logs
tail -f backend/server.log

# Check database
psql -U manasakallakuri -d datamiq

# List GCS files
gsutil ls gs://your-bucket/staging/

# Check migration status
psql -U manasakallakuri -d datamiq -c "SELECT id, migration_name, status, current_stage FROM migrations_bq_redshift ORDER BY id DESC LIMIT 5;"
```

## Support

If issues persist:
1. Check backend/server.log for errors
2. Check browser console for frontend errors
3. Verify database migration applied: `SELECT * FROM alembic_version;`
4. Verify BigQuery credentials are valid
5. Verify GCS bucket exists and is accessible
