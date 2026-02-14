"""
Unit tests for JWTService
Tests JWT token generation, validation, and expiration
"""

import pytest
import os
from datetime import datetime, timedelta
from services.jwt_service import JWTService, TokenPayload
from jose import jwt


class TestJWTTokenGeneration:
    """Test JWT token generation"""
    
    def test_generate_token_returns_string(self):
        """Test that generate_jwt_token returns a string"""
        token = JWTService.generate_jwt_token(1, "testuser", "user")
        
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_generate_token_contains_payload(self):
        """Test that generated token contains correct payload"""
        user_id = 1
        username = "testuser"
        role = "user"
        
        token = JWTService.generate_jwt_token(user_id, username, role)
        payload = JWTService.decode_token_without_validation(token)
        
        assert payload is not None
        assert payload["user_id"] == user_id
        assert payload["username"] == username
        assert payload["role"] == role
        assert "exp" in payload
        assert "iat" in payload
    
    def test_generate_token_expiration_time(self):
        """Test that token has correct expiration time (8 hours)"""
        token = JWTService.generate_jwt_token(1, "testuser", "user")
        payload = JWTService.decode_token_without_validation(token)
        
        exp_time = datetime.fromtimestamp(payload["exp"])
        iat_time = datetime.fromtimestamp(payload["iat"])
        
        # Should be 8 hours difference
        time_diff = (exp_time - iat_time).total_seconds() / 3600
        assert abs(time_diff - 8) < 0.01  # Within 0.01 hours tolerance
    
    def test_generate_token_different_users(self):
        """Test generating tokens for different users"""
        token1 = JWTService.generate_jwt_token(1, "user1", "user")
        token2 = JWTService.generate_jwt_token(2, "user2", "admin")
        
        payload1 = JWTService.decode_token_without_validation(token1)
        payload2 = JWTService.decode_token_without_validation(token2)
        
        assert payload1["user_id"] != payload2["user_id"]
        assert payload1["username"] != payload2["username"]
        assert payload1["role"] != payload2["role"]


class TestJWTTokenValidation:
    """Test JWT token validation"""
    
    def test_validate_valid_token(self):
        """Test validation of a valid token"""
        token = JWTService.generate_jwt_token(1, "testuser", "user")
        payload = JWTService.validate_jwt_token(token)
        
        assert payload is not None
        assert isinstance(payload, TokenPayload)
        assert payload.user_id == 1
        assert payload.username == "testuser"
        assert payload.role == "user"
    
    def test_validate_invalid_token(self):
        """Test validation of an invalid token"""
        invalid_token = "invalid.token.string"
        payload = JWTService.validate_jwt_token(invalid_token)
        
        assert payload is None
    
    def test_validate_tampered_token(self):
        """Test validation of a tampered token"""
        token = JWTService.generate_jwt_token(1, "testuser", "user")
        
        # Tamper with the token
        parts = token.split('.')
        if len(parts) == 3:
            tampered_token = parts[0] + ".tampered." + parts[2]
            payload = JWTService.validate_jwt_token(tampered_token)
            
            assert payload is None
    
    def test_validate_token_wrong_secret(self):
        """Test validation fails with wrong secret key"""
        # Generate token with current secret
        token = JWTService.generate_jwt_token(1, "testuser", "user")
        
        # Change secret key temporarily
        original_secret = os.getenv('JWT_SECRET_KEY')
        os.environ['JWT_SECRET_KEY'] = 'different_secret_key'
        
        try:
            payload = JWTService.validate_jwt_token(token)
            assert payload is None
        finally:
            # Restore original secret
            if original_secret:
                os.environ['JWT_SECRET_KEY'] = original_secret


class TestTokenExpiration:
    """Test token expiration logic"""
    
    def test_get_token_expiration(self):
        """Test getting expiration time from token"""
        token = JWTService.generate_jwt_token(1, "testuser", "user")
        expiration = JWTService.get_token_expiration(token)
        
        assert expiration is not None
        assert isinstance(expiration, datetime)
        assert expiration > datetime.utcnow()
    
    def test_is_token_expired_fresh_token(self):
        """Test that fresh token is not expired"""
        token = JWTService.generate_jwt_token(1, "testuser", "user")
        
        assert JWTService.is_token_expired(token) is False
    
    def test_decode_without_validation(self):
        """Test decoding token without validation"""
        token = JWTService.generate_jwt_token(1, "testuser", "user")
        payload = JWTService.decode_token_without_validation(token)
        
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["username"] == "testuser"
        assert payload["role"] == "user"


class TestTokenPayloadModel:
    """Test TokenPayload model"""
    
    def test_token_payload_creation(self):
        """Test creating TokenPayload from dict"""
        payload_dict = {
            "user_id": 1,
            "username": "testuser",
            "role": "user",
            "exp": int((datetime.utcnow() + timedelta(hours=8)).timestamp()),
            "iat": int(datetime.utcnow().timestamp())
        }
        
        payload = TokenPayload(**payload_dict)
        
        assert payload.user_id == 1
        assert payload.username == "testuser"
        assert payload.role == "user"
    
    def test_token_payload_validation(self):
        """Test TokenPayload validation"""
        # Missing required field
        with pytest.raises(Exception):
            TokenPayload(user_id=1, username="test")  # Missing role, exp, iat
