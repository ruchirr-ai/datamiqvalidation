# Quick Fix: Security Policies Display

## 🎯 Goal
Make Row-Level Security (RLS) policies visible in existing assessment reports.

## ⚡ Quick Steps

### 1️⃣ Restart Backend (Required)
```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 2️⃣ Update Existing Reports (Recommended)
Open a **new terminal** and run:
```bash
cd backend
source .venv/bin/activate
python scripts/backfill_security_metadata.py
```

### 3️⃣ Verify
- Open any assessment report in browser
- Go to "Security Policies" tab
- RLS policies should now be visible with DDL

## 📊 Expected Results

**Before Fix:**
- Security policies section empty or incomplete
- No DDL statements shown

**After Fix:**
- ✅ Row-Level Security policies displayed
- ✅ Policy names, tables, and filter predicates shown
- ✅ DDL/creation statements included
- ✅ Grantees (users/groups) listed
- ✅ Column-Level Security policy tags shown

## ⏱️ Time Required
- Backend restart: ~10 seconds
- Backfill script: ~30 seconds per assessment

## 🔍 Troubleshooting

**No policies found?**
- Your BigQuery might not have RLS policies configured (this is normal)
- Check service account has `bigquery.rowAccessPolicies.list` permission

**Script fails?**
- Ensure backend server is running
- Check BigQuery connection credentials are valid
- Verify assessments completed successfully

## 📚 Full Documentation
- Detailed guide: [APPLY_SECURITY_FIX.md](./APPLY_SECURITY_FIX.md)
- Technical details: [SECURITY_POLICIES_FIX.md](./SECURITY_POLICIES_FIX.md)

## ✅ Checklist
- [ ] Backend server restarted
- [ ] Backfill script executed successfully
- [ ] Security policies visible in UI
- [ ] DDL statements displayed
- [ ] All existing reports updated
