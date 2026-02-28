# Encryption & Decryption Architecture

## Overview

DataMIQ implements encryption for sensitive data including database credentials, AWS secret keys, and connection parameters. The current implementation uses **Fernet symmetric encryption** from the Python `cryptography` library.

## Current Implementation

### Encryption Service

**Location**: `backend/services/encryption_service.py`

**Algorithm**: Fernet (symmetric encryption)
- Based on AES-128 in CBC mode
- HMAC for authentication
- Timestamp for TTL support
- URL-safe base64 encoding

### Key Management

#### Development/Local Environment

The encryption key is derived using **PBKDF2** (Password-Based Key Derivation Function 2):

```python
# Key derivation parameters
password = os.getenv('ENCRYPTION_PASSWORD', 'default-dev-password-change-in-production')
salt = b'datamiq-salt-2026'  # Fixed salt (NOT SECURE for production)
iterations = 100,000
algorithm = SHA256
key_length = 32 bytes (256 bits)
```

**Configuration Options** (in order of precedence):
1. `ENCRYPTION_KEY` environment variable (base64-encoded Fernet key)
2. `ENCRYPTION_PASSWORD` environment variable (used with PBKDF2)
3. Default password: `'default-dev-password-change-in-production'`

⚠️ **Security Warning**: The default configuration uses a fixed salt and default password, which is **NOT SECURE** for production use.

### What Gets Encrypted

#### 1. AWS Secret Access Keys

**Location**: `backend/routers/bq_redshift_migration.py`

**When**: During migration creation and updates

**Storage**: `bq_redshift_migrations.aws_secret_access_key_encrypted` (TEXT column)

```python
# Encryption (on create/update)
encryption_service = get_encryption_service()
aws_secret_encrypted = encryption_service.encrypt(req.aws_secret_access_key)

# Storage
migration.aws_secret_access_key_encrypted = aws_secret_encrypted
```

**Decryption**: When migration is executed

```python
# Decryption (during execution)
encryption_service = get_encryption_service()
aws_secret_key = encryption_service.decrypt(migration.aws_secret_access_key_encrypted)
```

**Used in**:
- `orchestrator.py` - Main migration orchestration
- `pathway_c.py` - Direct GCS to S3 transfer

#### 2. Database Connection Parameters

**Location**: `backend/models/connection.py`

**Storage**: `connections.connection_params` (JSON column)

**Current Status**: ⚠️ **NOT ENCRYPTED** - Marked with TODO comments

```python
# In connections_router.py (line 523, 722)
connection_params=request.connection_params,  # TODO: Encrypt in production
```

**Contains**:
- Database passwords
- Service account credentials (JSON)
- API keys
- Connection strings

#### 3. Redshift Passwords

**Location**: `backend/services/bq_redshift_migration/pathway_c.py`

**When**: During Redshift data loading

**Decryption**:
```python
encryption_service = get_encryption_service()
target_password = encryption_service.decrypt(password_encrypted)
```

## Encryption Flow

### 1. Data Creation/Update Flow

```
User Input (Frontend)
    ↓
API Request (Plain Text)
    ↓
Backend Router
    ↓
Encryption Service.encrypt()
    ↓
Encrypted Data (Base64)
    ↓
Database Storage (TEXT/JSON column)
```

### 2. Data Retrieval/Usage Flow

```
Database Storage (Encrypted)
    ↓
Backend Service
    ↓
Encryption Service.decrypt()
    ↓
Plain Text Data
    ↓
Used in Operations (BigQuery, S3, Redshift)
```

## Security Analysis

### Current Strengths

1. **Symmetric Encryption**: Fast and efficient for application-level encryption
2. **Authenticated Encryption**: Fernet includes HMAC for integrity verification
3. **Service Abstraction**: Centralized encryption service for consistency
4. **No Plain Text Storage**: Sensitive keys are encrypted before database storage

### Current Weaknesses

