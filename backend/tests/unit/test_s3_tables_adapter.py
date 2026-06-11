"""
Unit tests for S3TablesAdapter service.

Tests namespace validation, namespace creation, table creation,
MaintenanceConfig dataclass, derive_glue_id, and error handling
for AWS S3 Tables (managed Iceberg) operations.
"""

import pytest
from unittest.mock import MagicMock, PropertyMock

from services.bq_iceberg_migration.s3_tables_adapter import (
    S3TablesAdapter,
    MaintenanceConfig,
)


# --- Sample payloads ---

VALID_TABLE_BUCKET_ARN = "arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket"
VALID_AWS_REGION = "us-east-1"

VALID_NAMESPACE_NAMES = [
    "analytics",
    "my_namespace",
    "_private",
    "a",
    "data_warehouse_2025",
    "ns" + "_x" * 126,  # 254 chars
]

INVALID_NAMESPACE_NAMES = [
    "",                          # empty
    "123invalid",                # starts with number
    "UPPERCASE",                 # uppercase letters
    "has-dashes",                # dashes not allowed
    "has spaces",                # spaces not allowed
    "has.dots",                  # dots not allowed
    "a" * 256,                   # exceeds 255 chars
    "special!chars",             # special characters
    "namespace/path",            # slashes not allowed
]

VALID_TABLE_NAMES = [
    "users",
    "order_items",
    "_internal_table",
    "t",
    "table_2025_data",
]

INVALID_TABLE_NAMES = [
    "",                          # empty
    "1starts_with_number",       # starts with number
    "HAS_UPPER",                 # uppercase
    "has-dashes",                # dashes
    "has spaces",                # spaces
    "a" * 256,                   # exceeds 255 chars
]


def _make_s3tables_client(
    create_namespace_side_effect=None,
    create_table_response=None,
    get_table_response=None,
    conflict_exception_class=None,
):
    """Create a mock S3Tables client with configurable behavior."""
    client = MagicMock()

    # Set up exceptions namespace
    exceptions = MagicMock()
    if conflict_exception_class is None:
        conflict_exception_class = type("ConflictException", (Exception,), {})
    exceptions.ConflictException = conflict_exception_class
    client.exceptions = exceptions

    if create_namespace_side_effect:
        client.create_namespace.side_effect = create_namespace_side_effect
    else:
        client.create_namespace.return_value = {}

    if create_table_response:
        client.create_table.return_value = create_table_response
    else:
        client.create_table.return_value = {
            "tableARN": "arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket/table/test_table",
            "versionToken": "v1",
        }

    if get_table_response:
        client.get_table.return_value = get_table_response
    else:
        client.get_table.return_value = {
            "metadataLocation": "s3://my-table-bucket/metadata/00000-abc.metadata.json",
            "name": "test_table",
            "namespace": ["analytics"],
        }

    return client


class TestValidateNamespaceName:
    """Test validate_namespace_name follows S3 Tables naming conventions."""

    def test_valid_simple_name(self):
        """Simple lowercase name should be valid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter.validate_namespace_name("analytics") is True

    def test_valid_name_with_underscores(self):
        """Name with underscores should be valid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter.validate_namespace_name("my_data_warehouse") is True

    def test_valid_name_starting_with_underscore(self):
        """Name starting with underscore should be valid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter.validate_namespace_name("_private") is True

    def test_valid_name_with_numbers(self):
        """Name with numbers (not at start) should be valid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter.validate_namespace_name("data2025") is True

    def test_valid_single_character(self):
        """Single lowercase letter should be valid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter.validate_namespace_name("a") is True

    def test_valid_max_length(self):
        """Name at exactly 255 characters should be valid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        name = "a" * 255
        assert adapter.validate_namespace_name(name) is True

    def test_invalid_empty_string(self):
        """Empty string should be invalid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter.validate_namespace_name("") is False

    def test_invalid_starts_with_number(self):
        """Name starting with a number should be invalid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter.validate_namespace_name("123invalid") is False

    def test_invalid_uppercase(self):
        """Name with uppercase letters should be invalid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter.validate_namespace_name("UPPERCASE") is False

    def test_invalid_dashes(self):
        """Name with dashes should be invalid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter.validate_namespace_name("has-dashes") is False

    def test_invalid_spaces(self):
        """Name with spaces should be invalid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter.validate_namespace_name("has spaces") is False

    def test_invalid_exceeds_max_length(self):
        """Name exceeding 255 characters should be invalid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        name = "a" * 256
        assert adapter.validate_namespace_name(name) is False

    def test_invalid_special_characters(self):
        """Name with special characters should be invalid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter.validate_namespace_name("special!chars") is False

    def test_invalid_dots(self):
        """Name with dots should be invalid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter.validate_namespace_name("has.dots") is False

    @pytest.mark.parametrize("name", VALID_NAMESPACE_NAMES)
    def test_all_valid_names(self, name):
        """All names in VALID_NAMESPACE_NAMES should pass validation."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter.validate_namespace_name(name) is True

    @pytest.mark.parametrize("name", INVALID_NAMESPACE_NAMES)
    def test_all_invalid_names(self, name):
        """All names in INVALID_NAMESPACE_NAMES should fail validation."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter.validate_namespace_name(name) is False


