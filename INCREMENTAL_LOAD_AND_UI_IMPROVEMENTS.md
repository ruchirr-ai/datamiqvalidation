# Incremental Load & UI Improvements Summary

## Deployment Status: ✅ COMPLETE

All changes have been committed to `shivansh-dev` branch and deployed to EC2 (54.156.223.137).

---

## 1. IST Timezone Conversion ✅

**Status:** Deployed

**Changes:**
- Migration log timestamps now display in IST (Asia/Kolkata) timezone instead of UTC
- Format: `MM/DD/YYYY, HH:MM:SS AM/PM`
- Backend still stores timestamps in UTC (correct practice)
- Frontend converts to IST for display only

**Files Modified:**
- `frontend/src/pages/MigrationsPage.tsx`

---

## 2. Incremental Load Implementation ✅

**Status:** Already Implemented & Working

**How It Works:**
1. User creates a migration with `load_type: 'incremental'`
2. User specifies `timestamp_column` (e.g., `updated_at`) per table
3. On first run, all data is exported and loaded
4. Backend stores `last_extracted_value` (timestamp of last run)
5. On subsequent runs:
   - BigQuery exporter creates temp table with filter: `WHERE timestamp_column > last_extracted_value`
   - Only changed rows are exported to GCS
   - Redshift loader uses MERGE (DELETE + INSERT) based on `primary_key_column`
   - `last_extracted_value` is updated to current timestamp

**Key Files:**
- `backend/services/bq_redshift_migration/bigquery_exporter.py` - Incremental filtering
- `backend/services/bq_redshift_migration/redshift_loader.py` - MERGE logic
- `backend/services/bq_redshift_migration/orchestrator.py` - Updates `last_extracted_value`
- `backend/models/bq_redshift_migration.py` - Stores `last_extracted_value`, `timestamp_column`

**Database Fields:**
- `load_type` - 'full' or 'incremental'
- `primary_key_column` - For MERGE operations
- `timestamp_column` - For incremental filtering
- `last_extracted_value` - Bookmark for next incremental run
- `table_load_configs` - Per-table configuration (JSONB)

---

## 3. Improved Load Type UI ✅

**Status:** Deployed

**Changes:**

### Single Table Configuration:
- Clean, simple form with two fields:
  - Primary Key Column
  - Timestamp Column

### Multiple Tables Configuration:
- Improved table layout with 5 columns:
  - **TABLE** - Table name
  - **LOAD TYPE** - Dropdown (Incremental/Full)
  - **PRIMARY KEY** - Input field (disabled for Full load)
  - **TIMESTAMP COL** - Input field (disabled for Full load)
  - **TRUNCATE** - Toggle button (per-table truncate option)

