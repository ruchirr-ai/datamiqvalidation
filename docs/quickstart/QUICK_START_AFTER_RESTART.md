# Quick Start After Server Restart

## What Changed
1. ✅ Migrations now run in background (won't block UI)
2. ✅ Added "View Logs" option in migration dropdown
3. ✅ Export format and compression saved to database
4. ✅ Real BigQuery export integrated

## Once Server Starts

### 1. Verify Server is Running
```bash
# Check backend
curl http://localhost:8000/health
# Should return: {"status":"healthy"}

# Check frontend
# Open: http://localhost:3000
```

### 2. Test the Flow

**Create Migration**:
1. Go to http://localhost:3000/migrations
2. Click "Create Migration"
3. Select BigQuery connection (ID 2, 3, or 6)
4. Select dataset: sales_analytics
5. Select table: assess_tbl
6. Format: AVRO, Compression: SNAPPY
7. GCS Bucket: (your bucket name)
8. Create

**Run Migration**:
1. Find migration in list
2. Click ⋮ menu
3. Click "Run Migration"
4. **Should see**: "Migration started successfully in background"
5. **Status should change**: pending → running

**View Logs**:
1. Click ⋮ menu again
2. Click "View Logs"
3. **Should see**: Modal with logs
4. **Logs should show**: Export progress, stages, timestamps

### 3. Monitor Progress

**Backend Logs**:
```bash
tail -f backend/server.log | grep -i "migration\|export"
```

**Database**:
```sql
-- Quick status check
SELECT id, migration_name, status, current_stage, progress_percentage
FROM migrations_bq_redshift
ORDER BY id DESC LIMIT 3;

-- View logs
SELECT log_level, stage, message
FROM migration_logs
WHERE migration_id = (SELECT MAX(id) FROM migrations_bq_redshift)
ORDER BY created_at DESC
LIMIT 10;
```

## Expected Behavior

### Before (Old):
- Click "Run Migration" → UI freezes → timeout → fails

### After (New):
- Click "Run Migration" → Immediate response → Status: running → Background execution → Logs available

## If Something Goes Wrong

### Migration stuck in 'pending'
```bash
# Check if backend is running
curl http://localhost:8000/health

# Check backend logs
tail -50 backend/server.log
```

### No logs showing
```bash
# Check if logs exist in database
psql -U manasakallakuri -d datamiq -c "SELECT COUNT(*) FROM migration_logs;"
```

### Export fails
```bash
# Check backend logs for error
tail -100 backend/server.log | grep -i error

# Check connection credentials
psql -U manasakallakuri -d datamiq -c "SELECT id, name, database FROM connections WHERE id IN (2,3,6);"
```

## Key Files to Watch

1. **Backend logs**: `backend/server.log`
2. **Browser console**: F12 → Console tab
3. **Database**: migrations_bq_redshift table
4. **GCS bucket**: gs://your-bucket/staging/

## Success Indicators

✅ Migration status changes to 'running' immediately
✅ Backend logs show "Starting migration X in background thread"
✅ Logs modal shows export progress
✅ Files appear in GCS bucket
✅ Migration completes with status 'completed' or 'failed'
