#!/usr/bin/env python3
"""
Admin User Setup Script
Creates initial admin user for the application
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import db_instance
from services.auth_service import AuthService, PasswordValidationError
from repositories.user_repository import UserRepository
from services.authentication_service import AuthenticationService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_admin_credentials():
    """
    Get admin credentials from environment variables or AWS Secrets Manager
    
    Returns:
        tuple: (username, password)
    """
    # Try to get from environment first
    admin_user = os.getenv('ADMIN_USER')
    admin_password = os.getenv('ADMIN_PASSWORD')
    
    if admin_user and admin_password:
        logger.info("Admin credentials loaded from environment variables")
        return admin_user, admin_password
    
    # Try AWS Secrets Manager
    try:
        import boto3
        import json
        
        secrets_client = boto3.client(
            'secretsmanager',
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        secret_name = os.getenv('ADMIN_CREDENTIALS_SECRET', 'datamiq/admin-credentials')
        
        response = secrets_client.get_secret_value(SecretId=secret_name)
        
        if 'SecretString' in response:
            secret = json.loads(response['SecretString'])
            admin_user = secret.get('username')
            admin_password = secret.get('password')
            
            if admin_user and admin_password:
                logger.info("Admin credentials loaded from AWS Secrets Manager")
                return admin_user, admin_password
    
    except Exception as e:
        logger.warning(f"Could not load credentials from AWS Secrets Manager: {str(e)}")
    
    # If neither source available, return None
    logger.error("Admin credentials not found in environment or AWS Secrets Manager")
    return None, None


def create_admin_user(username: str, password: str) -> bool:
    """
    Create admin user in database
    
    Args:
        username: Admin username
        password: Admin password (plain text)
        
    Returns:
        bool: True if created successfully, False otherwise
    """
    try:
        with db_instance.get_session() as db:
            user_repo = UserRepository(db)
            
            # Check if admin user already exists
            existing_user = user_repo.get_user_by_username(username)
            
            if existing_user:
                logger.info(f"Admin user '{username}' already exists. Skipping creation.")
                return True
            
            # Validate password strength
            try:
                AuthService.validate_password_strength(password)
            except PasswordValidationError as e:
                logger.error(f"Password validation failed: {str(e)}")
                return False
            
            # Hash password
            password_hash = AuthService.hash_password(password)
            
            # Create admin user
            admin_user = user_repo.create_user(
                username=username,
                password_hash=password_hash,
                role='admin'
            )
            
            if admin_user:
                logger.info(f"Admin user '{username}' created successfully with ID: {admin_user['id']}")
                return True
            else:
                logger.error("Failed to create admin user")
                return False
                
    except Exception as e:
        logger.error(f"Error creating admin user: {str(e)}")
        return False


def validate_admin_authentication(username: str, password: str) -> bool:
    """
    Validate that admin user can authenticate
    
    Args:
        username: Admin username
        password: Admin password
        
    Returns:
        bool: True if authentication successful, False otherwise
    """
    try:
        with db_instance.get_session() as db:
            user_repo = UserRepository(db)
            auth_service = AuthenticationService(user_repo)
            
            result = auth_service.authenticate_user(username, password)
            
            if result and result.get('access_token'):
                logger.info(f"Admin user '{username}' authentication validated successfully")
                return True
            else:
                logger.error("Admin authentication validation failed")
                return False
                
    except Exception as e:
        logger.error(f"Error validating admin authentication: {str(e)}")
        return False


def main():
    """Main setup function"""
    logger.info("Starting admin user setup...")
    
    # Step 1: Get admin credentials
    logger.info("Step 1: Loading admin credentials")
    username, password = get_admin_credentials()
    
    if not username or not password:
        logger.error("Admin credentials not available. Please set ADMIN_USER and ADMIN_PASSWORD environment variables.")
        logger.error("Or store credentials in AWS Secrets Manager.")
        sys.exit(1)
    
    # Step 2: Create admin user
    logger.info("Step 2: Creating admin user")
    if not create_admin_user(username, password):
        logger.error("Failed to create admin user")
        sys.exit(1)
    
    # Step 3: Validate authentication
    logger.info("Step 3: Validating admin authentication")
    if not validate_admin_authentication(username, password):
        logger.error("Admin authentication validation failed")
        sys.exit(1)
    
    logger.info("Admin user setup completed successfully!")
    logger.info(f"Admin user '{username}' is ready to use")


if __name__ == "__main__":
    main()
