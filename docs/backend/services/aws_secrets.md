# AWS Secrets Service Documentation

## Overview

The `AWSSecretsService` provides integration with AWS Secrets Manager and AWS KMS (Key Management Service) for secure credential storage and data encryption. It implements envelope encryption patterns and uses IAM roles for authentication, following AWS security best practices.

**Location**: `backend/services/aws_secrets.py`

## Purpose

- Store and retrieve secrets from AWS Secrets Manager
- Encrypt/decrypt data using AWS KMS
- Implement envelope encryption for database connection strings
- Generate data encryption keys
- Use IAM roles for authentication (no hardcoded credentials)

## Dependencies

```python
import os
import json
import base64
import logging
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError
```

**External Libraries**:
- `boto3`: AWS SDK for Python (install: `uv pip install boto3`)
- `botocore`: AWS core library (installed with boto3)

## Configuration

### Environment Variables

Configure AWS services in `backend/.env`:

```bash
# AWS Configuration
AWS_REGION=us-east-1
KMS_KEY_ID=arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012
```

### IAM Role Requirements

The EC2/ECS instance must have an IAM role with these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:CreateSecret",
        "secretsmanager:PutSecretValue",
        "secretsmanager:UpdateSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:*:secret:datamiq/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:GenerateDataKey",
        "kms:DescribeKey"
      ],
      "Resource": "arn:aws:kms:us-east-1:*:key/*"
    }
  ]
}
```

## Class Definition

```python
class AWSSecretsService:
    """Service for AWS Secrets Manager and KMS operations"""
    
    def __init__(self):
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        self.kms_key_id = os.getenv('KMS_KEY_ID')
        self.secrets_client = boto3.client('secretsmanager', region_name=self.region)
        self.kms_client = boto3.client('kms', region_name=self.region)
```

## Methods

### get_secret()

Retrieves a secret from AWS Secrets Manager.

**Signature**:
```python
def get_secret(self, secret_name: str) -> Optional[Dict[str, Any]]
```

**Parameters**:
- `secret_name` (str): Name or ARN of the secret

**Returns**:
- `Dict[str, Any]`: Secret data as dictionary
- `None`: If secret not found or error occurred

**Error Handling**:
- Logs warnings for not found secrets
- Logs errors for access denied, decryption failures
- Returns None on any error (graceful degradation)

**Example**:
```python
from backend.services.aws_secrets import aws_secrets_service

# Get database credentials
secret = aws_secrets_service.get_secret('datamiq/db-credentials')

if secret:
    db_host = secret['host']
    db_user = secret['username']
    db_password = secret['password']
    db_name = secret['database']
    
    connection_string = f"postgresql://{db_user}:{db_password}@{db_host}/{db_name}"
else:
    print("Failed to retrieve secret")

# Get API keys
api_secret = aws_secrets_service.get_secret('datamiq/api-keys')
if api_secret:
    stripe_key = api_secret['stripe_api_key']
    sendgrid_key = api_secret['sendgrid_api_key']
```

**Secret Format in AWS Secrets Manager**:
```json
{
  "host": "db.example.com",
  "port": "5432",
  "username": "dbuser",
  "password": "SecurePassword123!",
  "database": "datamiq"
}
```

---

### create_or_update_secret()

Creates a new secret or updates an existing one in AWS Secrets Manager.

**Signature**:
```python
def create_or_update_secret(
    self,
    secret_name: str,
    secret_data: Dict[str, Any],
    description: Optional[str] = None
) -> bool
```

**Parameters**:
- `secret_name` (str): Name of the secret
- `secret_data` (Dict[str, Any]): Secret data as dictionary
- `description` (Optional[str]): Optional description

**Returns**:
- `bool`: True if successful, False otherwise

**Example**:
```python
from backend.services.aws_secrets import aws_secrets_service

# Create database credentials secret
db_credentials = {
    "host": "db.example.com",
    "port": "5432",
    "username": "dbuser",
    "password": "SecurePassword123!",
    "database": "datamiq"
}

success = aws_secrets_service.create_or_update_secret(
    secret_name='datamiq/db-credentials',
    secret_data=db_credentials,
    description='Database credentials for DataMIQ application'
)

if success:
    print("Secret created/updated successfully")
else:
    print("Failed to create/update secret")

# Update API keys
api_keys = {
    "stripe_api_key": "sk_live_...",
    "sendgrid_api_key": "SG...."
}

