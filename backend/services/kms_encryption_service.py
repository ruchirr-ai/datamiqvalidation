"""
AWS KMS Encryption Service

Production-grade encryption service using AWS KMS for encryption/decryption
and AWS Secrets Manager for storing the KMS key ID.

This service:
1. Retrieves KMS key ID from AWS Secrets Manager on each operation
2. Uses AWS KMS for encryption/decryption
3. Provides audit logging
4. Handles errors gracefully with fallback mechanisms
"""

import os
import base64
import logging
import json
from typing import Optional
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class KMSEncryptionService:
    """
    Production encryption service using AWS KMS
    
    Architecture:
    - KMS Key ID stored in AWS Secrets Manager
    - Each encrypt/decrypt operation fetches key ID from Secrets Manager
    - Uses AWS KMS for actual encryption/decryption
    - Provides comprehensive error handling and logging
    """
    
    def __init__(
        self,
        secret_name: str = None,
        region_name: str = None,
        kms_key_id: str = None
    ):
        """
        Initialize KMS encryption service
        
        Args:
            secret_name: Name of secret in Secrets Manager containing KMS key ID
                        Defaults to ENCRYPTION_SECRET_NAME env var or 'datamiq/encryption/kms-key-id'
            region_name: AWS region. Defaults to AWS_REGION env var or 'us-east-1'
            kms_key_id: Direct KMS key ID (bypasses Secrets Manager). For testing only.
        """
        self.region_name = region_name or os.getenv('AWS_REGION', 'us-east-1')
        self.secret_name = secret_name or os.getenv(
            'ENCRYPTION_SECRET_NAME',
            'datamiq/encryption/kms-key-id'
        )
        self._direct_kms_key_id = kms_key_id  # For testing/development only
        
        # Initialize AWS clients
        self.secrets_client = boto3.client('secretsmanager', region_name=self.region_name)
        self.kms_client = boto3.client('kms', region_name=self.region_name)
        
        logger.info(
            f"KMS Encryption Service initialized. "
            f"Region: {self.region_name}, Secret: {self.secret_name}"
        )
    
    def _get_kms_key_id(self) -> str:
        """
        Retrieve KMS key ID from AWS Secrets Manager
        
        Returns:
            KMS key ID (ARN or alias)
            
        Raises:
            ValueError: If key ID cannot be retrieved
        """
        # If direct key ID provided (testing/development), use it
        if self._direct_kms_key_id:
            logger.debug("Using direct KMS key ID (development mode)")
            return self._direct_kms_key_id
        
        try:
            logger.debug(f"Fetching KMS key ID from Secrets Manager: {self.secret_name}")
            
            response = self.secrets_client.get_secret_value(SecretId=self.secret_name)
            
            # Parse secret value
            if 'SecretString' in response:
                secret = response['SecretString']
                
                # Try to parse as JSON first
                try:
                    secret_dict = json.loads(secret)
                    kms_key_id = secret_dict.get('kms_key_id') or secret_dict.get('KeyId')
                    
                    if not kms_key_id:
                        raise ValueError(
                            f"Secret {self.secret_name} does not contain 'kms_key_id' or 'KeyId' field"
                        )
                    
                    logger.debug(f"Retrieved KMS key ID from JSON secret")
                    return kms_key_id
                    
                except json.JSONDecodeError:
                    # Secret is plain text (just the key ID)
                    logger.debug(f"Retrieved KMS key ID from plain text secret")
                    return secret.strip()
            else:
                raise ValueError(f"Secret {self.secret_name} does not contain SecretString")
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'ResourceNotFoundException':
                logger.error(f"Secret not found: {self.secret_name}")
                raise ValueError(
                    f"Encryption secret '{self.secret_name}' not found in Secrets Manager. "
                    f"Please create it with: aws secretsmanager create-secret "
                    f"--name {self.secret_name} --secret-string '{{\"kms_key_id\":\"your-kms-key-id\"}}'"
                )
            
            elif error_code == 'AccessDeniedException':
                logger.error(f"Access denied to secret: {self.secret_name}")
                raise ValueError(
                    f"Access denied to secret '{self.secret_name}'. "
                    f"Ensure IAM role has secretsmanager:GetSecretValue permission."
                )
            
            elif error_code == 'DecryptionFailure':
                logger.error(f"Failed to decrypt secret: {self.secret_name}")
                raise ValueError(
                    f"Failed to decrypt secret '{self.secret_name}'. "
                    f"Check KMS key permissions."
                )
            
            else:
                logger.error(f"Error retrieving secret: {str(e)}")
                raise ValueError(f"Failed to retrieve KMS key ID: {str(e)}")
        
        except Exception as e:
            logger.error(f"Unexpected error retrieving KMS key ID: {str(e)}")
            raise ValueError(f"Failed to retrieve KMS key ID: {str(e)}")
    
    def encrypt(self, plaintext: str, context: Optional[dict] = None) -> str:
        """
        Encrypt plaintext using AWS KMS
        
        Args:
            plaintext: String to encrypt
            context: Optional encryption context for audit trail
                    Example: {'resource_type': 'connection', 'resource_id': '123'}
        
        Returns:
            Base64-encoded encrypted ciphertext
            
        Raises:
            ValueError: If encryption fails
        """
        if not plaintext:
            logger.debug("Empty plaintext provided, returning empty string")
            return ''
        
        try:
            # Get KMS key ID from Secrets Manager
            kms_key_id = self._get_kms_key_id()
            
            # Prepare encryption context for audit trail
            encryption_context = {}
            if context:
                # Add user-provided context
                encryption_context.update(context)
            
            # Add service context
            encryption_context['service'] = 'datamiq'
            encryption_context['operation'] = 'encrypt'
            
            logger.debug(
                f"Encrypting data with KMS key: {kms_key_id[:20]}... "
                f"Context: {encryption_context}"
            )
            
            # Encrypt with KMS
            response = self.kms_client.encrypt(
                KeyId=kms_key_id,
                Plaintext=plaintext.encode('utf-8'),
                EncryptionContext=encryption_context
            )
            
            # Encode ciphertext as base64 for storage
            ciphertext_blob = response['CiphertextBlob']
            encrypted_data = base64.b64encode(ciphertext_blob).decode('utf-8')
            
            logger.info(
                f"Successfully encrypted data. "
                f"Context: {encryption_context.get('resource_type', 'unknown')}"
            )
            
            return encrypted_data
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'NotFoundException':
                logger.error(f"KMS key not found: {kms_key_id}")
                raise ValueError(f"KMS key not found. Check KMS_KEY_ID configuration.")
            
            elif error_code == 'DisabledException':
                logger.error(f"KMS key is disabled: {kms_key_id}")
                raise ValueError(f"KMS key is disabled. Enable the key in AWS console.")
            
            elif error_code == 'AccessDeniedException':
                logger.error(f"Access denied to KMS key: {kms_key_id}")
                raise ValueError(
                    f"Access denied to KMS key. "
                    f"Ensure IAM role has kms:Encrypt permission."
                )
            
            else:
                logger.error(f"KMS encryption error: {str(e)}")
                raise ValueError(f"Encryption failed: {str(e)}")
        
        except Exception as e:
            logger.error(f"Unexpected encryption error: {str(e)}")
            raise ValueError(f"Encryption failed: {str(e)}")
    
    def decrypt(self, ciphertext: str, context: Optional[dict] = None) -> str:
        """
        Decrypt ciphertext using AWS KMS
        
        Args:
            ciphertext: Base64-encoded encrypted string
            context: Optional encryption context (must match encryption context)
        
        Returns:
            Decrypted plaintext string
            
        Raises:
            ValueError: If decryption fails
        """
        if not ciphertext:
            logger.debug("Empty ciphertext provided, returning empty string")
            return ''
        
        try:
            # Decode base64 ciphertext
            ciphertext_blob = base64.b64decode(ciphertext)
            
            # Prepare encryption context (must match encryption)
            encryption_context = {}
            if context:
                encryption_context.update(context)
            
            # Add service context
            encryption_context['service'] = 'datamiq'
            encryption_context['operation'] = 'encrypt'  # Must match encryption operation
            
            logger.debug(
                f"Decrypting data with KMS. "
                f"Context: {encryption_context}"
            )
            
            # Decrypt with KMS
            # Note: KMS automatically determines which key to use from the ciphertext
            response = self.kms_client.decrypt(
                CiphertextBlob=ciphertext_blob,
                EncryptionContext=encryption_context
            )
            
            # Decode plaintext
            plaintext = response['Plaintext'].decode('utf-8')
            
            logger.info(
                f"Successfully decrypted data. "
                f"Context: {encryption_context.get('resource_type', 'unknown')}"
            )
            
            return plaintext
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'NotFoundException':
                logger.error("KMS key not found for decryption")
                raise ValueError("KMS key not found. Data may be encrypted with deleted key.")
            
            elif error_code == 'DisabledException':
                logger.error("KMS key is disabled")
                raise ValueError("KMS key is disabled. Enable the key to decrypt data.")
            
            elif error_code == 'InvalidCiphertextException':
                logger.error("Invalid ciphertext for decryption")
                raise ValueError(
                    "Invalid ciphertext. Data may be corrupted or encrypted with different key."
                )
            
            elif error_code == 'AccessDeniedException':
                logger.error("Access denied for KMS decryption")
                raise ValueError(
                    "Access denied to KMS key. "
                    "Ensure IAM role has kms:Decrypt permission."
                )
            
            elif error_code == 'InvalidGrantTokenException':
                logger.error("Encryption context mismatch")
                raise ValueError(
                    "Encryption context mismatch. "
                    "Provided context does not match encryption context."
                )
            
            else:
                logger.error(f"KMS decryption error: {str(e)}")
                raise ValueError(f"Decryption failed: {str(e)}")
        
        except Exception as e:
            logger.error(f"Unexpected decryption error: {str(e)}")
            raise ValueError(f"Decryption failed: {str(e)}")
    
    def rotate_key(self, old_ciphertext: str, context: Optional[dict] = None) -> str:
        """
        Re-encrypt data with current KMS key (for key rotation)
        
        Args:
            old_ciphertext: Previously encrypted data
            context: Encryption context
        
        Returns:
            Re-encrypted ciphertext with current key
        """
        try:
            # Decrypt with old key
            plaintext = self.decrypt(old_ciphertext, context)
            
            # Re-encrypt with current key
            new_ciphertext = self.encrypt(plaintext, context)
            
            logger.info("Successfully rotated encryption key for data")
            
            return new_ciphertext
        
        except Exception as e:
            logger.error(f"Key rotation failed: {str(e)}")
            raise ValueError(f"Key rotation failed: {str(e)}")


# Global instance
_kms_encryption_service = None


def get_kms_encryption_service() -> KMSEncryptionService:
    """
    Get or create global KMS encryption service instance
    
    Returns:
        KMSEncryptionService instance
    """
    global _kms_encryption_service
    
    if _kms_encryption_service is None:
        _kms_encryption_service = KMSEncryptionService()
    
    return _kms_encryption_service


def reset_kms_encryption_service():
    """Reset global instance (for testing)"""
    global _kms_encryption_service
    _kms_encryption_service = None
