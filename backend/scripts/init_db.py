#!/usr/bin/env python3
"""
Database initialization script
Creates database if it doesn't exist and runs migrations
"""

import os
import sys
import logging
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_database_if_not_exists():
    """Create the application database if it doesn't exist"""
    db_host = os.getenv('APP_DB_HOST', 'localhost')
    db_port = os.getenv('APP_DB_PORT', '5432')
    db_name = os.getenv('APP_DB_NAME')
    db_user = os.getenv('APP_DB_USER')
    db_password = os.getenv('APP_DB_PASSWORD')
    
    if not all([db_name, db_user, db_password]):
        logger.error("Missing required database environment variables")
        sys.exit(1)
    
    try:
        # Connect to PostgreSQL server (postgres database)
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database='postgres',
            user=db_user,
            password=db_password
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if database exists
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (db_name,)
        )
        exists = cursor.fetchone()
        
        if not exists:
            logger.info(f"Creating database: {db_name}")
            cursor.execute(f'CREATE DATABASE "{db_name}"')
            logger.info(f"Database {db_name} created successfully")
        else:
            logger.info(f"Database {db_name} already exists")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Failed to create database: {str(e)}")
        sys.exit(1)


def run_migrations():
    """Run Alembic migrations"""
    try:
        logger.info("Running database migrations...")
        os.system("alembic upgrade head")
        logger.info("Migrations completed successfully")
    except Exception as e:
        logger.error(f"Failed to run migrations: {str(e)}")
        sys.exit(1)


def main():
    """Main initialization function"""
    logger.info("Starting database initialization...")
    
    # Step 1: Create database if it doesn't exist
    create_database_if_not_exists()
    
    # Step 2: Run migrations
    run_migrations()
    
    logger.info("Database initialization completed successfully!")


if __name__ == "__main__":
    main()
