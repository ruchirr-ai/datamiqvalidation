"""
Migration Scheduler Service

Handles scheduling of BigQuery to Redshift migrations.
Supports CRON expressions and integration with background task systems.
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from croniter import croniter
from sqlalchemy.orm import Session

from models.bq_redshift_migration import MigrationBQRedshift
from .orchestrator import MigrationOrchestrator

logger = logging.getLogger(__name__)


class MigrationScheduler:
    """
    Manages scheduled migrations with CRON support.
    
    Features:
    - CRON expression parsing
    - Next run time calculation
    - Scheduled migration execution
    - Background task integration
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.orchestrator = MigrationOrchestrator(db)
    
    def calculate_next_run(self, cron_expression: str, base_time: Optional[datetime] = None) -> datetime:
        """
        Calculate next run time from CRON expression.
        
        Args:
            cron_expression: CRON expression (e.g., "0 2 * * *" for daily at 2 AM)
            base_time: Base time for calculation (defaults to now)
            
        Returns:
            Next scheduled run time
            
        Raises:
            ValueError: If CRON expression is invalid
        """
        try:
            base = base_time or datetime.utcnow()
            cron = croniter(cron_expression, base)
            next_run = cron.get_next(datetime)
            
            logger.debug(f"Next run calculated: {next_run} from expression: {cron_expression}")
            return next_run
            
        except Exception as e:
            logger.error(f"Invalid CRON expression '{cron_expression}': {e}")
            raise ValueError(f"Invalid CRON expression: {e}")
    
    def get_scheduled_migrations(self) -> List[MigrationBQRedshift]:
        """
        Get all migrations with active schedules.
        
        Returns:
            List of scheduled migrations
        """
        try:
            migrations = self.db.query(MigrationBQRedshift).filter(
                MigrationBQRedshift.schedule_type == 'recurring',
                MigrationBQRedshift.cron_expression.isnot(None),
                MigrationBQRedshift.schedule_enabled == True
            ).all()
            
            logger.info(f"Found {len(migrations)} scheduled migrations")
            return migrations
            
        except Exception as e:
            logger.error(f"Failed to get scheduled migrations: {e}")
            return []
    
    def get_due_migrations(self) -> List[MigrationBQRedshift]:
        """
        Get migrations that are due to run now.
        
        Returns:
            List of migrations due for execution
        """
        try:
            now = datetime.utcnow()
            
            migrations = self.db.query(MigrationBQRedshift).filter(
                MigrationBQRedshift.schedule_type == 'recurring',
                MigrationBQRedshift.schedule_enabled == True,
                MigrationBQRedshift.next_run_time <= now,
                MigrationBQRedshift.status.in_(['pending', 'completed', 'failed'])
            ).all()
            
            logger.info(f"Found {len(migrations)} migrations due for execution")
            return migrations
            
        except Exception as e:
            logger.error(f"Failed to get due migrations: {e}")
            return []
    
    def execute_scheduled_migration(self, migration_id: int) -> bool:
        """
        Execute a scheduled migration.
        
        Args:
            migration_id: Migration ID
            
        Returns:
            True if started successfully, False otherwise
        """
        try:
            migration = self.db.query(MigrationBQRedshift).filter_by(
                id=migration_id
            ).first()
            
            if not migration:
                logger.error(f"Migration {migration_id} not found")
                return False
            
            # Start migration
            logger.info(f"Starting scheduled migration {migration_id}: {migration.migration_name}")
            success = self.orchestrator.start_migration(migration_id)
            
            if success:
                # Update next run time
                if migration.cron_expression:
                    next_run = self.calculate_next_run(migration.cron_expression)
                    migration.next_run_time = next_run
                    migration.last_run_time = datetime.utcnow()
                    self.db.commit()
                    
                    logger.info(f"Migration {migration_id} scheduled for next run at {next_run}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to execute scheduled migration {migration_id}: {e}", exc_info=True)
            return False
    
    def process_scheduled_migrations(self) -> Dict[str, int]:
        """
        Process all due scheduled migrations.
        
        This method should be called periodically (e.g., every minute) by a background worker.
        
        Returns:
            Dictionary with execution statistics
        """
        try:
            due_migrations = self.get_due_migrations()
            
            stats = {
                'total_due': len(due_migrations),
                'started': 0,
                'failed': 0
            }
            
            for migration in due_migrations:
                success = self.execute_scheduled_migration(migration.id)
                if success:
                    stats['started'] += 1
                else:
                    stats['failed'] += 1
            
            logger.info(f"Processed scheduled migrations: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to process scheduled migrations: {e}", exc_info=True)
            return {'total_due': 0, 'started': 0, 'failed': 0}
    
    def enable_schedule(self, migration_id: int) -> bool:
        """
        Enable scheduling for a migration.
        
        Args:
            migration_id: Migration ID
            
        Returns:
            True if enabled successfully, False otherwise
        """
        try:
            migration = self.db.query(MigrationBQRedshift).filter_by(
                id=migration_id
            ).first()
            
            if not migration:
                logger.error(f"Migration {migration_id} not found")
                return False
            
            if not migration.cron_expression:
                logger.error(f"Migration {migration_id} has no CRON expression")
                return False
            
            # Calculate next run time
            next_run = self.calculate_next_run(migration.cron_expression)
            
            migration.schedule_enabled = True
            migration.next_run_time = next_run
            migration.updated_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Enabled schedule for migration {migration_id}, next run: {next_run}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enable schedule for migration {migration_id}: {e}")
            return False
    
    def disable_schedule(self, migration_id: int) -> bool:
        """
        Disable scheduling for a migration.
        
        Args:
            migration_id: Migration ID
            
        Returns:
            True if disabled successfully, False otherwise
        """
        try:
            migration = self.db.query(MigrationBQRedshift).filter_by(
                id=migration_id
            ).first()
            
            if not migration:
                logger.error(f"Migration {migration_id} not found")
                return False
            
            migration.schedule_enabled = False
            migration.updated_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Disabled schedule for migration {migration_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disable schedule for migration {migration_id}: {e}")
            return False
    
    def update_schedule(self, migration_id: int, cron_expression: str) -> bool:
        """
        Update CRON schedule for a migration.
        
        Args:
            migration_id: Migration ID
            cron_expression: New CRON expression
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # Validate CRON expression
            next_run = self.calculate_next_run(cron_expression)
            
            migration = self.db.query(MigrationBQRedshift).filter_by(
                id=migration_id
            ).first()
            
            if not migration:
                logger.error(f"Migration {migration_id} not found")
                return False
            
            migration.cron_expression = cron_expression
            migration.next_run_time = next_run
            migration.updated_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(f"Updated schedule for migration {migration_id}, next run: {next_run}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update schedule for migration {migration_id}: {e}")
            return False
