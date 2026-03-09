# Security Policies Display Fix

## Issue
Row-level security (RLS) policies were not displaying properly in the Security section of assessment reports because the `security_metadata` field (containing DDL) was missing from the API response.

## Changes Made

### 1. Backend API Fix (`backend/routers/assessment_router.py`)
Added `security_metadata` field to the security policies response:

```python
"security_policies": [
    {
        "security_type": s.security_type,
        "table_name": s.table_name,
        "policy_name": s.policy_name,
        "filter_predicate": s.filter_predicate,
        "grantees": s.grantees or [],
        "security_metadata": s.security_metadata or {}  # ← Added this field
    }
    for s in security_policies
],
```

### 2. Backfill Script (`backend/scripts/backfill_security_metadata.py`)
Created a script to re-collect security policies for existing assessments to ensure the `security_metadata` field is properly populated.

## How to Apply the Fix

**📋 See detailed step-by-step instructions in: [APPLY_SECURITY_FIX.md](./APPLY_SECURITY_FIX.md)**

### Quick Summary

1. **Restart Backend Server** - Required for API changes to take effect
2. **Run Backfill Script** - Updates existing assessments with security metadata
3. **Verify in UI** - Check that security policies now display properly

```bash
# Step 1: Restart backend
cd backend
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Step 2: Run backfill (in a new terminal)
cd backend
source .venv/bin/activate
python scripts/backfill_security_metadata.py

# Step 3: Verify in browser
# Open assessment report → Security Policies tab
```

## What Gets Displayed

### Row-Level Security (RLS)
- Policy name
- Table name
- Filter predicate
- Grantees (users/groups with access)
- DDL (policy creation statement)

### Column-Level Security (CLS)
- Tables with policy tags
- Columns with policy tags
- Policy tag names

## Notes

- If no security policies are found, it means:
  1. Your BigQuery dataset doesn't have RLS policies configured
  2. The service account doesn't have permission to read `INFORMATION_SCHEMA.ROW_ACCESS_POLICIES`
  3. The policies exist but weren't collected during assessment

- The backfill script is safe to run multiple times
- It will replace existing security policy data with fresh data from BigQuery
- Only completed assessments are processed

## Testing

To verify the fix works:

1. Create a test RLS policy in BigQuery:
```sql
CREATE ROW ACCESS POLICY test_policy
ON `project.dataset.table`
GRANT TO ("user:test@example.com")
FILTER USING (status = 'active');
```

2. Run a new assessment or re-run the backfill script
3. Check the Security section in the assessment report
4. The policy should now be visible with all details

## Files Modified

- `backend/routers/assessment_router.py` - Added security_metadata to API response
- `backend/scripts/backfill_security_metadata.py` - New backfill script

## Related Documentation

- BigQuery RLS: https://cloud.google.com/bigquery/docs/row-level-security-intro
- Assessment Security Model: `backend/models/assessment.py` (AssessmentSecurity class)
- Security Collection: `backend/services/bigquery_assessment_service.py` (collect_security_policies_detailed method)
