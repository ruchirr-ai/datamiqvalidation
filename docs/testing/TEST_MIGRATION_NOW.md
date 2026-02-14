# Test Migration Execution - Ready Now

## Status
✅ **Code Fixed and Deployed to Running Server**
✅ **Migration Reset to Pending**
✅ **Server Running on Port 8000**

## What Was Fixed

The orchestrator file has been updated in the running server directory with the service account key parsing fix. The server should auto-reload with the changes.

## Test Now via UI

### Step 1: Navigate to Migrations Page
Open: http://localhost:3000/migrations

### Step 2: Find Migration ID 2
- Look for migration named "bq_rs_mig"
- Status should show "pending"

### Step 3: Run Migration
1. Click the dropdown menu (⋮) next to the migration
2. Click "Run Migration"
3. Status should immediately change to "running"

### Step 4: Monitor Logs
1. Click the dropdown menu (⋮) again
2. Click "View Logs"
3. **Wait 5-10 seconds** for logs to appear
4. You should see:
   - "Migration thread started - beginning execution"
   - "Starting migration (Pathway A)"
   - "Starting BigQuery export to GCS"
   - "✓ Service account key parsed from JSON string" ← **This confirms the fix worked!**
   - "Initializing BigQuery exporter"
   - "Exporting N tables from dataset"

### Step 5: Check for Errors
If you see the error "'str' object has no attribute 'keys'" again, it means the server didn't reload. In that case:

1. **Stop the current server**:
   ```bash
   ps aux | grep uvicorn | grep -v grep
   # Note the PID (process ID)
   kill <PID>
   ```

2. **Start the server again**:
   ```bash
   cd /Users/manasakallakuri/Downloads/DataMIQ/backend
   nohup .venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000 > server.log 2>&1 &
   ```

3. **Wait 5 seconds** for server to start

4. **Test again** from Step 1

## Alternative: Test via API

If you prefer to test via API:

```bash
# Get your auth token from browser localStorage
# Then run:

curl -X POST http://localhost:8000/api/migrations/bq-redshift/2/start \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json"

# Check logs after 10 seconds:
curl http://localhost:8000/api/migrations/bq-redshift/2/logs \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" | jq '.logs[] | {level: .log_level, message: .message}'
```

## Expected Success Indicators

### ✅ Fix is Working If You See:
- Log message: "✓ Service account key parsed from JSON string"
- Log message: "Initializing BigQuery exporter (project: assessiq-484512)"
- Log message: "Exporting N tables from dataset"
- No error about "'str' object has no attribute 'keys'"

### ❌ Fix Not Applied If You See:
- Error: "BigQuery export failed: 'str' object has no attribute 'keys'"
- This means server didn't reload - follow Step 5 above

## About Real-Time Logs

**Important**: Logs may take 5-10 seconds to appear because:
1. Background thread needs to start
2. Database writes need to commit
3. UI polls every few seconds

**To see logs faster**:
- Keep the logs modal open
- Click "Refresh" button if available
- Or close and reopen the logs modal

## Troubleshooting

### Migration Stuck in "Running"
```sql
-- Check current status
psql -U manasakallakuri -d datamiq -c "SELECT id, status, current_stage, start_time FROM migrations_bq_redshift WHERE id = 2;"

-- Check recent logs
psql -U manasakallakuri -d datamiq -c "SELECT log_level, stage, message, created_at FROM migration_logs WHERE migration_id = 2 ORDER BY created_at DESC LIMIT 10;"

-- Reset if needed
psql -U manasakallakuri -d datamiq -c "UPDATE migrations_bq_redshift SET status = 'pending', current_stage = NULL, start_time = NULL, end_time = NULL WHERE id = 2;"
```

### Server Not Responding
```bash
# Check if server is running
ps aux | grep uvicorn | grep -v grep

# Check server health
curl http://localhost:8000/health

# If not running, start it:
cd /Users/manasakallakuri/Downloads/DataMIQ/backend
nohup .venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000 > server.log 2>&1 &
```

## Files Modified

**Running Server Directory**: `/Users/manasakallakuri/Downloads/DataMIQ/backend/`

**File Updated**:
- `services/bq_redshift_migration/orchestrator.py`

**Changes**:
1. Added JSON parsing for service account key (lines 493-508)
2. Fixed export_tables parameter names (line 556)
3. Fixed failed export error handling (line 571)

## Next Steps After Successful Test

Once you confirm the fix works (you see "✓ Service account key parsed from JSON string" in logs):

1. **Verify BigQuery Export Job**
   - Go to Google Cloud Console
   - Navigate to BigQuery → Job History
   - Look for export jobs from your project
   - Verify they're running/completed

2. **Check GCS Bucket**
   - Go to Cloud Storage
   - Open your configured GCS bucket
   - Check if files are being created in the specified path

3. **Monitor Progress**
   - Keep logs modal open
   - Watch for progress updates
   - Migration should complete with "completed" status

---

**Ready to Test**: Yes, go ahead and test via UI now!
**Server Status**: Running on port 8000
**Migration Status**: Reset to pending
**Code Status**: Fixed and deployed
