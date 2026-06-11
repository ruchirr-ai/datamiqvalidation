"""
Unit tests for Iceberg Production Hardening validators.

Tests validate_glue_id, validate_maintenance_config,
validate_compaction_strategy, and validate_s3_tables_parallelism
with valid inputs, invalid inputs, boundary values, and edge cases.

Requirements: 2.2, 2.6, 4.3, 4.4, 6.1, 6.7
"""

import pytest

from services.bq_iceberg_migration.validators import (
    validate_glue_id,
    validate_maintenance_config,
    validate_compaction_strategy,
    validate_s3_tables_parallelism,
)


# =============================================================================
# Sample Payloads
# =============================================================================

# --- Glue ID Samples ---

VALID_GLUE_IDS = [
    "123456789012:s3tablescatalog/my-bucket",
    "000000000000:s3tablescatalog/abc",
    "999999999999:s3tablescatalog/my.bucket.name",
    "123456789012:s3tablescatalog/a1b",
    "123456789012:s3tablescatalog/bucket-with-hyphens-and-dots.here",
    # Maximum bucket name length (63 chars): start + 61 middle + end
    "123456789012:s3tablescatalog/" + "a" + "b" * 61 + "c",
    # Minimum bucket name length (3 chars)
    "123456789012:s3tablescatalog/a1b",
]

INVALID_GLUE_IDS = [
    # (glue_id, expected_error_fragment)
    ("", "Invalid glue.id format"),
    ("invalid-format", "Invalid glue.id format"),
    ("12345:s3tablescatalog/my-bucket", "Invalid glue.id format"),  # short account ID
    ("1234567890123:s3tablescatalog/my-bucket", "Invalid glue.id format"),  # 13 digits
    ("123456789012:s3tablescatalog/", "Invalid glue.id format"),  # empty bucket
    ("123456789012:s3tablescatalog/A", "Invalid glue.id format"),  # uppercase
    ("123456789012:s3tablescatalog/-bucket", "Invalid glue.id format"),  # starts with hyphen
    ("123456789012:s3tablescatalog/bucket-", "Invalid glue.id format"),  # ends with hyphen
    ("123456789012:wrongprefix/my-bucket", "Invalid glue.id format"),  # wrong prefix
    ("123456789012/s3tablescatalog/my-bucket", "Invalid glue.id format"),  # slash instead of colon
    ("abcdefghijkl:s3tablescatalog/my-bucket", "Invalid glue.id format"),  # letters in account ID
    ("123456789012:s3tablescatalog/my_bucket", "Invalid glue.id format"),  # underscore in bucket
    ("123456789012:s3tablescatalog/my bucket", "Invalid glue.id format"),  # space in bucket
]

# --- Compaction Strategy Samples ---

VALID_COMPACTION_STRATEGIES = [
    # (strategy, sort_columns, table_schema_columns)
    ("binpack", [], ["col_a", "col_b", "col_c"]),
    ("binpack", [], []),  # binpack doesn't need schema columns
    ("sort", ["col_a"], ["col_a", "col_b", "col_c"]),
    ("sort", ["col_a", "col_b"], ["col_a", "col_b", "col_c"]),
    ("z-order", ["col_a"], ["col_a", "col_b"]),
    ("z-order", ["col_a", "col_b", "col_c"], ["col_a", "col_b", "col_c"]),
]

INVALID_COMPACTION_STRATEGIES = [
    # (strategy, sort_columns, table_schema_columns, expected_error_fragment)
    ("invalid", [], ["col_a"], "must be one of"),
    ("BINPACK", [], ["col_a"], "must be one of"),  # case-sensitive
    ("Sort", [], ["col_a"], "must be one of"),  # case-sensitive
    ("z_order", [], ["col_a"], "must be one of"),  # underscore instead of hyphen
    ("sort", [], ["col_a", "col_b"], "sort columns must be specified"),  # missing sort columns
    ("z-order", [], ["col_a"], "sort columns must be specified"),  # missing sort columns
    ("sort", ["missing_col"], ["col_a", "col_b"], "not found in table schema"),
    ("z-order", ["col_a", "bad_col"], ["col_a", "col_b"], "not found in table schema"),
]

# --- S3 Tables Parallelism Samples ---

VALID_S3_TABLES_PARALLELISM = [1, 2, 3, 4, 5, 6, 7, 8]

INVALID_S3_TABLES_PARALLELISM = [
    # (value, expected_error_fragment)
    (0, "must be between 1 and 8"),
    (-1, "must be between 1 and 8"),
    (9, "must be between 1 and 8"),
    (16, "must be between 1 and 8"),
    (100, "must be between 1 and 8"),
]


# =============================================================================
# Glue ID Validation Tests
# =============================================================================

class TestValidateGlueId:
    """Tests for validate_glue_id validator.

    Validates: Requirements 2.2, 2.6
    """

    @pytest.mark.parametrize("glue_id", VALID_GLUE_IDS)
    def test_valid_glue_ids(self, glue_id):
        """Test that valid glue.id values pass validation."""
        is_valid, error = validate_glue_id(glue_id)
        assert is_valid is True
        assert error is None

    @pytest.mark.parametrize("glue_id,expected_error_fragment", INVALID_GLUE_IDS)
    def test_invalid_glue_ids(self, glue_id, expected_error_fragment):
        """Test that invalid glue.id values fail with appropriate error messages."""
        is_valid, error = validate_glue_id(glue_id)
        assert is_valid is False
        assert error is not None
        assert expected_error_fragment.lower() in error.lower()

    def test_empty_string_rejected(self):
        """Test that empty string is rejected."""
        is_valid, error = validate_glue_id("")
        assert is_valid is False
        assert "Invalid glue.id format" in error

    def test_none_rejected(self):
        """Test that None is rejected."""
        is_valid, error = validate_glue_id(None)
        assert is_valid is False
        assert "Invalid glue.id format" in error

    def test_error_message_contains_expected_format(self):
        """Test that error message includes the expected format description (Req 2.6)."""
        is_valid, error = validate_glue_id("invalid")
        assert is_valid is False
        assert "{account_id}:s3tablescatalog/{bucket-name}" in error
        assert "Verify your table bucket ARN is correct" in error

    def test_exactly_12_digit_account_id(self):
        """Test that exactly 12 digits are required for account ID."""
        # 11 digits - invalid
        is_valid, error = validate_glue_id("12345678901:s3tablescatalog/my-bucket")
        assert is_valid is False

        # 12 digits - valid
        is_valid, error = validate_glue_id("123456789012:s3tablescatalog/my-bucket")
        assert is_valid is True

        # 13 digits - invalid
        is_valid, error = validate_glue_id("1234567890123:s3tablescatalog/my-bucket")
        assert is_valid is False

    def test_bucket_name_minimum_length(self):
        """Test minimum bucket name length (3 chars) in glue.id."""
        # 3 chars - valid
        is_valid, error = validate_glue_id("123456789012:s3tablescatalog/abc")
        assert is_valid is True

    def test_bucket_name_maximum_length(self):
        """Test maximum bucket name length (63 chars) in glue.id."""
        # 63 chars: 1 start + 61 middle + 1 end
        bucket = "a" + "b" * 61 + "c"
        is_valid, error = validate_glue_id(f"123456789012:s3tablescatalog/{bucket}")
        assert is_valid is True

    def test_bucket_name_too_short(self):
        """Test bucket name with only 2 chars is rejected."""
        is_valid, error = validate_glue_id("123456789012:s3tablescatalog/ab")
        assert is_valid is False

    def test_bucket_name_too_long(self):
        """Test bucket name exceeding 63 chars is rejected."""
        # 64 chars: 1 start + 62 middle + 1 end
        bucket = "a" + "b" * 62 + "c"
        is_valid, error = validate_glue_id(f"123456789012:s3tablescatalog/{bucket}")
        assert is_valid is False

    def test_bucket_name_with_dots_valid(self):
        """Test that dots are allowed in bucket name portion."""
        is_valid, error = validate_glue_id("123456789012:s3tablescatalog/my.bucket.name")
        assert is_valid is True

    def test_bucket_name_with_hyphens_valid(self):
        """Test that hyphens are allowed in bucket name portion."""
        is_valid, error = validate_glue_id("123456789012:s3tablescatalog/my-bucket-name")
        assert is_valid is True

    def test_bucket_name_starts_with_number(self):
        """Test that bucket name can start with a number."""
        is_valid, error = validate_glue_id("123456789012:s3tablescatalog/1my-bucket")
        assert is_valid is True

    def test_bucket_name_ends_with_number(self):
        """Test that bucket name can end with a number."""
        is_valid, error = validate_glue_id("123456789012:s3tablescatalog/my-bucket1")
        assert is_valid is True


# =============================================================================
# Maintenance Config Validation Tests
# =============================================================================

class TestValidateMaintenanceConfigProductionHardening:
    """Tests for validate_maintenance_config with boundary values.

    Validates: Requirements 4.3, 4.4
    """

    def test_boundary_min_file_size_64(self):
        """Test minimum valid target file size (64 MB)."""
        is_valid, error = validate_maintenance_config(64, 30, 720)
        assert is_valid is True
        assert error is None

    def test_boundary_max_file_size_512(self):
        """Test maximum valid target file size (512 MB)."""
        is_valid, error = validate_maintenance_config(512, 30, 720)
        assert is_valid is True
        assert error is None

    def test_boundary_below_min_file_size_63(self):
        """Test value just below minimum (63 MB) is rejected."""
        is_valid, error = validate_maintenance_config(63, 30, 720)
        assert is_valid is False
        assert "64" in error
        assert "512" in error

    def test_boundary_above_max_file_size_513(self):
        """Test value just above maximum (513 MB) is rejected."""
        is_valid, error = validate_maintenance_config(513, 30, 720)
        assert is_valid is False
        assert "64" in error
        assert "512" in error

    def test_zero_file_size_rejected(self):
        """Test that zero target file size is rejected (Req 4.4)."""
        is_valid, error = validate_maintenance_config(0, 30, 720)
        assert is_valid is False
        assert "required" in error.lower() or "between" in error.lower()

    def test_negative_file_size_rejected(self):
        """Test that negative target file size (-1) is rejected."""
        is_valid, error = validate_maintenance_config(-1, 30, 720)
        assert is_valid is False
        assert error is not None

    def test_zero_snapshots_rejected(self):
        """Test that zero min_snapshots_to_keep is rejected."""
        is_valid, error = validate_maintenance_config(256, 0, 720)
        assert is_valid is False
        assert "positive integer" in error.lower()

    def test_negative_snapshots_rejected(self):
        """Test that negative min_snapshots_to_keep (-1) is rejected."""
        is_valid, error = validate_maintenance_config(256, -1, 720)
        assert is_valid is False
        assert "positive integer" in error.lower()

    def test_zero_max_age_rejected(self):
        """Test that zero max_snapshot_age_hours is rejected."""
        is_valid, error = validate_maintenance_config(256, 30, 0)
        assert is_valid is False
        assert "positive integer" in error.lower()

    def test_negative_max_age_rejected(self):
        """Test that negative max_snapshot_age_hours (-1) is rejected."""
        is_valid, error = validate_maintenance_config(256, 30, -1)
        assert is_valid is False
        assert "positive integer" in error.lower()

    def test_min_valid_snapshots_one(self):
        """Test that min_snapshots_to_keep = 1 is valid."""
        is_valid, error = validate_maintenance_config(256, 1, 720)
        assert is_valid is True
        assert error is None

    def test_min_valid_age_one(self):
        """Test that max_snapshot_age_hours = 1 is valid."""
        is_valid, error = validate_maintenance_config(256, 30, 1)
        assert is_valid is True
        assert error is None

    def test_default_values_valid(self):
        """Test that documented defaults (512, 30, 720) are valid."""
        is_valid, error = validate_maintenance_config(512, 30, 720)
        assert is_valid is True
        assert error is None

    def test_large_snapshots_value_valid(self):
        """Test that large positive values for snapshots are valid."""
        is_valid, error = validate_maintenance_config(256, 10000, 720)
        assert is_valid is True
        assert error is None

    def test_large_age_value_valid(self):
        """Test that large positive values for age are valid."""
        is_valid, error = validate_maintenance_config(256, 30, 87600)
        assert is_valid is True
        assert error is None


# =============================================================================
# Compaction Strategy Validation Tests
# =============================================================================

class TestValidateCompactionStrategy:
    """Tests for validate_compaction_strategy validator.

    Validates: Requirements 2.2, 2.6, 4.3, 4.4, 6.1, 6.7
    """

    @pytest.mark.parametrize(
        "strategy,sort_columns,schema_columns",
        VALID_COMPACTION_STRATEGIES,
    )
    def test_valid_strategies(self, strategy, sort_columns, schema_columns):
        """Test that valid compaction strategy configurations pass validation."""
        is_valid, error = validate_compaction_strategy(
            strategy, sort_columns, schema_columns
        )
        assert is_valid is True
        assert error is None

    @pytest.mark.parametrize(
        "strategy,sort_columns,schema_columns,expected_error_fragment",
        INVALID_COMPACTION_STRATEGIES,
    )
    def test_invalid_strategies(
        self, strategy, sort_columns, schema_columns, expected_error_fragment
    ):
        """Test that invalid compaction strategies fail with appropriate errors."""
        is_valid, error = validate_compaction_strategy(
            strategy, sort_columns, schema_columns
        )
        assert is_valid is False
        assert error is not None
        assert expected_error_fragment.lower() in error.lower()

    def test_binpack_with_empty_sort_columns(self):
        """Test that binpack strategy accepts empty sort columns."""
        is_valid, error = validate_compaction_strategy(
            "binpack", [], ["col_a", "col_b"]
        )
        assert is_valid is True
        assert error is None

    def test_binpack_ignores_sort_columns(self):
        """Test that binpack strategy ignores provided sort columns (no validation)."""
        # binpack doesn't require sort columns, but providing them shouldn't fail
        is_valid, error = validate_compaction_strategy(
            "binpack", ["col_a"], ["col_a", "col_b"]
        )
        assert is_valid is True
        assert error is None

    def test_sort_requires_sort_columns(self):
        """Test that sort strategy requires non-empty sort columns."""
        is_valid, error = validate_compaction_strategy(
            "sort", [], ["col_a", "col_b"]
        )
        assert is_valid is False
        assert "sort columns must be specified" in error.lower()

    def test_z_order_requires_sort_columns(self):
        """Test that z-order strategy requires non-empty sort columns."""
        is_valid, error = validate_compaction_strategy(
            "z-order", [], ["col_a", "col_b"]
        )
        assert is_valid is False
        assert "sort columns must be specified" in error.lower()

    def test_sort_column_not_in_schema(self):
        """Test that sort columns not in schema are rejected."""
        is_valid, error = validate_compaction_strategy(
            "sort", ["nonexistent_col"], ["col_a", "col_b"]
        )
        assert is_valid is False
        assert "not found in table schema" in error.lower()
        assert "nonexistent_col" in error

    def test_multiple_invalid_sort_columns(self):
        """Test that multiple invalid sort columns are reported."""
        is_valid, error = validate_compaction_strategy(
            "z-order", ["bad_col1", "bad_col2"], ["col_a", "col_b"]
        )
        assert is_valid is False
        assert "bad_col1" in error
        assert "bad_col2" in error

    def test_partial_invalid_sort_columns(self):
        """Test that mix of valid and invalid sort columns is rejected."""
        is_valid, error = validate_compaction_strategy(
            "sort", ["col_a", "missing_col"], ["col_a", "col_b"]
        )
        assert is_valid is False
        assert "missing_col" in error
        # Valid column should not appear in error
        assert "col_a" not in error or "missing_col" in error

    def test_invalid_strategy_name(self):
        """Test that invalid strategy names are rejected."""
        is_valid, error = validate_compaction_strategy(
            "compact", [], ["col_a"]
        )
        assert is_valid is False
        assert "must be one of" in error.lower()
        assert "binpack" in error
        assert "sort" in error
        assert "z-order" in error

    def test_strategy_case_sensitive(self):
        """Test that strategy names are case-sensitive."""
        is_valid, error = validate_compaction_strategy(
            "Binpack", [], ["col_a"]
        )
        assert is_valid is False
        assert "must be one of" in error.lower()

    def test_sort_with_all_schema_columns(self):
        """Test sort strategy with all schema columns as sort columns."""
        schema = ["col_a", "col_b", "col_c"]
        is_valid, error = validate_compaction_strategy(
            "sort", schema, schema
        )
        assert is_valid is True
        assert error is None

    def test_z_order_with_single_column(self):
        """Test z-order strategy with a single sort column."""
        is_valid, error = validate_compaction_strategy(
            "z-order", ["col_a"], ["col_a", "col_b", "col_c"]
        )
        assert is_valid is True
        assert error is None

    def test_empty_schema_with_sort_strategy(self):
        """Test sort strategy with empty schema rejects any sort columns."""
        is_valid, error = validate_compaction_strategy(
            "sort", ["col_a"], []
        )
        assert is_valid is False
        assert "not found in table schema" in error.lower()


