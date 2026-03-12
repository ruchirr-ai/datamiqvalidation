"""
Unit tests for ValidationCache
Tests Redis caching for validation runs, table results, and reports
with fallback behavior when Redis is unavailable.

Validates: Requirements 11.1–11.10, 16.7
"""

import json
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, call
from redis.exceptions import ConnectionError, RedisError

from services.validation_cache import ValidationCache, _serialize


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

SAMPLE_RUN_DATA = {
    "id": 1,
    "workspace_id": 10,
    "migration_id": 100,
    "status": "running",
    "progress_percentage": 50,
    "tables_total": 4,
    "tables_passed": 2,
    "tables_failed": 0,
    "tables_error": 0,
    "created_at": "2026-01-25T10:00:00",
    "updated_at": "2026-01-25T10:05:00",
}

SAMPLE_TABLE_RESULT_DATA = {
    "id": 5,
    "run_id": 1,
    "table_name": "users",
    "ddl_status": "passed",
    "row_count_status": "passed",
    "data_match_status": "passed",
    "status": "completed",
}

SAMPLE_REPORT_DATA = {
    "run_id": 1,
    "migration_id": 100,
    "overall_status": "passed",
    "total_tables": 4,
    "tables_passed": 4,
    "tables_failed": 0,
    "tables_error": 0,
    "tables": [],
}

WORKSPACE_ID = 10
RUN_ID = 1
TABLE_NAME = "users"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    """Provide a MagicMock Redis client."""
    return MagicMock()


@pytest.fixture
def cache_with_redis(mock_redis):
    """ValidationCache with a working mock Redis client."""
    with patch.object(ValidationCache, '_initialize_redis'):
        cache = ValidationCache()
        cache.redis_client = mock_redis
    return cache


@pytest.fixture
def cache_without_redis():
    """ValidationCache with Redis disabled (simulates Redis unavailable)."""
    with patch.dict('os.environ', {'REDIS_ENABLED': 'false'}):
        cache = ValidationCache()
    return cache


# ---------------------------------------------------------------------------
# Serialization Tests
# ---------------------------------------------------------------------------

class TestSerialization:
    """Tests for the _serialize helper function"""

    def test_serialize_converts_datetime_to_iso_string(self):
        """Test that datetime fields are converted to ISO 8601 strings"""
        data = {"created_at": datetime(2026, 1, 25, 10, 0, 0), "name": "test"}
        result = json.loads(_serialize(data))
        assert result["created_at"] == "2026-01-25T10:00:00"
        assert result["name"] == "test"

    def test_serialize_handles_plain_dict(self):
        """Test that plain dicts serialize correctly"""
        data = {"key": "value", "count": 42}
        result = json.loads(_serialize(data))
        assert result == data

    def test_serialize_raises_for_unsupported_type(self):
        """Test that unsupported types raise TypeError"""
        with pytest.raises(TypeError):
            _serialize({"bad": set([1, 2, 3])})


# ---------------------------------------------------------------------------
# Validation Run Cache Tests
# ---------------------------------------------------------------------------