class TestEnsureNamespace:
    """Test ensure_namespace creates namespace or handles existing."""

    def test_creates_namespace_successfully(self):
        """Should call create_namespace with correct parameters."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        adapter.ensure_namespace("analytics")

        client.create_namespace.assert_called_once_with(
            tableBucketARN=VALID_TABLE_BUCKET_ARN,
            namespace=["analytics"],
        )

    def test_handles_existing_namespace(self):
        """Should not raise when namespace already exists (ConflictException)."""
        conflict_exc = type("ConflictException", (Exception,), {})
        client = _make_s3tables_client(
            create_namespace_side_effect=conflict_exc(),
            conflict_exception_class=conflict_exc,
        )
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        # Should not raise
        adapter.ensure_namespace("analytics")

    def test_raises_value_error_for_invalid_name(self):
        """Should raise ValueError for invalid namespace names."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        with pytest.raises(ValueError, match="Invalid namespace name"):
            adapter.ensure_namespace("123invalid")

    def test_raises_value_error_for_empty_name(self):
        """Should raise ValueError for empty namespace name."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        with pytest.raises(ValueError, match="Invalid namespace name"):
            adapter.ensure_namespace("")

    def test_raises_runtime_error_on_api_failure(self):
        """Should raise RuntimeError when S3 Tables API fails."""
        client = _make_s3tables_client(
            create_namespace_side_effect=Exception("Access denied"),
        )
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        with pytest.raises(RuntimeError, match="Failed to create namespace"):
            adapter.ensure_namespace("analytics")

    def test_does_not_call_api_for_invalid_name(self):
        """Should not call the API if the name is invalid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        with pytest.raises(ValueError):
            adapter.ensure_namespace("INVALID")

        client.create_namespace.assert_not_called()


class TestCreateTable:
    """Test create_table creates table and returns metadata location."""

    def test_creates_table_successfully(self):
        """Should create table and return metadata location dict."""
        client = _make_s3tables_client(
            create_table_response={
                "tableARN": "arn:aws:s3tables:us-east-1:123456789012:bucket/b/table/t",
                "versionToken": "v1",
            },
            get_table_response={
                "metadataLocation": "s3://bucket/metadata/00000.metadata.json",
                "name": "users",
                "namespace": ["analytics"],
            },
        )
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        schema = MagicMock()
        partition_spec = MagicMock()

        result = adapter.create_table("analytics", "users", schema, partition_spec)

        assert result["namespace"] == "analytics"
        assert result["table_name"] == "users"
        assert result["metadata_location"] == "s3://bucket/metadata/00000.metadata.json"
        assert "table_arn" in result

    def test_calls_create_table_api(self):
        """Should call the S3 Tables create_table API with correct params."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        schema = MagicMock()
        partition_spec = MagicMock()

        adapter.create_table("analytics", "users", schema, partition_spec)

        client.create_table.assert_called_once_with(
            tableBucketARN=VALID_TABLE_BUCKET_ARN,
            namespace="analytics",
            name="users",
            format="ICEBERG",
        )

    def test_handles_existing_table(self):
        """Should return metadata location when table already exists."""
        conflict_exc = type("ConflictException", (Exception,), {})
        client = _make_s3tables_client(conflict_exception_class=conflict_exc)
        client.create_table.side_effect = conflict_exc()
        client.get_table.return_value = {
            "metadataLocation": "s3://bucket/metadata/existing.metadata.json",
            "name": "users",
            "namespace": ["analytics"],
        }
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        schema = MagicMock()
        partition_spec = MagicMock()

        result = adapter.create_table("analytics", "users", schema, partition_spec)

        assert result["metadata_location"] == "s3://bucket/metadata/existing.metadata.json"
        assert result["namespace"] == "analytics"
        assert result["table_name"] == "users"

    def test_raises_value_error_for_invalid_namespace(self):
        """Should raise ValueError if namespace name is invalid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        schema = MagicMock()
        partition_spec = MagicMock()

        with pytest.raises(ValueError, match="Invalid namespace name"):
            adapter.create_table("123bad", "users", schema, partition_spec)

    def test_raises_value_error_for_invalid_table_name(self):
        """Should raise ValueError if table name is invalid."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        schema = MagicMock()
        partition_spec = MagicMock()

        with pytest.raises(ValueError, match="Invalid table name"):
            adapter.create_table("analytics", "123bad", schema, partition_spec)

    def test_raises_runtime_error_on_api_failure(self):
        """Should raise RuntimeError when S3 Tables API fails."""
        client = _make_s3tables_client()
        client.create_table.side_effect = Exception("Service unavailable")
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        schema = MagicMock()
        partition_spec = MagicMock()

        with pytest.raises(RuntimeError, match="Failed to create table"):
            adapter.create_table("analytics", "users", schema, partition_spec)

    def test_does_not_call_api_for_invalid_namespace(self):
        """Should not call the API if namespace validation fails."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        schema = MagicMock()
        partition_spec = MagicMock()

        with pytest.raises(ValueError):
            adapter.create_table("BAD", "users", schema, partition_spec)

        client.create_table.assert_not_called()

    def test_does_not_call_api_for_invalid_table_name(self):
        """Should not call the API if table name validation fails."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        schema = MagicMock()
        partition_spec = MagicMock()

        with pytest.raises(ValueError):
            adapter.create_table("analytics", "BAD-NAME", schema, partition_spec)

        client.create_table.assert_not_called()

    @pytest.mark.parametrize("table_name", VALID_TABLE_NAMES)
    def test_accepts_valid_table_names(self, table_name):
        """All valid table names should be accepted."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        schema = MagicMock()
        partition_spec = MagicMock()

        # Should not raise
        result = adapter.create_table("analytics", table_name, schema, partition_spec)
        assert result["table_name"] == table_name

    @pytest.mark.parametrize("table_name", INVALID_TABLE_NAMES)
    def test_rejects_invalid_table_names(self, table_name):
        """All invalid table names should be rejected."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        schema = MagicMock()
        partition_spec = MagicMock()

        with pytest.raises(ValueError):
            adapter.create_table("analytics", table_name, schema, partition_spec)


class TestInitialization:
    """Test S3TablesAdapter initialization."""

    def test_stores_client(self):
        """Should store the s3tables_client reference."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter._client is client

    def test_stores_table_bucket_arn(self):
        """Should store the table bucket ARN."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter._table_bucket_arn == VALID_TABLE_BUCKET_ARN

    def test_stores_aws_region(self):
        """Should store the AWS region."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        assert adapter._aws_region == VALID_AWS_REGION


