"""
Script to update status for existing connections in the database.
This script will test all existing connections and update their status accordingly.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from database import SessionLocal
from models.connection import Connection
from routers.connections_router import (
    test_bigquery_connection,
    test_mongodb_connection,
    test_postgresql_connection,
    test_mysql_connection
)
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_connection_by_type(database: str, connection_params: dict):
    """Test connection based on database type"""
    database_lower = database.lower()
    
    if database_lower == 'bigquery':
        return test_bigquery_connection(connection_params)
    elif database_lower in ['mongodb', 'documentdb']:
        return test_mongodb_connection(connection_params)
    elif database_lower in ['postgresql', 'redshift']:
        return test_postgresql_connection(connection_params)
    elif database_lower == 'mysql':
        return test_mysql_connection(connection_params)
    else:
        logger.warning(f"Unsupported database type: {database}")
        return None


def update_existing_connections():
    """Update status for all existing connections"""
    db: Session = SessionLocal()
    
    try:
        # Get all active connections
        connections = db.query(Connection).filter(
            Connection.is_active == True
        ).all()
        
        logger.info(f"Found {len(connections)} connections to update")
        
        updated_count = 0
        failed_count = 0
        
        for connection in connections:
            logger.info(f"Testing connection: {connection.name} (ID: {connection.id})")
            
            try:
                # Test the connection
                result = test_connection_by_type(
                    connection.database,
                    connection.connection_params or {}
                )
                
                if result and result.success:
                    # Update status to connected
                    connection.status = 'connected'
                    connection.last_tested_at = datetime.utcnow()
                    connection.updated_at = datetime.utcnow()
                    updated_count += 1
                    logger.info(f"✓ Connection {connection.name} is CONNECTED")
                else:
                    # Update status to disconnected
                    connection.status = 'disconnected'
                    connection.last_tested_at = datetime.utcnow()
                    connection.updated_at = datetime.utcnow()
                    failed_count += 1
                    logger.warning(f"✗ Connection {connection.name} is DISCONNECTED: {result.message if result else 'Unknown error'}")
                
            except Exception as e:
                logger.error(f"Error testing connection {connection.name}: {str(e)}")
                connection.status = 'disconnected'
                connection.last_tested_at = datetime.utcnow()
                connection.updated_at = datetime.utcnow()
                failed_count += 1
        
        # Commit all changes
        db.commit()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Update complete!")
        logger.info(f"Total connections: {len(connections)}")
        logger.info(f"Successfully connected: {updated_count}")
        logger.info(f"Failed/Disconnected: {failed_count}")
        logger.info(f"{'='*60}\n")
        
    except Exception as e:
        logger.error(f"Failed to update connections: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Starting connection status update...")
    update_existing_connections()
    logger.info("Done!")
