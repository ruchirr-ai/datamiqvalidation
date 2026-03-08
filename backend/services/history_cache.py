"""
History Cache Service

Implements cache-aside pattern for copy history, task history, and DataSync agents with Redis fallback to PostgreSQL
"""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from shared.redis_client import get_redis_client
from repositories.history_repository import HistoryRepository
from repositories.agent_repository import AgentRepository

logger = logging.getLogger(__name__)


class HistoryCache:
    """Cache service for history operations with database fallback"""
    
    # TTL values in seconds
    TTL_ACTIVE_COPY = 60  # 1 minute for active copy operations
    TTL_COPY_LIST = 300  # 5 minutes for copy history lists
    TTL_ACTIVE_TASK = 60  # 1 minute for active task operations
    TTL_TASK_LIST = 300  # 5 minutes for task history lists
    TTL_AGENT = 3600  # 1 hour for agent registry
    
    def __init__(self, history_repository: HistoryRepository, agent_repository: AgentRepository):
        self.history_repository = history_repository
        self.agent_repository = agent_repository
        self.redis_client = get_redis_client()
    
    # ==================== Copy History Cache Methods ====================
    
    def _get_copy_history_key(self, copy_history_id: int) -> str:
        """Generate cache key for copy history record"""
        return f"copy_history:record:{copy_history_id}"
    
    def _get_active_copy_key(self, migration_id: int) -> str:
        """Generate cache key for active copy operations"""
        return f"copy_history:active:{migration_id}"
    
    def _get_copy_list_key(self, migration_id: int, status: Optional[str] = None) -> str:
        """Generate cache key for copy history list"""
        status_suffix = f":{status}" if status else ":all"
        return f"copy_history:list:{migration_id}{status_suffix}"
    
    def _serialize_copy_history(self, copy_history) -> str:
        """Serialize copy history object to JSON"""
        return json.dumps({
            'id': copy_history.id,
            'migration_id': copy_history.migration_id,
            'schema_name': copy_history.schema_name,
            'table_name': copy_history.table_name,
            'copy_command': copy_history.copy_command,
            'status': copy_history.status,
            'rows_loaded': copy_history.rows_loaded,
            'bytes_loaded': copy_history.bytes_loaded,
            'duration_seconds': copy_history.duration_seconds,
            'error_details': copy_history.error_details,
            'started_at': copy_history.started_at.isoformat() if copy_history.started_at else None,
            'completed_at': copy_history.completed_at.isoformat() if copy_history.completed_at else None
        })
    
    def get_copy_history(self, copy_history_id: int, workspace_id: int) -> Optional[Dict[str, Any]]:
        """Get copy history record with cache-aside pattern"""
        cache_key = self._get_copy_history_key(copy_history_id)
        
        # Try Redis first
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    logger.debug(f"Cache hit for copy history {copy_history_id}")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Redis get failed for copy history {copy_history_id}: {e}, falling back to database")
        
        # Cache miss or Redis unavailable - fetch from database
        logger.debug(f"Cache miss for copy history {copy_history_id}, fetching from database")
        copy_history = self.history_repository.get_copy_history_by_id(copy_history_id, workspace_id)
        
        if not copy_history:
            return None
        
        # Serialize
        copy_data = self._serialize_copy_history(copy_history)
        
        # Try to cache for next time (best effort)
        if self.redis_client:
            try:
                ttl = self.TTL_ACTIVE_COPY if copy_history.status == 'running' else self.TTL_COPY_LIST
                self.redis_client.setex(cache_key, ttl, copy_data)
                logger.debug(f"Cached copy history {copy_history_id} with TTL {ttl}s")
            except Exception as e:
                logger.warning(f"Failed to cache copy history {copy_history_id}: {e}")
        
        return json.loads(copy_data)
    
    def invalidate_copy_history(self, copy_history_id: int, migration_id: int):
        """Invalidate copy history cache"""
        if not self.redis_client:
            return
        
        try:
            # Invalidate specific record
            cache_key = self._get_copy_history_key(copy_history_id)
            self.redis_client.delete(cache_key)
            
            # Invalidate active copy list
            active_key = self._get_active_copy_key(migration_id)
            self.redis_client.delete(active_key)
            
            # Invalidate list caches
            list_pattern = f"copy_history:list:{migration_id}:*"
            keys = self.redis_client.keys(list_pattern)
            if keys:
                self.redis_client.delete(*keys)
            
            logger.debug(f"Invalidated cache for copy history {copy_history_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate copy history cache: {e}")
    
    # ==================== Task History Cache Methods ====================
    
    def _get_task_history_key(self, task_history_id: int) -> str:
        """Generate cache key for task history record"""
        return f"task_history:record:{task_history_id}"
    
    def _get_active_task_key(self, migration_id: int) -> str:
        """Generate cache key for active task operations"""
        return f"task_history:active:{migration_id}"
    
    def _get_task_list_key(self, migration_id: int, status: Optional[str] = None) -> str:
        """Generate cache key for task history list"""
        status_suffix = f":{status}" if status else ":all"
        return f"task_history:list:{migration_id}{status_suffix}"
    
    def _serialize_task_history(self, task_history) -> str:
        """Serialize task history object to JSON"""
        return json.dumps({
            'id': task_history.id,
            'migration_id': task_history.migration_id,
            'task_name': task_history.task_name,
            'task_arn': task_history.task_arn,
            'agent_arn': task_history.agent_arn,
            'agent_ip': task_history.agent_ip,
            'source_uri': task_history.source_uri,
            'dest_uri': task_history.dest_uri,
            'status': task_history.status,
            'files_transferred': task_history.files_transferred,
            'bytes_transferred': task_history.bytes_transferred,
            'duration_seconds': task_history.duration_seconds,
            'error_details': task_history.error_details,
            'raw_result': task_history.raw_result,
            'started_at': task_history.started_at.isoformat() if task_history.started_at else None,
            'completed_at': task_history.completed_at.isoformat() if task_history.completed_at else None
        })
    
    def get_task_history(self, task_history_id: int, workspace_id: int) -> Optional[Dict[str, Any]]:
        """Get task history record with cache-aside pattern"""
        cache_key = self._get_task_history_key(task_history_id)
        
        # Try Redis first
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    logger.debug(f"Cache hit for task history {task_history_id}")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Redis get failed for task history {task_history_id}: {e}, falling back to database")
        
        # Cache miss or Redis unavailable - fetch from database
        logger.debug(f"Cache miss for task history {task_history_id}, fetching from database")
        task_history = self.history_repository.get_task_history_by_id(task_history_id, workspace_id)
        
        if not task_history:
            return None
        
        # Serialize
        task_data = self._serialize_task_history(task_history)
        
        # Try to cache for next time (best effort)
        if self.redis_client:
            try:
                ttl = self.TTL_ACTIVE_TASK if task_history.status == 'running' else self.TTL_TASK_LIST
                self.redis_client.setex(cache_key, ttl, task_data)
                logger.debug(f"Cached task history {task_history_id} with TTL {ttl}s")
            except Exception as e:
                logger.warning(f"Failed to cache task history {task_history_id}: {e}")
        
        return json.loads(task_data)
    
    def invalidate_task_history(self, task_history_id: int, migration_id: int):
        """Invalidate task history cache"""
        if not self.redis_client:
            return
        
        try:
            # Invalidate specific record
            cache_key = self._get_task_history_key(task_history_id)
            self.redis_client.delete(cache_key)
            
            # Invalidate active task list
            active_key = self._get_active_task_key(migration_id)
            self.redis_client.delete(active_key)
            
            # Invalidate list caches
            list_pattern = f"task_history:list:{migration_id}:*"
            keys = self.redis_client.keys(list_pattern)
            if keys:
                self.redis_client.delete(*keys)
            
            logger.debug(f"Invalidated cache for task history {task_history_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate task history cache: {e}")
    
    # ==================== DataSync Agent Cache Methods ====================
    
    def _get_agent_key(self, agent_id: int, workspace_id: int) -> str:
        """Generate cache key for DataSync agent"""
        return f"datasync_agent:{workspace_id}:{agent_id}"
    
    def _get_agent_by_vm_key(self, vm_ip: str, workspace_id: int) -> str:
        """Generate cache key for agent lookup by VM IP"""
        return f"datasync_agent:vm:{workspace_id}:{vm_ip}"
    
    def _get_agents_list_key(self, workspace_id: int, status: Optional[str] = None) -> str:
        """Generate cache key for agents list"""
        status_suffix = f":{status}" if status else ":all"
        return f"datasync_agent:list:{workspace_id}{status_suffix}"
    
    def _serialize_agent(self, agent) -> str:
        """Serialize DataSync agent object to JSON"""
        return json.dumps({
            'id': agent.id,
            'workspace_id': agent.workspace_id,
            'vm_ip': agent.vm_ip,
            'agent_arn': agent.agent_arn,
            'aws_region': agent.aws_region,
            'status': agent.status,
            'created_at': agent.created_at.isoformat() if agent.created_at else None,
            'last_used_at': agent.last_used_at.isoformat() if agent.last_used_at else None
        })
    
    def get_agent(self, agent_id: int, workspace_id: int) -> Optional[Dict[str, Any]]:
        """Get DataSync agent with cache-aside pattern"""
        cache_key = self._get_agent_key(agent_id, workspace_id)
        
        # Try Redis first
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    logger.debug(f"Cache hit for agent {agent_id}")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Redis get failed for agent {agent_id}: {e}, falling back to database")
        
        # Cache miss or Redis unavailable - fetch from database
        logger.debug(f"Cache miss for agent {agent_id}, fetching from database")
        agent = self.agent_repository.get_agent_by_id(agent_id, workspace_id)
        
        if not agent:
            return None
        
        # Serialize
        agent_data = self._serialize_agent(agent)
        
        # Try to cache for next time (best effort)
        if self.redis_client:
            try:
                self.redis_client.setex(cache_key, self.TTL_AGENT, agent_data)
                logger.debug(f"Cached agent {agent_id} with TTL {self.TTL_AGENT}s")
            except Exception as e:
                logger.warning(f"Failed to cache agent {agent_id}: {e}")
        
        return json.loads(agent_data)
    
    def get_agent_by_vm_ip(self, vm_ip: str, workspace_id: int) -> Optional[Dict[str, Any]]:
        """Get DataSync agent by VM IP with cache-aside pattern"""
        cache_key = self._get_agent_by_vm_key(vm_ip, workspace_id)
        
        # Try Redis first
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    logger.debug(f"Cache hit for agent with VM IP {vm_ip}")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Redis get failed for agent VM IP {vm_ip}: {e}, falling back to database")
        
        # Cache miss or Redis unavailable - fetch from database
        logger.debug(f"Cache miss for agent VM IP {vm_ip}, fetching from database")
        agent = self.agent_repository.get_agent_by_vm_ip(vm_ip, workspace_id)
        
        if not agent:
            return None
        
        # Serialize
        agent_data = self._serialize_agent(agent)
        
        # Try to cache for next time (best effort)
        if self.redis_client:
            try:
                self.redis_client.setex(cache_key, self.TTL_AGENT, agent_data)
                logger.debug(f"Cached agent VM IP {vm_ip} with TTL {self.TTL_AGENT}s")
            except Exception as e:
                logger.warning(f"Failed to cache agent VM IP {vm_ip}: {e}")
        
        return json.loads(agent_data)
    
    def invalidate_agent(self, agent_id: int, workspace_id: int, vm_ip: Optional[str] = None):
        """Invalidate agent cache"""
        if not self.redis_client:
            return
        
        try:
            # Invalidate by ID
            cache_key = self._get_agent_key(agent_id, workspace_id)
            self.redis_client.delete(cache_key)
            
            # Invalidate by VM IP if provided
            if vm_ip:
                vm_key = self._get_agent_by_vm_key(vm_ip, workspace_id)
                self.redis_client.delete(vm_key)
            
            # Invalidate list caches
            list_pattern = f"datasync_agent:list:{workspace_id}:*"
            keys = self.redis_client.keys(list_pattern)
            if keys:
                self.redis_client.delete(*keys)
            
            logger.debug(f"Invalidated cache for agent {agent_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate agent cache: {e}")
    
    def bulk_invalidate_agents(self, workspace_id: int):
        """Invalidate all agent caches for a workspace"""
        if not self.redis_client:
            return
        
        try:
            # Invalidate all agent-related keys for workspace
            pattern = f"datasync_agent:*:{workspace_id}:*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            
            logger.debug(f"Bulk invalidated agent caches for workspace {workspace_id}")
        except Exception as e:
            logger.warning(f"Failed to bulk invalidate agent caches: {e}")
