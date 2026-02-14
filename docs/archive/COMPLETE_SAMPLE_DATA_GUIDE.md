# Complete Sample Data Guide - BigQuery to Redshift Migration

## ✅ All Sample Data Added

Sample/dummy data has been added to all components to enable complete end-to-end testing of the BigQuery to Redshift migration flow.

## 📊 Sample Data Overview

### 1. Connections (6 Sample Connections)

**Source Connections:**
1. **Production BigQuery** - Connected ✅
2. **Dev BigQuery** - Connected ✅
3. **Analytics MongoDB** - Connected ✅

**Target Connections:**
1. **Production Redshift** - Connected ✅
2. **Staging Redshift** - Connected ✅
3. **Staging PostgreSQL** - Disconnected ❌

### 2. Migrations (7 Sample Migrations)

1. Customer Data Migration Q1 2026 - Completed ✅
2. Analytics Tables - Daily Sync - Running 🔄
3. Historical Data Archive - Failed ❌
4. Marketing Campaign Data - Pending ⏳
5. Sales Reports Migration - Completed ✅
6. User Activity Logs - Completed ✅
7. Product Catalog Sync - Running 🔄

### 3. BigQuery Metadata (3 Datasets, 12 Tables)

**Dataset: analytics** (5 tables)
- customers: 1.25M rows, 450 MB
- orders: 5.8M rows, 2.1 GB
- products: 45K rows, 15 MB
- user_activity: 12.5M rows, 3.2 GB
- sessions: 8.9M rows, 1.8 GB

**Dataset: sales** (3 tables)
- revenue: 890K rows, 280 MB
- invoices: 1.2M rows, 450 MB
- payments: 1.15M rows, 380 MB

**Dataset: marketing** (4 tables)
- campaigns: 50K rows, 12 MB
- email_metrics: 2.5M rows, 680 MB
- ad_performance: 1.8M rows, 520 MB
- conversions: 450K rows, 125 MB

## 🎯 Complete Testing Flow

### Step-by-Step Testing Guide

#### 1. View Connections Page
```
Navigate to: /connections
```
**What you'll see:**
- 6 sample connections in the table
- Different database types (BigQuery, Redshift, MongoDB, PostgreSQL)
- Different statuses (Connected, Disconnected, Testing)
- Three-dots menu with icons on each row

**Actions to test:**
- Click three-dots on any connection
- See: Test Connection, Update Connection, Delete Connection (all with icons)
- Try search functionality
- Try pagination

---

#### 2. View Migrations Page
```
Navigate to: /migrations
```
**What you'll see:**
- 7 sample migrations in the table
- Different statuses (Completed, Running, Failed, Pending)
- Source and destination connections
- Created by different users
- Last run timestamps

**Actions to test:**
- Click three-dots on any migration
- See: Test Migration, Update Migration, Delete Migration (all with icons)
- Try search functionality
- Try pagination

---

#### 3. Start Create Migration Wizard
```
Click: + New → Create
Navigate to: /migrations/create
```
**What you'll see:**
- Wizard header: "Setup Data Migration"
- Progress indicator showing 4 steps
- Step 1: Connection & Staging Configuration

---

#### 4. Step 1: Connection & Staging Configuration

**Form Fields:**
1. **Migration Name**: Enter "Test Migration Q1 2026"

2. **Source Connection**: 
   - Dropdown shows: Production BigQuery, Dev BigQuery, Analytics MongoDB
   - Select: **Production BigQuery**

3. **Target Connection**:
   - Dropdown shows: Production Redshift, Staging Redshift, Staging PostgreSQL
   - Select: **Production Redshift**

4. **GCS Staging Bucket**:
   - Bucket Name: `my-migration-staging`
   - Region: `us-central1`

5. **S3 Staging Bucket**:
   - Bucket Name: `my-redshift-staging`
   - Region: `us-east-1`

6. **Service Account JSON**: (Optional for testing)
   - Can skip or paste dummy JSON

**Click "Next"** to proceed to Step 2

---

#### 5. Step 2: Source Metadata Discovery

**What you'll see:**
- "Discover Metadata" button
- Empty state initially

**Actions:**
1. Click **"Discover Metadata"** button
2. Loading state appears briefly
3. Sample metadata loads (even if backend is down)
4. Tree view displays:

```
📁 analytics (5 tables)
  ☐ customers - 1.25M rows, 450 MB
  ☐ orders - 5.8M rows, 2.1 GB
  ☐ products - 45K rows, 15 MB
  ☐ user_activity - 12.5M rows, 3.2 GB
  ☐ sessions - 8.9M rows, 1.8 GB

📁 sales (3 tables)
  ☐ invoices - 1.2M rows, 450 MB
  ☐ payments - 1.15M rows, 380 MB
  ☐ revenue - 890K rows, 280 MB

📁 marketing (4 tables)
  ☐ ad_performance - 1.8M rows, 520 MB
  ☐ campaigns - 50K rows, 12 MB
  ☐ conversions - 450K rows, 125 MB
  ☐ email_metrics - 2.5M rows, 680 MB
```