class TestRunCache:
    """Tests for validation run caching operations"""

    def test_set_run_calls_setex_with_correct_ttl(self, cache_with_redis, mock_redis):
        """Test that set_run stores data with 900s (15 min) TTL"""
        cache_with_redis.set_run(RUN_ID, WORKSPACE_ID, SAMPLE_RUN_DATA)

        mock_redis.setex.assert_called_once_with(
            f"validation:run:{WORKSPACE_ID}:{RUN_ID}",
            900,
            _serialize(SAMPLE_RUN_DATA),
        )

    def test_get_run_returns_cached_data(self, cache_with_redis, mock_redis):
        """Test that get_run returns deserialized dict on cache hit"""
        mock_redis.get.return_value = json.dumps(SAMPLE_RUN_DATA)

        result = cache_with_redis.get_run(RUN_ID, WORKSPACE_ID)

        mock_redis.get.assert_called_once_with(f"validation:run:{WORKSPACE_ID}:{RUN_ID}")
        assert result == SAMPLE_RUN_DATA

    def test_get_run_returns_none_on_cache_miss(self, cache_with_redis, mock_redis):
        """Test that get_run returns None when key does not exist"""
        mock_redis.get.return_value = None

        result = cache_with_redis.get_run(RUN_ID, WORKSPACE_ID)

        assert result is None

    def test_invalidate_run_deletes_key(self, cache_with_redis, mock_redis):
        """Test that invalidate_run deletes the correct key"""
        cache_with_redis.invalidate_run(RUN_ID, WORKSPACE_ID)

        mock_redis.delete.assert_called_once_with(f"validation:run:{WORKSPACE_ID}:{RUN_ID}")

    def test_set_run_uses_workspace_in_key(self, cache_with_redis, mock_redis):
        """Test key pattern includes workspace_id for tenant isolation"""
        cache_with_redis.set_run(5, 20, {"status": "pending"})

        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "validation:run:20:5"


# ---------------------------------------------------------------------------
# Validation Table Result Cache Tests
# ---------------------------------------------------------------------------

class TestTableResultCache:
    """Tests for validation table result caching operations"""

    def test_set_table_result_calls_setex_with_correct_ttl(self, cache_with_redis, mock_redis):
        """Test that set_table_result stores data with 900s (15 min) TTL"""
        cache_with_redis.set_table_result(RUN_ID, TABLE_NAME, WORKSPACE_ID, SAMPLE_TABLE_RESULT_DATA)

        mock_redis.setex.assert_called_once_with(
            f"validation:table:{WORKSPACE_ID}:{RUN_ID}:{TABLE_NAME}",
            900,
            _serialize(SAMPLE_TABLE_RESULT_DATA),
        )

    def test_get_table_result_returns_cached_data(self, cache_with_redis, mock_redis):
        """Test that get_table_result returns deserialized dict on cache hit"""
        mock_redis.get.return_value = json.dumps(SAMPLE_TABLE_RESULT_DATA)

        result = cache_with_redis.get_table_result(RUN_ID, TABLE_NAME, WORKSPACE_ID)

        mock_redis.get.assert_called_once_with(f"validation:table:{WORKSPACE_ID}:{RUN_ID}:{TABLE_NAME}")
        assert result == SAMPLE_TABLE_RESULT_DATA

    def test_get_table_result_returns_none_on_cache_miss(self, cache_with_redis, mock_redis):
        """Test that get_table_result returns None when key does not exist"""
        mock_redis.get.return_value = None

        result = cache_with_redis.get_table_result(RUN_ID, TABLE_NAME, WORKSPACE_ID)

        assert result is None

    def test_invalidate_table_result_deletes_key(self, cache_with_redis, mock_redis):
        """Test that invalidate_table_result deletes the correct key"""
        cache_with_redis.invalidate_table_result(RUN_ID, TABLE_NAME, WORKSPACE_ID)

        mock_redis.delete.assert_called_once_with(f"validation:table:{WORKSPACE_ID}:{RUN_ID}:{TABLE_NAME}")

    def test_set_table_result_uses_workspace_in_key(self, cache_with_redis, mock_redis):
        """Test key pattern includes workspace_id for tenant isolation"""
        cache_with_redis.set_table_result(3, "orders", 25, {"status": "passed"})

        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "validation:table:25:3:orders"


# ---------------------------------------------------------------------------
# Validation Report Cache Tests
# ---------------------------------------------------------------------------

