# AWS Secret Key Encryption - Complete

## Summary

Successfully implemented encryption for AWS Secret Access Keys stored in the database. The secret keys are now encrypted before storage and decrypted only when needed for GCS → S3 transfers.

## What Was Implemented

### 1. Encryption Service ✅
**File**: `backend/services/encryption_service.py`

Created a production-ready encryption service using Fernet (symmetric encryption):
- `encrypt()` - Encrypts plaintext strings
- `decrypt()` - Decrypts encrypted strings
- `generate_key()` - Generates new encryption keys
- Configurable via environment variables
- Fallback to password-based key derivation for development

**Features**:
- Uses `cryptography` library (industry standard)
- Fernet symmetric encryption (AES-128 in CBC mode)
- PBKDF2 key derivation for password-based keys
- Singleton pattern for global instance
- Comprehensive error handling and logging

### 2. Router Updates ✅
**File**: `backend/routers/bq_redshift_migration.py`

Updated the create migration endpoint to:
- Import encryption service
- Encrypt AWS secret key before saving to database
- Store encrypted value in `aws_secret_access_key_encrypted` column
- Log encryption operations (without exposing keys)

**Code Flow**:
```python
# When creating migration
encryption_service = get_encryption_service()
aws_secret_encrypted = encryption_service.encrypt(req.aws_secret_access_key)

# Store encrypted value
migration_data['aws_secret_access_key_encrypted'] = aws_secret_encrypted
```

### 3. Orchestrator Updates ✅
**File**: `backend/services/bq_redshift_migration/orchestrator.py`

Updated the migration execution to:
- Import encryption service
- Decrypt AWS secret key before using it
- Pass decrypted key to pathway execution
- Handle decryption errors gracefully

**Code Flow**:
```python
# When executing migration
encryption_service = get_encryption_service()
aws_secret_key = encryption_service.decrypt(migration.aws_secret_access_key_encrypted)

# Use decrypted key
storage_config['aws_secret_access_key'] = aws_secret_key
```

### 4. UI Already Secure ✅
**File**: `frontend/src/components/migrations/steps/ConfigurationSetupStep.tsx`

The UI already has proper security:
- Input field uses `type="password"` - shows dots instead of text
- Help text warns: "Keep this secure - will be encrypted in database"
- No changes needed!

## Configuration

### Development Setup

Add to `backend/.env`:
```bash
# Option 1: Use a password (simpler for development)
ENCRYPTION_PASSWORD=your-secure-password-here-change-in-production

# Option 2: Use a pre-generated key (more secure)
ENCRYPTION_KEY=your-base64-encoded-key-here
```

### Generate a New Encryption Key

```python
# Run in Python shell
from services.encryption_service import EncryptionService
key = EncryptionService.generate_key()
print(f"ENCRYPTION_KEY={key}")
```

Or use the command line:
```bash
cd backend
source .venv/bin/activate
python -c "from services.encryption_service import EncryptionService; print(f'ENCRYPTION_KEY={EncryptionService.generate_key()}')"
```

### Production Setup

**Option 1: Environment Variable** (Recommended for containers)
```bash
# Set in your deployment environment
export ENCRYPTION_KEY="your-generated-key-here"
```

**Option 2: AWS Secrets Manager** (Most Secure)
```python
# Future enhancement - fetch key from AWS Secrets Manager
import boto3

secrets_client = boto3.client('secretsmanager')
response = secrets_client.get_secret_value(SecretId='datamiq/encryption-key')
encryption_key = response['SecretString']
```

**Option 3: AWS KMS** (Enterprise Grade)
```python
# Future enhancement - use AWS KMS for encryption
import boto3

kms_client = boto3.client('kms')
response = kms_client.encrypt(
    KeyId='alias/datamiq-encryption-key',
    Plaintext=aws_secret_key
)
encrypted_key = response['CiphertextBlob']
```

## Security Features

