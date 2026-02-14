#!/usr/bin/env python3
"""
Setup script for Database Migrator Tool
This script initializes the application by:
1. Creating KMS data encryption key
2. Storing encrypted key in AWS Secrets Manager
3. Validating AWS permissions
4. Initializing database schema
"""

import os
import sys
import boto3
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_environment():
    """Validate required environment variables"""
    required_vars = [
        'AWS_REGION',
        'KMS_KEY_ID',
        'SECRET_MANAGER_SECRET_NAME',
        'APP_DB_HOST',
        'APP_DB_NAME',
        'APP_DB_USER',
        'APP_DB_PASSWORD'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
    
    logger.info("Environment variables validated successfully")


def create_kms_data_key():
    """Generate a data encryption key using AWS KMS"""
    try:
        kms_client = boto3.client('kms', region_name=os.getenv('AWS_REGION'))
        
        response = kms_client.generate_data_key(
            KeyId=os.getenv('KMS_KEY_ID'),
            KeySpec='AES_256'
        )
        
        logger.info("KMS data encryption key generated successfully")
        return response['Plaintext'], response['CiphertextBlob']
        
    except Exception as e:
        logger.error(f"Failed to generate KMS data key: {str(e)}")
        sys.exit(1)


def store_key_in_secrets_manager(encrypted_key):
    """Store encrypted data key in AWS Secrets Manager"""
    try:
        secrets_client = boto3.client(
            'secretsmanager',
            region_name=os.getenv('SECRET_MANAGER_REGION', os.getenv('AWS_REGION'))
        )
        
        secret_name = os.getenv('SECRET_MANAGER_SECRET_NAME')
        
        # Try to create the secret
        try:
            secrets_client.create_secret(
                Name=secret_name,
                SecretBinary=encrypted_key,
                Description='Encrypted data key for database connection encryption'
            )
            logger.info(f"Secret created in Secrets Manager: {secret_name}")
        except secrets_client.exceptions.ResourceExistsException:
            # Update existing secret
            secrets_client.put_secret_value(
                SecretId=secret_name,
                SecretBinary=encrypted_key
            )
            logger.info(f"Secret updated in Secrets Manager: {secret_name}")
            
    except Exception as e:
        logger.error(f"Failed to store key in Secrets Manager: {str(e)}")
        sys.exit(1)


def validate_aws_permissions():
    """Validate required AWS permissions"""
    try:
        # Test KMS permissions
        kms_client = boto3.client('kms', region_name=os.getenv('AWS_REGION'))
        kms_client.describe_key(KeyId=os.getenv('KMS_KEY_ID'))
        logger.info("KMS permissions validated")
        
        # Test Secrets Manager permissions
        secrets_client = boto3.client(
            'secretsmanager',
            region_name=os.getenv('SECRET_MANAGER_REGION', os.getenv('AWS_REGION'))
        )
        secrets_client.list_secrets(MaxResults=1)
        logger.info("Secrets Manager permissions validated")
        
        # Test CloudWatch permissions (optional)
        try:
            logs_client = boto3.client('logs', region_name=os.getenv('AWS_REGION'))
            logs_client.describe_log_groups(limit=1)
            logger.info("CloudWatch Logs permissions validated")
        except Exception as e:
            logger.warning(f"CloudWatch Logs permissions check failed: {str(e)}")
        
    except Exception as e:
        logger.error(f"AWS permissions validation failed: {str(e)}")
        sys.exit(1)


def initialize_database():
    """Initialize database schema"""
    # TODO: Implement database initialization
    # This will use Alembic or similar for schema migrations
    logger.info("Database initialization - TODO: Implement with Alembic")


def main():
    """Main setup function"""
    logger.info("Starting Database Migrator Tool setup...")
    
    # Step 1: Validate environment
    logger.info("Step 1: Validating environment variables")
    validate_environment()
    
    # Step 2: Validate AWS permissions
    logger.info("Step 2: Validating AWS permissions")
    validate_aws_permissions()
    
    # Step 3: Generate KMS data key
    logger.info("Step 3: Generating KMS data encryption key")
    plaintext_key, encrypted_key = create_kms_data_key()
    
    # Step 4: Store in Secrets Manager
    logger.info("Step 4: Storing encrypted key in Secrets Manager")
    store_key_in_secrets_manager(encrypted_key)
    
    # Step 5: Initialize database
    logger.info("Step 5: Initializing database schema")
    initialize_database()
    
    logger.info("Setup completed successfully!")
    logger.info("You can now start the application")


if __name__ == "__main__":
    main()
