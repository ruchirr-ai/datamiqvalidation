# GCS Export Path Structure - Updated ✅

**Date**: February 9, 2026

## New GCS Path Structure

Files are now exported with an organized structure:

```
gs://bucket_name/dataset_name/table_name/filename
```

### Example:
```
gs://bq_data_transfer_rs/sales_analytics/customers/customers_000000000000.avro.snappy
gs://bq_data_transfer_rs/sales_analytics/orders/orders_000000000000.avro.snappy
```

## Changes Made

### 1. Updated BigQueryExporter Path Logic

**File**: `backend/services/bq_redshift_migration/bigquery_exporter.py`

**Changes**:
- Removed hardcoded "staging" prefix
- Files now go directly to `bucket/dataset/table/` structure
- If `gcs_path` is provided in migration config, it's used as a base prefix
- If `gcs_path` is empty, files go directly to `dataset/table/`

**Code**:
```python
# Build destination URI with organized structure: bucket/dataset/table/filename
if gcs_path:
    # Remove leading/trailing slashes
    gcs_path = gcs_path.strip('/')
    # Build path with base prefix
    organized_path = f"/{gcs_path}/{dataset}/{table}" if gcs_path else f"/{dataset}/{table}"
else:
    # No base path, go directly to dataset/table
    organized_path = f"/{dataset}/{table}"

file_extension = self._get_file_extension(export_format, compression)
destination_uri = f"gs://{gcs_bucket}{organized_path}/{table}_*.{file_extension}"
```

### 2. Updated Migration Configuration

**Database Update**:
```sql
UPDATE migrations_bq_redshift 
SET gcs_path = '' 
WHERE id = 3;
```

Now `gcs_path` is empty, so files export directly to `bucket/dataset/table/`.

## Path Structure Options

### Option 1: No Base Path (Current)
**Config**: `gcs_path = ""`
**Result**: `gs://bucket/dataset/table/filename`

### Option 2: With Base Path
**Config**: `gcs_path = "staging"`
**Result**: `gs://bucket/staging/dataset/table/filename`

### Option 3: With Nested Base Path
**Config**: `gcs_path = "exports/2026-02-09"`
**Result**: `gs://bucket/exports/2026-02-09/dataset/table/filename`

## Benefits

1. **Organized Structure**: Easy to navigate in GCS console
2. **Dataset Isolation**: Each dataset has its own folder
3. **Table Isolation**: Each table has its own folder
4. **Flexible Base Path**: Optional base path for additional organization
5. **Clean URLs**: No hardcoded "staging" prefix

## File Naming Convention

Files are named with the pattern: `{table}_*.{extension}`

Examples:
- `customers_000000000000.avro.snappy`
- `orders_000000000000.avro.snappy`
- `orders_000000000001.avro.snappy` (if table is large and split into multiple files)

## Export Format and Compression

The export format and compression type are taken from the migration configuration:

- **Format**: `migration.export_format` (AVRO, PARQUET, CSV, JSON)
- **Compression**: `migration.compression` (SNAPPY, GZIP, DEFLATE, ZSTD, NONE)

These are configured in the migration wizard when creating a migration.

## Testing

**Test Script**: `backend/test_direct_bq_export.py`

**Test Results**:
```
Dataset: sales_analytics
Tables: ['customers', 'orders']
GCS Bucket: gs://bq_data_transfer_rs
GCS Path: (empty)

Results:
✓ customers exported - Job ID: 38eae890-276e-4ee9-bf62-971d21b94dfd
✓ orders exported - Job ID: e64ea8d4-4c67-48af-9e63-291cdb632eb4

Expected GCS Paths:
- gs://bq_data_transfer_rs/sales_analytics/customers/customers_*.avro.snappy
- gs://bq_data_transfer_rs/sales_analytics/orders/orders_*.avro.snappy
```

## Verification

Check the GCS bucket to verify the new structure:

1. Go to: https://console.cloud.google.com/storage/browser/bq_data_transfer_rs
2. You should see folders:
   - `sales_analytics/`
     - `customers/`
       - `customers_000000000000.avro.snappy`
     - `orders/`
       - `orders_000000000000.avro.snappy`

## Migration Configuration

When creating a migration, the path structure is automatically organized:

1. **GCS Bucket**: User-specified bucket name
2. **GCS Path**: Optional base path (can be empty)
3. **Dataset**: Automatically added from source dataset
4. **Table**: Automatically added for each table
5. **Format**: User-specified export format
6. **Compression**: User-specified compression type

---

**Status**: GCS export path structure updated and tested successfully! ✅
