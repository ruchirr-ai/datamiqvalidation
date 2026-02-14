# Quick Start: GCS to S3 Transfer (Pathway A)

## Prerequisites

1. **GCP Service Account** with permissions:
   - Storage Transfer Service permissions
   - GCS bucket read access
   
2. **AWS IAM User** with permissions:
   - S3 bucket write access (PutObject, ListBucket)

3. **Backend and Frontend Running**:
   ```bash
   # Terminal 1 - Backend
   cd backend
   source .venv/bin/activate
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   
   # Terminal 2 - Frontend
   cd frontend
   npm run dev
   ```

## Step-by-Step Guide

### 1. Create Migration

Navigate to: `http://localhost:3000/migrations/create`

**Step 1: Connection & Staging**
- Migration Name: `Test GCS to S3 Transfer`
- Migration Type: `BigQuery to Redshift`
- Source Connection: Select your BigQuery connection
- Target Connection: Select your Redshift connection

**Step 2: Metadata Discovery**
- Project ID: `assessiq-484512` (or your project)
- Click "Discover Metadata"
- Select Dataset: `sales_analytics`
- Select Tables: `customers`, `orders`

**Step 3: Strategy Selection**
- Choose: **Path A - GCP Native**

**Step 4: Configuration & Setup**

**Stage 1: BigQuery to GCS Export**
- GCS Staging Bucket: `gs://bq_data_transfer_rs`
- GCS Region: `us-central1`
- Export Format: `PARQUET`
- Compression: `SNAPPY`

**Stage 2: GCS → S3 Transfer** (NEW!)
- S3 Bucket: `your-s3-bucket-name` (without s3:// prefix)
- S3 Path: `migrations/bq-to-redshift`
- AWS Access Key ID: `AKIAIOSFODNN7EXAMPLE`
- AWS Secret Access Key: `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`
- ☐ Overwrite Existing Files (optional)
- ☐ Delete Source After Transfer (optional)

**Step 5: Scheduling & Monitoring**
- Schedule Type: `One-time`
- Click **Create Migration**

### 2. Run Migration

1. Go to Migrations page: `http://localhost:3000/migrations`
2. Find your migration in the list
3. Click the menu (⋮) button
4. Select **Run Migration**
5. Confirm the action

### 3. Monitor Progress

**Watch the Status**:
- Status will change from `Pending` → `Running` → `Completed`
- "Last Run At" will show the execution timestamp

**View Logs**:
- Click menu (⋮) → **View Logs**
- Check for:
  - `Starting EXPORT stage` - BigQuery export started
  - `Export completed` - BigQuery export finished
  - `Starting TRANSFER stage` - GCS → S3 transfer started
  - `Created transfer job` - Transfer job created
  - `Transfer in progress` - Monitoring updates
  - `Transfer job completed successfully` - Transfer finished
  - `TRANSFER stage completed` - Stage 2 complete

### 4. Verify Results

**Check GCS Bucket**:
```bash
gsutil ls gs://bq_data_transfer_rs/staging/sales_analytics/
# Should see: customers/ and orders/ folders
```

**Check S3 Bucket**:
```bash
aws s3 ls s3://your-s3-bucket-name/migrations/bq-to-redshift/sales_analytics/
# Should see: customers/ and orders/ folders with same files
```

**Verify File Counts**:
```bash
# GCS
gsutil ls -r gs://bq_data_transfer_rs/staging/sales_analytics/ | wc -l

# S3
aws s3 ls --recursive s3://your-s3-bucket-name/migrations/bq-to-redshift/sales_analytics/ | wc -l

# Counts should match!
```

## Troubleshooting

### Issue: "Failed to create transfer job"

**Possible Causes**:
1. GCP service account lacks Storage Transfer Service permissions
2. AWS credentials are invalid
3. S3 bucket doesn't exist or is in different region

**Solution**:
```bash
# Check GCP permissions
gcloud projects get-iam-policy assessiq-484512 \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:YOUR_SERVICE_ACCOUNT"

# Test AWS credentials
aws s3 ls s3://your-s3-bucket-name/ \
  --profile your-profile
```

### Issue: "Transfer job timed out"

**Possible Causes**:
1. Large dataset taking longer than 1 hour
2. Network issues between GCP and AWS

**Solution**:
- Check transfer job in GCP Console: https://console.cloud.google.com/transfer/jobs
- Increase timeout in `pathway_a.py` if needed
- Monitor network bandwidth

### Issue: "AWS credentials not working"

**Possible Causes**:
1. Credentials have insufficient permissions
2. Credentials are expired
3. S3 bucket policy blocks access

**Solution**:
```bash
# Test credentials
aws sts get-caller-identity

# Check S3 bucket policy
aws s3api get-bucket-policy --bucket your-s3-bucket-name

# Verify IAM user permissions
aws iam get-user-policy --user-name your-iam-user --policy-name S3Access
```

### Issue: "Files not appearing in S3"

**Possible Causes**:
1. Transfer job still running
2. Transfer job failed silently
3. Wrong S3 path specified

**Solution**:
- Check GCP Transfer Service console for job status
- Review migration logs for errors
- Verify S3 path matches what you specified

## Expected Timeline

For a typical migration:
- **BigQuery Export**: 2-10 minutes (depends on data size)
- **GCS → S3 Transfer**: 5-30 minutes (depends on data size and network)
- **Total**: 7-40 minutes for small to medium datasets

## Next Steps

After successful GCS → S3 transfer:
1. **Stage 3**: Implement S3 → Redshift load (COPY command)
2. **Validation**: Compare row counts between BigQuery and Redshift
3. **Cleanup**: Optionally delete GCS files if transfer successful

## Support

If you encounter issues:
1. Check migration logs in the UI
2. Check backend logs: `backend/server.log`
3. Check GCP Transfer Service console
4. Review `GCS_TO_S3_TRANSFER_COMPLETE.md` for detailed documentation
