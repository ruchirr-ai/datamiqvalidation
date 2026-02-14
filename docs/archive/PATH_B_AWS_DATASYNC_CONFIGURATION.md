# Path B: AWS DataSync Configuration Guide

## Overview

Path B now uses **AWS DataSync** for transferring data from Google Cloud Storage (GCS) to Amazon S3. This provides enterprise-grade, managed data transfer with automatic retry, delta sync, and monitoring capabilities.

## Migration Flow

```
BigQuery → GCS → AWS DataSync → S3 → Redshift
```

### Stages
1. **Export**: BigQuery tables exported to GCS (PARQUET format)
2. **Transfer**: GCS to S3 using AWS DataSync
3. **Load**: S3 to Redshift using COPY command

---

## AWS DataSync Architecture

### Components

1. **DataSync Agent** (EC2 Instance)
   - Deployed in private subnet
   - Connects to GCS using HMAC credentials
   - Transfers data to S3

2. **Source Location** (GCS)
   - GCS bucket configured as object storage
   - Uses HMAC access/secret keys
   - Supports subdirectory paths

3. **Destination Location** (S3)
   - S3 bucket with IAM role access
   - Supports subdirectory paths
   - Configurable storage class

4. **Sync Task**
   - Transfer mode: CHANGED (delta sync)
   - Automatic retry on failure
   - Progress monitoring

---

## Required Configuration Parameters

### AWS Infrastructure

Add these parameters to your migration configuration:

```python
storage_config = {
    # Existing parameters
    'gcs_bucket': 'your-gcs-bucket',
    'gcs_path': 'path/to/data',
    's3_bucket': 'your-s3-bucket',
    's3_path': 'path/to/data',
    'aws_region': 'us-east-1',
    
    # NEW: AWS DataSync parameters
    'datasync_subnet_id': 'subnet-xxxxx',           # REQUIRED: Private subnet for agent
    'datasync_security_group_id': 'sg-xxxxx',       # REQUIRED: Security group for agent
    'datasync_instance_type': 'm5.xlarge',          # OPTIONAL: Default m5.xlarge
    'datasync_key_name': 'your-key-pair',           # OPTIONAL: SSH key for agent
    
    # NEW: GCS HMAC credentials
    'gcs_access_key': 'GOOG1E...',                  # REQUIRED: GCS HMAC access key
    'gcs_secret_key': 'your-secret-key',            # REQUIRED: GCS HMAC secret key
}
```

### Parameter Details

#### datasync_subnet_id (REQUIRED)
- **Type**: String
- **Description**: Private subnet ID where DataSync agent will be deployed
- **Example**: `subnet-0123456789abcdef0`
- **Requirements**:
  - Must be a private subnet with NAT Gateway for internet access
  - Must have route to AWS DataSync service endpoints
  - Must allow outbound HTTPS (443) to storage.googleapis.com

#### datasync_security_group_id (REQUIRED)
- **Type**: String
- **Description**: Security group for DataSync agent EC2 instance
- **Example**: `sg-0123456789abcdef0`
- **Requirements**:
  - Outbound HTTPS (443) to storage.googleapis.com (GCS)
  - Outbound HTTPS (443) to AWS DataSync service endpoints
  - Outbound HTTPS (443) to S3 endpoints
  - Inbound HTTP (80) from your VPC (for activation)

#### datasync_instance_type (OPTIONAL)
- **Type**: String
- **Default**: `m5.xlarge`
- **Description**: EC2 instance type for DataSync agent
- **Recommendations**:
  - Small datasets (<1TB): `m5.large`
  - Medium datasets (1-10TB): `m5.xlarge` (default)
  - Large datasets (>10TB): `m5.2xlarge` or higher
  - High throughput: Use network-optimized instances (m5n.*)

#### datasync_key_name (OPTIONAL)
- **Type**: String
- **Description**: SSH key pair name for agent instance
- **Example**: `my-key-pair`
- **Note**: Only needed if you want SSH access to the agent

#### gcs_access_key (REQUIRED)
- **Type**: String
- **Description**: GCS HMAC access key for authentication
- **Example**: `GOOG1E...`
- **How to create**: See "Creating GCS HMAC Keys" section below

#### gcs_secret_key (REQUIRED)
- **Type**: String
- **Description**: GCS HMAC secret key for authentication
- **Example**: `your-secret-key`
- **Security**: Store encrypted in database or AWS Secrets Manager

---

## AWS Infrastructure Setup

### 1. Create VPC and Subnets

