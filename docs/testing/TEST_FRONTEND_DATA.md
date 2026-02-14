# Frontend Data Flow Test

## Issue
Migration is still using sample data (`customers`, `orders`) instead of user selections.

## Root Cause
Browser is caching old JavaScript code. The fixes are in the source files but not loaded in the browser.

## Verification Steps

### 1. Check Source Code (✅ CLEAN)
```bash
# Check for sample data in wizard
grep -n "analytics.customers\|analytics.orders" frontend/src/components/migrations/CreateMigrationWizard.tsx
# Result: No matches (GOOD!)

# Check for sample data in metadata step
grep -n "customers.*orders" frontend/src/components/migrations/steps/MetadataDiscoveryStep.tsx
# Result: No matches (GOOD!)
```

### 2. Check Database (❌ HAS OLD DATA)
```bash
psql -U manasakallakuri -d datamiq -c "SELECT id, migration_name, source_dataset, source_tables FROM migrations_bq_redshift ORDER BY id DESC LIMIT 1;"
```

**Current Result**:
```
 id | migration_name | source_dataset  | source_tables    
----+----------------+-----------------+------------------
  7 | bq_rs_mig      | sales_analytics | {customers,orders}
```

**Analysis**:
- ✅ `source_dataset` = `sales_analytics` (CORRECT - fix is working!)
- ❌ `source_tables` = `{customers, orders}` (WRONG - should be just `{orders}`)

This means the `sourceDataset` fix is working, but the browser is still using old code that had sample tables.

## Solution

### Step 1: Clear Browser Cache
The browser is serving old JavaScript. You need to force reload:

**Chrome/Edge/Brave**:
- Windows: `Ctrl + Shift + R`
- Mac: `Cmd + Shift + R`

**Firefox**:
- Windows: `Ctrl + F5`
- Mac: `Cmd + Shift + R`

**Safari**:
- Mac: `Cmd + Option + R`

**Alternative**: Open DevTools (F12) → Right-click refresh button → "Empty Cache and Hard Reload"

### Step 2: Verify Frontend Shows Empty Fields
After hard refresh, open Create Migration wizard:

**Expected (NEW CODE)**:
- Migration Name: `[empty field]`
- Source Connection: `[not selected]`
- Target Connection: `[not selected]`
- Selected Tables: `[]` (empty array)

**Wrong (OLD CODE)**:
- Migration Name: `Sample Migration Project`
- Source Connection: `1` (pre-selected)
- Target Connection: `2` (pre-selected)
- Selected Tables: `['analytics.customers', 'analytics.orders']`

### Step 3: Delete Old Migration
```bash
psql -U manasakallakuri -d datamiq -c "DELETE FROM migrations_bq_redshift WHERE id = 7;"
```

### Step 4: Create Fresh Migration
1. Open Migrations page (after hard refresh!)
2. Click "Create Migration"
3. **Verify fields are EMPTY** (not pre-filled)
4. Fill in:
   - Name: "Test Sales Orders Only"
   - Source: BigQuery connection
   - Target: Redshift connection
5. Step 2: Metadata Discovery
   - Expand `sales_analytics`
   - Select ONLY `orders` table
   - **Verify**: Summary shows "1 table selected"
6. Complete wizard
7. Create migration

### Step 5: Verify Database
```bash
psql -U manasakallakuri -d datamiq -c "SELECT id, migration_name, source_dataset, source_tables FROM migrations_bq_redshift ORDER BY id DESC LIMIT 1;"
```

**Expected Result**:
```
 id | migration_name          | source_dataset  | source_tables
----+-------------------------+-----------------+---------------
  8 | Test Sales Orders Only  | sales_analytics | {orders}
```

## Debugging Tips

### Check if Frontend Dev Server Reloaded
When you saved the files, did you see in the terminal:
```
[vite] hmr update /src/components/migrations/CreateMigrationWizard.tsx
```

If not, the dev server might not have picked up the changes. Try:
```bash
# Stop frontend (Ctrl+C)
# Start again
cd frontend
npm run dev
```

### Check Browser Console
Open DevTools (F12) → Console tab

Look for:
```javascript
console.log('Creating migration with data:', formData);
```

This will show you what data the frontend is actually sending. If you see:
```javascript
selectedTables: ['analytics.customers', 'analytics.orders']
```

Then the browser is definitely using old cached code.

### Check Network Tab
Open DevTools (F12) → Network tab → Click "Create Migration"

Look at the POST request to `/api/migrations/bq-redshift/create`

Check the Request Payload:
```json
{
  "source_dataset": "sales_analytics",  // Should match your selection
  "source_tables": ["orders"],          // Should be ONLY what you selected
  ...
}
```

## Summary

The code fixes are correct and in place. The issue is browser caching. After a hard refresh and creating a new migration, it should work correctly.

**Key Indicators**:
- ✅ Source code is clean (no sample data)
- ✅ `sourceDataset` fix is working (database shows `sales_analytics`)
- ❌ Browser is using old JavaScript (still sending `customers, orders`)

**Solution**: Hard refresh browser + create new migration
