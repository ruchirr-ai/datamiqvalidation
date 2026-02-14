# Pathway A Testing Guide

## Overview

This guide enables you to test each step of Pathway A (GCP Storage Transfer Service) migration independently with actual connections.

**Pathway A Flow:**
1. **BigQuery → GCS**: Export BigQuery tables to Google Cloud Storage in AVRO format
2. **GCS → S3**: Transfer files from GCS to S3 using GCP Storage Transfer Service
3. **S3 → Redshift**: Load data from S3 to Redshift using COPY command

## Features Implemented

### Backend Test Endpoints

Three new test endpoints have been created in `backend/routers/pathway_a_test_router.py`:

#### 1. POST `/api/migrations/pathway-a/test/step1-bigquery-to-gcs`
Tests BigQuery to GCS export functionality.

**Request:**
```json
{
  "source_connection_id": 6,
  "project_id": "assessiq-484512",
  "dataset": "sales_analytics",
  "table": "customers_tbl",
  "gcs_bucket": "my-migration-bucket",
  "gcs_path": "migrations/test"
}
```

**Response:**
```json
{
  "success": true,
  "step": "bigquery_to_gcs",
  "message": "Successfully exported customers_tbl to GCS",
  "details": {
    "table": "customers_tbl",
    "table_info": {
      "num_rows": 1250000,
      "num_bytes": 450000000,
      "table_type": "TABLE"
    },
    "job_stats": {
      "job_id": "job_abc123",
      "state": "DONE",
      "destination_uri": "gs://my-migration-bucket/migrations/test/customers_tbl/shard-*.avro"
    },
    "gcs_location": "gs://my-migration-bucket/migrations/test/customers_tbl/shard-*.avro"
  },
  "duration_seconds": 45.23,
  "timestamp": "2026-02-08T20:30:00Z"
}
```

#### 2. POST `/api/migrations/pathway-a/test/step2-gcs-to-s3`
Tests GCS to S3 transfer using Storage Transfer Service.

**Request:**
```json
{
  "gcs_bucket": "my-migration-bucket",
  "gcs_path": "migrations/test",
  "s3_bucket": "my-migration-bucket",
  "s3_path": "migrations/test",
  "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
  "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
}
```

**Response:**
```json
{
  "success": true,
  "step": "gcs_to_s3",
  "message": "Transfer job created: transferJobs/123456789",
  "details": {
    "job": {
      "job_name": "transferJobs/123456789",
      "status": "ENABLED",
      "description": "Test transfer: migrations/test"
    },
    "source": "gs://my-migration-bucket/migrations/test",
    "destination": "s3://my-migration-bucket/migrations/test",
    "note": "Transfer job is running asynchronously. Check GCP Console for progress."
  },
  "duration_seconds": 2.15,
  "timestamp": "2026-02-08T20:31:00Z"
}
```

#### 3. POST `/api/migrations/pathway-a/test/step3-s3-to-redshift`
Tests S3 to Redshift load using COPY command.

**Request:**
```json
{
  "target_connection_id": 7,
  "s3_bucket": "my-migration-bucket",
  "s3_path": "migrations/test",
  "table_name": "customers_tbl",
  "schema": "public",
  "iam_role": "arn:aws:iam::123456789012:role/RedshiftCopyRole"
}
```

**Response:**
```json
{
  "success": true,
  "step": "s3_to_redshift",
  "message": "Successfully loaded 1250000 rows into customers_tbl",
  "details": {
    "table": "customers_tbl",
    "schema": "public",
    "row_count": 1250000,
    "table_size": "450 MB",
    "s3_source": "s3://my-migration-bucket/migrations/test/customers_tbl/"
  },
  "duration_seconds": 120.45,
  "timestamp": "2026-02-08T20:35:00Z"
}
```

### Frontend Testing UI

A new testing page has been created at `/migrations/pathway-a-test` with:

- **Step-by-step testing interface** for each migration stage
- **Connection selection** from existing BigQuery and Redshift connections
- **Form validation** to ensure all required fields are filled
- **Real-time test results** with success/failure indicators
- **Detailed error messages** and execution times
- **Auto-population** of subsequent steps based on previous results

## Prerequisites

### 1. BigQuery Connection
Create a BigQuery connection with:
- Service Account Key (JSON)
- Project ID
- Region

### 2. GCS Bucket
- Create a GCS bucket for staging data
- Ensure the service account has write permissions
- Example: `my-migration-bucket`

### 3. S3 Bucket
- Create an S3 bucket for receiving data
- Configure IAM permissions for Storage Transfer Service
- Example: `my-migration-bucket`

### 4. Redshift Connection
Create a Redshift connection with:
- Cluster endpoint
- Database name
- Username and password
- IAM role for COPY command (optional)

### 5. GCP Storage Transfer Service Setup
- Enable Storage Transfer API in GCP Console
- Grant Storage Transfer Service access to your S3 bucket
- Configure AWS credentials or IAM role

## Testing Steps

### Step 1: Test BigQuery to GCS Export

1. Navigate to `/migrations/pathway-a-test`
2. Select your BigQuery connection
3. Enter:
   - Project ID (e.g., `assessiq-484512`)
   - Dataset (e.g., `sales_analytics`)
   - Table (e.g., `customers_tbl`)
   - GCS Bucket (e.g., `my-migration-bucket`)
   - GCS Path (e.g., `migrations/test`)
4. Click "Test Step 1"
5. Wait for the export to complete
6. Verify:
   - Success message appears
   - Job statistics are displayed
   - Files are created in GCS bucket

