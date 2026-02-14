# Testing Guide: Real Migrations List

## Quick Test Steps

### 1. Start Backend Server

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

### 2. Start Frontend Server

```bash
cd frontend
npm run dev
```

### 3. Verify Database Table

```bash
cd backend
psql -U manasakallakuri -d datamiq -c "\d migrations_bq_redshift"
```

Expected output: Table structure with all columns

### 4. Create a Test Migration

1. Open browser: `http://localhost:3000`
2. Login if needed
3. Navigate to **Data Migrations** page
4. Click **+ New** → **Create**
5. Fill in the wizard:

**Step 1: Strategy Selection**
- Select **Pathway A: GCP Storage Transfer Service**
- Click **Next**

**Step 2: Connection & Staging**
- Source Connection: Select a BigQuery connection
- Target Connection: Select a Redshift connection
- Click **Next**

**Step 3: Metadata Discovery**
- Select dataset and tables
- Click **Next**

**Step 4: Configuration Setup**
- GCS Bucket: `gs://my-staging-bucket`
- GCS Region: Select any region
- S3 Bucket: `my-s3-staging-bucket`
- S3 Region: Select any region
- Click **Next**

**Step 5: Scheduling & Monitoring**
- Migration Name: `Test Migration 1`
- Schedule: One-time
- Click **Create Migration**

### 5. Verify Migration Appears

1. You should see success message
2. Navigate back to **Data Migrations** page
3. **Expected**: Your migration appears in the list
4. **Verify**:
   - Migration name: "Test Migration 1"
   - Status: "Pending" (yellow badge)
   - Source: Shows project.dataset
   - Destination: Shows cluster/database
   - Created By: "System"
   - Last Run At: "Just now" or "X mins ago"

### 6. Verify in Database

```bash
psql -U manasakallakuri -d datamiq -c "
SELECT 
  id, 
  migration_name, 
  pathway, 
  status, 
  source_project_id, 
  source_dataset,
  target_cluster,
  target_database,
  created_at 
FROM migrations_bq_redshift 
ORDER BY created_at DESC 
LIMIT 5;
"
```

Expected: Your migration record in the database

### 7. Test Migration Actions

**Test Migration**:
1. Click the three-dot menu on your migration
2. Click **Test Migration**
3. Should show status information

**Update Migration**:
1. Click three-dot menu
2. Click **Update Migration**
3. Modal opens with current values
4. Make changes and save

**Delete Migration**:
1. Click three-dot menu
2. Click **Delete Migration**
3. Confirm deletion
4. Migration removed from list

### 8. Test Empty State

```bash
# Delete all migrations
psql -U manasakallakuri -d datamiq -c "DELETE FROM migrations_bq_redshift;"
```

Refresh the Migrations page:
- Should show "No migrations found"
- Should show "Create Your First Migration" button

## Troubleshooting

### Issue: "Failed to load migrations" alert

**Check**:
1. Backend server is running on port 8000
2. Check browser console for errors
3. Check backend logs for errors
4. Verify auth token exists: `localStorage.getItem('auth_token')`

**Fix**:
```bash
# Restart backend
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

### Issue: Migration created but not appearing

**Check Database**:
```bash
psql -U manasakallakuri -d datamiq -c "SELECT COUNT(*) FROM migrations_bq_redshift;"
```

If count is 0, the migration wasn't saved. Check:
1. Backend logs for errors during creation
2. Browser network tab for failed POST request
3. Database connection is working

**Check API Response**:
Open browser DevTools → Network tab → Look for:
- POST `/api/migrations/bq-redshift/create` - Should return 201
- GET `/api/migrations/bq-redshift/list` - Should return array

### Issue: Table doesn't exist

```bash
# Recreate table
psql -U manasakallakuri -d datamiq -f - <<EOF
CREATE TABLE IF NOT EXISTS migrations_bq_redshift (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL DEFAULT 1,
    migration_name VARCHAR(255) NOT NULL,
    pathway VARCHAR(10) NOT NULL CHECK (pathway IN ('A', 'B', 'C', 'D')),
    source_connection_id INTEGER,
    source_project_id VARCHAR(255),
    source_dataset VARCHAR(255),
    source_tables TEXT[],
    target_connection_id INTEGER,
    target_cluster VARCHAR(255),
    target_database VARCHAR(255),
    target_schema VARCHAR(255),
    gcs_bucket VARCHAR(255),
    gcs_path VARCHAR(500),
    s3_bucket VARCHAR(255),
    s3_path VARCHAR(500),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    current_stage VARCHAR(50),
    checkpoint_data JSONB,
    manifest_uri TEXT,
    resume_point VARCHAR(100),
    schedule_type VARCHAR(50),
    cron_expression VARCHAR(100),
    next_run_time TIMESTAMP,
    total_rows_source BIGINT,
    total_rows_target BIGINT,
    total_bytes_transferred BIGINT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds INTEGER,
    created_by INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_migrations_bq_redshift_workspace ON migrations_bq_redshift(workspace_id);
CREATE INDEX IF NOT EXISTS idx_migrations_bq_redshift_status ON migrations_bq_redshift(status);
EOF
```

### Issue: Sample data still showing

**Clear browser cache**:
1. Open DevTools (F12)
2. Right-click refresh button
3. Select "Empty Cache and Hard Reload"

Or:
```bash
# Rebuild frontend
cd frontend
npm run build
```

## Expected Console Output

### Backend (when creating migration)
```
INFO:     POST /api/migrations/bq-redshift/create
INFO:     Created migration: Test Migration 1 (ID: 1)
INFO:     200 OK
```

### Frontend (when loading migrations)
```
Fetched migrations from API: [{...}]
✓ Loaded 1 migrations from database
```

## Success Indicators

✅ No sample data visible (no "Customer Data Migration Q1 2026", etc.)  
✅ Created migrations appear immediately  
✅ Empty state shows when no migrations exist  
✅ Status badges display correctly  
✅ Actions menu works (test, update, delete)  
✅ Database contains migration records  
✅ API returns real data  
✅ No errors in console  

## Common Errors

### "relation migrations_bq_redshift does not exist"
→ Run the CREATE TABLE script above

### "Failed to fetch migrations"
→ Backend server not running or wrong port

### "Authentication required"
→ Login again to refresh token

### "workspace_id violates foreign key constraint"
→ Model still has FK constraint, check model file was updated

## Next Steps After Testing

1. ✅ Verify migrations are persisted across page refreshes
2. ✅ Test with multiple migrations (create 3-5)
3. ✅ Test pagination with many migrations
4. ✅ Test search functionality
5. ✅ Test status filtering
6. ✅ Monitor performance with large datasets

## Clean Up Test Data

```bash
# Delete test migrations
psql -U manasakallakuri -d datamiq -c "
DELETE FROM migrations_bq_redshift 
WHERE migration_name LIKE 'Test%';
"
```
