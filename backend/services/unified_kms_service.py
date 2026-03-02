"""
Unified KMS Encryption Service for DataMIQ

This service provides centralized encryption/decryption for all sensitive credentials:
- AWS Access Keys & Secret Keys
- GCP Service Account JSON
- GCP HMAC Access & Secret Keys
- IAM Role ARNs (stored as-is, but can be encrypted if needed)
- Database passwords
- Any other sensitive data

Architecture:
1. KMS Key ARN is stored in AWS Secrets Manager under secret name "datamiq"
2. The secret contains a JSON with key "kms_arn" pointing to the KMS key
3. All encryption/decryption uses this KMS key
4. Graceful fallback for development environments without AWS credentials

Usage:
    from services.unified_kms_service import get_unified_kms_service
    
    kms = get_unified_kms_service()
    
    # Encrypt
    encrypted = kms.encrypt_credential(
        plaintext="my-secret-key",
        credential_type="aws_secret_key",
        resource_id=123
    )
    
    # Decrypt
    plaintext = kms.decrypt_credential(
        ciphertext=encrypted,
        credential_type="aws_secret_key",
        resource_id=123
    )
"""

import os
import base64
import json
import logging
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)


class UnifiedKMSService:
    """
    Unified KMS encryption service for all DataMIQ credentials
    
    Reads KMS key ARN from AWS Secrets Manager secret "datamiq" (key: "kms_arn")
    Provides encryption/decryption with audit context for all credential types
    """
    
    # Supported credential types for audit logging
    CREDENTIAL_TYPES = {
        'aws_access_key': 'AWS Access Key ID',
        'aws_secret_key': 'AWS Secret Access Key',
        'gcp_service_account': 'GCP Service Account JSON',
        'gcp_hmac_access': 'GCP HMAC Access Key',
        'gcp_hmac_secret': 'GCP HMAC Secret Key',
        'iam_role_arn': 'IAM Role ARN',
        'database_password': 'Database Password',
        'connection_password': 'Connection Password',
        'generic': 'Generic Credential'
    }
    
    def __init__(
        self,
        secret_name: str = 'datamiq',
        region_name: str = None,
        kms_key_arn: str = None
    ):
        """
        Initialize Unified KMS Service
        
        Args:
            secret_name: Name of AWS Secrets Manager secret containing KMS ARN
                        Default: 'datamiq'
            region_name: AWS region. Defaults to AWS_REGION env var or 'us-east-1'
            kms_key_arn: Direct KMS key ARN (bypasses Secrets Manager, for testing only)
        """
        self.secret_name = secret_name
        self.region_name = region_name or os.getenv('AWS_REGION', 'us-east-1')
        self._direct_kms_key_arn = kms_key_arn
        
        # Lazy initialization
        self._secrets_client = None
        self._kms_client = None
        self._kms_key_arn_cache = None
        self._initialization_error = None
        self._aws_available = None
        
        logger.info(
            f"Unified KMS Service initialized. "
            f"Region: {self.region_name}, Secret: {self.secret_name}"
        )
    
    def _check_aws_availability(self) -> bool:
        """Check if AWS credentials are available"""
        if self._aws_available is not None:
            return self._aws_available
        
        try:
            # Try to create a client to test credentials
            test_client = boto3.client('sts', region_name=self.region_name)
            test_client.get_caller_identity()
            self._aws_available = True
            logger.info("AWS credentials available")
            return True
        except (NoCredentialsError, ClientError) as e:
            self._aws_available = False
            logger.warning(f"AWS credentials not available: {e}")
            return False
    
    @property
    def secrets_client(self):
        """Lazy initialization of Secrets Manager client"""
        if self._secrets_client is None and self._initialization_error is None:
            try:
                if not self._check_aws_availability():
                    raise ValueError("AWS credentials not configured")
                self._secrets_client = boto3.client('secretsmanager', region_name=self.region_name)
            except Exception as e:
                self._initialization_error = e
                logger.warning(f"Failed to initialize AWS Secrets Manager client: {e}")
                raise ValueError(f"AWS credentials not configured: {e}")
        if self._initialization_error:
            raise ValueError(f"AWS credentials not configured: {self._initialization_error}")
        return self._secrets_client
    
    @property
    def kms_client(self):
        """Lazy initialization of KMS client"""
        if self._kms_client is None and self._initialization_error is None:
            try:
                if not self._check_aws_availability():
                    raise ValueError("AWS credentials not configured")
                self._kms_client = boto3.client('kms', region_name=self.region_name)
            except Exception as e:
                self._initialization_error = e
                logger.warning(f"Failed to initialize AWS KMS client: {e}")
                raise ValueError(f"AWS credentials not configured: {e}")
        if self._initialization_error:
            raise ValueError(f"AWS credentials not configured: {self._initialization_error}")
        return self._kms_client
    
    def _get_kms_key_arn(self) -> str:
        """
        Retrieve KMS key ARN from AWS Secrets Manager
        
        Reads from secret "datamiq" and extracts the "kms_arn" key
        
        Returns:
            KMS key ARN
            
        Raises:
            ValueError: If KMS ARN cannot be retrieved
        """
        # Return cached value if available
        if self._kms_key_arn_cache:
            return self._kms_key_arn_cache
        
        # If direct ARN provided (testing/development), use it
        if self._direct_kms_key_arn:
            logger.debug("Using direct KMS key ARN (development mode)")
            self._kms_key_arn_cache = self._direct_kms_key_arn
            return self._direct_kms_key_arn
        
        try:
            logger.debug(f"Fetching KMS key ARN from Secrets Manager: {self.secret_name}")
            
            response = self.secrets_client.get_secret_value(SecretId=self.secret_name)
            
            if 'SecretString' not in response:
                raise ValueError(f"Secret '{self.secret_name}' does not contain SecretString")
            
            secret_string = response['SecretString']
            
            # Parse JSON
            try:
                secret_dict = json.loads(secret_string)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Secret '{self.secret_name}' is not valid JSON: {e}"
                )
            
            # Extract kms_arn
            kms_arn = secret_dict.get('kms_arn')
            if not kms_arn:
                raise ValueError(
                    f"Secret '{self.secret_name}' does not contain 'kms_arn' key. "
                    f"Available keys: {list(secret_dict.keys())}"
                )
            
            logger.info(f"Retrieved KMS key ARN from secret '{self.secret_name}'")
            self._kms_key_arn_cache = kms_arn
            return kms_arn
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'ResourceNotFoundException':
                raise ValueError(
                    f"Secret '{self.secret_name}' not found in AWS Secrets Manager. "
                    f"Please create it with:\n"
                    f"aws secretsmanager create-secret --name {self.secret_name} "
                    f"--secret-string '{{\"kms_arn\":\"arn:aws:kms:REGION:ACCOUNT:key/KEY_ID\"}}'"
                )
            elif error_code == 'AccessDeniedException':
                raise ValueError(
                    f"Access denied to secret '{self.secret_name}'. "
                    f"Ensure IAM role has 'secretsmanager:GetSecretValue' permission."
                )
            elif error_code == 'DecryptionFailure':
                raise ValueError(
                    f"Failed to decrypt secret '{self.secret_name}'. "
                    f"Check KMS key permissions for Secrets Manager."
                )
            else:
                raise ValueError(f"Failed to retrieve KMS key ARN: {str(e)}")
        
        except Exception as e:
            logger.error(f"Unexpected error retrieving KMS key ARN: {str(e)}")
            raise ValueError(f"Failed to retrieve KMS key ARN: {str(e)}")
    
    def encrypt_credential(
        self,
        plaintext: str,
        credential_type: str = 'generic',
        resource_type: str = None,
        resource_id: int = None
    ) -> str:
        """
        Encrypt a credential using AWS KMS
        
        Args:
            plaintext: Credential value to encrypt
            credential_type: Type of credential (for audit trail)
                           Options: aws_access_key, aws_secret_key, gcp_service_account,
                                   gcp_hmac_access, gcp_hmac_secret, iam_role_arn,
                                   database_password, connection_password, generic
            resource_type: Type of resource (e.g., 'migration', 'connection')
            resource_id: ID of the resource
        
        Returns:
            Base64-encoded encrypted ciphertext
            
        Raises:
            ValueError: If encryption fails or AWS not configured
        """
        if not plaintext:
            logger.debug("Empty plaintext provided, returning empty string")
            return ''
        
        # Check if AWS is available
        if not self._check_aws_availability():
            logger.warning(
                f"AWS not configured - storing {credential_type} unencrypted (development mode)"
            )
            return plaintext  # Graceful fallback for development
        
        try:
            # Get KMS key ARN
            kms_key_arn = self._get_kms_key_arn()
            
            # Build encryption context for audit trail
            encryption_context = {
                'service': 'datamiq',
                'credential_type': credential_type,
                'operation': 'encrypt'
            }
            
            if resource_type:
                encryption_context['resource_type'] = resource_type
            if resource_id:
                encryption_context['resource_id'] = str(resource_id)
            
            logger.debug(
                f"Encrypting {self.CREDENTIAL_TYPES.get(credential_type, credential_type)} "
                f"with KMS key: {kms_key_arn[:50]}..."
            )
            
            # Encrypt with KMS
            response = self.kms_client.encrypt(
                KeyId=kms_key_arn,
                Plaintext=plaintext.encode('utf-8'),
                EncryptionContext=encryption_context
            )
            
            # Encode as base64 for storage
            ciphertext_blob = response['CiphertextBlob']
            encrypted_data = base64.b64encode(ciphertext_blob).decode('utf-8')
            
            logger.info(
                f"Successfully encrypted {self.CREDENTIAL_TYPES.get(credential_type, credential_type)} "
                f"for {resource_type or 'unknown'} {resource_id or ''}"
            )
            
            return encrypted_data
        
        except ValueError:
            # Re-raise ValueError (AWS not configured, etc.)
            raise
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'NotFoundException':
                raise ValueError(f"KMS key not found: {kms_key_arn}")
            elif error_code == 'DisabledException':
                raise ValueError(f"KMS key is disabled: {kms_key_arn}")
            elif error_code == 'AccessDeniedException':
                raise ValueError(
                    f"Access denied to KMS key. "
                    f"Ensure IAM role has 'kms:Encrypt' permission."
                )
            else:
                raise ValueError(f"KMS encryption failed: {str(e)}")
        
        except Exception as e:
            logger.error(f"Unexpected encryption error: {str(e)}")
            raise ValueError(f"Encryption failed: {str(e)}")
    
    def decrypt_credential(
        self,
        ciphertext: str,
        credential_type: str = 'generic',
        resource_type: str = None,
        resource_id: int = None,
        allow_plaintext_fallback: bool = True
    ) -> str:
        """
        Decrypt a credential using AWS KMS
        
        Args:
            ciphertext: Base64-encoded encrypted credential
            credential_type: Type of credential (for audit trail)
            resource_type: Type of resource
            resource_id: ID of the resource
            allow_plaintext_fallback: If True, return ciphertext as-is if decryption fails
                                     (for backward compatibility with unencrypted data)
        
        Returns:
            Decrypted plaintext credential
            
        Raises:
            ValueError: If decryption fails and fallback not allowed
        """
        if not ciphertext:
            logger.debug("Empty ciphertext provided, returning empty string")
            return ''
        
        # Check if AWS is available
        if not self._check_aws_availability():
            if allow_plaintext_fallback:
                logger.warning(
                    f"AWS not configured - treating {credential_type} as plaintext (development mode)"
                )
                return ciphertext  # Assume it's plaintext
            else:
                raise ValueError("AWS credentials not configured and fallback not allowed")
        
        try:
            # Try to decode as base64 first
            try:
                ciphertext_blob = base64.b64decode(ciphertext)
            except Exception:
                # Not base64 - might be plaintext
                if allow_plaintext_fallback:
                    logger.warning(
                        f"Failed to decode {credential_type} as base64 - treating as plaintext"
                    )
                    return ciphertext
                else:
                    raise ValueError("Invalid base64 encoding and fallback not allowed")
            
            # Build encryption context (must match encryption)
            encryption_context = {
                'service': 'datamiq',
                'credential_type': credential_type,
                'operation': 'encrypt'  # Must match encryption operation
            }
            
            if resource_type:
                encryption_context['resource_type'] = resource_type
            if resource_id:
                encryption_context['resource_id'] = str(resource_id)
            
            logger.debug(
                f"Decrypting {self.CREDENTIAL_TYPES.get(credential_type, credential_type)}"
            )
            
            # Decrypt with KMS
            response = self.kms_client.decrypt(
                CiphertextBlob=ciphertext_blob,
                EncryptionContext=encryption_context
            )
            
            # Decode plaintext
            plaintext = response['Plaintext'].decode('utf-8')
            
            logger.info(
                f"Successfully decrypted {self.CREDENTIAL_TYPES.get(credential_type, credential_type)} "
                f"for {resource_type or 'unknown'} {resource_id or ''}"
            )
            
            return plaintext
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'InvalidCiphertextException':
                # Might be plaintext stored before encryption was enabled
                if allow_plaintext_fallback:
                    logger.warning(
                        f"Invalid ciphertext for {credential_type} - treating as plaintext (legacy data)"
                    )
                    return ciphertext
                else:
                    raise ValueError("Invalid ciphertext and fallback not allowed")
            
            elif error_code == 'AccessDeniedException':
                raise ValueError(
                    f"Access denied to KMS key. "
                    f"Ensure IAM role has 'kms:Decrypt' permission."
                )
            
            else:
                if allow_plaintext_fallback:
                    logger.warning(
                        f"KMS decryption failed for {credential_type}: {str(e)} - "
                        f"treating as plaintext"
                    )
                    return ciphertext
                else:
                    raise ValueError(f"KMS decryption failed: {str(e)}")
        
        except Exception as e:
            if allow_plaintext_fallback:
                logger.warning(
                    f"Unexpected decryption error for {credential_type}: {str(e)} - "
                    f"treating as plaintext"
                )
                return ciphertext
            else:
                raise ValueError(f"Decryption failed: {str(e)}")
    
    def is_encrypted(self, value: str) -> bool:
        """
        Check if a value appears to be encrypted (base64-encoded KMS ciphertext)
        
        Args:
            value: Value to check
        
        Returns:
            True if value appears to be encrypted, False otherwise
        """
        if not value:
            return False
        
        try:
            # Try to decode as base64
            decoded = base64.b64decode(value)
            # KMS ciphertext is typically > 100 bytes
            return len(decoded) > 100
        except Exception:
            return False


# Global instance
_unified_kms_service = None


def get_unified_kms_service() -> UnifiedKMSService:
    """
    Get or create global Unified KMS Service instance
    
    Returns:
        UnifiedKMSService instance
    """
    global _unified_kms_service
    
    if _unified_kms_service is None:
        _unified_kms_service = UnifiedKMSService()
    
    return _unified_kms_service


def reset_unified_kms_service():
    """Reset global instance (for testing)"""
    global _unified_kms_service
    _unified_kms_service = None
