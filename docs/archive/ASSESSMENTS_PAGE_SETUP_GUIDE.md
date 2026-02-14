# Assessments Page Setup Guide

## Current Status
The Assessments page code has been created but you need to complete these steps to see it in the UI.

## Steps to See the Assessments Page

### Step 1: Run Database Migration
The assessment tables need to be created in the database.

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

This will create all the assessment tables (assessments, assessment_datasets, assessment_tables, etc.)

### Step 2: Restart Backend Server
The backend needs to be restarted to load the new assessment router.

**Option A: Using the script**
```bash
# Stop current backend
pkill -9 -f "uvicorn main:app"

# Start backend again
./START_BACKEND_HERE.sh
```

**Option B: Manual restart**
1. Stop the current backend process (Process ID: 2)
2. Navigate to backend directory
3. Run: `source .venv/bin/activate`
4. Run: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`

### Step 3: Verify Backend is Running
Open browser and check:
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/api/docs

You should see the new `/api/assessments/` endpoints in the API documentation.

### Step 4: Access Assessments Page
The frontend should already be running and hot-reloaded the new files.

1. Open browser: http://localhost:3000
2. Login if needed
3. Click "Assessments" in the sidebar
4. You should see the Assessments page (similar to Connections/Migrations)

## What You Should See

### Assessments Page Features:
- **Title**: "BigQuery Assessments" with FileSearch icon
- **Count**: Shows number of assessments
- **Search box**: To search assessments
- **"+ New Assessment" button**: To create new assessment
- **Table** with columns:
  - Project ID
  - Status (Pending/Running/Completed/Failed)
  - Datasets count
  - Tables count
  - Total Size
  - Started At
  - Completed At
  - Actions menu (three dots)

### Empty State:
If no assessments exist, you'll see:
- FileSearch icon
- "No assessments yet"
- "Create your first BigQuery assessment to analyze your data"
- "Create Your First Assessment" button

## Troubleshooting

### Issue: Assessments page not showing
**Solution**: Check browser console for errors. The route is `/assessments`

### Issue: "Failed to fetch assessments" error
**Solution**: 
1. Check backend is running on port 8000
2. Check API docs show assessment endpoints
3. Verify database migration ran successfully

### Issue: Can't create assessment
**Solution**:
1. Make sure you have a BigQuery connection created first
2. Check backend logs for errors
3. Verify service account JSON is in the connection

### Issue: Backend won't start
**Solution**:
1. Check if port 8000 is already in use: `lsof -i :8000`
2. Kill existing process: `kill -9 <PID>`
3. Check for Python errors in the terminal

## Testing the Assessment Flow

### 1. Create a BigQuery Connection
1. Go to Connections page
2. Click "+ New" → "Source Connection"
3. Select "BigQuery"
4. Fill in connection details with service account JSON
5. Save connection

### 2. Create an Assessment
1. Go to Assessments page
2. Click "+ New Assessment"
3. Select your BigQuery connection
4. Enter GCP Project ID
5. Click "Start Assessment"

### 3. Monitor Assessment Progress
1. Assessment will show "Pending" status initially
2. Then "Running" while extracting metadata
3. Finally "Completed" when done (or "Failed" if error)
4. This can take several minutes for large projects

### 4. View Assessment Report
1. Click three-dot menu on completed assessment
2. Select "View Report"
3. See all extracted metadata (to be implemented)

## Files Created

### Backend:
- ✅ `backend/services/bigquery_assessment_service.py`
- ✅ `backend/repositories/assessment_repository.py`
- ✅ `backend/routers/assessment_router.py`
- ✅ `backend/main.py` (modified - added router)

### Frontend:
- ✅ `frontend/src/pages/AssessmentsPage.tsx`
- ✅ `frontend/src/pages/AssessmentsPage.css`
- ✅ `frontend/src/components/assessments/CreateAssessmentModal.tsx`
- ✅ `frontend/src/components/assessments/CreateAssessmentModal.css`
- ✅ `frontend/src/App.tsx` (modified - added route)

### Database:
- ✅ `backend/models/assessment.py` (already existed)
- ✅ `backend/alembic/versions/010_create_assessment_tables.py` (already existed)

## Quick Verification Commands

```bash
# Check if backend is running
curl http://localhost:8000/health

# Check if assessment endpoints exist
curl http://localhost:8000/api/docs

# Check if frontend is running
curl http://localhost:3000

# Check database tables
psql -d your_database -c "\dt assessment*"
```

## Next Steps After Setup

1. **Test creating an assessment** with a real BigQuery connection
2. **Monitor the background task** execution
3. **View the assessment results** in the table
4. **Implement the report viewer page** for detailed metadata view

## Support

If you're still not seeing the Assessments page after following these steps:

1. Check browser console (F12) for JavaScript errors
2. Check backend terminal for Python errors
3. Verify the route in App.tsx: `/assessments` → `AssessmentsPage`
4. Clear browser cache and hard refresh (Ctrl+Shift+R)
5. Check network tab to see if API calls are being made

The page design matches Connections and Migrations pages exactly, so it should look familiar and professional!
