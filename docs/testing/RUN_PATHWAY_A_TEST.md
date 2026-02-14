# Run Pathway A End-to-End Test

## Overview
This test script validates the complete Pathway A data flow:
1. **BigQuery → GCS**: Export table from BigQuery to Google Cloud Storage
2. **GCS → S3**: Transfer files from GCS to AWS S3 using Storage Transfer Service (or direct transfer as fallback)

## Prerequisites

### 1. Environment Variables
Ensure your `backend/.env` file has the following configured:

```bash
# BigQuery Configuration
BIGQUERY_PROJECT_ID=assessiq-484512

# GCS Configuration
GCS_BUCKET=bq_data_transfer_rs

# AWS Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_REGION=us-east-1
S3_BUCKET=your-s3-bucket-name
```

### 2. Google Cloud Authentication
Make sure you're authenticated with Google Cloud:

```bash
# Check current authentication
gcloud auth list

# If not authenticated, login
gcloud auth application-default login

# Set the project
gcloud config set project assessiq-484512
```

### 3. Python Dependencies
Install required packages:

```bash
cd backend
pip install google-cloud-bigquery google-cloud-storage google-cloud-storage-transfer boto3 python-dotenv
```

### 4. Permissions Required

#### Google Cloud Permissions
- BigQuery Data Viewer (to read tables)
- BigQuery Job User (to run export jobs)
- Storage Object Admin (to write to GCS)
- Storage Transfer Admin (optional, for Storage Transfer Service)

#### AWS Permissions
- S3 PutObject (to write to S3)
- S3 ListBucket (to verify files)

## Configuration

### Edit Test Parameters
Open `backend/test_pathway_a_end_to_end.py` and modify these variables at the top:

```python
# Test configuration (lines 20-25)
BIGQUERY_DATASET = 'analytics'  # Change to your dataset
BIGQUERY_TABLE = 'customers'    # Change to your table
```

**Important**: Make sure the table exists in your BigQuery project!

### Check Available Tables
To see what tables are available:

```bash
cd backend
python list_bq_datasets.py
```

Or use the BigQuery console:
https://console.cloud.google.com/bigquery?project=assessiq-484512

## Running the Test

### Method 1: Direct Execution
```bash
cd backend
python test_pathway_a_end_to_end.py
```

### Method 2: Make it Executable
```bash
cd backend
chmod +x test_pathway_a_end_to_end.py
./test_pathway_a_end_to_end.py
```

## What the Test Does

### Step 1: Test BigQuery Connection
- Connects to BigQuery
- Retrieves table metadata (row count, size, etc.)
- Displays table information

### Step 2: Export BigQuery to GCS
- Exports the specified table to GCS
- Uses AVRO format with SNAPPY compression
- Creates files in: `gs://bq_data_transfer_rs/test_exports/{timestamp}/`
- Shows export progress and statistics

### Step 3: Test GCS Connection
- Verifies GCS bucket access
- Lists exported files
- Shows file sizes

### Step 4: Test S3 Connection
- Verifies S3 bucket access
- Checks AWS credentials

### Step 5: Transfer GCS to S3
The script tries two methods:

**Method A: Storage Transfer Service (Preferred)**
- Creates a Storage Transfer Service job
- Transfers files in the background
- Faster for large datasets
- Requires additional GCP permissions

**Method B: Direct Transfer (Fallback)**
- Downloads from GCS and uploads to S3
- Works without Storage Transfer Service
- Slower but simpler
- Shows progress for each file

### Step 6: Verify S3 Files
- Lists files in S3
- Verifies file count and sizes
- Confirms successful transfer

### Step 7: Cleanup
- Prompts to delete test files
- Removes files from both GCS and S3
- Optional (you can keep files for inspection)

## Expected Output

