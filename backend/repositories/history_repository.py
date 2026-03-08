"""
History Repository

Database operations for copy history, task history, and related entities
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, asc
from typing import List, Optional, Dict, Any
from datetime import datetime

from models.copy_history import CopyHistory
from models.task_history import TaskHistory
from models.bq_redshift_migration import BQRedshiftMigration


class HistoryRepository:
    """Repository for history-related database operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== Copy History Methods ====================
    
    def create_copy_history(
        self,
        migration_id: int,
        schema_name: str,
        table_name: str,
        copy_command: str,
        status: str = 'running'
    ) -> CopyHistory:
        """Create a new copy history record"""
        copy_history = CopyHistory(
            migration_id=migration_id,
            schema_name=schema_name,
            table_name=table_name,
            copy_command=copy_command,
            status=status,
            started_at=datetime.utcnow()
        )
        self.db.add(copy_history)
        self.db.commit()
        self.db.refresh(copy_history)
        return copy_history
    
    def update_copy_history(
        self,
        copy_history_id: int,
        status: str,
        rows_loaded: Optional[int] = None,
        bytes_loaded: Optional[int] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> Optional[CopyHistory]:
        """Update copy history record with completion details"""
        copy_history = self.db.query(CopyHistory).filter(
            CopyHistory.id == copy_history_id
        ).first()
        
        if not copy_history:
            return None
        
        copy_history.status = status
        copy_history.completed_at = datetime.utcnow()
        
        if rows_loaded is not None:
            copy_history.rows_loaded = rows_loaded
        if bytes_loaded is not None:
            copy_history.bytes_loaded = bytes_loaded
        if error_details is not None:
            copy_history.error_details = error_details
        
        # Calculate duration
        if copy_history.started_at and copy_history.completed_at:
            duration = copy_history.completed_at - copy_history.started_at
            copy_history.duration_seconds = int(duration.total_seconds())
        
        self.db.commit()
        self.db.refresh(copy_history)
        return copy_history
    
    def get_copy_history_by_id(
        self,
        copy_history_id: int,
        workspace_id: int
    ) -> Optional[CopyHistory]:
        """Get copy history by ID with workspace validation"""
        # Join with migration to validate workspace
        return self.db.query(CopyHistory).join(
            BQRedshiftMigration,
            CopyHistory.migration_id == BQRedshiftMigration.id
        ).filter(
            and_(
                CopyHistory.id == copy_history_id,
                BQRedshiftMigration.workspace_id == workspace_id
            )
        ).first()
    
    def get_copy_history_by_migration(
        self,
        migration_id: int,
        workspace_id: int,
        status: Optional[str] = None,
        sort_by: str = 'started_at',
        sort_order: str = 'desc',
        page: int = 1,
        page_size: int = 50
    ) -> List[CopyHistory]:
        """Get copy history records for a migration with filters and pagination"""
        # First validate migration belongs to workspace
        migration = self.db.query(BQRedshiftMigration).filter(
            and_(
                BQRedshiftMigration.id == migration_id,
                BQRedshiftMigration.workspace_id == workspace_id
            )
        ).first()
        
        if not migration:
            return []
        
        query = self.db.query(CopyHistory).filter(
            CopyHistory.migration_id == migration_id
        )
        
        if status:
            query = query.filter(CopyHistory.status == status)
        
        # Sorting
        sort_column = getattr(CopyHistory, sort_by, CopyHistory.started_at)
        if sort_order == 'asc':
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))
        
        # Pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        return query.all()
    
    def list_copy_history(
        self,
        workspace_id: int,
        migration_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> List[CopyHistory]:
        """List copy history records with workspace isolation"""
        query = self.db.query(CopyHistory).join(
            BQRedshiftMigration,
            CopyHistory.migration_id == BQRedshiftMigration.id
        ).filter(
            BQRedshiftMigration.workspace_id == workspace_id
        )
        
        if migration_id:
            query = query.filter(CopyHistory.migration_id == migration_id)
        if status:
            query = query.filter(CopyHistory.status == status)
        
        offset = (page - 1) * page_size
        query = query.order_by(desc(CopyHistory.started_at))
        query = query.offset(offset).limit(page_size)
        
        return query.all()
    
    # ==================== Task History Methods ====================
    
    def create_task_history(
        self,
        migration_id: int,
        task_name: str,
        task_arn: str,
        agent_arn: str,
        agent_ip: str,
        source_uri: str,
        dest_uri: str,
        status: str = 'running'
    ) -> TaskHistory:
        """Create a new task history record"""
        task_history = TaskHistory(
            migration_id=migration_id,
            task_name=task_name,
            task_arn=task_arn,
            agent_arn=agent_arn,
            agent_ip=agent_ip,
            source_uri=source_uri,
            dest_uri=dest_uri,
            status=status,
            started_at=datetime.utcnow()
        )
        self.db.add(task_history)
        self.db.commit()
        self.db.refresh(task_history)
        return task_history
    
    def update_task_history(
        self,
        task_history_id: int,
        status: str,
        files_transferred: Optional[int] = None,
        bytes_transferred: Optional[int] = None,
        error_details: Optional[Dict[str, Any]] = None,
        raw_result: Optional[Dict[str, Any]] = None
    ) -> Optional[TaskHistory]:
        """Update task history record with completion details"""
        task_history = self.db.query(TaskHistory).filter(
            TaskHistory.id == task_history_id
        ).first()
        
        if not task_history:
            return None
        
        task_history.status = status
        task_history.completed_at = datetime.utcnow()
        
        if files_transferred is not None:
            task_history.files_transferred = files_transferred
        if bytes_transferred is not None:
            task_history.bytes_transferred = bytes_transferred
        if error_details is not None:
            task_history.error_details = error_details
        if raw_result is not None:
            task_history.raw_result = raw_result
        
        # Calculate duration
        if task_history.started_at and task_history.completed_at:
            duration = task_history.completed_at - task_history.started_at
            task_history.duration_seconds = int(duration.total_seconds())
        
        self.db.commit()
        self.db.refresh(task_history)
        return task_history
    
    def get_task_history_by_id(
        self,
        task_history_id: int,
        workspace_id: int
    ) -> Optional[TaskHistory]:
        """Get task history by ID with workspace validation"""
        # Join with migration to validate workspace
        return self.db.query(TaskHistory).join(
            BQRedshiftMigration,
            TaskHistory.migration_id == BQRedshiftMigration.id
        ).filter(
            and_(
                TaskHistory.id == task_history_id,
                BQRedshiftMigration.workspace_id == workspace_id
            )
        ).first()
    
    def get_task_history_by_migration(
        self,
        migration_id: int,
        workspace_id: int,
        status: Optional[str] = None,
        agent_ip: Optional[str] = None,
        sort_by: str = 'started_at',
        sort_order: str = 'desc',
        page: int = 1,
        page_size: int = 50
    ) -> List[TaskHistory]:
        """Get task history records for a migration with filters and pagination"""
        # First validate migration belongs to workspace
        migration = self.db.query(BQRedshiftMigration).filter(
            and_(
                BQRedshiftMigration.id == migration_id,
                BQRedshiftMigration.workspace_id == workspace_id
            )
        ).first()
        
        if not migration:
            return []
        
        query = self.db.query(TaskHistory).filter(
            TaskHistory.migration_id == migration_id
        )
        
        if status:
            query = query.filter(TaskHistory.status == status)
        if agent_ip:
            query = query.filter(TaskHistory.agent_ip == agent_ip)
        
        # Sorting
        sort_column = getattr(TaskHistory, sort_by, TaskHistory.started_at)
        if sort_order == 'asc':
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))
        
        # Pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        return query.all()
    
    def list_task_history(
        self,
        workspace_id: int,
        migration_id: Optional[int] = None,
        status: Optional[str] = None,
        agent_ip: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> List[TaskHistory]:
        """List task history records with workspace isolation"""
        query = self.db.query(TaskHistory).join(
            BQRedshiftMigration,
            TaskHistory.migration_id == BQRedshiftMigration.id
        ).filter(
            BQRedshiftMigration.workspace_id == workspace_id
        )
        
        if migration_id:
            query = query.filter(TaskHistory.migration_id == migration_id)
        if status:
            query = query.filter(TaskHistory.status == status)
        if agent_ip:
            query = query.filter(TaskHistory.agent_ip == agent_ip)
        
        offset = (page - 1) * page_size
        query = query.order_by(desc(TaskHistory.started_at))
        query = query.offset(offset).limit(page_size)
        
        return query.all()
