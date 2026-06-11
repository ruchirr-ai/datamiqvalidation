"""
Unit tests for Error Code Categorization and Structured Logging.

Tests error code constants, credential sanitization, structured logging,
and the MigrationLogger class for Iceberg migration operations.

Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
"""

import pytest
from datetime import datetime, timezone

from services.bq_iceberg_migration.error_codes import (
    ErrorCode,
    ErrorCategory,
    ErrorCodeMetadata,
    ERROR_CODE_REGISTRY,
    RETRY_DELAYS_SECONDS,
    MigrationLogEntry,
    MigrationLogger,
    is_retryable,
    get_retry_delays,
    get_error_category,
    sanitize_message,
    sanitize_context,
)


# --- Sample Payloads ---

SAMPLE_CONTEXT_WITH_CREDENTIALS = {
    "table_name": "events",
    "aws_secret_access_key": "AKIAIOSFODNN7EXAMPLE/wJalrXUtnFEMI",
    "column_count": 15,
    "password": "super-secret-password",
    "aws_region": "us-east-1",
}

SAMPLE_CONTEXT_CLEAN = {
    "table_name": "events",
    "column_count": 15,
    "aws_region": "us-east-1",
    "partition_spec": "day(event_date)",
}

SAMPLE_MESSAGE_WITH_CREDENTIALS = (
    "Failed to connect: aws_secret_access_key=AKIAIOSFODNN7EXAMPLE "
    "password=mysecretpass123"
)

SAMPLE_MESSAGE_CLEAN = "Failed to create table 'events' in database 'analytics_db'"


# --- Tests: Error Code Constants ---

class TestErrorCodeConstants:
    """Test that all error codes from the design are defined."""

    def test_all_error_codes_defined(self):
        """All error codes from the design's error table should be defined."""
        expected_codes = [
            "GLUE_PERMISSION_DENIED",
            "GLUE_REGISTRATION_FAILED",
            "ICEBERG_TABLE_CREATE_FAILED",
            "ICEBERG_APPEND_FAILED",
            "ICEBERG_S3_ACCESS_ERROR",
            "ICEBERG_SCHEMA_EVOLUTION_FAILED",
            "SCHEMA_EVOLUTION_INCOMPATIBLE",
            "S3_TABLES_API_FAILED",
            "ATHENA_VERIFICATION_TIMEOUT",
            "COST_CALCULATION_FAILED",
            "CUSTOM_STRUCTURE_INVALID",
        ]
        for code_name in expected_codes:
            assert hasattr(ErrorCode, code_name), f"Missing error code: {code_name}"

    def test_error_codes_are_strings(self):
        """Error codes should be string values for JSON serialization."""
        for code in ErrorCode:
            assert isinstance(code.value, str)

    def test_all_codes_in_registry(self):
        """Every ErrorCode should have metadata in the registry."""
        for code in ErrorCode:
            assert code in ERROR_CODE_REGISTRY, f"Missing registry entry for {code}"

    def test_registry_metadata_types(self):
        """Registry entries should have correct metadata types."""
        for code, metadata in ERROR_CODE_REGISTRY.items():
            assert isinstance(metadata, ErrorCodeMetadata)
            assert metadata.code == code
            assert isinstance(metadata.category, ErrorCategory)
            assert isinstance(metadata.retryable, bool)
            assert isinstance(metadata.max_retries, int)
            assert isinstance(metadata.description, str)
            assert len(metadata.description) > 0


# --- Tests: Retry Configuration ---

