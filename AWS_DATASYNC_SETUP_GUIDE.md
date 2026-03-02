# Path B: AWS DataSync Agent on GCP VM — Setup Guide

## Architecture

```
BigQuery → GCS (private) → [DataSync Agent on GCP VM] → S3 → Redshift
                                    ↑
                          Reads GCS privately (same VPC)
                          Writes to S3 over encrypted channel
```

The DataSync agent runs as a GCP Compute Engine VM inside your VPC. This ensures:
- **Private GCS access**: The agent reads from GCS over Google's internal network
- **Encrypted transfer**: Data is sent to S3 over TLS
- **No public internet exposure** for the GCS read path

## Prerequisites

### 1. Import DataSync Agent Image into GCP (One-Time Setup)

**This is a required one-time setup before using Path B.**

AWS provides the DataSync agent as an OVA file that must be imported into your GCP project as a custom image named `aws-datasync-agent`.

#### Step 1: Download the DataSync Agent OVA

1. Go to [AWS DataSync Console](https://console.aws.amazon.com/datasync/)
2. Click **Agents** → **Create agent**
3. Select **VMware ESXi** as the hypervisor
4. Download the OVA file (approximately 500 MB)

#### Step 2: Upload to GCS

```bash
# Upload the OVA to a GCS bucket
gsutil cp aws-datasync-agent.ova gs://your-bucket/images/
```

#### Step 3: Import as GCP Custom Image

```bash
# Import the OVA as a GCP custom image
gcloud compute images create aws-datasync-agent \
  --source-uri=gs://your-bucket/images/aws-datasync-agent.ova \
  --project=your-project-id \
  --guest-os-features=UEFI_COMPATIBLE

# Verify the image was created
gcloud compute images describe aws-datasync-agent --project=your-project-id
```

**Important**: The image MUST be named `aws-datasync-agent` exactly. The application looks for this image name when creating VMs.

#### Alternative: Manual VM Creation

If you prefer to manage the VM yourself, create it manually and use the "Use Existing VM" option in the UI:

```bash
gcloud compute instances create datasync-agent-vm \
  --zone=us-central1-a \
  --machine-type=n1-standard-4 \
  --image=aws-datasync-agent \
  --boot-disk-size=80GB \
  --boot-disk-type=pd-ssd \
  --network=your-vpc \
  --subnet=your-subnet
```

### 2. Generate GCS HMAC Keys

DataSync accesses GCS using S3-compatible HMAC credentials:

1. Go to **Google Cloud Console → Cloud Storage → Settings → Interoperability**
2. Click **Create a key for a service account** (or your user account)
3. Save the **Access Key** and **Secret Key**

### 3. Create AWS IAM User

Create an IAM user with these policies:
- `AWSDataSyncFullAccess`
- `AmazonS3FullAccess`

Save the Access Key ID and Secret Access Key.

### 4. Create DataSync S3 Access Role

DataSync needs an IAM role to write to S3:

```json
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
```

Attach `AmazonS3FullAccess` policy to this role. Name it `DataSyncS3AccessRole`.

### 5. Create S3 Bucket

```bash
aws s3 mb s3://your-migration-bucket --region us-east-1
```

### 6. Network Requirements

The GCP VM running the DataSync agent needs:
- **Outbound HTTPS (443)** to AWS DataSync endpoints
- **Outbound HTTPS (443)** to your S3 bucket
- **Internal access** to GCS (automatic within GCP)

If the VM has no public IP, set up a **Cloud NAT** for outbound internet access.

## Using the UI

### Option A: Create New VM (Automatic)

1. Select **Path B** in the migration wizard
2. In Stage 2, choose **"Create New VM"**
3. Fill in:
   - **GCP Zone**: Same region as your GCS bucket (e.g., `us-central1-a`)
   - **Machine Type**: `n1-standard-4` recommended
   - **VPC Network**: Your VPC name (or leave empty for `default`)
   - **Subnet**: Your subnet (or leave empty for default)
4. Enter GCS HMAC credentials
5. Enter AWS credentials and S3 details
6. Click **Save & Continue**

The app will automatically:
- Create a GCP VM with the DataSync agent image
- Activate the agent with AWS DataSync
- Create source (GCS) and destination (S3) locations
- Run the transfer task
- Delete the VM after transfer completes

### Option B: Use Existing VM

1. Deploy the DataSync agent VM manually (see Prerequisites step 1)
2. Select **Path B** in the migration wizard
3. In Stage 2, choose **"Use Existing VM"**
4. Enter the VM's **internal IP address**
5. Enter GCS HMAC credentials
6. Enter AWS credentials and S3 details
7. Click **Save & Continue**

The app will:
- Connect to your existing VM to get the activation key
- Activate the agent with AWS DataSync
- Create and run the transfer task
- Leave the VM running (you manage its lifecycle)

## Troubleshooting

### Agent activation fails
- Ensure the DataMIQ backend can reach the VM's internal IP on port 80
- Check that the VM has outbound internet access (for AWS DataSync activation)
- Verify the VM is running the DataSync agent image

### Transfer is slow
- Use a larger machine type (n1-standard-8 or n1-standard-16)
- Ensure the GCP VM is in the same region as your GCS bucket
- Check network bandwidth limits

### Permission errors
- Verify GCS HMAC keys have read access to the source bucket
- Verify AWS IAM user has DataSync and S3 permissions
- Verify the `DataSyncS3AccessRole` exists and has S3 write access
