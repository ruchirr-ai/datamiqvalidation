# How to Fix User Insights - Quick Guide

## TL;DR

**Your current assessment has OLD data. Run a NEW assessment to see all users and recent queries.**

## Visual Explanation

### Current Situation (OLD Assessment)

```
Assessment ID: 7 (captured 2 weeks ago with OLD code)
═══════════════════════════════════════════════════════════════

Collection Window: 7 days
Captured Data:
  ┌─────────────────────────────────────────┐
  │ Queries: ~1 query                       │
  │ Users: 1 user (manasa.k@shellkode.com) │
  │ Time Range: 2-3 weeks ago               │
  └─────────────────────────────────────────┘

When you filter "Last 24 Hours":
  ┌──────────────────────────────────────────────────────┐
  │ Looking for: Queries from last 24 hours (from NOW)  │
  │ Found: NOTHING ❌                                    │
  │ Reason: All queries are 2-3 weeks old               │
  └──────────────────────────────────────────────────────┘

User Insights:
  ┌──────────────────────────────────────────┐
  │ Users shown: 1 user                      │
  │ Missing: assessiq, demo, service accounts│
  │ Reason: Only 1 user was active in that   │
  │         7-day window 2 weeks ago         │
  └──────────────────────────────────────────┘
```

### After NEW Assessment

```
Assessment ID: NEW (captured TODAY with NEW code)
═══════════════════════════════════════════════════════════════

Collection Window: 180 days
Captured Data:
  ┌──────────────────────────────────────────────────┐
  │ Queries: Up to 50,000 queries                    │
  │ Users: ALL users (manasa, assessiq, demo, etc.) │
  │ Time Range: Last 180 days (including TODAY)      │
  └──────────────────────────────────────────────────┘

When you filter "Last 24 Hours":
  ┌──────────────────────────────────────────────────────┐
  │ Looking for: Queries from last 24 hours (from NOW)  │
  │ Found: Recent queries ✅                             │
  │ Reason: Data includes queries from TODAY             │
  └──────────────────────────────────────────────────────┘

User Insights:
  ┌──────────────────────────────────────────┐
  │ Users shown: ALL users                   │
  │ Includes: manasa, assessiq, demo, etc.   │
  │ Reason: 180-day window captures all users│
  └──────────────────────────────────────────┘
```

## Step-by-Step Fix

### Step 1: Open Assessments Page

```
Browser → http://localhost:3000/assessments
```

### Step 2: Create New Assessment

```
Click "Create Assessment" button

Fill in form:
┌─────────────────────────────────────────────────┐
│ Name: BigQuery Full Assessment - 180 Days      │
│ Source Connection: [Select BigQuery]           │
│ Target Connection: [Select Redshift]           │
└─────────────────────────────────────────────────┘

Click "Create"
```

### Step 3: Wait for Completion

```
Status: running → completed
⏱️  Wait time: 2-5 minutes (depending on data size)
```

### Step 4: View New Report

```
Click on new assessment → View report

Check tabs:
✅ Summary: Shows totals
✅ Query Insights: Time filters work
✅ User Insights: Shows ALL users
```

## What You'll See

### Before (OLD Assessment)

```
User Insights Tab:
┌────────────────────────────────────────────┐
│ User Email              │ Queries          │
├────────────────────────────────────────────┤
│ manasa.k@shellkode.com │ 1                │
└────────────────────────────────────────────┘

Query Insights → Last 24 Hours:
┌────────────────────────────────────────────┐
│ No query statistics found                  │
└────────────────────────────────────────────┘
```

### After (NEW Assessment)

```
User Insights Tab:
┌────────────────────────────────────────────────────────┐
│ User Email              │ Queries │ Data Scanned       │
├────────────────────────────────────────────────────────┤
│ manasa.k@shellkode.com │ 1,234   │ 45.2 GB           │
│ assessiq               │ 856     │ 32.1 GB           │
│ demo                   │ 423     │ 18.7 GB           │
│ service-account-1      │ 312     │ 12.4 GB           │
│ service-account-2      │ 189     │ 8.9 GB            │
└────────────────────────────────────────────────────────┘

Query Insights → Last 24 Hours:
┌────────────────────────────────────────────┐
│ Total Queries: 150                         │
│ Avg Execution Time: 2.5s                   │
│ Cache Hit Rate: 45.2%                      │
│                                            │
│ [Hourly Activity Chart with bars]          │
│                                            │
│ [Recent Queries Table with 50 rows]        │
└────────────────────────────────────────────┘
```

## Why This is Necessary

### Assessment Data is Static

```
┌─────────────────────────────────────────────────────────┐
│                                                          │
│  Assessment = Snapshot of BigQuery at a point in time   │
│                                                          │
│  When you run assessment:                               │
│  1. Backend queries BigQuery                            │
│  2. Captures data (queries, users, tables, etc.)        │
│  3. Stores in PostgreSQL database                       │
│  4. Data NEVER updates                                  │
│                                                          │
│  To get new data → Run new assessment                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Code vs Data

```
┌─────────────────────────────────────────────────────────┐
│ CODE (Already Fixed ✅)                                 │
├─────────────────────────────────────────────────────────┤
│ • Collects 180 days of queries                          │
│ • Collects up to 50,000 queries                         │
│ • Captures ALL users                                    │
│ • Returns all data to frontend                          │
│ • Frontend filters by time correctly                    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ DATA (Needs Update ❌)                                  │
├─────────────────────────────────────────────────────────┤
│ • Current assessment has OLD data                       │
│ • Captured with OLD code (7 days)                       │
│ • Only 1 user in that 7-day window                      │
│ • Data is 2-3 weeks old                                 │
│                                                          │
│ Solution: Run NEW assessment to get NEW data            │
└─────────────────────────────────────────────────────────┘
```

## FAQ

### Q: Can I update the existing assessment?
**A:** No. Assessment data is immutable. You must run a new assessment.

### Q: Will the new assessment replace the old one?
**A:** No. Both will exist. You can view either one.

### Q: How long does a new assessment take?
**A:** 2-5 minutes, depending on your BigQuery data size.

### Q: Will I lose the old assessment?
**A:** No. The old assessment remains in the database. You can delete it later if you want.

### Q: Why can't the system just update the data automatically?
**A:** Assessments are designed as point-in-time snapshots for comparison and historical tracking. Each assessment represents the state of your database at a specific moment.

### Q: Do I need to run assessments regularly?
**A:** Yes, if you want up-to-date insights. Consider running assessments:
- Weekly for active development
- Monthly for production monitoring
- Before/after major changes for comparison

## Verification

After running the new assessment, check:

```
✅ User Insights Tab
   └─ Shows multiple users (not just 1)

✅ Query Insights → Last 24 Hours
   └─ Shows recent queries (not empty)

✅ Query Insights → Hourly Activity Chart
   └─ Shows bars with query counts

✅ Recent Queries Table
   └─ Shows queries with recent timestamps
```

## Summary

```
┌─────────────────────────────────────────────────────────┐
│                                                          │
│  Problem: OLD assessment has OLD data                   │
│  Solution: Run NEW assessment to get NEW data           │
│                                                          │
│  Code: Already fixed ✅                                 │
│  Data: Needs new assessment 🎯                          │
│                                                          │
│  Action: Go to /assessments → Create Assessment         │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Need Help?

If after running a new assessment you still see issues:

1. Check assessment status is "completed"
2. Check backend logs for errors
3. Verify BigQuery connection is working
4. Confirm BigQuery has query history in INFORMATION_SCHEMA.JOBS

All backend and frontend code is already fixed and ready to capture comprehensive data! 🚀