**UI Improvements:**
- Cleaner header styling with uppercase labels
- Better spacing and borders
- Improved color scheme (#F5F5F5 header, #E0E0E0 borders)
- Disabled fields show with reduced opacity and grey background
- Each table can have different load type (Incremental or Full)

**Files Modified:**
- `frontend/src/components/migrations/steps/ConfigurationSetupStep.tsx`

---

## 4. Per-Table Truncate Option ✅

**Status:** Deployed

**Changes:**
- Removed global "Truncate Before Load" toggle
- Added per-table truncate toggle in the configuration table
- Each table can independently have truncate enabled/disabled
- Stored in `table_load_configs` JSONB field: `{ "table_name": { "truncate_before_load": true/false } }`

**Backend Support:**
- `pathway_c.py` updated to read per-table truncate setting
- Falls back to global setting if not specified per-table
- Logs show truncate status per table

**Files Modified:**
- `frontend/src/components/migrations/steps/ConfigurationSetupStep.tsx`
- `backend/services/bq_redshift_migration/pathway_c.py`

---

## 5. Toggle Button Blue Color Fix ✅

**Status:** Deployed

**Changes:**
- Toggle now shows bright blue (#2563EB) when enabled
- Grey (#D1D5DB) when disabled
- Hover states: darker blue (#1D4ED8) when enabled, darker grey (#9CA3AF) when disabled
- Adjusted toggle width from 48px to 44px for better proportions
- Handle translation adjusted to 20px (from 24px)

**Files Modified:**
- `frontend/src/components/ui/Toggle.css`

---

## How to Use Incremental Load

### Step 1: Create Migration
1. Go to Migrations page → Click "New" → "Create"
2. Select source (BigQuery) and target (Redshift) connections
3. Choose tables to migrate

### Step 2: Configure Load Type
1. In Stage 3 (Redshift Load Configuration), select "Incremental Load"
2. For each table, specify:
   - **Primary Key Column** - Unique identifier (e.g., `id`)
   - **Timestamp Column** - Change tracking column (e.g., `updated_at`, `modified_at`)
   - **Load Type** - Choose "Incremental" or "Full" per table
   - **Truncate** - Toggle on/off per table

### Step 3: Run Migration
1. First run: All data is migrated
2. Subsequent runs: Only changed rows (based on timestamp) are migrated
3. Backend automatically tracks `last_extracted_value`

### Step 4: Verify
- Check migration logs to see incremental filtering in action
- Logs will show: `"Incremental mode: filtering WHERE updated_at > '2026-03-03T08:00:00'"`

---

## Technical Details

### Per-Table Configuration Structure

```json
{
  "table_name": {
    "load_type": "incremental",
    "primary_key_column": "id",
    "timestamp_column": "updated_at",
    "truncate_before_load": false
  }
}
```

### Incremental Load SQL Logic

**BigQuery Export (Temp Table):**
```sql
CREATE OR REPLACE TABLE `project.dataset._tmp_export_table_123456` AS
SELECT * FROM `project.dataset.table`
WHERE `updated_at` > TIMESTAMP('2026-03-03T08:00:00')
```

**Redshift Load (MERGE):**
```sql
-- Step 1: COPY into staging table
COPY schema._staging_table FROM 's3://bucket/path/'
IAM_ROLE 'arn:aws:iam::...' FORMAT AS PARQUET;

-- Step 2: DELETE matching rows
DELETE FROM schema.table
USING schema._staging_table
WHERE schema.table.id = schema._staging_table.id;

-- Step 3: INSERT from staging
INSERT INTO schema.table
SELECT * FROM schema._staging_table;
```

---

## Testing Checklist

- [x] IST timestamps display correctly in logs modal
- [x] Toggle button turns blue when enabled
- [x] Per-table load type dropdown works
- [x] Per-table truncate toggle works
- [x] Incremental load filters data correctly
- [x] MERGE operation updates existing rows
- [x] `last_extracted_value` is updated after each run
- [x] UI looks clean and professional
- [x] Changes deployed to EC2

---

## Files Changed

### Frontend:
1. `frontend/src/pages/MigrationsPage.tsx` - IST timezone conversion
2. `frontend/src/components/migrations/steps/ConfigurationSetupStep.tsx` - Improved UI, per-table truncate
3. `frontend/src/components/ui/Toggle.css` - Blue color fix

### Backend:
1. `backend/services/bq_redshift_migration/pathway_c.py` - Per-table truncate support

---

## Commit Messages

1. `Convert migration log timestamps from UTC to IST (Asia/Kolkata timezone)`
2. `Improve load type UI with per-table truncate option and fix toggle blue color`

---

## Next Steps (If Needed)

1. Add validation to ensure timestamp column exists in BigQuery table
2. Add UI indicator showing last run timestamp per table
3. Add option to manually set `last_extracted_value` for custom incremental runs
4. Add progress indicator showing how many rows were filtered in incremental mode

---

**Deployment Date:** March 3, 2026  
**Branch:** shivansh-dev  
**EC2 IP:** 54.156.223.137  
**Status:** ✅ All changes deployed and working
