# Query Insights No Data Fix

## Problem
Query Insights tab shows no data even though assessments have been run.

## Root Cause
Query statistics are not being collected during assessment because:
1. BigQuery INFORMATION_SCHEMA.JOBS_BY_PROJECT requires specific permissions
2. Service account may lack `bigquery.jobs.list` permission
3. Region detection might be incorrect
4. Errors are being caught silently and returning empty list

## Diagnosis

Run the diagnostic script to identify the issue:

```bash
cd backend
source .venv/bin/activate
python diagnose_query_insights.py
```

This will check:
1. Environment variables
2. BigQuery client initialization
3. Region detection
4. INFORMATION_SCHEMA access
5. Sample query data retrieval

## Solutions

### Solution 1: Grant Required Permissions

The service account needs these IAM roles:

1. **BigQuery Job User** - Required to list and view job information
   ```bash
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
     --role="roles/bigquery.jobUser"
   ```

2. **BigQuery Data Viewer** - Required to read INFORMATION_SCHEMA
   ```bash
   gcloud projects add-iam-policy-binding PROJECT_ID \
     --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
     --role="roles/bigquery.dataViewer"
   ```

### Solution 2: Fix Region Detection

If the region is incorrectly detected, you can:

1. **Check your dataset location**:
   ```sql
   SELECT 
     schema_name,
     location
   FROM `PROJECT_ID.INFORMATION_SCHEMA.SCHEMATA`
   LIMIT 10;
   ```

2. **Update the region detection logic** in `backend/services/bigquery_assessment_service.py`:
   ```python
   # Around line 485-500
   # Try different region formats based on your location:
   # - 'us' for US multi-region
   # - 'eu' for EU multi-region
   # - 'us-central1' for specific US region
   # - 'europe-west1' for specific EU region
   ```

### Solution 3: Test INFORMATION_SCHEMA Access

Test if you can query INFORMATION_SCHEMA directly:

```sql
SELECT COUNT(*) as job_count
FROM `PROJECT_ID.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
  AND job_type = 'QUERY'
  AND state = 'DONE';
```

Replace:
- `PROJECT_ID` with your GCP project ID
- `region-us` with your region (try: `region-us`, `region-eu`, `us-central1`, etc.)

### Solution 4: Enable Better Error Logging

Temporarily improve error logging to see what's failing:

1. Edit `backend/services/bigquery_assessment_service.py`
2. Find the `collect_query_statistics_detailed` method (around line 550)
3. Update the exception handler:

```python
except Exception as e:
    print(f"❌ ERROR: Could not collect query statistics from region-{region}")
    print(f"Error type: {type(e).__name__}")
    print(f"Error message: {str(e)}")
    import traceback
    traceback.print_exc()
    # Return empty list if INFORMATION_SCHEMA is not accessible
```

4. Run a new assessment and check the logs

## Verification

After applying fixes:

1. **Run a new assessment**:
   - Go to Assessments page
   - Create a new assessment
   - Wait for completion

2. **Check the logs** for:
   ```
   ✓ Collected X query statistics from region-{region}
   ```

3. **Verify in database**:
   ```sql
   SELECT COUNT(*) 
   FROM assessment_query_stats 
   WHERE assessment_id = YOUR_ASSESSMENT_ID;
   ```

4. **Check Query Insights tab**:
   - Navigate to Assessment Report
   - Click Query Insights tab
   - Data should now be visible

## Common Issues

### Issue 1: "Permission denied" error
**Solution**: Grant BigQuery Job User role (see Solution 1)

### Issue 2: "Table not found" error
**Solution**: Fix region format (see Solution 2)

### Issue 3: "No queries found"
**Possible causes**:
- No queries have been run in the last 180 days
- Queries were run by different users/service accounts
- INFORMATION_SCHEMA retention period expired

### Issue 4: Region-specific INFORMATION_SCHEMA
Some organizations use region-specific datasets. Try these formats:
- `PROJECT_ID.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
- `PROJECT_ID.us-central1.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
- `PROJECT_ID.INFORMATION_SCHEMA.JOBS_BY_PROJECT` (no region prefix)

## Testing in Production

For production environments:

1. **Check service account permissions**:
   ```bash
   gcloud projects get-iam-policy PROJECT_ID \
     --flatten="bindings[].members" \
     --filter="bindings.members:serviceAccount:SERVICE_ACCOUNT_EMAIL"
   ```

2. **Verify BigQuery API is enabled**:
   ```bash
   gcloud services list --enabled --filter="bigquery"
   ```

3. **Test with gcloud**:
   ```bash
   bq query --use_legacy_sql=false \
     "SELECT COUNT(*) FROM \`PROJECT_ID.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT\` LIMIT 1"
   ```

## Alternative: Manual Query Stats Collection

If INFORMATION_SCHEMA access cannot be granted, you can:

1. Export query logs to BigQuery using Cloud Logging
2. Create a custom table with query statistics
3. Modify the assessment service to read from your custom table

## Next Steps

1. Run diagnostic script
2. Apply appropriate solution based on diagnosis
3. Run new assessment
4. Verify data appears in Query Insights tab
5. If still not working, check backend logs for detailed errors

## Support

If issues persist:
1. Check backend logs: `backend/backend.log`
2. Check browser console for API errors
3. Verify API endpoint works: `GET /api/assessments/{id}/query-insights`
4. Contact support with diagnostic script output