class TestRetryConfiguration:
    """Test retry behavior for error codes."""

    def test_retry_delays_are_5_15_45(self):
        """Retry delays should be 5s, 15s, 45s per design."""
        assert RETRY_DELAYS_SECONDS == [5, 15, 45]

    def test_retryable_codes(self):
        """Retryable error codes should be correctly identified."""
        retryable_codes = [
            ErrorCode.GLUE_REGISTRATION_FAILED,
            ErrorCode.ICEBERG_TABLE_CREATE_FAILED,
            ErrorCode.ICEBERG_APPEND_FAILED,
            ErrorCode.ICEBERG_S3_ACCESS_ERROR,
            ErrorCode.S3_TABLES_API_FAILED,
        ]
        for code in retryable_codes:
            assert is_retryable(code) is True, f"{code} should be retryable"

    def test_non_retryable_codes(self):
        """Non-retryable error codes should be correctly identified."""
        non_retryable_codes = [
            ErrorCode.GLUE_PERMISSION_DENIED,
            ErrorCode.ICEBERG_SCHEMA_EVOLUTION_FAILED,
            ErrorCode.SCHEMA_EVOLUTION_INCOMPATIBLE,
            ErrorCode.ATHENA_VERIFICATION_TIMEOUT,
            ErrorCode.COST_CALCULATION_FAILED,
            ErrorCode.CUSTOM_STRUCTURE_INVALID,
        ]
        for code in non_retryable_codes:
            assert is_retryable(code) is False, f"{code} should NOT be retryable"

    def test_get_retry_delays_retryable(self):
        """Retryable codes should return [5, 15, 45] delays."""
        delays = get_retry_delays(ErrorCode.ICEBERG_S3_ACCESS_ERROR)
        assert delays == [5, 15, 45]

    def test_get_retry_delays_non_retryable(self):
        """Non-retryable codes should return empty list."""
        delays = get_retry_delays(ErrorCode.GLUE_PERMISSION_DENIED)
        assert delays == []

    def test_retryable_codes_have_max_retries_3(self):
        """All retryable codes should have max_retries=3."""
        for code, metadata in ERROR_CODE_REGISTRY.items():
            if metadata.retryable:
                assert metadata.max_retries == 3, (
                    f"{code} should have max_retries=3"
                )

    def test_non_retryable_codes_have_max_retries_0(self):
        """All non-retryable codes should have max_retries=0."""
        for code, metadata in ERROR_CODE_REGISTRY.items():
            if not metadata.retryable:
                assert metadata.max_retries == 0, (
                    f"{code} should have max_retries=0"
                )


# --- Tests: Error Categories ---

class TestErrorCategories:
    """Test error code categorization."""

    def test_get_error_category_auth(self):
        """GLUE_PERMISSION_DENIED should be in Auth category."""
        assert get_error_category(ErrorCode.GLUE_PERMISSION_DENIED) == ErrorCategory.AUTH

    def test_get_error_category_glue(self):
        """GLUE_REGISTRATION_FAILED should be in Glue category."""
        assert get_error_category(ErrorCode.GLUE_REGISTRATION_FAILED) == ErrorCategory.GLUE

    def test_get_error_category_iceberg(self):
        """ICEBERG_TABLE_CREATE_FAILED should be in Iceberg category."""
        assert get_error_category(ErrorCode.ICEBERG_TABLE_CREATE_FAILED) == ErrorCategory.ICEBERG

    def test_get_error_category_s3(self):
        """ICEBERG_S3_ACCESS_ERROR should be in S3 category."""
        assert get_error_category(ErrorCode.ICEBERG_S3_ACCESS_ERROR) == ErrorCategory.S3

    def test_get_error_category_schema(self):
        """SCHEMA_EVOLUTION_INCOMPATIBLE should be in Schema category."""
        assert get_error_category(ErrorCode.SCHEMA_EVOLUTION_INCOMPATIBLE) == ErrorCategory.SCHEMA

    def test_get_error_category_s3_tables(self):
        """S3_TABLES_API_FAILED should be in S3 Tables category."""
        assert get_error_category(ErrorCode.S3_TABLES_API_FAILED) == ErrorCategory.S3_TABLES

    def test_get_error_category_athena(self):
        """ATHENA_VERIFICATION_TIMEOUT should be in Athena category."""
        assert get_error_category(ErrorCode.ATHENA_VERIFICATION_TIMEOUT) == ErrorCategory.ATHENA

    def test_get_error_category_cost(self):
        """COST_CALCULATION_FAILED should be in Cost category."""
        assert get_error_category(ErrorCode.COST_CALCULATION_FAILED) == ErrorCategory.COST

    def test_get_error_category_validation(self):
        """CUSTOM_STRUCTURE_INVALID should be in Validation category."""
        assert get_error_category(ErrorCode.CUSTOM_STRUCTURE_INVALID) == ErrorCategory.VALIDATION


# --- Tests: Credential Sanitization ---

