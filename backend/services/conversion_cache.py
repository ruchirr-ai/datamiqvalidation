"""
Conversion Cache Service

Implements cache-aside pattern for conversion jobs and batches with Redis fallback to PostgreSQL
"""

import json
import gzip
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from shared.redis_client import get_redis_client
from repositories.conversion_repository import ConversionRepository

logger = logging.getLogger(__name__)


class ConversionCache:
    """Cache service for conversion operations with database fallback"""
    
    # TTL values in seconds
    TTL_JOB = 3600  # 1 hour for completed jobs
    TTL_ACTIVE_JOB = 60  # 1 minute for active jobs
    TTL_BATCH = 3600  # 1 hour for batches
    
    # Compression threshold (compress if value > 1KB)
    COMPRESSION_THRESHOLD = 1024
    
    def __init__(self, repository: ConversionRepository):
        self.repository = repository
        self.redis_client = get_redis_client()
    
    def _compress_value(self, value: str) -> bytes:
        """Compress large values using gzip"""
        if len(value) > self.COMPRESSION_THRESHOLD:
            return gzip.compress(value.encode('utf-8'))
        return value.encode('utf-8')
    
    def _decompress_value(self, value: bytes) -> str:
        """Decompress gzip-compressed values"""
        try:
            return gzip.decompress(value).decode('utf-8')
        except:
            # Not compressed, return as-is
            return value.decode('utf-8')
    
    def _get_job_key(self, job_id: int, workspace_id: int) -> str:
        """Generate cache key for conversion job"""
        return f"conversion:job:{workspace_id}:{job_id}"
    
    def _get_batch_key(self, batch_id: int, workspace_id: int) -> str:
        """Generate cache key for conversion batch"""
        return f"conversion:batch:{workspace_id}:{batch_id}"
    
    def _get_active_jobs_key(self, workspace_id: int) -> str:
        """Generate cache key for active jobs list"""
        return f"conversion:active_jobs:{workspace_id}"
    
    def _serialize_job(self, job) -> str:
        """Serialize job object to JSON"""
        return json.dumps({
            'id': job.id,
            'workspace_id': job.workspace_id,
            'source_code': job.source_code,
            'source_dialect': job.source_dialect,
            'target_dialect': job.target_dialect,
            'target_code': job.target_code,
            'asset_type': job.asset_type,
            'status': job.status,
            'batch_id': job.batch_id,
            'use_sqlglot': job.use_sqlglot,
            'sqlglot_success': job.sqlglot_success,
            'bedrock_model': job.bedrock_model,
            'error_message': job.error_message,
            'retry_count': job.retry_count,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None
        })
    
    def _serialize_batch(self, batch) -> str:
        """Serialize batch object to JSON"""
        return json.dumps({
            'id': batch.id,
            'workspace_id': batch.workspace_id,
            'source_connection_id': batch.source_connection_id,
            'target_connection_id': batch.target_connection_id,
            'total_assets': batch.total_assets,
            'completed_assets': batch.completed_assets,
            'failed_assets': batch.failed_assets,
            'status': batch.status,
            'created_at': batch.created_at.isoformat() if batch.created_at else None,
            'completed_at': batch.completed_at.isoformat() if batch.completed_at else None
        })
    
    def get_job(self, job_id: int, workspace_id: int) -> Optional[Dict[str, Any]]:
        """
        Get conversion job with cache-aside pattern
        
        1. Try Redis cache first
        2. On cache miss or Redis unavailable, fetch from database
        3. Cache the result for future requests
        """
        cache_key = self._get_job_key(job_id, workspace_id)
        
        # Try Redis first
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    logger.debug(f"Cache hit for job {job_id}")
                    decompressed = self._decompress_value(cached_data.encode('utf-8') if isinstance(cached_data, str) else cached_data)
                    return json.loads(decompressed)
            except Exception as e:
                logger.warning(f"Redis get failed for job {job_id}: {e}, falling back to database")
        
        # Cache miss or Redis unavailable - fetch from database
        logger.debug(f"Cache miss for job {job_id}, fetching from database")
        job = self.repository.get_job(job_id, workspace_id)
        
        if not job:
            return None
        
        # Serialize job
        job_data = self._serialize_job(job)
        
        # Try to cache for next time (best effort)
        if self.redis_client:
            try:
                compressed = self._compress_value(job_data)
                ttl = self.TTL_ACTIVE_JOB if job.status == 'processing' else self.TTL_JOB
                self.redis_client.setex(cache_key, ttl, compressed)
                logger.debug(f"Cached job {job_id} with TTL {ttl}s")
            except Exception as e:
                logger.warning(f"Failed to cache job {job_id}: {e}")
        
        return json.loads(job_data)
    
    def invalidate_job(self, job_id: int, workspace_id: int):
        """Invalidate job cache (called on status change)"""
        if not self.redis_client:
            return
        
        cache_key = self._get_job_key(job_id, workspace_id)
        try:
            self.redis_client.delete(cache_key)
            logger.debug(f"Invalidated cache for job {job_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for job {job_id}: {e}")
    
    def get_batch(self, batch_id: int, workspace_id: int) -> Optional[Dict[str, Any]]:
        """
        Get conversion batch with cache-aside pattern
        """
        cache_key = self._get_batch_key(batch_id, workspace_id)
        
        # Try Redis first
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    logger.debug(f"Cache hit for batch {batch_id}")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Redis get failed for batch {batch_id}: {e}, falling back to database")
        
        # Cache miss or Redis unavailable - fetch from database
        logger.debug(f"Cache miss for batch {batch_id}, fetching from database")
        batch = self.repository.get_batch(batch_id, workspace_id)
        
        if not batch:
            return None
        
        # Serialize batch
        batch_data = self._serialize_batch(batch)
        
        # Try to cache for next time (best effort)
        if self.redis_client:
            try:
                self.redis_client.setex(cache_key, self.TTL_BATCH, batch_data)
                logger.debug(f"Cached batch {batch_id} with TTL {self.TTL_BATCH}s")
            except Exception as e:
                logger.warning(f"Failed to cache batch {batch_id}: {e}")
        
        return json.loads(batch_data)
    
    def invalidate_batch(self, batch_id: int, workspace_id: int):
        """Invalidate batch cache (called on counter updates)"""
        if not self.redis_client:
            return
        
        cache_key = self._get_batch_key(batch_id, workspace_id)
        try:
            self.redis_client.delete(cache_key)
            logger.debug(f"Invalidated cache for batch {batch_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for batch {batch_id}: {e}")
    
    def get_active_jobs(self, workspace_id: int) -> List[int]:
        """
        Get list of active job IDs for a workspace
        Active = status in ['pending', 'processing']
        """
        cache_key = self._get_active_jobs_key(workspace_id)
        
        # Try Redis first
        if self.redis_client:
            try:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    logger.debug(f"Cache hit for active jobs (workspace {workspace_id})")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Redis get failed for active jobs: {e}, falling back to database")
        
        # Cache miss or Redis unavailable - fetch from database
        logger.debug(f"Cache miss for active jobs, fetching from database")
        active_jobs = self.repository.list_jobs(
            workspace_id=workspace_id,
            status='processing',
            page=1,
            page_size=1000  # Get all active jobs
        )
        
        job_ids = [job.id for job in active_jobs]
        
        # Try to cache for next time (best effort)
        if self.redis_client:
            try:
                self.redis_client.setex(cache_key, self.TTL_ACTIVE_JOB, json.dumps(job_ids))
                logger.debug(f"Cached active jobs list with TTL {self.TTL_ACTIVE_JOB}s")
            except Exception as e:
                logger.warning(f"Failed to cache active jobs: {e}")
        
        return job_ids
    
    def invalidate_active_jobs(self, workspace_id: int):
        """Invalidate active jobs list cache"""
        if not self.redis_client:
            return
        
        cache_key = self._get_active_jobs_key(workspace_id)
        try:
            self.redis_client.delete(cache_key)
            logger.debug(f"Invalidated active jobs cache for workspace {workspace_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate active jobs cache: {e}")
