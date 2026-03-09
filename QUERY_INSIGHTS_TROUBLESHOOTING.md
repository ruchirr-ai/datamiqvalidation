# Query Insights & User Insights Troubleshooting Guide

## Quick Diagnosis

If Query Insights and User Insights are not showing data in the Assessment Report, follow these steps:

### Step 1: Run Diagnostic Script

```bash
cd backend
python debug_query_insights.py <assessment_id>
```

**Example:**
```bash
python debug_query_insights.py 1
```

This will show you:
- ✅ Whether query statistics were collected
- ✅ Number of queries and unique users
- ✅ Time range of query history
- ✅ Sample query data
- ✅ User breakdown with metrics

### Step 2: Interpret Results

#### If you see "NO QUERY STATS FOUND"

**Problem**: The assessment didn't collect query statistics from BigQuery.

**Common Causes**:
1. BigQuery region detection failed
2. Service account lacks permissions
3. INFORMATION_SCHEMA.JOBS_BY_PROJECT not accessible
4. No queries in BigQuery history (last 180 days)

**Solutions**:
- Check backend logs for INFORMATION_SCHEMA errors
- Verify service account has `bigquery.jobUser` role
- Manually specify BigQuery region in assessment service
- Verify BigQuery has query history

#### If you see query stats but UI shows nothing

**Problem**: Frontend issue or API serialization problem.

**Solutions**:
- Open browser DevTools console
- Look for JavaScript errors
- Check Network tab for API response
- Verify `query_stats` array in API response

### Step 3: Test Frontend

Open the test page in your browser:

```
http://localhost:3000/test_query_insights.html
```

This will:
- Fetch assessment report from API
- Validate query_stats structure
- Test user aggregation logic
- Show sample data

### Step 4: Check Backend Logs

```bash
tail -f backend/backend.log | grep -i "query statistics"
```

Look for:
- "Querying INFORMATION_SCHEMA with region: ..."
- "✓ Collected X query statistics from region-..."
- Any error messages

## Common Issues & Fixes

### Issue 1: Empty Query Stats

**Symptom**: `query_stats` array is empty

**Fix**: Re-run assessment with correct BigQuery region

**File**: `backend/services/bigquery_assessment_service.py`

```python
# Hardcode region if auto-detection fails
region = 'us'  # or 'eu', 'asia-northeast1', etc.
```

### Issue 2: Wrong Region

**Symptom**: "Could not collect query statistics from region-X"

**Fix**: Identify correct region and update code

**Test regions**:
```bash
# In BigQuery console, run:
SELECT COUNT(*) FROM `project-id.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT` LIMIT 1;
SELECT COUNT(*) FROM `project-id.region-eu.INFORMATION_SCHEMA.JOBS_BY_PROJECT` LIMIT 1;
```

### Issue 3: Permission Denied

**Symptom**: "Permission denied" or "Access denied" errors

**Fix**: Grant service account permissions

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com" \
    --role="roles/bigquery.jobUser"
```

### Issue 4: Time Filter Excluding All Data

**Symptom**: Data shows in "All Time" but not in "Last 24 Hours"

**Fix**: This is expected if queries are older than 24 hours

**Verify**: Check query execution times in diagnostic output

## Files Created

### Diagnostic Tools
- `backend/debug_query_insights.py` - Diagnostic script to check query stats
- `frontend/test_query_insights.html` - Frontend test page

### Documentation
- `docs/fixes/QUERY_USER_INSIGHTS_FIX.md` - Comprehensive fix guide
- `QUERY_INSIGHTS_TROUBLESHOOTING.md` - This quick reference

## Quick Reference

### Backend Files
- `backend/services/bigquery_assessment_service.py` - Query collection (line ~500)
- `backend/routers/assessment_router.py` - API endpoint (line ~635)
- `backend/repositories/assessment_repository.py` - Database queries

### Frontend Files
- `frontend/src/pages/AssessmentReportPage.tsx` - Query Insights (line ~1004), User Insights (line ~1378)

### Database Tables
- `assessment_query_stats` - Stores query statistics

## Need Help?

1. Run diagnostic script first
2. Check backend logs
3. Test frontend with test page
4. Review comprehensive fix guide: `docs/fixes/QUERY_USER_INSIGHTS_FIX.md`

---

**Created**: February 15, 2026  
**Status**: Diagnostic tools ready for use
