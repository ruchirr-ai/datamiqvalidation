"""
JWT Token Service
Handles JWT token generation, validation, and payload management
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
from jose import jwt, JWTError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TokenPayload(BaseModel):
    """JWT token payload structure"""
    user_id: int
    username: str
    role: str
    exp: int
    iat: int


class JWTService:
    """Service for JWT token operations"""
    
    # Token settings
    TOKEN_EXPIRATION_HOURS = 8
    ALGORITHM = "HS256"
    
    @staticmethod
    def _get_secret_key() -> str:
        """Get JWT secret key from environment"""
        secret = os.getenv('JWT_SECRET_KEY')
        if not secret:
            raise ValueError("JWT_SECRET_KEY environment variable not set")
        return secret
    
    @staticmethod
    def generate_jwt_token(user_id: int, username: str, role: str) -> str:
        """
        Generate a JWT token for a user
        
        Args:
            user_id: User's database ID
            username: User's username
            role: User's role (admin, user)
            
        Returns:
            JWT token as string
            
        Example:
            >>> token = JWTService.generate_jwt_token(1, "testuser", "user")
            >>> isinstance(token, str)
            True
            >>> len(token) > 0
            True
        """
        now = datetime.utcnow()
        expires = now + timedelta(hours=JWTService.TOKEN_EXPIRATION_HOURS)
        
        payload = {
            "user_id": user_id,
            "username": username,
            "role": role,
            "exp": int(expires.timestamp()),
            "iat": int(now.timestamp())
        }
        
        secret_key = JWTService._get_secret_key()
        token = jwt.encode(payload, secret_key, algorithm=JWTService.ALGORITHM)
        
        return token
    
    @staticmethod
    def validate_jwt_token(token: str) -> Optional[TokenPayload]:
        """
        Validate and decode a JWT token
        
        Args:
            token: JWT token string to validate
            
        Returns:
            TokenPayload if valid, None if invalid
            
        Example:
            >>> token = JWTService.generate_jwt_token(1, "testuser", "user")
            >>> payload = JWTService.validate_jwt_token(token)
            >>> payload.username
            'testuser'
            >>> payload.role
            'user'
        """
        try:
            secret_key = JWTService._get_secret_key()
            payload_dict = jwt.decode(
                token,
                secret_key,
                algorithms=[JWTService.ALGORITHM]
            )
            
            # Validate payload structure
            payload = TokenPayload(**payload_dict)
            
            # Check expiration
            if datetime.utcnow().timestamp() > payload.exp:
                logger.warning("Token has expired")
                return None
            
            return payload
            
        except JWTError as e:
            logger.error(f"JWT validation error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error validating token: {str(e)}")
            return None
    
    @staticmethod
    def decode_token_without_validation(token: str) -> Optional[Dict[str, Any]]:
        """
        Decode token without validation (for inspection/debugging)
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded payload dict or None
            
        Warning:
            This method does NOT validate the token signature or expiration.
            Use only for debugging or inspection purposes.
        """
        try:
            payload = jwt.get_unverified_claims(token)
            return payload
        except Exception as e:
            logger.error(f"Error decoding token: {str(e)}")
            return None
    
    @staticmethod
    def get_token_expiration(token: str) -> Optional[datetime]:
        """
        Get expiration time from token
        
        Args:
            token: JWT token string
            
        Returns:
            Expiration datetime or None
        """
        payload = JWTService.decode_token_without_validation(token)
        if payload and 'exp' in payload:
            return datetime.fromtimestamp(payload['exp'])
        return None
    
    @staticmethod
    def is_token_expired(token: str) -> bool:
        """
        Check if token is expired
        
        Args:
            token: JWT token string
            
        Returns:
            True if expired, False otherwise
        """
        expiration = JWTService.get_token_expiration(token)
        if expiration is None:
            return True
        return datetime.utcnow() > expiration
