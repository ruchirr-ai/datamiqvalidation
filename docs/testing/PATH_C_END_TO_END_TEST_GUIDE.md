# Path C End-to-End Testing Guide

## Overview

This guide provides step-by-step instructions for testing the complete BigQuery to Redshift migration using Path C, with comprehensive logging visible in the UI.

## Prerequisites

### 1. Populate BigQuery Tables with Data

**CRITICAL**: The BigQuery tables must have actual data, not just metadata.

```bash
# Run the population script
python backend/populate_bigquery_tables.py
```

This script will:
- Delete existing data from `customers` and `orders` tables
- Insert 3 customers and 4 orders
- Verify data is queryable

**Expected Output**:
```
✓ Successfully inserted 3 customers
✓ Verified: 3 rows in customers table
✓ Successfully inserted 4 orders
✓ Verified: 4 rows in orders table
```

### 2. Verify Connections

Ensure both connections are configured and tested:

1. **BigQuery Connection** (ID: 6)
   - Type: BigQuery
   - Has service account credentials
   - Status: Active

2. **Redshift Connection** (ID: 7)
   - Type: Redshift
   - Cluster: `redshift-cluster-1.xxxxx.us-east-1.redshift.amazonaws.com`
   - Database: `dev` (initial connection database)
   - Username: `awsuser`
   - Password: Encrypted
   - Status: Active

### 3. Verify Migration Configuration

Check migration 12 has all required fields:

```sql
SELECT 
    id,
    migration_name,
    pathway,
    source_connection_id,
    target_connection_id,
    source_project_id,
    source_dataset,
    source_tables,
    gcs_bucket,
    gcs_path,
    s3_bucket,
    s3_path,
    iam_role_arn,
    export_format,
    status
FROM migrations_bq_redshift
WHERE id = 12;
```

**Required Values**:
- `pathway`: 'C'
- `source_connection_id`: 6
- `target_connection_id`: 7
- `source_project_id`: 'assessiq-484512'
- `source_dataset`: 'sales_analytics'
- `source_tables`: ['customers', 'orders']
- `gcs_bucket`: 'bq_data_transfer_rs'
- `gcs_path`: '/staging'
- `s3_bucket`: 'sk-manasa'
- `s3_path`: '/staging'
- `iam_role_arn`: 'arn:aws:iam::637423662539:role/redshiftS3Role'
- `export_format`: 'PARQUET'

## Testing Steps

### Step 1: Start Backend Server

```bash
# Navigate to backend directory
cd backend

# Activate virtual environment
source .venv/bin/activate

# Start server
uvicorn main:app --reload --port 8000
```

**Verify**: Server starts without errors and shows:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### Step 2: Open Frontend

```bash
# In a new terminal, navigate to frontend
cd frontend

# Start development server
npm start
```

**Verify**: Frontend opens at `http://localhost:3000`

### Step 3: Navigate to Migrations Page

1. Open browser to `http://localhost:3000`
2. Click on "Migrations" in the navigation
3. Find migration "bq_rs_mig" (ID: 12)

### Step 4: Execute Migration

1. Click the three-dot menu (⋮) next to migration 12
2. Select "Execute Migration"
3. Confirm execution

**Expected Behavior**:
- Status changes to "running"
- Progress indicator appears
- Current stage updates as migration progresses

### Step 5: Monitor Progress

The migration will go through 3 stages:

#### Stage 1: Export (BigQuery → GCS)
**Duration**: ~30-60 seconds

**What Happens**:
- Exports `customers` table to GCS
- Exports `orders` table to GCS
- Creates PARQUET files in `gs://bq_data_transfer_rs/staging/sales_analytics/`

**Expected Logs** (View Logs button):
```
[INFO] STARTING PATH C MIGRATION 12
[INFO] Source: BigQuery → GCS
[INFO] Transfer: GCS → S3 (Download & Upload)
[INFO] Load: S3 → Redshift
[INFO] Checkpoint Status:
[INFO]   Export: ✗ Pending
[INFO]   Transfer: ✗ Pending
[INFO]   Load: ✗ Pending
[INFO] Starting EXPORT stage
[INFO] Exporting table: customers
[INFO] ✓ Table customers exported successfully
[INFO] Exporting table: orders
[INFO] ✓ Table orders exported successfully
[INFO] ✓ EXPORT STAGE COMPLETED
```

#### Stage 2: Transfer (GCS → S3)
**Duration**: ~1-2 minutes

**What Happens**:
- Downloads files from GCS
- Uploads files to S3
- Transfers to `s3://sk-manasa/staging/sales_analytics/`

