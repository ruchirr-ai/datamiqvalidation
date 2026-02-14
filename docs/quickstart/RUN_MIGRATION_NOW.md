# Run Migration Now - Quick Guide

## ✅ Migration Reset Complete

Migration **bigquery_redshift_transfer** (ID: 17) has been reset to `pending` status.

## 🚀 How to Run the Migration

### Option 1: From the UI (Recommended)

1. **Open the Migrations page** in your browser:
   - URL: `http://localhost:3000/migrations`

2. **Find the migration**:
   - Look for "bigquery_redshift_transfer"
   - Status should show "Pending"

3. **Start the migration**:
   - Click the **"Run"** button or menu option
   - The migration will start immediately

4. **Monitor progress**:
   - Watch the status change from "Pending" → "Running" → "Completed"
   - View logs in real-time if available in UI

### Option 2: From the API

```bash
curl -X POST http://localhost:8000/api/bq-redshift-migrations/17/start \
  -H "Content-Type: application/json"
```

## 📊 What Will Happen

### Stage 1: Export (Will Skip)
- ✅ Already completed
- Checkpoint exists: `export_completed_at`
- 3 tables already exported to GCS

### Stage 2: Transfer (Will Skip)  
- ✅ Already completed
- Data already in S3: `s3://sk-manasa/bq_rs_staging/`
- 3 files (11.01 KB)

### Stage 3: Load (Will Execute) ⬅️ **THIS WILL RUN**
- Create Redshift database: `assessiq_484512`
- Create schema: `sales_analytics`
- Create tables: `assess_data`, `customers`, `orders`
- Load data from S3 using COPY command
- Verify row counts

## ⏱️ Expected Duration

- **Export**: 0 seconds (skipped)
- **Transfer**: 0 seconds (skipped)
- **Load**: 30-60 seconds (depends on Redshift cluster)
- **Total**: ~1 minute

## 🔍 Monitor the Migration

### Check Status
```bash
python backend/check_migration_status.py bigquery_redshift_transfer
```

### Watch Logs in Real-Time
The UI should show logs as they happen. Look for:
- ✓ Export stage verified
- ✓ Transfer stage verified
- ✓ Load stage starting
- ✓ Database created
- ✓ Schema created
- ✓ Tables created
- ✓ Data loaded
- ✓ Migration completed

## ✅ Verify Success

### 1. Check Migration Status
```bash
python backend/check_migration_status.py bigquery_redshift_transfer
```

Expected output:
```
Status: completed
Export completed: ✓
Transfer completed: ✓
Load completed: ✓
```

### 2. Query Redshift Data

Connect to your Redshift cluster and run:

```sql
-- Check database exists
SELECT datname FROM pg_database WHERE datname = 'assessiq_484512';

-- Check tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'sales_analytics';

-- Check data
SELECT COUNT(*) FROM assessiq_484512.sales_analytics.assess_data;
SELECT COUNT(*) FROM assessiq_484512.sales_analytics.customers;
SELECT COUNT(*) FROM assessiq_484512.sales_analytics.orders;

-- View sample data
SELECT * FROM assessiq_484512.sales_analytics.assess_data LIMIT 5;
```

## 🐛 If Something Goes Wrong

### Check Logs
```bash
python backend/check_migration_status.py bigquery_redshift_transfer
```

### Common Issues

1. **Redshift Connection Failed**
   - Verify cluster endpoint
   - Check security group allows your IP
   - Verify credentials are correct

2. **IAM Role Error**
   - Verify IAM role ARN is correct
   - Check role has S3 read permissions
   - Verify role is attached to Redshift cluster

3. **S3 Access Denied**
   - Verify S3 bucket exists: `s3://sk-manasa/bq_rs_staging/`
   - Check IAM role has access to bucket
   - Verify files exist in S3

### Get Help
If the migration fails, the logs will show detailed error messages with:
- Error type
- Error message
- Suggested fixes
- Error codes

## 📝 Notes

- **Data is safe**: All data is already in S3, so you can retry as many times as needed
- **Idempotent**: The load stage will drop and recreate tables if they exist
- **No data loss**: Source data remains in GCS (delete_source was false)
- **Fixed code**: The session management bug is fixed, so checkpoints will save correctly

## 🎯 Ready to Go!

The migration is reset and ready to run. Just click "Run" in the UI and watch it complete successfully!

---

**Migration ID**: 17  
**Migration Name**: bigquery_redshift_transfer  
**Status**: Pending (ready to run)  
**Fix Applied**: ✅ Session management fix deployed  
