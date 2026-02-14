# IAM Role ARN Fix - Complete

## Issue Identified

The IAM role ARN was being captured in the UI but **NOT being saved to the database** due to a missing field in the backend API.

### Root Cause

**Frontend** ✅ WORKING:
- `ConfigurationSetupStep.tsx` captures `iamRoleArn` in form data
- `CreateMigrationWizard.tsx` includes `iamRoleArn` in the form state
- UI sends `iamRoleArn` in the API request

**Backend** ❌ BROKEN:
- `CreateMigrationRequest` Pydantic model was **missing** the `iam_role_arn` field
- The migration creation endpoint was **not extracting** `iam_role_arn` from the request
- The migration record was being created **without** the IAM role ARN

## Fix Applied

### 1. Updated Pydantic Model

**File**: `backend/routers/bq_redshift_migration.py`

Added `iam_role_arn` field to `CreateMigrationRequest`:

```python
class CreateMigrationRequest(BaseModel):
    # ... existing fields ...
    
    # AWS Credentials for GCS → S3 Transfer (Path A & C)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    overwrite_existing_files: Optional[bool] = False
    delete_source_after_transfer: Optional[bool] = False
    
    # Redshift S3 Access (Required for COPY command)
    iam_role_arn: Optional[str] = None  # ← ADDED THIS
    
    # Scheduling (optional)
    schedule_type: Optional[str] = None
    cron_expression: Optional[str] = None
```

### 2. Updated Migration Creation Logic

Added `iam_role_arn` to the migration data dictionary:

```python
migration_data = {
    # ... existing fields ...
    
    # AWS credentials for GCS → S3 transfer
    'aws_access_key_id': req.aws_access_key_id,
    'aws_secret_access_key_encrypted': aws_secret_encrypted,
    'overwrite_existing_files': 'true' if req.overwrite_existing_files else 'false',
    'delete_source_after_transfer': 'true' if req.delete_source_after_transfer else 'false',
    
    # Redshift S3 access
    'iam_role_arn': req.iam_role_arn,  # ← ADDED THIS
    
    'schedule_type': req.schedule_type,
    'cron_expression': req.cron_expression,
    'created_by': current_user.user_id,
    'status': 'pending'
}
```

## Verification

### Before Fix
```sql
SELECT id, migration_name, iam_role_arn FROM migrations_bq_redshift WHERE id = 12;
-- Result: iam_role_arn = NULL
```

### After Fix
When you create a new migration with IAM role ARN:
```sql
SELECT id, migration_name, iam_role_arn FROM migrations_bq_redshift WHERE id = <new_id>;
-- Result: iam_role_arn = 'arn:aws:iam::123456789012:role/RedshiftS3Role'
```

## Testing the Fix

### 1. Restart Backend Server

```bash
cd backend
# Kill existing server
pkill -f "uvicorn main:app"

# Start server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Create New Migration

1. Go to Migrations page in UI
2. Click "Create Migration"
3. Fill in all fields including **IAM Role ARN** in Stage 3
4. Submit the migration

### 3. Verify in Database

```bash
cd backend
python -c "
from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift

db = next(get_db())
# Get the latest migration
migration = db.query(MigrationBQRedshift).order_by(MigrationBQRedshift.id.desc()).first()
print(f'Migration ID: {migration.id}')
print(f'Migration Name: {migration.migration_name}')
print(f'IAM Role ARN: {migration.iam_role_arn}')
db.close()
"
```

Expected output:
```
Migration ID: 13
Migration Name: test_migration
IAM Role ARN: arn:aws:iam::123456789012:role/RedshiftS3Role
```

### 4. Run Migration

The migration should now complete all 3 stages:
- ✅ Export: BigQuery → GCS
- ✅ Transfer: GCS → S3
- ✅ Load: S3 → Redshift (with IAM role)

## For Existing Migration 12

Migration 12 was created before this fix, so it doesn't have an IAM role ARN. You have two options:

### Option 1: Update Existing Migration

```sql
UPDATE migrations_bq_redshift 
SET iam_role_arn = 'arn:aws:iam::YOUR_ACCOUNT:role/RedshiftS3Role'
WHERE id = 12;
```

Then run:
```bash
cd backend
python fix_migration_12.py
```

### Option 2: Create New Migration

Create a new migration through the UI with all the same settings, but this time the IAM role ARN will be saved properly.

## Summary

**Problem**: IAM role ARN was being sent from frontend but not saved in backend
**Cause**: Missing field in Pydantic model and migration creation logic
**Fix**: Added `iam_role_arn` field to both the request model and migration data
**Status**: ✅ FIXED - New migrations will now save IAM role ARN correctly

## Files Modified

1. `backend/routers/bq_redshift_migration.py`
   - Added `iam_role_arn` to `CreateMigrationRequest` model
   - Added `iam_role_arn` to migration creation data

## Next Steps

1. Restart backend server
2. Test by creating a new migration with IAM role ARN
3. Verify the IAM role ARN is saved in database
4. Run the migration and confirm load stage completes successfully
