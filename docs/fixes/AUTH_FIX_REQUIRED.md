# Authentication Issue - 401 Unauthorized

## Problem Identified

The BigQuery metadata discovery API is returning **401 Unauthorized**, which is why you're seeing sample data instead of real data.

**Backend Logs Show**:
```
INFO: 127.0.0.1:49605 - "POST /api/migrations/bq-redshift/discover-metadata?connection_id=6 HTTP/1.1" 401 Unauthorized
INFO: 127.0.0.1:49607 - "POST /api/migrations/bq-redshift/discover-metadata?connection_id=6 HTTP/1.1" 401 Unauthorized
```

## Root Cause

The authentication token in `localStorage` is either:
1. Missing
2. Expired
3. Invalid
4. Not being sent correctly in the request headers

## Immediate Solution

### Option 1: Log Out and Log Back In (Recommended)

1. Click your user profile in the top right
2. Click **Log Out**
3. Log back in with your credentials
4. Try the migration wizard again

This will refresh your authentication token.

### Option 2: Clear Browser Storage

1. Open browser DevTools (F12)
2. Go to **Application** tab (Chrome) or **Storage** tab (Firefox)
3. Find **Local Storage** → `http://localhost:3000`
4. Delete the `access_token` entry
5. Refresh the page
6. Log in again

### Option 3: Check Token in Console

1. Open browser console (F12)
2. Type: `localStorage.getItem('access_token')`
3. If it returns `null`, you need to log in
4. If it returns a token, it might be expired

## Verification Steps

After logging back in:

1. Open browser console (F12)
2. Navigate to Migrations → Create Migration
3. Select BigQuery → Redshift → Next
4. Select a BigQuery connection → Next
5. Check console for these messages:
   ```
   Calling discover-metadata API: {connectionId: 6, ...}
   Auth token: Present
   API Response status: 200 OK
   API Response data: {project_id: "assessiq-484512", datasets: [...], tables: {...}}
   ```

## Expected Behavior After Fix

Once authenticated properly, you should see:

✅ **Real Data**:
- Dataset: `sales_analytics` (asia-south1)
- Tables: `assess_tbl` (10M rows, 10.5 GB)
- No warning message

❌ **Sample Data** (means still failing):
- Datasets: `analytics`, `sales`, `marketing`
- Warning: "Authentication failed. Please log out and log back in, then try again."

## Technical Details

### What Changed

Added better error handling and logging:

**Frontend** (`frontend/src/services/bqRedshiftApi.ts`):
- Added console logging for API calls
- Added token presence check
- Added specific 401 error handling
- Added response status logging

**Frontend** (`frontend/src/components/migrations/steps/MetadataDiscoveryStep.tsx`):
- Added detailed error logging
- Added specific authentication error message
- Added error response inspection

### How Authentication Works

1. User logs in → Backend returns JWT token
2. Frontend stores token in `localStorage.access_token`
3. API calls include token in `Authorization: Bearer <token>` header
4. Backend validates token on each request
5. If token is invalid/expired → 401 Unauthorized

### Token Expiration

JWT tokens typically expire after:
- 1 hour (default)
- 24 hours (extended)
- Custom duration (configured in backend)

If you've been logged in for a while, the token may have expired.

## Debug Information

### Check Token in Browser

```javascript
// Open console (F12) and run:
const token = localStorage.getItem('access_token');
console.log('Token:', token ? 'Present' : 'Missing');

// Decode token (if present)
if (token) {
  const payload = JSON.parse(atob(token.split('.')[1]));
  console.log('Token payload:', payload);
  console.log('Expires:', new Date(payload.exp * 1000));
  console.log('Is expired:', Date.now() > payload.exp * 1000);
}
```

### Check Network Request

1. Open DevTools (F12) → Network tab
2. Try the migration wizard again
3. Find `discover-metadata` request
4. Check **Request Headers**:
   - Should have: `Authorization: Bearer <token>`
   - If missing: Token not being sent
5. Check **Response**:
   - Status: Should be 200, not 401
   - Body: Should have datasets and tables

## Next Steps

1. **Log out and log back in** (easiest solution)
2. Try the migration wizard again
3. Check browser console for new error messages
4. If still seeing 401, check backend logs for more details
5. If seeing different error, share the error message

## Additional Notes

- The BigQuery connection itself is working (verified with test script)
- The backend endpoint is working (verified with logging)
- The frontend UI is working (verified with sample data)
- The ONLY issue is authentication

Once you log back in with a fresh token, you should see real BigQuery data immediately.
