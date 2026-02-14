# Assessment Testing Guide

## Current Status
✅ Backend restarted with all fixes applied
✅ Assessment ID 7 reset to "pending" status
✅ Ready for testing

## Testing Steps

### Step 1: Run Assessment
1. Open browser: http://localhost:3000/assessments
2. Find assessment "bq_rs_assess" (ID: 7)
3. Click the three-dot menu (⋮) on the right
4. Click "Run Assessment"
5. You should see: "Assessment started successfully. It will run in the background."

### Step 2: Watch Status Updates
- Status should change from "Pending" (grey) → "Running" (yellow)
- UI polls every 3 seconds automatically
- Watch the status badge change color
- After ~30-60 seconds, status should change to "Completed" (green) or "Failed" (red)

### Step 3: View Logs
1. While assessment is running (or after), click three-dot menu
2. Click "View Logs"
3. You should see logs like:
   - "Assessment execution started"
   - "Assessment status updated to running"
   - "Collecting datasets..."
   - "Collected X datasets"
   - etc.

### Step 4: View Report (Once Completed)
1. Wait for status to show "Completed" (green badge)
2. Click three-dot menu
3. Click "View Report" (should now be enabled)
4. You should see:
   - Summary cards with totals (Datasets, Tables, Views, etc.)
   - Assessment details (Project ID, timestamps)
   - Datasets table with all collected data

## Expected Results

### Successful Assessment
```
Status: pending → running → completed
Total Datasets: 1
Total Tables: 7
Total Size: ~20 GB
```

### If Assessment Fails
1. Check "View Logs" to see error message
2. Status will show "Failed" (red badge)
3. Error message will be displayed in logs

## Troubleshooting

### Status Not Updating
- Check browser console for errors (F12)
- Verify backend is running: http://localhost:8000/api/assessments/
- Check backend logs for errors

### "View Report" Still Disabled
- Verify status is exactly "completed" (not "running" or "failed")
- Refresh the page
- Check browser console for errors

### Assessment Fails
- Click "View Logs" to see detailed error
- Common issues:
  - BigQuery credentials invalid
  - Network connectivity issues
  - Insufficient permissions

## Backend Logs Location
Check terminal where you ran `./START_BACKEND_HERE.sh` for detailed logs

## Database Check
To manually check assessment status:
```bash
cd backend
source .venv/bin/activate
python -c "
from database import db_instance
from models.assessment import Assessment
from models.assessment_log import AssessmentLog

db = db_instance.SessionLocal()
assessment = db.query(Assessment).filter(Assessment.id == 7).first()
print(f'Status: {assessment.status}')
print(f'Datasets: {assessment.total_datasets}')
print(f'Tables: {assessment.total_tables}')
print(f'Error: {assessment.error_message}')

logs = db.query(AssessmentLog).filter(AssessmentLog.assessment_id == 7).count()
print(f'Total logs: {logs}')
db.close()
"
```

## Next Steps After Successful Test
1. Test with different BigQuery projects
2. Test with larger datasets
3. Verify report shows all metadata correctly
4. Test concurrent assessments
5. Test error handling (invalid credentials, etc.)

## Files Modified (For Reference)
- `backend/services/bigquery_assessment_service.py` - Fixed schema mismatches
- `backend/main.py` - Added model imports
- `frontend/src/App.tsx` - Added report route
- `frontend/src/pages/AssessmentsPage.tsx` - Fixed navigation

## Support
If issues persist:
1. Check backend logs
2. Check browser console
3. Verify BigQuery credentials are valid
4. Ensure database migration 014 is applied