class TestGetTableMetadataLocation:
    """Test _get_table_metadata_location retrieves metadata from S3 Tables."""

    def test_returns_metadata_location(self):
        """Should return the metadataLocation from get_table response."""
        client = _make_s3tables_client(
            get_table_response={
                "metadataLocation": "s3://bucket/metadata/00001.metadata.json",
                "name": "orders",
                "namespace": ["analytics"],
            }
        )
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        result = adapter._get_table_metadata_location("analytics", "orders")

        assert result == "s3://bucket/metadata/00001.metadata.json"
        client.get_table.assert_called_once_with(
            tableBucketARN=VALID_TABLE_BUCKET_ARN,
            namespace="analytics",
            name="orders",
        )

    def test_raises_runtime_error_on_failure(self):
        """Should raise RuntimeError when get_table API fails."""
        client = _make_s3tables_client()
        client.get_table.side_effect = Exception("Table not found")
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        with pytest.raises(RuntimeError, match="Failed to get metadata location"):
            adapter._get_table_metadata_location("analytics", "missing_table")


class TestMaintenanceConfig:
    """Test MaintenanceConfig dataclass defaults and field assignment."""

    def test_default_values(self):
        """MaintenanceConfig should have correct default values."""
        config = MaintenanceConfig()

        assert config.compaction_enabled is True
        assert config.target_file_size_mb == 512
        assert config.compaction_strategy == "binpack"
        assert config.sort_columns == []
        assert config.snapshot_management_enabled is True
        assert config.min_snapshots_to_keep == 30
        assert config.max_snapshot_age_hours == 720

    def test_custom_values(self):
        """MaintenanceConfig should accept custom values."""
        config = MaintenanceConfig(
            compaction_enabled=False,
            target_file_size_mb=128,
            compaction_strategy="sort",
            sort_columns=["order_date", "customer_id"],
            snapshot_management_enabled=False,
            min_snapshots_to_keep=10,
            max_snapshot_age_hours=168,
        )

        assert config.compaction_enabled is False
        assert config.target_file_size_mb == 128
        assert config.compaction_strategy == "sort"
        assert config.sort_columns == ["order_date", "customer_id"]
        assert config.snapshot_management_enabled is False
        assert config.min_snapshots_to_keep == 10
        assert config.max_snapshot_age_hours == 168

    def test_sort_columns_default_is_independent(self):
        """Each MaintenanceConfig instance should have its own sort_columns list."""
        config1 = MaintenanceConfig()
        config2 = MaintenanceConfig()

        config1.sort_columns.append("col_a")

        assert config2.sort_columns == []

    def test_z_order_strategy(self):
        """MaintenanceConfig should accept z-order strategy."""
        config = MaintenanceConfig(
            compaction_strategy="z-order",
            sort_columns=["col_a", "col_b"],
        )

        assert config.compaction_strategy == "z-order"
        assert config.sort_columns == ["col_a", "col_b"]

    def test_minimum_valid_file_size(self):
        """MaintenanceConfig should accept minimum valid file size (64 MB)."""
        config = MaintenanceConfig(target_file_size_mb=64)
        assert config.target_file_size_mb == 64

    def test_maximum_valid_file_size(self):
        """MaintenanceConfig should accept maximum valid file size (512 MB)."""
        config = MaintenanceConfig(target_file_size_mb=512)
        assert config.target_file_size_mb == 512


