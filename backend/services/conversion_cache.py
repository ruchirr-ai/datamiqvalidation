"""
Conversion Cache Service
Handles Redis caching for conversion batch status and discovered assets
with PostgreSQL fallback when Redis is unavailable.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
import redis
from redis.exceptions import RedisError, ConnectionError

logger = logging.getLogger(__name__)


class ConversionCache:
    """Service for caching conversion metadata with Redis and PostgreSQL fallback"""

    # TTL constants
    BATCH_STATUS_TTL = 120    # 2 minutes
    DISCOVERED_ASSETS_TTL = 900  # 15 minutes

    def __init__(self):
        self.redis_client = None
        self.redis_enabled = os.getenv('REDIS_ENABLED', 'true').lower() == 'true'

        if self.redis_enabled:
            self._initialize_redis()

    def _initialize_redis(self):
        """Initialize Redis connection"""
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
            logger.info("Conversion cache Redis connection initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis for conversion cache: {str(e)}. Will use database fallback.")
            self.redis_client = None

    def get_batch_status(self, batch_id: int) -> Optional[Dict[str, Any]]:
        """Get cached batch status from Redis."""
        if not self.redis_client:
            return None
        try:
            cache_key = f"conversion:batch:{batch_id}:status"
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                logger.debug(f"Batch status cache hit for batch_id={batch_id}")
                return json.loads(cached_data)
            return None
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to get batch status from cache: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting batch status from cache: {str(e)}")
            return None

    def set_batch_status(self, batch_id: int, status_dict: Dict[str, Any]) -> None:
        """Cache batch status in Redis with TTL of 2 minutes."""
        if not self.redis_client:
            return
        try:
            cache_key = f"conversion:batch:{batch_id}:status"
            self.redis_client.setex(
                cache_key,
                self.BATCH_STATUS_TTL,
                json.dumps(status_dict)
            )
            logger.debug(f"Batch status cached for batch_id={batch_id}")
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to cache batch status: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error caching batch status: {str(e)}")

    def invalidate_batch_status(self, batch_id: int) -> None:
        """Invalidate (delete) cached batch status from Redis."""
        if not self.redis_client:
            return
        try:
            cache_key = f"conversion:batch:{batch_id}:status"
            self.redis_client.delete(cache_key)
            logger.debug(f"Batch status cache invalidated for batch_id={batch_id}")
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to invalidate batch status cache: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error invalidating batch status cache: {str(e)}")

    def get_discovered_assets(self, project_id: int) -> Optional[List]:
        """Get cached discovered assets list from Redis."""
        if not self.redis_client:
            return None
        try:
            cache_key = f"conversion:assets:{project_id}"
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                logger.debug(f"Discovered assets cache hit for project_id={project_id}")
                return json.loads(cached_data)
            return None
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to get discovered assets from cache: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting discovered assets from cache: {str(e)}")
            return None

    def set_discovered_assets(self, project_id: int, assets: List) -> None:
        """Cache discovered assets list in Redis with TTL of 15 minutes."""
        if not self.redis_client:
            return
        try:
            cache_key = f"conversion:assets:{project_id}"
            self.redis_client.setex(
                cache_key,
                self.DISCOVERED_ASSETS_TTL,
                json.dumps(assets)
            )
            logger.debug(f"Discovered assets cached for project_id={project_id}")
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to cache discovered assets: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error caching discovered assets: {str(e)}")

    def invalidate_discovered_assets(self, project_id: int) -> None:
        """Invalidate (delete) cached discovered assets from Redis."""
        if not self.redis_client:
            return
        try:
            cache_key = f"conversion:assets:{project_id}"
            self.redis_client.delete(cache_key)
            logger.debug(f"Discovered assets cache invalidated for project_id={project_id}")
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to invalidate discovered assets cache: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error invalidating discovered assets cache: {str(e)}")

    def health_check(self) -> bool:
        """Check if Redis is healthy."""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False


# Global conversion cache instance
conversion_cache = ConversionCache()