aws_secrets_service.create_or_update_secret(
    secret_name='datamiq/api-keys',
    secret_data=api_keys,
    description='Third-party API keys'
)
```

---

### encrypt_with_kms()

Encrypts data using AWS KMS.

**Signature**:
```python
def encrypt_with_kms(self, plaintext: str) -> Optional[str]
```

**Parameters**:
- `plaintext` (str): Data to encrypt (max 4KB for direct KMS encryption)

**Returns**:
- `str`: Base64-encoded encrypted data
- `None`: If encryption failed

**Encryption Method**: Direct KMS encryption (suitable for data < 4KB)

**Example**:
```python
from backend.services.aws_secrets import aws_secrets_service

# Encrypt database connection string
connection_string = "postgresql://user:pass@host:5432/db"
encrypted = aws_secrets_service.encrypt_with_kms(connection_string)

if encrypted:
    print(f"Encrypted: {encrypted[:50]}...")
    # Store encrypted data in database
    connection_repo.save_encrypted_connection(encrypted)
else:
    print("Encryption failed")

# Encrypt API token
api_token = "secret_token_12345"
encrypted_token = aws_secrets_service.encrypt_with_kms(api_token)
```

**Usage in Database Connection Storage**:
```python
def save_database_connection(name: str, connection_string: str):
    """Save database connection with encrypted credentials"""
    
    # Encrypt connection string
    encrypted = aws_secrets_service.encrypt_with_kms(connection_string)
    
    if not encrypted:
        raise EncryptionError("Failed to encrypt connection string")
    
    # Store encrypted connection in database
    connection = Connection(
        name=name,
        encrypted_connection_string=encrypted,
        created_at=datetime.utcnow()
    )
    db.add(connection)
    db.commit()
    
    return connection
```

---

### decrypt_with_kms()

Decrypts data using AWS KMS.

**Signature**:
```python
def decrypt_with_kms(self, encrypted_data: str) -> Optional[str]
```

**Parameters**:
- `encrypted_data` (str): Base64-encoded encrypted data

**Returns**:
- `str`: Decrypted plaintext
- `None`: If decryption failed

**Example**:
```python
from backend.services.aws_secrets import aws_secrets_service

# Decrypt database connection string
encrypted = "AQICAHh..."  # From database
decrypted = aws_secrets_service.decrypt_with_kms(encrypted)

if decrypted:
    print(f"Connection string: {decrypted}")
    # Use decrypted connection string
    engine = create_engine(decrypted)
else:
    print("Decryption failed")
```

**Usage in Database Connection Retrieval**:
```python
def get_database_connection(connection_id: int):
    """Get database connection with decrypted credentials"""
    
    # Get connection from database
    connection = connection_repo.get_by_id(connection_id)
    
    if not connection:
        raise NotFoundError("Connection not found")
    
    # Decrypt connection string
    decrypted = aws_secrets_service.decrypt_with_kms(
        connection.encrypted_connection_string
    )
    
    if not decrypted:
        raise DecryptionError("Failed to decrypt connection string")
    
    return {
        "id": connection.id,
        "name": connection.name,
        "connection_string": decrypted
    }
```

---

### generate_data_key()

Generates a data encryption key using KMS for envelope encryption.

**Signature**:
```python
def generate_data_key(self) -> Optional[Dict[str, bytes]]
```

**Parameters**:
- None

**Returns**:
- `Dict[str, bytes]`: Dictionary with 'plaintext' and 'ciphertext' keys
  - `plaintext`: Unencrypted 256-bit AES key (use for encryption, then discard)
  - `ciphertext`: Encrypted data key (store this)
- `None`: If generation failed

**Envelope Encryption Pattern**:
1. Generate data key from KMS
2. Use plaintext key to encrypt data
3. Store encrypted data + encrypted key
4. Discard plaintext key
5. To decrypt: decrypt data key with KMS, then decrypt data

**Example**:
```python
from backend.services.aws_secrets import aws_secrets_service
from cryptography.fernet import Fernet
import base64

# Generate data key
keys = aws_secrets_service.generate_data_key()

if keys:
    plaintext_key = keys['plaintext']
    encrypted_key = keys['ciphertext']
    
    # Use plaintext key for encryption
    fernet_key = base64.urlsafe_b64encode(plaintext_key[:32])
    cipher = Fernet(fernet_key)
    
    # Encrypt large data
    large_data = "..." * 10000  # Large dataset
    encrypted_data = cipher.encrypt(large_data.encode())
    
    # Store encrypted data + encrypted key
    storage = {
        "encrypted_data": base64.b64encode(encrypted_data).decode(),
        "encrypted_key": base64.b64encode(encrypted_key).decode()
    }
    
    # Discard plaintext key (security best practice)
    del plaintext_key
