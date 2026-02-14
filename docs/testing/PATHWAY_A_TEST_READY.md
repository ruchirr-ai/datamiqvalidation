# Pathway A End-to-End Test Script Ready

## What Was Created

### 1. Test Script: `backend/test_pathway_a_end_to_end.py`
A comprehensive end-to-end test script that validates the complete Pathway A data flow:
- **Stage 1**: BigQuery → GCS (export table data)
- **Stage 2**: GCS → S3 (transfer using Storage Transfer Service or direct method)

### 2. Test Guide: `RUN_PATHWAY_A_TEST.md`
Complete documentation with:
- Prerequisites and setup instructions
- Configuration steps
- How to run the test
- Expected output
- Troubleshooting guide
- Performance benchmarks

## Quick Start

### 1. Configure Environment
Edit `backend/.env` and ensure these are set:
```bash
BIGQUERY_PROJECT_ID=assessiq-484512
GCS_BUCKET=bq_data_transfer_rs
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
S3_BUCKET=your-s3-bucket-name
AWS_REGION=us-east-1
```

### 2. Authenticate with Google Cloud
```bash
gcloud auth application-default login
gcloud config set project assessiq-484512
```

### 3. Edit Test Parameters
Open `backend/test_pathway_a_end_to_end.py` and set:
```python
BIGQUERY_DATASET = 'analytics'  # Your dataset
BIGQUERY_TABLE = 'customers'    # Your table
```

### 4. Run the Test
```bash
cd backend
python test_pathway_a_end_to_end.py
```

## What the Test Does

### Automated Testing Flow
1. ✅ **Test BigQuery Connection** - Verify access and get table metadata
2. ✅ **Export to GCS** - Export table data to Google Cloud Storage
3. ✅ **Test GCS Connection** - Verify GCS bucket access
4. ✅ **Test S3 Connection** - Verify AWS S3 bucket access
5. ✅ **Transfer GCS → S3** - Move files from GCS to S3
6. ✅ **Verify S3 Files** - Confirm all files transferred successfully
7. ✅ **Cleanup** - Optional cleanup of test files

### Transfer Methods

**Method A: Storage Transfer Service (Preferred)**
- Fast, scalable, managed by Google
- Best for large datasets
- Requires Storage Transfer Service permissions

**Method B: Direct Transfer (Fallback)**
- Downloads from GCS, uploads to S3
- Works without additional permissions
- Slower but reliable

## Features

### Real-Time Progress
- Color-coded output (success, error, info, warning)
- Progress indicators for each step
- File-by-file transfer progress
- Transfer statistics (speed, size, time)

### Comprehensive Validation
- Connection testing before operations
- File count and size verification
- Error handling with detailed messages
- Automatic fallback to direct transfer

### Cleanup Options
- Optional cleanup at the end
- Removes test files from both GCS and S3
- Or keep files for manual inspection

## Expected Results

### Success Indicators
- ✓ All steps complete without errors
- ✓ Files appear in both GCS and S3
- ✓ File counts and sizes match
- ✓ Transfer completes within expected time

### Test Output
```
================================================================================
           Pathway A End-to-End Test: BigQuery → GCS → S3
================================================================================

✓ Connected to BigQuery project: assessiq-484512
✓ Export completed in 45.23 seconds
✓ Found 8 file(s) in GCS
✓ Connected to GCS bucket: bq_data_transfer_rs
✓ Connected to S3 bucket: your-bucket
✓ Transfer completed!
✓ Found 8 file(s) in S3

================================================================================
                      Test Completed Successfully!
================================================================================
```

## Troubleshooting

### Common Issues

**"Failed to connect to BigQuery"**
→ Run: `gcloud auth application-default login`

**"GCS bucket does not exist"**
→ Check bucket name in `.env` file

**"S3 bucket not accessible"**
→ Verify AWS credentials and bucket name

**"Table not found"**
→ Check dataset and table names in script

**"Storage Transfer Service requires additional setup"**
→ Expected - script will use direct transfer (works fine)

## Performance Benchmarks

| Table Size | Export Time | Transfer Time | Total Time |
|------------|-------------|---------------|------------|
| < 100 MB   | 10-30 sec   | 20-60 sec     | 1-2 min    |
| 100 MB-1GB | 30-120 sec  | 1-5 min       | 2-7 min    |
| > 1 GB     | 2-10 min    | 5-30 min      | 7-40 min   |

## Next Steps After Successful Test

### 1. Test Your Migration Job
- Go to Migrations page in UI
- Click "Run Migration" on your updated job
- Monitor progress

### 2. Verify in UI
- Check migration status updates
- View logs for detailed progress
- Verify completion

### 3. Check Redshift
- Connect to Redshift cluster
- Verify tables were created
- Check row counts match source

## Files Created

1. **`backend/test_pathway_a_end_to_end.py`** - Main test script (executable)
2. **`RUN_PATHWAY_A_TEST.md`** - Comprehensive test guide
3. **`PATHWAY_A_TEST_READY.md`** - This summary document

## Test Data Locations

### During Test
- **GCS**: `gs://bq_data_transfer_rs/test_exports/{timestamp}/`
- **S3**: `s3://your-bucket/test_imports/{timestamp}/`

### After Cleanup
- All test files removed (if cleanup was chosen)
- Or files remain for manual inspection

## Manual Verification Commands

### Check GCS Files
```bash
gsutil ls -lh gs://bq_data_transfer_rs/test_exports/
```

### Check S3 Files
```bash
aws s3 ls s3://your-bucket/test_imports/ --recursive --human-readable
```

### Download Sample File
```bash
# From GCS
gsutil cp gs://bq_data_transfer_rs/test_exports/{timestamp}/customers/000000000000.avro .

# From S3
aws s3 cp s3://your-bucket/test_imports/{timestamp}/customers/000000000000.avro .
```

## Status
✅ **READY TO TEST** - All scripts and documentation complete

Run the test to verify your Pathway A configuration before running the actual migration job!
