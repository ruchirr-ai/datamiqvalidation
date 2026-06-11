"""
Unit tests for AthenaVerifier service.

Tests table queryability verification and row count queries
with timeout handling and error scenarios.
"""

import pytest
from unittest.mock import MagicMock, patch
import time

from services.bq_iceberg_migration.athena_verifier import (
    AthenaVerifier,
    VerificationResult,
    DEFAULT_QUERYABLE_TIMEOUT_SECONDS,
    DEFAULT_COUNT_TIMEOUT_SECONDS,
)


# --- Sample payloads ---

SAMPLE_DATABASE = "analytics_db"
SAMPLE_TABLE = "events"
SAMPLE_QUERY_EXECUTION_ID = "query-exec-12345"

SAMPLE_START_RESPONSE = {"QueryExecutionId": SAMPLE_QUERY_EXECUTION_ID}

SAMPLE_SUCCEEDED_STATUS = {
    "QueryExecution": {
        "Status": {
            "State": "SUCCEEDED",
            "StateChangeReason": "",
        }
    }
}

SAMPLE_FAILED_STATUS = {
    "QueryExecution": {
        "Status": {
            "State": "FAILED",
            "StateChangeReason": "Table not found",
        }
    }
}

SAMPLE_RUNNING_STATUS = {
    "QueryExecution": {
        "Status": {
            "State": "RUNNING",
            "StateChangeReason": "",
        }
    }
}

SAMPLE_COUNT_RESULTS = {
    "ResultSet": {
        "Rows": [
            {"Data": [{"VarCharValue": "_col0"}]},  # Header row
            {"Data": [{"VarCharValue": "42000"}]},   # Data row
        ]
    }
}


def _make_athena_client(
    start_response=None,
    status_responses=None,
    results_response=None,
):
    """Create a mock Athena client with configurable responses."""
    client = MagicMock()
    client.start_query_execution = MagicMock(
        return_value=start_response or SAMPLE_START_RESPONSE
    )

    if status_responses:
        client.get_query_execution = MagicMock(side_effect=status_responses)
    else:
        client.get_query_execution = MagicMock(return_value=SAMPLE_SUCCEEDED_STATUS)

    client.get_query_results = MagicMock(
        return_value=results_response or SAMPLE_COUNT_RESULTS
    )
    client.stop_query_execution = MagicMock()

    return client


