"""
Test script to debug migration background thread execution
"""

import logging
import sys
from database import db_instance
from services.bq_redshift_migration.orchestrator import MigrationOrchestrator
from models.bq_redshift_migration import MigrationBQRedshift

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def test_migration_execution(migration_id: int):
    """Test migration execution directly"""
    logger.info(f"=== Testing Migration {migration_id} Execution ===")
    
    # Create database session
    db = db_instance.SessionLocal()
    
    try:
        # Get migration
        migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
        
        if not migration:
            logger.error(f"Migration {migration_id} not found")
            return
        
        logger.info(f"Migration found: {migration.migration_name}")
        logger.info(f"Status: {migration.status}")
        logger.info(f"Pathway: {migration.pathway}")
        logger.info(f"Source: {migration.source_dataset}")
        logger.info(f"Tables: {migration.source_tables}")
        
        # Create orchestrator
        logger.info("Creating orchestrator...")
        orchestrator = MigrationOrchestrator(db)
        
        # Start migration
        logger.info("Starting migration...")
        success = orchestrator.start_migration(migration_id)
        
        logger.info(f"Migration completed: success={success}")
        
        # Get final status
        migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
        logger.info(f"Final status: {migration.status}")
        logger.info(f"Current stage: {migration.current_stage}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_migration_background.py <migration_id>")
        sys.exit(1)
    
    migration_id = int(sys.argv[1])
    test_migration_execution(migration_id)
