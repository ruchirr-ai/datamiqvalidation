"""
Checkpoint Manager for BigQuery to Redshift Migrations

Handles state management, checkpointing, and resume logic for large-scale migrations.
Implements granular shard-level tracking for robust resumability.
"""

import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from sqlalchemy.orm import Session

from models.bq_redshift_migration import MigrationBQRedshift, MigrationShard, MigrationLog

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manages migration checkpoints and resume logic.
    
    Key Features:
    - Shard-level granularity for precise resume points
    - Automatic detection of incomplete operations
    - State persistence to database
    - Recovery from any stage failure
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def save_checkpoint(
        self,
        migration_id: int,
        stage: str,
        data: Dict
    ) -> None:
        """
        Save current migration state as a checkpoint.
        
        Args:
            migration_id: Migration ID
            stage: Current stage (export, transfer, load)
            data: Checkpoint data to save
        """
        try:
            migration = self.db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
            if not migration:
                raise ValueError(f"Migration {migration_id} not found")
            
            checkpoint = {
                'stage': stage,
                'timestamp': datetime.utcnow().isoformat(),
                'data': data
            }
            
            migration.checkpoint_data = checkpoint
            migration.current_stage = stage
            migration.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(
                f"Checkpoint saved for migration {migration_id} at stage {stage}",
                extra={'migration_id': migration_id, 'stage': stage}
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                f"Failed to save checkpoint for migration {migration_id}: {e}",
                extra={'migration_id': migration_id, 'error': str(e)}
            )
            raise
    
    def load_checkpoint(self, migration_id: int) -> Optional[Dict]:
        """
        Load the last checkpoint for a migration.
        
        Args:
            migration_id: Migration ID
            
        Returns:
            Checkpoint data or None if no checkpoint exists
        """
        try:
            migration = self.db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
            if not migration:
                raise ValueError(f"Migration {migration_id} not found")
            
            return migration.checkpoint_data
            
        except Exception as e:
            logger.error(
                f"Failed to load checkpoint for migration {migration_id}: {e}",
                extra={'migration_id': migration_id, 'error': str(e)}
            )
            return None
    
    def get_resume_point(self, migration_id: int) -> Tuple[str, List[MigrationShard]]:
        """
        Determine where to resume a migration and which shards need processing.
        
        This is the core of the resume logic. It analyzes all shards to find:
        1. Which stage has incomplete work
        2. Which specific shards need to be processed
        
        Args:
            migration_id: Migration ID
            
        Returns:
            Tuple of (stage_name, list_of_shards_to_process)
            stage_name: 'export', 'transfer', 'load', or 'completed'
        """
        try:
            # Get all shards for this migration
            shards = self.db.query(MigrationShard).filter_by(
                migration_id=migration_id
            ).all()
            
            if not shards:
                logger.info(f"No shards found for migration {migration_id}, starting from export")
                return 'export', []
            
            # Categorize shards by status
            pending_export = [s for s in shards if s.export_status in ('pending', 'failed')]
            pending_transfer = [s for s in shards if s.export_status == 'completed' and s.transfer_status in ('pending', 'failed')]
            pending_load = [s for s in shards if s.transfer_status == 'completed' and s.load_status in ('pending', 'failed')]
            
            # Determine resume point based on what's incomplete
            if pending_export:
                logger.info(
                    f"Migration {migration_id}: Resuming from EXPORT stage "
                    f"({len(pending_export)} shards pending)"
                )
                return 'export', pending_export
                
            elif pending_transfer:
                logger.info(
                    f"Migration {migration_id}: Resuming from TRANSFER stage "
                    f"({len(pending_transfer)} shards pending)"
                )
                return 'transfer', pending_transfer
                
            elif pending_load:
                logger.info(
                    f"Migration {migration_id}: Resuming from LOAD stage "
                    f"({len(pending_load)} shards pending)"
                )
                return 'load', pending_load
                
            else:
                logger.info(f"Migration {migration_id}: All shards completed")
                return 'completed', []
                
        except Exception as e:
            logger.error(
                f"Failed to determine resume point for migration {migration_id}: {e}",
                extra={'migration_id': migration_id, 'error': str(e)}
            )
            raise
    
    def mark_shard_export_started(self, shard_id: int) -> None:
        """Mark a shard's export as started"""
        self._update_shard_status(shard_id, 'export_status', 'running')
    
    def mark_shard_export_completed(
        self,
        shard_id: int,
        gcs_uri: str,
        file_size: int,
        row_count: int,
        checksum: str
    ) -> None:
        """
        Mark a shard's export as completed with metadata.
        
        Args:
            shard_id: Shard ID
            gcs_uri: GCS URI where shard was exported
            file_size: File size in bytes
            row_count: Number of rows in shard
            checksum: SHA256 checksum of file
        """
        try:
            shard = self.db.query(MigrationShard).filter_by(id=shard_id).first()
            if not shard:
                raise ValueError(f"Shard {shard_id} not found")
            
            shard.export_status = 'completed'
            shard.export_completed_at = datetime.utcnow()
            shard.gcs_uri = gcs_uri
            shard.file_size_bytes = file_size
            shard.row_count = row_count
            shard.checksum = checksum
            shard.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(
                f"Shard {shard_id} export completed: {row_count} rows, "
                f"{file_size / (1024**2):.2f} MB",
                extra={
                    'shard_id': shard_id,
                    'gcs_uri': gcs_uri,
                    'row_count': row_count,
                    'file_size_bytes': file_size
                }
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to mark shard {shard_id} export completed: {e}")
            raise
    
    def mark_shard_export_failed(self, shard_id: int, error: str) -> None:
        """Mark a shard's export as failed"""
        self._update_shard_status(shard_id, 'export_status', 'failed', error)
    
    def mark_shard_transfer_started(self, shard_id: int) -> None:
        """Mark a shard's transfer as started"""
        self._update_shard_status(shard_id, 'transfer_status', 'running')
    
    def mark_shard_transfer_completed(self, shard_id: int, s3_uri: str) -> None:
        """
        Mark a shard's transfer as completed.
        
        Args:
            shard_id: Shard ID
            s3_uri: S3 URI where shard was transferred
        """
        try:
            shard = self.db.query(MigrationShard).filter_by(id=shard_id).first()
            if not shard:
                raise ValueError(f"Shard {shard_id} not found")
            
            shard.transfer_status = 'completed'
            shard.transfer_completed_at = datetime.utcnow()
            shard.s3_uri = s3_uri
            shard.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(
                f"Shard {shard_id} transfer completed to {s3_uri}",
                extra={'shard_id': shard_id, 's3_uri': s3_uri}
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to mark shard {shard_id} transfer completed: {e}")
            raise
    
    def mark_shard_transfer_failed(self, shard_id: int, error: str) -> None:
        """Mark a shard's transfer as failed"""
        self._update_shard_status(shard_id, 'transfer_status', 'failed', error)
    
    def mark_shard_load_started(self, shard_id: int) -> None:
        """Mark a shard's load as started"""
        self._update_shard_status(shard_id, 'load_status', 'running')
    
    def mark_shard_load_completed(self, shard_id: int) -> None:
        """Mark a shard's load as completed"""
        try:
            shard = self.db.query(MigrationShard).filter_by(id=shard_id).first()
            if not shard:
                raise ValueError(f"Shard {shard_id} not found")
            
            shard.load_status = 'completed'
            shard.load_completed_at = datetime.utcnow()
            shard.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(
                f"Shard {shard_id} load completed",
                extra={'shard_id': shard_id}
            )
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to mark shard {shard_id} load completed: {e}")
            raise
    
    def mark_shard_load_failed(self, shard_id: int, error: str) -> None:
        """Mark a shard's load as failed"""
        self._update_shard_status(shard_id, 'load_status', 'failed', error)
    
    def _update_shard_status(
        self,
        shard_id: int,
        status_field: str,
        status: str,
        error: Optional[str] = None
    ) -> None:
        """
        Internal method to update shard status.
        
        Args:
            shard_id: Shard ID
            status_field: Field to update (export_status, transfer_status, load_status)
            status: New status value
            error: Error message if status is 'failed'
        """
        try:
            shard = self.db.query(MigrationShard).filter_by(id=shard_id).first()
            if not shard:
                raise ValueError(f"Shard {shard_id} not found")
            
            setattr(shard, status_field, status)
            shard.updated_at = datetime.utcnow()
            
            if error:
                shard.last_error = error
                shard.last_error_time = datetime.utcnow()
                shard.retry_count += 1
            
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update shard {shard_id} status: {e}")
            raise
    
    def get_migration_progress(self, migration_id: int) -> Dict:
        """
        Calculate overall migration progress.
        
        Args:
            migration_id: Migration ID
            
        Returns:
            Dictionary with progress metrics
        """
        try:
            shards = self.db.query(MigrationShard).filter_by(
                migration_id=migration_id
            ).all()
            
            if not shards:
                return {
                    'total_shards': 0,
                    'completed_shards': 0,
                    'failed_shards': 0,
                    'progress_percentage': 0.0
                }
            
            total = len(shards)
            completed = sum(1 for s in shards if s.is_completed())
            failed = sum(1 for s in shards if s.has_failed())
            
            return {
                'total_shards': total,
                'completed_shards': completed,
                'failed_shards': failed,
                'progress_percentage': (completed / total * 100) if total > 0 else 0.0,
                'export_completed': sum(1 for s in shards if s.export_status == 'completed'),
                'transfer_completed': sum(1 for s in shards if s.transfer_status == 'completed'),
                'load_completed': sum(1 for s in shards if s.load_status == 'completed')
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate progress for migration {migration_id}: {e}")
            return {
                'total_shards': 0,
                'completed_shards': 0,
                'failed_shards': 0,
                'progress_percentage': 0.0,
                'error': str(e)
            }
    
    def can_resume(self, migration_id: int) -> bool:
        """
        Check if a migration can be resumed.
        
        Args:
            migration_id: Migration ID
            
        Returns:
            True if migration can be resumed, False otherwise
        """
        try:
            migration = self.db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
            if not migration:
                return False
            
            # Can resume if status is paused or failed
            return migration.status in ('paused', 'failed')
            
        except Exception as e:
            logger.error(f"Failed to check if migration {migration_id} can resume: {e}")
            return False
    
    def reset_failed_shards(self, migration_id: int) -> int:
        """
        Reset failed shards to pending status for retry.
        
        Args:
            migration_id: Migration ID
            
        Returns:
            Number of shards reset
        """
        try:
            shards = self.db.query(MigrationShard).filter_by(
                migration_id=migration_id
            ).all()
            
            reset_count = 0
            for shard in shards:
                if shard.export_status == 'failed':
                    shard.export_status = 'pending'
                    reset_count += 1
                if shard.transfer_status == 'failed':
                    shard.transfer_status = 'pending'
                    reset_count += 1
                if shard.load_status == 'failed':
                    shard.load_status = 'pending'
                    reset_count += 1
            
            self.db.commit()
            
            logger.info(
                f"Reset {reset_count} failed shard statuses for migration {migration_id}",
                extra={'migration_id': migration_id, 'reset_count': reset_count}
            )
            
            return reset_count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to reset failed shards for migration {migration_id}: {e}")
            raise