class TestVerifyTableQueryable:
    """Test verify_table_queryable executes SELECT 1 LIMIT 1."""

    def test_success_returns_success_status(self):
        """Should return status='success' when query succeeds."""
        client = _make_athena_client()
        verifier = AthenaVerifier(athena_client=client)

        result = verifier.verify_table_queryable(SAMPLE_DATABASE, SAMPLE_TABLE)

        assert result.status == "success"
        assert result.query_execution_id == SAMPLE_QUERY_EXECUTION_ID

    def test_executes_correct_query(self):
        """Should execute SELECT 1 FROM <db>.<table> LIMIT 1."""
        client = _make_athena_client()
        verifier = AthenaVerifier(athena_client=client)

        verifier.verify_table_queryable(SAMPLE_DATABASE, SAMPLE_TABLE)

        call_kwargs = client.start_query_execution.call_args[1]
        assert f'"{SAMPLE_DATABASE}"' in call_kwargs["QueryString"]
        assert f'"{SAMPLE_TABLE}"' in call_kwargs["QueryString"]
        assert "SELECT 1" in call_kwargs["QueryString"]
        assert "LIMIT 1" in call_kwargs["QueryString"]

    def test_uses_specified_workgroup(self):
        """Should use the configured workgroup."""
        client = _make_athena_client()
        verifier = AthenaVerifier(athena_client=client, workgroup="custom_wg")

        verifier.verify_table_queryable(SAMPLE_DATABASE, SAMPLE_TABLE)

        call_kwargs = client.start_query_execution.call_args[1]
        assert call_kwargs["WorkGroup"] == "custom_wg"

    def test_failed_query_returns_failed_status(self):
        """Should return status='failed' when query fails."""
        client = _make_athena_client(status_responses=[SAMPLE_FAILED_STATUS])
        verifier = AthenaVerifier(athena_client=client)

        result = verifier.verify_table_queryable(SAMPLE_DATABASE, SAMPLE_TABLE)

        assert result.status == "failed"
        assert result.error_message is not None
        assert "Table not found" in result.error_message

    def test_start_failure_returns_error_status(self):
        """Should return status='error' when start_query_execution fails."""
        client = MagicMock()
        client.start_query_execution = MagicMock(
            side_effect=Exception("Access denied")
        )
        verifier = AthenaVerifier(athena_client=client)

        result = verifier.verify_table_queryable(SAMPLE_DATABASE, SAMPLE_TABLE)

        assert result.status == "error"
        assert result.error_code == "ATHENA_START_FAILED"
        assert "Access denied" in result.error_message

    @patch("services.bq_iceberg_migration.athena_verifier.time.sleep")
    @patch("services.bq_iceberg_migration.athena_verifier.time.time")
    def test_timeout_returns_timeout_status(self, mock_time, mock_sleep):
        """Should return status='timeout' when query exceeds timeout."""
        # Simulate time passing beyond timeout
        mock_time.side_effect = [0.0, 0.0, 130.0]  # start, first check, second check
        client = _make_athena_client(status_responses=[SAMPLE_RUNNING_STATUS] * 5)
        verifier = AthenaVerifier(athena_client=client)

        result = verifier.verify_table_queryable(
            SAMPLE_DATABASE, SAMPLE_TABLE, timeout_seconds=120
        )

        assert result.status == "timeout"
        assert result.error_code == "ATHENA_VERIFICATION_TIMEOUT"

    @patch("services.bq_iceberg_migration.athena_verifier.time.sleep")
    @patch("services.bq_iceberg_migration.athena_verifier.time.time")
    def test_timeout_attempts_cancel(self, mock_time, mock_sleep):
        """Should attempt to cancel the query on timeout."""
        mock_time.side_effect = [0.0, 0.0, 130.0]
        client = _make_athena_client(status_responses=[SAMPLE_RUNNING_STATUS] * 5)
        verifier = AthenaVerifier(athena_client=client)

        verifier.verify_table_queryable(
            SAMPLE_DATABASE, SAMPLE_TABLE, timeout_seconds=120
        )

        client.stop_query_execution.assert_called_once_with(
            QueryExecutionId=SAMPLE_QUERY_EXECUTION_ID
        )

    def test_default_timeout_is_120_seconds(self):
        """Default timeout for verify_table_queryable should be 120s."""
        assert DEFAULT_QUERYABLE_TIMEOUT_SECONDS == 120

    def test_returns_verification_result_type(self):
        """Should return a VerificationResult dataclass."""
        client = _make_athena_client()
        verifier = AthenaVerifier(athena_client=client)

        result = verifier.verify_table_queryable(SAMPLE_DATABASE, SAMPLE_TABLE)

        assert isinstance(result, VerificationResult)

    def test_duration_seconds_populated(self):
        """Should populate duration_seconds in the result."""
        client = _make_athena_client()
        verifier = AthenaVerifier(athena_client=client)

        result = verifier.verify_table_queryable(SAMPLE_DATABASE, SAMPLE_TABLE)

        assert result.duration_seconds is not None
        assert result.duration_seconds >= 0

    def test_output_location_included_when_provided(self):
        """Should include ResultConfiguration when output_location is set."""
        client = _make_athena_client()
        verifier = AthenaVerifier(
            athena_client=client,
            output_location="s3://results-bucket/output/",
        )

        verifier.verify_table_queryable(SAMPLE_DATABASE, SAMPLE_TABLE)

        call_kwargs = client.start_query_execution.call_args[1]
        assert "ResultConfiguration" in call_kwargs
        assert call_kwargs["ResultConfiguration"]["OutputLocation"] == "s3://results-bucket/output/"


