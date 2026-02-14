# Migrations List Issue - Fixed

## Problem
The migrations page in the UI was showing an error: "Failed to load migrations: Failed to fetch migrations"

The backend API was returning an error:
```
column migrations_bq_redshift.target_username does not exist
column migrations_bq_redshift.target_password_encrypted does not exist
```

## Root Cause
The database model (`MigrationBQRedshift`) still had `target_username` and `target_password_encrypted` columns defined, but these columns were never created in the database (or were removed in a previous migration).

These fields are no longer needed because:
1. The Redshift connection is selected in Step 1 of migration creation
2. Connection details are fetched from the `connections` table using `target_connection_id`
3. The UI was already updated to not collect these fields

## Solution

### 1. Created Migration to Remove Columns
Created `backend/alembic/versions/009_remove_redshift_credentials.py`:
- Drops `target_username` column
- Drops `target_password_encrypted` column
- These are no longer needed as we use `target_connection_id` instead

### 2. Updated Model
Updated `backend/models/bq_redshift_migration.py`:
- Removed `target_username` field
- Removed `target_password_encrypted` field
- Added comment explaining that `target_connection_id` is used instead

### 3. Fixed Migration 007
Fixed `backend/alembic/versions/007_update_pathway_constraint.py`:
- Added check to see if constraint exists before dropping it
- Prevents error when constraint doesn't exist

### 4. Ran Migrations
```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

Migrations applied successfully:
- ✅ 007: Update pathway constraint to A, B, C
- ✅ 008: Add redshift credentials
- ✅ 009: Remove Redshift credentials from migrations table

## Testing

### Backend API Test
Created `test_migrations_api.sh` to test the API:

```bash
./test_migrations_api.sh
```

**Result**: ✅ Success
- Login successful
- Migrations list API returns data correctly
- Found 1 migration in database

**Sample Response**:
```json
[
    {
        "id": 11,
        "workspace_id": 1,
        "migration_name": "bq_rs",
        "pathway": "B",
        "status": "failed",
        "current_stage": "export",
        "source_connection_name": "bq_demo",
        "target_connection_name": "redshift_demo",
        "start_time": "2026-02-08T22:13:22.285523",
        "last_run_at": "2026-02-08T22:13:37.841468",
        "created_at": "2026-02-09T03:43:19.457812",
        "updated_at": "2026-02-08T22:13:37.850002"
    }
]
```

### Frontend Test
To test the frontend:

1. **Navigate to**: http://localhost:3000/migrations

2. **Login** (if not already logged in):
   - Username: `admin`
   - Password: `AdminPass123!`

3. **Expected Result**: Migrations list should load successfully showing the migration from the database

## Files Modified

1. **backend/models/bq_redshift_migration.py**
   - Removed `target_username` and `target_password_encrypted` fields

2. **backend/alembic/versions/007_update_pathway_constraint.py**
   - Added check for constraint existence before dropping

3. **backend/alembic/versions/009_remove_redshift_credentials.py** (NEW)
   - Migration to drop unused columns

4. **test_migrations_api.sh** (NEW)
   - Test script to verify API functionality

## Architecture Notes

### Connection Management
The migration now properly uses the connection architecture:

1. **Step 1 (Connection Staging)**: User selects source and target connections
   - `source_connection_id` → references `connections` table
   - `target_connection_id` → references `connections` table

2. **Backend Execution**: When running migration, backend:
   - Fetches connection details from `connections` table using `target_connection_id`
   - Retrieves host, port, database, username, password from connection record
   - Uses these credentials for Redshift operations

3. **Benefits**:
   - Single source of truth for connection details
   - Easier to update connection credentials
   - Better security (credentials stored in one place)
   - Cleaner migration records

## Next Steps

1. ✅ Database schema updated
2. ✅ Model updated
3. ✅ Backend API working
4. ⚠️ Frontend needs user to login first
5. ⚠️ Verify frontend displays migrations correctly after login

## Servers Status

- **Backend**: Running on http://localhost:8000 (PID: 93918)
- **Frontend**: Running on http://localhost:3000 (PID: 4)

Both servers are running and ready for testing.

## Login Credentials

- **Username**: `admin`
- **Password**: `AdminPass123!`

These credentials are stored in `backend/.env` and can be used to login to the application.
