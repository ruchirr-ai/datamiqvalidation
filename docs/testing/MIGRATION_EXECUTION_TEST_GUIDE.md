# Migration Execution Testing Guide

## What Was Fixed

### 1. Enhanced Background Thread Execution
- Added comprehensive error handling in background thread
- Created initial log entry immediately when thread starts
- Added detailed logging at each step
- Proper database session management in thread
- Graceful error handling with status updates

### 2. Improved Error Visibility
- All exceptions in background thread are now caught and logged
- Migration status is updated to 'failed' if thread encounters errors
- Error details are stored in migration_logs table
- Stack traces are preserved for debugging

### 3. Real-Time Log Creation
- Initial log entry created as soon as thread starts
- Logs are committed to database immediately
- Each stage of execution creates log entries
- UI can fetch logs to see progress

## Testing Steps

### Step 1: Reset Migration to Pending
The migration has already been reset to pending status.

### Step 2: Start the Migration
1. Go to Migrations page in UI
2. Click three-dot menu on migration ID 2
3. Click "Run Migration"
4. Click "Restart" (to start fresh)
5. Confirm the restart

### Step 3: Monitor Execution
1. Immediately click three-dot menu again
2. Click "View Logs"
3. You should see:
   - Initial log: "Migration thread started - beginning execution"
   - Subsequent logs as migration progresses

### Step 4: Check Backend Logs
Monitor the backend terminal for:
```
=== Background thread started for migration 2 ===
✓ Initial log entry created
✓ Orchestrator initialized
Starting migration 2 (Pathway A)
...
```

### Step 5: Verify Database Updates
Check migration status and logs:
```sql
-- Check migration status
SELECT id, status, current_stage, progress_percentage, start_time 
FROM migrations_bq_redshift WHERE id = 2;

-- Check logs (should see new entries)
SELECT id, log_level, stage, message, created_at 
FROM migration_logs 
WHERE migration_id = 2 
ORDER BY created_at DESC 
LIMIT 10;
```

## Expected Behavior

### Successful Execution:
1. Migration status changes to 'running'
2. Initial log entry appears immediately
3. Background thread executes orchestrator.start_migration()
4. Logs are created during BigQuery export
5. Migration status updates to 'completed' or 'failed'
6. End time is set

### If Errors Occur:
1. Error is caught in background thread
2. Migration status set to 'failed'
3. Error log entry created with details
4. Stack trace preserved in log
5. Thread completes gracefully

## Common Issues & Solutions

### Issue: No logs appear
**Solution**: Check backend terminal for thread errors. The initial log should be created immediately.

### Issue: Migration stuck in 'running'
**Solution**: Check backend logs for thread exceptions. The enhanced error handling should prevent this.

### Issue: BigQuery export fails
**Solution**: Check migration_logs for error details. Verify BigQuery credentials and permissions.

## Debugging Commands

```bash
# Watch backend logs in real-time
tail -f backend/server.log

# Check migration status
psql -U manasakallakuri -d datamiq -c "SELECT * FROM migrations_bq_redshift WHERE id = 2;"

# Check recent logs
psql -U manasakallakuri -d datamiq -c "SELECT * FROM migration_logs WHERE migration_id = 2 ORDER BY created_at DESC LIMIT 5;"

# Reset migration if needed
psql -U manasakallakuri -d datamiq -c "UPDATE migrations_bq_redshift SET status = 'pending', current_stage = NULL, start_time = NULL WHERE id = 2;"
```

## Next Steps After Testing

1. If migration starts successfully → Test full BigQuery export
2. If errors occur → Review error logs and fix issues
3. Implement real-time log polling in UI (optional)
4. Add progress bar based on progress_percentage
5. Test with actual BigQuery data export