class TestReportCache:
    """Tests for validation report caching operations"""

    def test_set_report_calls_setex_with_correct_ttl(self, cache_with_redis, mock_redis):
        """Test that set_report stores data with 1800s (30 min) TTL"""
        cache_with_redis.set_report(RUN_ID, WORKSPACE_ID, SAMPLE_REPORT_DATA)

        mock_redis.setex.assert_called_once_with(
            f"validation:report:{WORKSPACE_ID}:{RUN_ID}",
            1800,
            _serialize(SAMPLE_REPORT_DATA),
        )

    def test_get_report_returns_cached_data(self, cache_with_redis, mock_redis):
        """Test that get_report returns deserialized dict on cache hit"""
        mock_redis.get.return_value = json.dumps(SAMPLE_REPORT_DATA)

        result = cache_with_redis.get_report(RUN_ID, WORKSPACE_ID)

        mock_redis.get.assert_called_once_with(f"validation:report:{WORKSPACE_ID}:{RUN_ID}")
        assert result == SAMPLE_REPORT_DATA

    def test_get_report_returns_none_on_cache_miss(self, cache_with_redis, mock_redis):
        """Test that get_report returns None when key does not exist"""
        mock_redis.get.return_value = None

        result = cache_with_redis.get_report(RUN_ID, WORKSPACE_ID)

        assert result is None

    def test_invalidate_report_deletes_key(self, cache_with_redis, mock_redis):
        """Test that invalidate_report deletes the correct key"""
        cache_with_redis.invalidate_report(RUN_ID, WORKSPACE_ID)

        mock_redis.delete.assert_called_once_with(f"validation:report:{WORKSPACE_ID}:{RUN_ID}")

    def test_set_report_uses_workspace_in_key(self, cache_with_redis, mock_redis):
        """Test key pattern includes workspace_id for tenant isolation"""
        cache_with_redis.set_report(7, 30, {"overall_status": "failed"})

        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "validation:report:30:7"


# ---------------------------------------------------------------------------
# TTL Value Tests
# ---------------------------------------------------------------------------

class TestTTLValues:
    """Tests verifying correct TTL constants are applied"""

    def test_run_ttl_is_15_minutes(self):
        """Verify RUN_TTL is 900 seconds (15 minutes)"""
        assert ValidationCache.RUN_TTL == 900

    def test_table_result_ttl_is_15_minutes(self):
        """Verify TABLE_RESULT_TTL is 900 seconds (15 minutes)"""
        assert ValidationCache.TABLE_RESULT_TTL == 900

    def test_report_ttl_is_30_minutes(self):
        """Verify REPORT_TTL is 1800 seconds (30 minutes)"""
        assert ValidationCache.REPORT_TTL == 1800


# ---------------------------------------------------------------------------
# Invalidate All For Run Tests
# ---------------------------------------------------------------------------