```bash
# Create VPC
aws ec2 create-vpc --cidr-block 10.0.0.0/16

# Create private subnet
aws ec2 create-subnet \
  --vpc-id vpc-xxxxx \
  --cidr-block 10.0.1.0/24 \
  --availability-zone us-east-1a

# Create NAT Gateway (for private subnet internet access)
aws ec2 create-nat-gateway \
  --subnet-id subnet-public-xxxxx \
  --allocation-id eipalloc-xxxxx
```

### 2. Create Security Group

```bash
# Create security group
aws ec2 create-security-group \
  --group-name datasync-agent-sg \
  --description "Security group for DataSync agent" \
  --vpc-id vpc-xxxxx

# Add outbound rules
aws ec2 authorize-security-group-egress \
  --group-id sg-xxxxx \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0

# Add inbound rule for activation (from VPC only)
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxx \
  --protocol tcp \
  --port 80 \
  --cidr 10.0.0.0/16
```

### 3. Create IAM Role for DataSync S3 Access

```bash
# Create trust policy
cat > datasync-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "datasync.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name DataSyncS3AccessRole \
  --assume-role-policy-document file://datasync-trust-policy.json

# Attach S3 access policy
aws iam attach-role-policy \
  --role-name DataSyncS3AccessRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
```

---

## Creating GCS HMAC Keys

AWS DataSync requires HMAC keys to access GCS buckets.

### Steps:

1. **Open Google Cloud Console**
   - Navigate to: Cloud Storage → Settings → Interoperability

2. **Create HMAC Key**
   - Click "Create a key for a service account"
   - Select or create a service account
   - Click "Create Key"

3. **Save Credentials**
   - Access Key: `GOOG1E...` (starts with GOOG1E)
   - Secret: Long base64-encoded string
   - **Important**: Save the secret immediately - it won't be shown again!

4. **Grant Permissions**
   - Ensure the service account has `Storage Object Viewer` role on the GCS bucket

### Example:
```
Access Key: GOOG1EABCDEFGHIJKLMNOPQRSTUVWXYZ
Secret: abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGH
```

---

## DataSync Transfer Features

### Delta Sync (CHANGED Mode)
- Only transfers new or modified files
- Automatic on retry
- Reduces transfer time and costs

### Automatic Retry
- Up to 3 retry attempts by default
- Exponential backoff between retries
- Resumes from last successful point

### Monitoring
- Real-time progress tracking
- Files transferred count
- Bytes transferred count
- Task execution status

### Verification
- Verifies transferred files
- Ensures data integrity
- Reports any failures

---

## Example Migration Configuration

### Complete Configuration

```python
from models.bq_redshift_migration import MigrationBQRedshift

migration = MigrationBQRedshift(
    migration_name="bq_to_redshift_datasync",
    pathway="B",  # Use Path B for AWS DataSync
    
    # Source (BigQuery)
    source_project_id="my-gcp-project",
    source_dataset="my_dataset",
    source_tables=["table1", "table2", "table3"],
    
    # Target (Redshift)
    target_connection_id=7,  # Redshift connection
    
    # Storage Configuration
    gcs_bucket="my-gcs-bucket",
    gcs_path="exports/migration1",
    s3_bucket="my-s3-bucket",
    s3_path="imports/migration1",
    
    # AWS DataSync Configuration
    # Note: These should be added to storage_config in orchestrator
    # datasync_subnet_id="subnet-xxxxx",
    # datasync_security_group_id="sg-xxxxx",
    # datasync_instance_type="m5.xlarge",
    # gcs_access_key="GOOG1E...",
    # gcs_secret_key="secret-key",
    
    # IAM Role for Redshift
    iam_role_arn="arn:aws:iam::123456789012:role/RedshiftS3AccessRole",
    
    # AWS Credentials
    aws_access_key_id="AKIA...",
    aws_secret_access_key_encrypted="encrypted-secret",
    
    # Export Settings
    export_format="PARQUET",
    compression="SNAPPY"
)
```

---

## Orchestrator Integration

The orchestrator needs to pass DataSync parameters to PathwayB:

```python
# In orchestrator.py
storage_config = {
    'gcs_bucket': migration.gcs_bucket,
    'gcs_path': migration.gcs_path,
    's3_bucket': migration.s3_bucket,
    's3_path': migration.s3_path,
    'aws_region': 'us-east-1',
    
    # DataSync parameters (from migration or config)
    'datasync_subnet_id': migration.datasync_subnet_id or os.getenv('DATASYNC_SUBNET_ID'),
    'datasync_security_group_id': migration.datasync_security_group_id or os.getenv('DATASYNC_SECURITY_GROUP_ID'),
    'datasync_instance_type': migration.datasync_instance_type or 'm5.xlarge',
    'datasync_key_name': migration.datasync_key_name,
    
    # GCS HMAC credentials (from migration or secrets manager)
    'gcs_access_key': migration.gcs_access_key,
    'gcs_secret_key': migration.gcs_secret_key,  # Should be encrypted
    
    'export_format': migration.export_format,
    'compression': migration.compression
}
```

