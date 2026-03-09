# KMS Encryption Quick Start Guide

## For Developers

Quick reference for using KMS encryption in the DataMIQ application.

## Basic Usage

### Import the Service

```python
from services.kms_encryption_service import get_kms_encryption_service
```

### Encrypt Data

```python
# Get service instance
kms_service = get_kms_encryption_service()

# Define encryption context (for audit trail)
encryption_context = {
    'entity_id': str(entity_id),
    'field': 'password',
    'created_at': datetime.utcnow().isoformat()
}

# Encrypt
encrypted_value = kms_service.encrypt(
    plaintext_value,
    encryption_context
)

# Store encrypted_value in database
```

### Decrypt Data

```python
# Get service instance
kms_service = get_kms_encryption_service()

# Use same context (without timestamp fields)
encryption_context = {
    'entity_id': str(entity_id),
    'field': 'password'
}

# Decrypt
plaintext_value = kms_service.decrypt(
    encrypted_value,
    encryption_context
)
```

## Encryption Context Guidelines

### Required Fields
- `entity_id`: ID of the entity (migration_id, connection_id, workspace_id)
- `field`: Name of the field being encrypted

### Optional Fields (for encryption only)
- `created_at`: Timestamp when encrypted
- `updated_at`: Timestamp when updated

### Examples

#### Migration AWS Secret
```python
# Encrypt
encryption_context = {
    'migration_id': str(migration_id),
    'field': 'aws_secret_access_key',
    'created_at': datetime.utcnow().isoformat()
}

# Decrypt
encryption_context = {
    'migration_id': str(migration_id),
    'field': 'aws_secret_access_key'
}
```

#### Connection Password
```python
# Encrypt
encryption_context = {
    'connection_id': str(connection_id),
    'field': 'password',
    'created_at': datetime.utcnow().isoformat()
}

# Decrypt
encryption_context = {
    'connection_id': str(connection_id),
    'field': 'password'
}
```

#### Workspace-Scoped Data
```python
# Encrypt
encryption_context = {
    'workspace_id': str(workspace_id),
    'field': 'api_key',
    'created_at': datetime.utcnow().isoformat()
}

# Decrypt
encryption_context = {
    'workspace_id': str(workspace_id),
    'field': 'api_key'
}
```

## Common Patterns

### Pattern 1: Encrypt on Create

```python
from services.kms_encryption_service import get_kms_encryption_service
from datetime import datetime

def create_migration(request):
    # ... create migration object ...
    
    # Encrypt AWS secret
    if request.aws_secret_access_key:
        kms_service = get_kms_encryption_service()
        encryption_context = {
            'migration_id': str(migration.id),
            'field': 'aws_secret_access_key',
            'created_at': datetime.utcnow().isoformat()
        }
        migration.aws_secret_encrypted = kms_service.encrypt(
            request.aws_secret_access_key,
            encryption_context
        )
    
    db.add(migration)
    db.commit()
```

### Pattern 2: Encrypt on Update

```python
def update_migration(migration_id, request):
    migration = db.query(Migration).get(migration_id)
    
    # Update AWS secret if provided
    if request.aws_secret_access_key:
        kms_service = get_kms_encryption_service()
        encryption_context = {
            'migration_id': str(migration_id),
            'field': 'aws_secret_access_key',
            'updated_at': datetime.utcnow().isoformat()
        }
        migration.aws_secret_encrypted = kms_service.encrypt(
            request.aws_secret_access_key,
            encryption_context
        )
    
    db.commit()
```

### Pattern 3: Decrypt for Use

```python
def execute_migration(migration_id):
    migration = db.query(Migration).get(migration_id)
    
    # Decrypt AWS secret
    if migration.aws_secret_encrypted:
        kms_service = get_kms_encryption_service()
        encryption_context = {
            'migration_id': str(migration_id),
            'field': 'aws_secret_access_key'
        }
        aws_secret = kms_service.decrypt(
            migration.aws_secret_encrypted,
            encryption_context
        )
        
        # Use aws_secret for S3 operations
        # ...
```

### Pattern 4: Error Handling

```python
def decrypt_with_error_handling(encrypted_value, context):
    try:
        kms_service = get_kms_encryption_service()
        return kms_service.decrypt(encrypted_value, context)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDeniedException':
            logger.error("KMS access denied - check IAM permissions")
        elif error_code == 'NotFoundException':
            logger.error("KMS key not found - check Secrets Manager")
        elif error_code == 'InvalidCiphertextException':
            logger.error("Invalid ciphertext - data may be corrupted")
        raise
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        raise
```

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# AWS Region
AWS_REGION=us-east-1

# KMS Encryption Configuration
ENCRYPTION_SECRET_NAME=datamiq/encryption/kms-key-id
ENCRYPTION_AWS_REGION=us-east-1
```

### AWS Setup Required

1. Create KMS key in AWS
2. Store key ID in Secrets Manager (name: `datamiq/encryption/kms-key-id`)
3. Configure IAM permissions for KMS and Secrets Manager

See `KMS_ENCRYPTION_SETUP.md` for detailed setup instructions.

## Testing

### Test Encryption/Decryption

```python
# test_kms.py
from services.kms_encryption_service import get_kms_encryption_service

kms_service = get_kms_encryption_service()

# Test data
test_secret = "my-test-password"
context = {'test': 'true'}

# Encrypt
encrypted = kms_service.encrypt(test_secret, context)
print(f"Encrypted: {encrypted[:50]}...")

# Decrypt
decrypted = kms_service.decrypt(encrypted, context)
print(f"Decrypted: {decrypted}")

# Verify
assert decrypted == test_secret
print("✓ Test passed!")
```

Run test:
```bash
cd backend
source .venv/bin/activate
python test_kms.py
```

## Troubleshooting

### Error: "AccessDeniedException"
**Solution**: Check IAM permissions for KMS and Secrets Manager

### Error: "NotFoundException"
**Solution**: Verify Secrets Manager secret exists with correct name

### Error: "InvalidCiphertextException"
**Solution**: Encryption context doesn't match or data is corrupted

### Error: "KMSInvalidStateException"
**Solution**: KMS key is disabled - enable it in AWS Console

## Best Practices

1. **Always use encryption context** - Provides audit trail and additional security
2. **Don't cache decrypted values** - Decrypt on-demand for security
3. **Use consistent context keys** - Makes debugging easier
4. **Log encryption operations** - But never log plaintext values
5. **Handle errors gracefully** - Provide clear error messages
6. **Test thoroughly** - Verify encryption/decryption in all scenarios

## Migration from Old Encryption

If you have existing code using the old `get_encryption_service()`:

### Before (Fernet)
```python
from services.encryption_service import get_encryption_service

encryption_service = get_encryption_service()
encrypted = encryption_service.encrypt(plaintext)
decrypted = encryption_service.decrypt(encrypted)
```

### After (KMS)
```python
from services.kms_encryption_service import get_kms_encryption_service

kms_service = get_kms_encryption_service()
encryption_context = {
    'entity_id': str(entity_id),
    'field': 'field_name'
}
encrypted = kms_service.encrypt(plaintext, encryption_context)
decrypted = kms_service.decrypt(encrypted, encryption_context)
```

## Need Help?

- Full Setup Guide: `KMS_ENCRYPTION_SETUP.md`
- Implementation Details: `fixes/KMS_ENCRYPTION_IMPLEMENTATION.md`
- Architecture: `ENCRYPTION_ARCHITECTURE.md`
