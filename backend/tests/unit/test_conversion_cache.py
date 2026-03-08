"""
Unit tests for ConversionCache
Tests Redis caching for batch status and discovered assets with fallback behavior.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from redis.exceptions import ConnectionError, RedisError

from services.conversion_cache import ConversionCache


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

SAMPLE_BATCH_STATUS = {
    "id": 1,
    "status": "in_progress",
    "total_assets": 10,
    "completed_assets": 4,
    "failed_assets": 1,
}

SAMPLE_DISCOVERED_ASSETS = [
    {"asset_type": "TABLE_DDL", "asset_name": "users", "source_code": "CREATE TABLE users (id INT64)"},
    {"asset_type": "VIEW", "asset_name": "active_users", "source_code": "CREATE VIEW active_users AS SELECT * FROM users"},
    {"asset_type": "STORED_PROCEDURE", "asset_name": "update_user", "source_code": "CREATE PROCEDURE update_user()"},
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    """Provide a MagicMock Redis client."""
    return MagicMock()


@pytest.fixture
def cache_with_redis(mock_redis):
    """ConversionCache with a working mock Redis client."""
    with patch.object(ConversionCache, '_initialize_redis'):
        cache = ConversionCache()
        cache.redis_client = mock_redis
    return cache


@pytest.fixture
def cache_without_redis():
    """ConversionCache with Redis disabled (simulates Redis unavailable)."""
    with patch.dict('os.environ', {'REDIS_ENABLED': 'false'}):
        cache = ConversionCache()
    return cache


# ---------------------------------------------------------------------------
# Batch Status Tests
# ---------------------------------------------------------------------------

class TestBatchStatusCache:
    """Tests for batch status caching operations"""

    def test_set_batch_status_calls_setex_with_correct_ttl(self, cache_with_redis, mock_redis):
        """Test that set_batch_status stores data with 120s TTL"""
        cache_with_redis.set_batch_status(1, SAMPLE_BATCH_STATUS)

        mock_redis.setex.assert_called_once_with(
            "conversion:batch:1:status",
            120,
            json.dumps(SAMPLE_BATCH_STATUS),
        )

    def test_get_batch_status_returns_cached_data(self, cache_with_redis, mock_redis):
        """Test that get_batch_status returns deserialized dict on cache hit"""
        mock_redis.get.return_value = json.dumps(SAMPLE_BATCH_STATUS)

        result = cache_with_redis.get_batch_status(1)

        mock_redis.get.assert_called_once_with("conversion:batch:1:status")
        assert result == SAMPLE_BATCH_STATUS

    def test_get_batch_status_returns_none_on_cache_miss(self, cache_with_redis, mock_redis):
        """Test that get_batch_status returns None when key does not exist"""
        mock_redis.get.return_value = None

        result = cache_with_redis.get_batch_status(1)

        assert result is None

    def test_invalidate_batch_status_deletes_key(self, cache_with_redis, mock_redis):
        """Test that invalidate_batch_status deletes the correct key"""
        cache_with_redis.invalidate_batch_status(1)

        mock_redis.delete.assert_called_once_with("conversion:batch:1:status")

    def test_set_batch_status_uses_correct_key_pattern(self, cache_with_redis, mock_redis):
        """Test key pattern conversion:batch:{batch_id}:status"""
        cache_with_redis.set_batch_status(42, {"status": "completed"})

        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "conversion:batch:42:status"


# ---------------------------------------------------------------------------
# Discovered Assets Tests
# ---------------------------------------------------------------------------

class TestDiscoveredAssetsCache:
    """Tests for discovered assets caching operations"""

    def test_set_discovered_assets_calls_setex_with_correct_ttl(self, cache_with_redis, mock_redis):
        """Test that set_discovered_assets stores data with 900s TTL"""
        cache_with_redis.set_discovered_assets(5, SAMPLE_DISCOVERED_ASSETS)

        mock_redis.setex.assert_called_once_with(
            "conversion:assets:5",
            900,
            json.dumps(SAMPLE_DISCOVERED_ASSETS),
        )

    def test_get_discovered_assets_returns_cached_data(self, cache_with_redis, mock_redis):
        """Test that get_discovered_assets returns deserialized list on cache hit"""
        mock_redis.get.return_value = json.dumps(SAMPLE_DISCOVERED_ASSETS)

        result = cache_with_redis.get_discovered_assets(5)

        mock_redis.get.assert_called_once_with("conversion:assets:5")
        assert result == SAMPLE_DISCOVERED_ASSETS

    def test_get_discovered_assets_returns_none_on_cache_miss(self, cache_with_redis, mock_redis):
        """Test that get_discovered_assets returns None when key does not exist"""
        mock_redis.get.return_value = None

        result = cache_with_redis.get_discovered_assets(5)

        assert result is None

    def test_invalidate_discovered_assets_deletes_key(self, cache_with_redis, mock_redis):
        """Test that invalidate_discovered_assets deletes the correct key"""
        cache_with_redis.invalidate_discovered_assets(5)

        mock_redis.delete.assert_called_once_with("conversion:assets:5")

    def test_set_discovered_assets_uses_correct_key_pattern(self, cache_with_redis, mock_redis):
        """Test key pattern conversion:assets:{project_id}"""
        cache_with_redis.set_discovered_assets(99, [])

        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "conversion:assets:99"


# ---------------------------------------------------------------------------
# Redis Fallback Tests
# ---------------------------------------------------------------------------

class TestRedisFallback:
    """Tests verifying PostgreSQL fallback when Redis is unavailable"""

    def test_get_batch_status_returns_none_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, get_batch_status returns None (DB fallback)"""
        result = cache_without_redis.get_batch_status(1)
        assert result is None

    def test_set_batch_status_noop_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, set_batch_status does nothing (no error)"""
        cache_without_redis.set_batch_status(1, SAMPLE_BATCH_STATUS)
        # Should not raise

    def test_invalidate_batch_status_noop_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, invalidate_batch_status does nothing"""
        cache_without_redis.invalidate_batch_status(1)

    def test_get_discovered_assets_returns_none_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, get_discovered_assets returns None (DB fallback)"""
        result = cache_without_redis.get_discovered_assets(5)
        assert result is None

    def test_set_discovered_assets_noop_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, set_discovered_assets does nothing"""
        cache_without_redis.set_discovered_assets(5, SAMPLE_DISCOVERED_ASSETS)

    def test_invalidate_discovered_assets_noop_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, invalidate_discovered_assets does nothing"""
        cache_without_redis.invalidate_discovered_assets(5)

    def test_get_batch_status_returns_none_on_connection_error(self, cache_with_redis, mock_redis):
        """When Redis raises ConnectionError, get_batch_status returns None"""
        mock_redis.get.side_effect = ConnectionError("Connection refused")

        result = cache_with_redis.get_batch_status(1)

        assert result is None

    def test_set_batch_status_handles_connection_error(self, cache_with_redis, mock_redis):
        """When Redis raises ConnectionError, set_batch_status does not raise"""
        mock_redis.setex.side_effect = ConnectionError("Connection refused")

        cache_with_redis.set_batch_status(1, SAMPLE_BATCH_STATUS)
        # Should not raise

    def test_invalidate_batch_status_handles_connection_error(self, cache_with_redis, mock_redis):
        """When Redis raises ConnectionError, invalidate_batch_status does not raise"""
        mock_redis.delete.side_effect = ConnectionError("Connection refused")

        cache_with_redis.invalidate_batch_status(1)

    def test_get_discovered_assets_returns_none_on_redis_error(self, cache_with_redis, mock_redis):
        """When Redis raises RedisError, get_discovered_assets returns None"""
        mock_redis.get.side_effect = RedisError("Redis error")

        result = cache_with_redis.get_discovered_assets(5)

        assert result is None

    def test_set_discovered_assets_handles_redis_error(self, cache_with_redis, mock_redis):
        """When Redis raises RedisError, set_discovered_assets does not raise"""
        mock_redis.setex.side_effect = RedisError("Redis error")

        cache_with_redis.set_discovered_assets(5, SAMPLE_DISCOVERED_ASSETS)

    def test_invalidate_discovered_assets_handles_redis_error(self, cache_with_redis, mock_redis):
        """When Redis raises RedisError, invalidate_discovered_assets does not raise"""
        mock_redis.delete.side_effect = RedisError("Redis error")

        cache_with_redis.invalidate_discovered_assets(5)


# ---------------------------------------------------------------------------
# Health Check Tests
# ---------------------------------------------------------------------------

class TestHealthCheck:
    """Tests for the health_check method"""

    def test_health_check_returns_true_when_redis_healthy(self, cache_with_redis, mock_redis):
        """Test health_check returns True when Redis responds to ping"""
        mock_redis.ping.return_value = True

        assert cache_with_redis.health_check() is True

    def test_health_check_returns_false_when_redis_disabled(self, cache_without_redis):
        """Test health_check returns False when Redis is not available"""
        assert cache_without_redis.health_check() is False

    def test_health_check_returns_false_on_redis_error(self, cache_with_redis, mock_redis):
        """Test health_check returns False when Redis ping fails"""
        mock_redis.ping.side_effect = ConnectionError("Connection refused")

        assert cache_with_redis.health_check() is False
