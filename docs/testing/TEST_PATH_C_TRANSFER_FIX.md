# Test Path C Transfer Fix

## What Was Fixed
The transfer stage was being skipped because pathway_c was using shard-based checkpoint logic when it should use simple checkpoint_data flags. Now it properly checks if export is done and executes the transfer stage.

## Quick Test Steps

### 1. Create a New Path C Migration

1. Go to Migrations page
2. Click "Create Migration"
3. Fill in the wizard:
   - **Step 1**: Select BigQuery connection, choose dataset and tables
   - **Step 2**: Select "Path C - CLI/Legacy" 
   - **Step 3**: Configure:
     - GCS Bucket: `bq_data_transfer_rs`
     - GCS Path: `staging`
     - S3 Bucket: `your-s3-bucket-name`
     - S3 Path: `path-c-test`
     - AWS Access Key ID: (your key)
     - AWS Secret Access Key: (your secret)
     - Export Format: PARQUET
     - Compression: NONE
     - ✓ Overwrite existing files
     - ✓ Delete source after transfer (optional)
   - **Step 4**: Schedule = "Run Once"
4. Click "Create Migration"

### 2. Monitor the Migration

Watch the backend logs in real-time:
```bash
tail -f backend/server.log | grep -E "(MIGRATION|TRANSFER|pathway_c|GCS|S3)"
```

You should see:
```
=== Starting Migration Execution: X (Pathway C) ===
Step 1: Exporting data from BigQuery to GCS
✓ BigQuery export completed successfully
Step 2: Executing Pathway C transfer and load stages
================================================================================
STARTING PATH C MIGRATION X
================================================================================
Source: BigQuery → GCS
Transfer: GCS → S3 (Storage Transfer Service)
Load: S3 → Redshift
================================================================================
Checkpoint Status:
  Export: ✓ Completed
  Transfer: ✗ Pending
  Load: ✗ Pending
================================================================================
Starting TRANSFER stage
================================================================================
MIGRATION X: TRANSFER STAGE
================================================================================
Project ID: assessiq-484512
Source: gs://bq_data_transfer_rs/staging
Destination: s3://your-bucket/path-c-test
AWS Access Key: AKIA...
Overwrite Existing: True
Delete Source: False
Decrypting AWS secret access key...
✓ AWS secret key decrypted successfully
Creating Storage Transfer Service job...
✓ Transfer job created: transferJobs/...
Running transfer job...
✓ Transfer job started
Monitoring transfer progress...
(This may take several minutes depending on data size)
================================================================================
✓ TRANSFER COMPLETED SUCCESSFULLY
================================================================================
Transfer Statistics:
  Objects Found: 2
  Bytes Found: 334
  Objects Copied: 2
  Bytes Copied: 334
Completed At: 2026-02-09T...
================================================================================
✓ Transfer checkpoint saved to database
Cleaning up transfer job...
✓ Transfer job deleted
Starting LOAD stage
================================================================================
MIGRATION X: LOAD STAGE
================================================================================
⚠ LOAD STAGE NOT YET IMPLEMENTED
================================================================================
✓ Load checkpoint saved to database
================================================================================
✓ PATH C MIGRATION X COMPLETED SUCCESSFULLY
================================================================================
```

### 3. Verify Files in S3

Check that files actually appeared in S3:
```bash
aws s3 ls s3://your-bucket/path-c-test/ --recursive
```

You should see the transferred Parquet files:
```
2026-02-09 ... staging/sales_analytics/customers/customers_000000000000.parquet
2026-02-09 ... staging/sales_analytics/orders/orders_000000000000.parquet
```

### 4. Check Checkpoint Data

Verify the checkpoint data includes transfer information:
```bash
python3 << 'EOF'
import sys
sys.path.insert(0, 'backend')
from database import db_instance
from models.bq_redshift_migration import MigrationBQRedshift
import json

with db_instance.get_session() as db:
    migration = db.query(MigrationBQRedshift).order_by(MigrationBQRedshift.id.desc()).first()
    if migration:
        print(f"Migration ID: {migration.id}")
        print(f"Name: {migration.migration_name}")
        print(f"Status: {migration.status}")
        print(f"Current Stage: {migration.current_stage}")
        print(f"\nCheckpoint Data:")
        if migration.checkpoint_data:
            print(json.dumps(migration.checkpoint_data, indent=2))
        else:
            print("No checkpoint data")
EOF
```