**Expected Logs**:
```
[INFO] MIGRATION 12: TRANSFER STAGE
[INFO] Source: gs://bq_data_transfer_rs/staging
[INFO] Destination: s3://sk-manasa/staging
[INFO] Decrypting AWS secret access key...
[INFO] ✓ AWS secret key decrypted successfully
[INFO] Fetching GCP credentials from database...
[INFO] ✓ GCP credentials loaded
[INFO] Initializing GCS to S3 transfer service...
[INFO] 🚀 STARTING FILE TRANSFER FROM GCS TO S3
[INFO] This may take several minutes depending on data size...
[INFO] ✓ TRANSFER STAGE COMPLETED SUCCESSFULLY
[INFO] 📊 TRANSFER SUMMARY:
[INFO]    Status: SUCCESS
[INFO]    Files Found: 2
[INFO]    Files Transferred: 2
[INFO]    Files Failed: 0
[INFO]    Success Rate: 100.0%
[INFO]    Data Transferred: 1.5 KB
[INFO]    Duration: 45.2 seconds
[INFO]    Average Speed: 34.2 B/s
[INFO] ✓ Transfer checkpoint saved to database
```

#### Stage 3: Load (S3 → Redshift)
**Duration**: ~1-2 minutes

**What Happens**:
- Creates database `assessiq_484512` (if doesn't exist)
- Creates schema `sales_analytics` (if doesn't exist)
- Creates table `customers` with proper schema
- Loads data from S3 using COPY command
- Creates table `orders` with proper schema
- Loads data from S3 using COPY command
- Verifies row counts

**Expected Logs**:
```
[INFO] MIGRATION 12: LOAD STAGE (PRODUCTION)
[INFO] NAMING CONVENTION
[INFO] GCP Project ID: assessiq-484512
[INFO] GCP Dataset: sales_analytics
[INFO] Redshift Database: assessiq_484512
[INFO] Redshift Schema: sales_analytics
[INFO] Decrypting credentials...
[INFO] ✓ Target password decrypted
[INFO] ✓ AWS secret key decrypted
[INFO] INITIALIZING REDSHIFT LOADER
[INFO] ✓ Connected to Redshift
[INFO] STEP 1: CREATE DATABASE 'assessiq_484512' IF NOT EXISTS
[INFO] ✓ Database 'assessiq_484512' created successfully
[INFO] STEP 2: CONNECT TO DATABASE 'assessiq_484512'
[INFO] ✓ Connected to database 'assessiq_484512'
[INFO] STEP 3: CREATE SCHEMA 'sales_analytics' IF NOT EXISTS
[INFO] ✓ Schema 'sales_analytics' ready
[INFO] STEP 4: LOAD TABLES TO REDSHIFT
[INFO] TABLE 1/2: customers
[INFO] BigQuery Source: assessiq-484512.sales_analytics.customers
[INFO] Redshift Target: assessiq_484512.sales_analytics.customers
[INFO] Columns: 5
[INFO] S3 Location: s3://sk-manasa/staging/sales_analytics/customers
[INFO] ✓ Table customers loaded successfully
[INFO]   Rows loaded: 3
[INFO] TABLE 2/2: orders
[INFO] BigQuery Source: assessiq-484512.sales_analytics.orders
[INFO] Redshift Target: assessiq_484512.sales_analytics.orders
[INFO] Columns: 5
[INFO] S3 Location: s3://sk-manasa/staging/sales_analytics/orders
[INFO] ✓ Table orders loaded successfully
[INFO]   Rows loaded: 4
[INFO] ✓ LOAD STAGE COMPLETED
[INFO] Database: assessiq_484512
[INFO] Schema: sales_analytics
[INFO] Tables loaded successfully: 2/2
[INFO] Tables failed: 0
[INFO] Total rows loaded: 7
[INFO] Migration status: completed
[INFO] ✓ PATH C MIGRATION 12 COMPLETED SUCCESSFULLY
[INFO]   All stages completed: Export ✓ Transfer ✓ Load ✓
```

### Step 6: Verify Completion

1. **Check Migration Status**:
   - Status should be "completed"
   - Progress should be 100%
   - All stages should show checkmarks

2. **View Logs**:
   - Click "View Logs" button
   - Should see all stages completed successfully
   - No ERROR level logs

3. **Check Checkpoint Data**:
   ```sql
   SELECT checkpoint_data 
   FROM migrations_bq_redshift 
   WHERE id = 12;
   ```
   
   Should contain:
   - `export_completed_at`
   - `transfer_completed_at`
   - `load_completed_at`
   - `load_summary` with row counts

### Step 7: Verify Data in Redshift

Connect to Redshift and verify:

```sql
-- Connect to database assessiq_484512
\c assessiq_484512

-- Verify schema exists
SELECT schema_name 
FROM information_schema.schemata 
WHERE schema_name = 'sales_analytics';

-- Verify tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'sales_analytics';

-- Verify customers data
SELECT * FROM sales_analytics.customers;
-- Expected: 3 rows

-- Verify orders data
SELECT * FROM sales_analytics.orders;
-- Expected: 4 rows

-- Verify row counts
SELECT 
    'customers' as table_name,
    COUNT(*) as row_count
FROM sales_analytics.customers
UNION ALL
SELECT 
    'orders' as table_name,
    COUNT(*) as row_count
FROM sales_analytics.orders;
```

**Expected Results**:
```
 table_name | row_count
------------+-----------
 customers  |         3
 orders     |         4
```

## Troubleshooting

### Issue: Export Stage Fails

**Symptoms**:
- Status stuck at "running"
- Logs show "Export stage failed"

**Solutions**:
1. Check BigQuery connection is active
2. Verify service account has BigQuery permissions
3. Verify GCS bucket exists and is accessible
4. Check BigQuery tables have data (run `populate_bigquery_tables.py`)

### Issue: Transfer Stage Fails

**Symptoms**:
- Export completes but transfer fails
- Logs show "Transfer stage failed"

**Solutions**:
1. Verify AWS credentials are correct
2. Check S3 bucket exists and is accessible
3. Verify IAM permissions for S3 write
4. Check network connectivity to AWS

### Issue: Load Stage Fails

**Symptoms**:
- Transfer completes but load fails
- Logs show "Load stage failed"

**Solutions**:
1. Verify Redshift connection is active
2. Check IAM role ARN is correct
3. Verify IAM role has S3 read permissions
4. Check Redshift cluster is accessible
5. Verify database user has CREATE DATABASE permission

### Issue: No Data Loaded (0 Rows)

**Symptoms**:
- Migration completes successfully
- But Redshift tables have 0 rows

**Solutions**:
1. **MOST COMMON**: BigQuery tables are empty
   - Run `python backend/populate_bigquery_tables.py`
   - Verify data exists: `SELECT * FROM assessiq-484512.sales_analytics.customers`

2. Check S3 files have data:
   - Run `python backend/debug_s3_files.py`
   - Verify PARQUET files contain rows

3. Check COPY command errors in Redshift:
   ```sql
   SELECT * FROM stl_load_errors 
   ORDER BY starttime DESC 
   LIMIT 10;
   ```

## API Endpoints Used

### 1. Execute Migration
```
POST /api/bq-redshift-migrations/{migration_id}/execute
```

### 2. Get Migration Status
```
GET /api/bq-redshift-migrations/{migration_id}
```

### 3. Get Migration Logs
```
GET /api/bq-redshift-migrations/{migration_id}/logs?level=INFO&limit=1000
```

### 4. Stop Migration
```
POST /api/bq-redshift-migrations/{migration_id}/stop
```

## Log Levels

Logs are stored in the database and viewable from UI:

- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages (default)
- **WARNING**: Warning messages
- **ERROR**: Error messages
- **CRITICAL**: Critical failures

## Success Criteria

✅ Migration completes with status "completed"
✅ All 3 stages show as completed in logs
✅ No ERROR level logs
✅ Database `assessiq_484512` created in Redshift
✅ Schema `sales_analytics` created in Redshift
✅ Table `customers` has 3 rows
✅ Table `orders` has 4 rows
✅ Total rows loaded: 7
✅ Checkpoint data saved correctly

## Next Steps After Successful Test

1. **Test with Larger Dataset**:
   - Add more rows to BigQuery tables
   - Re-run migration
   - Verify performance

2. **Test Resume Functionality**:
   - Stop migration mid-transfer
   - Re-execute migration
   - Verify it resumes from checkpoint

3. **Test Error Handling**:
   - Intentionally cause failures
   - Verify error messages are clear
   - Verify logs capture errors

4. **Test UI Updates**:
   - Verify status updates in real-time
   - Verify progress bar updates
   - Verify logs refresh automatically

## Support

If you encounter issues:
1. Check logs in UI (View Logs button)
2. Check backend console output
3. Check database logs table: `SELECT * FROM migration_logs WHERE migration_id = 12 ORDER BY created_at DESC`
4. Review this guide's troubleshooting section
