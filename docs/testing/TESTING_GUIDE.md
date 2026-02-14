# Testing Guide: BigQuery Metadata Discovery

## Quick Test Steps

### 1. Navigate to Migrations Page
- Open browser: `http://localhost:3000`
- Click **Migrations** in sidebar
- Click **Create Migration** button

### 2. Select Migration Type
- Choose **BigQuery → Redshift**
- Click **Next**

### 3. Select Source Connection
- In **Connection Configuration** step
- **Source Connection** dropdown: Select `test`, `test_bq`, or `bq_demo`
- Click **Next**

### 4. View Real BigQuery Data
You should now see the **Setup Data Migration** step with:

#### Expected Real Data:
```
Dataset: sales_analytics (asia-south1)
├── assess_tbl
│   ├── 10,000,000 rows
│   └── 10.5 GB
├── assess_tbl_part_clust
│   ├── 10,000,000 rows
│   └── 10.5 GB
├── customers
│   ├── 3 rows
│   └── 161 bytes
└── ... 3 more tables
```

#### If You See Sample Data Instead:
```
Dataset: analytics (US)
├── customers: 1,250,000 rows
├── orders: 5,800,000 rows
└── ...

Dataset: sales (US)
Dataset: marketing (EU)
```

**This means the API call failed** - Check troubleshooting below.

## Troubleshooting

### Check 1: Browser Console
Press `F12` → Console tab

**Look for**:
- ✅ No errors = Good
- ❌ "Failed to fetch" = Network/backend issue
- ❌ "401 Unauthorized" = Authentication issue
- ❌ "404 Not Found" = Connection doesn't exist

### Check 2: Network Tab
Press `F12` → Network tab

**Find**: `discover-metadata` request

**Check**:
- Status: Should be `200 OK`
- Response: Should contain `sales_analytics` dataset
- Request Headers: Should have `Authorization: Bearer <token>`

### Check 3: Backend Logs
Look at terminal running backend

**Should see**:
```
=== BigQuery Metadata Discovery Started ===
Connection ID: 2, Project ID: assessiq-484512
✓ BigQuery client created successfully
✓ Found 1 datasets
Processing dataset: sales_analytics
  - Found 6 tables
=== Metadata Discovery Complete: 1 datasets, 6 tables ===
```

**If you see errors**:
- "Connection not found" → Wrong connection ID or workspace
- "Service Account Key is required" → Credentials missing
- "Invalid credentials" → Credentials malformed
- "Failed to discover" → BigQuery API error

## Common Issues & Solutions

### Issue 1: "Using sample data for testing" Warning

**Symptoms**: Orange warning box at top of page

**Cause**: API call failed, frontend fell back to sample data

**Solution**:
1. Check if logged in (try refreshing page)
2. Check backend logs for error details
3. Verify connection exists in Connections page

### Issue 2: No Datasets Shown

**Symptoms**: Empty state "No datasets found"

**Cause**: BigQuery project has no datasets

**Solution**:
1. Verify project ID is correct
2. Check service account has permissions
3. Create a dataset in BigQuery console

### Issue 3: Authentication Error

**Symptoms**: "Token is empty" or "401 Unauthorized"

**Cause**: Not logged in or token expired

**Solution**:
1. Log out and log back in
2. Clear browser cache
3. Check localStorage has `access_token`

### Issue 4: Connection Not Found

**Symptoms**: "Connection X not found"

**Cause**: Connection doesn't exist or wrong workspace

**Solution**:
1. Go to Connections page
2. Verify connection exists
3. Note the connection ID
4. Try creating a new BigQuery connection

## Verification Checklist

- [ ] Can navigate to Migrations page
- [ ] Can click Create Migration
- [ ] Can select BigQuery → Redshift
- [ ] Can select a BigQuery connection
- [ ] See "Setup Data Migration" step
- [ ] See real dataset: `sales_analytics`
- [ ] See real tables with row counts
- [ ] Can expand/collapse datasets
- [ ] Can select/deselect tables
- [ ] See summary statistics update
- [ ] Can search datasets
- [ ] Can click "Select All" / "Deselect All"
- [ ] Can click "Refresh" to reload data

## Success Criteria

✅ **You should see**:
- Real dataset name: `sales_analytics`
- Real table names: `assess_tbl`, `assess_tbl_part_clust`, `customers`
- Real row counts: 10,000,000, 10,000,000, 3
- Real data sizes: 10.5 GB, 10.5 GB, 161 bytes
- Location: asia-south1
- 6 tables total

❌ **You should NOT see**:
- Sample datasets: `analytics`, `sales`, `marketing`
- Sample tables: `user_activity`, `sessions`, `revenue`
- Sample locations: `US`, `EU`
- Warning: "Using sample data for testing"

## Need Help?

If you're still seeing sample data after checking all the above:

1. **Share Backend Logs**: Copy the terminal output when you click Next
2. **Share Browser Console**: Copy any error messages from F12 console
3. **Share Network Response**: Copy the response from discover-metadata request

The comprehensive logging will help identify the exact issue.