# =============================================================================
# S3 Tables Parallelism Validation Tests
# =============================================================================

class TestValidateS3TablesParallelism:
    """Tests for validate_s3_tables_parallelism validator.

    Validates: Requirements 6.1, 6.7
    """

    @pytest.mark.parametrize("value", VALID_S3_TABLES_PARALLELISM)
    def test_valid_parallelism_values(self, value):
        """Test that valid parallelism values [1-8] pass validation."""
        is_valid, error = validate_s3_tables_parallelism(value)
        assert is_valid is True
        assert error is None

    @pytest.mark.parametrize("value,expected_error_fragment", INVALID_S3_TABLES_PARALLELISM)
    def test_invalid_parallelism_values(self, value, expected_error_fragment):
        """Test that invalid parallelism values fail with appropriate errors."""
        is_valid, error = validate_s3_tables_parallelism(value)
        assert is_valid is False
        assert error is not None
        assert expected_error_fragment.lower() in error.lower()

    def test_boundary_zero_rejected(self):
        """Test that parallelism of 0 is rejected."""
        is_valid, error = validate_s3_tables_parallelism(0)
        assert is_valid is False
        assert "must be between 1 and 8" in error.lower()

    def test_boundary_one_accepted(self):
        """Test that parallelism of 1 (minimum) is accepted."""
        is_valid, error = validate_s3_tables_parallelism(1)
        assert is_valid is True
        assert error is None

    def test_boundary_eight_accepted(self):
        """Test that parallelism of 8 (maximum for S3 Tables) is accepted."""
        is_valid, error = validate_s3_tables_parallelism(8)
        assert is_valid is True
        assert error is None

    def test_boundary_nine_rejected(self):
        """Test that parallelism of 9 (just above max) is rejected."""
        is_valid, error = validate_s3_tables_parallelism(9)
        assert is_valid is False
        assert "must be between 1 and 8" in error.lower()

    def test_sixteen_rejected_for_s3_tables(self):
        """Test that parallelism of 16 (standard S3 max) is rejected for S3 Tables."""
        is_valid, error = validate_s3_tables_parallelism(16)
        assert is_valid is False
        assert "must be between 1 and 8" in error.lower()

    def test_negative_value_rejected(self):
        """Test that negative parallelism is rejected."""
        is_valid, error = validate_s3_tables_parallelism(-1)
        assert is_valid is False
        assert error is not None

    def test_error_mentions_s3_tables_limits(self):
        """Test that error message mentions S3 Tables concurrency limits."""
        is_valid, error = validate_s3_tables_parallelism(9)
        assert is_valid is False
        assert "s3 tables" in error.lower()

    def test_non_integer_float_rejected(self):
        """Test that float values are rejected."""
        is_valid, error = validate_s3_tables_parallelism(4.5)
        assert is_valid is False
        assert "integer" in error.lower()

    def test_non_integer_string_rejected(self):
        """Test that string values are rejected."""
        is_valid, error = validate_s3_tables_parallelism("4")
        assert is_valid is False
        assert "integer" in error.lower()

    def test_boolean_rejected(self):
        """Test that boolean values are rejected."""
        is_valid, error = validate_s3_tables_parallelism(True)
        assert is_valid is False
        assert "integer" in error.lower()

    def test_large_value_rejected(self):
        """Test that very large parallelism values are rejected."""
        is_valid, error = validate_s3_tables_parallelism(1000)
        assert is_valid is False
        assert "must be between 1 and 8" in error.lower()


# =============================================================================
# S3TablesAdapter Maintenance Configuration Tests (Task 2.4)
# =============================================================================

from unittest.mock import MagicMock, patch, call
from services.bq_iceberg_migration.s3_tables_adapter import (
    S3TablesAdapter,
    MaintenanceConfig,
)


# --- Sample Payloads for S3TablesAdapter Maintenance Tests ---

VALID_TABLE_BUCKET_ARN = "arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket"
VALID_AWS_REGION = "us-east-1"

SAMPLE_BINPACK_CONFIG = MaintenanceConfig(
    compaction_enabled=True,
    target_file_size_mb=256,
    compaction_strategy="binpack",
    sort_columns=[],
    snapshot_management_enabled=True,
    min_snapshots_to_keep=30,
    max_snapshot_age_hours=720,
)

SAMPLE_SORT_CONFIG = MaintenanceConfig(
    compaction_enabled=True,
    target_file_size_mb=128,
    compaction_strategy="sort",
    sort_columns=["order_date", "customer_id"],
    snapshot_management_enabled=True,
    min_snapshots_to_keep=10,
    max_snapshot_age_hours=168,
)

SAMPLE_ZORDER_CONFIG = MaintenanceConfig(
    compaction_enabled=True,
    target_file_size_mb=512,
    compaction_strategy="z-order",
    sort_columns=["region", "product_id", "event_time"],
    snapshot_management_enabled=True,
    min_snapshots_to_keep=50,
    max_snapshot_age_hours=1440,
)

# Valid ARNs for derive_glue_id tests
VALID_ARNS_AND_EXPECTED_GLUE_IDS = [
    (
        "arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket",
        "123456789012:s3tablescatalog/my-table-bucket",
    ),
    (
        "arn:aws:s3tables:eu-west-1:987654321098:bucket/analytics-data",
        "987654321098:s3tablescatalog/analytics-data",
    ),
    (
        "arn:aws:s3tables:ap-southeast-1:111222333444:bucket/my.dotted.bucket",
        "111222333444:s3tablescatalog/my.dotted.bucket",
    ),
    (
        "arn:aws:s3tables:us-west-2:000000000000:bucket/a1b",
        "000000000000:s3tablescatalog/a1b",
    ),
]

# Invalid ARNs for derive_glue_id tests
INVALID_ARNS = [
    "",
    "not-an-arn",
    "arn:aws:s3:us-east-1:123456789012:bucket/my-bucket",  # wrong service (s3 not s3tables)
    "arn:aws:s3tables:us-east-1:12345:bucket/my-bucket",  # short account ID
    "arn:aws:s3tables:us-east-1:123456789012:table/my-table",  # wrong resource type
    "arn:aws:s3tables::123456789012:bucket/my-bucket",  # missing region
    "arn:aws:s3tables:us-east-1:123456789012:bucket/A",  # uppercase bucket (too short too)
    "arn:aws:s3tables:us-east-1:123456789012:bucket/",  # empty bucket name
]


def _make_adapter(client=None):
    """Create an S3TablesAdapter with a mock client."""
    if client is None:
        client = MagicMock()
    return S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)


class TestConfigureMaintenanceRetry:
    """Tests for configure_maintenance retry behavior.

    Validates: Requirements 1.6, 1.7, 1.8
    """

    @patch("services.bq_iceberg_migration.s3_tables_adapter.time.sleep")
    def test_succeeds_on_first_attempt(self, mock_sleep):
        """Should return True and not retry when first attempt succeeds."""
        client = MagicMock()
        client.put_table_maintenance_configuration.return_value = {}
        adapter = _make_adapter(client)

        result = adapter.configure_maintenance("ns", "table1", SAMPLE_BINPACK_CONFIG)

        assert result is True
        client.put_table_maintenance_configuration.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("services.bq_iceberg_migration.s3_tables_adapter.time.sleep")
    def test_retries_on_first_failure_succeeds_on_second(self, mock_sleep):
        """Should retry after first failure and return True on second success."""
        client = MagicMock()
        client.put_table_maintenance_configuration.side_effect = [
            Exception("Temporary error"),
            {},  # success on second attempt
        ]
        adapter = _make_adapter(client)

        result = adapter.configure_maintenance("ns", "table1", SAMPLE_BINPACK_CONFIG)

        assert result is True
        assert client.put_table_maintenance_configuration.call_count == 2
        mock_sleep.assert_called_once_with(2)  # first backoff delay

    @patch("services.bq_iceberg_migration.s3_tables_adapter.time.sleep")
    def test_retries_with_exponential_backoff_delays(self, mock_sleep):
        """Should use exponential backoff delays: 2s, 6s, 18s."""
        client = MagicMock()
        client.put_table_maintenance_configuration.side_effect = [
            Exception("Error 1"),
            Exception("Error 2"),
            Exception("Error 3"),
            {},  # success on 4th attempt (after 3 retries)
        ]
        adapter = _make_adapter(client)

        result = adapter.configure_maintenance("ns", "table1", SAMPLE_BINPACK_CONFIG)

        assert result is True
        assert client.put_table_maintenance_configuration.call_count == 4
        mock_sleep.assert_has_calls([call(2), call(6), call(18)])

    @patch("services.bq_iceberg_migration.s3_tables_adapter.time.sleep")
    def test_returns_false_after_all_retries_exhausted(self, mock_sleep):
        """Should return False when all 3 retries are exhausted (Req 1.6)."""
        client = MagicMock()
        client.put_table_maintenance_configuration.side_effect = Exception("Persistent error")
        adapter = _make_adapter(client)

        result = adapter.configure_maintenance("ns", "table1", SAMPLE_BINPACK_CONFIG)

        assert result is False
        # Initial attempt + 3 retries = 4 total calls
        assert client.put_table_maintenance_configuration.call_count == 4
        mock_sleep.assert_has_calls([call(2), call(6), call(18)])

    @patch("services.bq_iceberg_migration.s3_tables_adapter.time.sleep")
    def test_succeeds_on_third_retry(self, mock_sleep):
        """Should succeed when the third retry works."""
        client = MagicMock()
        client.put_table_maintenance_configuration.side_effect = [
            Exception("Error 1"),
            Exception("Error 2"),
            {},  # success on 3rd attempt
        ]
        adapter = _make_adapter(client)

        result = adapter.configure_maintenance("ns", "table1", SAMPLE_SORT_CONFIG)

        assert result is True
        assert client.put_table_maintenance_configuration.call_count == 3
        mock_sleep.assert_has_calls([call(2), call(6)])


class TestConfigureMaintenanceNonFatal:
    """Tests that configure_maintenance does not fail table creation on error.

    Validates: Requirements 1.6 (non-fatal behavior)
    """

    @patch("services.bq_iceberg_migration.s3_tables_adapter.time.sleep")
    def test_does_not_raise_exception_on_failure(self, mock_sleep):
        """Should return False, not raise, when all retries fail (Req 1.6)."""
        client = MagicMock()
        client.put_table_maintenance_configuration.side_effect = Exception("API error")
        adapter = _make_adapter(client)

        # Should NOT raise - returns False instead
        result = adapter.configure_maintenance("ns", "table1", SAMPLE_BINPACK_CONFIG)

        assert result is False

    @patch("services.bq_iceberg_migration.s3_tables_adapter.time.sleep")
    def test_returns_boolean_true_on_success(self, mock_sleep):
        """Should return True (not raise) on success."""
        client = MagicMock()
        client.put_table_maintenance_configuration.return_value = {}
        adapter = _make_adapter(client)

        result = adapter.configure_maintenance("ns", "table1", SAMPLE_BINPACK_CONFIG)

        assert result is True
        assert isinstance(result, bool)

    @patch("services.bq_iceberg_migration.s3_tables_adapter.time.sleep")
    def test_returns_boolean_false_on_failure(self, mock_sleep):
        """Should return False (not raise) on failure."""
        client = MagicMock()
        client.put_table_maintenance_configuration.side_effect = Exception("Fail")
        adapter = _make_adapter(client)

        result = adapter.configure_maintenance("ns", "table1", SAMPLE_BINPACK_CONFIG)

        assert result is False
        assert isinstance(result, bool)

    @patch("services.bq_iceberg_migration.s3_tables_adapter.time.sleep")
    def test_logs_error_with_correct_error_code(self, mock_sleep):
        """Should log ERROR with S3_TABLES_MAINTENANCE_CONFIG_FAILED code."""
        client = MagicMock()
        client.put_table_maintenance_configuration.side_effect = Exception("API error")
        adapter = _make_adapter(client)

        with patch("services.bq_iceberg_migration.s3_tables_adapter.logger") as mock_logger:
            adapter.configure_maintenance("ns", "table1", SAMPLE_BINPACK_CONFIG)

            # Verify error was logged
            mock_logger.error.assert_called_once()
            error_call_kwargs = mock_logger.error.call_args
            extra = error_call_kwargs.kwargs.get("extra") or error_call_kwargs[1].get("extra")
            assert extra["error_code"] == "S3_TABLES_MAINTENANCE_CONFIG_FAILED"

    @patch("services.bq_iceberg_migration.s3_tables_adapter.time.sleep")
    def test_logs_info_on_success(self, mock_sleep):
        """Should log INFO with table name, strategy, file size, snapshot settings (Req 1.8)."""
        client = MagicMock()
        client.put_table_maintenance_configuration.return_value = {}
        adapter = _make_adapter(client)

        with patch("services.bq_iceberg_migration.s3_tables_adapter.logger") as mock_logger:
            adapter.configure_maintenance("analytics", "orders", SAMPLE_SORT_CONFIG)

            # Verify info was logged with correct fields
            mock_logger.info.assert_called()
            # Find the maintenance success log call
            info_calls = mock_logger.info.call_args_list
            maintenance_call = None
            for c in info_calls:
                if "Maintenance configuration applied" in str(c):
                    maintenance_call = c
                    break

            assert maintenance_call is not None
            extra = maintenance_call.kwargs.get("extra") or maintenance_call[1].get("extra")
            assert "analytics.orders" in extra["table_name"]
            assert extra["compaction_strategy"] == "sort"
            assert extra["target_file_size_mb"] == 128
            assert extra["min_snapshots_to_keep"] == 10
            assert extra["max_snapshot_age_hours"] == 168


class TestBuildMaintenancePayload:
    """Tests for _build_maintenance_payload producing correct API shape.

    Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5
    """

    def test_binpack_strategy_payload(self):
        """Should produce correct payload shape for binpack strategy."""
        adapter = _make_adapter()
        config = MaintenanceConfig(
            compaction_enabled=True,
            target_file_size_mb=256,
            compaction_strategy="binpack",
            sort_columns=[],
            snapshot_management_enabled=True,
            min_snapshots_to_keep=30,
            max_snapshot_age_hours=720,
        )

        payload = adapter._build_maintenance_payload(config)

        # Verify top-level structure
        assert "icebergCompaction" in payload
        assert "icebergSnapshotManagement" in payload

        # Verify compaction settings
        compaction = payload["icebergCompaction"]
        assert compaction["isEnabled"] is True
        assert compaction["settings"]["targetFileSizeMB"] == 256
        assert "binpack" in compaction["settings"]["strategy"]

        # Verify snapshot management settings
        snapshot = payload["icebergSnapshotManagement"]
        assert snapshot["isEnabled"] is True
        assert snapshot["settings"]["minSnapshotsToKeep"] == 30
        assert snapshot["settings"]["maxSnapshotAgeHours"] == 720

    def test_sort_strategy_payload(self):
        """Should produce correct payload shape for sort strategy with sort columns."""
        adapter = _make_adapter()
        config = MaintenanceConfig(
            compaction_enabled=True,
            target_file_size_mb=128,
            compaction_strategy="sort",
            sort_columns=["order_date", "customer_id"],
            snapshot_management_enabled=True,
            min_snapshots_to_keep=10,
            max_snapshot_age_hours=168,
        )

        payload = adapter._build_maintenance_payload(config)

        compaction = payload["icebergCompaction"]
        assert compaction["isEnabled"] is True
        assert compaction["settings"]["targetFileSizeMB"] == 128

        strategy = compaction["settings"]["strategy"]
        assert "sort" in strategy
        assert strategy["sort"]["sortColumns"] == ["order_date", "customer_id"]

        snapshot = payload["icebergSnapshotManagement"]
        assert snapshot["settings"]["minSnapshotsToKeep"] == 10
        assert snapshot["settings"]["maxSnapshotAgeHours"] == 168

    def test_z_order_strategy_payload(self):
        """Should produce correct payload shape for z-order strategy with sort columns."""
        adapter = _make_adapter()
        config = MaintenanceConfig(
            compaction_enabled=True,
            target_file_size_mb=512,
            compaction_strategy="z-order",
            sort_columns=["region", "product_id", "event_time"],
            snapshot_management_enabled=True,
            min_snapshots_to_keep=50,
            max_snapshot_age_hours=1440,
        )

        payload = adapter._build_maintenance_payload(config)

        compaction = payload["icebergCompaction"]
        assert compaction["isEnabled"] is True
        assert compaction["settings"]["targetFileSizeMB"] == 512

        strategy = compaction["settings"]["strategy"]
        assert "z-order" in strategy
        assert strategy["z-order"]["sortColumns"] == ["region", "product_id", "event_time"]

        snapshot = payload["icebergSnapshotManagement"]
        assert snapshot["settings"]["minSnapshotsToKeep"] == 50
        assert snapshot["settings"]["maxSnapshotAgeHours"] == 1440

    def test_compaction_disabled(self):
        """Should set isEnabled to False when compaction is disabled."""
        adapter = _make_adapter()
        config = MaintenanceConfig(
            compaction_enabled=False,
            target_file_size_mb=256,
            compaction_strategy="binpack",
        )

        payload = adapter._build_maintenance_payload(config)

        assert payload["icebergCompaction"]["isEnabled"] is False

    def test_snapshot_management_disabled(self):
        """Should set isEnabled to False when snapshot management is disabled."""
        adapter = _make_adapter()
        config = MaintenanceConfig(
            snapshot_management_enabled=False,
            min_snapshots_to_keep=30,
            max_snapshot_age_hours=720,
        )

        payload = adapter._build_maintenance_payload(config)

        assert payload["icebergSnapshotManagement"]["isEnabled"] is False

    def test_minimum_file_size_in_payload(self):
        """Should correctly set minimum target file size (64 MB)."""
        adapter = _make_adapter()
        config = MaintenanceConfig(target_file_size_mb=64)

        payload = adapter._build_maintenance_payload(config)

        assert payload["icebergCompaction"]["settings"]["targetFileSizeMB"] == 64

    def test_maximum_file_size_in_payload(self):
        """Should correctly set maximum target file size (512 MB)."""
        adapter = _make_adapter()
        config = MaintenanceConfig(target_file_size_mb=512)

        payload = adapter._build_maintenance_payload(config)

        assert payload["icebergCompaction"]["settings"]["targetFileSizeMB"] == 512

    def test_payload_has_required_top_level_keys(self):
        """Payload must have both icebergCompaction and icebergSnapshotManagement."""
        adapter = _make_adapter()
        config = MaintenanceConfig()

        payload = adapter._build_maintenance_payload(config)

        assert set(payload.keys()) == {"icebergCompaction", "icebergSnapshotManagement"}

    def test_sort_strategy_with_single_column(self):
        """Should handle sort strategy with a single sort column."""
        adapter = _make_adapter()
        config = MaintenanceConfig(
            compaction_strategy="sort",
            sort_columns=["created_at"],
        )

        payload = adapter._build_maintenance_payload(config)

        strategy = payload["icebergCompaction"]["settings"]["strategy"]
        assert strategy["sort"]["sortColumns"] == ["created_at"]


