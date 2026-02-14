# Run Assessment Diagnostic

## Step 1: Run the Diagnostic Script

```bash
cd backend
python diagnose_assessment_issues.py
```

When prompted, enter the Assessment ID you want to diagnose (e.g., 1, 2, 3, etc.)

## Step 2: Check API Response

Also run this command to see what the API is returning:

```bash
# Replace {assessment_id} with your actual assessment ID
curl http://localhost:8000/api/assessments/{assessment_id}/report | python -m json.tool > assessment_report_output.json
```

Then check the file `assessment_report_output.json` to see the actual data structure.

## Step 3: Check for Existing Assessments

To see what assessments exist:

```bash
curl http://localhost:8000/api/assessments/ | python -m json.tool
```

## What to Share

After running these commands, please share:

1. The complete output from `diagnose_assessment_issues.py`
2. The first table entry from `assessment_report_output.json` (just the first table object)
3. The first query stat entry from `assessment_report_output.json` (just the first query object)
4. Any error messages you see in the browser console when viewing the report

## Quick Browser Console Check

Also, open the assessment report page in your browser and:

1. Open Developer Tools (F12)
2. Go to Console tab
3. Look for any errors (red text)
4. Share any errors you see

This will help me understand exactly what's wrong and provide targeted fixes.
