"""
AWS Secrets Manager and KMS Integration Service
Handles encryption/decryption and secrets management using AWS services
"""

import os
import json
import base64
import logging
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class AWSSecretsService:
    """Service for AWS Secrets Manager and KMS operations"""
    
    def __init__(self):
        """Initialize AWS clients using IAM role (no explicit credentials needed)"""
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        self.kms_key_id = os.getenv('KMS_KEY_ID')
        
        # Initialize clients (uses IAM role attached to EC2/ECS instance)
        self.secrets_client = boto3.client('secretsmanager', region_name=self.region)
        self.kms_client = boto3.client('kms', region_name=self.region)
        
        logger.info(f"AWS Secrets Service initialized for region: {self.region}")
    
    def get_secret(self, secret_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve secret from AWS Secrets Manager
        
        Args:
            secret_name: Name or ARN of the secret
            
        Returns:
            Dict containing secret data, or None if not found
            
        Example:
            >>> service = AWSSecretsService()
            >>> secret = service.get_secret('datamiq/db-credentials')
            >>> secret['username']
            'db_user'
        """
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_name)
            
            # Parse secret based on type
            if 'SecretString' in response:
                secret_data = json.loads(response['SecretString'])
                logger.info(f"Retrieved secret: {secret_name}")
                return secret_data
            elif 'SecretBinary' in response:
                secret_data = base64.b64decode(response['SecretBinary'])
                logger.info(f"Retrieved binary secret: {secret_name}")
                return {'binary': secret_data}
            else:
                logger.warning(f"Secret {secret_name} has no data")
                return None
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'ResourceNotFoundException':
                logger.warning(f"Secret not found: {secret_name}")
            elif error_code == 'InvalidRequestException':
                logger.error(f"Invalid request for secret: {secret_name}")
            elif error_code == 'InvalidParameterException':
                logger.error(f"Invalid parameter for secret: {secret_name}")
            elif error_code == 'DecryptionFailure':
                logger.error(f"Decryption failed for secret: {secret_name}")
            elif error_code == 'AccessDeniedException':
                logger.error(f"Access denied to secret: {secret_name}")
            else:
                logger.error(f"Error retrieving secret {secret_name}: {str(e)}")
            
            return None
        
        except Exception as e:
            logger.error(f"Unexpected error retrieving secret {secret_name}: {str(e)}")
            return None
    
    def create_or_update_secret(
        self,
        secret_name: str,
        secret_data: Dict[str, Any],
        description: Optional[str] = None
    ) -> bool:
        """
        Create or update a secret in AWS Secrets Manager
        
        Args:
            secret_name: Name of the secret
            secret_data: Dict containing secret data
            description: Optional description
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            secret_string = json.dumps(secret_data)
            
            # Try to create the secret
            try:
                self.secrets_client.create_secret(
                    Name=secret_name,
                    SecretString=secret_string,
                    Description=description or f"Secret for {secret_name}"
                )
                logger.info(f"Created secret: {secret_name}")
                return True
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceExistsException':
                    # Update existing secret
                    self.secrets_client.put_secret_value(
                        SecretId=secret_name,
                        SecretString=secret_string
                    )
                    logger.info(f"Updated secret: {secret_name}")
                    return True
                else:
                    raise
                    
        except Exception as e:
            logger.error(f"Error creating/updating secret {secret_name}: {str(e)}")
            return False
    
    def encrypt_with_kms(self, plaintext: str) -> Optional[str]:
        """
        Encrypt data using AWS KMS
        
        Uses envelope encryption pattern:
        1. Generate data key from KMS
        2. Encrypt plaintext with data key
        3. Return encrypted data + encrypted data key
        
        Args:
            plaintext: Data to encrypt
            
        Returns:
            Base64-encoded encrypted data, or None if failed
            
        Example:
            >>> service = AWSSecretsService()
            >>> encrypted = service.encrypt_with_kms("my-secret-data")
            >>> encrypted
            'AQICAHh...'
        """
        try:
            if not self.kms_key_id:
                logger.error("KMS_KEY_ID not configured")
                return None
            
            # Encrypt directly with KMS (for small data < 4KB)
            response = self.kms_client.encrypt(
                KeyId=self.kms_key_id,
                Plaintext=plaintext.encode('utf-8')
            )
            
            # Return base64-encoded ciphertext
            encrypted_data = base64.b64encode(response['CiphertextBlob']).decode('utf-8')
            logger.info("Data encrypted with KMS")
            return encrypted_data
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'NotFoundException':
                logger.error(f"KMS key not found: {self.kms_key_id}")
            elif error_code == 'DisabledException':
                logger.error(f"KMS key is disabled: {self.kms_key_id}")
            elif error_code == 'InvalidKeyUsageException':
                logger.error(f"Invalid key usage for KMS key: {self.kms_key_id}")
            elif error_code == 'AccessDeniedException':
                logger.error(f"Access denied to KMS key: {self.kms_key_id}")
            else:
                logger.error(f"KMS encryption error: {str(e)}")
            
            return None
        
        except Exception as e:
            logger.error(f"Unexpected error during KMS encryption: {str(e)}")
            return None
    
    def decrypt_with_kms(self, encrypted_data: str) -> Optional[str]:
        """
        Decrypt data using AWS KMS
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            
        Returns:
            Decrypted plaintext string, or None if failed
            
        Example:
            >>> service = AWSSecretsService()
            >>> decrypted = service.decrypt_with_kms(encrypted_data)
            >>> decrypted
            'my-secret-data'
        """
        try:
            # Decode base64
            ciphertext_blob = base64.b64decode(encrypted_data)
            
            # Decrypt with KMS
            response = self.kms_client.decrypt(
                CiphertextBlob=ciphertext_blob
            )
            
            # Return decrypted plaintext
            plaintext = response['Plaintext'].decode('utf-8')
            logger.info("Data decrypted with KMS")
            return plaintext
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'NotFoundException':
                logger.error("KMS key not found for decryption")
            elif error_code == 'DisabledException':
                logger.error("KMS key is disabled")
            elif error_code == 'InvalidCiphertextException':
                logger.error("Invalid ciphertext for decryption")
            elif error_code == 'AccessDeniedException':
                logger.error("Access denied for KMS decryption")
            else:
                logger.error(f"KMS decryption error: {str(e)}")
            
            return None
        
        except Exception as e:
            logger.error(f"Unexpected error during KMS decryption: {str(e)}")
            return None
    
    def generate_data_key(self) -> Optional[Dict[str, bytes]]:
        """
        Generate a data encryption key using KMS
        
        Returns envelope encryption key pair:
        - plaintext: Unencrypted data key (use for encryption, then discard)
        - ciphertext: Encrypted data key (store this)
        
        Returns:
            Dict with 'plaintext' and 'ciphertext' keys, or None if failed
            
        Example:
            >>> service = AWSSecretsService()
            >>> keys = service.generate_data_key()
            >>> plaintext_key = keys['plaintext']
            >>> encrypted_key = keys['ciphertext']
        """
        try:
            if not self.kms_key_id:
                logger.error("KMS_KEY_ID not configured")
                return None
            
            response = self.kms_client.generate_data_key(
                KeyId=self.kms_key_id,
                KeySpec='AES_256'
            )
            
            logger.info("Data encryption key generated")
            return {
                'plaintext': response['Plaintext'],
                'ciphertext': response['CiphertextBlob']
            }
            
        except ClientError as e:
            logger.error(f"Error generating data key: {str(e)}")
            return None
        
        except Exception as e:
            logger.error(f"Unexpected error generating data key: {str(e)}")
            return None
    
    def encrypt_database_connection_string(self, connection_string: str) -> Optional[str]:
        """
        Encrypt database connection string using KMS
        
        Args:
            connection_string: Database connection string (e.g., postgresql://...)
            
        Returns:
            Encrypted connection string (base64), or None if failed
        """
        return self.encrypt_with_kms(connection_string)
    
    def decrypt_database_connection_string(self, encrypted_connection_string: str) -> Optional[str]:
        """
        Decrypt database connection string using KMS
        
        Args:
            encrypted_connection_string: Encrypted connection string (base64)
            
        Returns:
            Decrypted connection string, or None if failed
        """
        return self.decrypt_with_kms(encrypted_connection_string)


# Global instance
aws_secrets_service = AWSSecretsService()


# Convenience functions
def get_secret(secret_name: str) -> Optional[Dict[str, Any]]:
    """Get secret from AWS Secrets Manager"""
    return aws_secrets_service.get_secret(secret_name)


def encrypt_data(plaintext: str) -> Optional[str]:
    """Encrypt data with KMS"""
    return aws_secrets_service.encrypt_with_kms(plaintext)


def decrypt_data(encrypted_data: str) -> Optional[str]:
    """Decrypt data with KMS"""
    return aws_secrets_service.decrypt_with_kms(encrypted_data)
