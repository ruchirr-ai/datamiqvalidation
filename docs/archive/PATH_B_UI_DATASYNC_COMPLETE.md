# Path B UI Updated to AWS DataSync - Complete

## Summary
Updated the frontend UI for Path B to show AWS DataSync configuration instead of AWS SCT (Schema Conversion Tool). The UI now matches the backend implementation that uses AWS DataSync for GCS to S3 transfer.

## Changes Made

### 1. ConfigurationSetupStep.tsx
**File**: `frontend/src/components/migrations/steps/ConfigurationSetupStep.tsx`

**Updated `renderGCSToS3_PathB()` function**:
- Changed title from "Direct Migration Setup" to "GCS → S3 Transfer"
- Changed description from "Configure AWS Schema Conversion Tool" to "Configure AWS DataSync for automated data transfer"
- Replaced SCT info box with AWS DataSync info box
- Removed SCT toggle options (Auto-Convert Schema, Generate Assessment Report, Optimize for Redshift)
- Added AWS DataSync configuration fields:
  * **AWS Infrastructure Configuration**:
    - VPC Subnet ID (required)
    - Security Group ID (required)
    - EC2 Instance Type (dropdown: m5.large, m5.xlarge, m5.2xlarge, m5.4xlarge)
  * **GCS HMAC Credentials**:
    - GCS HMAC Access Key (required)
    - GCS HMAC Secret Key (required, password field)
  * **S3 Destination**:
    - S3 Bucket Name (required)
    - S3 Path (required)

### 2. CreateMigrationWizard.tsx
**File**: `frontend/src/components/migrations/CreateMigrationWizard.tsx`

**Updated MigrationFormData interface**:
- Removed SCT fields:
  * `sctEndpoint`
  * `sctProjectName`
  * `extractionAgentEndpoint`
  * `autoConvertSchema`
  * `generateAssessment`
  * `optimizeForRedshift`
- Added DataSync fields:
  * `datasyncSubnetId` - VPC subnet for agent deployment
  * `datasyncSecurityGroupId` - Security group for agent
  * `datasyncInstanceType` - EC2 instance type (default: m5.xlarge)
  * `gcsAccessKey` - GCS HMAC access key
  * `gcsSecretKey` - GCS HMAC secret key

**Updated `performSave()` function**:
- Added DataSync parameters to API request:
  * `datasync_subnet_id`
  * `datasync_security_group_id`
  * `datasync_instance_type`
  * `gcs_access_key`
  * `gcs_secret_key`

## Required AWS DataSync Parameters

### Infrastructure (AWS)
1. **VPC Subnet ID**: Private subnet where DataSync agent EC2 instance will be deployed
2. **Security Group ID**: Security group for the agent (must allow HTTPS outbound to AWS services and GCS)
3. **EC2 Instance Type**: Instance size for the agent (m5.xlarge recommended for most workloads)

### GCS Access (Google Cloud)
4. **GCS HMAC Access Key**: HMAC access key ID for GCS bucket access
5. **GCS HMAC Secret Key**: HMAC secret key for GCS bucket access

### S3 Destination (AWS)
6. **S3 Bucket Name**: Target S3 bucket for data transfer
7. **S3 Path**: Path within S3 bucket

## How AWS DataSync Works (Path B)

### Architecture
```
BigQuery → GCS → [DataSync Agent EC2] → S3 → Redshift
```

### Process Flow
1. **Agent Deployment**: EC2 instance deployed in private subnet with DataSync AMI
2. **Agent Activation**: Agent activated via local network call to get activation key
3. **Source Location**: GCS bucket configured as source using HMAC credentials
4. **Destination Location**: S3 bucket configured as destination
5. **Sync Task**: DataSync task created with CHANGED transfer mode (delta sync)
6. **Execution**: Task executed with automatic retry on failure
7. **Load to Redshift**: Uses PathwayC's load stage (S3 → Redshift via COPY command)

### Key Features
- **Automatic Retry**: Built-in retry logic with exponential backoff
- **Delta Sync**: Only transfers changed/new files (TransferMode='CHANGED')
- **Failure Recovery**: Resumes from last checkpoint on failure
- **Monitoring**: Real-time progress tracking (files transferred, bytes transferred)

## Backend Integration

The backend PathwayB implementation (`backend/services/bq_redshift_migration/pathway_b.py`) expects these parameters in `storage_config`:

```python
storage_config = {
    'gcs_bucket': 'my-gcs-bucket',
    'gcs_path': 'exports/bigquery',
    's3_bucket': 'my-s3-bucket',
    's3_path': 'migrations/bq-to-redshift',
    'aws_region': 'us-east-1',
    'datasync_subnet_id': 'subnet-0123456789abcdef0',
    'datasync_security_group_id': 'sg-0123456789abcdef0',
    'datasync_instance_type': 'm5.xlarge',
    'gcs_access_key': 'GOOG1E...',
    'gcs_secret_key': 'secret_key_here'
}
```

## UI/UX Improvements

### Visual Design
- **Info Box**: Orange/gold color scheme to distinguish from Path A (blue) and Path C (default)
- **Clear Sections**: Organized into 3 logical sections (Infrastructure, GCS Credentials, S3 Destination)
- **Help Text**: Descriptive help text for each field explaining purpose and format
- **Required Fields**: All critical fields marked as required with asterisk

### Field Validation
- Subnet ID format: `subnet-*`
- Security Group ID format: `sg-*`
- Instance type: Dropdown with recommended option highlighted
- Password field for GCS secret key (masked input)

## Testing Checklist

### UI Testing
- [ ] Path B shows AWS DataSync configuration (not SCT)
- [ ] All required fields are marked with asterisk
- [ ] Help text is clear and informative
- [ ] Instance type dropdown shows all options
- [ ] Password field masks GCS secret key
- [ ] Save & Continue button works correctly
- [ ] Form data persists when navigating between steps

### Integration Testing
- [ ] Form data correctly sent to backend API
- [ ] DataSync parameters included in migration creation request
- [ ] Edit mode loads existing DataSync configuration
- [ ] Validation errors displayed for missing required fields

### End-to-End Testing
- [ ] Create new migration with Path B
- [ ] Fill in all DataSync configuration fields
- [ ] Save and verify migration created in database
- [ ] Execute migration and verify DataSync agent deployment
- [ ] Verify data transfer from GCS to S3
- [ ] Verify data load from S3 to Redshift

## Documentation Updates Needed

### User Documentation
- Update migration pathway comparison table
- Add AWS DataSync setup guide
- Document GCS HMAC key generation process
- Document AWS infrastructure prerequisites (VPC, subnet, security group)
- Add troubleshooting guide for DataSync issues

### Developer Documentation
- Update API documentation with DataSync parameters
- Document DataSync agent lifecycle
- Add architecture diagrams for Path B
- Document error handling and retry logic

## AWS Prerequisites

### Required AWS Resources
1. **VPC**: Virtual Private Cloud with private subnet
2. **Subnet**: Private subnet with NAT Gateway for internet access
3. **Security Group**: 
   - Outbound HTTPS (443) to AWS services
   - Outbound HTTPS (443) to storage.googleapis.com
4. **IAM Role**: DataSync S3 access role with permissions:
   - `s3:GetObject`
   - `s3:PutObject`
   - `s3:ListBucket`
   - `s3:DeleteObject`

### GCS Prerequisites
1. **HMAC Keys**: Generate in Google Cloud Console
   - Navigate to: Cloud Storage → Settings → Interoperability
   - Click "Create a key for a service account"
   - Save Access Key ID and Secret

## Status

✅ **COMPLETE**: Frontend UI updated to show AWS DataSync configuration for Path B
✅ **COMPLETE**: Backend implementation supports AWS DataSync
✅ **COMPLETE**: Form data structure updated with DataSync parameters
✅ **COMPLETE**: API integration updated to send DataSync parameters

## Next Steps

1. **Test the UI**: Create a new migration with Path B and verify all fields display correctly
2. **Test Integration**: Verify form data is correctly sent to backend API
3. **Test End-to-End**: Execute a complete Path B migration with real AWS infrastructure
4. **Update Documentation**: Add user guide for AWS DataSync setup
5. **Add Validation**: Implement client-side validation for AWS resource IDs

## Related Files

- `frontend/src/components/migrations/steps/ConfigurationSetupStep.tsx` - UI component
- `frontend/src/components/migrations/CreateMigrationWizard.tsx` - Form data management
- `backend/services/bq_redshift_migration/pathway_b.py` - Backend implementation
- `PATH_B_AWS_DATASYNC_CONFIGURATION.md` - DataSync configuration guide
- `PATH_B_DATASYNC_INTEGRATION_COMPLETE.md` - Backend integration details