class TestSanitizeMessage:
    """Test that credential values are removed from log messages."""

    def test_sanitize_message_with_secret_key(self):
        """Messages containing aws_secret_access_key should be redacted."""
        msg = "Error: aws_secret_access_key=AKIAIOSFODNN7EXAMPLE/wJalrXUtnFEMI"
        result = sanitize_message(msg)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "***REDACTED***" in result

    def test_sanitize_message_with_password(self):
        """Messages containing password values should be redacted."""
        msg = "Connection failed: password=mysecretpass123"
        result = sanitize_message(msg)
        assert "mysecretpass123" not in result
        assert "***REDACTED***" in result

    def test_sanitize_message_clean(self):
        """Messages without credentials should pass through unchanged."""
        msg = "Table 'events' created successfully in 2.5s"
        result = sanitize_message(msg)
        assert result == msg

    def test_sanitize_message_preserves_key_name(self):
        """The key name should be preserved, only the value redacted."""
        msg = "Error: password=secret123"
        result = sanitize_message(msg)
        assert "password" in result
        assert "secret123" not in result

    def test_sanitize_message_empty_string(self):
        """Empty string should return empty string."""
        assert sanitize_message("") == ""


class TestSanitizeContext:
    """Test that credential values are removed from context dictionaries."""

    def test_sanitize_context_redacts_secret_key(self):
        """aws_secret_access_key should be redacted in context."""
        result = sanitize_context(SAMPLE_CONTEXT_WITH_CREDENTIALS)
        assert result["aws_secret_access_key"] == "***REDACTED***"

    def test_sanitize_context_redacts_password(self):
        """password should be redacted in context."""
        result = sanitize_context(SAMPLE_CONTEXT_WITH_CREDENTIALS)
        assert result["password"] == "***REDACTED***"

    def test_sanitize_context_preserves_safe_values(self):
        """Non-sensitive values should be preserved."""
        result = sanitize_context(SAMPLE_CONTEXT_WITH_CREDENTIALS)
        assert result["table_name"] == "events"
        assert result["column_count"] == 15
        assert result["aws_region"] == "us-east-1"

    def test_sanitize_context_clean_dict(self):
        """A context without credentials should pass through unchanged."""
        result = sanitize_context(SAMPLE_CONTEXT_CLEAN)
        assert result == SAMPLE_CONTEXT_CLEAN

    def test_sanitize_context_does_not_modify_original(self):
        """Original dictionary should not be modified."""
        original = dict(SAMPLE_CONTEXT_WITH_CREDENTIALS)
        sanitize_context(SAMPLE_CONTEXT_WITH_CREDENTIALS)
        assert SAMPLE_CONTEXT_WITH_CREDENTIALS == original

    def test_sanitize_context_empty_dict(self):
        """Empty dict should return empty dict."""
        assert sanitize_context({}) == {}


# --- Tests: MigrationLogEntry ---

class TestMigrationLogEntry:
    """Test MigrationLogEntry data class."""

    def test_to_dict_basic(self):
        """to_dict should include all required fields."""
        entry = MigrationLogEntry(
            timestamp=datetime(2026, 1, 25, 10, 0, 0, tzinfo=timezone.utc),
            level="INFO",
            stage="load",
            operation="table_creation_start",
            message="Creating table 'events'",
            migration_id=1,
        )
        result = entry.to_dict()

        assert result["timestamp"] == "2026-01-25T10:00:00+00:00"
        assert result["level"] == "INFO"
        assert result["stage"] == "load"
        assert result["operation"] == "table_creation_start"
        assert result["message"] == "Creating table 'events'"
        assert result["migration_id"] == 1

    def test_to_dict_with_error_code(self):
        """to_dict should include error_code when present."""
        entry = MigrationLogEntry(
            timestamp=datetime(2026, 1, 25, 10, 0, 0, tzinfo=timezone.utc),
            level="ERROR",
            stage="load",
            operation="table_creation",
            message="Failed to create table",
            error_code="ICEBERG_TABLE_CREATE_FAILED",
            table_name="events",
            migration_id=1,
        )
        result = entry.to_dict()

        assert result["error_code"] == "ICEBERG_TABLE_CREATE_FAILED"
        assert result["table_name"] == "events"

    def test_to_dict_sanitizes_context(self):
        """to_dict should sanitize credential values in context."""
        entry = MigrationLogEntry(
            timestamp=datetime(2026, 1, 25, 10, 0, 0, tzinfo=timezone.utc),
            level="ERROR",
            stage="load",
            operation="connection",
            message="Connection failed",
            migration_id=1,
            context={"password": "secret123", "table_name": "events"},
        )
        result = entry.to_dict()

        assert result["context"]["password"] == "***REDACTED***"
        assert result["context"]["table_name"] == "events"

    def test_to_dict_excludes_none_optional_fields(self):
        """to_dict should not include None optional fields."""
        entry = MigrationLogEntry(
            timestamp=datetime(2026, 1, 25, 10, 0, 0, tzinfo=timezone.utc),
            level="INFO",
            stage="load",
            operation="test",
            message="Test message",
        )
        result = entry.to_dict()

        assert "error_code" not in result
        assert "table_name" not in result
        assert "migration_id" not in result
        assert "context" not in result