### ✅ Encryption at Rest
- AWS secret keys encrypted in database
- Uses Fernet (AES-128 CBC + HMAC)
- Cannot be read without encryption key

### ✅ Secure Input
- UI shows password field (dots instead of text)
- Browser doesn't save password in autocomplete
- User warned about security

### ✅ Decryption Only When Needed
- Keys decrypted only during migration execution
- Decrypted value never logged
- Decrypted value not stored anywhere

### ✅ Error Handling
- Decryption errors logged (without exposing keys)
- Migration fails gracefully if decryption fails
- Clear error messages for troubleshooting

## How It Works

### Creating a Migration

1. **User enters AWS credentials** in UI
   - Access Key ID: Plain text (not sensitive)
   - Secret Access Key: Password field (hidden)

2. **Frontend sends to backend**
   - Both sent over HTTPS
   - Secret key in request body

3. **Backend encrypts secret key**
   ```python
   encrypted = encryption_service.encrypt(secret_key)
   ```

4. **Stored in database**
   - Access Key ID: Plain text
   - Secret Key: Encrypted blob

### Running a Migration

1. **Backend loads migration from database**
   - Gets encrypted secret key

2. **Backend decrypts secret key**
   ```python
   decrypted = encryption_service.decrypt(encrypted_key)
   ```

3. **Passes to GCS → S3 transfer**
   - Decrypted key used for API call
   - Never logged or stored

4. **Transfer completes**
   - Decrypted key discarded from memory
   - Only encrypted version remains in database

## Testing

### Test Encryption/Decryption

```python
# In Python shell
from services.encryption_service import get_encryption_service

service = get_encryption_service()

# Test encryption
plaintext = "my-secret-key-12345"
encrypted = service.encrypt(plaintext)
print(f"Encrypted: {encrypted}")

# Test decryption
decrypted = service.decrypt(encrypted)
print(f"Decrypted: {decrypted}")

# Verify
assert plaintext == decrypted
print("✓ Encryption/Decryption working!")
```

### Test End-to-End

1. Create a migration with AWS credentials
2. Check database - secret key should be encrypted blob
3. Run the migration
4. Check logs - should see "Decrypting AWS secret key" (without the key)
5. Verify transfer works with decrypted credentials

## Database Storage

### Before Encryption
```sql
SELECT 
  id, 
  migration_name,
  aws_access_key_id,
  aws_secret_access_key_encrypted
FROM migrations_bq_redshift;

-- Result:
-- aws_secret_access_key_encrypted: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
-- ❌ PLAIN TEXT - INSECURE!
```

### After Encryption
```sql
SELECT 
  id, 
  migration_name,
  aws_access_key_id,
  aws_secret_access_key_encrypted
FROM migrations_bq_redshift;

-- Result:
-- aws_secret_access_key_encrypted: "gAAAAABmXYZ123...encrypted_blob...xyz789=="
-- ✅ ENCRYPTED - SECURE!
```

## Security Best Practices

### ✅ Implemented
1. Encryption at rest using Fernet
2. Password input field in UI
3. Decryption only when needed
4. No logging of sensitive data
5. Graceful error handling

### ⚠️ Recommended for Production
1. **Use AWS KMS** instead of Fernet
   - Hardware security modules
   - Automatic key rotation
   - Audit logging

2. **Store encryption key in AWS Secrets Manager**
   - Centralized key management
   - Access control via IAM
   - Automatic rotation

3. **Implement key rotation**
   - Rotate encryption keys periodically
   - Re-encrypt existing data with new keys
   - Maintain key version history

4. **Add audit logging**
   - Log all encryption/decryption operations
   - Track who accessed which credentials
   - Alert on suspicious activity

5. **Use IAM roles instead of access keys**
   - Temporary credentials
   - Automatic rotation
   - No storage needed

## Migration Path to AWS KMS

### Phase 1: Current Implementation (Done)
- ✅ Fernet encryption
- ✅ Environment variable key
- ✅ Suitable for development and small deployments

