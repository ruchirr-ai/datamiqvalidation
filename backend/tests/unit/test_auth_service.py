"""
Unit tests for AuthService
Tests password hashing, validation, and account locking logic
"""

import pytest
from datetime import datetime, timedelta
from services.auth_service import AuthService, PasswordValidationError
from tests.fixtures.sample_payloads import (
    VALID_PASSWORDS,
    INVALID_PASSWORDS
)


class TestPasswordHashing:
    """Test password hashing and verification"""
    
    def test_hash_password_returns_string(self):
        """Test that hash_password returns a string"""
        password = "TestPass123!"
        hashed = AuthService.hash_password(password)
        
        assert isinstance(hashed, str)
        assert len(hashed) > 0
    
    def test_hash_password_different_each_time(self):
        """Test that hashing same password produces different hashes (due to salt)"""
        password = "TestPass123!"
        hash1 = AuthService.hash_password(password)
        hash2 = AuthService.hash_password(password)
        
        assert hash1 != hash2
    
    def test_verify_password_correct(self):
        """Test password verification with correct password"""
        password = "TestPass123!"
        hashed = AuthService.hash_password(password)
        
        assert AuthService.verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password"""
        password = "TestPass123!"
        hashed = AuthService.hash_password(password)
        
        assert AuthService.verify_password("WrongPass123!", hashed) is False
    
    def test_verify_password_empty_string(self):
        """Test password verification with empty string"""
        password = "TestPass123!"
        hashed = AuthService.hash_password(password)
        
        assert AuthService.verify_password("", hashed) is False
    
    def test_hash_password_with_special_characters(self):
        """Test hashing password with special characters"""
        password = "P@ssw0rd!#$%"
        hashed = AuthService.hash_password(password)
        
        assert AuthService.verify_password(password, hashed) is True


class TestPasswordValidation:
    """Test password strength validation"""
    
    def test_validate_valid_passwords(self):
        """Test validation passes for valid passwords"""
        for password in VALID_PASSWORDS:
            # Should not raise exception
            AuthService.validate_password_strength(password)
    
    def test_validate_too_short(self):
        """Test validation fails for password too short"""
        with pytest.raises(PasswordValidationError) as exc_info:
            AuthService.validate_password_strength(INVALID_PASSWORDS["short"])
        
        assert "at least 8 characters" in str(exc_info.value).lower()
    
    def test_validate_no_uppercase(self):
        """Test validation fails for password without uppercase"""
        with pytest.raises(PasswordValidationError) as exc_info:
            AuthService.validate_password_strength(INVALID_PASSWORDS["no_uppercase"])
        
        assert "uppercase" in str(exc_info.value).lower()
    
    def test_validate_no_lowercase(self):
        """Test validation fails for password without lowercase"""
        with pytest.raises(PasswordValidationError) as exc_info:
            AuthService.validate_password_strength(INVALID_PASSWORDS["no_lowercase"])
        
        assert "lowercase" in str(exc_info.value).lower()
    
    def test_validate_no_number(self):
        """Test validation fails for password without number"""
        with pytest.raises(PasswordValidationError) as exc_info:
            AuthService.validate_password_strength(INVALID_PASSWORDS["no_number"])
        
        assert "number" in str(exc_info.value).lower()
    
    def test_validate_empty_password(self):
        """Test validation fails for empty password"""
        with pytest.raises(PasswordValidationError):
            AuthService.validate_password_strength(INVALID_PASSWORDS["empty"])


class TestAccountLocking:
    """Test account locking logic"""
    
    def test_account_not_locked_below_threshold(self):
        """Test account is not locked with failed attempts below threshold"""
        assert AuthService.is_account_locked(0, None) is False
        assert AuthService.is_account_locked(3, None) is False
        assert AuthService.is_account_locked(4, None) is False
    
    def test_account_locked_at_threshold(self):
        """Test account is locked when reaching failed attempt threshold"""
        future_time = datetime.utcnow() + timedelta(minutes=10)
        assert AuthService.is_account_locked(5, future_time) is True
    
    def test_account_locked_above_threshold(self):
        """Test account is locked when exceeding failed attempt threshold"""
        future_time = datetime.utcnow() + timedelta(minutes=10)
        assert AuthService.is_account_locked(10, future_time) is True
    
    def test_account_unlocked_after_expiry(self):
        """Test account is unlocked after lock expiry time"""
        past_time = datetime.utcnow() - timedelta(minutes=10)
        assert AuthService.is_account_locked(5, past_time) is False
    
    def test_calculate_lockout_time(self):
        """Test lockout time calculation"""
        lockout_time = AuthService.calculate_lockout_time()
        
        # Should be in the future
        assert lockout_time > datetime.utcnow()
        
        # Should be approximately 30 minutes from now
        expected_time = datetime.utcnow() + timedelta(minutes=30)
        time_diff = abs((lockout_time - expected_time).total_seconds())
        assert time_diff < 5  # Within 5 seconds tolerance
