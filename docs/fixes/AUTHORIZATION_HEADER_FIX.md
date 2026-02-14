# Authorization Header Fix - BigQuery Metadata Discovery

## Issue Identified

The Authorization header was not being sent with the `discover-metadata` API request, causing 401 Unauthorized errors and preventing real BigQuery data from loading.

## Root Causes

### 1. Token Storage Key Mismatch
**Critical Issue**: The application stores the authentication token as `auth_token` in localStorage (via AuthContext), but the API service was looking for `access_token`.

**Location**: 
- `frontend/src/contexts/AuthContext.tsx` stores token as: `localStorage.setItem('auth_token', data.access_token)`
- `frontend/src/services/bqRedshiftApi.ts` was reading: `localStorage.getItem('access_token')`

**Result**: Token was never found, so Authorization header was never added to requests.

### 2. Redundant Query Parameters
The `discoverMetadata` function was adding query parameters to the URL while also sending the same data in the request body, which is redundant and can cause issues.

### 3. Insufficient Error Handling
The error handling wasn't providing enough detail about authentication failures or token issues.

## Fixes Applied

### Fix 1: Token Key Compatibility in `getAuthHeaders()`

**File**: `frontend/src/services/bqRedshiftApi.ts`

**Before:**
```typescript
const getAuthHeaders = () => {
  const token = localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` })
  };
};
```

**After:**
```typescript
const getAuthHeaders = () => {
  // Try both possible token keys for compatibility
  const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` })
  };
};
```

### Fix 2: Updated `discoverMetadata()` Function

**File**: `frontend/src/services/bqRedshiftApi.ts`

**Changes:**
1. Removed query parameters from URL
2. Added explicit token validation with both key names
3. Enhanced logging to track token presence and request details
4. Improved error messages

**Before:**
```typescript
const params = new URLSearchParams();
params.append('connection_id', connectionId.toString());
if (projectId) params.append('project_id', projectId);
if (dataset) params.append('dataset', dataset);

const response = await fetch(`${API_BASE}/discover-metadata?${params.toString()}`, {
  method: 'POST',
  headers: getAuthHeaders(),
  body: JSON.stringify({
    connection_id: connectionId,
    project_id: projectId
  })
});
```

**After:**
```typescript
// Try both possible token keys for compatibility
const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
console.log('Auth token:', token ? 'Present' : 'Missing');
console.log('Token keys checked:', {
  auth_token: !!localStorage.getItem('auth_token'),
  access_token: !!localStorage.getItem('access_token')
});

if (!token) {
  console.error('No access token found in localStorage');
  throw new Error('Authentication required. Please log in.');
}

const requestBody = {
  connection_id: connectionId,
  project_id: projectId || undefined,
  dataset: dataset || undefined
};

console.log('Request body:', requestBody);
console.log('Request headers:', getAuthHeaders());

const response = await fetch(`${API_BASE}/discover-metadata`, {
  method: 'POST',
  headers: getAuthHeaders(),
  body: JSON.stringify(requestBody)
});
```

## Testing Steps

1. **Open Browser DevTools** (F12)
2. **Check localStorage**:
   ```javascript
   // In Console tab
   console.log('auth_token:', localStorage.getItem('auth_token'));
   console.log('access_token:', localStorage.getItem('access_token'));
   ```
3. **Go to Network Tab**
4. **Navigate to Migrations page**
5. **Click "Create Migration"**
6. **Select BigQuery connection**
7. **Check the Network tab for the `discover-metadata` request**
8. **Verify the following:**
   - Request Method: POST
   - Request URL: `/api/migrations/bq-redshift/discover-metadata` (no query params)
   - Request Headers include: `Authorization: Bearer <token>`
   - Request Body contains: `{"connection_id": X, "project_id": "..."}`
   - Response Status: 200 OK (not 401)

## Expected Behavior

### Success Case
- Token found in localStorage (as `auth_token`)
- Request includes Authorization header
- Backend validates token successfully
- BigQuery client connects to project
- Real datasets and tables are returned
- UI displays actual BigQuery data (not sample data)

### Failure Cases

**No Token:**
- Console log: "No access token found in localStorage"
- Error: "Authentication required. Please log in."
- User should log out and log back in

**Invalid Token:**
- Response: 401 Unauthorized
- Error: "Authentication failed. Please log out and log back in."
- Token may be expired or invalid

**BigQuery Connection Error:**
- Response: 500 Internal Server Error
- Error: "Failed to discover BigQuery metadata: <details>"
- Check BigQuery credentials in connection

## Backend Validation

The backend endpoint (`/api/migrations/bq-redshift/discover-metadata`) expects:

**Request:**
```json
POST /api/migrations/bq-redshift/discover-metadata
Headers:
  Authorization: Bearer <token>
  Content-Type: application/json
Body:
  {
    "connection_id": 6,
    "project_id": "assessiq-484512"
  }
```

**Response (Success):**
```json
{
  "connection_id": 6,
  "project_id": "assessiq-484512",
  "datasets": [
    {
      "dataset_id": "sales_analytics",
      "location": "us-central1",
      "created": "2025-01-15T10:00:00Z",
      "modified": "2026-02-08T14:30:00Z",
      "table_count": 6
    }
  ],
  "tables": {
    "sales_analytics": [
      {
        "table_id": "assess_tbl",
        "dataset_id": "sales_analytics",
        "table_type": "TABLE",
        "num_rows": 10000000,
        "size_bytes": 10500000000,
        "created": "2025-01-15T10:30:00Z",
        "modified": "2026-02-08T14:30:00Z"
      }
    ]
  }
}
```

## Console Logging

The fix includes comprehensive console logging to help debug issues:

```
Calling discover-metadata API: {connectionId: 6, projectId: "assessiq-484512"}
Auth token: Present
Token keys checked: {auth_token: true, access_token: false}
Request body: {connection_id: 6, project_id: "assessiq-484512"}
Request headers: {Content-Type: "application/json", Authorization: "Bearer eyJ0..."}
API Response status: 200 OK
API Response data: {connection_id: 6, project_id: "assessiq-484512", datasets: [...], tables: {...}}
```

## Files Modified

1. `frontend/src/services/bqRedshiftApi.ts`:
   - Updated `getAuthHeaders()` to check both `auth_token` and `access_token`
   - Updated `discoverMetadata()` to validate token and remove query params
   - Added comprehensive logging

## Related Files (No Changes Needed)

- `frontend/src/contexts/AuthContext.tsx` - Stores token as `auth_token` (correct)
- `backend/routers/bq_redshift_migration.py` - Backend endpoint (working correctly)
- `backend/shared/middleware/auth_middleware.py` - Authentication middleware (working correctly)
- `frontend/src/components/migrations/steps/MetadataDiscoveryStep.tsx` - UI component (working correctly)

## Next Steps

1. **Test in Browser**: Open the application and try creating a migration
2. **Check Console**: Verify token is found and request is made correctly
3. **Check Network Tab**: Verify Authorization header is present
4. **Verify Data**: Confirm real BigQuery data is displayed (not sample data)

## Success Criteria

✅ Authorization header is present in all API requests  
✅ Token is found in localStorage (as `auth_token`)  
✅ Backend receives and validates token successfully  
✅ Real BigQuery metadata is fetched and displayed  
✅ No 401 Unauthorized errors  
✅ Sample data is NOT shown (unless there's a BigQuery connection error)
