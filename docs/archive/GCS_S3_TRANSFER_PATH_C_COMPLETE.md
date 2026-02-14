# GCS to S3 Transfer - Path C Implementation Complete

## Overview
Successfully implemented direct GCS to S3 transfer in Path C with AWS credential encryption, decryption, and secure storage.

## Implementation Summary

### 1. Frontend Changes ✅
**File**: `frontend/src/components/migrations/steps/ConfigurationSetupStep.tsx`

**Changes Made**:
- Updated `renderGCSToS3_PathC()` function to capture all required S3 credentials
- Added fields:
  - S3 Bucket Name (required)
  - S3 Path (required)
  - AWS Access Key ID (required)
  - AWS Secret Access Key (required, type="password")
  - AWS Region (dropdown with S3_REGIONS)
  - Transfer Method (direct/cli dropdown)
- All fields have proper labels, placeholders, and help text
- Secret key field uses `type="password"` for security

### 2. Backend API Changes ✅
**File**: `backend/routers/bq_redshift_migration.py`

**Changes Made**:
- Updated `CreateMigrationRequest` model to include:
  - `aws_access_key_id: Optional[str]`
  - `aws_secret_access_key: Optional[str]`
  - `aws_region: Optional[str] = 'us-east-1'`
  - `transfer_method: Optional[str] = 'direct'`
- Updated `create_migration` endpoint to:
  - Encrypt AWS secret key using `EncryptionService`
  - Store encrypted secret in `aws_secret_access_key_encrypted` field
  - Store AWS region in database
- Updated `update_migration` endpoint to handle AWS credential updates

### 3. Database Model Changes ✅
**File**: `backend/models/bq_redshift_migration.py`

**Changes Made**:
- Added `aws_region` column: `Column(String(50), default='us-east-1')`
- Existing fields already present:
  - `aws_access_key_id: Column(String(255))`
  - `aws_secret_access_key_encrypted: Column(Text)`

### 4. Database Migration ✅
**File**: `backend/alembic/versions/008_add_aws_region_to_migrations.py`

**Changes Made**:
- Created Alembic migration to add `aws_region` column
- Default value: `'us-east-1'`
- Nullable: True (for backward compatibility)

### 5. Path C Implementation ✅
**File**: `backend/services/bq_redshift_migration/pathway_c.py`

**Changes Made**:

#### Updated `_execute_cli_transfer()`:
- Retrieves AWS credentials from `storage_config`
- Decrypts `aws_secret_access_key_encrypted` using `EncryptionService`
- Passes decrypted credentials to `_transfer_shard_direct()`
- Logs decryption success/failure

#### Updated `_transfer_shard_direct()`:
- Added parameters:
  - `aws_access_key_id: Optional[str]`
  - `aws_secret_access_key: Optional[str]` (decrypted)
  - `aws_region: str = 'us-east-1'`
- Passes credentials to S3 client initialization
- Uses credentials for S3 upload operations

#### Updated `_get_s3_client()`:
- Now accepts optional AWS credentials
- If credentials provided: creates S3 client with explicit credentials
- If no credentials: uses default credentials (IAM role, env vars)
- Accepts `aws_region` parameter for regional S3 buckets

### 6. Orchestrator Changes ✅
**File**: `backend/services/bq_redshift_migration/orchestrator.py`

**Changes Made**:
- Updated `storage_config` to include:
  - `aws_secret_access_key_encrypted`: Passes encrypted value (not decrypted)
  - `aws_region`: From migration model
  - `transfer_method`: Default 'direct'
- Path C decrypts the secret key internally when needed

## Security Implementation

### Encryption Flow
1. **Frontend**: User enters AWS secret key in password field
2. **API**: `create_migration` endpoint receives plain text secret
3. **Encryption**: `EncryptionService.encrypt()` encrypts the secret
4. **Storage**: Encrypted secret stored in `aws_secret_access_key_encrypted` column
5. **Retrieval**: Orchestrator passes encrypted secret to Path C
6. **Decryption**: Path C decrypts using `EncryptionService.decrypt()`
7. **Usage**: Decrypted secret used to create S3 client

### Encryption Service
**File**: `backend/services/encryption_service.py`

**Features**:
- Uses Fernet symmetric encryption (cryptography library)
- Key derived from `ENCRYPTION_KEY` or `ENCRYPTION_PASSWORD` env var
- Provides `encrypt()` and `decrypt()` methods
- Handles errors gracefully

**Configuration**:
```bash
# .env file
ENCRYPTION_KEY=<base64-encoded-key>
# OR
ENCRYPTION_PASSWORD=<strong-password>
```

## Data Flow

### Complete Flow: Frontend → Database → Execution

```
1. User Input (Frontend)
   ├─ S3 Bucket: "my-s3-bucket"
   ├─ S3 Path: "migrations/bq-to-redshift"
   ├─ AWS Access Key: "AKIAIOSFODNN7EXAMPLE"
   ├─ AWS Secret Key: "wJalrXUtnFEMI/K7MDENG/..." (password field)
   ├─ AWS Region: "us-east-1"
   └─ Transfer Method: "direct"

2. API Request (POST /api/migrations/bq-redshift/create)
   └─ CreateMigrationRequest with plain text credentials

3. Encryption (create_migration endpoint)
   ├─ Get EncryptionService instance
   ├─ Encrypt AWS secret key
   └─ Store encrypted value in database

4. Database Storage (migrations_bq_redshift table)
   ├─ aws_access_key_id: "AKIAIOSFODNN7EXAMPLE" (plain)
   ├─ aws_secret_access_key_encrypted: "gAAAAA..." (encrypted)
   ├─ aws_region: "us-east-1"
   └─ Other migration fields

5. Migration Execution (Orchestrator)
   ├─ Retrieve migration from database
   ├─ Build storage_config with encrypted secret
   └─ Pass to PathwayC.execute()

6. Transfer Stage (PathwayC._execute_cli_transfer)
   ├─ Get encrypted secret from storage_config
   ├─ Decrypt using EncryptionService
   ├─ Pass decrypted secret to _transfer_shard_direct()
   └─ Create S3 client with credentials

7. S3 Upload (_transfer_shard_direct)
   ├─ Download from GCS
   ├─ Create S3 client with decrypted credentials
   ├─ Upload to S3 bucket in specified region
   └─ Clean up temporary files
```

