"""
History Service

Service for tracking Redshift COPY commands and AWS DataSync tasks.
Provides audit trail and monitoring capabilities.
"""

import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class HistoryService:
    """
    Service for tracking Redshift COPY commands and AWS DataSync tasks.
    Provides audit trail and monitoring capabilities.
    """
    
    def __init__(
        self,
        db: Session,
        redis_client: Optional[Any] = None
    ):
        """
        Initialize history service.
        
        Args:
            db: Database session
            redis_client: Redis client for caching
        """
        self.db = db
        self.redis_client = redis_client
        self.logger = logger
        
        # Initialize AWS DataSync client
        try:
            import os
            aws_region = os.getenv('AWS_DATASYNC_REGION', 'us-east-1')
            self.datasync_client = boto3.client('datasync', region_name=aws_region)
        except Exception as e:
            self.logger.warning(f"Failed to initialize DataSync client: {str(e)}")
            self.datasync_client = None
    
    async def create_copy_history(
        self,
        migration_id: int,
        workspace_id: int,
        copy_command: str,
        source_uri: str,
        table_name: str,
        schema_name: Optional[str] = None,
        migration_name: Optional[str] = None,
        file_format: Optional[str] = None,
        compression: Optional[str] = None,
        iam_role_arn: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create Copy History record for Redshift COPY command.
        
        Args:
            migration_id: Migration identifier
            workspace_id: Workspace identifier
            copy_command: Full COPY command text
            source_uri: S3 source URI
            table_name: Target table name
            schema_name: Target schema name
            migration_name: Migration name
            file_format: File format (CSV, JSON, PARQUET)
            compression: Compression type (GZIP, BZIP2)
            iam_role_arn: IAM role ARN for COPY
            
        Returns:
            Copy History record as dictionary
        """
        from models.copy_history import CopyHistory as CopyHistoryModel
        
        copy_history = CopyHistoryModel(
            migration_id=migration_id,
            migration_name=migration_name,
            schema_name=schema_name,
            table_name=table_name,
            copy_command=copy_command,
            source_uri=source_uri,
            file_format=file_format,
            compression=compression,
            iam_role_arn=iam_role_arn,
            status='running'
        )
        
        self.db.add(copy_history)
        self.db.commit()
        self.db.refresh(copy_history)
        
        self.logger.info(
            f"Created Copy History record {copy_history.id} for migration {migration_id}"
        )
        
        return self._copy_history_to_dict(copy_history)
    
    async def update_copy_history(
        self,
        copy_history_id: int,
        workspace_id: int,
        status: str,
        rows_loaded: Optional[int] = None,
        bytes_loaded: Optional[int] = None,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update Copy History with completion status.
        
        Args:
            copy_history_id: Copy History record ID
            workspace_id: Workspace identifier
            status: Completion status (completed, failed)
            rows_loaded: Number of rows loaded
            bytes_loaded: Bytes loaded
            error_message: Error details if failed
            error_details: Additional error details as JSON
            
        Returns:
            Updated Copy History record
        """
        from models.copy_history import CopyHistory as CopyHistoryModel
        
        copy_history = self.db.query(CopyHistoryModel).filter(
            CopyHistoryModel.id == copy_history_id
        ).first()
        
        if not copy_history:
            raise ValueError(f"Copy History {copy_history_id} not found")
        
        # Update fields
        copy_history.status = status
        copy_history.completed_at = datetime.utcnow()
        
        # Calculate duration
        if copy_history.started_at and copy_history.completed_at:
            duration = copy_history.completed_at - copy_history.started_at
            copy_history.duration_seconds = int(duration.total_seconds())
        
        if rows_loaded is not None:
            copy_history.rows_loaded = rows_loaded
        
        if bytes_loaded is not None:
            copy_history.bytes_loaded = bytes_loaded
        
        if error_message:
            copy_history.error_message = error_message
        
        if error_details:
            copy_history.error_details = error_details
        
        self.db.commit()
        self.db.refresh(copy_history)
        
        # Invalidate cache
        self._invalidate_copy_history_cache(copy_history.migration_id)
        
        self.logger.info(
            f"Updated Copy History {copy_history_id} to status {status}"
        )
        
        return self._copy_history_to_dict(copy_history)
    
    async def create_task_history(
        self,
        migration_id: int,
        workspace_id: int,
        task_arn: str,
        agent_arn: str,
        agent_ip: str,
        source_uri: str,
        dest_uri: str,
        task_name: Optional[str] = None,
        task_type: Optional[str] = None,
        table_name: Optional[str] = None,
        migration_name: Optional[str] = None,
        execution_arn: Optional[str] = None,
        source_location_arn: Optional[str] = None,
        dest_location_arn: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create Task History record for DataSync task.
        
        Args:
            migration_id: Migration identifier
            workspace_id: Workspace identifier
            task_arn: DataSync task ARN
            agent_arn: DataSync agent ARN
            agent_ip: Agent VM IP address
            source_uri: GCS source URI
            dest_uri: S3 destination URI
            task_name: Task name
            task_type: Task type
            table_name: Table name
            migration_name: Migration name
            execution_arn: Execution ARN
            source_location_arn: Source location ARN
            dest_location_arn: Destination location ARN
            
        Returns:
            Task History record as dictionary
        """
        from models.task_history import TaskHistory as TaskHistoryModel
        
        task_history = TaskHistoryModel(
            migration_id=migration_id,
            migration_name=migration_name,
            task_arn=task_arn,
            execution_arn=execution_arn,
            task_name=task_name,
            task_type=task_type,
            agent_arn=agent_arn,
            agent_ip=agent_ip,
            source_location_arn=source_location_arn,
            source_uri=source_uri,
            dest_location_arn=dest_location_arn,
            dest_uri=dest_uri,
            table_name=table_name,
            status='running'
        )
        
        self.db.add(task_history)
        self.db.commit()
        self.db.refresh(task_history)
        
        # Update agent last_used_at
        await self._update_agent_last_used(agent_ip, workspace_id)
        
        self.logger.info(
            f"Created Task History record {task_history.id} for migration {migration_id}"
        )
        
        return self._task_history_to_dict(task_history)
    
    async def update_task_history(
        self,
        task_history_id: int,
        workspace_id: int,
        status: str,
        files_transferred: Optional[int] = None,
        bytes_transferred: Optional[int] = None,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None,
        raw_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update Task History with completion status"""
        from models.task_history import TaskHistory as TaskHistoryModel
        
        task_history = self.db.query(TaskHistoryModel).filter(
            TaskHistoryModel.id == task_history_id
        ).first()
        
        if not task_history:
            raise ValueError(f"Task History {task_history_id} not found")
        
        # Update fields
        task_history.status = status
        task_history.completed_at = datetime.utcnow()
        
        # Calculate duration
        if task_history.started_at and task_history.completed_at:
            duration = task_history.completed_at - task_history.started_at
            task_history.duration_seconds = int(duration.total_seconds())
        
        if files_transferred is not None:
            task_history.files_transferred = files_transferred
        
        if bytes_transferred is not None:
            task_history.bytes_transferred = bytes_transferred
        
        if error_message:
            task_history.error_message = error_message
        
        if error_code:
            task_history.error_code = error_code
        
        if error_details:
            task_history.error_details = error_details
        
        if raw_result:
            task_history.raw_result = raw_result
        
        self.db.commit()
        self.db.refresh(task_history)
        
        # Invalidate cache
        self._invalidate_task_history_cache(task_history.migration_id)
        
        self.logger.info(
            f"Updated Task History {task_history_id} to status {status}"
        )
        
        return self._task_history_to_dict(task_history)
    
    async def register_datasync_agent(
        self,
        workspace_id: int,
        vm_ip: str,
        aws_region: str
    ) -> Dict[str, Any]:
        """
        Register or retrieve DataSync agent.
        
        Args:
            workspace_id: Workspace identifier
            vm_ip: Agent VM IP address
            aws_region: AWS region
            
        Returns:
            DataSync Agent record with agent_arn
        """
        from models.datasync_agent import DataSyncAgent as DataSyncAgentModel
        
        # Check if agent already registered
        existing_agent = self.db.query(DataSyncAgentModel).filter(
            and_(
                DataSyncAgentModel.vm_ip == vm_ip,
                DataSyncAgentModel.workspace_id == workspace_id
            )
        ).first()
        
        if existing_agent:
            self.logger.info(f"Reusing existing agent for VM IP {vm_ip}")
            return self._agent_to_dict(existing_agent)
        
        # Register new agent with AWS DataSync
        if not self.datasync_client:
            raise ValueError("DataSync client not initialized")
        
        try:
            # TODO: Actual agent registration with AWS DataSync
            # For now, create placeholder agent_arn
            agent_arn = f"arn:aws:datasync:{aws_region}:123456789012:agent/agent-{vm_ip.replace('.', '-')}"
            
            # Create agent record
            agent = DataSyncAgentModel(
                workspace_id=workspace_id,
                vm_ip=vm_ip,
                agent_arn=agent_arn,
                aws_region=aws_region,
                status='unknown'
            )
            
            self.db.add(agent)
            self.db.commit()
            self.db.refresh(agent)
            
            # Check agent health
            await self.check_agent_health(agent.id, workspace_id)
            
            self.logger.info(f"Registered new DataSync agent {agent.id} for VM {vm_ip}")
            
            return self._agent_to_dict(agent)
            
        except Exception as e:
            self.logger.error(f"Failed to register agent: {str(e)}")
            raise
    
    async def check_agent_health(
        self,
        agent_id: int,
        workspace_id: int
    ) -> Dict[str, Any]:
        """
        Check DataSync agent health status.
        
        Args:
            agent_id: Agent record ID
            workspace_id: Workspace identifier
            
        Returns:
            Agent health status
        """
        from models.datasync_agent import DataSyncAgent as DataSyncAgentModel
        
        agent = self.db.query(DataSyncAgentModel).filter(
            and_(
                DataSyncAgentModel.id == agent_id,
                DataSyncAgentModel.workspace_id == workspace_id
            )
        ).first()
        
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        if not self.datasync_client:
            return {
                'agent_id': agent.id,
                'status': 'unknown',
                'last_checked': datetime.utcnow(),
                'error_message': 'DataSync client not initialized'
            }
        
        try:
            # Call AWS DataSync DescribeAgent API
            response = self.datasync_client.describe_agent(
                AgentArn=agent.agent_arn
            )
            
            # Parse status
            agent_status = response.get('Status', 'UNKNOWN')
            
            if agent_status == 'ONLINE':
                status = 'online'
            elif agent_status == 'OFFLINE':
                status = 'offline'
            else:
                status = 'unknown'
            
            # Update agent status
            agent.status = status
            self.db.commit()
            
            return {
                'agent_id': agent.id,
                'status': status,
                'last_checked': datetime.utcnow(),
                'error_message': None
            }
            
        except ClientError as e:
            error_message = str(e)
            self.logger.error(f"Agent health check failed: {error_message}")
            
            # Update status to unknown
            agent.status = 'unknown'
            self.db.commit()
            
            return {
                'agent_id': agent.id,
                'status': 'unknown',
                'last_checked': datetime.utcnow(),
                'error_message': error_message
            }
    
    async def get_copy_history_by_migration(
        self,
        migration_id: int,
        workspace_id: int,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get Copy History for migration.
        
        Args:
            migration_id: Migration identifier
            workspace_id: Workspace identifier
            filters: Optional filters (status, date_range)
            page: Page number
            page_size: Records per page
            
        Returns:
            Tuple of (records, total_count)
        """
        from models.copy_history import CopyHistory as CopyHistoryModel
        
        # Build query
        query = self.db.query(CopyHistoryModel).filter(
            CopyHistoryModel.migration_id == migration_id
        )
        
        # Apply filters
        if filters:
            if 'status' in filters:
                query = query.filter(CopyHistoryModel.status == filters['status'])
            
            if 'schema_name' in filters:
                query = query.filter(CopyHistoryModel.schema_name.ilike(f"%{filters['schema_name']}%"))
            
            if 'table_name' in filters:
                query = query.filter(CopyHistoryModel.table_name.ilike(f"%{filters['table_name']}%"))
        
        # Get total count
        total = query.count()
        
        # Apply pagination and sorting
        records = query.order_by(desc(CopyHistoryModel.started_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        return [self._copy_history_to_dict(r) for r in records], total
    
    async def get_task_history_by_migration(
        self,
        migration_id: int,
        workspace_id: int,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get Task History for migration.
        
        Args:
            migration_id: Migration identifier
            workspace_id: Workspace identifier
            filters: Optional filters (status, agent_ip)
            page: Page number
            page_size: Records per page
            
        Returns:
            Tuple of (records, total_count)
        """
        from models.task_history import TaskHistory as TaskHistoryModel
        
        # Build query
        query = self.db.query(TaskHistoryModel).filter(
            TaskHistoryModel.migration_id == migration_id
        )
        
        # Apply filters
        if filters:
            if 'status' in filters:
                query = query.filter(TaskHistoryModel.status == filters['status'])
            
            if 'agent_ip' in filters:
                query = query.filter(TaskHistoryModel.agent_ip == filters['agent_ip'])
        
        # Get total count
        total = query.count()
        
        # Apply pagination and sorting
        records = query.order_by(desc(TaskHistoryModel.started_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        return [self._task_history_to_dict(r) for r in records], total
    
    async def list_agents(
        self,
        workspace_id: int,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all registered DataSync agents.
        
        Args:
            workspace_id: Workspace identifier
            status_filter: Optional status filter
            
        Returns:
            List of agent records
        """
        from models.datasync_agent import DataSyncAgent as DataSyncAgentModel
        
        query = self.db.query(DataSyncAgentModel).filter(
            DataSyncAgentModel.workspace_id == workspace_id
        )
        
        if status_filter:
            query = query.filter(DataSyncAgentModel.status == status_filter)
        
        agents = query.all()
        
        return [self._agent_to_dict(a) for a in agents]
    
    async def _update_agent_last_used(self, agent_ip: str, workspace_id: int):
        """Update agent last_used_at timestamp"""
        from models.datasync_agent import DataSyncAgent as DataSyncAgentModel
        
        agent = self.db.query(DataSyncAgentModel).filter(
            and_(
                DataSyncAgentModel.vm_ip == agent_ip,
                DataSyncAgentModel.workspace_id == workspace_id
            )
        ).first()
        
        if agent:
            agent.last_used_at = datetime.utcnow()
            self.db.commit()
    
    def _copy_history_to_dict(self, copy_history: Any) -> Dict[str, Any]:
        """Convert Copy History model to dictionary"""
        return {
            'id': copy_history.id,
            'migration_id': copy_history.migration_id,
            'migration_name': copy_history.migration_name,
            'schema_name': copy_history.schema_name,
            'table_name': copy_history.table_name,
            'copy_command': copy_history.copy_command,
            'source_uri': copy_history.source_uri,
            'file_format': copy_history.file_format,
            'compression': copy_history.compression,
            'iam_role_arn': copy_history.iam_role_arn,
            'status': copy_history.status,
            'started_at': copy_history.started_at,
            'completed_at': copy_history.completed_at,
            'duration_seconds': copy_history.duration_seconds,
            'rows_loaded': copy_history.rows_loaded,
            'bytes_loaded': copy_history.bytes_loaded,
            'error_message': copy_history.error_message,
            'error_details': copy_history.error_details,
            'created_at': copy_history.created_at
        }
    
    def _task_history_to_dict(self, task_history: Any) -> Dict[str, Any]:
        """Convert Task History model to dictionary"""
        return {
            'id': task_history.id,
            'migration_id': task_history.migration_id,
            'migration_name': task_history.migration_name,
            'task_arn': task_history.task_arn,
            'execution_arn': task_history.execution_arn,
            'task_name': task_history.task_name,
            'task_type': task_history.task_type,
            'agent_arn': task_history.agent_arn,
            'agent_ip': task_history.agent_ip,
            'source_location_arn': task_history.source_location_arn,
            'source_uri': task_history.source_uri,
            'dest_location_arn': task_history.dest_location_arn,
            'dest_uri': task_history.dest_uri,
            'table_name': task_history.table_name,
            'status': task_history.status,
            'started_at': task_history.started_at,
            'completed_at': task_history.completed_at,
            'duration_seconds': task_history.duration_seconds,
            'files_transferred': task_history.files_transferred,
            'bytes_transferred': task_history.bytes_transferred,
            'error_message': task_history.error_message,
            'error_code': task_history.error_code,
            'error_details': task_history.error_details,
            'raw_result': task_history.raw_result,
            'created_at': task_history.created_at
        }
    
    def _agent_to_dict(self, agent: Any) -> Dict[str, Any]:
        """Convert DataSync Agent model to dictionary"""
        return {
            'id': agent.id,
            'workspace_id': agent.workspace_id,
            'vm_ip': agent.vm_ip,
            'agent_arn': agent.agent_arn,
            'aws_region': agent.aws_region,
            'status': agent.status,
            'last_used_at': agent.last_used_at,
            'created_at': agent.created_at,
            'updated_at': agent.updated_at
        }
    
    def _invalidate_copy_history_cache(self, migration_id: int):
        """Invalidate Copy History cache"""
        if not self.redis_client:
            return
        
        try:
            cache_key = f"copy_history:active:{migration_id}"
            self.redis_client.delete(cache_key)
        except Exception as e:
            self.logger.warning(f"Failed to invalidate cache: {str(e)}")
    
    def _invalidate_task_history_cache(self, migration_id: int):
        """Invalidate Task History cache"""
        if not self.redis_client:
            return
        
        try:
            cache_key = f"task_history:active:{migration_id}"
            self.redis_client.delete(cache_key)
        except Exception as e:
            self.logger.warning(f"Failed to invalidate cache: {str(e)}")


    async def list_copy_history(
        self,
        workspace_id: int,
        migration_id: Optional[int] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        List Copy History records with filters and pagination.

        Args:
            workspace_id: Workspace ID for isolation
            migration_id: Optional migration ID filter
            status: Optional status filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Dict with records, total count, and summary statistics
        """
        from sqlalchemy import and_, func

        # Build query
        query = self.db.query(CopyHistory)

        # Filter by workspace through migration ownership
        if migration_id:
            query = query.filter(CopyHistory.migration_id == migration_id)

        # TODO: Add workspace validation through migration table join

        if status:
            query = query.filter(CopyHistory.status == status)

        if start_date:
            query = query.filter(CopyHistory.started_at >= start_date)

        if end_date:
            query = query.filter(CopyHistory.started_at <= end_date)

        # Get total count
        total = query.count()

        # Get summary statistics
        stats = query.with_entities(
            func.sum(CopyHistory.rows_loaded).label('total_rows_loaded'),
            func.sum(CopyHistory.bytes_loaded).label('total_bytes_loaded'),
            func.count().filter(CopyHistory.status == 'completed').label('success_count'),
            func.count().filter(CopyHistory.status == 'failed').label('failure_count')
        ).first()

        # Get paginated records
        records = query.order_by(CopyHistory.started_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        return {
            'records': [self._copy_history_to_dict(r) for r in records],
            'total': total,
            'page': page,
            'page_size': page_size,
            'summary': {
                'total_rows_loaded': int(stats.total_rows_loaded or 0),
                'total_bytes_loaded': int(stats.total_bytes_loaded or 0),
                'success_count': int(stats.success_count or 0),
                'failure_count': int(stats.failure_count or 0)
            }
        }

    async def get_copy_history_by_id(
        self,
        id: int,
        workspace_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get Copy History record by ID with workspace validation.

        Args:
            id: Copy History record ID
            workspace_id: Workspace ID for validation

        Returns:
            Copy History record dict or None if not found
        """
        record = self.db.query(CopyHistory).filter(CopyHistory.id == id).first()

        if not record:
            return None

        # TODO: Validate workspace through migration ownership

        return self._copy_history_to_dict(record)

    async def list_task_history(
        self,
        workspace_id: int,
        migration_id: Optional[int] = None,
        status: Optional[str] = None,
        agent_ip: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        List Task History records with filters and pagination.

        Args:
            workspace_id: Workspace ID for isolation
            migration_id: Optional migration ID filter
            status: Optional status filter
            agent_ip: Optional agent IP filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Dict with records, total count, and summary statistics
        """
        from sqlalchemy import and_, func

        # Build query
        query = self.db.query(TaskHistory)

        # Filter by workspace through migration ownership
        if migration_id:
            query = query.filter(TaskHistory.migration_id == migration_id)

        # TODO: Add workspace validation through migration table join

        if status:
            query = query.filter(TaskHistory.status == status)

        if agent_ip:
            query = query.filter(TaskHistory.agent_ip == agent_ip)

        if start_date:
            query = query.filter(TaskHistory.started_at >= start_date)

        if end_date:
            query = query.filter(TaskHistory.started_at <= end_date)

        # Get total count
        total = query.count()

        # Get summary statistics
        stats = query.with_entities(
            func.sum(TaskHistory.files_transferred).label('total_files_transferred'),
            func.sum(TaskHistory.bytes_transferred).label('total_bytes_transferred'),
            func.count().filter(TaskHistory.status == 'agent_offline').label('agent_offline_count')
        ).first()

        # Get paginated records
        records = query.order_by(TaskHistory.started_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

        return {
            'records': [self._task_history_to_dict(r) for r in records],
            'total': total,
            'page': page,
            'page_size': page_size,
            'summary': {
                'total_files_transferred': int(stats.total_files_transferred or 0),
                'total_bytes_transferred': int(stats.total_bytes_transferred or 0),
                'agent_offline_count': int(stats.agent_offline_count or 0)
            }
        }

    async def get_task_history_by_id(
        self,
        id: int,
        workspace_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get Task History record by ID with workspace validation.

        Args:
            id: Task History record ID
            workspace_id: Workspace ID for validation

        Returns:
            Task History record dict or None if not found
        """
        record = self.db.query(TaskHistory).filter(TaskHistory.id == id).first()

        if not record:
            return None

        # TODO: Validate workspace through migration ownership

        return self._task_history_to_dict(record)

    async def list_datasync_agents(
        self,
        workspace_id: int,
        status: Optional[str] = None
    ) -> list:
        """
        List DataSync agents with optional status filter.

        Args:
            workspace_id: Workspace ID for isolation
            status: Optional status filter (online, offline, unknown)

        Returns:
            List of agent dicts
        """
        query = self.db.query(DataSyncAgent).filter(
            DataSyncAgent.workspace_id == workspace_id
        )

        if status:
            query = query.filter(DataSyncAgent.status == status)

        agents = query.order_by(DataSyncAgent.last_used_at.desc()).all()

        return [self._agent_to_dict(agent) for agent in agents]

    async def delete_datasync_agent(
        self,
        agent_id: int,
        workspace_id: int
    ) -> Dict[str, Any]:
        """
        Delete DataSync agent if not in use.

        Args:
            agent_id: Agent ID to delete
            workspace_id: Workspace ID for validation

        Returns:
            Dict with success status and message
        """
        # Get agent
        agent = self.db.query(DataSyncAgent).filter(
            and_(
                DataSyncAgent.id == agent_id,
                DataSyncAgent.workspace_id == workspace_id
            )
        ).first()

        if not agent:
            return {
                'success': False,
                'message': 'Agent not found or access denied'
            }

        # Check if agent is used by active migrations
        active_tasks = self.db.query(TaskHistory).filter(
            and_(
                TaskHistory.agent_ip == agent.vm_ip,
                TaskHistory.status.in_(['running', 'pending'])
            )
        ).count()

        if active_tasks > 0:
            return {
                'success': False,
                'message': f'Agent is in use by {active_tasks} active task(s)'
            }

        # Delete agent
        self.db.delete(agent)
        self.db.commit()

        logger.info(f"Deleted DataSync agent {agent_id} from workspace {workspace_id}")

        return {
            'success': True,
            'message': 'Agent deleted successfully'
        }


from models.history_db import CopyHistory, TaskHistory, DataSyncAgent