class TestDeriveGlueId:
    """Test derive_glue_id static method for ARN parsing and glue.id derivation."""

    def test_valid_arn_us_east_1(self):
        """Should derive correct glue.id from a valid us-east-1 ARN."""
        arn = "arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket"
        result = S3TablesAdapter.derive_glue_id(arn)
        assert result == "123456789012:s3tablescatalog/my-table-bucket"

    def test_valid_arn_eu_west_1(self):
        """Should derive correct glue.id from a valid eu-west-1 ARN."""
        arn = "arn:aws:s3tables:eu-west-1:987654321098:bucket/analytics-bucket"
        result = S3TablesAdapter.derive_glue_id(arn)
        assert result == "987654321098:s3tablescatalog/analytics-bucket"

    def test_valid_arn_with_dots_in_bucket_name(self):
        """Should handle bucket names containing dots."""
        arn = "arn:aws:s3tables:us-west-2:111222333444:bucket/my.data.bucket"
        result = S3TablesAdapter.derive_glue_id(arn)
        assert result == "111222333444:s3tablescatalog/my.data.bucket"

    def test_valid_arn_with_hyphens_in_bucket_name(self):
        """Should handle bucket names containing hyphens."""
        arn = "arn:aws:s3tables:ap-southeast-1:555666777888:bucket/my-data-bucket"
        result = S3TablesAdapter.derive_glue_id(arn)
        assert result == "555666777888:s3tablescatalog/my-data-bucket"

    def test_valid_arn_minimum_bucket_name(self):
        """Should handle minimum-length bucket names (3 chars)."""
        arn = "arn:aws:s3tables:us-east-1:123456789012:bucket/abc"
        result = S3TablesAdapter.derive_glue_id(arn)
        assert result == "123456789012:s3tablescatalog/abc"

    def test_raises_value_error_for_empty_string(self):
        """Should raise ValueError for empty string."""
        with pytest.raises(ValueError, match="Invalid table bucket ARN format"):
            S3TablesAdapter.derive_glue_id("")

    def test_raises_value_error_for_wrong_service(self):
        """Should raise ValueError for non-s3tables ARN."""
        arn = "arn:aws:s3:us-east-1:123456789012:bucket/my-bucket"
        with pytest.raises(ValueError, match="Invalid table bucket ARN format"):
            S3TablesAdapter.derive_glue_id(arn)

    def test_raises_value_error_for_missing_bucket(self):
        """Should raise ValueError for ARN without bucket component."""
        arn = "arn:aws:s3tables:us-east-1:123456789012:table/my-table"
        with pytest.raises(ValueError, match="Invalid table bucket ARN format"):
            S3TablesAdapter.derive_glue_id(arn)

    def test_raises_value_error_for_invalid_account_id(self):
        """Should raise ValueError for ARN with non-12-digit account ID."""
        arn = "arn:aws:s3tables:us-east-1:12345:bucket/my-bucket"
        with pytest.raises(ValueError, match="Invalid table bucket ARN format"):
            S3TablesAdapter.derive_glue_id(arn)

    def test_raises_value_error_for_missing_region(self):
        """Should raise ValueError for ARN without region."""
        arn = "arn:aws:s3tables::123456789012:bucket/my-bucket"
        with pytest.raises(ValueError, match="Invalid table bucket ARN format"):
            S3TablesAdapter.derive_glue_id(arn)

    def test_raises_value_error_for_random_string(self):
        """Should raise ValueError for arbitrary non-ARN string."""
        with pytest.raises(ValueError, match="Invalid table bucket ARN format"):
            S3TablesAdapter.derive_glue_id("not-an-arn-at-all")

    def test_raises_value_error_for_uppercase_bucket(self):
        """Should raise ValueError for bucket name with uppercase letters."""
        arn = "arn:aws:s3tables:us-east-1:123456789012:bucket/MyBucket"
        with pytest.raises(ValueError, match="Invalid table bucket ARN format"):
            S3TablesAdapter.derive_glue_id(arn)

    def test_raises_value_error_for_bucket_starting_with_dot(self):
        """Should raise ValueError for bucket name starting with a dot."""
        arn = "arn:aws:s3tables:us-east-1:123456789012:bucket/.invalid-bucket"
        with pytest.raises(ValueError, match="Invalid table bucket ARN format"):
            S3TablesAdapter.derive_glue_id(arn)

    def test_raises_value_error_for_bucket_ending_with_dot(self):
        """Should raise ValueError for bucket name ending with a dot."""
        arn = "arn:aws:s3tables:us-east-1:123456789012:bucket/invalid-bucket."
        with pytest.raises(ValueError, match="Invalid table bucket ARN format"):
            S3TablesAdapter.derive_glue_id(arn)

    def test_is_static_method(self):
        """derive_glue_id should be callable without an instance."""
        # Should work without instantiating S3TablesAdapter
        result = S3TablesAdapter.derive_glue_id(
            "arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket"
        )
        assert isinstance(result, str)

    def test_error_message_includes_expected_format(self):
        """Error message should include the expected ARN format."""
        with pytest.raises(ValueError) as exc_info:
            S3TablesAdapter.derive_glue_id("bad-arn")

        error_msg = str(exc_info.value)
        assert "arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>" in error_msg


