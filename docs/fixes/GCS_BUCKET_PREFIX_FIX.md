# GCS Bucket Prefix Fix

## Problem

Migration export was failing with error:
```
Invalid extract destination URI 'gs://gs://bq_data_transfer_rs/staging/sales_analytics/customers/customers_*.parquet'
```

Notice the **double `gs://` prefix**!

## Root Cause

The user entered the GCS bucket as `gs://bq_data_transfer_rs` in the UI, but the backend code was adding another `gs://` prefix, resulting in:
```
gs:// + gs://bq_data_transfer_rs + /path = gs://gs://bq_data_transfer_rs/path
```

## Solution

Modified `backend/services/bq_redshift_migration/bigquery_exporter.py` to strip the `gs://` prefix if present:

```python
# Clean up gcs_bucket - remove gs:// prefix if present
clean_bucket = gcs_bucket.replace('gs://', '').strip('/')

# Use clean_bucket in destination URI
destination_uri = f"gs://{clean_bucket}{organized_path}/{table}_*.{file_extension}"
```

Now it works correctly whether the user enters:
- `gs://bq_data_transfer_rs` → cleaned to `bq_data_transfer_rs`
- `bq_data_transfer_rs` → stays as `bq_data_transfer_rs`

## Files Modified

- `backend/services/bq_redshift_migration/bigquery_exporter.py`
  - Added `clean_bucket` variable that strips `gs://` prefix
  - Updated all `destination_uri` constructions to use `clean_bucket`

## Testing

### 1. Restart Backend Server
```bash
# Stop backend (Ctrl+C)
# Start again
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

### 2. Run the Migration Again
1. Go to Migrations page
2. Find migration ID 8
3. Click "Run" button
4. Watch logs

### Expected Result
```
[INFO] Starting BigQuery export to GCS
[INFO] Exporting 2 tables from sales_analytics
[INFO] ✓ Table customers exported successfully
[INFO] ✓ Table orders exported successfully
[INFO] Export completed: 2/2 tables exported successfully
```

### 3. Verify in GCS
Check your GCS bucket for files:
```
gs://bq_data_transfer_rs/staging/sales_analytics/customers/customers_*.parquet
gs://bq_data_transfer_rs/staging/sales_analytics/orders/orders_*.parquet
```

## Summary

✅ **Fixed**: GCS bucket prefix handling
✅ **Result**: Export will now work correctly regardless of whether user includes `gs://` prefix

The migration should now successfully export data to GCS!
