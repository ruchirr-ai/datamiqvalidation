# Troubleshooting: Dropdowns Not Showing Connections

## Current Status

Added extensive debugging logs to identify why sample connections aren't appearing in the Create Migration wizard dropdowns.

## What Was Added

### 1. ConnectionStagingStep Debugging
- Log when component mounts
- Log when connections are fetched
- Log connection state on every render
- Log source/target connection counts

### 2. Select Component Debugging
- Log every time Select renders
- Log options count and values
- Log selected option

## How to Debug

### Step 1: Open Browser Console

1. Navigate to: `http://localhost:3000/migrations/create`
2. Open DevTools Console (F12 or Cmd+Option+I)
3. Look for these logs:

```
ConnectionStagingStep mounted, fetching connections...
```

### Step 2: Check What You See

#### Scenario A: API Call Succeeds
```
Loaded connections from API: [...]
ConnectionStagingStep render: {
  connectionsCount: 6,
  sourceCount: 3,
  targetCount: 3,
  loading: false,
  connections: [...]
}
```

#### Scenario B: API Call Fails (Expected)
```
Failed to fetch connections, using sample data: [error]
No connections from API, using sample data
ConnectionStagingStep render: {
  connectionsCount: 6,
  sourceCount: 3,
  targetCount: 3,
  loading: false,
  connections: [...]
}
```

#### Scenario C: Something Wrong
```
ConnectionStagingStep render: {
  connectionsCount: 0,
  sourceCount: 0,
  targetCount: 0,
  loading: true or false,
  connections: []
}
```

### Step 3: Check Select Component Logs

You should see TWO Select component logs (one for source, one for target):

```
Select component render: {
  optionsCount: 4,
  value: "",
  selectedOption: "Select source connection",
  options: [
    { value: "", label: "Select source connection" },
    { value: 1, label: "Production BigQuery (bigquery)" },
    { value: 3, label: "Analytics MongoDB (mongodb)" },
    { value: 5, label: "Dev BigQuery (bigquery)" }
  ]
}

Select component render: {
  optionsCount: 4,
  value: "",
  selectedOption: "Select target connection",
  options: [
    { value: "", label: "Select target connection" },
    { value: 2, label: "Production Redshift (redshift)" },
    { value: 4, label: "Staging PostgreSQL (postgresql)" },
    { value: 6, label: "Staging Redshift (redshift)" }
  ]
}
```

## Possible Issues & Solutions

### Issue 1: No Logs Appear
**Cause**: Page not loading or JavaScript error
**Solution**:
1. Check Console for errors (red text)
2. Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
3. Check if frontend dev server is running

### Issue 2: `connectionsCount: 0`
**Cause**: `getSampleConnections()` not being called or returning empty
**Solution**:
1. Check if there's a JavaScript error preventing execution
2. Verify the function exists in the component
3. Try hard refresh

### Issue 3: `loading: true` (stuck)
**Cause**: `fetchConnections()` not completing
**Solution**:
1. Check if there's an error in the try/catch block
2. Verify `finally` block executes
3. Check Network tab for hanging requests

### Issue 4: Select Shows "Select..." But No Options When Clicked
**Cause**: Options array is empty or not passed correctly
**Solution**:
1. Check Select component logs
2. Verify `optionsCount` is > 1
3. Click the dropdown and see if options appear

### Issue 5: Options Exist But Not Visible
**Cause**: CSS styling issue
**Solution**:
1. Inspect the dropdown element
2. Check if `.custom-select-dropdown` has `display: none`
3. Check z-index issues

## Quick Fixes

### Fix 1: Force Sample Data Immediately

Edit `ConnectionStagingStep.tsx`:

```typescript
// Change this line:
const [connections, setConnections] = useState<Connection[]>([]);

// To this:
const [connections, setConnections] = useState<Connection[]>(() => {
  return [
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
});
```

### Fix 2: Skip API Call Entirely

Comment out the API call:

```typescript
const fetchConnections = async () => {
  setLoading(true);
  // Skip API, go straight to sample data
  console.log('Using sample data directly');
  setConnections(getSampleConnections());
  setLoading(false);
};
```

### Fix 3: Check Import

Verify the import at the top of `ConnectionStagingStep.tsx`:

```typescript
import { listConnections, Connection } from '../../../services/api';
```

## What to Report

Please share these from your Console:

1. **ConnectionStagingStep logs**:
   - "ConnectionStagingStep mounted..." message
   - "ConnectionStagingStep render" object
   
2. **Select component logs**:
   - Both Select render logs (source and target)
   
3. **Any errors** (red text in Console)

4. **Network tab**:
   - Status of `/api/connections/` request (if any)

5. **Visual behavior**:
   - Do you see "Loading connections..." text?
   - Do dropdowns show "Select source connection" / "Select target connection"?
   - When you click dropdown, does anything appear?

## Expected Working State

When everything works:
1. Page loads
2. Console shows: "ConnectionStagingStep mounted, fetching connections..."
3. Console shows: "Failed to fetch connections, using sample data" (expected if backend is down)
4. Console shows: "ConnectionStagingStep render: { connectionsCount: 6, ... }"
5. Console shows: Two "Select component render" logs with 4 options each
6. Dropdowns show "Select source connection" and "Select target connection"
7. Clicking dropdown shows 3 connection options
8. Selecting "Production BigQuery" + "Production Redshift" reveals staging config section

## Next Steps

After checking the console logs, we can:
1. Identify the exact point of failure
2. Apply the appropriate fix
3. Verify connections appear in dropdowns
4. Test the complete wizard flow