# =============================================================================
# Task 2.4: Unit tests for S3TablesAdapter maintenance configuration
# Requirements: 1.6, 1.7, 1.8, 2.1, 2.3
# =============================================================================


class TestConfigureMaintenanceRetryBehavior:
    """Test configure_maintenance retry behavior with mocked Boto3 failures.

    Validates Requirement 1.6: Retry up to 3 times with exponential backoff
    (delays of 2, 6, and 18 seconds). Returns False on exhaustion, not raises.
    """

    def test_succeeds_on_first_attempt(self):
        """Should return True when API call succeeds on first attempt."""
        client = _make_s3tables_client()
        client.put_table_maintenance_configuration.return_value = {}
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig()
        result = adapter.configure_maintenance("analytics", "orders", config)

        assert result is True

    def test_succeeds_after_first_retry(self):
        """Should return True when API call succeeds on second attempt."""
        client = _make_s3tables_client()
        # First attempt: first call fails
        # Second attempt: both calls succeed
        client.put_table_maintenance_configuration.side_effect = [
            Exception("Temporary failure"),
            {},  # second attempt - compaction call succeeds
            {},  # second attempt - snapshot call succeeds
        ]
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig()
        result = adapter.configure_maintenance("analytics", "orders", config)

        assert result is True

    def test_succeeds_after_second_retry(self):
        """Should return True when API call succeeds on third attempt."""
        client = _make_s3tables_client()
        # First two attempts fail, third attempt succeeds
        client.put_table_maintenance_configuration.side_effect = [
            Exception("Failure 1"),  # attempt 1 fails
            Exception("Failure 2"),  # attempt 2 fails
            {},  # attempt 3 - compaction call succeeds
            {},  # attempt 3 - snapshot call succeeds
        ]
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig()
        result = adapter.configure_maintenance("analytics", "orders", config)

        assert result is True

    def test_returns_false_after_all_retries_exhausted(self):
        """Should return False when all retry attempts fail (Req 1.6)."""
        client = _make_s3tables_client()
        # All attempts fail
        client.put_table_maintenance_configuration.side_effect = Exception(
            "Persistent failure"
        )
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig()
        result = adapter.configure_maintenance("analytics", "orders", config)

        assert result is False

    def test_does_not_raise_on_failure(self):
        """configure_maintenance must not raise exceptions — returns False instead (Req 1.6)."""
        client = _make_s3tables_client()
        client.put_table_maintenance_configuration.side_effect = RuntimeError(
            "Service unavailable"
        )
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig()
        # Should NOT raise — this is the key requirement
        result = adapter.configure_maintenance("analytics", "orders", config)
        assert result is False

    def test_retry_count_matches_specification(self):
        """Should attempt exactly 4 total calls (initial + 3 retries)."""
        client = _make_s3tables_client()
        client.put_table_maintenance_configuration.side_effect = Exception("Fail")
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig()
        adapter.configure_maintenance("analytics", "orders", config)

        # Each attempt calls put_table_maintenance_configuration once (fails on first call)
        # 4 total attempts = initial + 3 retries
        call_count = client.put_table_maintenance_configuration.call_count
        assert call_count == 4  # initial attempt + 3 retries

    def test_retry_with_exponential_backoff(self, monkeypatch):
        """Should use exponential backoff delays of 2s, 6s, 18s (Req 1.6)."""
        import services.bq_iceberg_migration.s3_tables_adapter as adapter_module

        sleep_calls = []
        monkeypatch.setattr(
            adapter_module.time, "sleep", lambda delay: sleep_calls.append(delay)
        )

        client = _make_s3tables_client()
        client.put_table_maintenance_configuration.side_effect = Exception("Fail")
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig()
        adapter.configure_maintenance("analytics", "orders", config)

        # Should have 3 sleep calls with delays 2, 6, 18
        assert sleep_calls == [2, 6, 18]


