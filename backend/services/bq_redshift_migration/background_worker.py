"""
Background Worker for Scheduled Migrations

Runs as a separate process to execute scheduled migrations.
Can be deployed as a separate container or AWS Lambda function.
"""

import logging
import time
import signal
import sys
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

from .scheduler import MigrationScheduler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BackgroundWorker:
    """
    Background worker for processing scheduled migrations.
    
    Features:
    - Periodic execution (every minute)
    - Graceful shutdown
    - Error recovery
    - Health monitoring
    """
    
    def __init__(self, database_url: str, check_interval: int = 60):
        """
        Initialize background worker.
        
        Args:
            database_url: PostgreSQL connection string
            check_interval: Seconds between schedule checks (default: 60)
        """
        self.database_url = database_url
        self.check_interval = check_interval
        self.running = False
        
        # Setup database
        self.engine = create_engine(database_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def start(self):
        """Start the background worker"""
        logger.info("Starting background worker for scheduled migrations")
        logger.info(f"Check interval: {self.check_interval} seconds")
        
        self.running = True
        
        while self.running:
            try:
                self._process_cycle()
                
                # Sleep until next check
                if self.running:
                    time.sleep(self.check_interval)
                    
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in worker cycle: {e}", exc_info=True)
                # Continue running despite errors
                time.sleep(self.check_interval)
        
        logger.info("Background worker stopped")
    
    def _process_cycle(self):
        """Process one cycle of scheduled migrations"""
        try:
            db = self.SessionLocal()
            
            try:
                scheduler = MigrationScheduler(db)
                
                logger.debug("Checking for due migrations...")
                stats = scheduler.process_scheduled_migrations()
                
                if stats['total_due'] > 0:
                    logger.info(
                        f"Processed {stats['total_due']} due migrations: "
                        f"{stats['started']} started, {stats['failed']} failed"
                    )
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error processing scheduled migrations: {e}", exc_info=True)
    
    def health_check(self) -> bool:
        """
        Check if worker is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            db = self.SessionLocal()
            try:
                # Test database connection
                db.execute("SELECT 1")
                return True
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


def main():
    """Main entry point for background worker"""
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Get check interval (default: 60 seconds)
    check_interval = int(os.getenv('SCHEDULER_CHECK_INTERVAL', '60'))
    
    # Create and start worker
    worker = BackgroundWorker(database_url, check_interval)
    
    logger.info("=" * 60)
    logger.info("BigQuery to Redshift Migration Scheduler")
    logger.info("=" * 60)
    
    worker.start()


if __name__ == '__main__':
    main()
