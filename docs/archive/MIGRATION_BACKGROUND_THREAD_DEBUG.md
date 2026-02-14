# Migration Background Thread Debug - Issue Found

## Problem Summary

When running a migration from the UI, the migration gets stuck in "running" status with no logs being generated. The background thread starts but then fails silently.

## Root Cause Analysis

### Evidence from Logs

1. **Server logs show**:
   - Background thread starts: `"Starting migration X in background thread"`
   - Thread confirmed started: `"✓ Background thread started for migration X"`
   - **NO logs after that** - thread crashes silently

2. **Database logs show**:
   - Only ONE log entry: `"Migration thread started - beginning execution"`
   - **NO subsequent logs** - orchestrator never executes

3. **Migration status**:
   - Status stuck at `running`
   - `current_stage` is `NULL` (never set to 'export')
   - `start_time` is set but no progress

### Root Cause

The background thread in `backend/routers/bq_redshift_migration.py` is failing silently because:

1. **Logger not configured**: The background thread creates a new logger `bg_logger = logging.getLogger(f"migration_{migration_id}")` but this logger is not configured with handlers, so logs go nowhere

2. **Exception swallowed**: Even though there's a try-catch, the exception logging might not work if the logger isn't configured

3. **Database session issue**: The background thread creates a new session `bg_db = db_instance.SessionLocal()` but there might be session conflicts

## The Failing Code

**File**: `backend/routers/bq_redshift_migration.py` (lines ~587-670)

```python
def run_migration():
    from database import db_instance
    bg_db = db_instance.SessionLocal()
    bg_logger = logging.getLogger(f"migration_{migration_id}")  # ❌ NOT CONFIGURED
    
    try:
        bg_logger.info(f"=== Background thread started for migration {migration_id} ===")
        
        # Create initial log entry
        initial_log = MigrationLog(...)
        bg_db.add(initial_log)
        bg_db.commit()
        bg_logger.info("✓ Initial log entry created")
        
        # Execute migration
        orchestrator = MigrationOrchestrator(bg_db)
        bg_logger.info("✓ Orchestrator initialized")
        
        success = orchestrator.start_migration(migration_id)  # ❌ FAILS HERE
        
    except Exception as e:
        bg_logger.error(f"CRITICAL ERROR: {e}", exc_info=True)  # ❌ LOGS GO NOWHERE
```

## Why It Fails

1. **Orchestrator checks status**: When `orchestrator.start_migration()` is called, it queries the migration and sees status is already `'running'` (set by the main thread before starting background thread)

2. **Returns False immediately**: Orchestrator returns `False` with warning "Migration X is already running"

3. **No error raised**: Since it's not an exception, just a return value, the try-catch doesn't catch it

4. **Thread exits silently**: Background thread completes without updating migration status back to failed/completed

## Solution

### Fix 1: Don't Set Status to Running Before Thread Starts

The main thread sets status to `running` BEFORE starting the background thread. This causes the orchestrator to refuse to run it.

**Current code** (WRONG):
```python
# Update status to running immediately
migration.status = 'running'
migration.start_time = datetime.utcnow()
db.commit()

# Start background thread
thread = threading.Thread(target=run_migration, daemon=True)
thread.start()
```

**Fixed code**:
```python
# DON'T set status here - let orchestrator do it
# Just start the thread
thread = threading.Thread(target=run_migration, daemon=True)
thread.start()
```

### Fix 2: Configure Background Thread Logger

Add proper logging configuration for the background thread:

```python
def run_migration():
    from database import db_instance
    import logging
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
    
    try:
        bg_logger.info(f"=== Background thread started for migration {migration_id} ===")
        # ... rest of code
```

### Fix 3: Better Error Handling

Ensure all errors are logged to database even if logger fails:

```python
except Exception as e:
    # Log to console
    bg_logger.error(f"CRITICAL ERROR: {e}", exc_info=True)
    
    # ALWAYS log to database
    try:
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
        print(f"Failed to log error to database: {log_error}")
```

## Testing Steps

1. Reset stuck migration: `UPDATE migrations_bq_redshift SET status='pending' WHERE id=4;`
2. Apply fixes to `backend/routers/bq_redshift_migration.py`
3. Restart backend server
4. Run migration from UI
5. Check logs appear in database: `SELECT * FROM migration_logs WHERE migration_id=4 ORDER BY created_at;`
6. Verify migration progresses through stages

## Files to Fix

1. `backend/routers/bq_redshift_migration.py` - Fix status setting and logger configuration
2. Test with migration ID 4

## Expected Behavior After Fix

1. Migration starts with status `pending`
2. Background thread starts
3. Orchestrator sets status to `running`
4. Logs appear: "Starting BigQuery export to GCS"
5. Export executes
6. Logs show progress
7. Migration completes or fails with proper status update
