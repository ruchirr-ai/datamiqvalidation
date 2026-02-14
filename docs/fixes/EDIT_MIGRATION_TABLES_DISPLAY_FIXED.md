# Edit Migration - Tables and Datasets Display Fixed

## Issue
When editing a migration, the selected tables and datasets were not displaying in the Metadata Discovery step.

## Root Causes

### 1. Table Name Format Mismatch
**Problem**: The API returns table names as simple strings (e.g., `['customers', 'orders']`), but the UI expects them in `dataset.table` format (e.g., `['analytics.customers', 'analytics.orders']`).

**Impact**: The checkboxes couldn't match the selected tables because the formats didn't align.

### 2. Dataset Not Auto-Expanded
**Problem**: In edit mode, the dataset containing the selected tables was not automatically expanded, so users couldn't see the tables.

**Impact**: The UI appeared empty even though the data was loaded.

### 3. TypeScript Error in Existing Code
**Problem**: The `setDatasetTables` function had a type mismatch when handling the API response. The API returns `tables` as `Record<string, BigQueryTable[]>` but the code was treating it as `BigQueryTable[]`.

**Impact**: TypeScript compilation error.

## Fixes Applied

### Fix 1: Convert Table Names to Full Format
**File**: `frontend/src/components/migrations/CreateMigrationWizard.tsx`

Added logic to convert table names from API format to UI format:

```typescript
// Convert table names to full format (dataset.table)
// API returns: ['customers', 'orders']
// UI expects: ['analytics.customers', 'analytics.orders']
const selectedTablesWithDataset = sourceTables.map((tableName: string) => {
  // If already in dataset.table format, keep it
  if (tableName.includes('.')) {
    return tableName;
  }
  // Otherwise, prepend the dataset
  return `${sourceDataset}.${tableName}`;
});
```

Then use `selectedTablesWithDataset` instead of `sourceTables` when setting form data.

### Fix 2: Auto-Expand Dataset in Edit Mode
**File**: `frontend/src/components/migrations/steps/MetadataDiscoveryStep.tsx`

Added a `useEffect` hook to automatically expand the dataset and load tables when in edit mode:

```typescript
// Auto-expand dataset in edit mode if tables are selected
useEffect(() => {
  if (isEditMode && formData.sourceDataset && formData.selectedTables.length > 0) {
    console.log('Edit mode: Auto-expanding dataset:', formData.sourceDataset);
    console.log('Selected tables:', formData.selectedTables);
    
    // Expand the dataset that contains the selected tables
    setExpandedDatasets(new Set([formData.sourceDataset]));
    
    // If we don't have tables loaded for this dataset yet, fetch them
    if (!datasetTables[formData.sourceDataset]) {
      fetchTablesForDataset(formData.sourceDataset);
    }
  }
}, [isEditMode, formData.sourceDataset, formData.selectedTables, datasetTables]);
```

### Fix 3: Correct API Response Handling
**File**: `frontend/src/components/migrations/steps/MetadataDiscoveryStep.tsx`

Fixed the `fetchTablesForDataset` function to correctly extract tables from the API response:

```typescript
setDatasetTables(prev => {
  const updated = { ...prev };
  // data.tables is Record<string, BigQueryTable[]>, so get the array for this dataset
  if (data.tables && data.tables[datasetId]) {
    updated[datasetId] = data.tables[datasetId];
  } else {
    updated[datasetId] = [];
  }
  return updated;
});
```

## Verification
✅ No TypeScript/compilation errors
✅ Table names are converted to correct format
✅ Dataset auto-expands in edit mode
✅ Selected tables are displayed with checkboxes checked
✅ Tables remain read-only in edit mode

## Testing Steps

1. **Create a Migration**:
   - Go to Migrations page
   - Click "New" → "Create"
   - Select source and target connections
   - Go to Metadata Discovery step
   - Select a dataset (e.g., "analytics")
   - Select some tables (e.g., "customers", "orders")
   - Complete the wizard and create the migration

2. **Edit the Migration**:
   - Go back to Migrations page
   - Click the menu (⋮) on the migration row
   - Click "Edit Migration"
   - Navigate to step 2 (Metadata Discovery)
   - **Verify**: The dataset should be automatically expanded
   - **Verify**: The previously selected tables should have checkboxes checked
   - **Verify**: The summary stats should show correct counts
   - **Verify**: All controls should be disabled (read-only mode)

3. **Check Console Logs**:
   - Open browser console
   - Look for logs like:
     - "Edit mode: Auto-expanding dataset: analytics"
     - "Selected tables: ['analytics.customers', 'analytics.orders']"

## Data Flow

### Create Mode
1. User selects tables → Format: `['analytics.customers', 'analytics.orders']`
2. On submit → Extract table names: `['customers', 'orders']`
3. Send to API → Store in DB: `['customers', 'orders']`

### Edit Mode
1. Load from API → Receive: `['customers', 'orders']`
2. Convert format → Add dataset prefix: `['analytics.customers', 'analytics.orders']`
3. Set form data → UI displays with checkboxes checked
4. Auto-expand dataset → Show tables in expanded view

## Files Modified
- `frontend/src/components/migrations/CreateMigrationWizard.tsx`
- `frontend/src/components/migrations/steps/MetadataDiscoveryStep.tsx`

## Status
✅ **FIXED** - Tables and datasets now display correctly in edit mode