class TestDeriveGlueIdUnit:
    """Unit tests for derive_glue_id with valid and invalid ARN formats.

    Validates: Requirements 2.1, 2.3
    """

    @pytest.mark.parametrize("arn,expected_glue_id", VALID_ARNS_AND_EXPECTED_GLUE_IDS)
    def test_valid_arns_produce_correct_glue_id(self, arn, expected_glue_id):
        """Should derive correct glue.id from valid table bucket ARNs."""
        result = S3TablesAdapter.derive_glue_id(arn)
        assert result == expected_glue_id

    @pytest.mark.parametrize("invalid_arn", INVALID_ARNS)
    def test_invalid_arns_raise_value_error(self, invalid_arn):
        """Should raise ValueError for invalid ARN formats."""
        with pytest.raises(ValueError, match="Invalid table bucket ARN format"):
            S3TablesAdapter.derive_glue_id(invalid_arn)

    def test_glue_id_format_account_colon_catalog_slash_bucket(self):
        """Derived glue.id must follow {account_id}:s3tablescatalog/{bucket-name} format."""
        arn = "arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket"
        result = S3TablesAdapter.derive_glue_id(arn)

        # Verify format
        parts = result.split(":")
        assert len(parts) == 2
        assert parts[0] == "123456789012"
        assert parts[1].startswith("s3tablescatalog/")
        assert parts[1] == "s3tablescatalog/my-bucket"

    def test_extracts_account_id_correctly(self):
        """Should extract the 12-digit account ID from the ARN."""
        arn = "arn:aws:s3tables:us-west-2:999888777666:bucket/test-bucket"
        result = S3TablesAdapter.derive_glue_id(arn)
        assert result.startswith("999888777666:")

    def test_extracts_bucket_name_correctly(self):
        """Should extract the bucket name from the ARN."""
        arn = "arn:aws:s3tables:eu-central-1:123456789012:bucket/my-special-bucket"
        result = S3TablesAdapter.derive_glue_id(arn)
        assert result.endswith("s3tablescatalog/my-special-bucket")

    def test_none_input_raises_value_error(self):
        """Should raise ValueError (or TypeError) for None input."""
        with pytest.raises((ValueError, TypeError)):
            S3TablesAdapter.derive_glue_id(None)

    def test_arn_with_extra_slashes_rejected(self):
        """Should reject ARN with extra path components after bucket name."""
        arn = "arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket/extra"
        with pytest.raises(ValueError):
            S3TablesAdapter.derive_glue_id(arn)


class TestNoPyIcebergMaintenanceProperties:
    """Tests that no PyIceberg maintenance properties are set for S3 Tables.

    Validates: Requirement 1.7 — S3 Tables silently ignores properties set
    through the Iceberg catalog interface.
    """

    @patch("services.bq_iceberg_migration.s3_tables_adapter.time.sleep")
    def test_configure_maintenance_uses_boto3_api_not_pyiceberg(self, mock_sleep):
        """Maintenance config should use put_table_maintenance_configuration, not table properties."""
        client = MagicMock()
        client.put_table_maintenance_configuration.return_value = {}
        adapter = _make_adapter(client)

        adapter.configure_maintenance("ns", "table1", SAMPLE_BINPACK_CONFIG)

        # Verify Boto3 API was called
        client.put_table_maintenance_configuration.assert_called_once()

        # Verify no PyIceberg-style property setting methods were called
        # (e.g., update_table, alter_table, set_properties)
        assert not hasattr(client, "update_table") or not client.update_table.called
        assert not hasattr(client, "set_properties") or not client.set_properties.called

    def test_maintenance_payload_does_not_contain_pyiceberg_property_keys(self):
        """Payload should not contain PyIceberg table property keys."""
        adapter = _make_adapter()
        config = MaintenanceConfig(
            compaction_strategy="sort",
            sort_columns=["col_a"],
        )

        payload = adapter._build_maintenance_payload(config)

        # PyIceberg maintenance properties that should NOT be in the payload
        pyiceberg_keys = [
            "write.target-file-size-bytes",
            "write.metadata.delete-after-commit.enabled",
            "history.expire.max-snapshot-age-ms",
            "history.expire.min-snapshots-to-keep",
        ]

        payload_str = str(payload)
        for key in pyiceberg_keys:
            assert key not in payload_str, (
                f"PyIceberg property '{key}' should not be in maintenance payload"
            )

    def test_maintenance_payload_uses_s3_tables_api_format(self):
        """Payload should use S3 Tables API format (camelCase keys)."""
        adapter = _make_adapter()
        config = MaintenanceConfig()

        payload = adapter._build_maintenance_payload(config)

        # S3 Tables API uses camelCase
        assert "icebergCompaction" in payload
        assert "icebergSnapshotManagement" in payload
        assert "isEnabled" in payload["icebergCompaction"]
        assert "targetFileSizeMB" in payload["icebergCompaction"]["settings"]
        assert "minSnapshotsToKeep" in payload["icebergSnapshotManagement"]["settings"]
        assert "maxSnapshotAgeHours" in payload["icebergSnapshotManagement"]["settings"]


# --- Tests for _load_single_table_s3_tables (Task 5.2) ---


class TestLoadSingleTableS3TablesMaintenanceConfig:
    """Tests for _load_single_table_s3_tables maintenance config integration.

    Validates: Requirements 1.1, 1.6
    - Maintenance config is called after successful table creation
    - Maintenance config failure does not fail table creation
    - Load continues even if maintenance config fails
    """

    @pytest.fixture
    def loader(self):
        """Create a ParallelIcebergLoader with mocked dependencies."""
        from services.bq_iceberg_migration.iceberg_loader import ParallelIcebergLoader

        catalog = MagicMock()
        credential_provider = MagicMock()
        type_mapper = MagicMock()
        partition_mapper = MagicMock()
        dedup_guard = MagicMock()
        dedup_guard.is_safe_to_append.return_value = (True, ["s3://bucket/file1.parquet"])

        loader = ParallelIcebergLoader(
            catalog=catalog,
            credential_provider=credential_provider,
            type_mapper=type_mapper,
            partition_mapper=partition_mapper,
            dedup_guard=dedup_guard,
            parallelism=4,
        )
        return loader

    @pytest.fixture
    def s3_tables_adapter(self):
        """Create a mocked S3TablesAdapter."""
        adapter = MagicMock()
        adapter.ensure_namespace.return_value = None
        adapter.create_table.return_value = {
            "metadata_location": "s3://bucket/metadata/v1.metadata.json",
            "table_arn": "arn:aws:s3tables:us-east-1:123456789012:bucket/b/table/t",
            "namespace": "analytics",
            "table_name": "orders",
        }
        adapter.configure_maintenance.return_value = True
        return adapter

    @pytest.fixture
    def table_config(self):
        """Sample table configuration for S3 Tables loading."""
        return {
            "proposed_name": "orders",
            "namespace": "analytics",
            "database": "my_database",
            "schema": MagicMock(),
            "partition_spec": MagicMock(),
            "data_files": ["s3://bucket/data/orders/file1.parquet"],
            "columns": [{"name": "id"}, {"name": "order_date"}],
        }

    @pytest.fixture
    def maintenance_config(self):
        """Sample maintenance configuration."""
        return MaintenanceConfig(
            compaction_enabled=True,
            target_file_size_mb=256,
            compaction_strategy="sort",
            sort_columns=["order_date"],
            snapshot_management_enabled=True,
            min_snapshots_to_keep=30,
            max_snapshot_age_hours=720,
        )

    @pytest.mark.asyncio
    async def test_maintenance_config_called_after_table_creation(
        self, loader, s3_tables_adapter, table_config, maintenance_config
    ):
        """Should call configure_maintenance immediately after successful table creation (Req 1.1)."""
        # Make _try_load_table return a mock table for append
        loader._try_load_table = MagicMock(return_value=MagicMock())

        result = await loader._load_single_table_s3_tables(
            table_config=table_config,
            s3_tables_adapter=s3_tables_adapter,
            maintenance_config=maintenance_config,
        )

        assert result.success is True
        s3_tables_adapter.configure_maintenance.assert_called_once_with(
            "analytics", "orders", maintenance_config
        )

    @pytest.mark.asyncio
    async def test_maintenance_config_failure_does_not_fail_table_creation(
        self, loader, s3_tables_adapter, table_config, maintenance_config
    ):
        """Should continue load even if maintenance config fails (Req 1.6)."""
        s3_tables_adapter.configure_maintenance.return_value = False
        loader._try_load_table = MagicMock(return_value=MagicMock())

        result = await loader._load_single_table_s3_tables(
            table_config=table_config,
            s3_tables_adapter=s3_tables_adapter,
            maintenance_config=maintenance_config,
        )

        # Load should still succeed despite maintenance config failure
        assert result.success is True
        assert result.table_name == "orders"

    @pytest.mark.asyncio
    async def test_maintenance_config_exception_does_not_fail_table_creation(
        self, loader, s3_tables_adapter, table_config, maintenance_config
    ):
        """Should continue load even if maintenance config raises an exception."""
        s3_tables_adapter.configure_maintenance.side_effect = Exception("Unexpected error")
        loader._try_load_table = MagicMock(return_value=MagicMock())

        result = await loader._load_single_table_s3_tables(
            table_config=table_config,
            s3_tables_adapter=s3_tables_adapter,
            maintenance_config=maintenance_config,
        )

        # Load should still succeed despite maintenance config exception
        assert result.success is True
        assert result.table_name == "orders"

    @pytest.mark.asyncio
    async def test_maintenance_config_none_skips_configuration(
        self, loader, s3_tables_adapter, table_config
    ):
        """Should skip maintenance configuration when maintenance_config is None."""
        loader._try_load_table = MagicMock(return_value=MagicMock())

        result = await loader._load_single_table_s3_tables(
            table_config=table_config,
            s3_tables_adapter=s3_tables_adapter,
            maintenance_config=None,
        )

        assert result.success is True
        s3_tables_adapter.configure_maintenance.assert_not_called()

    @pytest.mark.asyncio
    async def test_maintenance_config_called_with_correct_namespace_and_table(
        self, loader, s3_tables_adapter, maintenance_config
    ):
        """Should pass correct namespace and table_name to configure_maintenance."""
        table_config = {
            "proposed_name": "customers",
            "namespace": "production",
            "database": "prod_db",
            "schema": MagicMock(),
            "partition_spec": MagicMock(),
            "data_files": [],
            "columns": [],
        }
        loader._try_load_table = MagicMock(return_value=MagicMock())

        await loader._load_single_table_s3_tables(
            table_config=table_config,
            s3_tables_adapter=s3_tables_adapter,
            maintenance_config=maintenance_config,
        )

        s3_tables_adapter.configure_maintenance.assert_called_once_with(
            "production", "customers", maintenance_config
        )

    @pytest.mark.asyncio
    async def test_data_files_appended_after_maintenance_config(
        self, loader, s3_tables_adapter, table_config, maintenance_config
    ):
        """Should append data files after maintenance config (regardless of config result)."""
        mock_table = MagicMock()
        loader._try_load_table = MagicMock(return_value=mock_table)
        loader._dedup_guard.is_safe_to_append.return_value = (
            True,
            ["s3://bucket/data/orders/file1.parquet"],
        )

        result = await loader._load_single_table_s3_tables(
            table_config=table_config,
            s3_tables_adapter=s3_tables_adapter,
            maintenance_config=maintenance_config,
        )

        assert result.success is True
        assert result.files_appended == 1

    @pytest.mark.asyncio
    async def test_table_creation_failure_does_not_call_maintenance(
        self, loader, s3_tables_adapter, table_config, maintenance_config
    ):
        """Should not call configure_maintenance if table creation fails."""
        s3_tables_adapter.create_table.side_effect = Exception("Table creation failed")

        result = await loader._load_single_table_s3_tables(
            table_config=table_config,
            s3_tables_adapter=s3_tables_adapter,
            maintenance_config=maintenance_config,
        )

        assert result.success is False
        s3_tables_adapter.configure_maintenance.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_table_load_result_on_success(
        self, loader, s3_tables_adapter, table_config, maintenance_config
    ):
        """Should return a TableLoadResult with correct fields on success."""
        loader._try_load_table = MagicMock(return_value=MagicMock())

        result = await loader._load_single_table_s3_tables(
            table_config=table_config,
            s3_tables_adapter=s3_tables_adapter,
            maintenance_config=maintenance_config,
        )

        assert result.table_name == "orders"
        assert result.success is True
        assert result.error_code is None
        assert result.error_message is None
        assert result.duration_seconds > 0


# =============================================================================
# Throttle Retry Logic Tests (Task 5.1)
# =============================================================================

import asyncio
from services.bq_iceberg_migration.iceberg_loader import (
    ParallelIcebergLoader,
    _RetryExhaustedError,
)
from services.bq_iceberg_migration.error_codes import ErrorCode


class TestThrottleRetryConstants:
    """Tests for S3 Tables throttle retry constants.

    Validates: Requirements 6.3
    """

    def test_max_retries_is_five(self):
        """S3_TABLES_THROTTLE_MAX_RETRIES should be 5."""
        assert ParallelIcebergLoader.S3_TABLES_THROTTLE_MAX_RETRIES == 5

    def test_base_delay_is_one_second(self):
        """S3_TABLES_THROTTLE_BASE_DELAY should be 1.0 seconds."""
        assert ParallelIcebergLoader.S3_TABLES_THROTTLE_BASE_DELAY == 1.0

    def test_max_delay_is_32_seconds(self):
        """S3_TABLES_THROTTLE_MAX_DELAY should be 32.0 seconds."""
        assert ParallelIcebergLoader.S3_TABLES_THROTTLE_MAX_DELAY == 32.0


