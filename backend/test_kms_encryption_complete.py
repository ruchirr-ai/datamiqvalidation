"""
Complete KMS Encryption Test Script

Tests all KMS encryption functionality including:
- Basic encrypt/decrypt
- Encryption context validation
- Migration AWS secrets
- Connection parameters
- Error handling
"""

import sys
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_basic_encryption():
    """Test basic encryption and decryption"""
    logger.info("="*80)
    logger.info("TEST 1: Basic Encryption/Decryption")
    logger.info("="*80)
    
    try:
        from services.kms_encryption_service import get_kms_encryption_service
        
        kms_service = get_kms_encryption_service()
        
        # Test data
        test_secret = "my-super-secret-password-123"
        encryption_context = {
            'test': 'true',
            'purpose': 'basic_test'
        }
        
        # Encrypt
        logger.info("Encrypting test data...")
        encrypted = kms_service.encrypt(test_secret, encryption_context)
        logger.info(f"✓ Encrypted: {encrypted[:50]}...")
        
        # Decrypt
        logger.info("Decrypting test data...")
        decrypted = kms_service.decrypt(encrypted, encryption_context)
        logger.info(f"✓ Decrypted: {decrypted}")
        
        # Verify
        assert decrypted == test_secret, "Decrypted value doesn't match original"
        logger.info("✓ TEST 1 PASSED: Basic encryption/decryption works")
        return True
        
    except Exception as e:
        logger.error(f"✗ TEST 1 FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_encryption_context_validation():
    """Test that encryption context is validated"""
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Encryption Context Validation")
    logger.info("="*80)
    
    try:
        from services.kms_encryption_service import get_kms_encryption_service
        
        kms_service = get_kms_encryption_service()
        
        # Test data
        test_secret = "context-test-secret"
        correct_context = {
            'entity_id': '123',
            'field': 'password'
        }
        wrong_context = {
            'entity_id': '456',  # Different ID
            'field': 'password'
        }
        
        # Encrypt with correct context
        logger.info("Encrypting with context...")
        encrypted = kms_service.encrypt(test_secret, correct_context)
        logger.info(f"✓ Encrypted with context: {correct_context}")
        
        # Decrypt with correct context (should work)
        logger.info("Decrypting with correct context...")
        decrypted = kms_service.decrypt(encrypted, correct_context)
        assert decrypted == test_secret
        logger.info("✓ Decryption with correct context succeeded")
        
        # Try to decrypt with wrong context (should fail)
        logger.info("Attempting to decrypt with wrong context...")
        try:
            kms_service.decrypt(encrypted, wrong_context)
            logger.error("✗ TEST 2 FAILED: Decryption with wrong context should have failed")
            return False
        except Exception as e:
            logger.info(f"✓ Decryption with wrong context failed as expected: {type(e).__name__}")
        
        logger.info("✓ TEST 2 PASSED: Encryption context validation works")
        return True
        
    except Exception as e:
        logger.error(f"✗ TEST 2 FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_migration_aws_secret():
    """Test migration AWS secret encryption pattern"""
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Migration AWS Secret Encryption")
    logger.info("="*80)
    
    try:
        from services.kms_encryption_service import get_kms_encryption_service
        
        kms_service = get_kms_encryption_service()
        
        # Simulate migration AWS secret
        migration_id = 123
        aws_secret = "AKIAIOSFODNN7EXAMPLE/wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        
        # Encrypt (as done in create migration)
        logger.info(f"Encrypting AWS secret for migration {migration_id}...")
        encryption_context = {
            'migration_id': str(migration_id),
            'field': 'aws_secret_access_key',
            'created_at': datetime.utcnow().isoformat()
        }
        encrypted = kms_service.encrypt(aws_secret, encryption_context)
        logger.info(f"✓ Encrypted: {encrypted[:50]}...")
        
        # Decrypt (as done in migration execution)
        logger.info("Decrypting AWS secret for migration execution...")
        decryption_context = {
            'migration_id': str(migration_id),
            'field': 'aws_secret_access_key'
        }
        decrypted = kms_service.decrypt(encrypted, decryption_context)
        logger.info("✓ Decrypted successfully")
        
        # Verify
        assert decrypted == aws_secret
        logger.info("✓ TEST 3 PASSED: Migration AWS secret encryption works")
        return True
        
    except Exception as e:
        logger.error(f"✗ TEST 3 FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_connection_params():
    """Test connection parameters encryption pattern"""
    logger.info("\n" + "="*80)
    logger.info("TEST 4: Connection Parameters Encryption")
    logger.info("="*80)
    
    try:
        from services.kms_encryption_service import get_kms_encryption_service
        import json
        
        kms_service = get_kms_encryption_service()
        
        # Simulate connection parameters
        connection_id = 456
        connection_params = {
            'host': 'db.example.com',
            'port': 5432,
            'database': 'mydb',
            'username': 'dbuser',
            'password': 'super-secret-password'
        }
        
        # Encrypt (as done in create connection)
        logger.info(f"Encrypting connection params for connection {connection_id}...")
        encryption_context = {
            'connection_id': str(connection_id),
            'field': 'connection_params',
            'created_at': datetime.utcnow().isoformat()
        }
        params_json = json.dumps(connection_params)
        encrypted = kms_service.encrypt(params_json, encryption_context)
        logger.info(f"✓ Encrypted: {encrypted[:50]}...")
        
        # Decrypt (as done when retrieving connection)
        logger.info("Decrypting connection params...")
        decryption_context = {
            'connection_id': str(connection_id),
            'field': 'connection_params'
        }
        decrypted_json = kms_service.decrypt(encrypted, decryption_context)
        decrypted_params = json.loads(decrypted_json)
        logger.info("✓ Decrypted successfully")
        
        # Verify
        assert decrypted_params == connection_params
        assert decrypted_params['password'] == 'super-secret-password'
        logger.info("✓ TEST 4 PASSED: Connection parameters encryption works")
        return True
        
    except Exception as e:
        logger.error(f"✗ TEST 4 FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_error_handling():
    """Test error handling"""
    logger.info("\n" + "="*80)
    logger.info("TEST 5: Error Handling")
    logger.info("="*80)
    
    try:
        from services.kms_encryption_service import get_kms_encryption_service
        
        kms_service = get_kms_encryption_service()
        
        # Test 1: Invalid ciphertext
        logger.info("Testing invalid ciphertext...")
        try:
            kms_service.decrypt("invalid-ciphertext", {'test': 'true'})
            logger.error("✗ Should have raised exception for invalid ciphertext")
            return False
        except Exception as e:
            logger.info(f"✓ Invalid ciphertext handled: {type(e).__name__}")
        
        # Test 2: Empty plaintext
        logger.info("Testing empty plaintext...")
        try:
            kms_service.encrypt("", {'test': 'true'})
            logger.error("✗ Should have raised exception for empty plaintext")
            return False
        except ValueError as e:
            logger.info(f"✓ Empty plaintext handled: {e}")
        
        logger.info("✓ TEST 5 PASSED: Error handling works")
        return True
        
    except Exception as e:
        logger.error(f"✗ TEST 5 FAILED: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Run all tests"""
    logger.info("="*80)
    logger.info("KMS ENCRYPTION COMPLETE TEST SUITE")
    logger.info("="*80)
    logger.info("")
    
    tests = [
        ("Basic Encryption/Decryption", test_basic_encryption),
        ("Encryption Context Validation", test_encryption_context_validation),
        ("Migration AWS Secret", test_migration_aws_secret),
        ("Connection Parameters", test_connection_params),
        ("Error Handling", test_error_handling),
    ]
    
    results = []
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY")
    logger.info("="*80)
    
    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{status}: {test_name}")
    
    logger.info("="*80)
    logger.info(f"Total: {len(results)} tests")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    logger.info("="*80)
    
    if failed > 0:
        logger.error("\n✗ SOME TESTS FAILED")
        sys.exit(1)
    else:
        logger.info("\n✓ ALL TESTS PASSED")
        sys.exit(0)


if __name__ == '__main__':
    main()
