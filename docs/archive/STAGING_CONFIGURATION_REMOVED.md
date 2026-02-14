# Staging Configuration Removed from UI

## Overview
Removed the entire staging configuration section from the migration wizard UI, including all related components and state management.

## What Was Removed

### 1. Staging Configuration Section
The complete staging configuration UI that included:
- **Google Cloud Storage (Source Side)**
  - GCS Bucket Name input field
  - GCS Region dropdown
- **AWS S3 (Target Side)**
  - S3 Bucket Name input field
  - S3 Region dropdown
- **Cross-Cloud Access Credentials**
  - Service Account Key (JSON) file upload
  - File upload button and validation
- **Info boxes**
  - "Why staging buckets?" explanation
  - Conditional info message for non-BigQuery-Redshift migrations

### 2. Related Constants
Removed unused region constants:
```typescript
// REMOVED
const GCS_REGIONS = [...]
const S3_REGIONS = [...]
```

### 3. State Management
Removed staging-related state:
```typescript
// REMOVED
const [showStagingConfig, setShowStagingConfig] = useState(false);
```

### 4. Logic and Effects
Removed conditional logic for showing/hiding staging config:
```typescript
// REMOVED
useEffect(() => {
  // Show staging configuration when both BigQuery and Redshift are selected
  const sourceConn = connections.find(c => c.id === formData.sourceConnectionId);
  const targetConn = connections.find(c => c.id === formData.targetConnectionId);
  
  if (
    sourceConn?.database.toLowerCase() === 'bigquery' &&
    targetConn?.database.toLowerCase() === 'redshift'
  ) {
    setShowStagingConfig(true);
  } else {
    setShowStagingConfig(false);
  }
}, [formData.sourceConnectionId, formData.targetConnectionId, connections]);
```

### 5. File Upload Handler
Removed the file upload handler function:
```typescript
// REMOVED
const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
  // JSON file validation and upload logic
};
```

## Changes Made

### File: `frontend/src/components/migrations/steps/ConnectionStagingStep.tsx`

#### Before
- Component title: "Connection & Staging Configuration"
- Description: "Select source and target connections, and configure staging buckets"
- Showed staging configuration section when BigQuery → Redshift was selected
- Included GCS bucket, S3 bucket, and service account key fields
- Had conditional rendering based on connection types

#### After
- Component title: "Connection Configuration"
- Description: "Select source and target connections for your migration"
- Only shows connection selection (source and target)
- No staging configuration fields
- Cleaner, simpler UI focused on connection selection

## Remaining Functionality

The component still provides:
1. **Migration Name** - Text input for naming the migration
2. **Migration Type** - Dropdown to select BigQuery→Redshift or MongoDB→DocumentDB
3. **Source Connection** - Dropdown filtered by migration type
4. **Target Connection** - Dropdown filtered by migration type
5. **Connection Filtering** - Automatically filters connections based on selected migration type
6. **Validation** - Shows error messages if no connections are available

## UI Simplification

### Before (with staging config)
```
┌─────────────────────────────────────────┐
│ Connection & Staging Configuration      │
├─────────────────────────────────────────┤
│ Migration Name                          │
│ Migration Type                          │
│ Source Connection                       │
│ Target Connection                       │
│                                         │
│ ┌─ Staging Configuration ─────────────┐│
│ │ GCS Bucket Name                     ││
│ │ GCS Region                          ││
│ │ S3 Bucket Name                      ││
│ │ S3 Region                           ││
│ │ Service Account Key Upload          ││
│ │ [Why staging buckets? info box]    ││
│ └─────────────────────────────────────┘│
└─────────────────────────────────────────┘
```

### After (staging removed)
```
┌─────────────────────────────────────────┐
│ Connection Configuration                │
├─────────────────────────────────────────┤
│ Migration Name                          │
│ Migration Type                          │
│ Source Connection                       │
│ Target Connection                       │
└─────────────────────────────────────────┘
```

## Benefits

1. **Simpler UI** - Reduced complexity and cognitive load
2. **Faster Setup** - Fewer fields to fill out
3. **Cleaner Code** - Removed ~150 lines of code
4. **Better Focus** - Users focus on essential connection configuration
5. **Easier Maintenance** - Less code to maintain and test

## Backend Considerations

The staging configuration fields were only used in the frontend form. The backend migration logic may still need staging buckets for BigQuery→Redshift migrations, but this will be handled:
- **Automatically** - Backend determines staging requirements
- **From Connection Metadata** - Staging info stored in connection parameters
- **Via Configuration** - Backend configuration files or environment variables

## Migration Wizard Flow

The wizard now has a cleaner flow:

1. **Strategy Selection** - Choose migration pathway (A, B, C, D)
2. **Connection Configuration** - Select source and target connections (THIS STEP)
3. **Metadata Discovery** - Discover and select tables/datasets
4. **Configuration Setup** - Configure transfer options and settings
5. **Schedule & Monitor** - Set up scheduling and monitoring

## Testing Checklist

- [x] Component renders without errors
- [x] Migration name input works
- [x] Migration type dropdown works
- [x] Source connection dropdown filters correctly
- [x] Target connection dropdown filters correctly
- [x] No console errors related to removed state
- [x] No references to removed constants
- [x] Step navigation works correctly
- [x] Form data updates correctly

## Files Modified

1. **frontend/src/components/migrations/steps/ConnectionStagingStep.tsx**
   - Removed `GCS_REGIONS` constant
   - Removed `S3_REGIONS` constant
   - Removed `showStagingConfig` state
   - Removed staging config useEffect
   - Removed `handleFileUpload` function
   - Removed entire staging configuration JSX section
   - Updated component title and description
   - Simplified component structure

## Status
✅ **COMPLETE** - Staging configuration section successfully removed from the UI.

## Notes

- The removal is clean with no orphaned code or unused imports
- All TypeScript compilation passes without errors
- Component is now more focused and easier to understand
- If staging configuration is needed in the future, it can be re-added as a separate optional step or handled automatically by the backend
