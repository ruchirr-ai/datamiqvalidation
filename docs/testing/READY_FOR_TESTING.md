# Ready for Testing - Migration System

## Status: ✅ READY FOR FRESH TESTING

The database has been cleaned (0 migrations) and all fixes have been applied. The system is ready for end-to-end testing from scratch.

---

## What Was Fixed

### 1. Migration Execution Issue (FIXED ✅)
**Problem**: Migrations were stuck in "running" state with no logs
**Root Cause**: Main thread was setting status to 'running' BEFORE starting background thread, causing orchestrator to refuse execution
**Solution**: 
- Removed premature status setting - let orchestrator handle it
- Configured background thread logger with proper handlers
- Improved error logging to always log to database

**Files Changed**:
- `backend/routers/bq_redshift_migration.py` - Removed status setting before thread start
- Background thread now properly logs all stages

### 2. Table/Dataset Mismatch Issue (FIXED ✅)
**Problem**: Frontend was sending tables from different datasets mixed together
**Root Cause**: Frontend stored tables as `dataset.table` and sent them directly without filtering
**Solution**:
- Filter tables to only include those from selected dataset
- Strip dataset prefix before sending to backend
- Send clean table names like `['customers', 'orders']`
- Validate and warn if tables from multiple datasets are selected

**Files Changed**:
- `frontend/src/components/migrations/CreateMigrationWizard.tsx` - Added filtering and validation

### 3. GCS Export Path Structure (FIXED ✅)
**Problem**: Export paths were inconsistent
**Solution**: Organized GCS export path structure to `bucket/dataset/table/filename`
- Removed staging prefix
- Clean, organized structure

**Files Changed**:
- `backend/services/bq_redshift_migration/bigquery_exporter.py`

### 4. GCS Region Support (FIXED ✅)
**Problem**: GCS region not being used in BigQuery operations
**Solution**: Extract region from connection params and pass to BigQuery client
- Defaults to 'us-central1' if not specified

**Files Changed**:
- `backend/services/bq_redshift_migration/bigquery_exporter.py`

### 5. TypeScript Errors (FIXED ✅)
**Problem**: Missing `compression` property in MigrationFormData interface
**Solution**: Added compression field to interface and initial data

**Files Changed**:
- `frontend/src/components/migrations/CreateMigrationWizard.tsx`

---

## System Architecture

### Migration Flow
```
1. User creates migration in UI
   ↓
2. Frontend validates and sends to backend
   ↓
3. Backend creates migration record (status: 'pending')
   ↓
4. User clicks "Run Migration"
   ↓
5. Backend starts background thread
   ↓
6. Orchestrator sets status to 'running' and begins execution
   ↓
7. Stage 1: Export BigQuery → GCS
   ↓
8. Stage 2: Transfer GCS → S3 (pathway-specific)
   ↓
9. Stage 3: Load S3 → Redshift
   ↓
10. Status updated to 'completed' or 'failed'
```

### Key Components

#### Backend
- **Router**: `backend/routers/bq_redshift_migration.py`
  - Handles all API endpoints
  - Starts migrations in background threads
  - Manages migration lifecycle

- **Orchestrator**: `backend/services/bq_redshift_migration/orchestrator.py`
  - Coordinates migration execution
  - Manages state transitions
  - Handles error recovery

- **BigQuery Exporter**: `backend/services/bq_redshift_migration/bigquery_exporter.py`
  - Exports tables from BigQuery to GCS
  - Supports multiple formats (AVRO, PARQUET, CSV, JSON)
  - Supports compression (GZIP, SNAPPY, DEFLATE, ZSTD)

#### Frontend
- **Wizard**: `frontend/src/components/migrations/CreateMigrationWizard.tsx`
  - 5-step migration creation wizard
  - Validates input at each step
  - Filters tables by selected dataset

- **Migrations Page**: `frontend/src/pages/MigrationsPage.tsx`
  - Lists all migrations
  - Shows status, progress, logs
  - Allows run, pause, cancel, delete operations

---

## Testing Guide

### Prerequisites
1. Backend server running on port 8000
2. Frontend server running on port 3000
3. Login credentials: admin / admin123
4. BigQuery connection configured (ID: 1)
5. Redshift connection configured (ID: 2)

### Test Scenario 1: Create and Run Migration

#### Step 1: Create Migration
1. Navigate to Migrations page
2. Click "Create Migration"
3. Fill in wizard:
   - **Step 1**: Select connections
     - Migration Name: "Test Migration 1"
     - Source: BigQuery connection
     - Target: Redshift connection
   
   - **Step 2**: Discover metadata
     - Project ID: assessiq-484512
     - Click "Discover Datasets"
     - Select dataset: `sales_analytics`
     - Click "Load Tables"
     - Select tables: `customers`, `orders`
   
   - **Step 3**: Select strategy
     - Choose Pathway A (GCP Native)
   
   - **Step 4**: Configure
     - GCS Bucket: bq_data_transfer_rs
     - Export Format: PARQUET
     - Compression: NONE
     - S3 Bucket: (your S3 bucket)
   
   - **Step 5**: Schedule
     - Schedule Type: One-time
     - Enable checkpointing: Yes

4. Click "Create Migration"
5. Verify migration appears in list with status "pending"

