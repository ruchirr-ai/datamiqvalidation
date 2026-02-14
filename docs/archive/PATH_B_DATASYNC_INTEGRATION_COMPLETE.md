# Path B: AWS DataSync Integration - Complete ✅

## Summary

Path B has been successfully updated to use **AWS DataSync** for transferring data from Google Cloud Storage (GCS) to Amazon S3. Path C remains unchanged and continues to use GCP Storage Transfer Service.

---

## What Changed

### PathwayB Class (`backend/services/bq_redshift_migration/pathway_b.py`)

#### Before
- Used simplified approach that delegated to PathwayC
- No AWS DataSync integration
- Same transfer method as Path C

#### After
- ✅ Uses AWS DataSync for GCS → S3 transfer
- ✅ Automated EC2 agent deployment
- ✅ GCS source location with HMAC credentials
- ✅ S3 destination location with IAM role
- ✅ Delta sync with CHANGED transfer mode
- ✅ Automatic retry on failure (up to 3 attempts)
- ✅ Real-time progress monitoring
- ✅ Reuses PathwayC's `_execute_load_stage` for S3 → Redshift

---

## Migration Flow

### Path B (AWS DataSync)
```
BigQuery → GCS → AWS DataSync → S3 → Redshift
```

**Stages**:
1. **Export**: BigQuery tables to GCS (handled by orchestrator)
2. **Transfer**: GCS to S3 using AWS DataSync (NEW)
3. **Load**: S3 to Redshift using RedshiftLoader (reused from PathwayC)

### Path C (GCP Storage Transfer Service) - UNCHANGED
```
BigQuery → GCS → GCP Storage Transfer → S3 → Redshift
```

**Stages**:
1. **Export**: BigQuery tables to GCS
2. **Transfer**: GCS to S3 using GCP Storage Transfer Service
3. **Load**: S3 to Redshift using RedshiftLoader

---

## Key Features

### AWS DataSync Implementation

1. **Automated Agent Deployment**
   - Retrieves latest DataSync AMI from SSM Parameter Store
   - Deploys EC2 instance in private subnet
   - Waits for agent initialization
   - Retrieves activation key via HTTP

2. **GCS Source Location**
   - Connects to GCS using HMAC access/secret keys
   - Supports subdirectory paths
   - Uses HTTPS protocol (port 443)

3. **S3 Destination Location**
   - Uses IAM role for S3 access
   - Supports subdirectory paths
   - Configurable storage class

4. **Sync Task Configuration**
   - **Transfer Mode**: CHANGED (delta sync)
   - **Verify Mode**: ONLY_FILES_TRANSFERRED
   - **Overwrite Mode**: ALWAYS
   - **Preserve**: Mtime (modification time)
   - **Bandwidth**: Unlimited (-1)

5. **Automatic Retry**
   - Up to 3 retry attempts
   - Exponential backoff (60s, 120s, 180s)
   - Delta sync on retry (only transfers remaining files)

6. **Monitoring**
   - Real-time progress tracking
   - Files transferred count
   - Bytes transferred count
   - Task execution status

---

## Required Configuration Parameters

### New Parameters for Path B

```python
storage_config = {
    # Existing parameters
    'gcs_bucket': 'your-gcs-bucket',
    'gcs_path': 'path/to/data',
    's3_bucket': 'your-s3-bucket',
    's3_path': 'path/to/data',
    'aws_region': 'us-east-1',
    
    # NEW: AWS DataSync parameters
    'datasync_subnet_id': 'subnet-xxxxx',           # REQUIRED
    'datasync_security_group_id': 'sg-xxxxx',       # REQUIRED
    'datasync_instance_type': 'm5.xlarge',          # OPTIONAL (default: m5.xlarge)
    'datasync_key_name': 'your-key-pair',           # OPTIONAL
    
    # NEW: GCS HMAC credentials
    'gcs_access_key': 'GOOG1E...',                  # REQUIRED
    'gcs_secret_key': 'your-secret-key',            # REQUIRED
}
```

### Parameter Details

| Parameter | Required | Description |
|-----------|----------|-------------|
| `datasync_subnet_id` | ✅ Yes | Private subnet ID for DataSync agent |
| `datasync_security_group_id` | ✅ Yes | Security group for agent instance |
| `datasync_instance_type` | ❌ No | EC2 instance type (default: m5.xlarge) |
| `datasync_key_name` | ❌ No | SSH key pair for agent access |
| `gcs_access_key` | ✅ Yes | GCS HMAC access key |
| `gcs_secret_key` | ✅ Yes | GCS HMAC secret key |

---

## AWS Infrastructure Requirements

### 1. VPC and Networking
- Private subnet with NAT Gateway for internet access
- Route to AWS DataSync service endpoints
- Route to storage.googleapis.com (GCS)

### 2. Security Group
- **Outbound**:
  - HTTPS (443) to storage.googleapis.com
  - HTTPS (443) to AWS DataSync endpoints
  - HTTPS (443) to S3 endpoints
- **Inbound**:
  - HTTP (80) from VPC (for agent activation)

### 3. IAM Role
- Role name: `DataSyncS3AccessRole`
- Trust policy: Allow datasync.amazonaws.com
- Permissions: S3 read/write access

### 4. GCS HMAC Keys
- Created in GCS Console → Settings → Interoperability
- Service account with Storage Object Viewer role
- Access key starts with `GOOG1E`

---

## Code Changes

### File Modified
`backend/services/bq_redshift_migration/pathway_b.py`

### Methods Updated

#### 1. `execute()` Method
- Now implements full Path B flow with AWS DataSync
- Checks checkpoints to determine which stage to execute
- Calls `_execute_transfer_stage_datasync()` for transfer
- Reuses PathwayC's `_execute_load_stage()` for load