## Transfer Methods

### Method 1: Direct Transfer (Recommended)
- Uses GCS and S3 client libraries
- Downloads from GCS to temporary file
- Uploads from temporary file to S3
- Supports multipart upload for large files (>100MB)
- Better error handling and progress tracking
- No CLI tools required

### Method 2: CLI Transfer (Legacy)
- Uses gsutil and aws cli commands
- Requires CLI tools installed
- Supports streaming transfer
- Fallback to download/upload if streaming fails

## Configuration

### Frontend Form Fields
```typescript
{
  s3Bucket: string,           // Required
  s3Path: string,             // Required
  awsAccessKeyId: string,     // Required
  awsSecretAccessKey: string, // Required (password field)
  awsRegion: string,          // Required (dropdown)
  transferMethod: string      // 'direct' or 'cli'
}
```

### Backend Storage Config
```python
storage_config = {
    'gcs_bucket': str,
    'gcs_path': str,
    's3_bucket': str,
    's3_path': str,
    'aws_access_key_id': str,
    'aws_secret_access_key_encrypted': str,  # Encrypted
    'aws_region': str,
    'transfer_method': str,
    'overwrite_existing': bool,
    'delete_source': bool
}
```

## Testing Guide

### 1. Run Database Migration
```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

### 2. Restart Backend
```bash
# Kill existing process
lsof -ti:8000 | xargs kill -9

# Start backend
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

### 3. Test Frontend Form
1. Navigate to Migrations page
2. Click "Create Migration"
3. Select Path C (CLI/Legacy)
4. Fill in all fields including AWS credentials
5. Verify password field masks secret key
6. Submit form

### 4. Verify Database Storage
```sql
SELECT 
    id,
    migration_name,
    aws_access_key_id,
    LENGTH(aws_secret_access_key_encrypted) as encrypted_length,
    aws_region
FROM migrations_bq_redshift
WHERE pathway = 'C'
ORDER BY created_at DESC
LIMIT 1;
```

### 5. Test Migration Execution
```bash
# Start migration via API or UI
# Monitor logs for:
# - "✓ AWS secret key decrypted successfully"
# - "Direct transfer: gs://... -> s3://..."
# - "✓ Credentials created"
# - "Uploading to S3: s3://..."
```

## Error Handling

### Encryption Errors
- If encryption fails during creation: Returns 500 error
- If decryption fails during execution: Migration fails with clear error
- Logs all encryption/decryption errors

### S3 Client Errors
- Invalid credentials: Fails with authentication error
- Invalid region: Fails with region error
- Network issues: Retries with exponential backoff
- All errors logged with context

### Transfer Errors
- GCS download fails: Logs error, marks shard as failed
- S3 upload fails: Logs error, marks shard as failed
- Temporary file cleanup: Always executed in finally block

## Security Best Practices

### ✅ Implemented
- AWS secret key encrypted before storage
- Password field in frontend (masked input)
- Decryption only when needed (just-in-time)
- Encrypted value never logged
- Secure key derivation (PBKDF2)

### 🔒 Production Recommendations
1. Use AWS KMS instead of Fernet for encryption
2. Store encryption key in AWS Secrets Manager
3. Rotate encryption keys regularly
4. Use IAM roles instead of access keys when possible
5. Enable CloudTrail for audit logging
6. Implement key versioning

## Files Modified

### Frontend
- `frontend/src/components/migrations/steps/ConfigurationSetupStep.tsx`

### Backend
- `backend/routers/bq_redshift_migration.py`
- `backend/models/bq_redshift_migration.py`
- `backend/services/bq_redshift_migration/pathway_c.py`
- `backend/services/bq_redshift_migration/orchestrator.py`
- `backend/alembic/versions/008_add_aws_region_to_migrations.py` (new)

### Documentation
- `GCS_S3_TRANSFER_PATH_C_COMPLETE.md` (this file)

## Next Steps

### Immediate
1. Run database migration: `alembic upgrade head`
2. Restart backend server
3. Test form submission with AWS credentials
4. Verify encryption/decryption in logs

### Future Enhancements
1. Add AWS region validation
2. Implement credential testing before migration
3. Add support for AWS STS temporary credentials
4. Implement AWS KMS encryption
5. Add credential rotation support
6. Implement S3 bucket validation
7. Add transfer progress tracking
8. Implement bandwidth throttling

## Status: ✅ COMPLETE

All components implemented and ready for testing:
- ✅ Frontend form captures AWS credentials
- ✅ Backend encrypts secret key before storage
- ✅ Database stores encrypted credentials
- ✅ Path C decrypts and uses credentials for S3 transfer
- ✅ Database migration created for aws_region column
- ✅ Error handling and logging implemented
- ✅ Security best practices followed

**Ready for end-to-end testing!**
