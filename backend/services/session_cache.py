"""
Session Cache Service
Handles Redis operations for session management with database fallback
"""

import os
import json
import logging
from typing import Optional, Dict, Any
import redis
from redis.exceptions import RedisError, ConnectionError

logger = logging.getLogger(__name__)


class SessionCache:
    """Service for session caching with Redis"""
    
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
            
            # Test connection
            self.redis_client.ping()
            logger.info("Redis connection initialized successfully")
            
        except Exception as e:
            logger.warning(f"Failed to initialize Redis: {str(e)}. Will use database fallback.")
            self.redis_client = None
    
    def cache_session(
        self,
        user_id: int,
        token: str,
        session_data: Dict[str, Any],
        ttl: int = 28800  # 8 hours in seconds
    ) -> None:
        """
        Cache user session data in Redis
        
        Args:
            user_id: User ID
            token: JWT token (used as cache key)
            session_data: Session data to cache
            ttl: Time to live in seconds (default: 8 hours)
        """
        if not self.redis_client:
            logger.debug("Redis not available, skipping cache")
            return
        
        try:
            cache_key = f"session:{token}"
            session_json = json.dumps(session_data)
            
            self.redis_client.setex(
                cache_key,
                ttl,
                session_json
            )
            
            logger.debug(f"Session cached for user {user_id}")
            
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to cache session: {str(e)}")
            # Don't raise exception - fallback to database
        except Exception as e:
            logger.error(f"Unexpected error caching session: {str(e)}")
    
    def get_session(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get session data from Redis cache
        
        Args:
            token: JWT token (cache key)
            
        Returns:
            Session data dict if found, None otherwise
        """
        if not self.redis_client:
            logger.debug("Redis not available, returning None")
            return None
        
        try:
            cache_key = f"session:{token}"
            session_json = self.redis_client.get(cache_key)
            
            if session_json:
                session_data = json.loads(session_json)
                logger.debug("Session retrieved from cache")
                return session_data
            
            return None
            
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to get session from cache: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting session: {str(e)}")
            return None
    
    def invalidate_session(self, token: str) -> None:
        """
        Invalidate (delete) session from cache
        
        Args:
            token: JWT token (cache key)
        """
        if not self.redis_client:
            logger.debug("Redis not available, skipping invalidation")
            return
        
        try:
            cache_key = f"session:{token}"
            self.redis_client.delete(cache_key)
            logger.debug("Session invalidated from cache")
            
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to invalidate session: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error invalidating session: {str(e)}")
    
    def is_token_blacklisted(self, token: str) -> bool:
        """
        Check if token is in blacklist
        
        Args:
            token: JWT token to check
            
        Returns:
            True if blacklisted, False otherwise
        """
        if not self.redis_client:
            logger.debug("Redis not available, assuming not blacklisted")
            return False
        
        try:
            blacklist_key = f"blacklist:{token}"
            exists = self.redis_client.exists(blacklist_key)
            return bool(exists)
            
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to check blacklist: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error checking blacklist: {str(e)}")
            return False
    
    def add_to_blacklist(self, token: str, ttl: int = 28800) -> None:
        """
        Add token to blacklist
        
        Args:
            token: JWT token to blacklist
            ttl: Time to live in seconds (should match token expiration)
        """
        if not self.redis_client:
            logger.debug("Redis not available, skipping blacklist")
            return
        
        try:
            blacklist_key = f"blacklist:{token}"
            self.redis_client.setex(
                blacklist_key,
                ttl,
                "1"
            )
            logger.debug("Token added to blacklist")
            
        except (RedisError, ConnectionError) as e:
            logger.warning(f"Failed to add to blacklist: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error adding to blacklist: {str(e)}")
    
    def health_check(self) -> bool:
        """
        Check if Redis is healthy
        
        Returns:
            True if Redis is available and responding, False otherwise
        """
        if not self.redis_client:
            return False
        
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False


# Global session cache instance
session_cache = SessionCache()