Expected output:
```json
{
  "export_results": [
    {
      "table": "assessiq-484512.sales_analytics.customers",
      "format": "PARQUET",
      "success": true,
      "num_rows": 3,
      "destination_uris": ["gs://bq_data_transfer_rs/staging/..."]
    },
    {
      "table": "assessiq-484512.sales_analytics.orders",
      "format": "PARQUET",
      "success": true,
      "num_rows": 4,
      "destination_uris": ["gs://bq_data_transfer_rs/staging/..."]
    }
  ],
  "export_completed_at": "2026-02-09T...",
  "transfer_completed_at": "2026-02-09T...",
  "transfer_job_name": "transferJobs/...",
  "transfer_stats": {
    "objects_found": 2,
    "bytes_found": 334,
    "objects_copied": 2,
    "bytes_copied": 334,
    "objects_failed": 0
  },
  "load_completed_at": "2026-02-09T...",
  "load_status": "pending_implementation"
}
```

### 5. Verify GCS Files (Optional)

Check that files exist in GCS source:
```bash
gsutil ls gs://bq_data_transfer_rs/staging/sales_analytics/
```

If you enabled "Delete source after transfer", these files should be gone after transfer completes.

## What to Look For

### ✅ Success Indicators
- Migration status shows "completed"
- Backend logs show "TRANSFER STAGE" execution
- Backend logs show "✓ TRANSFER COMPLETED SUCCESSFULLY"
- Checkpoint data has `transfer_completed_at` field
- Checkpoint data has `transfer_stats` with objects_copied > 0
- Files appear in S3 bucket at specified path
- No errors in backend logs

### ❌ Failure Indicators
- Migration completes but no transfer logs
- Checkpoint data missing `transfer_completed_at`
- No files in S3 bucket
- Errors about "Project ID is required"
- Errors about "AWS Access Key ID is required"
- Errors about "Failed to decrypt AWS secret key"
- Errors about "Failed to create transfer job"

## Troubleshooting

### If Transfer Stage Doesn't Execute
1. Check backend logs for errors
2. Verify migration status in database
3. Check checkpoint_data has export_completed_at
4. Restart backend server: `pkill -f uvicorn && cd backend && nohup .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload > server.log 2>&1 &`

### If Transfer Job Fails
1. Check GCP permissions for Storage Transfer Service
2. Verify AWS credentials are correct
3. Check S3 bucket exists and is accessible
4. Check GCS bucket has files to transfer
5. Review transfer_stats in checkpoint_data for error details

### If Files Don't Appear in S3
1. Check S3 bucket name and path are correct
2. Verify AWS credentials have S3 write permissions
3. Check transfer_stats shows objects_copied > 0
4. Try listing with different path: `aws s3 ls s3://bucket/ --recursive | grep staging`
5. Check if files are in a different location than expected

## Expected Timeline
- Export: 10-30 seconds (depends on table size)
- Transfer: 1-5 minutes (depends on data size and network)
- Load: Instant (not yet implemented, just marks as complete)
- Total: 2-6 minutes for small datasets

## Comparison: Before vs After Fix

### Before Fix
```
Migration Status: completed ✓
Checkpoint Data: {
  "export_results": [...],
  "export_completed_at": "..."
}
Backend Logs: Only export stage
S3 Files: None ✗
```

### After Fix
```
Migration Status: completed ✓
Checkpoint Data: {
  "export_results": [...],
  "export_completed_at": "...",
  "transfer_completed_at": "...",  ← NEW!
  "transfer_stats": {...}           ← NEW!
}
Backend Logs: Export + Transfer + Load stages
S3 Files: Present ✓
```

## Next Steps After Successful Test

1. **Implement Load Stage**: Add Redshift COPY command to actually load data
2. **Add Progress Tracking**: Show transfer progress in UI
3. **Add Validation**: Verify row counts match between GCS and S3
4. **Add Retry Logic**: Handle transient transfer failures
5. **Add Monitoring**: Track transfer performance metrics

## Files Modified
- `backend/services/bq_redshift_migration/pathway_c.py` - Fixed checkpoint logic

## Related Documentation
- `PATH_C_TRANSFER_BUG_FIXED.md` - Detailed explanation of the bug and fix
- `GCS_S3_TRANSFER_PATH_C_COMPLETE.md` - Original Path C implementation
- `TEST_GCS_S3_TRANSFER_GUIDE.md` - Testing guide for GCS to S3 transfer