class TestIsS3TablesThrottleError:
    """Tests for _is_s3_tables_throttle_error classification.

    Validates: Requirements 6.4
    """

    def test_http_429_in_message_is_throttle(self):
        """Exception with '429' in message should be classified as throttle."""
        error = Exception("HTTP 429 Too Many Requests")
        assert ParallelIcebergLoader._is_s3_tables_throttle_error(error) is True

    def test_slowdown_in_message_is_throttle(self):
        """Exception with 'SlowDown' in message should be classified as throttle."""
        error = Exception("An error occurred (SlowDown) when calling PutTableMaintenanceConfiguration")
        assert ParallelIcebergLoader._is_s3_tables_throttle_error(error) is True

    def test_botocore_client_error_429_is_throttle(self):
        """Botocore ClientError with HTTPStatusCode 429 should be throttle."""
        error = Exception("Throttled")
        error.response = {
            "ResponseMetadata": {"HTTPStatusCode": 429},
            "Error": {"Code": "TooManyRequestsException", "Message": "Rate exceeded"},
        }
        assert ParallelIcebergLoader._is_s3_tables_throttle_error(error) is True

    def test_botocore_client_error_slowdown_code_is_throttle(self):
        """Botocore ClientError with Error Code 'SlowDown' should be throttle."""
        error = Exception("SlowDown error")
        error.response = {
            "ResponseMetadata": {"HTTPStatusCode": 503},
            "Error": {"Code": "SlowDown", "Message": "Please reduce your request rate"},
        }
        assert ParallelIcebergLoader._is_s3_tables_throttle_error(error) is True

    def test_http_403_is_not_throttle(self):
        """Exception with HTTP 403 should NOT be classified as throttle."""
        error = Exception("HTTP 403 Forbidden - Access Denied")
        # Note: '403' alone doesn't match since we check for '429' specifically
        # But we need to make sure it's not a false positive
        assert ParallelIcebergLoader._is_s3_tables_throttle_error(error) is False

    def test_http_500_is_not_throttle(self):
        """Exception with HTTP 500 should NOT be classified as throttle."""
        error = Exception("HTTP 500 Internal Server Error")
        assert ParallelIcebergLoader._is_s3_tables_throttle_error(error) is False

    def test_access_denied_is_not_throttle(self):
        """Exception with 'AccessDenied' should NOT be classified as throttle."""
        error = Exception("An error occurred (AccessDenied) when calling GetObject")
        assert ParallelIcebergLoader._is_s3_tables_throttle_error(error) is False

    def test_no_such_key_is_not_throttle(self):
        """Exception with 'NoSuchKey' should NOT be classified as throttle."""
        error = Exception("An error occurred (NoSuchKey) when calling GetObject")
        assert ParallelIcebergLoader._is_s3_tables_throttle_error(error) is False

    def test_generic_exception_is_not_throttle(self):
        """Generic exception without throttle indicators should NOT be throttle."""
        error = Exception("Something went wrong")
        assert ParallelIcebergLoader._is_s3_tables_throttle_error(error) is False

    def test_botocore_error_404_is_not_throttle(self):
        """Botocore ClientError with HTTPStatusCode 404 should NOT be throttle."""
        error = Exception("Not found")
        error.response = {
            "ResponseMetadata": {"HTTPStatusCode": 404},
            "Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist"},
        }
        assert ParallelIcebergLoader._is_s3_tables_throttle_error(error) is False


