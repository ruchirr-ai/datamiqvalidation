# Quick Guide: Run Path C Test

## What This Does
Tests complete Path C migration (BigQuery → GCS → S3) using data from your database.

## Prerequisites
1. Backend running
2. Migration created via UI with Path C configuration
3. GCP and AWS credentials configured

## Step 1: List Migrations

```bash
cd backend
source .venv/bin/activate
python test_path_c_from_db.py --list
```

You'll see:
```
================================================================================
PATH C MIGRATIONS IN DATABASE
================================================================================

ID: 1
Name: My Test Migration
Status: pending
Source: my-project.my_dataset
GCS: gs://my-bucket/exports/
S3: s3://my-s3-bucket/data/
Created: 2026-02-09 10:30:00
================================================================================
```

## Step 2: Run Test

Use the ID from step 1:

```bash
python test_path_c_from_db.py --migration-id 1
```

## What Happens

### Stage 1: BigQuery → GCS
- Uses BigQueryExporter service (same as migration job)
- Exports each table to GCS
- Shows progress for each table
- Logs row counts and file locations

### Stage 2: GCS → S3
- Uses download and upload approach
- Downloads files from GCS to /tmp
- Uploads files to S3
- Shows progress for each file
- Optionally deletes source files

### Stage 3: Verification
- Lists files in S3 bucket
- Confirms successful transfer
- Shows file sizes

## Expected Output

```
================================================================================
PATH C TEST: BIGQUERY → GCS → S3 (FROM DATABASE)
================================================================================
Fetching migration ID: 1
✓ Found migration: My Test Migration
  Pathway: C
  Status: pending

================================================================================
STAGE 1: EXPORT FROM BIGQUERY TO GCS
================================================================================
=== Starting BigQuery Export ===
Table: my-project.my_dataset.customers
Destination: gs://my-bucket/exports/my_dataset/customers
Format: AVRO, Compression: GZIP
Table info: 10,000 rows, 1,234,567 bytes
Starting BigQuery extract job...
Job ID: job_abc123
✓ Export completed successfully

=== Starting BigQuery Export ===
Table: my-project.my_dataset.orders
...

================================================================================
STAGE 1 COMPLETE: BIGQUERY EXPORT
================================================================================
Tables Exported: 2/2
Total Rows: 60,000
Total Bytes: 5,234,567
================================================================================

================================================================================
STAGE 2: TRANSFER FROM GCS TO S3
================================================================================
================================================================================
STARTING GCS TO S3 TRANSFER
================================================================================
Source: gs://my-bucket/exports/
Destination: s3://my-s3-bucket/data/
✓ Found 4 files to transfer

[1/4] Transferring: exports/my_dataset/customers/customers_000000000000.avro.gz
  Downloading from GCS...
  ✓ Downloaded 1,234,567 bytes
  Uploading to S3: s3://my-s3-bucket/data/my_dataset/customers/customers_000000000000.avro.gz
  ✓ Uploaded to S3
  ✓ Transfer complete

[2/4] Transferring: ...

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
Checking S3 bucket: s3://my-s3-bucket/data/
✓ Found 4 files in S3:
  - data/my_dataset/customers/customers_000000000000.avro.gz (1,234,567 bytes)
  - data/my_dataset/customers/customers_000000000001.avro.gz (1,123,456 bytes)
  - data/my_dataset/orders/orders_000000000000.avro.gz (1,456,789 bytes)
  - data/my_dataset/orders/orders_000000000001.avro.gz (1,419,755 bytes)
================================================================================

================================================================================
✓ PATH C TEST COMPLETED SUCCESSFULLY
================================================================================
Migration ID: 1
Migration Name: My Test Migration
Tables Exported: 2/2
Total Rows: 60,000
Total Bytes: 5,234,567
Files Transferred: 4
Bytes Transferred: 5,234,567
Status: SUCCESS
================================================================================
```

## Verify Results

### Check GCS Files
```bash
gsutil ls gs://my-bucket/exports/ -r
```

### Check S3 Files
```bash
aws s3 ls s3://my-s3-bucket/data/ --recursive
```

### Compare Counts
```bash
# GCS file count
gsutil ls gs://my-bucket/exports/**/*.avro.gz | wc -l

# S3 file count
aws s3 ls s3://my-s3-bucket/data/ --recursive | grep avro.gz | wc -l
```

## Troubleshooting

### No migrations found
Create a migration via UI first (Migrations page → Create Migration → Path C)

### GCP authentication error
```bash
# Check credentials
echo $GOOGLE_APPLICATION_CREDENTIALS
ls -la $GOOGLE_APPLICATION_CREDENTIALS

# Test access
gcloud auth application-default login
```

### AWS authentication error
Check AWS credentials in migration record are correct

### Files not in S3
1. Check backend logs: `tail -100 backend/server.log`
2. Verify GCS files exist: `gsutil ls gs://bucket/path/`
3. Check AWS credentials
4. Check S3 bucket permissions

## Key Features

✓ Uses BigQueryExporter service (same as migration job)
✓ Uses download/upload for GCS → S3 (reliable)
✓ Reads all configuration from database
✓ Shows detailed progress
✓ Verifies files in S3
✓ Easy to debug

## Next Steps

After successful test:
1. Run migration via UI
2. Monitor progress in UI
3. Check files in S3
4. Implement Redshift COPY (Stage 3)