---

## Cost Considerations

### AWS DataSync Pricing
- **Data Scanned**: $0.0125 per GB scanned
- **Data Transferred**: Standard AWS data transfer rates
- **EC2 Instance**: Hourly rate for agent instance type
- **S3 Storage**: Standard S3 storage rates

### Cost Optimization Tips
1. Use delta sync (CHANGED mode) to minimize data transfer
2. Choose appropriate instance type for your dataset size
3. Terminate agent instance after migration completes
4. Use S3 lifecycle policies for long-term storage

---

## Troubleshooting

### Common Issues

#### 1. Agent Activation Fails
**Error**: Cannot retrieve activation key from agent

**Solutions**:
- Ensure agent instance is in running state
- Verify security group allows inbound HTTP (80) from your network
- Check that subnet has internet access via NAT Gateway
- Wait 60 seconds after instance launch for agent to initialize

#### 2. GCS Connection Fails
**Error**: Cannot connect to GCS bucket

**Solutions**:
- Verify HMAC credentials are correct
- Ensure service account has Storage Object Viewer role
- Check that security group allows outbound HTTPS (443) to storage.googleapis.com
- Verify GCS bucket name is correct (without gs:// prefix)

#### 3. S3 Access Denied
**Error**: Cannot write to S3 bucket

**Solutions**:
- Verify DataSyncS3AccessRole exists and has S3 permissions
- Check S3 bucket policy allows DataSync access
- Ensure IAM role trust policy includes datasync.amazonaws.com

#### 4. Transfer Fails Midway
**Error**: Task execution status shows ERROR

**Solutions**:
- Check CloudWatch Logs for detailed error messages
- Verify network connectivity is stable
- Use automatic retry feature (enabled by default)
- Check if source files were modified during transfer

---

## Monitoring and Logs

### CloudWatch Logs
DataSync automatically sends logs to CloudWatch:
- Log Group: `/aws/datasync`
- Contains detailed transfer logs
- Shows file-level errors

### Task Execution Metrics
- Files transferred
- Bytes transferred
- Transfer duration
- Error count
- Verification results

### Query Logs
```bash
# Get task execution details
aws datasync describe-task-execution \
  --task-execution-arn arn:aws:datasync:...

# List all task executions
aws datasync list-task-executions \
  --task-arn arn:aws:datasync:...
```

---

## Cleanup

After migration completes, clean up resources:

```python
# Automatic cleanup (if enabled)
datasync.cleanup_resources(delete_agent=True)
```

Or manually:
```bash
# Delete task
aws datasync delete-task --task-arn arn:aws:datasync:...

# Delete locations
aws datasync delete-location --location-arn arn:aws:datasync:...

# Delete agent
aws datasync delete-agent --agent-arn arn:aws:datasync:...

# Terminate EC2 instance
aws ec2 terminate-instances --instance-ids i-xxxxx
```

---

## Comparison: Path B vs Path C

| Feature | Path B (AWS DataSync) | Path C (Direct Transfer) |
|---------|----------------------|--------------------------|
| Transfer Method | AWS DataSync | GCP Storage Transfer Service |
| Infrastructure | EC2 agent required | No additional infrastructure |
| Setup Complexity | Higher (VPC, security groups, IAM) | Lower (API-based) |
| Delta Sync | Yes (CHANGED mode) | Yes (built-in) |
| Retry Logic | Automatic with exponential backoff | Automatic |
| Monitoring | CloudWatch + DataSync console | Application logs |
| Cost | DataSync + EC2 + data transfer | Data transfer only |
| Best For | Large datasets, enterprise requirements | Simple migrations, smaller datasets |

---

## Status: ✅ Path B AWS DataSync Integration Complete

Path B now uses AWS DataSync for GCS to S3 transfer with:
- ✅ Automated EC2 agent deployment
- ✅ GCS source location with HMAC authentication
- ✅ S3 destination location with IAM role
- ✅ Delta sync with CHANGED transfer mode
- ✅ Automatic retry on failure
- ✅ Real-time progress monitoring
- ✅ Reuses PathwayC load stage for S3 → Redshift

**Path C remains unchanged** and continues to use GCP Storage Transfer Service.
