# Quick Test Guide - BigQuery Export

## Prerequisites ✅
- ✅ Database migration completed (006_add_export_format_compression)
- ✅ Backend server running on port 8000
- ✅ Frontend server running on port 3000
- ✅ BigQuery connections exist in database (IDs: 2, 3, 6)

## Test Steps

### 1. Create a New Migration

1. Navigate to: http://localhost:3000/migrations

2. Click "Create Migration" button

3. **Step 1: Connection & Staging**
   - Migration Type: BigQuery to Redshift
   - Migration Name: "Test Export Migration"
   - Pathway: A (GCP Native)

4. **Step 2: Metadata Discovery**
   - Source Connection: Select any BigQuery connection (ID 2, 3, or 6)
   - Project ID: assessiq-484512 (auto-filled)
   - Click "Discover Metadata"
   - Wait for datasets to load
   - Select Dataset: sales_analytics
   - Select Tables: Check one or more tables (e.g., assess_tbl)

5. **Step 3: Configuration Setup**
   - **BigQuery to GCS Export**:
     - Export Format: AVRO
     - Compression: SNAPPY
     - GCS Bucket: Enter your bucket name (e.g., "my-test-bucket")
     - GCS Region: us-central1
   
   - **GCS to S3 Transfer**: (Coming Soon - skip for now)
   
   - **S3 to Redshift Load**: (Coming Soon - skip for now)
   
   - Target Connection: Select any Redshift connection

6. **Step 4: Scheduling & Monitoring**
   - Schedule Type: One-time (or leave as is)
   - Click "Create Migration"

7. **Verify Creation**
   - Should see success message
   - Should redirect to migrations list
   - Should see your new migration with status "pending"

### 2. Run the Migration

1. Find your migration in the list

2. Click the three-dot menu (⋮) on the right

3. Click "Run Migration"

4. **Watch Backend Logs**:
   ```bash
   tail -f backend/server.log
   ```

5. **Expected Log Output**:
   ```
   === Starting Migration Execution: X (Pathway A) ===
   Step 1: Exporting data from BigQuery to GCS
   Source connection: [Connection Name]
   Initializing BigQuery exporter (project: assessiq-484512, region: us-central1)
   Export configuration: format=AVRO, compression=SNAPPY
   Exporting 1 tables: ['assess_tbl']
   Exporting table assess_tbl to gs://my-test-bucket/staging/assess_tbl/*.avro.snappy
   ✓ Export job completed successfully
   ✓ BigQuery export completed successfully
   ```

### 3. Verify Export Results

#### Option A: Check GCS Bucket
```bash
# List files in GCS bucket
gsutil ls gs://your-bucket-name/staging/

# Should see files like:
# gs://your-bucket-name/staging/assess_tbl/000000000000.avro.snappy
# gs://your-bucket-name/staging/assess_tbl/000000000001.avro.snappy
# ...
```

#### Option B: Check Database
```sql
-- Connect to PostgreSQL
psql -U manasakallakuri -d datamiq

-- Check migration status
SELECT id, migration_name, status, current_stage, progress_percentage
FROM migrations_bq_redshift
WHERE migration_name = 'Test Export Migration';

-- Check checkpoint data (export results)
SELECT checkpoint_data
FROM migrations_bq_redshift
WHERE migration_name = 'Test Export Migration';

-- Should see JSON with export_results:
-- {
--   "export_results": [
--     {
--       "table_id": "assess_tbl",
--       "success": true,
--       "destination_uris": ["gs://.../*.avro.snappy"],
--       "num_files": 42
--     }
--   ],
--   "export_completed_at": "2026-02-08T..."
-- }
```

#### Option C: Check Migration Logs
```sql
-- View migration logs
SELECT log_level, stage, message, created_at
FROM migration_logs
WHERE migration_id = X
ORDER BY created_at DESC
LIMIT 20;
```

### 4. Test Different Formats/Compressions

Repeat the test with different combinations:

**Test Case 1: Parquet with GZIP**
- Format: PARQUET
- Compression: GZIP
- Expected files: `*.parquet.gz`

**Test Case 2: CSV with GZIP**
- Format: CSV
- Compression: GZIP
- Expected files: `*.csv.gz`

**Test Case 3: JSON with None**
- Format: JSON
- Compression: NONE
- Expected files: `*.json`

**Test Case 4: AVRO with DEFLATE**
- Format: AVRO
- Compression: DEFLATE
- Expected files: `*.avro.deflate`

## Troubleshooting

### Error: "Service account key not found"
**Solution**: Check connection in database:
```sql
SELECT id, name, connection_params
FROM connections
WHERE id = X;

-- Ensure connection_params has:
-- {
--   "service_account_key": "{...json...}",
--   "project_id": "assessiq-484512",
--   "region": "us-central1"
-- }
```

### Error: "Permission denied"
**Solution**: Ensure service account has these roles:
- BigQuery Data Editor
- Storage Object Creator
- Storage Object Viewer

### Error: "Migration failed"
**Check logs**:
```bash
# Backend logs
tail -f backend/server.log

# Database logs
SELECT * FROM migration_logs WHERE migration_id = X ORDER BY created_at DESC;
```

### Migration Stuck in "running"
**Check status**:
```sql
-- Check current status
SELECT id, status, current_stage, progress_percentage, updated_at
FROM migrations_bq_redshift
WHERE id = X;

-- If stuck, manually update:
UPDATE migrations_bq_redshift
SET status = 'failed', updated_at = NOW()
WHERE id = X;
```

## Success Criteria

✅ Migration created successfully with status='pending'
✅ Migration starts when "Run Migration" clicked
✅ Backend logs show export progress
✅ Files appear in GCS bucket with correct format/compression
✅ Migration status updates to 'completed' (or 'failed' with error logs)
✅ checkpoint_data contains export_results
✅ progress_percentage shows 100%

## Next Steps After Successful Test

1. ✅ BigQuery → GCS export working
2. ⏳ Implement GCS → S3 transfer (Pathway A, B, C, D)
3. ⏳ Implement S3 → Redshift COPY command
4. ⏳ Add real-time progress tracking
5. ⏳ Add export cancellation support
6. ⏳ Add validation and checksum verification

## Quick Commands

```bash
# Restart backend server
cd backend
./restart_server.sh

# Run database migration
cd backend
.venv/bin/alembic upgrade head

# Check backend logs
tail -f backend/server.log

# Check database
psql -U manasakallakuri -d datamiq

# List GCS files
gsutil ls gs://your-bucket/staging/
```

## Test Data

**Available BigQuery Connections**:
- ID 2: BigQuery connection with assessiq-484512 project
- ID 3: BigQuery connection with assessiq-484512 project
- ID 6: BigQuery connection with assessiq-484512 project

**Available Dataset**:
- sales_analytics (6 tables, including assess_tbl with 10M rows)

**Available Tables**:
- assess_tbl (10M rows, 10.5 GB)
- Other tables in sales_analytics dataset
