# Quick Test: BigQuery Real Data

## 🚀 Fast Test (2 minutes)

### Step 1: Open Migration Wizard
```
http://localhost:3000 → Migrations → Create Migration
```

### Step 2: Select Type
```
BigQuery → Redshift → Next
```

### Step 3: Select Connection
```
Source Connection: test (or test_bq or bq_demo) → Next
```

### Step 4: Verify Real Data
```
✅ Should see: sales_analytics dataset
✅ Should see: assess_tbl (10M rows, 10.5 GB)
❌ Should NOT see: analytics, sales, marketing (sample data)
```

## 🔍 Quick Debug

### If you see sample data:

**1. Check Browser Console (F12)**
```javascript
// Look for errors
Failed to fetch
401 Unauthorized
404 Not Found
```

**2. Check Backend Logs**
```bash
# Terminal running backend
# Should see:
=== BigQuery Metadata Discovery Started ===
✓ Found 1 datasets
Processing dataset: sales_analytics
```

**3. Check Network Tab (F12)**
```
Request: POST /api/migrations/bq-redshift/discover-metadata
Status: 200 OK
Response: { "datasets": [...], "tables": {...} }
```

## 📊 Expected Results

### Real Data:
- **Dataset**: sales_analytics
- **Location**: asia-south1
- **Tables**: 6
- **Total Rows**: 20,000,003
- **Total Size**: 21+ GB

### Sample Data (means API failed):
- **Datasets**: analytics, sales, marketing
- **Locations**: US, EU
- **Warning**: "Using sample data for testing"

## 🛠️ Quick Fixes

### Not logged in?
```
Log out → Log in → Try again
```

### Backend not running?
```bash
cd backend
source .venv/bin/activate
python main.py
```

### Connection not found?
```
Go to Connections page → Verify connection exists
```

## ✅ Success Checklist

- [ ] Backend running on port 8000
- [ ] Frontend running on port 3000
- [ ] Logged in to application
- [ ] BigQuery connection exists
- [ ] See real dataset name
- [ ] See real row counts
- [ ] See real data sizes
- [ ] No warning message

## 📞 Need Help?

Check these files:
- `TESTING_GUIDE.md` - Detailed testing steps
- `BIGQUERY_METADATA_REAL_DATA_READY.md` - Full implementation details
- `IMPLEMENTATION_SUMMARY.md` - Overview and technical details

Share these if issues persist:
- Browser console errors
- Backend log output
- Network tab response
