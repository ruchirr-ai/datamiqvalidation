# Verification Checklist

## ✅ Database Setup

```bash
# Check table exists
psql -U manasakallakuri -d datamiq -c "\dt migrations_bq_redshift"
```

**Expected**: Table listed

```bash
# Check table structure
psql -U manasakallakuri -d datamiq -c "\d migrations_bq_redshift"
```

**Expected**: All columns visible (id, workspace_id, migration_name, pathway, etc.)

```bash
# Check current data
psql -U manasakallakuri -d datamiq -c "SELECT COUNT(*) FROM migrations_bq_redshift;"
```

**Expected**: Number (0 if no migrations created yet)

## ✅ Backend Model

Check `backend/models/bq_redshift_migration.py`:

```python
# Should have this (no FK constraint):
workspace_id = Column(Integer, nullable=False, default=1)

# Should NOT have this:
# workspace_id = Column(Integer, ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False)
```

## ✅ Frontend Code

Check `frontend/src/pages/MigrationsPage.tsx`:

**Should NOT contain**:
- ❌ `getSampleMigrations()` function
- ❌ Sample data like "Customer Data Migration Q1 2026"
- ❌ Fallback to `getSampleMigrations()` on error

**Should contain**:
- ✅ Direct API call: `await bqRedshiftApi.listMigrations()`
- ✅ Error handling: `alert(\`Failed to load migrations: ${err.message}\`)`
- ✅ Empty array on error: `setMigrations([])`

## ✅ API Endpoint

```bash
# Test list endpoint (replace TOKEN with your auth token)
curl -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/migrations/bq-redshift/list
```

**Expected**: JSON array (empty `[]` or with migrations)

## Quick Test

1. **Start Backend**:
   ```bash
   cd backend
   source .venv/bin/activate
   uvicorn main:app --reload --port 8000
   ```

2. **Start Frontend**:
   ```bash
   cd frontend
   npm run dev
   ```

3. **Open Browser**: `http://localhost:3000/migrations`

4. **Expected Results**:
   - If no migrations: "No migrations found" + "Create Your First Migration" button
   - If migrations exist: List of real migrations from database
   - NO sample data like "Customer Data Migration", "Analytics Tables", etc.

## Create Test Migration

1. Click **+ New** → **Create**
2. Fill wizard with any values
3. Click **Create Migration**
4. Return to Migrations page
5. **Verify**: Your migration appears in the list

## Verification Commands

```bash
# All in one check
cd backend

echo "=== Checking Database Table ==="
psql -U manasakallakuri -d datamiq -c "SELECT COUNT(*) as migration_count FROM migrations_bq_redshift;"

echo ""
echo "=== Checking Recent Migrations ==="
psql -U manasakallakuri -d datamiq -c "SELECT id, migration_name, pathway, status, created_at FROM migrations_bq_redshift ORDER BY created_at DESC LIMIT 5;"

echo ""
echo "=== Checking Model File ==="
grep -n "workspace_id.*ForeignKey" models/bq_redshift_migration.py && echo "❌ FK constraint still exists!" || echo "✅ FK constraint removed"

echo ""
echo "=== Checking Frontend File ==="
grep -n "getSampleMigrations" ../frontend/src/pages/MigrationsPage.tsx && echo "❌ Sample data still exists!" || echo "✅ Sample data removed"
```

## Success Indicators

✅ Database table exists  
✅ Model has no FK constraint to workspaces  
✅ Frontend has no sample data function  
✅ API returns real data  
✅ Empty state shows when no migrations  
✅ Created migrations appear immediately  
✅ No dummy data visible in UI  

## If Something's Wrong

### Table doesn't exist
→ Run CREATE TABLE script from `MIGRATIONS_LIST_REAL_DATA_FIXED.md`

### Model has FK constraint
→ Edit `backend/models/bq_redshift_migration.py` and remove ForeignKey

### Sample data still showing
→ Check `frontend/src/pages/MigrationsPage.tsx` for `getSampleMigrations`

### API returns 500 error
→ Check backend logs, likely model/database mismatch

### Migrations not appearing
→ Check browser console and network tab for errors
