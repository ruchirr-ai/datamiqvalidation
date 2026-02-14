"""
Encrypt Connection Passwords

This script encrypts all plaintext passwords in the connections table.
Run this once to migrate existing connections to use encrypted passwords.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database import get_db
from models.connection import Connection
from services.encryption_service import get_encryption_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def encrypt_connection_passwords():
    """Encrypt all plaintext passwords in connections table"""
    
    db = next(get_db())
    encryption_service = get_encryption_service()
    
    try:
        # Get all connections
        connections = db.query(Connection).all()
        
        logger.info(f"Found {len(connections)} connections")
        logger.info("="*80)
        
        updated_count = 0
        
        for conn in connections:
            connection_params = conn.connection_params or {}
            
            # Check if password exists and is not encrypted
            password = connection_params.get('password')
            password_encrypted = connection_params.get('password_encrypted')
            
            if password and not password_encrypted:
                logger.info(f"\nConnection ID {conn.id}: {conn.name}")
                logger.info(f"  Type: {conn.type}")
                logger.info(f"  Database: {conn.database}")
                logger.info(f"  Password: Found (plaintext)")
                
                # Encrypt the password
                try:
                    encrypted_password = encryption_service.encrypt(password)
                    
                    # Update connection_params
                    connection_params['password_encrypted'] = encrypted_password
                    # Remove plaintext password
                    del connection_params['password']
                    
                    # Save to database - IMPORTANT: Create new dict to trigger SQLAlchemy change detection
                    conn.connection_params = dict(connection_params)
                    # Mark as modified explicitly for JSON column
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(conn, 'connection_params')
                    
                    db.commit()
                    
                    logger.info(f"  ✓ Password encrypted and saved")
                    updated_count += 1
                    
                except Exception as e:
                    logger.error(f"  ✗ Failed to encrypt password: {e}")
                    db.rollback()
                    
            elif password_encrypted:
                logger.info(f"\nConnection ID {conn.id}: {conn.name}")
                logger.info(f"  ✓ Password already encrypted")
                
            else:
                logger.info(f"\nConnection ID {conn.id}: {conn.name}")
                logger.info(f"  ⚠ No password found")
        
        logger.info("\n" + "="*80)
        logger.info(f"✓ Encryption complete")
        logger.info(f"  Connections updated: {updated_count}")
        logger.info("="*80)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to encrypt passwords: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        db.close()


if __name__ == '__main__':
    success = encrypt_connection_passwords()
    sys.exit(0 if success else 1)
