# BigQuery Connection Setup Guide

## ✅ Issue Fixed

The Service Account JSON textarea field is now visible in the Create Connection modal!

## 📝 What Was Fixed

1. **Added textarea support** to the `DynamicField` component
2. **Added CSS styles** for textarea fields with proper formatting
3. **Updated layout logic** to make textarea fields span full width
4. **Auto-reloaded** via Vite HMR - no server restart needed

## 🔧 Creating a BigQuery Connection

### Step 1: Open Create Connection Modal
1. Navigate to http://localhost:3000
2. Login with admin/AdminPass123!
3. Go to Connections page
4. Click "Create Connection"
5. Select "Source" or "Target" connection type

### Step 2: Fill in BigQuery Details

You should now see these fields:

1. **Connection Name** (required)
   - Example: "Production BigQuery"

2. **Data Source** (required)
   - Select "BigQuery" from dropdown

3. **Project ID** (required)
   - Your Google Cloud project ID
   - Example: "my-gcp-project"

4. **Dataset** (required)
   - BigQuery dataset name
   - Example: "my_dataset"

5. **Service Account JSON** (required) ⭐ NOW VISIBLE
   - Large textarea field for pasting JSON
   - Paste your complete service account key JSON
   - Uses monospace font for better readability

6. **Location** (optional)
   - BigQuery region
   - Default: "US"
   - Examples: "US", "EU", "asia-northeast1"

### Step 3: Get Service Account JSON

If you don't have a service account key yet:

1. Go to Google Cloud Console
2. Navigate to IAM & Admin > Service Accounts
3. Create a new service account or select existing one
4. Grant these permissions:
   - BigQuery Data Viewer
   - BigQuery Job User
   - BigQuery Metadata Viewer (for schema discovery)
5. Create a JSON key
6. Download the JSON file
7. Copy the entire JSON content

### Step 4: Test and Create Connection

1. Paste the service account JSON into the textarea
2. Click "Test Connection" button
3. Wait for success message (green toast notification)
4. Click "Create Connection" button

## 📋 Sample Service Account JSON Structure

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "abc123...",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----\n",
  "client_email": "service-account@project.iam.gserviceaccount.com",
  "client_id": "123456789",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/..."
}
```

## ✅ Required Fields in Service Account JSON

The backend validates these fields:
- `type` (must be "service_account")
- `project_id`
- `private_key_id`
- `private_key`
- `client_email`

## 🔍 Troubleshooting

### If textarea is still not visible:
1. Hard refresh the browser (Ctrl+Shift+R or Cmd+Shift+R)
2. Clear browser cache
3. Check browser console for errors

### If test connection fails:
- Verify the JSON is valid (no syntax errors)
- Check that all required fields are present
- Ensure service account has proper permissions
- Verify project ID matches the one in service account JSON
- Check that BigQuery API is enabled in your GCP project

### Common Error Messages:

**"Service Account Key is required"**
- The textarea is empty or contains invalid JSON

**"Service account JSON is missing required fields"**
- The JSON is missing one of: type, project_id, private_key_id, private_key, client_email

**"Connection failed: 403 Forbidden"**
- Service account doesn't have proper BigQuery permissions

**"Connection failed: Invalid project ID"**
- Project ID doesn't exist or service account doesn't have access

## 🎨 UI Features

The textarea field now has:
- ✅ Monospace font for better JSON readability
- ✅ Resizable (drag bottom-right corner)
- ✅ Minimum height of 120px
- ✅ Full width layout (spans both columns)
- ✅ Proper focus states with blue border
- ✅ Error states with red border
- ✅ Help text below the field
- ✅ Required field indicator (*)

## 🚀 Next Steps

After creating your BigQuery connection:
1. Create a Redshift target connection (if migrating to Redshift)
2. Run an Assessment to analyze your BigQuery data
3. Use the Migration Wizard to migrate data

## 📚 Related Documentation

- Main Setup Guide: `SETUP_COMPLETE.md`
- Architecture: `ARCHITECTURE.md`
- Deployment Guide: `DEPLOYMENT_GUIDE.md`