class TestInvalidateAllForRun:
    """Tests for invalidate_all_for_run bulk invalidation"""

    def test_invalidate_all_for_run_clears_run_key(self, cache_with_redis, mock_redis):
        """Test that invalidate_all_for_run deletes the run cache key"""
        mock_redis.scan.return_value = (0, [])

        cache_with_redis.invalidate_all_for_run(RUN_ID, WORKSPACE_ID)

        # First delete call is for the run key
        delete_calls = mock_redis.delete.call_args_list
        assert call(f"validation:run:{WORKSPACE_ID}:{RUN_ID}") in delete_calls

    def test_invalidate_all_for_run_clears_report_key(self, cache_with_redis, mock_redis):
        """Test that invalidate_all_for_run deletes the report cache key"""
        mock_redis.scan.return_value = (0, [])

        cache_with_redis.invalidate_all_for_run(RUN_ID, WORKSPACE_ID)

        delete_calls = mock_redis.delete.call_args_list
        assert call(f"validation:report:{WORKSPACE_ID}:{RUN_ID}") in delete_calls

    def test_invalidate_all_for_run_scans_and_deletes_table_keys(self, cache_with_redis, mock_redis):
        """Test that invalidate_all_for_run scans for table keys and deletes them"""
        table_keys = [
            f"validation:table:{WORKSPACE_ID}:{RUN_ID}:users",
            f"validation:table:{WORKSPACE_ID}:{RUN_ID}:orders",
        ]
        mock_redis.scan.return_value = (0, table_keys)

        cache_with_redis.invalidate_all_for_run(RUN_ID, WORKSPACE_ID)

        mock_redis.scan.assert_called_with(
            cursor=0,
            match=f"validation:table:{WORKSPACE_ID}:{RUN_ID}:*",
            count=100,
        )
        # Table keys should be deleted in a single call
        mock_redis.delete.assert_any_call(*table_keys)

    def test_invalidate_all_for_run_handles_multiple_scan_pages(self, cache_with_redis, mock_redis):
        """Test that invalidate_all_for_run iterates through scan cursor pages"""
        page1_keys = [f"validation:table:{WORKSPACE_ID}:{RUN_ID}:t1"]
        page2_keys = [f"validation:table:{WORKSPACE_ID}:{RUN_ID}:t2"]
        mock_redis.scan.side_effect = [
            (42, page1_keys),   # first page, cursor=42 means more pages
            (0, page2_keys),    # second page, cursor=0 means done
        ]

        cache_with_redis.invalidate_all_for_run(RUN_ID, WORKSPACE_ID)

        assert mock_redis.scan.call_count == 2
        mock_redis.delete.assert_any_call(*page1_keys)
        mock_redis.delete.assert_any_call(*page2_keys)

    def test_invalidate_all_for_run_noop_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, invalidate_all_for_run does nothing"""
        cache_without_redis.invalidate_all_for_run(RUN_ID, WORKSPACE_ID)
        # Should not raise


# ---------------------------------------------------------------------------
# Redis Fallback Tests
# ---------------------------------------------------------------------------

class TestRedisFallback:
    """Tests verifying PostgreSQL fallback when Redis is unavailable"""

    # -- Redis disabled --

    def test_get_run_returns_none_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, get_run returns None (DB fallback)"""
        assert cache_without_redis.get_run(RUN_ID, WORKSPACE_ID) is None

    def test_set_run_noop_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, set_run does nothing (no error)"""
        cache_without_redis.set_run(RUN_ID, WORKSPACE_ID, SAMPLE_RUN_DATA)

    def test_invalidate_run_noop_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, invalidate_run does nothing"""
        cache_without_redis.invalidate_run(RUN_ID, WORKSPACE_ID)

    def test_get_table_result_returns_none_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, get_table_result returns None (DB fallback)"""
        assert cache_without_redis.get_table_result(RUN_ID, TABLE_NAME, WORKSPACE_ID) is None

    def test_set_table_result_noop_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, set_table_result does nothing"""
        cache_without_redis.set_table_result(RUN_ID, TABLE_NAME, WORKSPACE_ID, SAMPLE_TABLE_RESULT_DATA)

    def test_invalidate_table_result_noop_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, invalidate_table_result does nothing"""
        cache_without_redis.invalidate_table_result(RUN_ID, TABLE_NAME, WORKSPACE_ID)

    def test_get_report_returns_none_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, get_report returns None (DB fallback)"""
        assert cache_without_redis.get_report(RUN_ID, WORKSPACE_ID) is None

    def test_set_report_noop_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, set_report does nothing"""
        cache_without_redis.set_report(RUN_ID, WORKSPACE_ID, SAMPLE_REPORT_DATA)

    def test_invalidate_report_noop_when_redis_disabled(self, cache_without_redis):
        """When Redis is disabled, invalidate_report does nothing"""
        cache_without_redis.invalidate_report(RUN_ID, WORKSPACE_ID)

    # -- ConnectionError handling --

    def test_get_run_returns_none_on_connection_error(self, cache_with_redis, mock_redis):
        """When Redis raises ConnectionError, get_run returns None"""
        mock_redis.get.side_effect = ConnectionError("Connection refused")
        assert cache_with_redis.get_run(RUN_ID, WORKSPACE_ID) is None

    def test_set_run_handles_connection_error(self, cache_with_redis, mock_redis):
        """When Redis raises ConnectionError, set_run does not raise"""
        mock_redis.setex.side_effect = ConnectionError("Connection refused")
        cache_with_redis.set_run(RUN_ID, WORKSPACE_ID, SAMPLE_RUN_DATA)

    def test_invalidate_run_handles_connection_error(self, cache_with_redis, mock_redis):
        """When Redis raises ConnectionError, invalidate_run does not raise"""
        mock_redis.delete.side_effect = ConnectionError("Connection refused")
        cache_with_redis.invalidate_run(RUN_ID, WORKSPACE_ID)

    def test_get_table_result_returns_none_on_connection_error(self, cache_with_redis, mock_redis):
        """When Redis raises ConnectionError, get_table_result returns None"""
        mock_redis.get.side_effect = ConnectionError("Connection refused")
        assert cache_with_redis.get_table_result(RUN_ID, TABLE_NAME, WORKSPACE_ID) is None

    def test_set_table_result_handles_connection_error(self, cache_with_redis, mock_redis):
        """When Redis raises ConnectionError, set_table_result does not raise"""
        mock_redis.setex.side_effect = ConnectionError("Connection refused")
        cache_with_redis.set_table_result(RUN_ID, TABLE_NAME, WORKSPACE_ID, SAMPLE_TABLE_RESULT_DATA)

    def test_invalidate_table_result_handles_connection_error(self, cache_with_redis, mock_redis):
        """When Redis raises ConnectionError, invalidate_table_result does not raise"""
        mock_redis.delete.side_effect = ConnectionError("Connection refused")
        cache_with_redis.invalidate_table_result(RUN_ID, TABLE_NAME, WORKSPACE_ID)

    def test_get_report_returns_none_on_connection_error(self, cache_with_redis, mock_redis):
        """When Redis raises ConnectionError, get_report returns None"""
        mock_redis.get.side_effect = ConnectionError("Connection refused")
        assert cache_with_redis.get_report(RUN_ID, WORKSPACE_ID) is None

    def test_set_report_handles_connection_error(self, cache_with_redis, mock_redis):
        """When Redis raises ConnectionError, set_report does not raise"""
        mock_redis.setex.side_effect = ConnectionError("Connection refused")
        cache_with_redis.set_report(RUN_ID, WORKSPACE_ID, SAMPLE_REPORT_DATA)

    def test_invalidate_report_handles_connection_error(self, cache_with_redis, mock_redis):
        """When Redis raises ConnectionError, invalidate_report does not raise"""
        mock_redis.delete.side_effect = ConnectionError("Connection refused")
        cache_with_redis.invalidate_report(RUN_ID, WORKSPACE_ID)

    def test_invalidate_all_for_run_handles_connection_error(self, cache_with_redis, mock_redis):
        """When Redis raises ConnectionError, invalidate_all_for_run does not raise"""
        mock_redis.delete.side_effect = ConnectionError("Connection refused")
        cache_with_redis.invalidate_all_for_run(RUN_ID, WORKSPACE_ID)

    # -- RedisError handling --

    def test_get_run_returns_none_on_redis_error(self, cache_with_redis, mock_redis):
        """When Redis raises RedisError, get_run returns None"""
        mock_redis.get.side_effect = RedisError("Redis error")
        assert cache_with_redis.get_run(RUN_ID, WORKSPACE_ID) is None

    def test_set_run_handles_redis_error(self, cache_with_redis, mock_redis):
        """When Redis raises RedisError, set_run does not raise"""
        mock_redis.setex.side_effect = RedisError("Redis error")
        cache_with_redis.set_run(RUN_ID, WORKSPACE_ID, SAMPLE_RUN_DATA)

    def test_get_table_result_returns_none_on_redis_error(self, cache_with_redis, mock_redis):
        """When Redis raises RedisError, get_table_result returns None"""
        mock_redis.get.side_effect = RedisError("Redis error")
        assert cache_with_redis.get_table_result(RUN_ID, TABLE_NAME, WORKSPACE_ID) is None

    def test_set_table_result_handles_redis_error(self, cache_with_redis, mock_redis):
        """When Redis raises RedisError, set_table_result does not raise"""
        mock_redis.setex.side_effect = RedisError("Redis error")
        cache_with_redis.set_table_result(RUN_ID, TABLE_NAME, WORKSPACE_ID, SAMPLE_TABLE_RESULT_DATA)

    def test_get_report_returns_none_on_redis_error(self, cache_with_redis, mock_redis):
        """When Redis raises RedisError, get_report returns None"""
        mock_redis.get.side_effect = RedisError("Redis error")
        assert cache_with_redis.get_report(RUN_ID, WORKSPACE_ID) is None

    def test_set_report_handles_redis_error(self, cache_with_redis, mock_redis):
        """When Redis raises RedisError, set_report does not raise"""
        mock_redis.setex.side_effect = RedisError("Redis error")
        cache_with_redis.set_report(RUN_ID, WORKSPACE_ID, SAMPLE_REPORT_DATA)


# ---------------------------------------------------------------------------
# Workspace Isolation Tests
# ---------------------------------------------------------------------------

class TestWorkspaceIsolation:
    """Tests verifying workspace_id is included in all cache keys"""

    def test_run_key_includes_workspace_id(self, cache_with_redis, mock_redis):
        """Verify run cache key contains workspace_id to prevent cross-tenant access"""
        mock_redis.get.return_value = None
        cache_with_redis.get_run(RUN_ID, workspace_id=10)
        cache_with_redis.get_run(RUN_ID, workspace_id=20)

        calls = mock_redis.get.call_args_list
        assert calls[0][0][0] == f"validation:run:10:{RUN_ID}"
        assert calls[1][0][0] == f"validation:run:20:{RUN_ID}"

    def test_table_result_key_includes_workspace_id(self, cache_with_redis, mock_redis):
        """Verify table result cache key contains workspace_id"""
        mock_redis.get.return_value = None
        cache_with_redis.get_table_result(RUN_ID, TABLE_NAME, workspace_id=10)
        cache_with_redis.get_table_result(RUN_ID, TABLE_NAME, workspace_id=20)

        calls = mock_redis.get.call_args_list
        assert calls[0][0][0] == f"validation:table:10:{RUN_ID}:{TABLE_NAME}"
        assert calls[1][0][0] == f"validation:table:20:{RUN_ID}:{TABLE_NAME}"

    def test_report_key_includes_workspace_id(self, cache_with_redis, mock_redis):
        """Verify report cache key contains workspace_id"""
        mock_redis.get.return_value = None
        cache_with_redis.get_report(RUN_ID, workspace_id=10)
        cache_with_redis.get_report(RUN_ID, workspace_id=20)

        calls = mock_redis.get.call_args_list
        assert calls[0][0][0] == f"validation:report:10:{RUN_ID}"
        assert calls[1][0][0] == f"validation:report:20:{RUN_ID}"

    def test_different_workspaces_produce_different_keys(self, cache_with_redis, mock_redis):
        """Verify same run_id with different workspace_ids produces different cache keys"""
        cache_with_redis.set_run(RUN_ID, workspace_id=1, data={"status": "pending"})
        cache_with_redis.set_run(RUN_ID, workspace_id=2, data={"status": "running"})

        calls = mock_redis.setex.call_args_list
        key1 = calls[0][0][0]
        key2 = calls[1][0][0]
        assert key1 != key2
        assert key1 == f"validation:run:1:{RUN_ID}"
        assert key2 == f"validation:run:2:{RUN_ID}"


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