class TestConfigureMaintenanceNonFatal:
    """Test that configure_maintenance failure does not fail table creation.

    Validates Requirement 1.6: Migration continues after config failure.
    The method returns False (not raises) so the caller can continue.
    """

    def test_returns_false_not_raises_on_boto3_client_error(self):
        """Boto3 ClientError should result in False return, not exception propagation."""
        client = _make_s3tables_client()
        # Simulate a Boto3 ClientError
        client.put_table_maintenance_configuration.side_effect = Exception(
            "An error occurred (ValidationException): Invalid parameter"
        )
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig()
        result = adapter.configure_maintenance("analytics", "orders", config)

        assert result is False

    def test_returns_false_not_raises_on_connection_error(self):
        """Connection errors should result in False return, not exception propagation."""
        client = _make_s3tables_client()
        client.put_table_maintenance_configuration.side_effect = ConnectionError(
            "Could not connect to endpoint"
        )
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig()
        result = adapter.configure_maintenance("analytics", "orders", config)

        assert result is False

    def test_returns_false_not_raises_on_timeout(self):
        """Timeout errors should result in False return, not exception propagation."""
        client = _make_s3tables_client()
        client.put_table_maintenance_configuration.side_effect = TimeoutError(
            "Read timed out"
        )
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig()
        result = adapter.configure_maintenance("analytics", "orders", config)

        assert result is False

    def test_table_creation_continues_after_maintenance_failure(self):
        """Simulates the full flow: table creation succeeds, maintenance fails, migration continues."""
        client = _make_s3tables_client(
            create_table_response={
                "tableARN": "arn:aws:s3tables:us-east-1:123456789012:bucket/b/table/t",
                "versionToken": "v1",
            },
            get_table_response={
                "metadataLocation": "s3://bucket/metadata/00000.metadata.json",
                "name": "orders",
                "namespace": ["analytics"],
            },
        )
        # Maintenance config always fails
        client.put_table_maintenance_configuration.side_effect = Exception(
            "Access denied"
        )
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        # Step 1: Create table succeeds
        schema = MagicMock()
        partition_spec = MagicMock()
        table_result = adapter.create_table("analytics", "orders", schema, partition_spec)
        assert table_result["table_name"] == "orders"

        # Step 2: Maintenance config fails but returns False (non-fatal)
        config = MaintenanceConfig()
        maintenance_result = adapter.configure_maintenance("analytics", "orders", config)
        assert maintenance_result is False

        # Step 3: Migration can continue (no exception was raised)
        # This is the key assertion — the caller can proceed


class TestBuildMaintenancePayloadBinpack:
    """Test _build_maintenance_payload produces correct API shape for binpack strategy.

    Validates Requirements 1.1, 1.2, 1.3, 1.4.
    """

    def test_binpack_payload_structure(self):
        """Binpack strategy should produce correct nested dict structure."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig(
            compaction_enabled=True,
            target_file_size_mb=256,
            compaction_strategy="binpack",
            snapshot_management_enabled=True,
            min_snapshots_to_keep=30,
            max_snapshot_age_hours=720,
        )

        payload = adapter._build_maintenance_payload(config)

        # Top-level keys
        assert "icebergCompaction" in payload
        assert "icebergSnapshotManagement" in payload

        # Compaction structure
        compaction = payload["icebergCompaction"]
        assert compaction["isEnabled"] is True
        assert "settings" in compaction
        assert compaction["settings"]["targetFileSizeMB"] == 256
        assert "strategy" in compaction["settings"]
        # Binpack strategy should be a dict with "binpack" key
        assert "binpack" in compaction["settings"]["strategy"]

    def test_binpack_no_sort_columns(self):
        """Binpack strategy should not include sortColumns in the payload."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig(compaction_strategy="binpack")
        payload = adapter._build_maintenance_payload(config)

        compaction_settings = payload["icebergCompaction"]["settings"]
        assert "sortColumns" not in compaction_settings

    def test_binpack_default_file_size(self):
        """Default config should produce targetFileSizeMB of 512."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig()  # defaults
        payload = adapter._build_maintenance_payload(config)

        assert payload["icebergCompaction"]["settings"]["targetFileSizeMB"] == 512


class TestBuildMaintenancePayloadSort:
    """Test _build_maintenance_payload produces correct API shape for sort strategy.

    Validates Requirements 1.4, 1.5.
    """

    def test_sort_payload_structure(self):
        """Sort strategy should include sortColumns in the strategy dict."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig(
            compaction_strategy="sort",
            sort_columns=["order_date", "customer_id"],
            target_file_size_mb=128,
        )

        payload = adapter._build_maintenance_payload(config)

        compaction = payload["icebergCompaction"]
        assert compaction["isEnabled"] is True
        strategy = compaction["settings"]["strategy"]
        assert "sort" in strategy
        assert strategy["sort"]["sortColumns"] == ["order_date", "customer_id"]

    def test_sort_with_single_column(self):
        """Sort strategy should work with a single sort column."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig(
            compaction_strategy="sort",
            sort_columns=["event_timestamp"],
        )

        payload = adapter._build_maintenance_payload(config)

        strategy = payload["icebergCompaction"]["settings"]["strategy"]
        assert strategy["sort"]["sortColumns"] == ["event_timestamp"]

    def test_sort_target_file_size(self):
        """Sort strategy should still include targetFileSizeMB."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig(
            compaction_strategy="sort",
            sort_columns=["col_a"],
            target_file_size_mb=64,
        )

        payload = adapter._build_maintenance_payload(config)

        assert payload["icebergCompaction"]["settings"]["targetFileSizeMB"] == 64


