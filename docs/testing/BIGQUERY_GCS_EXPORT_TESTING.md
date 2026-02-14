# BigQuery to GCS Export Testing

## Overview

A dedicated testing interface for exporting BigQuery tables to Google Cloud Storage (GCS) with production data. This allows you to test the first step of the migration pipeline independently before implementing the full end-to-end flow.

## Features

✅ **Production Data Export** - Export real BigQuery tables to GCS  
✅ **Multiple Formats** - AVRO, Parquet, CSV, JSON  
✅ **Compression Options** - GZIP, SNAPPY, DEFLATE, or None  
✅ **Real-time Feedback** - See export progress and results  
✅ **Detailed Statistics** - Rows, bytes, files, duration  
✅ **Error Handling** - Clear error messages with troubleshooting  

## Architecture

### Backend Endpoint

**File**: `backend/routers/bq_export_test_router.py`

**Endpoint**: `POST /api/bq-export-test/export`

**Flow**:
1. Validates BigQuery connection
2. Retrieves service account credentials
3. Creates BigQuery client
4. Validates table exists
5. Configures export job (format, compression)
6. Starts BigQuery extract job
7. Waits for completion
8. Returns detailed results

### Frontend Page

**File**: `frontend/src/pages/BQExportTestPage.tsx`

**Route**: `/migrations/bq-export-test`

**UI Sections**:
1. **BigQuery Source** - Connection, project, dataset, table selection
2. **GCS Destination** - Bucket and path configuration
3. **Export Options** - Format and compression selection
4. **Results Display** - Statistics and file locations

## Usage

### Access the Page

Navigate to: `http://localhost:3000/migrations/bq-export-test`

### Step 1: Configure BigQuery Source

1. **Select Connection**: Choose a BigQuery connection from dropdown
2. **Project ID**: Enter GCP project ID (e.g., `assessiq-484512`)
3. **Dataset**: Enter dataset name (e.g., `sales_analytics`)
4. **Table**: Enter table name (e.g., `assess_tbl`)

**Example**:
```
Connection: bq_demo
Project ID: assessiq-484512
Dataset: sales_analytics
Table: assess_tbl
```

**Table Reference**: `assessiq-484512.sales_analytics.assess_tbl`

### Step 2: Configure GCS Destination

1. **GCS Bucket**: Enter bucket name WITHOUT `gs://` prefix
2. **GCS Path**: Enter path within bucket (default: `/exports`)

**Example**:
```
GCS Bucket: my-gcs-staging-bucket
GCS Path: /exports
```

**Destination URI**: `gs://my-gcs-staging-bucket/exports/assess_tbl_*.avro`

### Step 3: Choose Format & Compression

**Export Formats**:

| Format | Description | Best For | Compression Options |
|--------|-------------|----------|---------------------|
| **AVRO** | Binary format, preserves schema | Large datasets, recommended | SNAPPY, DEFLATE, None |
| **Parquet** | Columnar format, excellent compression | Analytics workloads | SNAPPY, GZIP, None |
| **CSV** | Simple text format | Human-readable, compatibility | GZIP, None |
| **JSON** | Newline-delimited JSON | Human-readable, flexible | GZIP, None |

**Compression Options**:

| Compression | Speed | Size | Best For |
|-------------|-------|------|----------|
| **SNAPPY** | Fast | Larger | Quick exports, AVRO/Parquet |
| **GZIP** | Slow | Smaller | Storage optimization |
| **DEFLATE** | Medium | Medium | Balanced approach |
| **None** | Fastest | Largest | Testing, fast networks |

**Recommendation**: Use **AVRO + SNAPPY** for production migrations

### Step 4: Start Export

Click **"Start Export"** button

The system will:
1. Validate all inputs
2. Connect to BigQuery
3. Start export job
4. Monitor progress
5. Display results

## API Request Format

```json
{
  "connection_id": 3,
  "project_id": "assessiq-484512",
  "dataset": "sales_analytics",
  "table": "assess_tbl",
  "gcs_bucket": "my-gcs-staging-bucket",
  "gcs_path": "/exports",
  "export_format": "AVRO",
  "compression": "SNAPPY"
}
```

