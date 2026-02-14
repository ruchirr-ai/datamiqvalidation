# Test Migration from Database - Quick Guide

## What This Script Does

The `test_migration_from_db.py` script:
1. Connects to your PostgreSQL database
2. Lists all migrations
3. Lets you select a migration by **ID or name**
4. Loads all configuration from the database
5. Tests the complete data flow:
   - BigQuery → GCS export
   - GCS → S3 transfer
6. Verifies files at each stage
7. Offers cleanup

## Prerequisites

### 1. Google Cloud Authentication
You need to authenticate with Google Cloud first:

```bash
gcloud auth application-default login
```

This will open a browser window for you to authenticate.

### 2. AWS Credentials
Make sure your `backend/.env` file has AWS credentials:

```bash
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
```

Or the migration job should have them stored in the database.

## Running the Test

### Step 1: Authenticate with Google Cloud
```bash
gcloud auth application-default login
```

### Step 2: Run the Script
```bash
source backend/.venv/bin/activate
python backend/test_migration_from_db.py
```

### Step 3: Select Migration
When prompted, enter either:
- Migration ID: `9`
- Migration name: `test`

### Step 4: Confirm and Run
- Review the configuration displayed
- Type `y` to confirm and run the test
- Watch the progress

### Step 5: Cleanup (Optional)
- At the end, choose whether to cleanup test files
- Type `y` to delete test files from GCS and S3
- Type `n` to keep them for inspection

## Example Output

```
================================================================================
                  Test Migration Using Database Parameters
================================================================================

✓ Connected to database
ℹ Found 1 migration(s):

  1. test
     ID: 9
     Status: failed
     Pathway: A
     Dataset: sales_analytics
     Tables: orders, customers
     Created: 2026-02-09 01:22:47.890830


Enter migration ID or name to test: test

================================================================================
                          Migration Configuration
================================================================================

Migration Details:
  Name: test
  ID: 9
  Pathway: A
  Status: failed

Source (BigQuery):
  Connection: bq_demo
  Project: assessiq-484512
  Dataset: sales_analytics
  Tables: 2 table(s)
    - orders
    - customers

Storage Configuration:
  GCS Bucket: gs://bq_data_transfer_rs
  GCS Path: /staging
  S3 Bucket: s3://sk-manasa
  S3 Path: /staging
  Export Format: PARQUET
  Compression: NONE

Target (Redshift):
  Connection: redshift_demo
  Cluster: redshift-cluster
  Database: target_db
  Schema: public


Run test with this configuration? (y/n): y

[Step 1] Testing BigQuery Export
✓ Connected to BigQuery
ℹ Table: assessiq-484512.sales_analytics.orders
ℹ Rows: 1,250,000
ℹ Size: 450.00 MB
ℹ Export destination: gs://bq_data_transfer_rs/staging/test_20260209_143022/orders/*.parquet
ℹ Format: PARQUET
ℹ Compression: NONE
ℹ Starting export job...
✓ Export completed in 45.23 seconds
ℹ Job ID: job_abc123xyz
✓ Found 8 file(s) in GCS
ℹ Total size: 320.45 MB
ℹ   - staging/test_20260209_143022/orders/000000000000.parquet (40.12 MB)
ℹ   - staging/test_20260209_143022/orders/000000000001.parquet (40.08 MB)
  ... and 6 more files

[Step 2] Testing GCS to S3 Transfer
✓ Connected to S3 bucket: sk-manasa
ℹ Transferring 8 file(s) from GCS to S3...
ℹ [1/8] Downloading staging/test_20260209_143022/orders/000000000000.parquet...
ℹ [1/8] Uploading to s3://sk-manasa/staging/test_20260209_143022/orders/000000000000.parquet...
✓ [1/8] Transferred 40.12 MB
  ... (continues for all files)
✓ Transfer completed!
ℹ Files transferred: 8
ℹ Total size: 320.45 MB
ℹ Time: 125.67 seconds
ℹ Throughput: 2.55 MB/s
ℹ Verifying files in S3...
✓ Found 8 file(s) in S3
ℹ Total size: 320.45 MB

[Step 3] Cleanup Test Files

Do you want to clean up test files? (y/n): y
ℹ Deleting GCS files...
✓ Deleted 8 file(s) from GCS
ℹ Deleting S3 files...
✓ Deleted 8 file(s) from S3
✓ Cleanup completed

================================================================================
                      Test Completed Successfully!
================================================================================

✓ All stages completed successfully:
ℹ   ✓ BigQuery export to GCS
ℹ   ✓ GCS to S3 transfer
ℹ   ✓ File verification

ℹ Your migration configuration is working correctly!
ℹ You can now run the actual migration from the UI.
```

## What Gets Tested

### Your Migration Configuration
The script uses the exact configuration from your database:
- ✅ Source: BigQuery project, dataset, tables
- ✅ GCS: Bucket, path, export format, compression
- ✅ S3: Bucket, path
- ✅ AWS: Credentials (from migration or environment)

### Test Data
- Tests with the **first table** from your migration
- Creates files in a `test_{timestamp}` folder
- Doesn't affect your actual migration data

### File Locations
- **GCS**: `gs://{gcs_bucket}{gcs_path}/test_{timestamp}/{table}/`
- **S3**: `s3://{s3_bucket}{s3_path}/test_{timestamp}/{table}/`

## Troubleshooting

### Error: "Your default credentials were not found"
**Solution**: Run authentication command
```bash
gcloud auth application-default login
```

### Error: "Cannot access S3 bucket"
**Solution**: Check AWS credentials in `.env` or migration config
```bash
# In backend/.env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
```

### Error: "Table not found"
**Solution**: Verify the table exists in BigQuery
- Check dataset name: `sales_analytics`
- Check table names: `orders`, `customers`
- Use BigQuery console to verify

### Error: "Migration not found"
**Solution**: Check migration name or ID
- List migrations in the script output
- Use exact name (case-sensitive)
- Or use the numeric ID

## Next Steps After Successful Test

1. **Run the Actual Migration**:
   - Go to Migrations page in UI
   - Click "Run Migration" on your migration
   - Monitor progress

2. **Monitor in UI**:
   - Check status updates
   - View logs for detailed progress
   - Verify completion

3. **Verify in Redshift**:
   - Connect to Redshift cluster
   - Check if tables were created
   - Verify row counts

## Benefits of This Script

✅ **Uses Real Configuration**: Tests with your actual migration settings
✅ **Safe Testing**: Uses test folders, doesn't affect real data
✅ **Complete Flow**: Tests both BigQuery→GCS and GCS→S3
✅ **Easy Selection**: Use migration name instead of remembering IDs
✅ **Detailed Output**: See exactly what's happening at each step
✅ **Optional Cleanup**: Keep or delete test files

## Files Created

- **Script**: `backend/test_migration_from_db.py`
- **Guide**: `TEST_MIGRATION_FROM_DB_GUIDE.md` (this file)

## Quick Commands

```bash
# Authenticate with Google Cloud
gcloud auth application-default login

# Run the test
source backend/.venv/bin/activate
python backend/test_migration_from_db.py

# When prompted, enter: test
# Or enter: 9
```

That's it! The script will handle everything else.
