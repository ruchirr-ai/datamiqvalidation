# AWS Credentials Issue - RESOLVED

## Problem Identified

The AWS credentials you're using are **temporary security credentials** (session tokens), not permanent IAM user credentials.

### Evidence:
- Your AWS Access Key ID: `ASIA...FSVN`
- Access keys starting with `ASIA` are temporary credentials from AWS STS
- These credentials expire after a few hours
- Error: `InvalidClientTokenId: The security token included in the request is invalid`

## Solution

You need to use **permanent IAM user credentials** instead of temporary ones.

### Step 1: Create a New IAM User (if you don't have one)

1. Go to AWS Console → IAM → Users
2. Click "Create user"
3. User name: `datamiq-datasync-user` (or any name you prefer)
4. Click "Next"
5. Attach policies:
   - `AWSDataSyncFullAccess`
   - `AmazonS3FullAccess`
6. Click "Next" → "Create user"

### Step 2: Create Access Keys for the IAM User

1. Click on the user you just created
2. Go to "Security credentials" tab
3. Scroll down to "Access keys"
4. Click "Create access key"
5. Select "Application running outside AWS"
6. Click "Next" → "Create access key"
7. **IMPORTANT**: Copy both:
   - Access key ID (starts with `AKIA`, not `ASIA`)
   - Secret access key (only shown once!)

### Step 3: Update Your Migration

1. Go to the Migrations page
2. Click "Edit" on migration "sdfghm" (ID: 18)
3. In Stage 2 (Configuration Setup), update:
   - AWS Access Key ID: `AKIA...` (your new permanent key)
   - AWS Secret Access Key: (your new secret key)
4. Save the migration

### Step 4: Run the Migration Again

1. Click "Run" on the migration
2. The credentials should now work!

## How to Verify Your Credentials

You can test your credentials before running the migration:

```bash
cd datamiq/backend
.venv\Scripts\python.exe test_aws_credentials.py 18
```

This will:
- ✓ Verify the credentials are valid
- ✓ Check if they have DataSync permissions
- ✓ Check if they have S3 permissions
- Show detailed error messages if something is wrong

## Key Differences

| Temporary Credentials (ASIA) | Permanent Credentials (AKIA) |
|------------------------------|------------------------------|
| Start with `ASIA` | Start with `AKIA` |
| Expire after hours/days | Never expire (until deleted) |
| From AWS STS, IAM roles, SSO | From IAM users |
| Include session token | No session token |
| **NOT suitable for DataMIQ** | **✓ Use these!** |

## Why This Happened

You might have gotten temporary credentials from:
- AWS SSO login
- AWS CLI with `aws sso login`
- IAM role assumption
- AWS Console "Command line or programmatic access" option

For DataMIQ, you need permanent IAM user credentials that don't expire.

## Next Steps

1. Create permanent IAM user credentials (see above)
2. Update the migration with the new credentials
3. Run the test script to verify: `python test_aws_credentials.py 18`
4. Run the migration again

The DataSync agent activation should work once you use permanent credentials!