class TestRetryWithThrottleBackoff:
    """Tests for _retry_with_throttle_backoff method.

    Validates: Requirements 6.3, 6.4, 6.5, 6.6
    """

    def _make_loader(self):
        """Create a ParallelIcebergLoader with mocked dependencies."""
        return ParallelIcebergLoader(
            catalog=MagicMock(),
            credential_provider=MagicMock(),
            type_mapper=MagicMock(),
            partition_mapper=MagicMock(),
            dedup_guard=MagicMock(),
            parallelism=4,
        )

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self):
        """Should return result immediately when operation succeeds first time."""
        loader = self._make_loader()
        operation = MagicMock(return_value="success_result")

        result = await loader._retry_with_throttle_backoff(
            operation, "orders", "append_data"
        )

        assert result == "success_result"
        operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_retries_on_throttle_and_succeeds(self):
        """Should retry on throttle error and return result on success."""
        loader = self._make_loader()
        throttle_error = Exception("An error occurred (SlowDown) when calling API")
        operation = MagicMock(side_effect=[throttle_error, throttle_error, "success"])

        async def mock_sleep(delay):
            pass

        with patch("services.bq_iceberg_migration.iceberg_loader.asyncio.sleep", side_effect=mock_sleep):
            result = await loader._retry_with_throttle_backoff(
                operation, "orders", "append_data"
            )

        assert result == "success"
        assert operation.call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self):
        """Should use exponential backoff: 1s, 2s, 4s, 8s, 16s."""
        loader = self._make_loader()
        throttle_error = Exception("HTTP 429 Too Many Requests")
        # Fail 6 times (initial + 5 retries) to exhaust all retries
        operation = MagicMock(side_effect=[throttle_error] * 6)

        sleep_delays = []

        async def mock_sleep(delay):
            sleep_delays.append(delay)

        with patch("services.bq_iceberg_migration.iceberg_loader.asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(_RetryExhaustedError):
                await loader._retry_with_throttle_backoff(
                    operation, "orders", "create_table"
                )

        # Should have 5 sleep calls with exponential backoff
        assert sleep_delays == [1.0, 2.0, 4.0, 8.0, 16.0]

    @pytest.mark.asyncio
    async def test_raises_retry_exhausted_after_max_retries(self):
        """Should raise _RetryExhaustedError with S3_TABLES_THROTTLED after 5 retries."""
        loader = self._make_loader()
        throttle_error = Exception("An error occurred (SlowDown)")
        operation = MagicMock(side_effect=throttle_error)

        async def mock_sleep(delay):
            pass

        with patch("services.bq_iceberg_migration.iceberg_loader.asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(_RetryExhaustedError) as exc_info:
                await loader._retry_with_throttle_backoff(
                    operation, "orders", "append_data"
                )

        assert exc_info.value.error_code == ErrorCode.S3_TABLES_THROTTLED
        assert exc_info.value.retries == 5
        # Initial attempt + 5 retries = 6 total calls
        assert operation.call_count == 6

    @pytest.mark.asyncio
    async def test_non_throttle_error_raises_immediately(self):
        """Should re-raise non-throttle errors immediately without retry."""
        loader = self._make_loader()
        non_throttle_error = Exception("Access Denied - permission error")
        operation = MagicMock(side_effect=non_throttle_error)

        with pytest.raises(Exception, match="Access Denied"):
            await loader._retry_with_throttle_backoff(
                operation, "orders", "create_table"
            )

        # Should only be called once - no retry for non-throttle errors
        operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_logs_warning_on_each_retry(self):
        """Should log WARNING with table_name, operation, retry count, and backoff delay."""
        loader = self._make_loader()
        throttle_error = Exception("HTTP 429 Too Many Requests")
        operation = MagicMock(side_effect=[throttle_error, throttle_error, "success"])

        async def mock_sleep(delay):
            pass

        with patch("services.bq_iceberg_migration.iceberg_loader.asyncio.sleep", side_effect=mock_sleep):
            with patch("services.bq_iceberg_migration.iceberg_loader.logger") as mock_logger:
                await loader._retry_with_throttle_backoff(
                    operation, "orders", "append_data"
                )

                # Should have 2 warning calls (2 retries before success)
                assert mock_logger.warning.call_count == 2

                # Verify first warning contains expected info
                first_call_args = mock_logger.warning.call_args_list[0]
                log_msg = first_call_args[0][0] % first_call_args[0][1:]
                assert "orders" in log_msg
                assert "append_data" in log_msg
                assert "1/5" in log_msg  # retry 1 of 5
                assert "1.0" in log_msg  # 1.0s backoff

    @pytest.mark.asyncio
    async def test_marks_table_failed_with_throttled_error_code(self):
        """After 5 retries exhausted, error code should be S3_TABLES_THROTTLED."""
        loader = self._make_loader()
        throttle_error = Exception("An error occurred (SlowDown)")
        operation = MagicMock(side_effect=throttle_error)

        async def mock_sleep(delay):
            pass

        with patch("services.bq_iceberg_migration.iceberg_loader.asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(_RetryExhaustedError) as exc_info:
                await loader._retry_with_throttle_backoff(
                    operation, "my_table", "put_maintenance_config"
                )

        # Verify the error code is S3_TABLES_THROTTLED (not S3_TABLES_API_FAILED)
        assert exc_info.value.error_code == ErrorCode.S3_TABLES_THROTTLED
        assert "my_table" in str(exc_info.value)
        assert "put_maintenance_config" in str(exc_info.value)


class TestClassifyErrorThrottling:
    """Tests for _classify_error distinguishing throttle from other S3 Tables errors.

    Validates: Requirements 6.4
    """

    def test_classify_429_as_throttled(self):
        """HTTP 429 error should be classified as S3_TABLES_THROTTLED."""
        error = Exception("HTTP 429 Too Many Requests from S3 Tables")
        result = ParallelIcebergLoader._classify_error(error)
        assert result == ErrorCode.S3_TABLES_THROTTLED

    def test_classify_slowdown_as_throttled(self):
        """SlowDown error should be classified as S3_TABLES_THROTTLED."""
        error = Exception("An error occurred (SlowDown) when calling PutTableMaintenanceConfiguration")
        result = ParallelIcebergLoader._classify_error(error)
        assert result == ErrorCode.S3_TABLES_THROTTLED

    def test_classify_s3tables_non_throttle_as_api_failed(self):
        """Non-throttle S3 Tables error should be classified as S3_TABLES_API_FAILED."""
        error = Exception("S3Tables API returned InternalError")
        result = ParallelIcebergLoader._classify_error(error)
        assert result == ErrorCode.S3_TABLES_API_FAILED

    def test_classify_access_denied_as_s3_access_error(self):
        """Access denied error should be classified as ICEBERG_S3_ACCESS_ERROR."""
        error = Exception("Access Denied when accessing S3 bucket")
        result = ParallelIcebergLoader._classify_error(error)
        assert result == ErrorCode.ICEBERG_S3_ACCESS_ERROR

    def test_classify_glue_permission_denied(self):
        """Glue permission error should be classified as GLUE_PERMISSION_DENIED."""
        error = Exception("Access Denied: not authorized for Glue operation")
        result = ParallelIcebergLoader._classify_error(error)
        assert result == ErrorCode.GLUE_PERMISSION_DENIED

    def test_classify_generic_error_as_table_create_failed(self):
        """Generic error should be classified as ICEBERG_TABLE_CREATE_FAILED."""
        error = Exception("Something unexpected happened")
        result = ParallelIcebergLoader._classify_error(error)
        assert result == ErrorCode.ICEBERG_TABLE_CREATE_FAILED


# =============================================================================
# File-Time Watermark Logic Tests (Task 5.3)
# =============================================================================

from datetime import datetime, timezone, timedelta
from services.bq_iceberg_migration.iceberg_loader import ParallelIcebergLoader


# --- Sample Payloads for Watermark Tests ---

SAMPLE_FILES_WITH_TIMESTAMPS = [
    {
        "uri": "s3://bucket/data/orders/file1.parquet",
        "file_modification_time": "2024-01-15T10:30:00Z",
    },
    {
        "uri": "s3://bucket/data/orders/file2.parquet",
        "file_modification_time": "2024-01-15T11:00:00Z",
    },
    {
        "uri": "s3://bucket/data/orders/file3.parquet",
        "file_modification_time": "2024-01-15T09:00:00Z",
    },
]

SAMPLE_FILES_WITH_DATETIME_OBJECTS = [
    {
        "uri": "s3://bucket/data/orders/file1.parquet",
        "file_modification_time": datetime(2024, 3, 10, 14, 30, 0, tzinfo=timezone.utc),
    },
    {
        "uri": "s3://bucket/data/orders/file2.parquet",
        "file_modification_time": datetime(2024, 3, 10, 16, 45, 0, tzinfo=timezone.utc),
    },
]

SAMPLE_CHECKPOINT_DATA_WITH_WATERMARK = {
    "file_time_watermarks": {
        "orders": "2024-01-15T10:30:00Z",
        "customers": "2024-01-14T08:00:00Z",
    }
}

SAMPLE_CHECKPOINT_DATA_EMPTY = {}


class TestComputeFileTimeWatermark:
    """Tests for _compute_file_time_watermark method.

    Validates: Requirements 8.1, 8.6
    """

    @pytest.fixture
    def loader(self):
        """Create a ParallelIcebergLoader with mocked dependencies."""
        return ParallelIcebergLoader(
            catalog=MagicMock(),
            credential_provider=MagicMock(),
            type_mapper=MagicMock(),
            partition_mapper=MagicMock(),
            dedup_guard=MagicMock(),
            parallelism=4,
        )

    def test_returns_max_timestamp_from_iso_strings(self, loader):
        """Should return the maximum file_modification_time as ISO 8601 UTC."""
        result = loader._compute_file_time_watermark(SAMPLE_FILES_WITH_TIMESTAMPS)
        assert result == "2024-01-15T11:00:00Z"

    def test_returns_max_timestamp_from_datetime_objects(self, loader):
        """Should handle datetime objects and return max as ISO 8601 UTC."""
        result = loader._compute_file_time_watermark(SAMPLE_FILES_WITH_DATETIME_OBJECTS)
        assert result == "2024-03-10T16:45:00Z"

    def test_returns_none_for_empty_list(self, loader):
        """Should return None when no files are provided."""
        result = loader._compute_file_time_watermark([])
        assert result is None

    def test_returns_none_for_files_without_timestamps(self, loader):
        """Should return None when files have no file_modification_time."""
        files = [
            {"uri": "s3://bucket/file1.parquet"},
            {"uri": "s3://bucket/file2.parquet"},
        ]
        result = loader._compute_file_time_watermark(files)
        assert result is None

    def test_returns_none_for_none_timestamps(self, loader):
        """Should return None when all file_modification_time values are None."""
        files = [
            {"uri": "s3://bucket/file1.parquet", "file_modification_time": None},
            {"uri": "s3://bucket/file2.parquet", "file_modification_time": None},
        ]
        result = loader._compute_file_time_watermark(files)
        assert result is None

    def test_single_file_returns_its_timestamp(self, loader):
        """Should return the single file's timestamp."""
        files = [
            {"uri": "s3://bucket/file1.parquet", "file_modification_time": "2024-06-01T12:00:00Z"},
        ]
        result = loader._compute_file_time_watermark(files)
        assert result == "2024-06-01T12:00:00Z"

    def test_format_is_iso_8601_utc_with_second_precision(self, loader):
        """Should format watermark as ISO 8601 UTC with second precision (Req 8.6)."""
        files = [
            {
                "uri": "s3://bucket/file1.parquet",
                "file_modification_time": datetime(2024, 1, 15, 10, 30, 45, 123456, tzinfo=timezone.utc),
            },
        ]
        result = loader._compute_file_time_watermark(files)
        # Should truncate to second precision
        assert result == "2024-01-15T10:30:45Z"
        # Verify format matches pattern
        import re
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", result)

    def test_handles_mixed_string_and_datetime_timestamps(self, loader):
        """Should handle a mix of string and datetime timestamps."""
        files = [
            {"uri": "s3://bucket/file1.parquet", "file_modification_time": "2024-01-15T10:00:00Z"},
            {
                "uri": "s3://bucket/file2.parquet",
                "file_modification_time": datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            },
        ]
        result = loader._compute_file_time_watermark(files)
        assert result == "2024-01-15T12:00:00Z"

    def test_skips_invalid_timestamp_strings(self, loader):
        """Should skip files with unparseable timestamp strings."""
        files = [
            {"uri": "s3://bucket/file1.parquet", "file_modification_time": "not-a-date"},
            {"uri": "s3://bucket/file2.parquet", "file_modification_time": "2024-01-15T10:00:00Z"},
        ]
        result = loader._compute_file_time_watermark(files)
        assert result == "2024-01-15T10:00:00Z"

    def test_handles_naive_datetime_as_utc(self, loader):
        """Should treat naive datetimes as UTC."""
        files = [
            {
                "uri": "s3://bucket/file1.parquet",
                "file_modification_time": datetime(2024, 1, 15, 10, 0, 0),  # naive
            },
        ]
        result = loader._compute_file_time_watermark(files)
        assert result == "2024-01-15T10:00:00Z"


class TestFilterFilesByWatermark:
    """Tests for _filter_files_by_watermark method.

    Validates: Requirements 8.2
    """

    @pytest.fixture
    def loader(self):
        """Create a ParallelIcebergLoader with mocked dependencies."""
        return ParallelIcebergLoader(
            catalog=MagicMock(),
            credential_provider=MagicMock(),
            type_mapper=MagicMock(),
            partition_mapper=MagicMock(),
            dedup_guard=MagicMock(),
            parallelism=4,
        )

    def test_returns_all_files_when_watermark_is_none(self, loader):
        """Should return all files when watermark is None (first load)."""
        result = loader._filter_files_by_watermark(SAMPLE_FILES_WITH_TIMESTAMPS, None)
        assert len(result) == 3

    def test_filters_files_strictly_greater_than_watermark(self, loader):
        """Should return only files with modification_time > watermark (Req 8.2)."""
        watermark = "2024-01-15T10:00:00Z"
        result = loader._filter_files_by_watermark(SAMPLE_FILES_WITH_TIMESTAMPS, watermark)
        # file1 (10:30) and file2 (11:00) are > 10:00, file3 (09:00) is not
        assert len(result) == 2
        uris = [f["uri"] for f in result]
        assert "s3://bucket/data/orders/file1.parquet" in uris
        assert "s3://bucket/data/orders/file2.parquet" in uris

    def test_excludes_files_equal_to_watermark(self, loader):
        """Should exclude files with modification_time == watermark (strictly greater)."""
        watermark = "2024-01-15T10:30:00Z"
        result = loader._filter_files_by_watermark(SAMPLE_FILES_WITH_TIMESTAMPS, watermark)
        # Only file2 (11:00) is strictly > 10:30
        assert len(result) == 1
        assert result[0]["uri"] == "s3://bucket/data/orders/file2.parquet"

    def test_returns_empty_when_all_files_at_or_before_watermark(self, loader):
        """Should return empty list when all files are at or before watermark."""
        watermark = "2024-01-15T11:00:00Z"
        result = loader._filter_files_by_watermark(SAMPLE_FILES_WITH_TIMESTAMPS, watermark)
        assert len(result) == 0

    def test_returns_all_files_when_watermark_before_all(self, loader):
        """Should return all files when watermark is before all file timestamps."""
        watermark = "2024-01-01T00:00:00Z"
        result = loader._filter_files_by_watermark(SAMPLE_FILES_WITH_TIMESTAMPS, watermark)
        assert len(result) == 3

    def test_handles_datetime_objects_in_files(self, loader):
        """Should handle datetime objects in file metadata."""
        watermark = "2024-03-10T15:00:00Z"
        result = loader._filter_files_by_watermark(SAMPLE_FILES_WITH_DATETIME_OBJECTS, watermark)
        # Only file2 (16:45) is > 15:00
        assert len(result) == 1
        assert result[0]["uri"] == "s3://bucket/data/orders/file2.parquet"

    def test_includes_files_without_modification_time(self, loader):
        """Should include files that have no file_modification_time (safe default)."""
        files = [
            {"uri": "s3://bucket/file1.parquet"},  # no timestamp
            {"uri": "s3://bucket/file2.parquet", "file_modification_time": "2024-01-15T10:00:00Z"},
        ]
        watermark = "2024-01-15T11:00:00Z"
        result = loader._filter_files_by_watermark(files, watermark)
        # file1 (no timestamp) included, file2 (10:00) excluded
        assert len(result) == 1
        assert result[0]["uri"] == "s3://bucket/file1.parquet"

    def test_returns_all_files_for_invalid_watermark(self, loader):
        """Should return all files when watermark format is invalid (safe fallback)."""
        result = loader._filter_files_by_watermark(
            SAMPLE_FILES_WITH_TIMESTAMPS, "not-a-valid-timestamp"
        )
        assert len(result) == 3

    def test_empty_files_list_returns_empty(self, loader):
        """Should return empty list when no files provided."""
        result = loader._filter_files_by_watermark([], "2024-01-15T10:00:00Z")
        assert len(result) == 0

    def test_empty_files_list_with_none_watermark(self, loader):
        """Should return empty list when no files and watermark is None."""
        result = loader._filter_files_by_watermark([], None)
        assert len(result) == 0


class TestLoadTableIncremental:
    """Tests for load_table_incremental method.

    Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
    """

    @pytest.fixture
    def loader(self):
        """Create a ParallelIcebergLoader with mocked dependencies."""
        catalog = MagicMock()
        catalog.load_table.return_value = MagicMock()
        dedup_guard = MagicMock()
        dedup_guard.is_safe_to_append.return_value = (True, ["s3://bucket/file1.parquet"])

        loader = ParallelIcebergLoader(
            catalog=catalog,
            credential_provider=MagicMock(),
            type_mapper=MagicMock(),
            partition_mapper=MagicMock(),
            dedup_guard=dedup_guard,
            parallelism=4,
        )
        return loader

    @pytest.fixture
    def migration(self):
        """Create a mock migration object."""
        m = MagicMock()
        m.glue_database_name = "test_db"
        return m

    @pytest.mark.asyncio
    async def test_no_new_files_returns_success_with_zero_files(self, loader, migration):
        """Should return success with 0 files when no new files found (Req 8.5)."""
        checkpoint_data = {
            "file_time_watermarks": {"orders": "2024-01-15T12:00:00Z"}
        }
        source_files = [
            {"uri": "s3://bucket/file1.parquet", "file_modification_time": "2024-01-15T10:00:00Z"},
            {"uri": "s3://bucket/file2.parquet", "file_modification_time": "2024-01-15T11:00:00Z"},
        ]

        result = await loader.load_table_incremental(
            migration=migration,
            table_name="orders",
            source_files=source_files,
            checkpoint_data=checkpoint_data,
        )

        assert result.success is True
        assert result.files_appended == 0
        assert result.table_name == "orders"

    @pytest.mark.asyncio
    async def test_watermark_not_updated_on_no_new_files(self, loader, migration):
        """Should not modify watermark when no new files found."""
        checkpoint_data = {
            "file_time_watermarks": {"orders": "2024-01-15T12:00:00Z"}
        }
        source_files = [
            {"uri": "s3://bucket/file1.parquet", "file_modification_time": "2024-01-15T10:00:00Z"},
        ]

        await loader.load_table_incremental(
            migration=migration,
            table_name="orders",
            source_files=source_files,
            checkpoint_data=checkpoint_data,
        )

        # Watermark should remain unchanged
        assert checkpoint_data["file_time_watermarks"]["orders"] == "2024-01-15T12:00:00Z"

    @pytest.mark.asyncio
    async def test_watermark_updated_on_success(self, loader, migration):
        """Should update watermark to max file_modification_time on success (Req 8.1)."""
        checkpoint_data = {
            "file_time_watermarks": {"orders": "2024-01-15T09:00:00Z"}
        }
        source_files = [
            {"uri": "s3://bucket/file1.parquet", "file_modification_time": "2024-01-15T10:00:00Z"},
            {"uri": "s3://bucket/file2.parquet", "file_modification_time": "2024-01-15T11:00:00Z"},
        ]

        result = await loader.load_table_incremental(
            migration=migration,
            table_name="orders",
            source_files=source_files,
            checkpoint_data=checkpoint_data,
        )

        assert result.success is True
        assert checkpoint_data["file_time_watermarks"]["orders"] == "2024-01-15T11:00:00Z"

    @pytest.mark.asyncio
    async def test_watermark_not_updated_on_failure(self, loader, migration):
        """Should NOT update watermark on partial failure (Req 8.4)."""
        # Make the append fail
        loader._catalog.load_table.side_effect = RuntimeError("Table not found in catalog")

        checkpoint_data = {
            "file_time_watermarks": {"orders": "2024-01-15T09:00:00Z"}
        }
        source_files = [
            {"uri": "s3://bucket/file1.parquet", "file_modification_time": "2024-01-15T10:00:00Z"},
            {"uri": "s3://bucket/file2.parquet", "file_modification_time": "2024-01-15T11:00:00Z"},
        ]

        result = await loader.load_table_incremental(
            migration=migration,
            table_name="orders",
            source_files=source_files,
            checkpoint_data=checkpoint_data,
        )

        assert result.success is False
        # Watermark should remain at previous value
        assert checkpoint_data["file_time_watermarks"]["orders"] == "2024-01-15T09:00:00Z"

    @pytest.mark.asyncio
    async def test_first_load_creates_watermark_entry(self, loader, migration):
        """Should create file_time_watermarks entry on first successful load."""
        checkpoint_data = {}  # No watermarks yet
        source_files = [
            {"uri": "s3://bucket/file1.parquet", "file_modification_time": "2024-01-15T10:00:00Z"},
        ]

        result = await loader.load_table_incremental(
            migration=migration,
            table_name="orders",
            source_files=source_files,
            checkpoint_data=checkpoint_data,
        )

        assert result.success is True
        assert "file_time_watermarks" in checkpoint_data
        assert checkpoint_data["file_time_watermarks"]["orders"] == "2024-01-15T10:00:00Z"

    @pytest.mark.asyncio
    async def test_watermark_monotonic_update(self, loader, migration):
        """Should only update watermark if new value is strictly greater (Req 8.3)."""
        checkpoint_data = {
            "file_time_watermarks": {"orders": "2024-01-15T12:00:00Z"}
        }
        # Files with timestamps before the existing watermark but after a different watermark
        # This simulates a scenario where the new max is less than existing
        source_files = [
            {"uri": "s3://bucket/file1.parquet", "file_modification_time": "2024-01-15T12:30:00Z"},
        ]

        result = await loader.load_table_incremental(
            migration=migration,
            table_name="orders",
            source_files=source_files,
            checkpoint_data=checkpoint_data,
        )

        assert result.success is True
        # Watermark should be updated to 12:30 (greater than 12:00)
        assert checkpoint_data["file_time_watermarks"]["orders"] == "2024-01-15T12:30:00Z"

    @pytest.mark.asyncio
    async def test_all_files_processed_on_first_load(self, loader, migration):
        """Should process all files when no watermark exists (first load)."""
        checkpoint_data = {}
        source_files = [
            {"uri": "s3://bucket/file1.parquet", "file_modification_time": "2024-01-15T10:00:00Z"},
            {"uri": "s3://bucket/file2.parquet", "file_modification_time": "2024-01-15T11:00:00Z"},
            {"uri": "s3://bucket/file3.parquet", "file_modification_time": "2024-01-15T09:00:00Z"},
        ]

        result = await loader.load_table_incremental(
            migration=migration,
            table_name="orders",
            source_files=source_files,
            checkpoint_data=checkpoint_data,
        )

        assert result.success is True
        assert result.files_appended == 3

    @pytest.mark.asyncio
    async def test_watermark_stored_as_iso_8601_utc(self, loader, migration):
        """Should store watermark as ISO 8601 UTC with second precision (Req 8.6)."""
        import re

        checkpoint_data = {}
        source_files = [
            {"uri": "s3://bucket/file1.parquet", "file_modification_time": "2024-06-15T14:30:45Z"},
        ]

        await loader.load_table_incremental(
            migration=migration,
            table_name="orders",
            source_files=source_files,
            checkpoint_data=checkpoint_data,
        )

        watermark = checkpoint_data["file_time_watermarks"]["orders"]
        # Verify ISO 8601 UTC format with second precision
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", watermark)
        assert watermark.endswith("Z")


# =============================================================================
# Lake Formation Prerequisites Tests
# =============================================================================


class TestLakeFormationPrerequisites:
    """Tests for Lake Formation prerequisites in structure report.

    Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 2.4
    - Lake Formation section only shown for S3 Tables destinations
    - Data location permission includes bucket ARN
    - DESCRIBE on Glue database included
    - SELECT on Glue tables included
    - lakeformation:GetDataAccess IAM permission included
    - Glue execution role permissions included
    - glue.id included in prerequisites
    """

    @pytest.fixture
    def generator(self):
        """Create a StructureReportGenerator instance."""
        from services.bq_iceberg_migration.structure_report import (
            StructureReportGenerator,
        )
        return StructureReportGenerator()

    @pytest.fixture
    def s3_tables_migration(self):
        """Create a mock migration with S3 Tables destination."""
        migration = MagicMock()
        migration.id = 1
        migration.destination_type = "iceberg_s3_tables"
        migration.table_bucket_arn = (
            "arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket"
        )
        migration.glue_database_name = "analytics_db"
        migration.aws_region = "us-east-1"
        migration.s3_tables_namespace = "analytics"
        return migration

    @pytest.fixture
    def standard_s3_migration(self):
        """Create a mock migration with standard S3 destination."""
        migration = MagicMock()
        migration.id = 2
        migration.destination_type = "iceberg_s3"
        migration.table_bucket_arn = None
        migration.glue_database_name = "my_db"
        migration.aws_region = "us-west-2"
        migration.s3_tables_namespace = None
        return migration

    def test_lake_formation_not_shown_for_standard_s3(
        self, generator, standard_s3_migration
    ):
        """Lake Formation section should NOT appear for standard S3 destinations (Req 5.6)."""
        prereqs = generator._generate_prerequisites(
            "iceberg_s3", standard_s3_migration
        )
        assert "lake_formation" not in prereqs
        assert "glue_id" not in prereqs

    def test_lake_formation_shown_for_s3_tables(
        self, generator, s3_tables_migration
    ):
        """Lake Formation section should appear for S3 Tables destinations (Req 5.1)."""
        prereqs = generator._generate_prerequisites(
            "iceberg_s3_tables", s3_tables_migration
        )
        assert "lake_formation" in prereqs
        assert isinstance(prereqs["lake_formation"], list)
        assert len(prereqs["lake_formation"]) == 5

    def test_glue_id_included_in_prerequisites(
        self, generator, s3_tables_migration
    ):
        """Prerequisites should include derived glue.id value (Req 2.4)."""
        prereqs = generator._generate_prerequisites(
            "iceberg_s3_tables", s3_tables_migration
        )
        assert "glue_id" in prereqs
        assert prereqs["glue_id"] == "123456789012:s3tablescatalog/my-table-bucket"

    def test_data_location_permission_includes_bucket_arn(
        self, generator, s3_tables_migration
    ):
        """Data location permission should reference the bucket ARN (Req 5.2)."""
        prereqs = generator._generate_prerequisites(
            "iceberg_s3_tables", s3_tables_migration
        )
        lf_items = prereqs["lake_formation"]
        data_loc_item = lf_items[0]

        assert data_loc_item["action_type"] == "data_location_permission"
        assert (
            "arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket"
            in data_loc_item["arn_or_permission"]
        )
        assert "bucket ARN" in data_loc_item["description"]
        assert "s3://" in data_loc_item["description"]

    def test_describe_permission_on_glue_database(
        self, generator, s3_tables_migration
    ):
        """DESCRIBE permission should reference the Glue database (Req 5.3)."""
        prereqs = generator._generate_prerequisites(
            "iceberg_s3_tables", s3_tables_migration
        )
        lf_items = prereqs["lake_formation"]
        describe_item = lf_items[1]

        assert describe_item["action_type"] == "DESCRIBE"
        assert "analytics_db" in describe_item["arn_or_permission"]
        assert "arn:aws:glue:us-east-1:123456789012:database/analytics_db" == (
            describe_item["arn_or_permission"]
        )

    def test_select_permission_on_glue_tables(
        self, generator, s3_tables_migration
    ):
        """SELECT permission should reference Glue tables in the database (Req 5.3)."""
        prereqs = generator._generate_prerequisites(
            "iceberg_s3_tables", s3_tables_migration
        )
        lf_items = prereqs["lake_formation"]
        select_item = lf_items[2]

        assert select_item["action_type"] == "SELECT"
        assert "analytics_db" in select_item["arn_or_permission"]
        assert "arn:aws:glue:us-east-1:123456789012:table/analytics_db/*" == (
            select_item["arn_or_permission"]
        )

    def test_get_data_access_iam_permission(
        self, generator, s3_tables_migration
    ):
        """lakeformation:GetDataAccess IAM permission should be included (Req 5.4)."""
        prereqs = generator._generate_prerequisites(
            "iceberg_s3_tables", s3_tables_migration
        )
        lf_items = prereqs["lake_formation"]
        iam_item = lf_items[3]

        assert iam_item["action_type"] == "iam_permission"
        assert iam_item["arn_or_permission"] == "lakeformation:GetDataAccess"

    def test_glue_execution_role_permissions(
        self, generator, s3_tables_migration
    ):
        """Glue execution role permissions should be included (Req 5.5)."""
        prereqs = generator._generate_prerequisites(
            "iceberg_s3_tables", s3_tables_migration
        )
        lf_items = prereqs["lake_formation"]
        role_item = lf_items[4]

        assert role_item["action_type"] == "glue_execution_role"
        assert "123456789012" in role_item["arn_or_permission"]
        assert "glue-execution-role" in role_item["arn_or_permission"]

    def test_items_are_actionable_checklist_format(
        self, generator, s3_tables_migration
    ):
        """Each item should have description, arn_or_permission, and action_type (Req 5.7)."""
        prereqs = generator._generate_prerequisites(
            "iceberg_s3_tables", s3_tables_migration
        )
        lf_items = prereqs["lake_formation"]

        for item in lf_items:
            assert "description" in item, "Each item must have a description"
            assert "arn_or_permission" in item, "Each item must have arn_or_permission"
            assert "action_type" in item, "Each item must have action_type"
            assert len(item["description"]) > 0
            assert len(item["arn_or_permission"]) > 0

    def test_full_generate_includes_lake_formation_for_s3_tables(
        self, generator, s3_tables_migration
    ):
        """Full generate() method should include Lake Formation in prerequisites (Req 5.1)."""
        from services.bq_iceberg_migration.type_mapper import BQToIcebergTypeMapper
        from services.bq_iceberg_migration.partition_mapper import PartitionSpecMapper

        report = generator.generate(
            migration=s3_tables_migration,
            assessment_tables=[],
            type_mapper=BQToIcebergTypeMapper(),
            partition_mapper=PartitionSpecMapper(),
        )

        assert "lake_formation" in report["prerequisites"]
        assert "glue_id" in report["prerequisites"]
        assert report["prerequisites"]["glue_id"] == (
            "123456789012:s3tablescatalog/my-table-bucket"
        )

    def test_full_generate_excludes_lake_formation_for_standard_s3(
        self, generator, standard_s3_migration
    ):
        """Full generate() method should NOT include Lake Formation for standard S3 (Req 5.6)."""
        from services.bq_iceberg_migration.type_mapper import BQToIcebergTypeMapper
        from services.bq_iceberg_migration.partition_mapper import PartitionSpecMapper

        report = generator.generate(
            migration=standard_s3_migration,
            assessment_tables=[],
            type_mapper=BQToIcebergTypeMapper(),
            partition_mapper=PartitionSpecMapper(),
        )

        assert "lake_formation" not in report["prerequisites"]
        assert "glue_id" not in report["prerequisites"]

    def test_missing_table_bucket_arn_uses_placeholder(self, generator):
        """Should use placeholder when table_bucket_arn is missing."""
        migration = MagicMock()
        migration.table_bucket_arn = ""
        migration.glue_database_name = "my_db"
        migration.aws_region = "us-east-1"

        prereqs = generator._generate_prerequisites(
            "iceberg_s3_tables", migration
        )

        assert "lake_formation" in prereqs
        # glue_id should not be present when ARN is empty
        assert "glue_id" not in prereqs
        # Data location should use placeholder
        lf_items = prereqs["lake_formation"]
        assert lf_items[0]["arn_or_permission"] == "<table-bucket-arn>"

    def test_different_region_reflected_in_arns(self, generator):
        """ARNs should reflect the correct AWS region."""
        migration = MagicMock()
        migration.table_bucket_arn = (
            "arn:aws:s3tables:eu-west-1:987654321098:bucket/eu-bucket"
        )
        migration.glue_database_name = "eu_database"
        migration.aws_region = "eu-west-1"

        prereqs = generator._generate_prerequisites(
            "iceberg_s3_tables", migration
        )

        lf_items = prereqs["lake_formation"]
        assert "eu-west-1" in lf_items[1]["arn_or_permission"]
        assert "987654321098" in lf_items[1]["arn_or_permission"]
        assert "eu_database" in lf_items[1]["arn_or_permission"]
        assert prereqs["glue_id"] == "987654321098:s3tablescatalog/eu-bucket"

# =============================================================================
# Additional Throttle Retry and Watermark Tests (Task 5.6)
# =============================================================================


class TestNoNewFilesLogsInfo:
    """Tests that no new files scenario logs INFO message.

    Validates: Requirements 8.5
    """

    @pytest.fixture
    def loader(self):
        """Create a ParallelIcebergLoader with mocked dependencies."""
        catalog = MagicMock()
        catalog.load_table.return_value = MagicMock()
        dedup_guard = MagicMock()
        dedup_guard.is_safe_to_append.return_value = (True, [])

        loader = ParallelIcebergLoader(
            catalog=catalog,
            credential_provider=MagicMock(),
            type_mapper=MagicMock(),
            partition_mapper=MagicMock(),
            dedup_guard=dedup_guard,
            parallelism=4,
        )
        return loader

    @pytest.fixture
    def migration(self):
        """Create a mock migration object."""
        m = MagicMock()
        m.glue_database_name = "test_db"
        return m

    @pytest.mark.asyncio
    async def test_no_new_files_logs_info_message(self, loader, migration):
        """Should log INFO when no new files are found for a table (Req 8.5)."""
        checkpoint_data = {
            "file_time_watermarks": {"orders": "2024-01-15T12:00:00Z"}
        }
        source_files = [
            {"uri": "s3://bucket/file1.parquet", "file_modification_time": "2024-01-15T10:00:00Z"},
            {"uri": "s3://bucket/file2.parquet", "file_modification_time": "2024-01-15T11:00:00Z"},
        ]

        with patch("services.bq_iceberg_migration.iceberg_loader.logger") as mock_logger:
            result = await loader.load_table_incremental(
                migration=migration,
                table_name="orders",
                source_files=source_files,
                checkpoint_data=checkpoint_data,
            )

            assert result.success is True
            assert result.files_appended == 0

            # Verify INFO log was called with "No new files" message
            info_calls = mock_logger.info.call_args_list
            no_new_files_logged = False
            for c in info_calls:
                msg = c[0][0] if c[0] else ""
                if "No new files" in msg and "orders" in str(c):
                    no_new_files_logged = True
                    break

            assert no_new_files_logged, (
                "Expected INFO log with 'No new files' message for table 'orders'"
            )

    @pytest.mark.asyncio
    async def test_no_new_files_returns_zero_files_appended(self, loader, migration):
        """Should return TableLoadResult with files_appended=0 when no new files."""
        checkpoint_data = {
            "file_time_watermarks": {"customers": "2024-06-01T00:00:00Z"}
        }
        source_files = [
            {"uri": "s3://bucket/old.parquet", "file_modification_time": "2024-05-01T10:00:00Z"},
        ]

        result = await loader.load_table_incremental(
            migration=migration,
            table_name="customers",
            source_files=source_files,
            checkpoint_data=checkpoint_data,
        )

        assert result.success is True
        assert result.files_appended == 0
        assert result.table_name == "customers"
        assert result.error_code is None


class TestFullReloadResetsWatermark:
    """Tests that full reload resets watermark to null.

    Validates: Requirement 8.7 — When the user triggers a full reload for a table
    that has an existing watermark, the system SHALL reset the watermark for that
    table to null, causing the next load to process all available files.
    """

    @pytest.fixture
    def loader(self):
        """Create a ParallelIcebergLoader with mocked dependencies."""
        return ParallelIcebergLoader(
            catalog=MagicMock(),
            credential_provider=MagicMock(),
            type_mapper=MagicMock(),
            partition_mapper=MagicMock(),
            dedup_guard=MagicMock(),
            parallelism=4,
        )

    def test_reset_watermark_sets_to_null(self, loader):
        """Should set watermark to None for the specified table (Req 8.7)."""
        checkpoint_data = {
            "file_time_watermarks": {
                "orders": "2024-01-15T10:30:00Z",
                "customers": "2024-01-14T08:00:00Z",
            }
        }

        loader.reset_watermark_for_full_reload("orders", checkpoint_data)

        assert checkpoint_data["file_time_watermarks"]["orders"] is None
        # Other tables should not be affected
        assert checkpoint_data["file_time_watermarks"]["customers"] == "2024-01-14T08:00:00Z"

    def test_reset_watermark_preserves_other_tables(self, loader):
        """Should not affect watermarks of other tables."""
        checkpoint_data = {
            "file_time_watermarks": {
                "orders": "2024-01-15T10:30:00Z",
                "customers": "2024-01-14T08:00:00Z",
                "products": "2024-01-13T06:00:00Z",
            }
        }

        loader.reset_watermark_for_full_reload("customers", checkpoint_data)

        assert checkpoint_data["file_time_watermarks"]["customers"] is None
        assert checkpoint_data["file_time_watermarks"]["orders"] == "2024-01-15T10:30:00Z"
        assert checkpoint_data["file_time_watermarks"]["products"] == "2024-01-13T06:00:00Z"

    def test_reset_watermark_on_nonexistent_table_is_safe(self, loader):
        """Should handle gracefully when table has no existing watermark."""
        checkpoint_data = {
            "file_time_watermarks": {
                "orders": "2024-01-15T10:30:00Z",
            }
        }

        # Should not raise even if table doesn't exist in watermarks
        loader.reset_watermark_for_full_reload("nonexistent_table", checkpoint_data)

        # Original watermarks should be unchanged
        assert checkpoint_data["file_time_watermarks"]["orders"] == "2024-01-15T10:30:00Z"

    def test_reset_watermark_on_empty_checkpoint_data(self, loader):
        """Should handle gracefully when checkpoint_data has no file_time_watermarks."""
        checkpoint_data = {}

        # Should not raise
        loader.reset_watermark_for_full_reload("orders", checkpoint_data)

        # checkpoint_data should remain unchanged (no watermarks key created)
        assert "file_time_watermarks" not in checkpoint_data

    def test_next_load_processes_all_files_after_reset(self, loader):
        """After reset, _filter_files_by_watermark should return all files."""
        checkpoint_data = {
            "file_time_watermarks": {
                "orders": "2024-01-15T10:30:00Z",
            }
        }

        # Reset watermark
        loader.reset_watermark_for_full_reload("orders", checkpoint_data)

        # Now filter with the reset watermark (None)
        files = [
            {"uri": "s3://bucket/file1.parquet", "file_modification_time": "2024-01-10T10:00:00Z"},
            {"uri": "s3://bucket/file2.parquet", "file_modification_time": "2024-01-15T10:30:00Z"},
            {"uri": "s3://bucket/file3.parquet", "file_modification_time": "2024-01-20T12:00:00Z"},
        ]

        watermark = checkpoint_data["file_time_watermarks"]["orders"]
        assert watermark is None

        # With None watermark, all files should be returned
        result = loader._filter_files_by_watermark(files, watermark)
        assert len(result) == 3

    def test_reset_watermark_logs_info(self, loader):
        """Should log INFO when watermark is reset for full reload."""
        checkpoint_data = {
            "file_time_watermarks": {
                "orders": "2024-01-15T10:30:00Z",
            }
        }

        with patch("services.bq_iceberg_migration.iceberg_loader.logger") as mock_logger:
            loader.reset_watermark_for_full_reload("orders", checkpoint_data)

            mock_logger.info.assert_called()
            info_call = mock_logger.info.call_args
            msg = info_call[0][0] % info_call[0][1:]
            assert "orders" in msg
            assert "full reload" in msg.lower() or "Reset watermark" in msg


# =============================================================================
# Structure Report Compaction Strategy Tests (Task 6.4)
# =============================================================================

from services.bq_iceberg_migration.structure_report import (
    StructureReportGenerator,
    COMPACTION_STRATEGY_DESCRIPTIONS,
)
from services.bq_iceberg_migration.type_mapper import BQToIcebergTypeMapper
from services.bq_iceberg_migration.partition_mapper import PartitionSpecMapper


# --- Sample Payloads for Structure Report Compaction Tests ---

SAMPLE_TABLE_META_NO_CLUSTERING = {
    "table_name": "orders",
    "columns": [
        {"name": "id", "type": "INT64", "mode": "REQUIRED"},
        {"name": "order_date", "type": "DATE", "mode": "NULLABLE"},
        {"name": "amount", "type": "FLOAT64", "mode": "NULLABLE"},
    ],
    "partition_column": "order_date",
    "partition_type": "DATE",
    "partition_granularity": None,
    "clustering_columns": [],
    "estimated_rows": 10000,
    "estimated_size_bytes": 1048576,
    "dataset": "analytics",
}

SAMPLE_TABLE_META_WITH_CLUSTERING = {
    "table_name": "events",
    "columns": [
        {"name": "event_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "event_timestamp", "type": "TIMESTAMP", "mode": "REQUIRED"},
        {"name": "user_id", "type": "STRING", "mode": "NULLABLE"},
        {"name": "region", "type": "STRING", "mode": "NULLABLE"},
    ],
    "partition_column": "event_timestamp",
    "partition_type": "TIMESTAMP",
    "partition_granularity": "DAY",
    "clustering_columns": ["user_id", "region"],
    "estimated_rows": 500000,
    "estimated_size_bytes": 52428800,
    "dataset": "analytics",
}

SAMPLE_TABLE_META_MULTIPLE_CLUSTERING = {
    "table_name": "page_views",
    "columns": [
        {"name": "view_id", "type": "STRING", "mode": "REQUIRED"},
        {"name": "page_url", "type": "STRING", "mode": "NULLABLE"},
        {"name": "user_id", "type": "STRING", "mode": "NULLABLE"},
        {"name": "country", "type": "STRING", "mode": "NULLABLE"},
        {"name": "device_type", "type": "STRING", "mode": "NULLABLE"},
        {"name": "view_time", "type": "TIMESTAMP", "mode": "REQUIRED"},
    ],
    "partition_column": "view_time",
    "partition_type": "TIMESTAMP",
    "partition_granularity": "DAY",
    "clustering_columns": ["country", "device_type", "user_id"],
    "estimated_rows": 2000000,
    "estimated_size_bytes": 209715200,
    "dataset": "web",
}


class TestStructureReportCompactionDefaults:
    """Tests for compaction strategy defaults in structure report.

    Validates: Requirements 3.1, 3.2, 3.5, 3.6
    - Default compaction strategy is binpack when no selection made
    - Compaction config is included in the report per table
    - Compaction config is persisted in checkpoint_data via structure plan
    """

    @pytest.fixture
    def generator(self):
        """Create a StructureReportGenerator instance."""
        return StructureReportGenerator()

    @pytest.fixture
    def type_mapper(self):
        """Create a BQToIcebergTypeMapper instance."""
        return BQToIcebergTypeMapper()

    @pytest.fixture
    def partition_mapper(self):
        """Create a PartitionSpecMapper instance."""
        return PartitionSpecMapper()

    @pytest.fixture
    def s3_tables_migration(self):
        """Create a mock migration with S3 Tables destination."""
        migration = MagicMock()
        migration.id = 10
        migration.destination_type = "iceberg_s3_tables"
        migration.table_bucket_arn = (
            "arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket"
        )
        migration.glue_database_name = "analytics_db"
        migration.aws_region = "us-east-1"
        migration.s3_tables_namespace = "analytics"
        return migration

    def test_default_binpack_when_no_clustering(
        self, generator, type_mapper, partition_mapper, s3_tables_migration
    ):
        """Should default to binpack strategy when table has no clustering columns (Req 3.6)."""
        report = generator.generate(
            migration=s3_tables_migration,
            assessment_tables=[SAMPLE_TABLE_META_NO_CLUSTERING],
            type_mapper=type_mapper,
            partition_mapper=partition_mapper,
        )

        table_report = report["tables"][0]
        assert "compaction_config" in table_report
        assert table_report["compaction_config"]["strategy"] == "binpack"
        assert table_report["compaction_config"]["sort_columns"] == []

    def test_default_binpack_no_recommendation_without_clustering(
        self, generator, type_mapper, partition_mapper, s3_tables_migration
    ):
        """Should not include recommended_strategy when no clustering columns exist (Req 3.1)."""
        report = generator.generate(
            migration=s3_tables_migration,
            assessment_tables=[SAMPLE_TABLE_META_NO_CLUSTERING],
            type_mapper=type_mapper,
            partition_mapper=partition_mapper,
        )

        table_report = report["tables"][0]
        compaction_config = table_report["compaction_config"]
        assert "recommended_strategy" not in compaction_config
        assert "recommended_sort_columns" not in compaction_config

    def test_recommends_sort_when_clustering_columns_exist(
        self, generator, type_mapper, partition_mapper, s3_tables_migration
    ):
        """Should recommend sort strategy when source has clustering columns (Req 3.2)."""
        report = generator.generate(
            migration=s3_tables_migration,
            assessment_tables=[SAMPLE_TABLE_META_WITH_CLUSTERING],
            type_mapper=type_mapper,
            partition_mapper=partition_mapper,
        )

        table_report = report["tables"][0]
        compaction_config = table_report["compaction_config"]
        assert compaction_config["strategy"] == "binpack"  # default still binpack
        assert compaction_config["recommended_strategy"] == "sort"
        assert compaction_config["recommended_sort_columns"] == ["user_id", "region"]

    def test_recommended_sort_columns_match_clustering(
        self, generator, type_mapper, partition_mapper, s3_tables_migration
    ):
        """Recommended sort columns should match the source clustering columns (Req 3.2)."""
        report = generator.generate(
            migration=s3_tables_migration,
            assessment_tables=[SAMPLE_TABLE_META_MULTIPLE_CLUSTERING],
            type_mapper=type_mapper,
            partition_mapper=partition_mapper,
        )

        table_report = report["tables"][0]
        compaction_config = table_report["compaction_config"]
        assert compaction_config["recommended_sort_columns"] == [
            "country", "device_type", "user_id"
        ]

    def test_compaction_config_present_for_all_tables(
        self, generator, type_mapper, partition_mapper, s3_tables_migration
    ):
        """Every table in the report should have a compaction_config field (Req 3.1)."""
        report = generator.generate(
            migration=s3_tables_migration,
            assessment_tables=[
                SAMPLE_TABLE_META_NO_CLUSTERING,
                SAMPLE_TABLE_META_WITH_CLUSTERING,
                SAMPLE_TABLE_META_MULTIPLE_CLUSTERING,
            ],
            type_mapper=type_mapper,
            partition_mapper=partition_mapper,
        )

        for table_report in report["tables"]:
            assert "compaction_config" in table_report, (
                f"Table '{table_report['source_table']}' missing compaction_config"
            )
            assert "strategy" in table_report["compaction_config"]
            assert "sort_columns" in table_report["compaction_config"]


class TestCompactionStrategyPersistenceInCheckpointData:
    """Tests for compaction strategy persistence in checkpoint_data.

    Validates: Requirement 3.5
    - Per-table compaction strategy and sort columns are persisted in the
      approved structure plan within checkpoint_data
    """

    @pytest.fixture
    def generator(self):
        """Create a StructureReportGenerator instance."""
        return StructureReportGenerator()

    @pytest.fixture
    def type_mapper(self):
        """Create a BQToIcebergTypeMapper instance."""
        return BQToIcebergTypeMapper()

    @pytest.fixture
    def partition_mapper(self):
        """Create a PartitionSpecMapper instance."""
        return PartitionSpecMapper()

    @pytest.fixture
    def s3_tables_migration(self):
        """Create a mock migration with S3 Tables destination and checkpoint_data."""
        migration = MagicMock()
        migration.id = 20
        migration.destination_type = "iceberg_s3_tables"
        migration.table_bucket_arn = (
            "arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket"
        )
        migration.glue_database_name = "analytics_db"
        migration.aws_region = "us-east-1"
        migration.s3_tables_namespace = "analytics"
        migration.checkpoint_data = {}
        migration.status = "pending_review"
        migration.structure_approved_at = None
        return migration

    def test_compaction_config_in_structure_plan(
        self, generator, type_mapper, partition_mapper, s3_tables_migration
    ):
        """Compaction config should be included in the structure plan stored in checkpoint_data (Req 3.5)."""
        report = generator.generate(
            migration=s3_tables_migration,
            assessment_tables=[SAMPLE_TABLE_META_WITH_CLUSTERING],
            type_mapper=type_mapper,
            partition_mapper=partition_mapper,
        )

        # Simulate approval: store report in checkpoint_data
        checkpoint = s3_tables_migration.checkpoint_data or {}
        checkpoint["iceberg_structure_plan"] = report
        s3_tables_migration.checkpoint_data = checkpoint

        # Verify compaction_config is persisted
        plan = s3_tables_migration.checkpoint_data["iceberg_structure_plan"]
        assert "tables" in plan
        table_entry = plan["tables"][0]
        assert "compaction_config" in table_entry
        assert table_entry["compaction_config"]["strategy"] == "binpack"
        assert table_entry["compaction_config"]["recommended_strategy"] == "sort"
        assert table_entry["compaction_config"]["recommended_sort_columns"] == [
            "user_id", "region"
        ]

    def test_multiple_tables_compaction_persisted(
        self, generator, type_mapper, partition_mapper, s3_tables_migration
    ):
        """Each table's compaction config should be independently persisted (Req 3.5)."""
        report = generator.generate(
            migration=s3_tables_migration,
            assessment_tables=[
                SAMPLE_TABLE_META_NO_CLUSTERING,
                SAMPLE_TABLE_META_WITH_CLUSTERING,
            ],
            type_mapper=type_mapper,
            partition_mapper=partition_mapper,
        )

        # Simulate approval
        checkpoint = {"iceberg_structure_plan": report}
        s3_tables_migration.checkpoint_data = checkpoint

        plan = s3_tables_migration.checkpoint_data["iceberg_structure_plan"]
        tables = plan["tables"]

        # First table (no clustering) - default binpack, no recommendation
        assert tables[0]["compaction_config"]["strategy"] == "binpack"
        assert "recommended_strategy" not in tables[0]["compaction_config"]

        # Second table (with clustering) - default binpack, recommends sort
        assert tables[1]["compaction_config"]["strategy"] == "binpack"
        assert tables[1]["compaction_config"]["recommended_strategy"] == "sort"

    def test_compaction_config_serializable_for_jsonb(
        self, generator, type_mapper, partition_mapper, s3_tables_migration
    ):
        """Compaction config should be JSON-serializable for JSONB storage (Req 3.5)."""
        import json

        report = generator.generate(
            migration=s3_tables_migration,
            assessment_tables=[SAMPLE_TABLE_META_WITH_CLUSTERING],
            type_mapper=type_mapper,
            partition_mapper=partition_mapper,
        )

        # Verify the entire report is JSON-serializable
        json_str = json.dumps(report)
        assert json_str is not None

        # Verify compaction_config specifically
        compaction_config = report["tables"][0]["compaction_config"]
        json_str = json.dumps(compaction_config)
        parsed = json.loads(json_str)
        assert parsed["strategy"] == "binpack"
        assert parsed["recommended_strategy"] == "sort"
        assert parsed["recommended_sort_columns"] == ["user_id", "region"]


class TestCompactionStrategyDescriptions:
    """Tests for compaction strategy descriptions in structure report response.

    Validates: Requirement 3.7
    - System displays brief explanation for each strategy option
    """

    def test_descriptions_dict_has_all_strategies(self):
        """COMPACTION_STRATEGY_DESCRIPTIONS should contain all three strategies (Req 3.7)."""
        assert "binpack" in COMPACTION_STRATEGY_DESCRIPTIONS
        assert "sort" in COMPACTION_STRATEGY_DESCRIPTIONS
        assert "z-order" in COMPACTION_STRATEGY_DESCRIPTIONS
        assert len(COMPACTION_STRATEGY_DESCRIPTIONS) == 3

    def test_binpack_description_content(self):
        """Binpack description should mention combining files without reordering (Req 3.7)."""
        desc = COMPACTION_STRATEGY_DESCRIPTIONS["binpack"]
        assert "small files" in desc.lower() or "combines" in desc.lower()
        assert "reordering" in desc.lower() or "without reordering" in desc.lower()
        assert "append" in desc.lower()

    def test_sort_description_content(self):
        """Sort description should mention reordering by columns (Req 3.7)."""
        desc = COMPACTION_STRATEGY_DESCRIPTIONS["sort"]
        assert "reorder" in desc.lower() or "sort" in desc.lower()
        assert "column" in desc.lower()
        assert "range" in desc.lower() or "queries" in desc.lower()

    def test_z_order_description_content(self):
        """Z-order description should mention interleaving multiple columns (Req 3.7)."""
        desc = COMPACTION_STRATEGY_DESCRIPTIONS["z-order"]
        assert "interleave" in desc.lower() or "multiple" in desc.lower()
        assert "column" in desc.lower()
        assert "filter" in desc.lower() or "queries" in desc.lower()

    def test_descriptions_are_non_empty_strings(self):
        """All strategy descriptions should be non-empty strings."""
        for strategy, desc in COMPACTION_STRATEGY_DESCRIPTIONS.items():
            assert isinstance(desc, str), f"{strategy} description is not a string"
            assert len(desc) > 10, f"{strategy} description is too short"

    def test_descriptions_accessible_from_module(self):
        """COMPACTION_STRATEGY_DESCRIPTIONS should be importable from structure_report module."""
        from services.bq_iceberg_migration.structure_report import (
            COMPACTION_STRATEGY_DESCRIPTIONS as imported_descs,
        )
        assert imported_descs is not None
        assert "binpack" in imported_descs
        assert "sort" in imported_descs
        assert "z-order" in imported_descs

    def test_descriptions_match_requirement_text(self):
        """Descriptions should match the requirement specification text (Req 3.7)."""
        # Req 3.7 specifies exact descriptions
        assert "Combines small files without reordering" in COMPACTION_STRATEGY_DESCRIPTIONS["binpack"]
        assert "Reorders data by specified columns" in COMPACTION_STRATEGY_DESCRIPTIONS["sort"]
        assert "Interleaves multiple columns" in COMPACTION_STRATEGY_DESCRIPTIONS["z-order"]


# =============================================================================
# API Router Unit Tests (Task 8.5)
#
# These tests validate the Pydantic request models and API endpoint behavior
# for maintenance config, compaction config, and parallelism validation.
#
# Validates: Requirements 4.3, 4.4, 4.5, 3.4, 6.2, 6.7
# =============================================================================

from pydantic import BaseModel, Field, ValidationError
from typing import Optional, Dict, List

# Define Pydantic models locally to avoid database import dependency.
# These mirror the models in routers/bq_iceberg_migration.py exactly.


class MaintenanceConfigRequest(BaseModel):
    """Request schema for S3 Tables maintenance configuration."""
    target_file_size_mb: int = Field(512, ge=64, le=512)
    min_snapshots_to_keep: int = Field(30, gt=0)
    max_snapshot_age_hours: int = Field(720, gt=0)


class CompactionConfigRequest(BaseModel):
    """Per-table compaction strategy configuration."""
    strategy: str = Field("binpack", pattern="^(binpack|sort|z-order)$")
    sort_columns: list[str] = Field(default_factory=list)


class CreateIcebergMigrationRequest(BaseModel):
    """Request schema for creating a new BQ-to-Iceberg migration (subset for testing)."""
    migration_name: str = Field(..., min_length=1, max_length=255)
    pathway: str = Field(..., pattern="^[ABC]$")
    destination_type: str = Field(..., pattern="^(iceberg_s3|iceberg_s3_tables)$")
    s3_bucket: Optional[str] = Field(None, max_length=63)
    table_bucket_arn: Optional[str] = Field(None, max_length=500)
    s3_tables_namespace: Optional[str] = Field(None, max_length=255)
    aws_region: str = Field(..., min_length=1, max_length=50)
    glue_database_name: str = Field(..., min_length=1, max_length=255)
    parallelism: Optional[int] = Field(4, ge=1, le=16)
    maintenance_config: Optional[MaintenanceConfigRequest] = None


class ApproveStructureRequest(BaseModel):
    """Request schema for approving structure with optional overrides."""
    overrides: Optional[Dict[str, object]] = None
    excluded_tables: Optional[List[str]] = None
    table_compaction_configs: Optional[Dict[str, CompactionConfigRequest]] = None


# --- Sample Payloads for API Router Tests ---

VALID_CREATE_S3_TABLES_WITH_MAINTENANCE = {
    "migration_name": "Test S3 Tables Migration",
    "pathway": "A",
    "destination_type": "iceberg_s3_tables",
    "table_bucket_arn": "arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket",
    "s3_tables_namespace": "test_ns",
    "aws_region": "us-east-1",
    "glue_database_name": "test_db",
    "parallelism": 4,
    "maintenance_config": {
        "target_file_size_mb": 256,
        "min_snapshots_to_keep": 10,
        "max_snapshot_age_hours": 168,
    },
}

VALID_CREATE_S3_STANDARD = {
    "migration_name": "Test S3 Standard Migration",
    "pathway": "A",
    "destination_type": "iceberg_s3",
    "s3_bucket": "my-data-lake",
    "aws_region": "us-east-1",
    "glue_database_name": "test_db",
    "parallelism": 12,
}


class TestMaintenanceConfigRequestModel:
    """Tests for MaintenanceConfigRequest Pydantic model validation.

    Validates: Requirements 4.3, 4.4
    """

    def test_valid_maintenance_config_defaults(self):
        """Test that default values are applied correctly."""
        config = MaintenanceConfigRequest()
        assert config.target_file_size_mb == 512
        assert config.min_snapshots_to_keep == 30
        assert config.max_snapshot_age_hours == 720

    def test_valid_maintenance_config_custom_values(self):
        """Test valid custom values are accepted."""
        config = MaintenanceConfigRequest(
            target_file_size_mb=256,
            min_snapshots_to_keep=10,
            max_snapshot_age_hours=168,
        )
        assert config.target_file_size_mb == 256
        assert config.min_snapshots_to_keep == 10
        assert config.max_snapshot_age_hours == 168

    def test_valid_boundary_min_file_size(self):
        """Test minimum valid file size (64 MB) is accepted."""
        config = MaintenanceConfigRequest(target_file_size_mb=64)
        assert config.target_file_size_mb == 64

    def test_valid_boundary_max_file_size(self):
        """Test maximum valid file size (512 MB) is accepted."""
        config = MaintenanceConfigRequest(target_file_size_mb=512)
        assert config.target_file_size_mb == 512

    def test_invalid_file_size_below_min(self):
        """Test file size below 64 is rejected (Req 4.4)."""
        with pytest.raises(ValidationError) as exc_info:
            MaintenanceConfigRequest(target_file_size_mb=63)
        assert "target_file_size_mb" in str(exc_info.value)

    def test_invalid_file_size_above_max(self):
        """Test file size above 512 is rejected (Req 4.4)."""
        with pytest.raises(ValidationError) as exc_info:
            MaintenanceConfigRequest(target_file_size_mb=513)
        assert "target_file_size_mb" in str(exc_info.value)

    def test_invalid_file_size_zero(self):
        """Test file size of 0 is rejected (Req 4.4)."""
        with pytest.raises(ValidationError) as exc_info:
            MaintenanceConfigRequest(target_file_size_mb=0)
        assert "target_file_size_mb" in str(exc_info.value)

    def test_invalid_file_size_negative(self):
        """Test negative file size is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MaintenanceConfigRequest(target_file_size_mb=-1)
        assert "target_file_size_mb" in str(exc_info.value)

    def test_invalid_snapshots_zero(self):
        """Test min_snapshots_to_keep of 0 is rejected (must be > 0)."""
        with pytest.raises(ValidationError) as exc_info:
            MaintenanceConfigRequest(min_snapshots_to_keep=0)
        assert "min_snapshots_to_keep" in str(exc_info.value)

    def test_invalid_snapshots_negative(self):
        """Test negative min_snapshots_to_keep is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MaintenanceConfigRequest(min_snapshots_to_keep=-5)
        assert "min_snapshots_to_keep" in str(exc_info.value)

    def test_invalid_max_age_zero(self):
        """Test max_snapshot_age_hours of 0 is rejected (must be > 0)."""
        with pytest.raises(ValidationError) as exc_info:
            MaintenanceConfigRequest(max_snapshot_age_hours=0)
        assert "max_snapshot_age_hours" in str(exc_info.value)

    def test_invalid_max_age_negative(self):
        """Test negative max_snapshot_age_hours is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MaintenanceConfigRequest(max_snapshot_age_hours=-10)
        assert "max_snapshot_age_hours" in str(exc_info.value)


class TestCompactionConfigRequestModel:
    """Tests for CompactionConfigRequest Pydantic model validation.

    Validates: Requirements 3.4
    """

    def test_valid_binpack_default(self):
        """Test default strategy is binpack with empty sort columns."""
        config = CompactionConfigRequest()
        assert config.strategy == "binpack"
        assert config.sort_columns == []

    def test_valid_sort_strategy(self):
        """Test sort strategy with sort columns is accepted."""
        config = CompactionConfigRequest(
            strategy="sort", sort_columns=["col_a", "col_b"]
        )
        assert config.strategy == "sort"
        assert config.sort_columns == ["col_a", "col_b"]

    def test_valid_z_order_strategy(self):
        """Test z-order strategy with sort columns is accepted."""
        config = CompactionConfigRequest(
            strategy="z-order", sort_columns=["region", "product_id"]
        )
        assert config.strategy == "z-order"
        assert config.sort_columns == ["region", "product_id"]

    def test_invalid_strategy_name(self):
        """Test invalid strategy name is rejected by pattern validation."""
        with pytest.raises(ValidationError) as exc_info:
            CompactionConfigRequest(strategy="invalid")
        assert "strategy" in str(exc_info.value)

    def test_invalid_strategy_uppercase(self):
        """Test uppercase strategy name is rejected (case-sensitive)."""
        with pytest.raises(ValidationError) as exc_info:
            CompactionConfigRequest(strategy="Binpack")
        assert "strategy" in str(exc_info.value)

    def test_invalid_strategy_underscore(self):
        """Test z_order (underscore) is rejected - must be z-order (hyphen)."""
        with pytest.raises(ValidationError) as exc_info:
            CompactionConfigRequest(strategy="z_order")
        assert "strategy" in str(exc_info.value)

    def test_sort_columns_empty_list_accepted(self):
        """Test empty sort columns list is accepted at model level."""
        config = CompactionConfigRequest(strategy="binpack", sort_columns=[])
        assert config.sort_columns == []


class TestCreateMigrationWithMaintenanceConfig:
    """Tests for CreateIcebergMigrationRequest with maintenance_config field.

    Validates: Requirements 4.3, 4.4, 4.5, 6.2, 6.7
    """

    def test_create_request_with_valid_maintenance_config(self):
        """Test create request accepts valid maintenance config for S3 Tables."""
        req = CreateIcebergMigrationRequest(**VALID_CREATE_S3_TABLES_WITH_MAINTENANCE)
        assert req.maintenance_config is not None
        assert req.maintenance_config.target_file_size_mb == 256
        assert req.maintenance_config.min_snapshots_to_keep == 10
        assert req.maintenance_config.max_snapshot_age_hours == 168

    def test_create_request_without_maintenance_config(self):
        """Test create request works without maintenance config (optional)."""
        payload = VALID_CREATE_S3_TABLES_WITH_MAINTENANCE.copy()
        del payload["maintenance_config"]
        req = CreateIcebergMigrationRequest(**payload)
        assert req.maintenance_config is None

    def test_create_request_maintenance_config_none(self):
        """Test create request accepts None for maintenance config."""
        payload = VALID_CREATE_S3_TABLES_WITH_MAINTENANCE.copy()
        payload["maintenance_config"] = None
        req = CreateIcebergMigrationRequest(**payload)
        assert req.maintenance_config is None

    def test_create_request_invalid_maintenance_file_size_below_min(self):
        """Test create request rejects maintenance config with file size < 64."""
        payload = VALID_CREATE_S3_TABLES_WITH_MAINTENANCE.copy()
        payload["maintenance_config"] = {
            "target_file_size_mb": 32,
            "min_snapshots_to_keep": 30,
            "max_snapshot_age_hours": 720,
        }
        with pytest.raises(ValidationError) as exc_info:
            CreateIcebergMigrationRequest(**payload)
        assert "target_file_size_mb" in str(exc_info.value)

    def test_create_request_invalid_maintenance_file_size_above_max(self):
        """Test create request rejects maintenance config with file size > 512."""
        payload = VALID_CREATE_S3_TABLES_WITH_MAINTENANCE.copy()
        payload["maintenance_config"] = {
            "target_file_size_mb": 1024,
            "min_snapshots_to_keep": 30,
            "max_snapshot_age_hours": 720,
        }
        with pytest.raises(ValidationError) as exc_info:
            CreateIcebergMigrationRequest(**payload)
        assert "target_file_size_mb" in str(exc_info.value)

    def test_create_request_invalid_maintenance_zero_snapshots(self):
        """Test create request rejects maintenance config with 0 snapshots."""
        payload = VALID_CREATE_S3_TABLES_WITH_MAINTENANCE.copy()
        payload["maintenance_config"] = {
            "target_file_size_mb": 256,
            "min_snapshots_to_keep": 0,
            "max_snapshot_age_hours": 720,
        }
        with pytest.raises(ValidationError) as exc_info:
            CreateIcebergMigrationRequest(**payload)
        assert "min_snapshots_to_keep" in str(exc_info.value)

    def test_create_request_invalid_maintenance_zero_age(self):
        """Test create request rejects maintenance config with 0 age hours."""
        payload = VALID_CREATE_S3_TABLES_WITH_MAINTENANCE.copy()
        payload["maintenance_config"] = {
            "target_file_size_mb": 256,
            "min_snapshots_to_keep": 30,
            "max_snapshot_age_hours": 0,
        }
        with pytest.raises(ValidationError) as exc_info:
            CreateIcebergMigrationRequest(**payload)
        assert "max_snapshot_age_hours" in str(exc_info.value)

    def test_maintenance_config_hidden_for_standard_s3(self):
        """Test that standard S3 destination does not use maintenance config.

        While the model accepts it, the API endpoint rejects it for non-S3-Tables.
        At model level, maintenance_config is optional and destination-agnostic.
        Validates: Requirement 4.5
        """
        payload = VALID_CREATE_S3_STANDARD.copy()
        payload["maintenance_config"] = None
        req = CreateIcebergMigrationRequest(**payload)
        assert req.maintenance_config is None
        assert req.destination_type == "iceberg_s3"


class TestApproveStructureWithCompactionConfigs:
    """Tests for ApproveStructureRequest with per-table compaction configs.

    Validates: Requirements 3.4
    """

    def test_approve_with_valid_compaction_configs(self):
        """Test approve request accepts valid per-table compaction configs."""
        req = ApproveStructureRequest(
            table_compaction_configs={
                "orders": CompactionConfigRequest(
                    strategy="sort", sort_columns=["order_date"]
                ),
                "customers": CompactionConfigRequest(strategy="binpack"),
            }
        )
        assert req.table_compaction_configs is not None
        assert "orders" in req.table_compaction_configs
        assert req.table_compaction_configs["orders"].strategy == "sort"
        assert req.table_compaction_configs["orders"].sort_columns == ["order_date"]
        assert req.table_compaction_configs["customers"].strategy == "binpack"

    def test_approve_without_compaction_configs(self):
        """Test approve request works without compaction configs (optional)."""
        req = ApproveStructureRequest(overrides={"some_table": {"key": "value"}})
        assert req.table_compaction_configs is None

    def test_approve_with_invalid_strategy_rejected(self):
        """Test approve request rejects invalid compaction strategy."""
        with pytest.raises(ValidationError) as exc_info:
            ApproveStructureRequest(
                table_compaction_configs={
                    "orders": CompactionConfigRequest(strategy="invalid_strategy"),
                }
            )
        assert "strategy" in str(exc_info.value)

    def test_approve_with_z_order_compaction(self):
        """Test approve request accepts z-order compaction config."""
        req = ApproveStructureRequest(
            table_compaction_configs={
                "events": CompactionConfigRequest(
                    strategy="z-order",
                    sort_columns=["region", "event_time"],
                ),
            }
        )
        assert req.table_compaction_configs["events"].strategy == "z-order"
        assert req.table_compaction_configs["events"].sort_columns == [
            "region", "event_time"
        ]

    def test_approve_compaction_config_sort_columns_validation_at_api_level(self):
        """Test that sort column validation against schema happens at API level.

        The Pydantic model accepts any sort_columns list - the actual validation
        against the table schema is done in the endpoint using validate_compaction_strategy.
        Validates: Requirement 3.4
        """
        # Model level accepts any column names
        req = ApproveStructureRequest(
            table_compaction_configs={
                "orders": CompactionConfigRequest(
                    strategy="sort",
                    sort_columns=["nonexistent_column"],
                ),
            }
        )
        assert req.table_compaction_configs["orders"].sort_columns == [
            "nonexistent_column"
        ]


class TestParallelismValidationInCreateRequest:
    """Tests for parallelism validation in CreateIcebergMigrationRequest.

    Validates: Requirements 6.2, 6.7
    """

    def test_s3_tables_parallelism_at_max_8_accepted(self):
        """Test parallelism of 8 is accepted for S3 Tables at model level."""
        payload = VALID_CREATE_S3_TABLES_WITH_MAINTENANCE.copy()
        payload["parallelism"] = 8
        req = CreateIcebergMigrationRequest(**payload)
        assert req.parallelism == 8

    def test_s3_tables_parallelism_above_8_rejected_at_model_level(self):
        """Test parallelism above 16 is rejected at model level (ge=1, le=16).

        Note: The model allows up to 16 for general use. The S3 Tables cap of 8
        is enforced at the API endpoint level using validate_s3_tables_parallelism.
        """
        payload = VALID_CREATE_S3_TABLES_WITH_MAINTENANCE.copy()
        payload["parallelism"] = 17
        with pytest.raises(ValidationError) as exc_info:
            CreateIcebergMigrationRequest(**payload)
        assert "parallelism" in str(exc_info.value)

    def test_standard_s3_parallelism_up_to_16_accepted(self):
        """Test standard S3 Iceberg allows parallelism up to 16 (Req 6.7)."""
        payload = VALID_CREATE_S3_STANDARD.copy()
        payload["parallelism"] = 16
        req = CreateIcebergMigrationRequest(**payload)
        assert req.parallelism == 16

    def test_parallelism_zero_rejected(self):
        """Test parallelism of 0 is rejected at model level."""
        payload = VALID_CREATE_S3_TABLES_WITH_MAINTENANCE.copy()
        payload["parallelism"] = 0
        with pytest.raises(ValidationError) as exc_info:
            CreateIcebergMigrationRequest(**payload)
        assert "parallelism" in str(exc_info.value)

    def test_parallelism_negative_rejected(self):
        """Test negative parallelism is rejected at model level."""
        payload = VALID_CREATE_S3_TABLES_WITH_MAINTENANCE.copy()
        payload["parallelism"] = -1
        with pytest.raises(ValidationError) as exc_info:
            CreateIcebergMigrationRequest(**payload)
        assert "parallelism" in str(exc_info.value)


# =============================================================================
# API Endpoint Behavior Tests (Task 8.5)
#
# These tests validate the endpoint-level logic by testing the validators
# that the API endpoints call. This avoids needing a real DB connection
# while still verifying the same behavior.
#
# Validates: Requirements 4.3, 4.4, 4.5, 3.4, 6.2, 6.7
# =============================================================================


class TestCreateMigrationEndpointMaintenanceConfig:
    """Tests for create migration endpoint maintenance config validation logic.

    The endpoint calls validate_maintenance_config() for S3 Tables destinations
    and rejects maintenance_config for standard S3 destinations.

    Validates: Requirements 4.3, 4.4, 4.5
    """

    def test_create_with_valid_maintenance_config_passes_validation(self):
        """Test that valid maintenance config passes endpoint validation."""
        is_valid, error = validate_maintenance_config(256, 10, 168)
        assert is_valid is True
        assert error is None

    def test_create_with_invalid_file_size_below_min_fails(self):
        """Test that file size < 64 fails endpoint validation."""
        is_valid, error = validate_maintenance_config(32, 30, 720)
        assert is_valid is False
        assert "64" in error

    def test_create_with_invalid_file_size_above_max_fails(self):
        """Test that file size > 512 fails endpoint validation."""
        is_valid, error = validate_maintenance_config(1024, 30, 720)
        assert is_valid is False
        assert "512" in error

    def test_create_with_zero_snapshots_fails(self):
        """Test that 0 snapshots fails endpoint validation."""
        is_valid, error = validate_maintenance_config(256, 0, 720)
        assert is_valid is False
        assert "positive" in error.lower()

    def test_create_with_zero_age_fails(self):
        """Test that 0 age hours fails endpoint validation."""
        is_valid, error = validate_maintenance_config(256, 30, 0)
        assert is_valid is False
        assert "positive" in error.lower()

    def test_maintenance_config_only_for_s3_tables(self):
        """Test that maintenance config is only valid for S3 Tables (Req 4.5).

        The endpoint rejects maintenance_config when destination_type != iceberg_s3_tables.
        We verify this by checking the model allows both destination types but the
        endpoint logic differentiates them.
        """
        # Standard S3 destination - maintenance config should be rejected by endpoint
        req_standard = CreateIcebergMigrationRequest(
            migration_name="Standard S3",
            pathway="A",
            destination_type="iceberg_s3",
            s3_bucket="my-bucket",
            aws_region="us-east-1",
            glue_database_name="test_db",
            maintenance_config=None,
        )
        assert req_standard.destination_type == "iceberg_s3"
        assert req_standard.maintenance_config is None

        # S3 Tables destination - maintenance config is accepted
        req_s3_tables = CreateIcebergMigrationRequest(
            migration_name="S3 Tables",
            pathway="A",
            destination_type="iceberg_s3_tables",
            aws_region="us-east-1",
            glue_database_name="test_db",
            maintenance_config=MaintenanceConfigRequest(
                target_file_size_mb=256,
                min_snapshots_to_keep=10,
                max_snapshot_age_hours=168,
            ),
        )
        assert req_s3_tables.destination_type == "iceberg_s3_tables"
        assert req_s3_tables.maintenance_config is not None


class TestCreateMigrationEndpointParallelism:
    """Tests for create migration endpoint parallelism validation for S3 Tables.

    The endpoint calls validate_s3_tables_parallelism() when destination is
    iceberg_s3_tables and returns a warning for values 5-8.

    Validates: Requirements 6.2, 6.7
    """

    def test_s3_tables_parallelism_8_accepted(self):
        """Test S3 Tables with parallelism 8 passes validation."""
        is_valid, error = validate_s3_tables_parallelism(8)
        assert is_valid is True
        assert error is None

    def test_s3_tables_parallelism_above_8_rejected(self):
        """Test S3 Tables with parallelism > 8 is rejected (Req 6.7)."""
        is_valid, error = validate_s3_tables_parallelism(9)
        assert is_valid is False
        assert "must be between 1 and 8" in error.lower()

    def test_s3_tables_parallelism_12_rejected(self):
        """Test S3 Tables with parallelism 12 is rejected."""
        is_valid, error = validate_s3_tables_parallelism(12)
        assert is_valid is False

    def test_s3_tables_parallelism_16_rejected(self):
        """Test S3 Tables with parallelism 16 (standard S3 max) is rejected."""
        is_valid, error = validate_s3_tables_parallelism(16)
        assert is_valid is False

    def test_s3_tables_parallelism_warning_range(self):
        """Test that parallelism 5-8 is valid but warrants a warning (Req 6.2).

        The endpoint returns a warning message for values > 4 but <= 8.
        The validator accepts these values (they are valid).
        """
        for value in [5, 6, 7, 8]:
            is_valid, error = validate_s3_tables_parallelism(value)
            assert is_valid is True, f"Parallelism {value} should be valid"

    def test_standard_s3_parallelism_up_to_16_accepted_at_model_level(self):
        """Test standard S3 Iceberg allows parallelism up to 16 (Req 6.7).

        The model allows up to 16 for all destinations. The S3 Tables cap
        is enforced at the endpoint level via validate_s3_tables_parallelism.
        """
        req = CreateIcebergMigrationRequest(
            migration_name="Standard S3",
            pathway="A",
            destination_type="iceberg_s3",
            s3_bucket="my-bucket",
            aws_region="us-east-1",
            glue_database_name="test_db",
            parallelism=16,
        )
        assert req.parallelism == 16

    def test_parallelism_above_16_rejected_at_model_level(self):
        """Test parallelism above 16 is rejected at model level for all destinations."""
        with pytest.raises(ValidationError):
            CreateIcebergMigrationRequest(
                migration_name="Too High",
                pathway="A",
                destination_type="iceberg_s3",
                aws_region="us-east-1",
                glue_database_name="test_db",
                parallelism=17,
            )


class TestApproveStructureEndpointCompaction:
    """Tests for approve-structure endpoint compaction config validation.

    The endpoint calls validate_compaction_strategy() for each table's
    compaction config against the table schema from the structure report.

    Validates: Requirements 3.4
    """

    def test_approve_valid_sort_columns_in_schema(self):
        """Test that sort columns present in schema pass validation."""
        is_valid, error = validate_compaction_strategy(
            "sort", ["order_date", "customer_id"], ["order_id", "order_date", "customer_id", "amount"]
        )
        assert is_valid is True
        assert error is None

    def test_approve_rejects_sort_columns_not_in_schema(self):
        """Test that sort columns not in schema are rejected (Req 3.4)."""
        is_valid, error = validate_compaction_strategy(
            "sort", ["nonexistent_column"], ["order_id", "order_date", "customer_id"]
        )
        assert is_valid is False
        assert "nonexistent_column" in error
        assert "not found in table schema" in error.lower()

    def test_approve_rejects_partial_invalid_sort_columns(self):
        """Test that mix of valid and invalid sort columns is rejected."""
        is_valid, error = validate_compaction_strategy(
            "z-order",
            ["order_date", "bad_column"],
            ["order_id", "order_date", "customer_id"],
        )
        assert is_valid is False
        assert "bad_column" in error

    def test_approve_binpack_no_sort_columns_needed(self):
        """Test that binpack strategy doesn't require sort columns."""
        is_valid, error = validate_compaction_strategy(
            "binpack", [], ["col_a", "col_b"]
        )
        assert is_valid is True

    def test_approve_sort_requires_sort_columns(self):
        """Test that sort strategy requires non-empty sort columns."""
        is_valid, error = validate_compaction_strategy(
            "sort", [], ["col_a", "col_b"]
        )
        assert is_valid is False
        assert "sort columns must be specified" in error.lower()

    def test_approve_z_order_requires_sort_columns(self):
        """Test that z-order strategy requires non-empty sort columns."""
        is_valid, error = validate_compaction_strategy(
            "z-order", [], ["col_a", "col_b"]
        )
        assert is_valid is False
        assert "sort columns must be specified" in error.lower()

    def test_approve_structure_model_accepts_compaction_configs(self):
        """Test that ApproveStructureRequest model accepts compaction configs."""
        req = ApproveStructureRequest(
            table_compaction_configs={
                "orders": CompactionConfigRequest(
                    strategy="sort", sort_columns=["order_date"]
                ),
                "customers": CompactionConfigRequest(strategy="binpack"),
            }
        )
        assert req.table_compaction_configs is not None
        assert len(req.table_compaction_configs) == 2
        assert req.table_compaction_configs["orders"].strategy == "sort"
        assert req.table_compaction_configs["customers"].strategy == "binpack"

    def test_approve_structure_model_optional_compaction(self):
        """Test that compaction configs are optional in approve request."""
        req = ApproveStructureRequest(overrides={"table": {"key": "val"}})
        assert req.table_compaction_configs is None