## API Response Format

### Success Response

```json
{
  "success": true,
  "message": "Successfully exported 10,000,000 rows to GCS",
  "job_id": "bquxjob_1234567890_abcdef",
  "destination_uris": [
    "gs://my-gcs-staging-bucket/exports/assess_tbl_000000000000.avro",
    "gs://my-gcs-staging-bucket/exports/assess_tbl_000000000001.avro"
  ],
  "rows_exported": 10000000,
  "bytes_exported": 10737418240,
  "files_created": 2,
  "duration_seconds": 45.23
}
```

### Error Response

```json
{
  "success": false,
  "message": "Export failed",
  "error": "Table not found: assessiq-484512.sales_analytics.wrong_table",
  "duration_seconds": 2.15
}
```

## Results Display

### Success View

```
✓ Export Successful!

Successfully exported 10,000,000 rows to GCS

┌─────────────────────────────────────────┐
│ Rows Exported:    10,000,000            │
│ Data Size:        10.00 GB              │
│ Files Created:    ~2                    │
│ Duration:         45.23s                │
└─────────────────────────────────────────┘

Job ID: bquxjob_1234567890_abcdef

Destination Files:
- gs://my-gcs-staging-bucket/exports/assess_tbl_000000000000.avro
- gs://my-gcs-staging-bucket/exports/assess_tbl_000000000001.avro

Next Steps:
✓ Verify files in GCS bucket: gs://my-gcs-staging-bucket/exports/
• Test GCS to S3 transfer (coming soon)
• Test S3 to Redshift load (coming soon)
```

### Error View

```
✗ Export Failed

Export failed

Error Details:
Table not found: assessiq-484512.sales_analytics.wrong_table
```

## Testing Scenarios

### Test 1: Small Table Export

**Purpose**: Verify basic functionality

```
Table: Small test table (< 1000 rows)
Format: CSV
Compression: None
Expected: Quick export, single file
```

### Test 2: Large Table Export

**Purpose**: Test production-scale data

```
Table: assess_tbl (10M rows, 10 GB)
Format: AVRO
Compression: SNAPPY
Expected: Multiple files, ~30-60 seconds
```

### Test 3: Different Formats

**Purpose**: Verify all formats work

```
Test AVRO, Parquet, CSV, JSON
Compare file sizes and export times
Verify data integrity
```

### Test 4: Compression Comparison

**Purpose**: Compare compression options

```
Export same table with:
- No compression
- SNAPPY
- GZIP
Compare file sizes and export times
```

## Verification

### Check Files in GCS

```bash
# List files in GCS bucket
gsutil ls gs://my-gcs-staging-bucket/exports/

# Check file sizes
gsutil du -sh gs://my-gcs-staging-bucket/exports/

# Download a file to inspect
gsutil cp gs://my-gcs-staging-bucket/exports/assess_tbl_000000000000.avro ./
```

### Verify Row Count

```bash
# For AVRO files
avro-tools getmeta assess_tbl_000000000000.avro

# For Parquet files
parquet-tools rowcount assess_tbl_000000000000.parquet

# For CSV files
wc -l assess_tbl_000000000000.csv
```

## Troubleshooting

### Error: "Connection not found"

**Cause**: Invalid connection ID or connection doesn't exist

**Fix**:
1. Go to Connections page
2. Verify BigQuery connection exists
3. Note the connection ID
4. Use correct ID in export test

### Error: "Service Account Key not found"

**Cause**: Connection missing credentials

**Fix**:
1. Edit BigQuery connection
2. Add service account JSON key
3. Test connection
4. Retry export

### Error: "Table not found"

**Cause**: Invalid project/dataset/table name

**Fix**:
1. Verify table exists in BigQuery console
2. Check spelling of project, dataset, table
3. Ensure service account has access
4. Use correct format: `project.dataset.table`

### Error: "Permission denied"

**Cause**: Service account lacks permissions

**Fix**:
1. Grant BigQuery Data Viewer role
2. Grant Storage Object Creator role
3. Verify bucket permissions
4. Check IAM policies

