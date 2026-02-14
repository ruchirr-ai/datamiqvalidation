# Migration Stuck in Running Status - FIXED ✅

## Problem

When running a migration from the UI:
- Migration gets stuck in "running" status
- No logs are generated
- Background thread starts but fails silently
- Migration never progresses

## Root Cause

**The main thread was setting migration status to `'running'` BEFORE starting the background thread**. This caused the orchestrator (running in the background thread) to refuse to start the migration because it checks if status is already `'running'` and returns immediately with a warning.

### The Bug

**File**: `backend/routers/bq_redshift_migration.py`

**Before (BROKEN)**:
```python
# Update status to running immediately
migration.status = 'running'
migration.start_time = datetime.utcnow()
db.commit()

# Start background thread
thread = threading.Thread(target=run_migration, daemon=True)
thread.start()
```

**What happened**:
1. Main thread sets status to `'running'`
2. Background thread starts
3. Background thread calls `orchestrator.start_migration()`
4. Orchestrator checks: `if migration.status == 'running': return False`
5. Background thread exits silently
6. Migration stuck in `'running'` status forever

## Solution Applied

### Fix 1: Don't Set Status Before Thread Starts

Let the orchestrator set the status to `'running'` when it actually starts executing.

**After (FIXED)**:
```python
# DON'T set status to running here - let orchestrator do it
# This was causing the orchestrator to refuse to run the migration

logger.info(f"Starting migration {migration_id} in background thread")

# Start background thread
thread = threading.Thread(target=run_migration, daemon=True)
thread.start()
```

### Fix 2: Configure Background Thread Logger

Added proper logging configuration so we can see what's happening in the background thread.

```python
def run_migration():
    from database import db_instance
    import sys
    
    bg_db = db_instance.SessionLocal()
    
    # Configure logger for background thread
    bg_logger = logging.getLogger(f"migration_{migration_id}")
    bg_logger.setLevel(logging.INFO)
    
    # Add handler if not already present
    if not bg_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        bg_logger.addHandler(handler)
```

### Fix 3: Better Error Logging

Improved error handling to ensure errors are always logged to database even if the logger fails.

```python
except Exception as e:
    bg_logger.error(f"CRITICAL ERROR: {e}", exc_info=True)
    
    # ALWAYS log to database even if logger fails
    try:
        import traceback
        error_log = MigrationLog(
            migration_id=migration_id,
            log_level='CRITICAL',
            stage='thread',
            message=f'Background thread failed: {str(e)}',
            stack_trace=traceback.format_exc()
        )
        bg_db.add(error_log)
        bg_db.commit()
    except Exception as log_error:
        print(f"CRITICAL: Migration {migration_id} failed: {e}")
        print(f"Failed to log error to database: {log_error}")
```

## Files Modified

- ✅ `backend/routers/bq_redshift_migration.py` - Fixed status setting and logger configuration

## Testing Steps

1. **Reset any stuck migrations**:
   ```sql
   UPDATE migrations_bq_redshift SET status='pending', start_time=NULL, current_stage=NULL WHERE status='running';
   ```

2. **Restart backend server**:
   ```bash
   ./START_BACKEND_HERE.sh
   ```

3. **Create and run a migration from UI**:
   - Go to Migrations page
   - Click "New" → "Create"
   - Fill in migration details
   - Click "Run Migration"

4. **Verify logs are generated**:
   ```sql
   SELECT log_level, stage, message, created_at 
   FROM migration_logs 
   WHERE migration_id=<your_migration_id> 
   ORDER BY created_at DESC;
   ```

5. **Check migration progresses**:
   - Status should change from `pending` → `running` → `completed` or `failed`
   - `current_stage` should show: `export` → `transfer` → `load`
   - Logs should show progress at each stage

## Expected Behavior After Fix

1. ✅ User clicks "Run Migration"
2. ✅ Migration starts with status `pending`
3. ✅ Background thread starts
4. ✅ Orchestrator sets status to `running`
5. ✅ Logs appear: "Starting migration (Pathway A)"
6. ✅ Logs appear: "Starting BigQuery export to GCS"
7. ✅ Export executes and logs progress
8. ✅ Migration completes with status `completed` or `failed`
9. ✅ All logs visible in database and UI

## What Was Wrong

The issue was a **race condition** where:
- Main thread: "I'll set this to running and start the background thread"
- Background thread: "Oh, it's already running? I'll just exit then"
- Result: Migration stuck in running status with no actual work being done

## What's Fixed Now

- Main thread: "I'll just start the background thread"
- Background thread: "Migration is pending, I'll start it and set status to running"
- Orchestrator: "Setting status to running, starting export..."
- Result: Migration executes properly with full logging

## Next Steps

1. Restart backend server to load the fixes
2. Test with a new migration
3. Verify logs are generated properly
4. Confirm migration completes successfully
