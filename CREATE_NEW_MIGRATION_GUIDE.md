# Create New Migration - Guide

## Why Create a New Migration?

The existing migrations (ID 13 and 17) were started with the OLD buggy code before the fix was deployed. Even though we reset them, they still have issues because:

1. The migration execution started in a background thread with the old code
2. The checkpoint save bug affects the entire execution
3. Creating a fresh migration ensures it uses the fixed code from the start

## ✅ Solution: Create a New Migration

### Option 1: From the UI (Recommended)

1. **Go to Migrations Page**:
   - URL: `http://localhost:3000/migrations`

2. **Click "Create Migration" or "New Migration"**

3. **Fill in the Configuration**:
   
   **Step 1: Basic Info**
   - Name: `bigquery_to_redshift_fixed` (or any name you prefer)
   - Pathway: **C** (GCS → S3 → Redshift)

   **Step 2: Source (BigQuery)**
   - Connection: Select your BigQuery connection
   - Project ID: `assessiq-484512`
   - Dataset: `sales_analytics`
   - Tables: Select all 3 tables:
     - `assess_data`
     - `customers`
     - `orders`

   **Step 3: Target (Redshift)**
   - Connection: Select your Redshift connection
   - Cluster: Your Redshift endpoint
   - Database: `dev` (or your database name)
   - IAM Role ARN: Your IAM role for S3 access

   **Step 4: Storage Configuration**
   - **GCS Bucket**: `bq_data_transfer_rs` (without `gs://` prefix)
   - **GCS Path**: `staging`
   - **S3 Bucket**: `sk-manasa`
   - **S3 Path**: `bq_rs_staging_new` (use a new path to avoid conflicts)
   - **Export Format**: PARQUET
   - **Compression**: NONE
   - **Delete Source**: No

   **Step 5: AWS Credentials**
   - AWS Access Key ID: Your AWS access key
   - AWS Secret Access Key: Your AWS secret key (will be encrypted)

4. **Click "Create" or "Save"**

5. **Start the Migration**:
   - Click "Run" on the newly created migration
   - Monitor the progress

### Option 2: Reuse Existing Data in S3

Since data is already in S3 from the previous migration, you can:

1. Create the new migration with the same configuration
2. The export stage will run again (or you can skip it if data is fresh)
3. The transfer stage will transfer to S3 again (or use existing data)
4. The load stage will finally work and load data to Redshift

## What Will Happen with the New Migration

### Stage 1: Export (BigQuery → GCS)
- Export 3 tables from BigQuery to GCS
- Duration: ~30 seconds
- Result: Parquet files in `gs://bq_data_transfer_rs/staging/`

### Stage 2: Transfer (GCS → S3)
- Transfer files from GCS to S3
- Duration: ~5 seconds (small dataset)
- Result: Files in `s3://sk-manasa/bq_rs_staging_new/`

### Stage 3: Load (S3 → Redshift) ⬅️ **THIS WILL FINALLY WORK**
- Create database: `assessiq_484512`
- Create schema: `sales_analytics`
- Create tables with proper schema
- Load data using COPY command
- Verify row counts
- Duration: ~30-60 seconds

## Why This Will Work

1. ✅ **Fixed Code**: New migration uses the fixed session management code
2. ✅ **Fresh Start**: No old checkpoint data or state issues
3. ✅ **Proper Checkpoints**: All checkpoints will save correctly
4. ✅ **Resume Support**: Can resume from any stage if needed
5. ✅ **Complete Flow**: All three stages will execute properly

## Alternative: Use Existing S3 Data

If you want to skip export and transfer and just load from existing S3 data:

### Create a Test Script

```python
# backend/load_from_existing_s3.py
from services.bq_redshift_migration.pathway_c import PathwayC
from database import get_db

# Configuration
migration_id = 18  # Your new migration ID
target_config = {
    'cluster': 'your-redshift-endpoint',
    'port': 5439,
    'database': 'dev',
    'username': 'your-username',
    'password_encrypted': 'your-encrypted-password',
    'iam_role_arn': 'your-iam-role-arn'
}
storage_config = {
    's3_bucket': 'sk-manasa',
    's3_path': 'bq_rs_staging',  # Existing data location
    'export_format': 'PARQUET',
    'aws_access_key_id': 'your-key',
    'aws_secret_access_key_encrypted': 'your-encrypted-secret'
}

# Execute load stage only
db = next(get_db())
pathway = PathwayC(None, None, None)
success = pathway._execute_load_stage(
    migration_id=migration_id,
    target_config=target_config,
    storage_config=storage_config,
    pending_shards=[],
    db=db
)
db.close()

print(f"Load stage: {'✓ Success' if success else '✗ Failed'}")
```

## Monitoring the New Migration

### Check Status
```bash
python backend/check_migration_status.py bigquery_to_redshift_fixed
```

### Watch Logs
The UI will show real-time logs as the migration progresses.

### Verify Completion
```bash
# Check all migrations
python backend/list_all_migrations.py

# Check specific migration
python backend/check_migration_status.py bigquery_to_redshift_fixed
```

## Expected Timeline

- **Export**: 30 seconds
- **Transfer**: 5 seconds  
- **Load**: 60 seconds
- **Total**: ~2 minutes

## Verification After Completion

### 1. Check Migration Status
```bash
python backend/check_migration_status.py bigquery_to_redshift_fixed
```

Should show:
```
Status: completed
Export completed: ✓
Transfer completed: ✓
Load completed: ✓
```

### 2. Query Redshift
```sql
-- Check database
SELECT datname FROM pg_database WHERE datname = 'assessiq_484512';

-- Check tables
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'sales_analytics';

-- Check data
SELECT COUNT(*) FROM assessiq_484512.sales_analytics.assess_data;
SELECT COUNT(*) FROM assessiq_484512.sales_analytics.customers;
SELECT COUNT(*) FROM assessiq_484512.sales_analytics.orders;
```

## Summary

**Current Situation**:
- Migrations 13 and 17 are stuck due to old buggy code
- Data is in S3 but not loaded to Redshift
- Checkpoint save bug prevents load stage from running

**Solution**:
- Create a NEW migration with the same configuration
- The new migration will use the FIXED code
- All stages will complete successfully
- Data will be loaded to Redshift

**Action Required**:
1. Go to UI and create a new migration
2. Use the configuration details above
3. Start the migration
4. Monitor progress
5. Verify data in Redshift

---

**Status**: Ready to create new migration  
**Fix Applied**: ✅ Session management bug fixed  
**Server**: ✅ Running with fixed code  
**Next Step**: Create new migration from UI  