```

**Decryption with Envelope Encryption**:
```python
# Retrieve encrypted data and key
encrypted_data = base64.b64decode(storage["encrypted_data"])
encrypted_key = base64.b64decode(storage["encrypted_key"])

# Decrypt data key with KMS
response = aws_secrets_service.kms_client.decrypt(
    CiphertextBlob=encrypted_key
)
plaintext_key = response['Plaintext']

# Use plaintext key to decrypt data
fernet_key = base64.urlsafe_b64encode(plaintext_key[:32])
cipher = Fernet(fernet_key)
decrypted_data = cipher.decrypt(encrypted_data).decode()

# Discard plaintext key
del plaintext_key
```

---

### encrypt_database_connection_string()

Convenience method to encrypt database connection strings.

**Signature**:
```python
def encrypt_database_connection_string(self, connection_string: str) -> Optional[str]
```

**Parameters**:
- `connection_string` (str): Database connection string

**Returns**:
- `str`: Encrypted connection string (base64)
- `None`: If encryption failed

**Example**:
```python
from backend.services.aws_secrets import aws_secrets_service

# Encrypt PostgreSQL connection string
connection_string = "postgresql://user:password@host:5432/database"
encrypted = aws_secrets_service.encrypt_database_connection_string(connection_string)

# Store in database
connection = Connection(
    name="Production DB",
    type="postgresql",
    encrypted_connection_string=encrypted
)
db.add(connection)
db.commit()
```

---

### decrypt_database_connection_string()

Convenience method to decrypt database connection strings.

**Signature**:
```python
def decrypt_database_connection_string(self, encrypted_connection_string: str) -> Optional[str]
```

**Parameters**:
- `encrypted_connection_string` (str): Encrypted connection string (base64)

**Returns**:
- `str`: Decrypted connection string
- `None`: If decryption failed

**Example**:
```python
from backend.services.aws_secrets import aws_secrets_service

# Get connection from database
connection = connection_repo.get_by_id(connection_id)

# Decrypt connection string
connection_string = aws_secrets_service.decrypt_database_connection_string(
    connection.encrypted_connection_string
)

# Use connection string
from sqlalchemy import create_engine
engine = create_engine(connection_string)
```

## Global Instance and Convenience Functions

### Global Instance

```python
from backend.services.aws_secrets import aws_secrets_service

# Use global instance
secret = aws_secrets_service.get_secret('my-secret')
```

### Convenience Functions

```python
from backend.services.aws_secrets import get_secret, encrypt_data, decrypt_data

# Get secret
db_creds = get_secret('datamiq/db-credentials')

# Encrypt data
encrypted = encrypt_data("sensitive data")

# Decrypt data
decrypted = decrypt_data(encrypted)
```

## Complete Usage Examples

### Database Connection Management

```python
from backend.services.aws_secrets import aws_secrets_service
from backend.repositories.connection_repository import ConnectionRepository

class ConnectionService:
    """Service for managing database connections"""
    
    def __init__(self):
        self.aws_secrets = aws_secrets_service
        self.connection_repo = ConnectionRepository()
    
    def create_connection(
        self,
        name: str,
        db_type: str,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        workspace_id: int
    ):
        """Create database connection with encrypted credentials"""
        
        # Build connection string
        connection_string = f"{db_type}://{username}:{password}@{host}:{port}/{database}"
        
        # Encrypt connection string
        encrypted = self.aws_secrets.encrypt_database_connection_string(connection_string)
        
        if not encrypted:
            raise EncryptionError("Failed to encrypt connection string")
        
        # Store in database
        connection = self.connection_repo.create(
            name=name,
            type=db_type,
            encrypted_connection_string=encrypted,
            workspace_id=workspace_id
        )
        
        return connection
    
    def get_connection_string(self, connection_id: int) -> str:
        """Get decrypted connection string"""
        
        # Get connection from database
        connection = self.connection_repo.get_by_id(connection_id)
        
        if not connection:
            raise NotFoundError("Connection not found")
        
        # Decrypt connection string
        connection_string = self.aws_secrets.decrypt_database_connection_string(
            connection.encrypted_connection_string
        )
        
        if not connection_string:
            raise DecryptionError("Failed to decrypt connection string")
        
        return connection_string
    
    def test_connection(self, connection_id: int) -> bool:
        """Test database connection"""
        
        # Get decrypted connection string
        connection_string = self.get_connection_string(connection_id)
        
        # Test connection
        try:
            from sqlalchemy import create_engine
            engine = create_engine(connection_string)
            with engine.connect() as conn:
                conn.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False
