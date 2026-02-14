# Dropdown Debug Guide

## Issue
Sample connections are not appearing in the Create Migration wizard dropdowns.

## Debugging Steps

### 1. Open Browser Console
1. Navigate to: `http://localhost:3000/migrations/create`
2. Open browser DevTools (F12 or Cmd+Option+I on Mac)
3. Go to the Console tab

### 2. Check Console Logs

You should see these logs when the page loads:

```
ConnectionStagingStep mounted, fetching connections...
```

Then one of these:
```
Loaded connections from API: [...]
```
OR
```
Failed to fetch connections, using sample data: [error]
No connections from API, using sample data
```

Then you should see:
```
ConnectionStagingStep render: {
  connectionsCount: 6,
  sourceCount: 3,
  targetCount: 3,
  loading: false,
  connections: [...]
}
```

### 3. Expected Values

**If working correctly:**
- `connectionsCount: 6`
- `sourceCount: 3` (Production BigQuery, Analytics MongoDB, Dev BigQuery)
- `targetCount: 3` (Production Redshift, Staging PostgreSQL, Staging Redshift)
- `loading: false`

### 4. Check Dropdown Elements

In the Console, run:
```javascript
// Check if dropdowns exist
document.querySelectorAll('select').length

// Check source dropdown options
const sourceSelect = document.querySelectorAll('select')[0];
console.log('Source options:', sourceSelect?.options.length);
Array.from(sourceSelect?.options || []).forEach(opt => console.log(opt.value, opt.text));

// Check target dropdown options
const targetSelect = document.querySelectorAll('select')[1];
console.log('Target options:', targetSelect?.options.length);
Array.from(targetSelect?.options || []).forEach(opt => console.log(opt.value, opt.text));
```

### 5. Common Issues & Solutions

#### Issue: `connectionsCount: 0`
**Cause**: Sample data not loading
**Solution**: 
1. Hard refresh browser (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows)
2. Clear browser cache
3. Check if `getSampleConnections()` function exists in the component

#### Issue: `loading: true` (stuck)
**Cause**: API call hanging
**Solution**:
1. Check if backend is running on port 8000
2. Check Network tab for failed requests
3. The component should fallback to sample data even if API fails

#### Issue: Dropdowns show "Loading connections..."
**Cause**: `loading` state not updating to `false`
**Solution**:
1. Check console for errors in `fetchConnections()`
2. Verify `finally` block is executing

#### Issue: Options show but dropdown appears empty
**Cause**: CSS styling issue
**Solution**:
1. Inspect the `<select>` element
2. Check if options have proper `value` and text
3. Check CSS for `display: none` or `visibility: hidden`

### 6. Manual Test in Console

If dropdowns still don't work, test the sample data directly:

```javascript
// Test sample data structure
const sampleConnections = [
  {
    id: 1,
    name: 'Production BigQuery',
    type: 'source',
    database: 'bigquery',
    connection_params: {},
    connection_string: '',
    created_by: 'John Doe',
    status: 'connected',
    last_tested_at: '2026-02-08 14:30:00',
    created_at: '2026-01-15 10:00:00',
    updated_at: '2026-02-08 14:30:00',
    is_active: true,
    workspace_id: 1
  },
  {
    id: 2,
    name: 'Production Redshift',
    type: 'target',
    database: 'redshift',
    connection_params: {},
    connection_string: '',
    created_by: 'Jane Smith',
    status: 'connected',
    last_tested_at: '2026-02-08 15:00:00',
    created_at: '2026-01-15 11:00:00',
    updated_at: '2026-02-08 15:00:00',
    is_active: true,
    workspace_id: 1
  }
];

const sourceConnections = sampleConnections.filter(c => c.type === 'source');
const targetConnections = sampleConnections.filter(c => c.type === 'target');

console.log('Source:', sourceConnections);
console.log('Target:', targetConnections);
```

### 7. Check Select Component

The Select component might have an issue. Check:

```javascript
// In Console, check if Select component is rendering options
const selects = document.querySelectorAll('select');
console.log('Number of select elements:', selects.length);

selects.forEach((select, index) => {
  console.log(`Select ${index}:`, {
    optionsCount: select.options.length,
    options: Array.from(select.options).map(opt => ({
      value: opt.value,
      text: opt.text
    }))
  });
});
```

### 8. Network Tab Check

1. Open Network tab in DevTools
2. Filter by "Fetch/XHR"
3. Look for request to `/api/connections/`
4. Check if it's:
   - ✅ Succeeding (200) with empty array `[]`
   - ❌ Failing (404, 500, etc.)
   - ⏳ Pending (hanging)

### 9. React DevTools

If you have React DevTools installed:
1. Open React DevTools
2. Find `ConnectionStagingStep` component
3. Check its state:
   - `connections` should be array of 6 items
   - `loading` should be `false`
   - `showStagingConfig` should be `false` initially

### 10. Quick Fix - Force Sample Data

If nothing works, temporarily force sample data by modifying the component:

```typescript
// At the top of ConnectionStagingStep component, replace:
const [connections, setConnections] = useState<Connection[]>([]);

// With:
const [connections, setConnections] = useState<Connection[]>(getSampleConnections());
```

This will immediately load sample data without waiting for API.

## Expected Behavior

When working correctly:
1. Page loads
2. "Loading connections..." appears briefly
3. Dropdowns populate with:
   - **Source Connection**: 4 options (placeholder + 3 sources)
   - **Target Connection**: 4 options (placeholder + 3 targets)
4. Selecting "Production BigQuery" + "Production Redshift" shows staging config

## Report Back

Please share:
1. Console logs (especially the "ConnectionStagingStep render" log)
2. Number of options in each dropdown
3. Any errors in Console
4. Network tab status for `/api/connections/` request

This will help identify the exact issue!
