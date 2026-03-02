"""
Test KMS Encryption Setup

This script verifies that AWS KMS encryption is properly configured.

Usage:
    python test_kms_setup.py
"""

import sys
import os
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.unified_kms_service import get_unified_kms_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_kms_setup():
    """Test KMS encryption setup"""
    
    print("\n" + "=" * 80)
    print("KMS ENCRYPTION SETUP TEST")
    print("=" * 80)
    
    try:
        # Initialize service
        print("\n1. Initializing Unified KMS Service...")
        kms = get_unified_kms_service()
        print("   ✓ Service initialized")
        
        # Test encryption
        print("\n2. Testing encryption...")
        test_data = "test-secret-value-12345"
        
        encrypted = kms.encrypt_credential(
            plaintext=test_data,
            credential_type="generic",
            resource_type="test",
            resource_id=1
        )
        
        print(f"   ✓ Encrypted successfully")
        print(f"   Ciphertext length: {len(encrypted)} characters")
        print(f"   Ciphertext preview: {encrypted[:50]}...")
        
        # Test decryption
        print("\n3. Testing decryption...")
        decrypted = kms.decrypt_credential(
            ciphertext=encrypted,
            credential_type="generic",
            resource_type="test",
            resource_id=1
        )
        
        if decrypted == test_data:
            print(f"   ✓ Decrypted successfully")
            print(f"   Plaintext matches original: {decrypted}")
        else:
            print(f"   ✗ Decryption failed - data mismatch")
            print(f"   Expected: {test_data}")
            print(f"   Got: {decrypted}")
            return False
        
        # Test different credential types
        print("\n4. Testing different credential types...")
        
        credential_types = [
            ('aws_secret_key', 'AKIAIOSFODNN7EXAMPLE'),
            ('gcp_hmac_secret', 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'),
            ('gcp_service_account', '{"type":"service_account","project_id":"test"}'),
            ('connection_password', 'MySecurePassword123!')
        ]
        
        for cred_type, test_value in credential_types:
            encrypted = kms.encrypt_credential(
                plaintext=test_value,
                credential_type=cred_type,
                resource_type="test",
                resource_id=1
            )
            
            decrypted = kms.decrypt_credential(
                ciphertext=encrypted,
                credential_type=cred_type,
                resource_type="test",
                resource_id=1
            )
            
            if decrypted == test_value:
                print(f"   ✓ {cred_type}: OK")
            else:
                print(f"   ✗ {cred_type}: FAILED")
                return False
        
        # Test is_encrypted check
        print("\n5. Testing encryption detection...")
        
        if kms.is_encrypted(encrypted):
            print(f"   ✓ Correctly identified encrypted data")
        else:
            print(f"   ✗ Failed to identify encrypted data")
            return False
        
        if not kms.is_encrypted("plaintext-value"):
            print(f"   ✓ Correctly identified plaintext data")
        else:
            print(f"   ✗ Incorrectly identified plaintext as encrypted")
            return False
        
        # Test graceful fallback
        print("\n6. Testing graceful fallback for plaintext...")
        
        plaintext_fallback = kms.decrypt_credential(
            ciphertext="plaintext-value",
            credential_type="generic",
            allow_plaintext_fallback=True
        )
        
        if plaintext_fallback == "plaintext-value":
            print(f"   ✓ Graceful fallback works")
        else:
            print(f"   ✗ Graceful fallback failed")
            return False
        
        # Success
        print("\n" + "=" * 80)
        print("✓ ALL TESTS PASSED")
        print("=" * 80)
        print("\nKMS encryption is properly configured and working!")
        print("\nNext steps:")
        print("1. Run: python scripts/encrypt_existing_credentials.py --dry-run")
        print("2. Review the output")
        print("3. Run: python scripts/encrypt_existing_credentials.py")
        print("=" * 80)
        
        return True
    
    except Exception as e:
        print("\n" + "=" * 80)
        print("✗ TEST FAILED")
        print("=" * 80)
        print(f"\nError: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Check AWS credentials: aws sts get-caller-identity")
        print("2. Verify secret exists: aws secretsmanager get-secret-value --secret-id datamiq")
        print("3. Check IAM permissions (see KMS_ENCRYPTION_SETUP_GUIDE.md)")
        print("=" * 80)
        
        return False


if __name__ == '__main__':
    success = test_kms_setup()
    sys.exit(0 if success else 1)