```

### Application Initialization with Secrets Manager

```python
from backend.services.aws_secrets import get_secret
import os

def initialize_application():
    """Initialize application with secrets from AWS Secrets Manager"""
    
    # Get database credentials
    db_secret = get_secret('datamiq/db-credentials')
    
    if db_secret:
        os.environ['DB_HOST'] = db_secret['host']
        os.environ['DB_PORT'] = str(db_secret['port'])
        os.environ['DB_USER'] = db_secret['username']
        os.environ['DB_PASSWORD'] = db_secret['password']
        os.environ['DB_NAME'] = db_secret['database']
    
    # Get Redis credentials
    redis_secret = get_secret('datamiq/redis-credentials')
    
    if redis_secret:
        os.environ['REDIS_HOST'] = redis_secret['host']
        os.environ['REDIS_PORT'] = str(redis_secret['port'])
        os.environ['REDIS_PASSWORD'] = redis_secret['password']
    
    # Get API keys
    api_secret = get_secret('datamiq/api-keys')
    
    if api_secret:
        os.environ['STRIPE_API_KEY'] = api_secret['stripe_api_key']
        os.environ['SENDGRID_API_KEY'] = api_secret['sendgrid_api_key']
    
    print("Application initialized with secrets from AWS Secrets Manager")
```

### Setup Script for Initial Deployment

```python
from backend.services.aws_secrets import aws_secrets_service

def setup_secrets():
    """Setup initial secrets in AWS Secrets Manager"""
    
    # Create database credentials secret
    db_credentials = {
        "host": "db.example.com",
        "port": "5432",
        "username": "datamiq_user",
        "password": "GeneratedSecurePassword123!",
        "database": "datamiq"
    }
    
    success = aws_secrets_service.create_or_update_secret(
        secret_name='datamiq/db-credentials',
        secret_data=db_credentials,
        description='Database credentials for DataMIQ'
    )
    
    if success:
        print("✓ Database credentials secret created")
    else:
        print("✗ Failed to create database credentials secret")
    
    # Create Redis credentials secret
    redis_credentials = {
        "host": "redis.example.com",
        "port": "6379",
        "password": "RedisSecurePassword123!"
    }
    
    success = aws_secrets_service.create_or_update_secret(
        secret_name='datamiq/redis-credentials',
        secret_data=redis_credentials,
        description='Redis credentials for DataMIQ'
    )
    
    if success:
        print("✓ Redis credentials secret created")
    else:
        print("✗ Failed to create Redis credentials secret")
    
    # Create API keys secret
    api_keys = {
        "stripe_api_key": "sk_live_...",
        "sendgrid_api_key": "SG....",
        "jwt_secret_key": "GeneratedJWTSecret123!"
    }
    
    success = aws_secrets_service.create_or_update_secret(
        secret_name='datamiq/api-keys',
        secret_data=api_keys,
        description='Third-party API keys for DataMIQ'
    )
    
    if success:
        print("✓ API keys secret created")
    else:
        print("✗ Failed to create API keys secret")

if __name__ == "__main__":
    setup_secrets()
```

## Security Considerations

### IAM Role Authentication
- **No Hardcoded Credentials**: Uses IAM role attached to EC2/ECS instance
- **Automatic Rotation**: IAM role credentials rotate automatically
- **Least Privilege**: Grant only required permissions

### Encryption Best Practices
- **Envelope Encryption**: Use for large data (> 4KB)
- **Direct KMS**: Use for small data (< 4KB)
- **Key Rotation**: Enable automatic key rotation in KMS
- **Audit Logging**: Enable CloudTrail for KMS and Secrets Manager

### Secret Management
- **Never Log Secrets**: Never log decrypted secrets or credentials
- **Minimize Exposure**: Decrypt only when needed, discard immediately
- **Access Control**: Use IAM policies to restrict secret access
- **Versioning**: Secrets Manager supports versioning

### Data Protection
- **Encryption at Rest**: KMS encrypts data at rest
- **Encryption in Transit**: TLS for all AWS API calls
- **No Plaintext Storage**: Never store plaintext credentials in database

## Performance Considerations

### Caching Decrypted Secrets
```python
from functools import lru_cache
from datetime import datetime, timedelta