# --- Tests: MigrationLogger ---

class TestMigrationLogger:
    """Test the MigrationLogger structured logging class."""

    def test_log_stage_transition(self):
        """log_stage_transition should create INFO entry with correct fields."""
        ml = MigrationLogger(migration_id=42)
        entry = ml.log_stage_transition("transfer", "load")

        assert entry.level == "INFO"
        assert entry.stage == "load"
        assert entry.operation == "stage_transition"
        assert "transfer" in entry.message
        assert "load" in entry.message
        assert entry.migration_id == 42
        assert entry.context["from_stage"] == "transfer"
        assert entry.context["to_stage"] == "load"

    def test_log_table_creation_start(self):
        """log_table_creation_start should log table name and column count."""
        ml = MigrationLogger(migration_id=1)
        entry = ml.log_table_creation_start("events", 15, "day(event_date)")

        assert entry.level == "INFO"
        assert entry.stage == "load"
        assert entry.operation == "table_creation_start"
        assert "events" in entry.message
        assert "15" in entry.message
        assert entry.table_name == "events"
        assert entry.context["column_count"] == 15
        assert entry.context["partition_spec"] == "day(event_date)"

    def test_log_schema_mapping(self):
        """log_schema_mapping should log column count, partition, and sort order."""
        ml = MigrationLogger(migration_id=1)
        entry = ml.log_schema_mapping(
            "users", 8, partition_spec="day(created_at)", sort_order="user_id"
        )

        assert entry.level == "INFO"
        assert entry.operation == "schema_mapping"
        assert "users" in entry.message
        assert "8" in entry.message
        assert entry.context["partition_spec"] == "day(created_at)"
        assert entry.context["sort_order"] == "user_id"

    def test_log_data_file_registration(self):
        """log_data_file_registration should log file count."""
        ml = MigrationLogger(migration_id=1)
        entry = ml.log_data_file_registration("events", 25)

        assert entry.level == "INFO"
        assert entry.operation == "data_file_registration"
        assert "25" in entry.message
        assert "events" in entry.message
        assert entry.context["file_count"] == 25

    def test_log_table_creation_complete(self):
        """log_table_creation_complete should log success with duration."""
        ml = MigrationLogger(migration_id=1)
        entry = ml.log_table_creation_complete("events", duration_seconds=3.45)

        assert entry.level == "INFO"
        assert entry.operation == "table_creation_complete"
        assert "events" in entry.message
        assert "3.45" in entry.message
        assert entry.context["duration_seconds"] == 3.45

    def test_log_schema_evolution_column_addition(self):
        """log_schema_evolution should log column addition."""
        ml = MigrationLogger(migration_id=1)
        entry = ml.log_schema_evolution(
            "events", "new_col", "column_addition", new_type="string"
        )

        assert entry.level == "INFO"
        assert entry.operation == "schema_evolution"
        assert "new_col" in entry.message
        assert "optional" in entry.message
        assert entry.context["operation_type"] == "column_addition"

    def test_log_schema_evolution_type_promotion(self):
        """log_schema_evolution should log type promotion with old and new types."""
        ml = MigrationLogger(migration_id=1)
        entry = ml.log_schema_evolution(
            "events", "count_col", "type_promotion",
            old_type="int", new_type="long"
        )

        assert entry.level == "INFO"
        assert "type promotion" in entry.message
        assert "int" in entry.message
        assert "long" in entry.message
        assert entry.context["old_type"] == "int"
        assert entry.context["new_type"] == "long"

    def test_log_error_with_error_code(self):
        """log_error should create ERROR entry with categorized error_code."""
        ml = MigrationLogger(migration_id=1)
        entry = ml.log_error(
            error_code=ErrorCode.ICEBERG_TABLE_CREATE_FAILED,
            operation="create_table",
            message="Table creation failed: S3 access denied",
            table_name="events",
        )

        assert entry.level == "ERROR"
        assert entry.error_code == "ICEBERG_TABLE_CREATE_FAILED"
        assert entry.table_name == "events"
        assert entry.context["error_category"] == "Iceberg"
        assert entry.context["retryable"] is True

    def test_log_error_sanitizes_credentials(self):
        """log_error should sanitize credentials in message and context."""
        ml = MigrationLogger(migration_id=1)
        entry = ml.log_error(
            error_code=ErrorCode.ICEBERG_S3_ACCESS_ERROR,
            operation="append_data",
            message="Failed: password=secret123",
            context={"aws_secret_access_key": "AKIAIOSFODNN7EXAMPLE"},
        )

        assert "secret123" not in entry.message
        assert "***REDACTED***" in entry.message
        assert entry.context["aws_secret_access_key"] == "***REDACTED***"

    def test_log_warning(self):
        """log_warning should create WARNING entry."""
        ml = MigrationLogger(migration_id=1)
        entry = ml.log_warning(
            operation="verification",
            message="Athena query timed out",
            table_name="events",
            error_code=ErrorCode.ATHENA_VERIFICATION_TIMEOUT,
        )

        assert entry.level == "WARNING"
        assert entry.error_code == "ATHENA_VERIFICATION_TIMEOUT"
        assert entry.table_name == "events"

    def test_log_progress(self):
        """log_progress should log completed/total/percentage."""
        ml = MigrationLogger(migration_id=1)
        entry = ml.log_progress(5, 10, 50)

        assert entry.level == "INFO"
        assert entry.operation == "progress_update"
        assert "5/10" in entry.message
        assert "50%" in entry.message
        assert entry.context["completed_tables"] == 5
        assert entry.context["total_tables"] == 10
        assert entry.context["progress_percentage"] == 50

    def test_entries_property_returns_copy(self):
        """entries property should return a copy of the internal list."""
        ml = MigrationLogger(migration_id=1)
        ml.log_stage_transition("export", "transfer")
        ml.log_stage_transition("transfer", "load")

        entries = ml.entries
        assert len(entries) == 2

        # Modifying the returned list should not affect internal state
        entries.clear()
        assert len(ml.entries) == 2

    def test_no_credentials_in_any_log_entry(self):
        """No log entry should ever contain credential values."""
        ml = MigrationLogger(migration_id=1)

        # Log with credentials in message
        ml.log_error(
            error_code=ErrorCode.ICEBERG_S3_ACCESS_ERROR,
            operation="test",
            message="secret_key=AKIAIOSFODNN7EXAMPLE token=abc123xyz",
            context={
                "password": "my-password",
                "session_token": "token-value",
                "table_name": "safe_value",
            },
        )

        for entry in ml.entries:
            entry_dict = entry.to_dict()
            # Check message
            assert "AKIAIOSFODNN7EXAMPLE" not in entry_dict["message"]
            assert "abc123xyz" not in entry_dict["message"]
            # Check context
            if "context" in entry_dict:
                for key, value in entry_dict["context"].items():
                    if key in ("password", "session_token"):
                        assert value == "***REDACTED***"

    def test_stage_transitions_logged_as_info(self):
        """Stage transitions should always be INFO level (Requirement 11.1)."""
        ml = MigrationLogger(migration_id=1)
        transitions = [
            ("export", "transfer"),
            ("transfer", "review"),
            ("review", "load"),
        ]
        for from_s, to_s in transitions:
            entry = ml.log_stage_transition(from_s, to_s)
            assert entry.level == "INFO"

    def test_table_operations_logged_as_info(self):
        """Table operations should be INFO level (Requirement 11.2)."""
        ml = MigrationLogger(migration_id=1)

        ops = [
            ml.log_table_creation_start("t1", 5),
            ml.log_schema_mapping("t1", 5),
            ml.log_data_file_registration("t1", 10),
            ml.log_table_creation_complete("t1", 2.0),
        ]
        for entry in ops:
            assert entry.level == "INFO"

    def test_errors_have_categorized_error_code(self):
        """Error entries should always have a categorized error_code (Requirement 11.3)."""
        ml = MigrationLogger(migration_id=1)

        for code in ErrorCode:
            entry = ml.log_error(
                error_code=code,
                operation="test_op",
                message=f"Test error for {code.value}",
            )
            assert entry.error_code == code.value
            assert entry.level == "ERROR"
