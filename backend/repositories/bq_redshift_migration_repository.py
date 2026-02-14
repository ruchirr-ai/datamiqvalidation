"""
BigQuery to Redshift Migration Repository

Data access layer for migration operations.
"""

from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from models.bq_redshift_migration import MigrationBQRedshift, MigrationShard, MigrationLog


class BQRedshiftMigrationRepository:
    """Repository for BigQuery to Redshift migration operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_migration(self, migration_data: Dict) -> MigrationBQRedshift:
        """Create a new migration"""
        migration = MigrationBQRedshift(**migration_data)
        self.db.add(migration)
        self.db.commit()
        self.db.refresh(migration)
        return migration
    
    def get_migration_by_id(self, migration_id: int) -> Optional[MigrationBQRedshift]:
        """Get migration by ID"""
        return self.db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
    
    def get_migrations_by_workspace(
        self,
        workspace_id: int,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[MigrationBQRedshift]:
        """Get migrations for a workspace with optional filtering"""
        query = self.db.query(MigrationBQRedshift).filter_by(workspace_id=workspace_id)
        
        if status:
            query = query.filter_by(status=status)
        
        return query.order_by(MigrationBQRedshift.created_at.desc()).limit(limit).offset(offset).all()
    
    def update_migration(self, migration_id: int, updates: Dict) -> Optional[MigrationBQRedshift]:
        """Update migration fields"""
        migration = self.get_migration_by_id(migration_id)
        if not migration:
            return None
        
        for key, value in updates.items():
            if hasattr(migration, key):
                setattr(migration, key, value)
        
        self.db.commit()
        self.db.refresh(migration)
        return migration
    
    def delete_migration(self, migration_id: int) -> bool:
        """Delete a migration"""
        migration = self.get_migration_by_id(migration_id)
        if not migration:
            return False
        
        self.db.delete(migration)
        self.db.commit()
        return True
    
    def create_shard(self, shard_data: Dict) -> MigrationShard:
        """Create a new shard"""
        shard = MigrationShard(**shard_data)
        self.db.add(shard)
        self.db.commit()
        self.db.refresh(shard)
        return shard
    
    def get_shards_by_migration(self, migration_id: int) -> List[MigrationShard]:
        """Get all shards for a migration"""
        return self.db.query(MigrationShard).filter_by(migration_id=migration_id).all()
    
    def get_shard_by_id(self, shard_id: int) -> Optional[MigrationShard]:
        """Get shard by ID"""
        return self.db.query(MigrationShard).filter_by(id=shard_id).first()
    
    def create_log(self, log_data: Dict) -> MigrationLog:
        """Create a log entry"""
        log = MigrationLog(**log_data)
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log
    
    def get_logs_by_migration(
        self,
        migration_id: int,
        level: Optional[str] = None,
        limit: int = 1000
    ) -> List[MigrationLog]:
        """Get logs for a migration"""
        query = self.db.query(MigrationLog).filter_by(migration_id=migration_id)
        
        if level:
            query = query.filter_by(log_level=level)
        
        return query.order_by(MigrationLog.created_at.desc()).limit(limit).all()
    
    def get_scheduled_migrations(self) -> List[MigrationBQRedshift]:
        """Get migrations that are due to run"""
        from datetime import datetime
        
        return self.db.query(MigrationBQRedshift).filter(
            and_(
                MigrationBQRedshift.schedule_type == 'recurring',
                MigrationBQRedshift.next_run_time <= datetime.utcnow(),
                MigrationBQRedshift.status.in_(['pending', 'completed'])
            )
        ).all()
