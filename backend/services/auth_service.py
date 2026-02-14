"""
Authentication Service
Handles password hashing, validation, user authentication, and workspace context
"""

import bcrypt
import re
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class PasswordValidationError(Exception):
    """Raised when password doesn't meet requirements"""
    pass


class AuthenticationError(Exception):
    """Raised when authentication fails"""
    pass


class AuthService:
    """Service for authentication operations"""
    
    # Password requirements
    MIN_PASSWORD_LENGTH = 8
    PASSWORD_PATTERN = re.compile(
        r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$'
    )
    
    # Account locking settings
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt with cost factor 12
        
        Args:
            password: Plain text password to hash
            
        Returns:
            Hashed password as string
            
        Example:
            >>> hashed = AuthService.hash_password("MySecurePass123!")
            >>> isinstance(hashed, str)
            True
        """
        # Convert password to bytes
        password_bytes = password.encode('utf-8')
        
        # Generate salt and hash with cost factor 12
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password_bytes, salt)
        
        # Return as string
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash
        
        Args:
            plain_password: Plain text password to verify
            hashed_password: Hashed password to compare against
            
        Returns:
            True if password matches, False otherwise
            
        Example:
            >>> hashed = AuthService.hash_password("MyPass123!")
            >>> AuthService.verify_password("MyPass123!", hashed)
            True
            >>> AuthService.verify_password("WrongPass", hashed)
            False
        """
        try:
            password_bytes = plain_password.encode('utf-8')
            hashed_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except Exception as e:
            logger.error(f"Password verification error: {str(e)}")
            return False
    
    @staticmethod
    def validate_password_strength(password: str) -> None:
        """
        Validate password meets strength requirements
        
        Requirements:
        - Minimum 8 characters
        - At least 1 uppercase letter
        - At least 1 lowercase letter
        - At least 1 number
        
        Args:
            password: Password to validate
            
        Raises:
            PasswordValidationError: If password doesn't meet requirements
            
        Example:
            >>> AuthService.validate_password_strength("ValidPass123")
            >>> # No exception raised
            
            >>> AuthService.validate_password_strength("weak")
            Traceback (most recent call last):
            ...
            PasswordValidationError: Password must be at least 8 characters...
        """
        if len(password) < AuthService.MIN_PASSWORD_LENGTH:
            raise PasswordValidationError(
                f"Password must be at least {AuthService.MIN_PASSWORD_LENGTH} characters long"
            )
        
        if not re.search(r'[a-z]', password):
            raise PasswordValidationError(
                "Password must contain at least one lowercase letter"
            )
        
        if not re.search(r'[A-Z]', password):
            raise PasswordValidationError(
                "Password must contain at least one uppercase letter"
            )
        
        if not re.search(r'\d', password):
            raise PasswordValidationError(
                "Password must contain at least one number"
            )
    
    @staticmethod
    def is_account_locked(failed_attempts: int, locked_until: Optional[datetime]) -> bool:
        """
        Check if an account is currently locked
        
        Args:
            failed_attempts: Number of failed login attempts
            locked_until: Timestamp when lock expires (None if not locked)
            
        Returns:
            True if account is locked, False otherwise
            
        Example:
            >>> from datetime import datetime, timedelta
            >>> future = datetime.utcnow() + timedelta(minutes=10)
            >>> AuthService.is_account_locked(5, future)
            True
            >>> past = datetime.utcnow() - timedelta(minutes=10)
            >>> AuthService.is_account_locked(5, past)
            False
        """
        if failed_attempts < AuthService.MAX_FAILED_ATTEMPTS:
            return False
        
        if locked_until is None:
            return False
        
        # Check if lock has expired
        return datetime.utcnow() < locked_until
    
    @staticmethod
    def calculate_lockout_time() -> datetime:
        """
        Calculate when account lock should expire
        
        Returns:
            Datetime when lock expires
            
        Example:
            >>> lockout = AuthService.calculate_lockout_time()
            >>> lockout > datetime.utcnow()
            True
        """
        return datetime.utcnow() + timedelta(
            minutes=AuthService.LOCKOUT_DURATION_MINUTES
        )