class TestBuildMaintenancePayloadZOrder:
    """Test _build_maintenance_payload produces correct API shape for z-order strategy.

    Validates Requirements 1.4, 1.5.
    """

    def test_z_order_payload_structure(self):
        """Z-order strategy should include sortColumns in the strategy dict."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig(
            compaction_strategy="z-order",
            sort_columns=["col_a", "col_b", "col_c"],
            target_file_size_mb=256,
        )

        payload = adapter._build_maintenance_payload(config)

        compaction = payload["icebergCompaction"]
        assert compaction["isEnabled"] is True
        strategy = compaction["settings"]["strategy"]
        assert "z-order" in strategy
        assert strategy["z-order"]["sortColumns"] == ["col_a", "col_b", "col_c"]

    def test_z_order_with_two_columns(self):
        """Z-order strategy should work with two sort columns."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig(
            compaction_strategy="z-order",
            sort_columns=["region", "timestamp"],
        )

        payload = adapter._build_maintenance_payload(config)

        strategy = payload["icebergCompaction"]["settings"]["strategy"]
        assert strategy["z-order"]["sortColumns"] == ["region", "timestamp"]


class TestBuildMaintenancePayloadSnapshotManagement:
    """Test _build_maintenance_payload snapshot management section.

    Validates Requirement 1.3.
    """

    def test_snapshot_management_structure(self):
        """Snapshot management should have isEnabled and settings with correct fields."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig(
            snapshot_management_enabled=True,
            min_snapshots_to_keep=50,
            max_snapshot_age_hours=168,
        )

        payload = adapter._build_maintenance_payload(config)

        snapshot = payload["icebergSnapshotManagement"]
        assert snapshot["isEnabled"] is True
        assert snapshot["settings"]["minSnapshotsToKeep"] == 50
        assert snapshot["settings"]["maxSnapshotAgeHours"] == 168

    def test_snapshot_management_disabled(self):
        """Should set isEnabled to False when snapshot management is disabled."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig(snapshot_management_enabled=False)
        payload = adapter._build_maintenance_payload(config)

        assert payload["icebergSnapshotManagement"]["isEnabled"] is False

    def test_compaction_disabled(self):
        """Should set compaction isEnabled to False when compaction is disabled."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig(compaction_enabled=False)
        payload = adapter._build_maintenance_payload(config)

        assert payload["icebergCompaction"]["isEnabled"] is False


class TestDeriveGlueIdAdditional:
    """Additional derive_glue_id tests for edge cases.

    Validates Requirements 2.1, 2.3.
    """

    def test_valid_arn_ap_northeast_1(self):
        """Should handle ap-northeast-1 region correctly."""
        arn = "arn:aws:s3tables:ap-northeast-1:111222333444:bucket/tokyo-bucket"
        result = S3TablesAdapter.derive_glue_id(arn)
        assert result == "111222333444:s3tablescatalog/tokyo-bucket"

    def test_valid_arn_with_numbers_in_bucket(self):
        """Should handle bucket names with numbers."""
        arn = "arn:aws:s3tables:us-east-1:123456789012:bucket/bucket123data"
        result = S3TablesAdapter.derive_glue_id(arn)
        assert result == "123456789012:s3tablescatalog/bucket123data"

    def test_raises_for_arn_with_extra_path(self):
        """Should raise ValueError for ARN with extra path segments."""
        arn = "arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket/extra"
        with pytest.raises(ValueError, match="Invalid table bucket ARN format"):
            S3TablesAdapter.derive_glue_id(arn)

    def test_raises_for_none_input(self):
        """Should raise an error for None input."""
        with pytest.raises((ValueError, TypeError)):
            S3TablesAdapter.derive_glue_id(None)

    def test_raises_for_arn_with_underscores_in_bucket(self):
        """Should raise ValueError for bucket names with underscores (not valid S3 bucket names)."""
        arn = "arn:aws:s3tables:us-east-1:123456789012:bucket/my_bucket"
        with pytest.raises(ValueError, match="Invalid table bucket ARN format"):
            S3TablesAdapter.derive_glue_id(arn)

    def test_raises_for_partial_arn(self):
        """Should raise ValueError for incomplete ARN."""
        arn = "arn:aws:s3tables:us-east-1:123456789012"
        with pytest.raises(ValueError, match="Invalid table bucket ARN format"):
            S3TablesAdapter.derive_glue_id(arn)

    def test_raises_for_arn_with_single_char_bucket(self):
        """Should raise ValueError for bucket name that's too short (< 3 chars)."""
        arn = "arn:aws:s3tables:us-east-1:123456789012:bucket/a"
        with pytest.raises(ValueError, match="Invalid table bucket ARN format"):
            S3TablesAdapter.derive_glue_id(arn)

    def test_output_format_matches_glue_id_pattern(self):
        """Derived glue.id should match the expected validation pattern."""
        import re

        arn = "arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket"
        result = S3TablesAdapter.derive_glue_id(arn)

        # Should match the glue.id validation pattern from validators.py
        pattern = re.compile(
            r'^\d{12}:s3tablescatalog/[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]$'
        )
        assert pattern.match(result), f"Derived glue.id '{result}' does not match expected pattern"