#### Step 2: Run Migration
1. Find the migration in the list
2. Click the "Run" button (play icon)
3. Observe:
   - Status changes to "running"
   - Progress percentage updates
   - Logs appear in real-time

#### Step 3: Monitor Progress
1. Click "View Logs" to see detailed logs
2. Watch for these stages:
   - `init` - Migration thread started
   - `export` - BigQuery export to GCS
   - `transfer` - GCS to S3 transfer (pathway-specific)
   - `load` - S3 to Redshift load

#### Step 4: Verify Completion
1. Status should change to "completed"
2. Check logs for success messages
3. Verify data in GCS bucket:
   - Path: `bq_data_transfer_rs/sales_analytics/customers/`
   - Path: `bq_data_transfer_rs/sales_analytics/orders/`

### Test Scenario 2: Error Handling

#### Test Invalid Dataset
1. Create migration with non-existent dataset
2. Run migration
3. Verify error is logged and status is "failed"

#### Test Invalid Table
1. Create migration with non-existent table
2. Run migration
3. Verify error is logged for that table
4. Other tables should still export successfully

### Test Scenario 3: Delete Migration

1. Create a test migration
2. Ensure it's NOT running
3. Click delete button
4. Confirm deletion
5. Verify migration is removed from list
6. Verify logs are also deleted (cascade delete)

### Test Scenario 4: Multiple Tables

1. Create migration with 3+ tables
2. Run migration
3. Verify all tables are exported
4. Check logs for each table
5. Verify progress percentage updates correctly

---

## Expected Behavior

### Successful Migration
```
Status: pending → running → completed
Logs:
  [INFO] Migration thread started - beginning execution
  [INFO] Starting migration (Pathway A)
  [INFO] Starting BigQuery export to GCS
  [INFO] Exporting 2 tables from sales_analytics
  [INFO] ✓ Table customers exported successfully
  [INFO] ✓ Table orders exported successfully
  [INFO] Export completed: 2/2 tables exported successfully
  [INFO] ✓ BigQuery export completed successfully
  [INFO] ✓ Pathway A execution completed successfully
  [INFO] Migration completed successfully
```

### Failed Migration
```
Status: pending → running → failed
Logs:
  [INFO] Migration thread started - beginning execution
  [INFO] Starting migration (Pathway A)
  [INFO] Starting BigQuery export to GCS
  [ERROR] Failed to export table invalid_table: Table not found
  [ERROR] BigQuery export failed
  [ERROR] Migration failed
```

---

## Known Limitations

1. **Pathway Implementation**: Only Pathway A (BigQuery → GCS) is fully implemented
   - Pathways B, C, D need GCS → S3 and S3 → Redshift implementation

2. **Workspace Filtering**: Not yet implemented
   - All users can see all migrations
   - Workspace ID is hardcoded to 1

3. **Connection Credentials**: Hardcoded in orchestrator
   - Should be fetched from connection records
   - Should use AWS Secrets Manager

4. **Validation**: Post-migration validation not implemented
   - Row count comparison
   - Data integrity checks

---

## Database State

### Current State
- **Migrations**: 0 (clean database)
- **Logs**: 0
- **Connections**: 2 (BigQuery and Redshift)

### Tables
- `migrations_bq_redshift` - Migration records
- `migration_logs` - Migration logs (cascade delete)
- `migration_shards` - Migration shards (cascade delete)
- `connections` - Database connections

---

## Troubleshooting

### Migration Stuck in Running
**Symptom**: Migration status is "running" but no logs appear
**Solution**: This should be fixed now. If it happens:
1. Check backend logs for errors
2. Check if background thread started
3. Verify orchestrator is executing

### No Logs Appearing
**Symptom**: Migration is running but logs don't show
**Solution**: This should be fixed now. Background thread logger is configured.

### Table Not Found
**Symptom**: Error "Table not found" in logs
**Solution**: 
1. Verify table exists in BigQuery
2. Verify dataset is correct
3. Check connection credentials

### Export Failed
**Symptom**: BigQuery export fails
**Solution**:
1. Check GCS bucket exists and is accessible
2. Verify service account has permissions
3. Check BigQuery quota limits

---

## Next Steps

### For Testing
1. Create a new migration from UI
2. Run the migration
3. Monitor logs and progress
4. Report any issues you encounter

### For Development
1. Implement Pathways B, C, D (GCS → S3 → Redshift)
2. Add workspace filtering
3. Implement connection credential fetching
4. Add post-migration validation
5. Add retry logic for failed shards

---

## Quick Commands

### Start Backend
```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

### Start Frontend
```bash
cd frontend
npm run dev
```

### Check Database
```bash
psql -U manasakallakuri -d datamiq -c "SELECT id, migration_name, status, current_stage FROM migrations_bq_redshift;"
```

### View Logs
```bash
psql -U manasakallakuri -d datamiq -c "SELECT log_level, stage, message FROM migration_logs WHERE migration_id = 1 ORDER BY created_at;"
```

---

## Contact

If you encounter any issues during testing, please provide:
1. Migration ID
2. Error message from UI
3. Backend logs
4. Database state (migration status, logs)

This will help diagnose and fix any remaining issues quickly.
