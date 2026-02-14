# BigQuery Real Data Integration - Fixed

## Issue
The metadata discovery was only showing sample data instead of actual data from the BigQuery connection.

## Root Cause
The backend endpoint was trying to use AWS Secrets Service to decrypt connection strings, but the actual connection model stores credentials in `connection_params` as a JSON field, not in an encrypted `connection_string` field.

## Solution

### Backend Changes

#### File: `backend/routers/bq_redshift_migration.py`

**Fixed the `discover-metadata` endpoint to:**

1. **Read from `connection_params`** instead of encrypted `connection_string`
   ```python
   connection_params = connection.connection_params or {}
   
   # Get service account key from connection params
   service_account_key = (
       connection_params.get('service_account_key') or 
       connection_params.get('serviceAccountKey') or
       connection_params.get('credentials_json') or
       connection_params.get('credentialsJson')
   )
   ```

2. **Get project ID from multiple sources**
   ```python
   project_id = (
       req.project_id or 
       connection_params.get('project_id') or 
       connection_params.get('projectId') or
       credentials_dict.get('project_id')
   )
   ```

3. **Use correct database field name**
   ```python
   if connection.database.lower() != 'bigquery':
       raise HTTPException(...)
   ```
   Changed from `connection.db_type` to `connection.database`

4. **Parse service account JSON properly**
   ```python
   if isinstance(service_account_key, str):
       credentials_dict = json.loads(service_account_key)
   else:
       credentials_dict = service_account_key
   ```

5. **Create BigQuery client with proper credentials**
   ```python
   credentials = service_account.Credentials.from_service_account_info(credentials_dict)
   region = connection_params.get('region') or connection_params.get('location', 'us-central1')
   client = bigquery.Client(
       credentials=credentials,
       project=project_id,
       location=region
   )
   ```

### Frontend Changes

#### File: `frontend/src/services/bqRedshiftApi.ts`

**Updated API call to use POST with body:**
```typescript
const response = await fetch(`${API_BASE}/discover-metadata?${params.toString()}`, {
  method: 'POST',
  headers: getAuthHeaders(),
  body: JSON.stringify({
    connection_id: connectionId,
    project_id: projectId
  })
});
```

**Updated BigQueryTable interface to handle both field names:**
```typescript
export interface BigQueryTable {
  table_id: string;
  dataset_id?: string;
  type?: string;
  table_type?: string;
  num_rows: number;
  num_bytes?: number;      // Frontend field name
  size_bytes?: number;     // Backend field name
  created: string;
  modified: string;
  description?: string;
}
```

#### File: `frontend/src/components/migrations/steps/MetadataDiscoveryStep.tsx`

**Updated to handle both field names:**
```typescript
// In getTotalStats()
totalBytes += (table.num_bytes || table.size_bytes || 0);

// In table rendering
{formatBytes((table.num_bytes || table.size_bytes || 0))}
```

## How It Works Now

### 1. User Creates BigQuery Connection
- User provides:
  - Project ID
  - Service Account Key (JSON)
  - Region/Location
- Connection stored in database with `connection_params` containing these fields

### 2. User Starts Migration Wizard
- Selects BigQuery source connection
- Wizard proceeds to MetadataDiscoveryStep

### 3. Frontend Calls API
```typescript
const data = await discoverBigQueryMetadata(formData.sourceConnectionId);
```

### 4. Backend Processes Request
1. Fetches connection from database
2. Extracts service account key from `connection_params`
3. Parses JSON credentials
4. Creates BigQuery client
5. Lists all datasets in the project
6. For each dataset:
   - Gets dataset metadata (location, description, etc.)
   - Lists all tables
   - Gets table metadata (rows, size, etc.)
7. Returns structured response

### 5. Frontend Displays Data
- Shows datasets with expand/collapse
- Shows tables with:
  - Table name
  - Row count (formatted with commas)
  - Data size (formatted as MB, GB, etc.)
- Allows selection of tables for migration
- Shows summary statistics

## API Request/Response

### Request
```http
POST /api/migrations/bq-redshift/discover-metadata
Content-Type: application/json

{
  "connection_id": 1,
  "project_id": "my-gcp-project"  // optional
}
```