class TestNoPyIcebergMaintenanceProperties:
    """Test that no PyIceberg maintenance properties are set for S3 Tables.

    Validates Requirement 1.7: The System SHALL NOT attempt to set
    maintenance-related table properties via PyIceberg table properties
    for S3 Tables destinations.
    """

    def test_create_table_does_not_set_maintenance_properties(self):
        """create_table should not pass any maintenance-related properties to the API."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        schema = MagicMock()
        partition_spec = MagicMock()

        adapter.create_table("analytics", "orders", schema, partition_spec)

        # Verify create_table was called without any maintenance/compaction properties
        call_kwargs = client.create_table.call_args
        # The create_table call should not include any properties related to maintenance
        if call_kwargs.kwargs:
            properties = call_kwargs.kwargs.get("properties", {})
        else:
            # Check positional args — the call uses keyword args
            properties = {}
            for arg in call_kwargs:
                if isinstance(arg, dict) and any(
                    k in str(arg)
                    for k in [
                        "write.target-file-size-bytes",
                        "snapshot.retain.num-snapshots",
                        "snapshot.max-age-ms",
                        "compaction",
                    ]
                ):
                    properties = arg

        # No maintenance-related PyIceberg properties should be present
        maintenance_keys = [
            "write.target-file-size-bytes",
            "snapshot.retain.num-snapshots",
            "snapshot.max-age-ms",
            "write.spark.fanout.enabled",
            "compaction.enabled",
            "compaction.target-file-size-bytes",
        ]
        for key in maintenance_keys:
            assert key not in str(call_kwargs), (
                f"PyIceberg maintenance property '{key}' should NOT be set "
                f"for S3 Tables destinations (Req 1.7)"
            )

    def test_maintenance_configured_via_boto3_api_not_pyiceberg(self):
        """Maintenance should be configured via put_table_maintenance_configuration, not table properties."""
        client = _make_s3tables_client()
        client.put_table_maintenance_configuration.return_value = {}
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig(
            target_file_size_mb=256,
            compaction_strategy="sort",
            sort_columns=["order_date"],
        )

        # Maintenance is configured via the dedicated API method
        result = adapter.configure_maintenance("analytics", "orders", config)
        assert result is True

        # Verify it called the Boto3 API, not PyIceberg properties
        client.put_table_maintenance_configuration.assert_called()

    def test_build_payload_does_not_produce_pyiceberg_property_format(self):
        """_build_maintenance_payload should produce Boto3 API format, not PyIceberg property format."""
        client = _make_s3tables_client()
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig()
        payload = adapter._build_maintenance_payload(config)

        # Payload should use Boto3 API keys (camelCase), not PyIceberg property keys (dot-separated)
        payload_str = str(payload)
        assert "write.target-file-size-bytes" not in payload_str
        assert "snapshot.retain.num-snapshots" not in payload_str

        # Should use Boto3 API format
        assert "icebergCompaction" in payload
        assert "icebergSnapshotManagement" in payload
        assert "targetFileSizeMB" in str(payload["icebergCompaction"])


class TestConfigureMaintenanceLogging:
    """Test configure_maintenance logging behavior.

    Validates Requirement 1.8: INFO log on success with table name,
    strategy, file size, and snapshot settings.
    """

    def test_logs_info_on_success(self, caplog):
        """Should log INFO with table name, strategy, and settings on success."""
        import logging

        client = _make_s3tables_client()
        client.put_table_maintenance_configuration.return_value = {}
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig(
            compaction_strategy="sort",
            target_file_size_mb=256,
            sort_columns=["order_date"],
            min_snapshots_to_keep=50,
            max_snapshot_age_hours=168,
        )

        with caplog.at_level(logging.INFO):
            result = adapter.configure_maintenance("analytics", "orders", config)

        assert result is True
        # Verify INFO log was emitted with relevant details
        info_messages = [r.message for r in caplog.records if r.levelno == logging.INFO]
        assert any("maintenance" in msg.lower() or "Maintenance" in msg for msg in info_messages)

    def test_logs_warning_on_retry(self, caplog):
        """Should log WARNING on each failed attempt before retry."""
        import logging

        client = _make_s3tables_client()
        # Fail twice, succeed on third
        client.put_table_maintenance_configuration.side_effect = [
            Exception("Fail 1"),
            Exception("Fail 2"),
            {},
        ]
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig()

        with caplog.at_level(logging.WARNING):
            result = adapter.configure_maintenance("analytics", "orders", config)

        assert result is True
        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_messages) >= 2  # At least 2 warnings for 2 failures

    def test_logs_error_on_exhaustion(self, caplog):
        """Should log ERROR with S3_TABLES_MAINTENANCE_CONFIG_FAILED on all retries exhausted."""
        import logging

        client = _make_s3tables_client()
        client.put_table_maintenance_configuration.side_effect = Exception("Persistent")
        adapter = S3TablesAdapter(client, VALID_TABLE_BUCKET_ARN, VALID_AWS_REGION)

        config = MaintenanceConfig()

        with caplog.at_level(logging.ERROR):
            result = adapter.configure_maintenance("analytics", "orders", config)

        assert result is False
        error_messages = [r.message for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_messages) >= 1
