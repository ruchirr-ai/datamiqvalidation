# AWS DataSync Agent Deployment in GCP

## Overview

For Path B (DataSync) in BigQuery to Redshift migrations, the AWS DataSync agent must be deployed in Google Cloud Platform (GCP) to enable private connectivity between Google Cloud Storage (GCS) and Amazon S3.

## Why Deploy in GCP?

**Private Connectivity**: Deploying the DataSync agent in GCP allows direct, private transfer of data from GCS to S3 without exposing data to the public internet. This provides:

- Enhanced security
- Better performance
- Lower egress costs
- Compliance with data residency requirements

## Prerequisites

### GCP Requirements
- Active GCP project with billing enabled
- Compute Engine API enabled
- Sufficient quota for VM instances
- VPC network configured
- Firewall rules allowing HTTPS outbound (port 443)

### AWS Requirements
- AWS account with DataSync service access
- S3 bucket for destination
- IAM permissions to create DataSync tasks and locations
- DataSync agent activation key

### Network Requirements
- GCP VM must have internet access (for AWS DataSync service endpoints)
- Firewall rules allowing:
  - Outbound HTTPS (443) to AWS DataSync endpoints
  - Outbound HTTPS (443) to GCS
  - Outbound HTTPS (443) to S3

## Deployment Steps

### Step 1: Create DataSync Agent VM in GCP

#### 1.1 Download DataSync Agent AMI

AWS provides a DataSync agent as a virtual appliance. You'll need to:

1. Go to AWS DataSync console
2. Navigate to "Agents" → "Create agent"
3. Download the agent OVA/VMDK image
4. Convert to GCP-compatible format

#### 1.2 Create Compute Engine VM

```bash
# Set variables
PROJECT_ID="your-gcp-project"
ZONE="us-central1-a"
VM_NAME="datasync-agent"
MACHINE_TYPE="n1-standard-4"  # 4 vCPU, 15 GB RAM (recommended)
NETWORK="default"
SUBNET="default"

# Create VM instance
gcloud compute instances create $VM_NAME \
  --project=$PROJECT_ID \
  --zone=$ZONE \
  --machine-type=$MACHINE_TYPE \
  --network-interface=network-tier=PREMIUM,subnet=$SUBNET \
  --maintenance-policy=MIGRATE \
  --provisioning-model=STANDARD \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --tags=datasync-agent \
  --create-disk=auto-delete=yes,boot=yes,device-name=$VM_NAME,image-family=ubuntu-2004-lts,image-project=ubuntu-os-cloud,mode=rw,size=80,type=pd-standard \
  --no-shielded-secure-boot \
  --shielded-vtpm \
  --shielded-integrity-monitoring \
  --reservation-affinity=any
```

#### 1.3 Configure Firewall Rules

```bash
# Allow HTTPS outbound
gcloud compute firewall-rules create allow-datasync-outbound \
  --project=$PROJECT_ID \
  --direction=EGRESS \
  --priority=1000 \
  --network=$NETWORK \
  --action=ALLOW \
  --rules=tcp:443 \
  --destination-ranges=0.0.0.0/0 \
  --target-tags=datasync-agent

# Allow SSH for management
gcloud compute firewall-rules create allow-datasync-ssh \
  --project=$PROJECT_ID \
  --direction=INGRESS \
  --priority=1000 \
  --network=$NETWORK \
  --action=ALLOW \
  --rules=tcp:22 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=datasync-agent
```

### Step 2: Install and Configure DataSync Agent

#### 2.1 SSH into the VM

```bash
gcloud compute ssh $VM_NAME --zone=$ZONE --project=$PROJECT_ID
```

#### 2.2 Install DataSync Agent Software

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install required packages
sudo apt-get install -y wget curl

# Download DataSync agent installer
# Note: AWS provides specific installation instructions
# Follow AWS documentation for the latest agent version
wget https://s3.amazonaws.com/aws-datasync-downloads/latest/aws-datasync-agent-installer.sh