### Error: "Bucket not found"

**Cause**: GCS bucket doesn't exist or no access

**Fix**:
1. Create GCS bucket if needed
2. Grant service account write access
3. Verify bucket name (no gs:// prefix)
4. Check bucket location matches region

## Performance Expectations

### Small Tables (< 1 GB)

- **Export Time**: 5-15 seconds
- **Files Created**: 1
- **Throughput**: ~100 MB/s

### Medium Tables (1-10 GB)

- **Export Time**: 15-60 seconds
- **Files Created**: 1-5
- **Throughput**: ~200 MB/s

### Large Tables (10-100 GB)

- **Export Time**: 1-5 minutes
- **Files Created**: 5-20
- **Throughput**: ~300 MB/s

### Very Large Tables (> 100 GB)

- **Export Time**: 5-30 minutes
- **Files Created**: 20-100+
- **Throughput**: ~400 MB/s

**Note**: BigQuery automatically splits large exports into multiple files (~100 MB each)

## Next Steps

After successful BigQuery to GCS export:

1. ✅ **Verify Files**: Check GCS bucket for exported files
2. ⏳ **GCS to S3 Transfer**: Coming soon - test transferring files to S3
3. ⏳ **S3 to Redshift Load**: Coming soon - test loading into Redshift
4. ⏳ **End-to-End Pipeline**: Full migration workflow

## Files Created

### Backend
- `backend/routers/bq_export_test_router.py` - Export API endpoint
- `backend/main.py` - Router registration

### Frontend
- `frontend/src/pages/BQExportTestPage.tsx` - Testing UI
- `frontend/src/App.tsx` - Route configuration

## API Documentation

### POST /api/bq-export-test/export

**Description**: Export BigQuery table to GCS

**Authentication**: Required (Bearer token)

**Request Body**:
```typescript
{
  connection_id: number;      // BigQuery connection ID
  project_id: string;         // GCP project ID
  dataset: string;            // BigQuery dataset
  table: string;              // BigQuery table
  gcs_bucket: string;         // GCS bucket (no gs:// prefix)
  gcs_path: string;           // Path in bucket
  export_format: string;      // AVRO, PARQUET, CSV, JSON
  compression?: string;       // GZIP, SNAPPY, DEFLATE, null
}
```

**Response**: `BQExportTestResponse`

**Status Codes**:
- `200 OK`: Export completed (check success field)
- `400 Bad Request`: Invalid input
- `404 Not Found`: Connection or table not found
- `500 Internal Server Error`: Export failed

### GET /api/bq-export-test/formats

**Description**: Get available export formats

**Authentication**: Required

**Response**:
```json
{
  "formats": [
    {
      "value": "AVRO",
      "label": "AVRO",
      "description": "Binary format, preserves schema...",
      "compression": ["SNAPPY", "DEFLATE", "None"]
    }
  ]
}
```

## Best Practices

1. **Start Small**: Test with small tables first
2. **Use AVRO**: Best format for large-scale migrations
3. **Enable Compression**: SNAPPY for speed, GZIP for size
4. **Verify Results**: Always check GCS bucket after export
5. **Monitor Costs**: BigQuery exports incur egress charges
6. **Clean Up**: Delete test files from GCS after verification

## Success Criteria

✅ Export completes without errors  
✅ Files appear in GCS bucket  
✅ Row count matches source table  
✅ File format is correct  
✅ Compression applied (if selected)  
✅ Export time is reasonable  
✅ No data loss or corruption  

## Production Readiness

This testing interface is **production-ready** for:
- ✅ Testing BigQuery exports
- ✅ Validating credentials
- ✅ Verifying table access
- ✅ Comparing formats and compression
- ✅ Performance benchmarking

**Not yet implemented**:
- ⏳ GCS to S3 transfer
- ⏳ S3 to Redshift load
- ⏳ End-to-end pipeline orchestration
- ⏳ Automated scheduling
- ⏳ Progress tracking for long exports

The BigQuery to GCS export is fully functional and ready for production testing!