**Actions to test:**
- Click dataset name to expand/collapse
- Check individual tables
- Check entire dataset (selects all tables)
- Use "Select All" toggle
- See selection count update

**Select some tables** (e.g., customers, orders, products)

**Click "Next"** to proceed to Step 3

---

#### 6. Step 3: Migration Strategy Selection

**What you'll see:**
- 4 strategy cards:

**Pathway A: GCP Native**
- Tag: "Recommended for 100TB+"
- Uses Storage Transfer Service
- Best for large-scale migrations

**Pathway B: AWS Native**
- Tag: "Recommended for Schema-heavy"
- Uses AWS Schema Conversion Tool
- Best for complex schemas

**Pathway C: Hybrid Sync**
- Tag: "Recommended for Continuous Sync"
- Uses AWS DataSync
- Best for ongoing synchronization

**Pathway D: CLI Orchestration**
- Tag: "Legacy / Small scale"
- Uses gsutil and aws-cli
- Best for small migrations

**Summary Sidebar:**
- Shows selected table count
- Shows total data size
- Shows recommended pathway

**Select Pathway A** (or any pathway)

**Click "Next"** to proceed to Step 4

---

#### 7. Step 4: Scheduling & Monitoring

**Form Fields:**

1. **Execution Type**:
   - ⚪ Run Now (default)
   - ⚪ Scheduled

2. **Schedule** (if Scheduled selected):
   - CRON Expression: `0 2 * * *`
   - Description: "Daily at 2 AM UTC"

3. **Notifications**:
   - ☑️ Email: `user@company.com`
   - ☑️ Slack: `#data-migrations`
   - ☐ Webhook: `https://...`

4. **Error Handling**:
   - Retry Count: `3`
   - Retry Delay: `5 minutes`
   - On Failure: `Pause and notify`

**Fill in the form** with your preferences

**Click "Create Migration"** to finish

---

#### 8. Post-Creation

**What happens:**
- Migration is created (if backend is running)
- Success message appears
- Redirected back to migrations list
- New migration appears in table

**If backend is not running:**
- Error message appears
- Can still see the form data was valid
- Can retry when backend is available

---

## 🔍 What Works Without Backend

✅ **Fully Functional (No Backend Required):**
- View Connections page with sample data
- View Migrations page with sample data
- Navigate through all 4 wizard steps
- See sample connections in dropdowns
- See sample BigQuery metadata
- Select tables and datasets
- Choose migration strategy
- Fill in scheduling form
- Form validation

❌ **Requires Backend:**
- Creating actual migration (POST /api/migrations/bq-redshift/create)
- Fetching real BigQuery metadata (if you have real credentials)
- Starting migration execution
- Real-time progress tracking
- Validation

---

## 🎨 UI Components Verified

All UI components are now visible and testable:

✅ **Navigation & Layout:**
- Sidebar navigation
- Page headers with icons
- Search boxes
- Pagination controls

✅ **Tables:**
- Data tables with sorting
- Status badges (colored)
- User avatars
- Database icons
- Three-dots menus with icons

✅ **Forms:**
- Text inputs
- Dropdowns/selects
- Checkboxes
- Radio buttons
- File upload
- CRON expression input

✅ **Wizard:**
- Progress indicator
- Step navigation
- Form validation
- Next/Back buttons

✅ **Tree View:**
- Expandable datasets
- Selectable tables
- Checkbox states
- Metadata display

✅ **Strategy Cards:**
- Card layout
- Tags/badges
- Descriptions
- Selection state

✅ **Menus:**
- Dropdown menus
- Icons in menu items
- Dividers
- Hover states
- Danger items (red)

---

## 📝 Sample Data Summary

**Total Sample Records:**
- 6 Connections
- 7 Migrations
- 3 BigQuery Datasets
- 12 BigQuery Tables
- ~35M total rows
- ~10 GB total data size

**All data is realistic and production-like** to give you a true sense of how the application will look and behave with real data.

---

## 🚀 Next Steps

Now that you have complete sample data, you can:

1. **Test the entire UI flow** without needing backend
2. **Show to stakeholders** for feedback
3. **Identify UI improvements** needed
4. **Test with real backend** when ready
5. **Add more sample scenarios** if needed

---

## 💡 Tips for Testing

1. **Hard refresh browser** (Cmd+Shift+R) to see changes
2. **Open browser console** to see any errors
3. **Try different selections** in the wizard
4. **Test all menu actions** (three-dots)
5. **Try search and pagination**
6. **Test on different screen sizes**

---

## ✨ What's Great About This Setup

1. **No backend dependency** for UI testing
2. **Realistic data** that looks production-ready
3. **Complete flow** from start to finish
4. **All UI components** are visible
5. **Easy to demo** to stakeholders
6. **Fast iteration** on UI improvements

The UI is now fully testable and looks professional! 🎉
