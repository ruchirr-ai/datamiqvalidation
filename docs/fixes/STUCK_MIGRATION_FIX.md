# Stuck Migration Fix - Complete

## ✅ Issue Resolved

Your stuck migration (ID: 2, "bq_rs_mig") has been reset from 'running' to 'failed' status. You can now resume it or create a new migration.

## What Was Done

### 1. Reset Stuck Migration
```sql
UPDATE migrations_bq_redshift
SET status = 'failed',
    end_time = NOW(),
    updated_at = NOW()
WHERE id = 2 AND status = 'running';
```

**Result**: Migration ID 2 is now in 'failed' status and can be resumed.

### 2. Added Cancel Button to UI
- Added "Cancel Migration" option in dropdown menu for running migrations
- Shows only when migration status is 'running'
- Confirms before cancelling
- Calls `/api/migrations/bq-redshift/{id}/cancel` endpoint

### 3. Created Reset Script
**File**: `backend/scripts/reset_stuck_migrations.py`

**Usage**:
```bash
# Reset all migrations stuck for more than 1 hour
cd backend
.venv/bin/python scripts/reset_stuck_migrations.py

# Reset all migrations stuck for more than 2 hours
.venv/bin/python scripts/reset_stuck_migrations.py --hours 2

# Reset specific migration by ID
.venv/bin/python scripts/reset_stuck_migrations.py --id 2
```

## How to Use

### Option 1: Resume the Failed Migration
1. Go to http://localhost:3000/migrations
2. Find migration "bq_rs_mig" (status: failed)
3. Click ⋮ menu
4. Click "Resume Migration"
5. Migration will restart from where it left off

### Option 2: Create New Migration
1. Click "Create Migration"
2. Fill in all details
3. Click "Create Migration"
4. Click "Run Migration"

### Option 3: Cancel Running Migration (Future)
1. If a migration is running and you want to stop it
2. Click ⋮ menu
3. Click "Cancel Migration"
4. Confirm cancellation
5. Migration will be cancelled and can be resumed later

## Manual Reset (If Needed)

If you need to manually reset a stuck migration in the future:

```sql
-- Check stuck migrations
SELECT id, migration_name, status, current_stage, updated_at
FROM migrations_bq_redshift
WHERE status = 'running'
ORDER BY updated_at DESC;

-- Reset specific migration
UPDATE migrations_bq_redshift
SET status = 'failed',
    end_time = NOW(),
    updated_at = NOW()
WHERE id = YOUR_MIGRATION_ID;

-- Or reset all stuck migrations older than 1 hour
UPDATE migrations_bq_redshift
SET status = 'failed',
    end_time = NOW(),
    updated_at = NOW()
WHERE status = 'running'
  AND updated_at < NOW() - INTERVAL '1 hour';
```

## Prevention

To prevent migrations from getting stuck:

1. **Monitor backend logs**:
   ```bash
   tail -f backend/server.log
   ```

2. **Check migration status regularly**:
   ```sql
   SELECT id, migration_name, status, current_stage, 
          EXTRACT(EPOCH FROM (NOW() - updated_at))/60 as minutes_since_update
   FROM migrations_bq_redshift
   WHERE status = 'running'
   ORDER BY updated_at DESC;
   ```

3. **Use the Cancel button** if migration is taking too long

4. **Check logs** if migration fails:
   - Click ⋮ menu → "View Logs"
   - Check backend logs: `tail -f backend/server.log`

## What's Available Now

### UI Features
- ✅ Run Migration (for pending migrations)
- ✅ Resume Migration (for paused/failed migrations)
- ✅ Cancel Migration (for running migrations) - NEW!
- ✅ View Logs (for all migrations)
- ✅ Test Migration (for all migrations)
- ✅ Update Migration (for all migrations)
- ✅ Delete Migration (for all migrations)

### Backend Features
- ✅ Background execution (non-blocking)
- ✅ BigQuery export integration
- ✅ Logs tracking
- ✅ Cancel endpoint
- ✅ Resume capability

### Scripts
- ✅ `reset_stuck_migrations.py` - Reset stuck migrations
- ✅ `update_connection_status.py` - Update connection status
- ✅ `setup_admin.py` - Setup admin user

## Quick Commands

```bash
# Check migration status
psql -U manasakallakuri -d datamiq -c "SELECT id, migration_name, status FROM migrations_bq_redshift ORDER BY id DESC LIMIT 5;"

# Reset stuck migration
cd backend
.venv/bin/python scripts/reset_stuck_migrations.py --id 2

# View logs
psql -U manasakallakuri -d datamiq -c "SELECT log_level, message FROM migration_logs WHERE migration_id = 2 ORDER BY created_at DESC LIMIT 10;"

# Check backend logs
tail -f backend/server.log
```

## Summary

Your migration is no longer stuck! You can now:
1. ✅ Resume the failed migration
2. ✅ Create a new migration
3. ✅ Cancel running migrations in the future
4. ✅ Use the reset script for future stuck migrations

The system is ready to use!