#### 2. `_execute_transfer_stage_datasync()` Method (NEW)
- Extracts and validates configuration parameters
- Constructs S3 bucket ARN
- Calls `execute_pathway_b_migration()` function
- Handles success/failure with detailed logging

### Existing DataSync Implementation
The `PathwayBDataSync` class was already implemented with:
- Agent deployment
- Activation
- Location creation
- Task creation and execution
- Monitoring
- Retry logic
- Cleanup

---

## Usage Example

### Create Migration with Path B

```python
from models.bq_redshift_migration import MigrationBQRedshift

migration = MigrationBQRedshift(
    migration_name="bq_to_redshift_datasync",
    pathway="B",  # Use Path B for AWS DataSync
    
    # Source
    source_project_id="my-gcp-project",
    source_dataset="my_dataset",
    source_tables=["table1", "table2"],
    
    # Target
    target_connection_id=7,
    
    # Storage
    gcs_bucket="my-gcs-bucket",
    gcs_path="exports",
    s3_bucket="my-s3-bucket",
    s3_path="imports",
    
    # IAM Role
    iam_role_arn="arn:aws:iam::123456789012:role/RedshiftS3AccessRole",
    
    # AWS Credentials
    aws_access_key_id="AKIA...",
    aws_secret_access_key_encrypted="encrypted-secret"
)
```

### Configure DataSync Parameters

These should be added to the orchestrator's `storage_config`:

```python
storage_config = {
    # ... existing config ...
    'datasync_subnet_id': os.getenv('DATASYNC_SUBNET_ID'),
    'datasync_security_group_id': os.getenv('DATASYNC_SECURITY_GROUP_ID'),
    'datasync_instance_type': 'm5.xlarge',
    'gcs_access_key': os.getenv('GCS_ACCESS_KEY'),
    'gcs_secret_key': os.getenv('GCS_SECRET_KEY'),
}
```

---

## Comparison: Path B vs Path C

| Aspect | Path B (AWS DataSync) | Path C (GCP Storage Transfer) |
|--------|----------------------|-------------------------------|
| **Transfer Service** | AWS DataSync | GCP Storage Transfer Service |
| **Infrastructure** | EC2 agent required | No additional infrastructure |
| **Setup** | VPC, subnet, security group, IAM | API-based, simpler setup |
| **Authentication** | GCS HMAC keys | GCP service account |
| **Delta Sync** | CHANGED mode | Built-in |
| **Retry** | Automatic (3 attempts) | Automatic |
| **Monitoring** | CloudWatch + DataSync console | Application logs |
| **Cost** | DataSync + EC2 + transfer | Transfer only |
| **Best For** | Enterprise, large datasets | Simple migrations, smaller datasets |
| **Load Stage** | Reuses PathwayC | Native implementation |

---

## Error Handling

### Validation Errors
- Missing `datasync_subnet_id` → Clear error message
- Missing `datasync_security_group_id` → Clear error message
- Missing GCS HMAC credentials → Clear error message

### Transfer Errors
- Agent deployment failure → Exception with details
- Activation failure → Exception with details
- Location creation failure → Exception with details
- Task execution failure → Automatic retry (up to 3 times)

### Logging
- Detailed logs at each step
- Progress tracking during transfer
- Success/failure summary with metrics

---

## Testing

### Test Script Available
`backend/test_datasync_path_b.py` - Tests AWS DataSync integration

### Manual Testing Steps
1. Set up AWS infrastructure (VPC, subnet, security group, IAM role)
2. Create GCS HMAC keys
3. Configure environment variables
4. Create migration with pathway="B"
5. Start migration
6. Monitor DataSync console and logs
7. Verify data in S3
8. Verify data loaded to Redshift

---

## Documentation

### Files Created
1. **PATH_B_AWS_DATASYNC_CONFIGURATION.md** - Complete configuration guide
   - AWS infrastructure setup
   - Parameter details
   - GCS HMAC key creation
   - Troubleshooting
   - Cost considerations

2. **PATH_B_DATASYNC_INTEGRATION_COMPLETE.md** - This file
   - Summary of changes
   - Usage examples
   - Comparison with Path C

### Existing Documentation
- **PATH_B_DATASYNC_IMPLEMENTATION_COMPLETE.md** - Original DataSync implementation
- **backend/services/bq_redshift_migration/aws_datasync_manager.py** - DataSync manager class

---

## Status: ✅ COMPLETE

Path B has been successfully updated to use AWS DataSync for GCS to S3 transfer:

- ✅ PathwayB.execute() method updated
- ✅ _execute_transfer_stage_datasync() method added
- ✅ Reuses PathwayC load stage
- ✅ Comprehensive error handling
- ✅ Detailed logging
- ✅ Automatic retry logic
- ✅ Configuration validation
- ✅ Documentation complete

**Path C remains unchanged** and continues to work as before with GCP Storage Transfer Service.

---

## Next Steps

1. **Update Orchestrator** (if needed)
   - Add DataSync parameters to storage_config
   - Pass GCS HMAC credentials securely

2. **Update Migration Model** (optional)
   - Add fields for DataSync configuration
   - Add fields for GCS HMAC credentials

3. **Update UI** (optional)
   - Add DataSync configuration fields for Path B
   - Show DataSync-specific status and progress

4. **Test End-to-End**
   - Create test migration with Path B
   - Verify AWS DataSync transfer
   - Verify data loaded to Redshift

5. **Monitor and Optimize**
   - Review CloudWatch logs
   - Optimize instance type based on dataset size
   - Adjust retry logic if needed