**Expected Result:**
- BigQuery export job completes successfully
- AVRO files are created in GCS: `gs://my-migration-bucket/migrations/test/customers_tbl/shard-*.avro`
- Table metadata is displayed (row count, size)

### Step 2: Test GCS to S3 Transfer

1. GCS bucket and path are auto-populated from Step 1
2. Enter:
   - S3 Bucket (e.g., `my-migration-bucket`)
   - S3 Path (e.g., `migrations/test`)
   - AWS credentials (optional if using IAM)
3. Click "Test Step 2"
4. Wait for transfer job creation
5. Verify:
   - Transfer job is created
   - Job name is displayed
   - Check GCP Console for transfer progress

**Expected Result:**
- Storage Transfer Service job is created
- Job status is "ENABLED"
- Files will be transferred asynchronously (check GCP Console)

**Note:** The transfer happens asynchronously. Monitor progress in:
- GCP Console → Storage Transfer Service
- Check S3 bucket for transferred files

### Step 3: Test S3 to Redshift Load

1. S3 bucket and path are auto-populated from Step 2
2. Select your Redshift connection
3. Enter:
   - Table name (e.g., `customers_tbl`)
   - Schema (default: `public`)
   - IAM Role (optional)
4. Click "Test Step 3"
5. Wait for COPY command to complete
6. Verify:
   - Success message appears
   - Row count matches source
   - Table size is displayed

**Expected Result:**
- Redshift COPY command completes successfully
- Data is loaded into Redshift table
- Row count matches BigQuery source

## Troubleshooting

### Step 1 Errors

**Error: "Service Account Key is required"**
- Ensure your BigQuery connection has valid service account credentials
- Check that the JSON key is properly formatted

**Error: "Table not found"**
- Verify project ID, dataset, and table name are correct
- Ensure service account has BigQuery Data Viewer permission

**Error: "Permission denied on GCS bucket"**
- Grant service account Storage Object Creator role on GCS bucket
- Verify bucket name is correct

### Step 2 Errors

**Error: "Storage Transfer API not enabled"**
- Enable Storage Transfer API in GCP Console
- Wait a few minutes for API to activate

**Error: "Access denied to S3 bucket"**
- Configure Storage Transfer Service access to S3
- Follow GCP documentation for S3 access setup
- Provide AWS credentials if not using IAM

**Error: "Transfer job creation failed"**
- Check GCP project permissions
- Verify S3 bucket exists and is accessible
- Ensure AWS credentials are valid

### Step 3 Errors

**Error: "Connection refused"**
- Verify Redshift cluster is running
- Check security group allows connections
- Ensure VPC/network configuration is correct

**Error: "Table does not exist"**
- Create the target table in Redshift first
- Ensure schema name is correct

**Error: "S3 access denied"**
- Provide IAM role with S3 read permissions
- Or provide AWS credentials in connection
- Verify S3 bucket policy allows Redshift access

**Error: "COPY command failed"**
- Check AVRO file format is correct
- Verify S3 path contains the files
- Ensure table schema matches AVRO schema

## API Testing with cURL

### Test Step 1
```bash
curl -X POST http://localhost:8000/api/migrations/pathway-a/test/step1-bigquery-to-gcs \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source_connection_id": 6,
    "project_id": "assessiq-484512",
    "dataset": "sales_analytics",
    "table": "customers_tbl",
    "gcs_bucket": "my-migration-bucket",
    "gcs_path": "migrations/test"
  }'
```

### Test Step 2
```bash
curl -X POST http://localhost:8000/api/migrations/pathway-a/test/step2-gcs-to-s3 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "gcs_bucket": "my-migration-bucket",
    "gcs_path": "migrations/test",
    "s3_bucket": "my-migration-bucket",
    "s3_path": "migrations/test"
  }'
```

### Test Step 3
```bash
curl -X POST http://localhost:8000/api/migrations/pathway-a/test/step3-s3-to-redshift \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "target_connection_id": 7,
    "s3_bucket": "my-migration-bucket",
    "s3_path": "migrations/test",
    "table_name": "customers_tbl",
    "schema": "public"
  }'
```

## Files Created

### Backend
- `backend/routers/pathway_a_test_router.py` - Test endpoints for each step
- Updated `backend/main.py` - Registered new router

### Frontend
- `frontend/src/pages/PathwayATestPage.tsx` - Testing UI
- `frontend/src/pages/PathwayATestPage.css` - Styling
- Updated `frontend/src/App.tsx` - Added route

## Next Steps

1. **Test each step independently** to verify connectivity and permissions
2. **Fix any configuration issues** before running full migrations
3. **Document successful configurations** for production use
4. **Create Redshift tables** with appropriate schemas before loading
5. **Monitor GCS and S3 buckets** for file transfers
6. **Verify data integrity** by comparing row counts

## Production Considerations

- **IAM Roles**: Use IAM roles instead of access keys for better security
- **Encryption**: Enable encryption for data at rest and in transit
- **Monitoring**: Set up CloudWatch and GCP monitoring for transfer jobs
- **Cost**: Monitor data transfer costs between GCP and AWS
- **Performance**: Consider file sizes and sharding for large tables
- **Cleanup**: Implement lifecycle policies to delete temporary files

## Support

For issues or questions:
1. Check backend logs: `backend/server.log`
2. Check browser console for frontend errors
3. Verify all prerequisites are met
4. Review GCP and AWS console for service-specific errors
