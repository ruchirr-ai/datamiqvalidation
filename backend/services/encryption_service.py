"""
Simple Encryption Service

Provides basic encryption/decryption for sensitive data.
Uses Fernet (symmetric encryption) from cryptography library.

For production, this should be replaced with AWS KMS or similar.
"""

import os
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class EncryptionService:
    """Simple encryption service using Fernet symmetric encryption"""
    
    def __init__(self, encryption_key: str = None):
        """
        Initialize encryption service
        
        Args:
            encryption_key: Base64-encoded encryption key. If not provided,
                          will use ENCRYPTION_KEY from environment or generate one.
        """
        if encryption_key:
            self.key = encryption_key.encode()
        else:
            # Get from environment or use default (NOT SECURE FOR PRODUCTION)
            env_key = os.getenv('ENCRYPTION_KEY')
            if env_key:
                self.key = env_key.encode()
            else:
                # Generate a key from a password (for development only)
                password = os.getenv('ENCRYPTION_PASSWORD', 'default-dev-password-change-in-production')
                salt = b'datamiq-salt-2026'  # Should be random and stored securely
                
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
                self.key = key
                
                logger.warning(
                    "Using default encryption key. "
                    "Set ENCRYPTION_KEY or ENCRYPTION_PASSWORD in .env for production!"
                )
        
        self.cipher = Fernet(self.key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        try:
            if not plaintext:
                return ''
            
            encrypted_bytes = self.cipher.encrypt(plaintext.encode())
            return encrypted_bytes.decode()
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a string
        
        Args:
            ciphertext: Base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string
        """
        try:
            if not ciphertext:
                return ''
            
            decrypted_bytes = self.cipher.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    @staticmethod
    def generate_key() -> str:
        """
        Generate a new encryption key
        
        Returns:
            Base64-encoded encryption key
        """
        key = Fernet.generate_key()
        return key.decode()


# Global instance
_encryption_service = None


def get_encryption_service() -> EncryptionService:
    """Get or create global encryption service instance"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service