# Run installer
sudo bash aws-datasync-agent-installer.sh
```

#### 2.3 Activate DataSync Agent

1. Get the agent's local IP address:
   ```bash
   hostname -I
   ```

2. In AWS Console:
   - Go to DataSync → Agents → Create agent
   - Select "Amazon EC2" as deployment option
   - Enter the agent's IP address
   - Get the activation key

3. Activate the agent:
   ```bash
   # Use the activation key from AWS Console
   sudo aws-datasync-agent activate \
     --activation-key YOUR_ACTIVATION_KEY \
     --region us-east-1
   ```

### Step 3: Configure GCS Access

#### 3.1 Create GCS HMAC Keys

DataSync requires HMAC keys to access GCS:

1. Go to Google Cloud Console
2. Navigate to Cloud Storage → Settings → Interoperability
3. Click "Create a key for a service account"
4. Select or create a service account with Storage Object Viewer permissions
5. Save the Access Key and Secret Key

#### 3.2 Grant Service Account Permissions

```bash
# Grant Storage Object Viewer role
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:datasync-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
```

### Step 4: Create DataSync Task

#### 4.1 Create GCS Location

In AWS Console or CLI:

```bash
aws datasync create-location-object-storage \
  --server-hostname storage.googleapis.com \
  --bucket-name your-gcs-bucket \
  --access-key YOUR_GCS_HMAC_ACCESS_KEY \
  --secret-key YOUR_GCS_HMAC_SECRET_KEY \
  --agent-arns arn:aws:datasync:region:account:agent/agent-id \
  --subdirectory /path/to/data
```

#### 4.2 Create S3 Location

```bash
aws datasync create-location-s3 \
  --s3-bucket-arn arn:aws:s3:::your-s3-bucket \
  --s3-config BucketAccessRoleArn=arn:aws:iam::account:role/DataSyncS3Role \
  --subdirectory /migrations/bq-to-redshift
```

#### 4.3 Create DataSync Task

```bash
aws datasync create-task \
  --source-location-arn arn:aws:datasync:region:account:location/source-location-id \
  --destination-location-arn arn:aws:datasync:region:account:location/destination-location-id \
  --name "GCS-to-S3-Migration" \
  --options VerifyMode=POINT_IN_TIME_CONSISTENT,OverwriteMode=ALWAYS
```

## VM Sizing Recommendations

### Small Migrations (< 1 TB)
- **Machine Type**: n1-standard-2 (2 vCPU, 7.5 GB RAM)
- **Disk**: 50 GB SSD
- **Cost**: ~$50/month

### Medium Migrations (1-10 TB)
- **Machine Type**: n1-standard-4 (4 vCPU, 15 GB RAM) - Recommended
- **Disk**: 80 GB SSD
- **Cost**: ~$100/month

### Large Migrations (> 10 TB)
- **Machine Type**: n1-standard-8 (8 vCPU, 30 GB RAM)
- **Disk**: 100 GB SSD
- **Cost**: ~$200/month

## Network Configuration

### VPC Peering (Optional)

For enhanced security, set up VPC peering between GCP and AWS:

1. Create VPC peering connection in GCP
2. Create VPC peering connection in AWS
3. Update route tables
4. Update firewall rules

### Cloud VPN (Alternative)

Set up a VPN tunnel between GCP and AWS:

1. Create Cloud VPN gateway in GCP
2. Create VPN gateway in AWS
3. Configure IPsec tunnels
4. Update routing

## Monitoring

### GCP Monitoring

Monitor the DataSync agent VM:

```bash
# CPU utilization
gcloud compute instances describe $VM_NAME \
  --zone=$ZONE \
  --format="get(cpuPlatform)"

# Network traffic
gcloud compute instances get-serial-port-output $VM_NAME \
  --zone=$ZONE
