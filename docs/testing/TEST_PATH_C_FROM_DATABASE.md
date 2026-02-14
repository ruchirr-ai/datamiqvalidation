# Test Path C Migration from Database

## Overview
This guide shows how to test Path C (BigQuery → GCS → S3) migration using data from the database.

## What Changed
- **Removed**: GCP Storage Transfer Service (was failing)
- **Added**: Simple download-and-upload approach
- **Benefit**: More reliable, easier to debug, works with all file sizes

## Prerequisites

1. **Backend running**:
   ```bash
   cd backend
   source .venv/bin/activate
   uvicorn main:app --reload
   ```

2. **Environment variables set** (in `backend/.env`):
   ```
   DATABASE_URL=postgresql://...
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcp-credentials.json
   ```

3. **Migration created** via UI with Path C configuration

## Step 1: List Available Migrations

```bash
cd backend
source .venv/bin/activate
python test_path_c_from_db.py --list
```

This will show all Path C migrations in the database:
```
================================================================================
PATH C MIGRATIONS IN DATABASE
================================================================================

ID: 1
Name: Test Migration
Status: pending
Source: my-project.my_dataset
GCS: gs://my-bucket/exports/
S3: s3://my-s3-bucket/data/
Created: 2026-02-09 10:30:00
================================================================================
```

## Step 2: Run Migration Test

Use the migration ID from step 1:

```bash
python test_path_c_from_db.py --migration-id 1
```

## What the Test Does

### Stage 1: Export BigQuery to GCS
- Reads source configuration from database
- Exports each table to GCS
- Uses configured format (AVRO/CSV/JSON) and compression
- Logs progress for each table

### Stage 2: Transfer GCS to S3
- Downloads files from GCS to temporary directory
- Uploads files to S3
- Maintains directory structure
- Optionally deletes source files after transfer
- Shows detailed progress

### Stage 3: Verification
- Lists files in S3 bucket
- Confirms successful transfer
- Shows file sizes and counts

## Expected Output

```
================================================================================
PATH C TEST: BIGQUERY → GCS → S3 (FROM DATABASE)
================================================================================
Fetching migration ID: 1
✓ Found migration: Test Migration
  Pathway: C
  Status: pending

✓ Source connection: BigQuery Production (bigquery)

================================================================================
MIGRATION CONFIGURATION
================================================================================
Source Project: my-project
Source Dataset: my_dataset
Source Tables: ["customers", "orders"]
GCS Bucket: my-bucket
GCS Path: exports/migration-1
S3 Bucket: my-s3-bucket
S3 Path: data/migration-1
Export Format: AVRO
Compression: GZIP
Delete After Transfer: False
================================================================================

================================================================================
STAGE 1: EXPORT FROM BIGQUERY TO GCS
================================================================================

Exporting table: customers
✓ Exported 10,000 rows
  Files: gs://my-bucket/exports/migration-1/customers/*.avro

Exporting table: orders
✓ Exported 50,000 rows
  Files: gs://my-bucket/exports/migration-1/orders/*.avro

================================================================================
STAGE 1 COMPLETE: BIGQUERY EXPORT
================================================================================
Tables Exported: 2
Total Rows: 60,000
================================================================================

================================================================================
STAGE 2: TRANSFER FROM GCS TO S3
================================================================================
Source: gs://my-bucket/exports/migration-1
Destination: s3://my-s3-bucket/data/migration-1
Delete source after transfer: False
================================================================================
✓ Found 4 files to transfer
Using temporary directory: /tmp/tmpxyz123

[1/4] Transferring: exports/migration-1/customers/000000000000.avro
  Downloading from GCS...
  ✓ Downloaded 1,234,567 bytes
  Uploading to S3: s3://my-s3-bucket/data/migration-1/customers/000000000000.avro
  ✓ Uploaded to S3
  ✓ Transfer complete

[2/4] Transferring: exports/migration-1/customers/000000000001.avro
  ...

================================================================================
TRANSFER COMPLETE
================================================================================
Files found: 4
Files transferred: 4
Bytes transferred: 5,234,567
Files failed: 0
================================================================================

================================================================================
VERIFICATION
================================================================================
Checking S3 bucket: s3://my-s3-bucket/data/migration-1
✓ Found 4 files in S3:
  - data/migration-1/customers/000000000000.avro (1,234,567 bytes)
  - data/migration-1/customers/000000000001.avro (1,123,456 bytes)
  - data/migration-1/orders/000000000000.avro (1,456,789 bytes)
  - data/migration-1/orders/000000000001.avro (1,419,755 bytes)
================================================================================

================================================================================
✓ PATH C TEST COMPLETED SUCCESSFULLY
================================================================================
Migration ID: 1
Migration Name: Test Migration
Tables Exported: 2
Total Rows: 60,000
Files Transferred: 4
Bytes Transferred: 5,234,567
Status: SUCCESS
================================================================================
```