1. **Fixed Salt**: Uses hardcoded salt for PBKDF2 (not secure)
2. **Default Password**: Falls back to default password if not configured
3. **No Key Rotation**: No mechanism to rotate encryption keys
4. **Single Key**: All data encrypted with same key (no key hierarchy)
5. **Connection Params Not Encrypted**: Database credentials stored in plain JSON
6. **No Audit Trail**: No logging of encryption/decryption operations
7. **Key in Environment**: Encryption key stored in environment variables (accessible to process)

### Security Risks

| Risk | Severity | Impact |
|------|----------|--------|
| Default password usage | **HIGH** | Anyone with code access can decrypt data |
| Fixed salt | **HIGH** | Reduces PBKDF2 effectiveness |
| Connection params unencrypted | **CRITICAL** | Database credentials exposed |
| No key rotation | **MEDIUM** | Compromised key affects all data |
| Single encryption key | **MEDIUM** | Key compromise exposes all secrets |
| Environment variable storage | **MEDIUM** | Process memory dump exposes key |

## Production Recommendations

### Immediate Actions (Required)

#### 1. Encrypt Connection Parameters

**File**: `backend/routers/connections_router.py`

```python
# Before storing
encryption_service = get_encryption_service()
encrypted_params = encryption_service.encrypt(json.dumps(request.connection_params))

# Store as encrypted string instead of JSON
connection.connection_params_encrypted = encrypted_params

# When retrieving
decrypted_params = encryption_service.decrypt(connection.connection_params_encrypted)
connection_params = json.loads(decrypted_params)
```

**Database Migration Required**:
```sql
-- Add new encrypted column
ALTER TABLE connections ADD COLUMN connection_params_encrypted TEXT;

-- Migrate existing data (requires encryption)
-- Then drop old column
ALTER TABLE connections DROP COLUMN connection_params;
```

#### 2. Set Strong Encryption Key

**In `.env` file**:
```bash
# Generate a new key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set in .env
ENCRYPTION_KEY=<generated-key>
```

**Never commit** `.env` to version control!

#### 3. Remove Default Password Fallback

**File**: `backend/services/encryption_service.py`

```python
# Replace default password logic with:
if not env_key:
    raise ValueError(
        "ENCRYPTION_KEY or ENCRYPTION_PASSWORD must be set in environment. "
        "Generate a key with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
    )
```

### Long-Term Improvements (Recommended)

#### 1. Migrate to AWS KMS

**Benefits**:
- Hardware security modules (HSM)
- Automatic key rotation
- Audit logging via CloudTrail
- Fine-grained access control
- Envelope encryption pattern

**Implementation**:

```python
# backend/services/aws_kms_encryption.py
import boto3
import base64

class KMSEncryptionService:
    def __init__(self, kms_key_id: str):
        self.kms_client = boto3.client('kms')
        self.kms_key_id = kms_key_id
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt using AWS KMS"""
        response = self.kms_client.encrypt(
            KeyId=self.kms_key_id,
            Plaintext=plaintext.encode()
        )
        return base64.b64encode(response['CiphertextBlob']).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt using AWS KMS"""
        ciphertext_blob = base64.b64decode(ciphertext)
        response = self.kms_client.decrypt(
            CiphertextBlob=ciphertext_blob
        )
        return response['Plaintext'].decode()
```

**Configuration**:
```bash
# .env
AWS_KMS_KEY_ID=arn:aws:kms:us-east-1:123456789:key/12345678-1234-1234-1234-123456789012
AWS_REGION=us-east-1
```

#### 2. Implement Envelope Encryption

**Pattern**: Use KMS to encrypt data keys, use data keys to encrypt data