### Phase 2: AWS Secrets Manager (Future)
```python
# Store encryption key in Secrets Manager
import boto3

secrets = boto3.client('secretsmanager')
key = secrets.get_secret_value(SecretId='datamiq/encryption-key')
encryption_service = EncryptionService(key['SecretString'])
```

### Phase 3: AWS KMS (Future)
```python
# Use KMS for encryption/decryption
import boto3

kms = boto3.client('kms')

# Encrypt
response = kms.encrypt(
    KeyId='alias/datamiq-key',
    Plaintext=secret_key
)
encrypted = response['CiphertextBlob']

# Decrypt
response = kms.decrypt(CiphertextBlob=encrypted)
decrypted = response['Plaintext']
```

## Troubleshooting

### Issue: "Decryption failed"

**Possible Causes**:
1. Encryption key changed
2. Data corrupted in database
3. Wrong encryption key being used

**Solution**:
```bash
# Check encryption key
echo $ENCRYPTION_KEY

# Verify it matches what was used to encrypt
# If key changed, old data cannot be decrypted
# Need to re-enter AWS credentials
```

### Issue: "No encryption key found"

**Possible Causes**:
1. ENCRYPTION_KEY not set in environment
2. ENCRYPTION_PASSWORD not set
3. .env file not loaded

**Solution**:
```bash
# Set encryption password
export ENCRYPTION_PASSWORD="your-password"

# Or generate and set encryption key
export ENCRYPTION_KEY=$(python -c "from services.encryption_service import EncryptionService; print(EncryptionService.generate_key())")

# Restart backend
```

### Issue: "Transfer fails with authentication error"

**Possible Causes**:
1. Decryption successful but wrong AWS credentials
2. AWS credentials expired
3. AWS credentials lack permissions

**Solution**:
```bash
# Test AWS credentials directly
aws sts get-caller-identity \
  --aws-access-key-id YOUR_KEY_ID \
  --aws-secret-access-key YOUR_SECRET_KEY

# If fails, credentials are wrong
# Re-enter correct credentials in UI
```

## Files Modified

### Backend
- `backend/services/encryption_service.py` - NEW FILE (encryption service)
- `backend/routers/bq_redshift_migration.py` - Added encryption on save
- `backend/services/bq_redshift_migration/orchestrator.py` - Added decryption on use

### Frontend
- No changes needed - already using `type="password"`

### Configuration
- `backend/.env` - Add ENCRYPTION_KEY or ENCRYPTION_PASSWORD

## Dependencies

Already installed:
- `cryptography>=46.0.4` - Encryption library

## Success Criteria

✅ AWS secret keys encrypted before database storage
✅ Encryption uses industry-standard Fernet algorithm
✅ Decryption only happens during migration execution
✅ UI shows password field (dots instead of text)
✅ Configurable encryption key via environment
✅ Graceful error handling for decryption failures
✅ No sensitive data in logs

## Next Steps

### Immediate (Ready to Use)
1. ✅ Set ENCRYPTION_PASSWORD in backend/.env
2. ✅ Restart backend server
3. ✅ Test creating migration with AWS credentials
4. ✅ Verify secret key encrypted in database

### Short-term (Production Hardening)
1. ⚠️ Generate dedicated encryption key
2. ⚠️ Store key in AWS Secrets Manager
3. ⚠️ Add audit logging for encryption operations
4. ⚠️ Implement key rotation mechanism

### Long-term (Enterprise Grade)
1. ❌ Migrate to AWS KMS for encryption
2. ❌ Implement automatic key rotation
3. ❌ Add compliance reporting
4. ❌ Use IAM roles instead of access keys

## Conclusion

AWS Secret Access Keys are now **securely encrypted** in the database using industry-standard Fernet encryption. The keys are only decrypted when needed for GCS → S3 transfers and are never logged or exposed.

For production deployments, consider migrating to AWS KMS for hardware-backed encryption and automatic key rotation.
