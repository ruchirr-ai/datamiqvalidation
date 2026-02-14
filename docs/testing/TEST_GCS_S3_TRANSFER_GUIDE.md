# GCS to S3 Transfer Testing Guide

## UI Improvements ✅

The Transfer Options UI has been enhanced with:

### Visual Improvements
- **White background** with 2px border for better visibility
- **Hover effect** - Border changes to blue with subtle shadow
- **Section header** with icon and divider line
- **Better spacing** - 12px margin between toggle options
- **Enhanced typography** - Clearer titles and descriptions

### What You'll See
```
┌─────────────────────────────────────────────────────────┐
│ ⊕ Transfer Options                                      │
│ ═══════════════════════════════════════════════════════ │
│                                                          │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Overwrite Existing Files              [Toggle OFF] │ │
│ │ Overwrite files in S3 if they already exist        │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                          │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Delete Source After Transfer          [Toggle OFF] │ │
│ │ Delete files from GCS after successful transfer    │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

The toggles are now much more visible with:
- Clear white cards with borders
- Hover effects when you move your mouse over them
- Better visual separation between options
- Prominent section header

## Test Script Usage

### Prerequisites

1. **Install Dependencies** (if not already installed):
```bash
cd backend
source .venv/bin/activate
uv pip install google-cloud-storage-transfer
```

2. **GCP Service Account**:
   - You need a service account with Storage Transfer permissions
   - Set `GOOGLE_APPLICATION_CREDENTIALS` environment variable (optional)
   - Or the script will use your default credentials

3. **AWS Credentials**:
   - AWS Access Key ID
   - AWS Secret Access Key
   - Credentials must have write permissions to S3 bucket

4. **Existing Data**:
   - GCS bucket with some test data
   - S3 bucket (can be empty)

### Running the Test

```bash
cd backend
source .venv/bin/activate
python test_gcs_to_s3_transfer.py
```

### Interactive Prompts

The script will ask you for:

#### GCP Configuration
```
GCP Project ID: assessiq-484512
GCS Bucket (without gs://): bq_data_transfer_rs
GCS Path (e.g., exports/test): exports/test-migration
```

#### AWS Configuration
```
S3 Bucket (without s3://): my-redshift-data
S3 Path (e.g., imports/test): imports/test-migration
AWS Access Key ID: AKIAIOSFODNN7EXAMPLE
AWS Secret Access Key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

#### Transfer Options
```
Overwrite existing files? (y/n) [n]: n
Delete source after transfer? (y/n) [n]: n
```

### Example Session

```bash
$ python test_gcs_to_s3_transfer.py

================================================================================
GCS to S3 Transfer Test
================================================================================

Checking prerequisites...

✓ google-cloud-storage-transfer installed
✓ google-auth installed
✓ GOOGLE_APPLICATION_CREDENTIALS set: /path/to/service-account.json


Please provide the following information:

--- GCP Configuration ---
GCP Project ID: assessiq-484512
GCS Bucket (without gs://): bq_data_transfer_rs
GCS Path (e.g., exports/test): exports/shakespeare

--- AWS Configuration ---
S3 Bucket (without s3://): my-redshift-data
S3 Path (e.g., imports/test): imports/shakespeare
AWS Access Key ID: AKIAIOSFODNN7EXAMPLE
AWS Secret Access Key: ****************************************

--- Transfer Options ---
Overwrite existing files? (y/n) [n]: n
Delete source after transfer? (y/n) [n]: n

================================================================================
Configuration Summary
================================================================================
Source: gs://bq_data_transfer_rs/exports/shakespeare
Destination: s3://my-redshift-data/imports/shakespeare
Overwrite Existing: False
Delete Source: False
================================================================================

Proceed with transfer? (y/n): y

Starting transfer test...

2026-02-09 10:30:00 - INFO - Initializing GCS to S3 Transfer Service
2026-02-09 10:30:01 - INFO - Creating transfer job...
✓ Transfer job created: transferJobs/1234567890

2026-02-09 10:30:02 - INFO - Running transfer job...
✓ Transfer job started

Monitoring transfer progress...
(This may take several minutes depending on data size)

2026-02-09 10:30:32 - INFO - Transfer in progress... (30s elapsed)
2026-02-09 10:31:02 - INFO - Transfer in progress... (60s elapsed)
2026-02-09 10:31:32 - INFO - Transfer in progress... (90s elapsed)
2026-02-09 10:32:02 - INFO - ✓ Transfer job completed successfully

================================================================================
Transfer Results
================================================================================
✓ Transfer completed successfully!

Transfer Statistics:
  Objects Found: 1,234
  Bytes Found: 45,678,901
  Objects Copied: 1,234
  Bytes Copied: 45,678,901
  Objects Failed: 0

Completed At: 2026-02-09T10:32:02.123456

Delete transfer job? (y/n) [y]: y
2026-02-09 10:32:05 - INFO - Deleting transfer job...
✓ Transfer job deleted
================================================================================

✓ Test completed successfully!
```

## What the Script Tests

### 1. Transfer Job Creation ✅
- Creates a GCP Storage Transfer Service job
- Configures source (GCS) and destination (S3)
- Sets AWS credentials for S3 write access
- Configures transfer options (overwrite, delete)

### 2. Transfer Execution ✅
- Runs the transfer job immediately
- Monitors progress every 30 seconds
- Handles timeout (1 hour max)
- Collects transfer statistics

### 3. Transfer Monitoring ✅
- Polls transfer status every 30 seconds
- Shows elapsed time
- Detects completion or failure
- Retrieves detailed statistics

### 4. Cleanup ✅
- Optionally deletes transfer job after completion
- Cleans up GCP resources

## Verification Steps

### 1. Check GCS Bucket (Before Transfer)
```bash
gsutil ls -lh gs://bq_data_transfer_rs/exports/shakespeare/
```

Expected output:
```
  1.2 MiB  2026-02-09T10:00:00Z  gs://bq_data_transfer_rs/exports/shakespeare/shard-0.avro
  1.3 MiB  2026-02-09T10:00:01Z  gs://bq_data_transfer_rs/exports/shakespeare/shard-1.avro
  ...
```

### 2. Check S3 Bucket (After Transfer)
```bash
aws s3 ls s3://my-redshift-data/imports/shakespeare/ --human-readable
```

Expected output:
```
2026-02-09 10:32:00    1.2 MiB shard-0.avro
2026-02-09 10:32:01    1.3 MiB shard-1.avro
...
```

### 3. Verify File Counts Match
```bash
# Count GCS files
gsutil ls gs://bq_data_transfer_rs/exports/shakespeare/ | wc -l

# Count S3 files
aws s3 ls s3://my-redshift-data/imports/shakespeare/ | wc -l
```

Both should return the same number.

### 4. Verify File Sizes Match
```bash
# GCS total size
gsutil du -sh gs://bq_data_transfer_rs/exports/shakespeare/

# S3 total size
aws s3 ls s3://my-redshift-data/imports/shakespeare/ --recursive --summarize
```

## Common Issues and Solutions

### Issue 1: "google-cloud-storage-transfer not installed"

**Solution**:
```bash
cd backend
source .venv/bin/activate
uv pip install google-cloud-storage-transfer
```

### Issue 2: "GOOGLE_APPLICATION_CREDENTIALS not set"

**Solution**:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

Or the script will use your default GCP credentials.

### Issue 3: "Permission denied" on GCS

**Solution**:
Ensure your service account has these permissions:
- `storage.buckets.get`
- `storage.objects.list`
- `storage.objects.get`
- `storagetransfer.jobs.create`
- `storagetransfer.jobs.get`
- `storagetransfer.operations.list`

### Issue 4: "Access Denied" on S3

**Solution**:
Ensure your AWS credentials have these permissions:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::my-redshift-data/*",
        "arn:aws:s3:::my-redshift-data"
      ]
    }
  ]
}
```

### Issue 5: "Transfer job failed"

**Possible Causes**:
1. Invalid AWS credentials
2. S3 bucket doesn't exist
3. GCS bucket doesn't exist or is empty
4. Network connectivity issues

**Solution**:
Check the error message in the output and verify:
- AWS credentials are correct
- Both buckets exist and are accessible
- Network connectivity to both GCP and AWS

### Issue 6: "Transfer timeout"

**Cause**: Transfer taking longer than 1 hour

**Solution**:
- For large datasets, increase timeout in the script
- Or run transfer in smaller batches

## Test Scenarios

### Scenario 1: Basic Transfer
```
GCS: gs://bq_data_transfer_rs/exports/test
S3: s3://my-redshift-data/imports/test
Overwrite: No
Delete: No
```

**Expected**: Files copied from GCS to S3, both locations have files

### Scenario 2: Transfer with Overwrite
```
GCS: gs://bq_data_transfer_rs/exports/test
S3: s3://my-redshift-data/imports/test (already has files)
Overwrite: Yes
Delete: No
```

**Expected**: Existing S3 files overwritten, both locations have files

### Scenario 3: Transfer with Delete
```
GCS: gs://bq_data_transfer_rs/exports/test
S3: s3://my-redshift-data/imports/test
Overwrite: No
Delete: Yes
```

**Expected**: Files copied to S3, GCS files deleted after transfer

### Scenario 4: Large Dataset
```
GCS: gs://bq_data_transfer_rs/exports/large-dataset (10GB+)
S3: s3://my-redshift-data/imports/large-dataset
Overwrite: No
Delete: No
```

**Expected**: Transfer takes several minutes, progress shown every 30s

## Integration with Migration Wizard

After successful test, you can use the same credentials in the UI:

1. Navigate to: http://localhost:3000/migrations/create
2. Select Pathway A
3. In Stage 2 (GCS → S3 Transfer):
   - S3 Bucket: `my-redshift-data`
   - S3 Path: `imports/test-migration`
   - AWS Access Key ID: Your key
   - AWS Secret Access Key: Your secret (will be encrypted)
   - Toggle "Overwrite Existing Files" as needed
   - Toggle "Delete Source After Transfer" as needed

## Next Steps

### After Successful Test
1. ✅ Verify files in S3 bucket
2. ✅ Test with different transfer options
3. ✅ Test with larger datasets
4. ✅ Use credentials in migration wizard
5. ✅ Run complete end-to-end migration

### Production Considerations
1. ⚠️ Use IAM roles instead of access keys
2. ⚠️ Implement automatic cleanup of old transfer jobs
3. ⚠️ Add cost estimation before transfer
4. ⚠️ Implement retry logic for failed transfers
5. ⚠️ Add CloudWatch monitoring for transfer jobs

## Support

If you encounter issues:

1. **Check Logs**: Script shows detailed logs
2. **Verify Credentials**: Test GCS and S3 access separately
3. **Check Permissions**: Ensure service account and IAM user have required permissions
4. **Network**: Verify connectivity to both GCP and AWS

---

**Ready to test!** Run the script and provide your credentials when prompted. 🚀
