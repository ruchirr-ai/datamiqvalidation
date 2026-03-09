"""
Redis Client

Centralized Redis connection management with connection pooling
"""

import redis
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis client with connection pooling"""
    
    _instance: Optional[redis.Redis] = None
    _pool: Optional[redis.ConnectionPool] = None
    
    @classmethod
    def get_client(cls) -> Optional[redis.Redis]:
        """Get Redis client instance (singleton pattern)"""
        if cls._instance is None:
            try:
                cls._pool = redis.ConnectionPool(
                    host=os.getenv('REDIS_HOST', 'localhost'),
                    port=int(os.getenv('REDIS_PORT', 6379)),
                    db=int(os.getenv('REDIS_DB', 0)),
                    password=os.getenv('REDIS_PASSWORD'),
                    max_connections=int(os.getenv('REDIS_MAX_CONNECTIONS', 50)),
                    socket_timeout=int(os.getenv('REDIS_SOCKET_TIMEOUT', 5)),
                    socket_connect_timeout=int(os.getenv('REDIS_SOCKET_CONNECT_TIMEOUT', 5)),
                    decode_responses=True
                )
                cls._instance = redis.Redis(connection_pool=cls._pool)
                
                # Test connection
                cls._instance.ping()
                logger.info("Redis connection established successfully")
                
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Application will use database fallback.")
                cls._instance = None
        
        return cls._instance
    
    @classmethod
    def is_available(cls) -> bool:
        """Check if Redis is available"""
        try:
            client = cls.get_client()
            if client:
                client.ping()
                return True
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}")
        return False
    
    @classmethod
    def close(cls):
        """Close Redis connection"""
        if cls._instance:
            cls._instance.close()
            cls._instance = None
        if cls._pool:
            cls._pool.disconnect()
            cls._pool = None


def get_redis_client() -> Optional[redis.Redis]:
    """Get Redis client instance"""
    return RedisClient.get_client()