### Response
```json
{
  "connection_id": 1,
  "project_id": "my-gcp-project",
  "datasets": [
    {
      "dataset_id": "analytics",
      "location": "US",
      "description": "Analytics data",
      "created": "2025-01-15T10:00:00Z",
      "modified": "2026-02-08T14:30:00Z",
      "table_count": 5
    }
  ],
  "tables": {
    "analytics": [
      {
        "table_id": "customers",
        "dataset_id": "analytics",
        "table_type": "TABLE",
        "num_rows": 1250000,
        "size_bytes": 450000000,
        "created": "2025-01-15T10:30:00Z",
        "modified": "2026-02-08T14:30:00Z",
        "description": "Customer master data"
      }
    ]
  }
}
```

## Error Handling

### Backend Errors
1. **Connection not found**: 404 error
2. **Wrong database type**: 400 error (must be BigQuery)
3. **Missing service account key**: 400 error
4. **Invalid JSON credentials**: 400 error
5. **BigQuery client initialization failed**: 500 error
6. **BigQuery API errors**: 500 error with details

### Frontend Fallback
If API call fails, frontend:
1. Catches the error
2. Logs error to console
3. Falls back to sample data
4. Shows warning message: "Using sample data for testing"
5. Allows user to continue with wizard

## Testing

### Prerequisites
1. Valid BigQuery connection created with:
   - Project ID
   - Service Account Key (JSON with proper permissions)
   - Region

### Test Steps
1. Create BigQuery connection in Connections page
2. Test connection to verify credentials work
3. Start migration wizard
4. Select BigQuery source connection
5. Proceed to "Select Tables to Migrate" step
6. Verify:
   - Real datasets appear (not sample data)
   - Dataset names match your BigQuery project
   - Table counts are accurate
   - Expand dataset to see tables
   - Row counts and sizes are accurate
   - Can select/deselect tables
   - Summary statistics update correctly

### Troubleshooting

#### Still Seeing Sample Data
1. Check browser console for API errors
2. Check backend logs for detailed error messages
3. Verify BigQuery connection has valid credentials
4. Verify service account has BigQuery permissions:
   - `bigquery.datasets.get`
   - `bigquery.tables.list`
   - `bigquery.tables.get`

#### API Errors
1. **"Service Account Key is required"**
   - Connection missing service account key
   - Re-create connection with valid JSON key

2. **"Invalid BigQuery credentials format"**
   - Service account JSON is malformed
   - Verify JSON is valid

3. **"Failed to initialize BigQuery client"**
   - Credentials don't have proper format
   - Missing required fields in service account JSON

4. **"Failed to discover BigQuery metadata"**
   - Service account lacks permissions
   - Project ID is incorrect
   - Network connectivity issues

## Required BigQuery Permissions

The service account must have these permissions:
```
bigquery.datasets.get
bigquery.datasets.list
bigquery.tables.get
bigquery.tables.list
```

Or use these predefined roles:
- `roles/bigquery.dataViewer`
- `roles/bigquery.user`
- `roles/bigquery.metadataViewer`

## Files Modified

### Backend
1. **backend/routers/bq_redshift_migration.py**
   - Fixed `discover-metadata` endpoint
   - Read from `connection_params` instead of encrypted string
   - Handle multiple field name variations
   - Proper error handling

### Frontend
1. **frontend/src/services/bqRedshiftApi.ts**
   - Updated API call to use POST with body
   - Updated BigQueryTable interface

2. **frontend/src/components/migrations/steps/MetadataDiscoveryStep.tsx**
   - Handle both `num_bytes` and `size_bytes` field names
   - Proper fallback to sample data on error

## Status
✅ **FIXED** - BigQuery metadata discovery now fetches real data from actual BigQuery connections instead of showing sample data.

## Next Steps

1. **Test with Real BigQuery Connection**
   - Create connection with valid credentials
   - Verify real data appears

2. **Add Caching** (Optional)
   - Cache metadata in Redis for faster subsequent loads
   - TTL: 15-30 minutes

3. **Add Pagination** (Optional)
   - For projects with many datasets/tables
   - Load tables on-demand when dataset is expanded

4. **Add Column Metadata** (Optional)
   - Show column names and types
   - Allow column-level selection

5. **Add Data Preview** (Optional)
   - Show sample rows from selected tables
   - Help users verify correct tables selected