class TestCountRows:
    """Test count_rows executes SELECT COUNT(*) and returns integer result."""

    def test_returns_row_count_on_success(self):
        """Should return the integer row count from query results."""
        client = _make_athena_client()
        verifier = AthenaVerifier(athena_client=client)

        result = verifier.count_rows(SAMPLE_DATABASE, SAMPLE_TABLE)

        assert result == 42000

    def test_executes_count_query(self):
        """Should execute SELECT COUNT(*) FROM <db>.<table>."""
        client = _make_athena_client()
        verifier = AthenaVerifier(athena_client=client)

        verifier.count_rows(SAMPLE_DATABASE, SAMPLE_TABLE)

        call_kwargs = client.start_query_execution.call_args[1]
        assert "COUNT(*)" in call_kwargs["QueryString"]
        assert f'"{SAMPLE_DATABASE}"' in call_kwargs["QueryString"]
        assert f'"{SAMPLE_TABLE}"' in call_kwargs["QueryString"]

    def test_returns_none_on_failure(self):
        """Should return None when the query fails."""
        client = _make_athena_client(status_responses=[SAMPLE_FAILED_STATUS])
        verifier = AthenaVerifier(athena_client=client)

        result = verifier.count_rows(SAMPLE_DATABASE, SAMPLE_TABLE)

        assert result is None

    def test_returns_none_on_start_failure(self):
        """Should return None when start_query_execution fails."""
        client = MagicMock()
        client.start_query_execution = MagicMock(
            side_effect=Exception("Service unavailable")
        )
        verifier = AthenaVerifier(athena_client=client)

        result = verifier.count_rows(SAMPLE_DATABASE, SAMPLE_TABLE)

        assert result is None

    @patch("services.bq_iceberg_migration.athena_verifier.time.sleep")
    @patch("services.bq_iceberg_migration.athena_verifier.time.time")
    def test_returns_none_on_timeout(self, mock_time, mock_sleep):
        """Should return None when query times out."""
        mock_time.side_effect = [0.0, 0.0, 310.0]
        client = _make_athena_client(status_responses=[SAMPLE_RUNNING_STATUS] * 5)
        verifier = AthenaVerifier(athena_client=client)

        result = verifier.count_rows(
            SAMPLE_DATABASE, SAMPLE_TABLE, timeout_seconds=300
        )

        assert result is None

    def test_default_timeout_is_300_seconds(self):
        """Default timeout for count_rows should be 300s."""
        assert DEFAULT_COUNT_TIMEOUT_SECONDS == 300

    def test_handles_zero_row_count(self):
        """Should correctly return 0 for empty tables."""
        zero_results = {
            "ResultSet": {
                "Rows": [
                    {"Data": [{"VarCharValue": "_col0"}]},
                    {"Data": [{"VarCharValue": "0"}]},
                ]
            }
        }
        client = _make_athena_client(results_response=zero_results)
        verifier = AthenaVerifier(athena_client=client)

        result = verifier.count_rows(SAMPLE_DATABASE, SAMPLE_TABLE)

        assert result == 0

    def test_handles_large_row_count(self):
        """Should correctly parse large row counts."""
        large_results = {
            "ResultSet": {
                "Rows": [
                    {"Data": [{"VarCharValue": "_col0"}]},
                    {"Data": [{"VarCharValue": "999999999999"}]},
                ]
            }
        }
        client = _make_athena_client(results_response=large_results)
        verifier = AthenaVerifier(athena_client=client)

        result = verifier.count_rows(SAMPLE_DATABASE, SAMPLE_TABLE)

        assert result == 999999999999

    def test_custom_timeout_respected(self):
        """Should accept a custom timeout parameter."""
        client = _make_athena_client()
        verifier = AthenaVerifier(athena_client=client)

        # Should not raise — just verifying the parameter is accepted
        result = verifier.count_rows(
            SAMPLE_DATABASE, SAMPLE_TABLE, timeout_seconds=60
        )

        assert result == 42000


class TestVerificationResult:
    """Test VerificationResult dataclass structure."""

    def test_success_result_fields(self):
        """Success result should have correct field values."""
        result = VerificationResult(
            status="success",
            row_count=1000,
            query_execution_id="exec-123",
            duration_seconds=5.2,
        )

        assert result.status == "success"
        assert result.row_count == 1000
        assert result.error_message is None
        assert result.error_code is None
        assert result.query_execution_id == "exec-123"
        assert result.duration_seconds == 5.2

    def test_error_result_fields(self):
        """Error result should have error details populated."""
        result = VerificationResult(
            status="error",
            error_message="Access denied",
            error_code="ATHENA_START_FAILED",
            duration_seconds=0.1,
        )

        assert result.status == "error"
        assert result.row_count is None
        assert result.error_message == "Access denied"
        assert result.error_code == "ATHENA_START_FAILED"

    def test_timeout_result_fields(self):
        """Timeout result should have timeout error code."""
        result = VerificationResult(
            status="timeout",
            error_message="Query timed out after 120s",
            error_code="ATHENA_VERIFICATION_TIMEOUT",
            query_execution_id="exec-456",
            duration_seconds=120.0,
        )

        assert result.status == "timeout"
        assert result.error_code == "ATHENA_VERIFICATION_TIMEOUT"
