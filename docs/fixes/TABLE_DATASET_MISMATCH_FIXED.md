# Table and Dataset Mismatch Issue - FIXED ✅

## Problem

When creating a migration, different tables and datasets were being picked up than the ones selected in the UI. For example:
- **Selected in UI**: Tables from `sales_analytics` dataset
- **Stored in database**: `{analytics.customers, analytics.orders, sales_analytics.orders}` with `source_dataset='analytics'`
- **Result**: Backend tries to export `sales_analytics.orders` from `analytics` dataset, which fails

## Root Cause

The frontend was storing selected tables with the full `dataset.table` format (e.g., `analytics.customers`, `sales_analytics.orders`), but when creating the migration:

1. **Frontend stored**: `selectedTables = ['analytics.customers', 'sales_analytics.orders']`
2. **Frontend sent to backend**: Same array with dataset prefixes
3. **Backend received**: `source_tables = ['analytics.customers', 'sales_analytics.orders']`
4. **Backend tried to export**: Tables with dataset prefixes from `source_dataset='analytics'`

This caused a mismatch where:
- Tables from multiple datasets were mixed together
- Table names included dataset prefixes when they shouldn't
- Backend couldn't find tables because it was looking in the wrong dataset

## Solution Applied

### Fix 1: Strip Dataset Prefix from Table Names

**File**: `frontend/src/components/migrations/CreateMigrationWizard.tsx`

Added logic to extract just the table names without the dataset prefix before sending to the backend:

```typescript
// Extract table names without dataset prefix
// selectedTables format: ['dataset.table1', 'dataset.table2']
// Filter to only include tables from the selected dataset
const tablesFromSelectedDataset = formData.selectedTables.filter(fullTableName => {
  const [dataset] = fullTableName.split('.');
  return dataset === formData.sourceDataset;
});

if (tablesFromSelectedDataset.length === 0) {
  throw new Error(`No tables selected from dataset "${formData.sourceDataset}". Please select tables from the correct dataset.`);
}

// Extract just the table names (without dataset prefix)
const tableNames = tablesFromSelectedDataset.map(fullTableName => {
  const parts = fullTableName.split('.');
  return parts.length > 1 ? parts[1] : fullTableName;
});

console.log('Selected tables (with dataset):', formData.selectedTables);
console.log('Tables from selected dataset:', tablesFromSelectedDataset);
console.log('Table names (without dataset):', tableNames);

// Send to backend
const migrationData = {
  ...
  source_dataset: formData.sourceDataset,
  source_tables: tableNames, // ✅ Now sends ['customers', 'orders'] instead of ['analytics.customers', 'analytics.orders']
  ...
};
```

### Fix 2: Filter Tables by Selected Dataset

Added validation to ensure only tables from the selected dataset are included in the migration:

```typescript
// Filter to only include tables from the selected dataset
const tablesFromSelectedDataset = formData.selectedTables.filter(fullTableName => {
  const [dataset] = fullTableName.split('.');
  return dataset === formData.sourceDataset;
});

if (tablesFromSelectedDataset.length === 0) {
  throw new Error(`No tables selected from dataset "${formData.sourceDataset}". Please select tables from the correct dataset.`);
}

if (tablesFromSelectedDataset.length < formData.selectedTables.length) {
  const skippedCount = formData.selectedTables.length - tablesFromSelectedDataset.length;
  console.warn(`Skipping ${skippedCount} tables from other datasets. Only migrating tables from "${formData.sourceDataset}"`);
}
```

## How It Works Now

### Before Fix
1. User selects tables: `analytics.customers`, `sales_analytics.orders`
2. User selects dataset: `analytics`
3. Frontend sends: `source_tables = ['analytics.customers', 'sales_analytics.orders']`
4. Backend tries to export from `analytics` dataset
5. ❌ Fails because `sales_analytics.orders` doesn't exist in `analytics` dataset

### After Fix
1. User selects tables: `analytics.customers`, `analytics.orders`, `sales_analytics.orders`
2. User selects dataset: `analytics`
3. Frontend filters: Only keeps `analytics.customers` and `analytics.orders`
4. Frontend strips prefixes: `['customers', 'orders']`
5. Frontend sends: `source_tables = ['customers', 'orders']`, `source_dataset = 'analytics'`
6. Backend exports: `customers` and `orders` from `analytics` dataset
7. ✅ Success!

## Example

### Scenario: User Selects Tables from Multiple Datasets

**User selections**:
- Dataset: `sales_analytics`
- Tables: 
  - ✅ `sales_analytics.customers` (from selected dataset)
  - ✅ `sales_analytics.orders` (from selected dataset)
  - ❌ `analytics.products` (from different dataset - will be filtered out)

**What gets sent to backend**:
```json
{
  "source_dataset": "sales_analytics",
  "source_tables": ["customers", "orders"]
}
```

**Console output**:
```
Selected tables (with dataset): ['sales_analytics.customers', 'sales_analytics.orders', 'analytics.products']
Tables from selected dataset: ['sales_analytics.customers', 'sales_analytics.orders']
Table names (without dataset): ['customers', 'orders']
⚠️ Skipping 1 tables from other datasets. Only migrating tables from "sales_analytics"
```

## Files Modified

- ✅ `frontend/src/components/migrations/CreateMigrationWizard.tsx` - Added table name extraction and dataset filtering

## Testing Steps

1. **Create a new migration**:
   - Go to Migrations page
   - Click "New" → "Create"
   - Select BigQuery source connection
   - In Metadata Discovery step, select tables from ONE dataset
   - Complete the wizard

2. **Verify in database**:
   ```sql
   SELECT id, migration_name, source_dataset, source_tables 
   FROM migrations_bq_redshift 
   WHERE id = <new_migration_id>;
   ```
   
   **Expected result**:
   - `source_dataset`: Should be the selected dataset (e.g., `sales_analytics`)
   - `source_tables`: Should contain ONLY table names without dataset prefix (e.g., `{customers, orders}`)

3. **Run the migration**:
   - Click "Run Migration"
   - Check logs to verify it's exporting from the correct dataset
   - Verify export succeeds

## Expected Behavior After Fix

1. ✅ Only tables from the selected dataset are included in the migration
2. ✅ Table names are sent without dataset prefix
3. ✅ Backend exports tables from the correct dataset
4. ✅ User is warned if they selected tables from multiple datasets
5. ✅ Migration runs successfully with correct tables

## Notes

- The UI still stores selected tables with the `dataset.table` format for display purposes
- The conversion happens only when creating the migration (sending to backend)
- If user selects tables from multiple datasets, only tables from the selected dataset are included
- A warning is logged to console if tables from other datasets are skipped
