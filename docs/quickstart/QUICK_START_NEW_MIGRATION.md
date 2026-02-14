# Quick Start: Test New Migration

## ✅ Server Status: Running & Ready

Backend server is running on port 8000 with the S3 → Redshift connection fix deployed.

## Create New Migration (UI)

1. **Open UI**: http://localhost:3000
2. **Navigate**: Migrations page
3. **Click**: "Create Migration" button
4. **Configure**:
   - **Source**: Select BigQuery connection
   - **Target**: Select Redshift connection
   - **Pathway**: Choose "C - CLI/Legacy"
   - **Tables**: Select tables to migrate
   - **Storage**: Configure GCS and S3 buckets
5. **Start**: Click "Start Migration"

## What to Expect

### Stage 1: Export (BigQuery → GCS)
```
✓ Connecting to BigQuery
✓ Exporting table 1 of 3
✓ Exporting table 2 of 3
✓ Exporting table 3 of 3
✓ Export stage completed
```

### Stage 2: Transfer (GCS → S3)
```
✓ Initializing GCS to S3 transfer
✓ Transferring files
✓ Transfer completed
✓ Transfer stage completed
```

### Stage 3: Load (S3 → Redshift) - NOW FIXED!
```
================================================================================
FETCHING TARGET CONNECTION FROM DATABASE
================================================================================
✓ Found target connection: Redshift Production
Connection params keys: ['server_name', 'port', 'database_name', 'username', 'password_encrypted']

================================================================================
REDSHIFT CONNECTION DETAILS
================================================================================
Cluster: redshift-cluster-1.abc123.us-east-1.redshift.amazonaws.com
Port: 5439
Initial Database: dev
User: admin
IAM Role: arn:aws:iam::123456789012:role/RedshiftS3AccessRole
================================================================================

✓ Connected to Redshift
✓ IAM role verified
✓ Creating database: assessiq_484512
✓ Creating schema: sales_analytics
✓ Creating table: assess_data
✓ Loading data from S3
✓ Verifying row count
✓ Load stage completed
```

## Monitor Progress

### Option 1: UI
Watch the migration progress in the UI - status updates in real-time.

### Option 2: Backend Logs
```bash
tail -f backend/backend.log
```

### Option 3: Check Status Script
```bash
cd backend
python check_migration_status.py
```

## Expected Timeline

- **Export**: 2-5 minutes (depends on data size)
- **Transfer**: 1-3 minutes (depends on file size)
- **Load**: 2-5 minutes (depends on table count and data size)

**Total**: ~5-15 minutes for small datasets

## Success Indicators

### In UI
- Status changes: `pending` → `running` → `completed`
- Progress bar reaches 100%
- All 3 stages show checkmarks ✓

### In Logs
- No error messages
- Each stage shows "completed"
- Row counts match between source and target

### In Redshift
Query to verify data loaded:
```sql
-- Check database exists
SELECT datname FROM pg_database WHERE datname = 'assessiq_484512';

-- Check schema exists
SELECT schema_name FROM information_schema.schemata 
WHERE schema_name = 'sales_analytics';

-- Check tables exist
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'sales_analytics';

-- Check row counts
SELECT COUNT(*) FROM assessiq_484512.sales_analytics.assess_data;
SELECT COUNT(*) FROM assessiq_484512.sales_analytics.customers;
SELECT COUNT(*) FROM assessiq_484512.sales_analytics.orders;
```

## Troubleshooting

### If Export Fails
- Check BigQuery connection credentials
- Verify GCS bucket exists and is accessible
- Check BigQuery dataset and tables exist

### If Transfer Fails
- Check GCS bucket name (no double `gs://`)
- Verify S3 bucket exists and is accessible
- Check AWS credentials are valid

### If Load Fails
- Check Redshift connection details
- Verify IAM role has S3 access
- Check S3 files exist from transfer stage
- Review detailed error messages in logs

## Connection Requirements Checklist

### BigQuery Connection
- ✓ Project ID
- ✓ Service account credentials
- ✓ Dataset access

### Redshift Connection
- ✓ Cluster endpoint (server_name or host)
- ✓ Port (default: 5439)
- ✓ Database name
- ✓ Username
- ✓ Password (encrypted)

### Migration Settings
- ✓ IAM role ARN (for Redshift S3 access)
- ✓ AWS access key ID
- ✓ AWS secret access key (encrypted)
- ✓ GCS bucket name
- ✓ S3 bucket name

## What's Different Now

### Before (Broken)
- ❌ Used target_config directly
- ❌ Didn't fetch from database
- ❌ Failed on field name variations
- ❌ Generic error messages

### After (Fixed)
- ✅ Fetches connection from database
- ✅ Handles all field name variations
- ✅ Detailed logging at each step
- ✅ Clear error messages with hints

## Ready to Test!

Everything is set up and ready. Create a new migration to test the complete BigQuery → GCS → S3 → Redshift flow!

**Server**: ✅ Running on port 8000
**Fix**: ✅ Deployed in PathwayC
**Logs**: ✅ Enhanced with detailed output
**Status**: 🚀 Ready for production testing