```

### AWS DataSync Monitoring

Monitor DataSync tasks in AWS:

- CloudWatch metrics for task execution
- DataSync console for task status
- CloudWatch Logs for detailed logs

## Troubleshooting

### Agent Not Activating

**Issue**: Agent activation fails

**Solutions**:
1. Verify VM has internet access
2. Check firewall rules allow HTTPS outbound
3. Verify activation key is correct
4. Check AWS region matches

### GCS Access Denied

**Issue**: DataSync cannot access GCS bucket

**Solutions**:
1. Verify HMAC keys are correct
2. Check service account has Storage Object Viewer role
3. Verify bucket name is correct
4. Check bucket permissions

### Slow Transfer Speed

**Issue**: Data transfer is slower than expected

**Solutions**:
1. Increase VM machine type (more vCPUs)
2. Check network bandwidth
3. Verify no rate limiting on GCS or S3
4. Consider using multiple DataSync tasks in parallel

### High Costs

**Issue**: GCP egress costs are high

**Solutions**:
1. Use GCP's committed use discounts
2. Consider AWS Direct Connect or GCP Interconnect
3. Optimize data transfer schedule
4. Use compression where possible

## Security Best Practices

### 1. Use Service Accounts

- Create dedicated service account for DataSync agent
- Grant minimum required permissions
- Rotate HMAC keys regularly

### 2. Network Security

- Deploy agent in private subnet
- Use VPC peering or VPN for private connectivity
- Restrict firewall rules to specific IP ranges
- Enable VPC Flow Logs

### 3. Data Encryption

- Enable encryption in transit (TLS)
- Enable encryption at rest in S3
- Use AWS KMS for S3 encryption keys
- Verify data integrity with checksums

### 4. Access Control

- Use IAM roles for AWS resources
- Implement least privilege access
- Enable MFA for administrative access
- Audit access logs regularly

## Cost Optimization

### GCP Costs

- **Compute**: ~$50-200/month (depending on VM size)
- **Egress**: $0.12/GB to AWS (first 1 TB free per month)
- **Storage**: Minimal (agent uses local disk)

### AWS Costs

- **DataSync**: $0.0125 per GB transferred
- **S3 Storage**: $0.023 per GB/month (Standard)
- **S3 Requests**: Minimal

### Tips to Reduce Costs

1. **Right-size the VM**: Don't over-provision
2. **Use committed use discounts**: Save up to 57% on GCP compute
3. **Schedule transfers**: Transfer during off-peak hours
4. **Compress data**: Reduce transfer volume
5. **Delete agent after migration**: Don't leave running indefinitely

## Cleanup

After migration is complete:

```bash
# Stop DataSync agent
sudo systemctl stop aws-datasync-agent

# Delete GCP VM
gcloud compute instances delete $VM_NAME \
  --zone=$ZONE \
  --project=$PROJECT_ID

# Delete firewall rules
gcloud compute firewall-rules delete allow-datasync-outbound --project=$PROJECT_ID
gcloud compute firewall-rules delete allow-datasync-ssh --project=$PROJECT_ID

# Delete DataSync resources in AWS
aws datasync delete-task --task-arn arn:aws:datasync:region:account:task/task-id
aws datasync delete-location --location-arn arn:aws:datasync:region:account:location/location-id
aws datasync delete-agent --agent-arn arn:aws:datasync:region:account:agent/agent-id
```

## References

- [AWS DataSync Documentation](https://docs.aws.amazon.com/datasync/)
- [GCP Compute Engine Documentation](https://cloud.google.com/compute/docs)
- [GCS HMAC Keys Documentation](https://cloud.google.com/storage/docs/authentication/hmackeys)
- [AWS DataSync Pricing](https://aws.amazon.com/datasync/pricing/)
- [GCP Network Pricing](https://cloud.google.com/vpc/network-pricing)

---

**Last Updated**: February 15, 2026  
**Status**: Production Ready