```python
class EnvelopeEncryptionService:
    def __init__(self, kms_key_id: str):
        self.kms_client = boto3.client('kms')
        self.kms_key_id = kms_key_id
    
    def encrypt(self, plaintext: str) -> dict:
        """Encrypt using envelope encryption"""
        # Generate data key
        response = self.kms_client.generate_data_key(
            KeyId=self.kms_key_id,
            KeySpec='AES_256'
        )
        
        plaintext_key = response['Plaintext']
        encrypted_key = response['CiphertextBlob']
        
        # Encrypt data with data key
        cipher = Fernet(base64.urlsafe_b64encode(plaintext_key[:32]))
        encrypted_data = cipher.encrypt(plaintext.encode())
        
        return {
            'encrypted_data': encrypted_data.decode(),
            'encrypted_key': base64.b64encode(encrypted_key).decode()
        }
    
    def decrypt(self, encrypted_data: str, encrypted_key: str) -> str:
        """Decrypt using envelope encryption"""
        # Decrypt data key with KMS
        response = self.kms_client.decrypt(
            CiphertextBlob=base64.b64decode(encrypted_key)
        )
        plaintext_key = response['Plaintext']
        
        # Decrypt data with data key
        cipher = Fernet(base64.urlsafe_b64encode(plaintext_key[:32]))
        return cipher.decrypt(encrypted_data.encode()).decode()
```

#### 3. Use AWS Secrets Manager

**For**: Database credentials, API keys, service account credentials

**Benefits**:
- Automatic rotation
- Versioning
- Audit logging
- Fine-grained access control
- Integration with RDS, Redshift

**Implementation**:

```python
# Store secret
secrets_client = boto3.client('secretsmanager')
secrets_client.create_secret(
    Name='datamiq/connections/bigquery-prod',
    SecretString=json.dumps({
        'project_id': 'my-project',
        'credentials': {...}
    })
)

# Retrieve secret
response = secrets_client.get_secret_value(
    SecretId='datamiq/connections/bigquery-prod'
)
credentials = json.loads(response['SecretString'])
```

**Update Connection Model**:
```python
class Connection(Base):
    # Instead of storing credentials directly
    secret_arn = Column(String(255))  # ARN to Secrets Manager secret
    
    def get_credentials(self):
        """Retrieve credentials from Secrets Manager"""
        secrets_service = AWSSecretsService()
        return secrets_service.get_secret(self.secret_arn)
```

#### 4. Implement Key Rotation

**Strategy**: Support multiple encryption keys with versioning

```python
class VersionedEncryptionService:
    def __init__(self):
        self.keys = {
            'v1': Fernet(os.getenv('ENCRYPTION_KEY_V1')),
            'v2': Fernet(os.getenv('ENCRYPTION_KEY_V2')),
        }
        self.current_version = 'v2'
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt with current key version"""
        cipher = self.keys[self.current_version]
        encrypted = cipher.encrypt(plaintext.encode())
        # Prepend version
        return f"{self.current_version}:{encrypted.decode()}"
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt with appropriate key version"""
        version, encrypted_data = ciphertext.split(':', 1)
        cipher = self.keys[version]
        return cipher.decrypt(encrypted_data.encode()).decode()
    
    def rotate_key(self, old_ciphertext: str) -> str:
        """Re-encrypt with new key"""
        plaintext = self.decrypt(old_ciphertext)
        return self.encrypt(plaintext)
```

#### 5. Add Encryption Audit Logging

```python
class AuditedEncryptionService:
    def encrypt(self, plaintext: str, context: dict = None) -> str:
        """Encrypt with audit logging"""
        encrypted = self.cipher.encrypt(plaintext.encode())
        
        # Log encryption event
        audit_log.info(
            "Encryption performed",
            extra={
                'user': context.get('user'),
                'resource_type': context.get('resource_type'),
                'resource_id': context.get('resource_id'),
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        return encrypted.decode()
    
    def decrypt(self, ciphertext: str, context: dict = None) -> str:
        """Decrypt with audit logging"""
        decrypted = self.cipher.decrypt(ciphertext.encode())
        
        # Log decryption event
        audit_log.info(
            "Decryption performed",
            extra={
                'user': context.get('user'),
                'resource_type': context.get('resource_type'),
                'resource_id': context.get('resource_id'),
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        
        return decrypted.decode()
```

## Migration Path to AWS KMS

### Phase 1: Dual Encryption (Transition Period)

1. Deploy KMS encryption service alongside Fernet
2. Encrypt new data with KMS
3. Keep Fernet for decrypting old data
4. Add `encryption_version` column to track which system was used