class CachedSecretsService:
    """Service with secret caching"""
    
    def __init__(self):
        self.aws_secrets = aws_secrets_service
        self.cache = {}
        self.cache_ttl = timedelta(minutes=5)
    
    def get_secret_cached(self, secret_name: str):
        """Get secret with caching"""
        
        # Check cache
        if secret_name in self.cache:
            cached_data, cached_time = self.cache[secret_name]
            if datetime.utcnow() - cached_time < self.cache_ttl:
                return cached_data
        
        # Fetch from AWS
        secret = self.aws_secrets.get_secret(secret_name)
        
        # Cache result
        if secret:
            self.cache[secret_name] = (secret, datetime.utcnow())
        
        return secret
```

### Batch Operations
```python
# Encrypt multiple connection strings in batch
connections = [...]
encrypted_connections = []

for conn in connections:
    encrypted = aws_secrets_service.encrypt_database_connection_string(
        conn.connection_string
    )
    encrypted_connections.append(encrypted)
```

### KMS Request Limits
- **Rate Limits**: KMS has rate limits (varies by region)
- **Batching**: Batch operations when possible
- **Caching**: Cache decrypted data keys for envelope encryption

## Error Handling

### Common Errors

```python
from botocore.exceptions import ClientError

try:
    secret = aws_secrets_service.get_secret('my-secret')
except ClientError as e:
    error_code = e.response['Error']['Code']
    
    if error_code == 'ResourceNotFoundException':
        print("Secret not found")
    elif error_code == 'AccessDeniedException':
        print("Access denied - check IAM permissions")
    elif error_code == 'DecryptionFailure':
        print("Decryption failed - check KMS key")
    else:
        print(f"AWS error: {error_code}")
```

## Testing

### Unit Tests

```python
import pytest
from unittest.mock import Mock, patch
from backend.services.aws_secrets import AWSSecretsService

@pytest.fixture
def aws_service():
    """Create AWSSecretsService instance for testing"""
    return AWSSecretsService()

@patch('boto3.client')
def test_get_secret_success(mock_boto_client, aws_service):
    """Test successful secret retrieval"""
    
    # Mock Secrets Manager response
    mock_client = Mock()
    mock_client.get_secret_value.return_value = {
        'SecretString': '{"username": "testuser", "password": "testpass"}'
    }
    mock_boto_client.return_value = mock_client
    
    # Get secret
    secret = aws_service.get_secret('test-secret')
    
    assert secret is not None
    assert secret['username'] == 'testuser'
    assert secret['password'] == 'testpass'

@patch('boto3.client')
def test_encrypt_decrypt_roundtrip(mock_boto_client, aws_service):
    """Test encryption and decryption"""
    
    # Mock KMS responses
    mock_client = Mock()
    mock_client.encrypt.return_value = {
        'CiphertextBlob': b'encrypted_data'
    }
    mock_client.decrypt.return_value = {
        'Plaintext': b'test data'
    }
    mock_boto_client.return_value = mock_client
    
    # Encrypt
    plaintext = "test data"
    encrypted = aws_service.encrypt_with_kms(plaintext)
    
    assert encrypted is not None
    
    # Decrypt
    decrypted = aws_service.decrypt_with_kms(encrypted)
    
    assert decrypted == plaintext
```

## Related Documentation

- [Security Standards](../../../.kiro/steering/security-standards.md) - Security guidelines
- [Configuration Management](../../../.kiro/steering/configuration-management.md) - Configuration best practices
- [AWS Deployment](../../../.kiro/steering/aws-deployment.md) - AWS deployment guide
- [Database Architecture](../../../.kiro/steering/database-architecture.md) - Database encryption

## Troubleshooting

### Issue: "Access Denied" errors
**Solution**: Check IAM role has required permissions for Secrets Manager and KMS.

### Issue: "KMS key not found"
**Solution**: Verify KMS_KEY_ID in `.env` is correct and key exists in the region.

### Issue: Decryption fails
**Solution**: Ensure encrypted data was encrypted with the same KMS key.

### Issue: Boto3 import error
**Solution**: Install boto3: `uv pip install boto3`

### Issue: Secrets not found
**Solution**: Verify secret name is correct and exists in AWS Secrets Manager.

---

**Last Updated**: 2026-01-25  
**Version**: 1.0  
**Status**: Production Ready