```
================================================================================
           Pathway A End-to-End Test: BigQuery → GCS → S3
================================================================================

ℹ Test timestamp: 20260209_143022
ℹ BigQuery: assessiq-484512.analytics.customers
ℹ GCS: gs://bq_data_transfer_rs/test_exports/20260209_143022/
ℹ S3: s3://your-bucket/test_imports/20260209_143022/

[Step 1] Testing BigQuery Connection
✓ Connected to BigQuery project: assessiq-484512
ℹ Table: assessiq-484512.analytics.customers
ℹ Rows: 1,250,000
ℹ Size: 450.00 MB
ℹ Created: 2025-01-15 10:30:00
ℹ Modified: 2026-02-08 14:30:00

[Step 2] Exporting BigQuery Table to GCS
ℹ Export destination: gs://bq_data_transfer_rs/test_exports/20260209_143022/customers/*.avro
ℹ Format: AVRO
ℹ Compression: SNAPPY
ℹ Export job started, waiting for completion...
✓ Export completed in 45.23 seconds
ℹ Job ID: job_abc123xyz
✓ Found 8 file(s) in GCS
ℹ Total size: 320.45 MB
ℹ   - test_exports/20260209_143022/customers/000000000000.avro (40.12 MB)
ℹ   - test_exports/20260209_143022/customers/000000000001.avro (40.08 MB)
  ... and 6 more files

[Step 3] Testing GCS Connection
✓ Connected to GCS bucket: bq_data_transfer_rs
ℹ Location: US
ℹ Storage class: STANDARD

[Step 4] Testing S3 Connection
✓ Connected to S3 bucket: your-bucket
ℹ Region: us-east-1

[Step 5] Transferring Files from GCS to S3 (Direct Method)
ℹ Transferring 8 file(s)...
ℹ [1/8] Downloading test_exports/20260209_143022/customers/000000000000.avro...
ℹ [1/8] Uploading to s3://your-bucket/test_imports/20260209_143022/customers/000000000000.avro...
✓ [1/8] Transferred 40.12 MB
  ... (continues for all files)
✓ Transfer completed!
ℹ Files transferred: 8
ℹ Total size: 320.45 MB
ℹ Time: 125.67 seconds
ℹ Throughput: 2.55 MB/s

[Step 6] Verifying Files in S3
✓ Found 8 file(s) in S3
ℹ Total size: 320.45 MB
ℹ   - test_imports/20260209_143022/customers/000000000000.avro (40.12 MB)
  ... and 7 more files

[Step 7] Cleanup
⚠ Do you want to clean up test files? (y/n): y
ℹ Deleting GCS files...
✓ Deleted 8 file(s) from GCS
ℹ Deleting S3 files...
✓ Deleted 8 file(s) from S3
✓ Cleanup completed

================================================================================
                      Test Completed Successfully!
================================================================================
```

## Troubleshooting

### Error: "Failed to connect to BigQuery"
**Solution**: 
- Run `gcloud auth application-default login`
- Verify project ID in `.env` file
- Check you have BigQuery permissions

### Error: "GCS bucket does not exist"
**Solution**:
- Verify bucket name in `.env` file
- Check bucket exists: `gsutil ls gs://bq_data_transfer_rs`
- Ensure you have access to the bucket

### Error: "S3 bucket does not exist or is not accessible"
**Solution**:
- Verify S3 bucket name in `.env` file
- Check AWS credentials are correct
- Verify bucket exists in AWS Console
- Check IAM permissions for the AWS user

### Error: "Table not found"
**Solution**:
- Verify the table exists in BigQuery
- Check dataset and table names in the script
- Run `python list_bq_datasets.py` to see available tables

### Error: "Storage Transfer Service requires additional setup"
**Solution**:
- This is expected if Storage Transfer Service is not enabled
- The script will automatically fall back to direct transfer
- Direct transfer works fine, just slower for large datasets

### Slow Transfer Speed
**Causes**:
- Large table size
- Network bandwidth limitations
- Using direct transfer instead of Storage Transfer Service

**Solutions**:
- For large datasets, enable Storage Transfer Service
- Run test with a smaller table first
- Check network connectivity

## Verifying Results

### Check GCS Files
```bash
gsutil ls -lh gs://bq_data_transfer_rs/test_exports/
```

### Check S3 Files
```bash
aws s3 ls s3://your-bucket/test_imports/ --recursive --human-readable
```

### Download and Inspect a File
```bash
# From GCS
gsutil cp gs://bq_data_transfer_rs/test_exports/20260209_143022/customers/000000000000.avro .

# From S3
aws s3 cp s3://your-bucket/test_imports/20260209_143022/customers/000000000000.avro .
```

## Next Steps

After successful test:

1. **Test with Your Migration Job**:
   - Go to the Migrations page
   - Click "Run Migration" on your updated job
   - Monitor progress in the UI

2. **Check Migration Logs**:
   - Click "View Logs" in the migration menu
   - Verify each stage completed successfully

3. **Verify Data in Redshift**:
   - Connect to your Redshift cluster
   - Check if tables were created
   - Verify row counts match source

## Performance Benchmarks

### Small Table (< 100 MB)
- Export: 10-30 seconds
- Transfer: 20-60 seconds
- Total: ~1-2 minutes

### Medium Table (100 MB - 1 GB)
- Export: 30-120 seconds
- Transfer: 1-5 minutes
- Total: ~2-7 minutes

### Large Table (> 1 GB)
- Export: 2-10 minutes
- Transfer: 5-30 minutes
- Total: ~7-40 minutes

**Note**: Storage Transfer Service is significantly faster for large datasets.

## Cleanup

If you chose not to cleanup during the test, you can manually delete files:

### Delete GCS Files
```bash
gsutil -m rm -r gs://bq_data_transfer_rs/test_exports/
```

### Delete S3 Files
```bash
aws s3 rm s3://your-bucket/test_imports/ --recursive
```

## Support

If you encounter issues:
1. Check the error message carefully
2. Review the Troubleshooting section above
3. Check GCP and AWS console for more details
4. Verify all prerequisites are met
5. Try with a smaller table first
