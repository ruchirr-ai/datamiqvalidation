"""
Validation Cache Service
Handles Redis caching for validation run data, table results, and reports
with PostgreSQL fallback when Redis is unavailable.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import redis
from redis.exceptions import RedisError, ConnectionError

logger = logging.getLogger(__name__)


def _serialize(data: Any) -> str:
    """Serialize data to JSON, converting datetime fields to ISO 8601 strings."""

    def _default(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    return json.dumps(data, default=_default)


class ValidationCache:
    """Service for caching validation data with Redis and PostgreSQL fallback."""

    # TTL constants (seconds)
    RUN_TTL = 900            # 15 minutes
    TABLE_RESULT_TTL = 900   # 15 minutes
    REPORT_TTL = 1800        # 30 minutes

    def __init__(self):
        self.redis_client = None
        self.redis_enabled = os.getenv('REDIS_ENABLED', 'true').lower() == 'true'

        if self.redis_enabled:
            self._initialize_redis()

    def _initialize_redis(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', '6379')),
                db=int(os.getenv('REDIS_DB', '0')),
                password=os.getenv('REDIS_PASSWORD'),
                socket_timeout=int(os.getenv('REDIS_SOCKET_TIMEOUT', '5')),
                socket_connect_timeout=int(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', '5')),
                max_connections=int(os.getenv('REDIS_MAX_CONNECTIONS', '50')),
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("Validation cache Redis connection initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis for validation cache: {str(e)}. Will use database fallback.")
            self.redis_client = None

    # ------------------------------------------------------------------
    # Validation Run cache
    # ------------------------------------------------------------------

    def get_run(self, run_id: int, workspace_id: int) -> Optional[Dict[str, Any]]:
        """Get cached validation run from Redis."""
        if not self.redis_client:
            return None
        try:
            cache_key = f"validation:run:{workspace_id}:{run_id}"
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                logger.debug(f"Validation run cache hit for run_id={run_id}, workspace_id={workspace_id}")
                return json.loads(cached_data)
            logger.debug(f"Validation run cache miss for run_id={run_id}, workspace_id={workspace_id}")
            return None
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to get validation run from cache: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting validation run from cache: {str(e)}")
            return None

    def set_run(self, run_id: int, workspace_id: int, data: Dict[str, Any]) -> None:
        """Cache validation run in Redis with TTL of 15 minutes."""
        if not self.redis_client:
            return
        try:
            cache_key = f"validation:run:{workspace_id}:{run_id}"
            self.redis_client.setex(cache_key, self.RUN_TTL, _serialize(data))
            logger.debug(f"Validation run cached for run_id={run_id}, workspace_id={workspace_id}")
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to cache validation run: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error caching validation run: {str(e)}")

    def invalidate_run(self, run_id: int, workspace_id: int) -> None:
        """Invalidate cached validation run from Redis."""
        if not self.redis_client:
            return
        try:
            cache_key = f"validation:run:{workspace_id}:{run_id}"
            self.redis_client.delete(cache_key)
            logger.debug(f"Validation run cache invalidated for run_id={run_id}, workspace_id={workspace_id}")
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to invalidate validation run cache: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error invalidating validation run cache: {str(e)}")

    # ------------------------------------------------------------------
    # Validation Table Result cache
    # ------------------------------------------------------------------

    def get_table_result(self, run_id: int, table_name: str, workspace_id: int) -> Optional[Dict[str, Any]]:
        """Get cached validation table result from Redis."""
        if not self.redis_client:
            return None
        try:
            cache_key = f"validation:table:{workspace_id}:{run_id}:{table_name}"
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                logger.debug(f"Validation table result cache hit for run_id={run_id}, table={table_name}, workspace_id={workspace_id}")
                return json.loads(cached_data)
            logger.debug(f"Validation table result cache miss for run_id={run_id}, table={table_name}, workspace_id={workspace_id}")
            return None
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to get validation table result from cache: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting validation table result from cache: {str(e)}")
            return None

    def set_table_result(self, run_id: int, table_name: str, workspace_id: int, data: Dict[str, Any]) -> None:
        """Cache validation table result in Redis with TTL of 15 minutes."""
        if not self.redis_client:
            return
        try:
            cache_key = f"validation:table:{workspace_id}:{run_id}:{table_name}"
            self.redis_client.setex(cache_key, self.TABLE_RESULT_TTL, _serialize(data))
            logger.debug(f"Validation table result cached for run_id={run_id}, table={table_name}, workspace_id={workspace_id}")
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to cache validation table result: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error caching validation table result: {str(e)}")

    def invalidate_table_result(self, run_id: int, table_name: str, workspace_id: int) -> None:
        """Invalidate cached validation table result from Redis."""
        if not self.redis_client:
            return
        try:
            cache_key = f"validation:table:{workspace_id}:{run_id}:{table_name}"
            self.redis_client.delete(cache_key)
            logger.debug(f"Validation table result cache invalidated for run_id={run_id}, table={table_name}, workspace_id={workspace_id}")
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to invalidate validation table result cache: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error invalidating validation table result cache: {str(e)}")

    # ------------------------------------------------------------------
    # Validation Report cache
    # ------------------------------------------------------------------

    def get_report(self, run_id: int, workspace_id: int) -> Optional[Dict[str, Any]]:
        """Get cached validation report from Redis."""
        if not self.redis_client:
            return None
        try:
            cache_key = f"validation:report:{workspace_id}:{run_id}"
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                logger.debug(f"Validation report cache hit for run_id={run_id}, workspace_id={workspace_id}")
                return json.loads(cached_data)
            logger.debug(f"Validation report cache miss for run_id={run_id}, workspace_id={workspace_id}")
            return None
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to get validation report from cache: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting validation report from cache: {str(e)}")
            return None

    def set_report(self, run_id: int, workspace_id: int, data: Dict[str, Any]) -> None:
        """Cache validation report in Redis with TTL of 30 minutes."""
        if not self.redis_client:
            return
        try:
            cache_key = f"validation:report:{workspace_id}:{run_id}"
            self.redis_client.setex(cache_key, self.REPORT_TTL, _serialize(data))
            logger.debug(f"Validation report cached for run_id={run_id}, workspace_id={workspace_id}")
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to cache validation report: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error caching validation report: {str(e)}")

    def invalidate_report(self, run_id: int, workspace_id: int) -> None:
        """Invalidate cached validation report from Redis."""
        if not self.redis_client:
            return
        try:
            cache_key = f"validation:report:{workspace_id}:{run_id}"
            self.redis_client.delete(cache_key)
            logger.debug(f"Validation report cache invalidated for run_id={run_id}, workspace_id={workspace_id}")
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to invalidate validation report cache: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error invalidating validation report cache: {str(e)}")

    # ------------------------------------------------------------------
    # Bulk invalidation
    # ------------------------------------------------------------------

    def invalidate_all_for_run(self, run_id: int, workspace_id: int) -> None:
        """Invalidate all cached keys for a validation run (run, tables, report)."""
        if not self.redis_client:
            return
        try:
            # Invalidate the run itself
            self.redis_client.delete(f"validation:run:{workspace_id}:{run_id}")

            # Invalidate all table results using pattern scan
            pattern = f"validation:table:{workspace_id}:{run_id}:*"
            cursor = 0
            while True:
                cursor, keys = self.redis_client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    self.redis_client.delete(*keys)
                if cursor == 0:
                    break

            # Invalidate the report
            self.redis_client.delete(f"validation:report:{workspace_id}:{run_id}")

            logger.debug(f"All validation cache invalidated for run_id={run_id}, workspace_id={workspace_id}")
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to invalidate all validation cache for run: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error invalidating all validation cache for run: {str(e)}")

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """Check if Redis is healthy."""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False


# Global validation cache instance
validation_cache = ValidationCache()