## Troubleshooting

### No migrations found
```bash
# Check database connection
psql $DATABASE_URL -c "SELECT id, migration_name, pathway FROM migrations_bq_redshift;"

# Create a migration via UI first
```

### GCP authentication error
```bash
# Check credentials file exists
ls -la $GOOGLE_APPLICATION_CREDENTIALS

# Test GCP access
gcloud auth application-default login
```

### AWS authentication error
```bash
# Check AWS credentials in migration record
# Verify AWS secret key is encrypted properly
# Test AWS access
aws s3 ls s3://your-bucket/
```

### Files not appearing in S3
```bash
# Check S3 bucket and path
aws s3 ls s3://your-bucket/your-path/ --recursive

# Check AWS credentials are correct
# Check S3 bucket permissions
```

### Transfer fails
```bash
# Check backend logs
tail -100 backend/server.log | grep -i "transfer"

# Check GCS files exist
gsutil ls gs://your-bucket/your-path/

# Check network connectivity
# Check temporary directory has space
df -h /tmp
```

## Verify Files in S3

After successful transfer:

```bash
# List all files
aws s3 ls s3://your-bucket/your-path/ --recursive

# Check file sizes
aws s3 ls s3://your-bucket/your-path/ --recursive --human-readable

# Download a sample file to verify
aws s3 cp s3://your-bucket/your-path/table/file.avro /tmp/test.avro
```

## Next Steps

1. **Test with UI**: Create migration via UI and run it
2. **Monitor progress**: Watch backend logs during migration
3. **Verify data**: Check row counts match between BigQuery and files
4. **Load to Redshift**: Implement Stage 3 (Redshift COPY)

## Key Improvements

### Before (Storage Transfer Service)
- Required GCP project configuration
- Required AWS region selection
- Complex job creation and monitoring
- Failed silently in some cases
- Hard to debug

### After (Download and Upload)
- Simple, direct approach
- Works with any GCS/S3 configuration
- Clear progress logging
- Easy to debug
- Reliable for all file sizes

## Performance Notes

- **Small datasets** (< 1GB): Very fast, completes in seconds
- **Medium datasets** (1-10GB): Completes in minutes
- **Large datasets** (> 10GB): May take longer, but reliable
- **Network speed**: Transfer speed depends on your network bandwidth
- **Temporary storage**: Requires disk space for temporary files

## Files Modified

1. `backend/test_path_c_from_db.py` - New test script
2. `backend/services/bq_redshift_migration/pathway_c.py` - Updated transfer stage
3. `backend/services/bq_redshift_migration/gcs_to_s3_transfer.py` - Already using download/upload

## Success Criteria

✓ Migration reads configuration from database
✓ BigQuery export completes successfully
✓ Files appear in GCS bucket
✓ Files transfer from GCS to S3
✓ Files appear in S3 bucket with correct structure
✓ File sizes match between GCS and S3
✓ No errors in logs