### Phase 2: Data Migration

1. Create background job to re-encrypt all data
2. Decrypt with Fernet, re-encrypt with KMS
3. Update `encryption_version` field
4. Verify all data migrated

### Phase 3: Deprecate Fernet

1. Remove Fernet encryption code
2. Keep Fernet decryption for rollback
3. Monitor for any Fernet-encrypted data
4. After grace period, remove Fernet completely

## Best Practices

### Do's

✅ Use environment variables for encryption keys
✅ Generate strong, random encryption keys
✅ Encrypt all sensitive data before storage
✅ Use authenticated encryption (like Fernet)
✅ Implement audit logging for encryption operations
✅ Rotate encryption keys regularly
✅ Use AWS KMS for production
✅ Store secrets in AWS Secrets Manager
✅ Implement envelope encryption for large data
✅ Test encryption/decryption in CI/CD pipeline

### Don'ts

❌ Use default or hardcoded encryption keys
❌ Store encryption keys in code or version control
❌ Use fixed salts for key derivation
❌ Store sensitive data unencrypted
❌ Share encryption keys across environments
❌ Log decrypted sensitive data
❌ Expose encryption keys in error messages
❌ Use weak encryption algorithms
❌ Skip encryption for "internal" data
❌ Forget to encrypt connection parameters

## Testing Encryption

### Unit Tests

```python
def test_encryption_decryption():
    """Test encryption and decryption"""
    service = EncryptionService()
    plaintext = "my-secret-password"
    
    # Encrypt
    encrypted = service.encrypt(plaintext)
    assert encrypted != plaintext
    assert len(encrypted) > 0
    
    # Decrypt
    decrypted = service.decrypt(encrypted)
    assert decrypted == plaintext

def test_encryption_with_empty_string():
    """Test encryption handles empty strings"""
    service = EncryptionService()
    encrypted = service.encrypt("")
    assert encrypted == ""
    
    decrypted = service.decrypt("")
    assert decrypted == ""
```

### Integration Tests

```python
def test_connection_params_encryption():
    """Test connection parameters are encrypted in database"""
    # Create connection
    connection = create_connection({
        'name': 'Test Connection',
        'type': 'bigquery',
        'connection_params': {'password': 'secret123'}
    })
    
    # Verify encrypted in database
    db_connection = db.query(Connection).filter_by(id=connection.id).first()
    assert 'secret123' not in str(db_connection.connection_params_encrypted)
    
    # Verify can decrypt
    decrypted = decrypt_connection_params(db_connection)
    assert decrypted['password'] == 'secret123'
```

## Compliance Considerations

### GDPR

- Encryption at rest for personal data
- Right to erasure (delete encryption keys)
- Data breach notification (encrypted data less severe)

### HIPAA

- Encryption required for PHI
- Access controls for encryption keys
- Audit logging of access

### PCI DSS

- Strong cryptography for cardholder data
- Key management procedures
- Encryption key rotation

## Summary

### Current State

- ✅ AWS secret keys encrypted with Fernet
- ❌ Connection parameters NOT encrypted
- ❌ Using default/weak key derivation
- ❌ No key rotation
- ❌ No audit logging

### Required Actions

1. **Immediate**: Set strong `ENCRYPTION_KEY` in production
2. **High Priority**: Encrypt connection parameters
3. **High Priority**: Remove default password fallback
4. **Medium Priority**: Migrate to AWS KMS
5. **Medium Priority**: Implement key rotation
6. **Low Priority**: Add audit logging

### Production Checklist

- [ ] Generate and set strong encryption key
- [ ] Encrypt all connection parameters
- [ ] Remove default password fallback
- [ ] Test encryption/decryption in staging
- [ ] Set up AWS KMS
- [ ] Migrate to KMS encryption
- [ ] Implement key rotation
- [ ] Add encryption audit logging
- [ ] Document key management procedures
- [ ] Train team on encryption best practices

---

**Last Updated**: February 15, 2026  
**Status**: Documentation Complete - Action Required
