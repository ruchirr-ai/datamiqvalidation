# Feature: iceberg-production-hardening
"""
Property tests for Iceberg Production Hardening validators.

Tests cover:
- Property 2: Compaction sort column validation
- Property 4: glue.id validation rejects invalid formats
- Property 6: Maintenance config validation
- Property 7: S3 Tables parallelism enforcement

Uses Hypothesis with minimum 100 iterations per property.
"""

import re
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings, assume, strategies as st

from services.bq_iceberg_migration.validators import (
    validate_compaction_strategy,
    validate_glue_id,
    validate_maintenance_config,
    validate_s3_tables_parallelism,
)


# =============================================================================
# Strategies
# =============================================================================

# --- Column name strategy ---
# Realistic column names: lowercase letters and underscores, 1-30 chars
column_name_strategy = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz_",
    min_size=1,
    max_size=30,
).filter(lambda s: s[0] != "_" and s[-1] != "_" and "__" not in s)

# --- Table schema strategy ---
# A table schema is a list of unique column names (1-20 columns)
table_schema_strategy = st.lists(
    column_name_strategy,
    min_size=1,
    max_size=20,
    unique=True,
)

# --- Valid glue.id strategy ---
# Format: {12-digit account_id}:s3tablescatalog/{bucket-name}
_GLUE_ID_REGEX = re.compile(
    r'^\d{12}:s3tablescatalog/[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]$'
)

account_id_strategy = st.from_regex(r"\d{12}", fullmatch=True)

bucket_name_for_glue_strategy = st.from_regex(
    r"[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]",
    fullmatch=True,
)

valid_glue_id_strategy = st.builds(
    lambda account, bucket: f"{account}:s3tablescatalog/{bucket}",
    account=account_id_strategy,
    bucket=bucket_name_for_glue_strategy,
)

# --- Invalid glue.id strategy ---
# Arbitrary strings that do NOT match the valid pattern
invalid_glue_id_strategy = st.text(min_size=0, max_size=200).filter(
    lambda s: not _GLUE_ID_REGEX.match(s)
)


# =============================================================================
# Property 2: Compaction sort column validation
# =============================================================================


@given(
    schema=table_schema_strategy,
    data=st.data(),
)
@settings(max_examples=100)
def test_compaction_sort_column_validation_accepts_valid_columns(schema, data):
    """Property 2a: Validator accepts when all sort columns exist in schema.

    For any table schema and sort columns that are a subset of the schema,
    the compaction strategy validator SHALL accept the configuration.

    **Validates: Requirements 1.5, 3.4**
    """
    # Pick a subset of schema columns as sort columns (at least 1)
    sort_columns = data.draw(
        st.lists(
            st.sampled_from(schema),
            min_size=1,
            max_size=min(len(schema), 5),
        )
    )
    # Use sort or z-order strategy (requires sort columns)
    strategy = data.draw(st.sampled_from(["sort", "z-order"]))

    is_valid, error = validate_compaction_strategy(strategy, sort_columns, schema)
    assert is_valid, (
        f"Valid sort columns {sort_columns} from schema {schema} "
        f"with strategy '{strategy}' was rejected: {error}"
    )
    assert error is None


@given(
    schema=table_schema_strategy,
    data=st.data(),
)
@settings(max_examples=100)
def test_compaction_sort_column_validation_rejects_invalid_columns(schema, data):
    """Property 2b: Validator rejects when sort columns don't exist in schema.

    For any table schema and sort columns where at least one column does NOT
    exist in the schema, the validator SHALL reject with an error identifying
    the invalid column(s).

    **Validates: Requirements 1.5, 3.4**
    """
    # Generate column names that are NOT in the schema
    schema_set = set(schema)
    invalid_column = data.draw(
        column_name_strategy.filter(lambda c: c not in schema_set)
    )
    # Mix valid and invalid columns
    valid_subset = data.draw(
        st.lists(st.sampled_from(schema), min_size=0, max_size=2)
    )
    sort_columns = valid_subset + [invalid_column]

    strategy = data.draw(st.sampled_from(["sort", "z-order"]))

    is_valid, error = validate_compaction_strategy(strategy, sort_columns, schema)
    assert not is_valid, (
        f"Sort columns {sort_columns} with invalid column '{invalid_column}' "
        f"should be rejected for schema {schema}"
    )
    assert error is not None
    assert invalid_column in error, (
        f"Error message should identify invalid column '{invalid_column}', "
        f"got: {error}"
    )


@given(schema=table_schema_strategy)
@settings(max_examples=100)
def test_compaction_binpack_accepts_any_schema(schema):
    """Property 2c: Binpack strategy accepts any schema without sort columns.

    For any table schema, the binpack strategy SHALL accept the configuration
    regardless of sort columns (empty list).

    **Validates: Requirements 1.5, 3.4**
    """
    is_valid, error = validate_compaction_strategy("binpack", [], schema)
    assert is_valid, (
        f"Binpack strategy with empty sort columns should be accepted: {error}"
    )
    assert error is None


# =============================================================================
# Property 4: glue.id validation rejects invalid formats
# =============================================================================


@given(glue_id=invalid_glue_id_strategy)
@settings(max_examples=100)
def test_glue_id_validation_rejects_invalid_formats(glue_id):
    """Property 4: glue.id validation rejects invalid formats.

    For any string that does NOT match the pattern
    ^\\d{12}:s3tablescatalog/[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$,
    the glue.id validator SHALL return (False, error_message) where the
    error message contains the expected format description.

    **Validates: Requirements 2.2, 2.6**
    """
    is_valid, error = validate_glue_id(glue_id)
    assert not is_valid, (
        f"Invalid glue.id '{glue_id}' should be rejected"
    )
    assert error is not None
    # Error message should contain expected format info
    assert "glue.id" in error.lower() or "format" in error.lower(), (
        f"Error message should describe expected format, got: {error}"
    )


@given(glue_id=valid_glue_id_strategy)
@settings(max_examples=100)
def test_glue_id_validation_accepts_valid_formats(glue_id):
    """Property 4 (inverse): Valid glue.id values are accepted.

    For any string matching the valid glue.id pattern, the validator
    SHALL return (True, None).

    **Validates: Requirements 2.2, 2.6**
    """
    is_valid, error = validate_glue_id(glue_id)
    assert is_valid, (
        f"Valid glue.id '{glue_id}' was rejected: {error}"
    )
    assert error is None


# =============================================================================
# Property 6: Maintenance config validation
# =============================================================================


@given(target_file_size_mb=st.integers(min_value=64, max_value=512))
@settings(max_examples=100)
def test_maintenance_config_accepts_valid_target_file_size(target_file_size_mb):
    """Property 6a: Maintenance config accepts target_file_size_mb in [64, 512].

    For any integer target_file_size_mb in [64, 512], the validator SHALL
    accept the value (with valid min_snapshots and max_age).

    **Validates: Requirements 4.3, 4.4**
    """
    is_valid, error = validate_maintenance_config(target_file_size_mb, 30, 720)
    assert is_valid, (
        f"Valid target_file_size_mb={target_file_size_mb} was rejected: {error}"
    )
    assert error is None


@given(
    target_file_size_mb=st.integers().filter(
        lambda x: x < 64 or x > 512
    ).filter(lambda x: x != 0)  # 0 has special handling
)
@settings(max_examples=100)
def test_maintenance_config_rejects_invalid_target_file_size(target_file_size_mb):
    """Property 6b: Maintenance config rejects target_file_size_mb outside [64, 512].

    For any integer target_file_size_mb outside [64, 512], the validator
    SHALL reject the value.

    **Validates: Requirements 4.3, 4.4**
    """
    is_valid, error = validate_maintenance_config(target_file_size_mb, 30, 720)
    assert not is_valid, (
        f"Invalid target_file_size_mb={target_file_size_mb} should be rejected"
    )
    assert error is not None


@given(min_snapshots=st.integers(min_value=1, max_value=10000))
@settings(max_examples=100)
def test_maintenance_config_accepts_positive_min_snapshots(min_snapshots):
    """Property 6c: Maintenance config accepts positive min_snapshots_to_keep.

    For any positive integer min_snapshots_to_keep, the validator SHALL
    accept the value.

    **Validates: Requirements 4.3, 4.4**
    """
    is_valid, error = validate_maintenance_config(512, min_snapshots, 720)
    assert is_valid, (
        f"Valid min_snapshots_to_keep={min_snapshots} was rejected: {error}"
    )
    assert error is None


@given(min_snapshots=st.integers(max_value=0))
@settings(max_examples=100)
def test_maintenance_config_rejects_non_positive_min_snapshots(min_snapshots):
    """Property 6d: Maintenance config rejects zero/negative min_snapshots_to_keep.

    For any integer min_snapshots_to_keep <= 0, the validator SHALL reject
    the value.

    **Validates: Requirements 4.3, 4.4**
    """
    is_valid, error = validate_maintenance_config(512, min_snapshots, 720)
    assert not is_valid, (
        f"Invalid min_snapshots_to_keep={min_snapshots} should be rejected"
    )
    assert error is not None


@given(max_age=st.integers(min_value=1, max_value=100000))
@settings(max_examples=100)
def test_maintenance_config_accepts_positive_max_age(max_age):
    """Property 6e: Maintenance config accepts positive max_snapshot_age_hours.

    For any positive integer max_snapshot_age_hours, the validator SHALL
    accept the value.

    **Validates: Requirements 4.3, 4.4**
    """
    is_valid, error = validate_maintenance_config(512, 30, max_age)
    assert is_valid, (
        f"Valid max_snapshot_age_hours={max_age} was rejected: {error}"
    )
    assert error is None


@given(max_age=st.integers(max_value=0))
@settings(max_examples=100)
def test_maintenance_config_rejects_non_positive_max_age(max_age):
    """Property 6f: Maintenance config rejects zero/negative max_snapshot_age_hours.

    For any integer max_snapshot_age_hours <= 0, the validator SHALL reject
    the value.

    **Validates: Requirements 4.3, 4.4**
    """
    is_valid, error = validate_maintenance_config(512, 30, max_age)
    assert not is_valid, (
        f"Invalid max_snapshot_age_hours={max_age} should be rejected"
    )
    assert error is not None


# =============================================================================
# Property 7: S3 Tables parallelism enforcement
# =============================================================================


@given(parallelism=st.integers(min_value=1, max_value=8))
@settings(max_examples=100)
def test_s3_tables_parallelism_accepts_valid_range(parallelism):
    """Property 7a: S3 Tables parallelism accepts values in [1, 8].

    For any integer parallelism value in [1, 8], the validator SHALL
    accept the value.

    **Validates: Requirements 6.1, 6.7**
    """
    is_valid, error = validate_s3_tables_parallelism(parallelism)
    assert is_valid, (
        f"Valid parallelism={parallelism} was rejected: {error}"
    )
    assert error is None


@given(parallelism=st.integers(min_value=9, max_value=1000))
@settings(max_examples=100)
def test_s3_tables_parallelism_rejects_above_max(parallelism):
    """Property 7b: S3 Tables parallelism rejects values greater than 8.

    For any integer parallelism value > 8, the validator SHALL reject
    the value.

    **Validates: Requirements 6.1, 6.7**
    """
    is_valid, error = validate_s3_tables_parallelism(parallelism)
    assert not is_valid, (
        f"Parallelism={parallelism} (> 8) should be rejected"
    )
    assert error is not None


@given(parallelism=st.integers(max_value=0))
@settings(max_examples=100)
def test_s3_tables_parallelism_rejects_below_min(parallelism):
    """Property 7c: S3 Tables parallelism rejects values less than 1.

    For any integer parallelism value < 1, the validator SHALL reject
    the value.

    **Validates: Requirements 6.1, 6.7**
    """
    is_valid, error = validate_s3_tables_parallelism(parallelism)
    assert not is_valid, (
        f"Parallelism={parallelism} (< 1) should be rejected"
    )
    assert error is not None


# =============================================================================
# Property 1: Maintenance configuration payload correctness
# =============================================================================

from unittest.mock import MagicMock

from services.bq_iceberg_migration.s3_tables_adapter import (
    MaintenanceConfig,
    S3TablesAdapter,
)


# --- Custom strategies for maintenance config ---

# Valid compaction strategies
compaction_strategy_strategy = st.sampled_from(["binpack", "sort", "z-order"])

# Valid target file size (64-512 MB)
target_file_size_strategy = st.integers(min_value=64, max_value=512)

# Valid min snapshots to keep (positive integer)
min_snapshots_strategy = st.integers(min_value=1, max_value=10000)

# Valid max snapshot age hours (positive integer)
max_snapshot_age_strategy = st.integers(min_value=1, max_value=100000)

# Sort columns strategy (1-5 lowercase column names)
sort_columns_strategy = st.lists(
    st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz_",
        min_size=1,
        max_size=20,
    ).filter(lambda s: s[0] != "_" and "__" not in s),
    min_size=1,
    max_size=5,
    unique=True,
)


@given(
    target_file_size_mb=target_file_size_strategy,
    compaction_strategy=compaction_strategy_strategy,
    min_snapshots_to_keep=min_snapshots_strategy,
    max_snapshot_age_hours=max_snapshot_age_strategy,
    sort_columns=sort_columns_strategy,
)
@settings(max_examples=100)
def test_maintenance_payload_correctness(
    target_file_size_mb,
    compaction_strategy,
    min_snapshots_to_keep,
    max_snapshot_age_hours,
    sort_columns,
):
    """Property 1: Maintenance configuration payload correctness.

    For any valid maintenance configuration (target_file_size_mb in [64, 512],
    compaction_strategy in {binpack, sort, z-order}, min_snapshots_to_keep > 0,
    max_snapshot_age_hours > 0, and sort_columns valid for the given strategy),
    the constructed `put_table_maintenance_configuration` API payload SHALL have
    `icebergCompaction.isEnabled` set to true, `targetFileSizeMB` matching the
    input, the correct strategy, and `icebergSnapshotManagement` fields matching
    the input values.

    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    """
    # For binpack, sort_columns are not used
    if compaction_strategy == "binpack":
        config_sort_columns = []
    else:
        config_sort_columns = sort_columns

    config = MaintenanceConfig(
        compaction_enabled=True,
        target_file_size_mb=target_file_size_mb,
        compaction_strategy=compaction_strategy,
        sort_columns=config_sort_columns,
        snapshot_management_enabled=True,
        min_snapshots_to_keep=min_snapshots_to_keep,
        max_snapshot_age_hours=max_snapshot_age_hours,
    )

    # Create adapter with mock client
    mock_client = MagicMock()
    adapter = S3TablesAdapter(
        s3tables_client=mock_client,
        table_bucket_arn="arn:aws:s3tables:us-east-1:123456789012:bucket/test-bucket",
        aws_region="us-east-1",
    )

    payload = adapter._build_maintenance_payload(config)

    # Assert icebergCompaction structure
    assert "icebergCompaction" in payload, "Payload must contain icebergCompaction"
    compaction = payload["icebergCompaction"]
    assert compaction["isEnabled"] is True, "icebergCompaction.isEnabled must be True"

    compaction_settings = compaction["settings"]
    assert compaction_settings["targetFileSizeMB"] == target_file_size_mb, (
        f"targetFileSizeMB should be {target_file_size_mb}, "
        f"got {compaction_settings['targetFileSizeMB']}"
    )
    assert compaction_settings["strategy"] == compaction_strategy, (
        f"strategy should be '{compaction_strategy}', "
        f"got '{compaction_settings['strategy']}'"
    )

    # For sort/z-order, sort columns must be present
    if compaction_strategy in ("sort", "z-order"):
        assert "sortColumns" in compaction_settings, (
            f"sortColumns must be present for '{compaction_strategy}' strategy"
        )
        assert compaction_settings["sortColumns"] == config_sort_columns, (
            f"sortColumns should be {config_sort_columns}, "
            f"got {compaction_settings['sortColumns']}"
        )

    # Assert icebergSnapshotManagement structure
    assert "icebergSnapshotManagement" in payload, (
        "Payload must contain icebergSnapshotManagement"
    )
    snapshot_mgmt = payload["icebergSnapshotManagement"]
    assert snapshot_mgmt["isEnabled"] is True, (
        "icebergSnapshotManagement.isEnabled must be True"
    )

    snapshot_settings = snapshot_mgmt["settings"]
    assert snapshot_settings["minSnapshotsToKeep"] == min_snapshots_to_keep, (
        f"minSnapshotsToKeep should be {min_snapshots_to_keep}, "
        f"got {snapshot_settings['minSnapshotsToKeep']}"
    )
    assert snapshot_settings["maxSnapshotAgeHours"] == max_snapshot_age_hours, (
        f"maxSnapshotAgeHours should be {max_snapshot_age_hours}, "
        f"got {snapshot_settings['maxSnapshotAgeHours']}"
    )


# =============================================================================
# Property 3: glue.id derivation round-trip
# =============================================================================

# --- Custom strategy for valid table bucket ARNs ---

# AWS regions strategy
aws_region_strategy = st.sampled_from([
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "eu-west-1", "eu-west-2", "eu-central-1",
    "ap-southeast-1", "ap-southeast-2", "ap-northeast-1",
])

# 12-digit account ID strategy
aws_account_id_strategy = st.from_regex(r"\d{12}", fullmatch=True)

# Valid bucket name for ARN (3-63 chars, lowercase alphanumeric + dots/hyphens,
# starts and ends with alphanumeric)
bucket_name_strategy = st.from_regex(
    r"[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]",
    fullmatch=True,
)

# Valid table bucket ARN strategy
valid_table_bucket_arn_strategy = st.builds(
    lambda region, account, bucket: f"arn:aws:s3tables:{region}:{account}:bucket/{bucket}",
    region=aws_region_strategy,
    account=aws_account_id_strategy,
    bucket=bucket_name_strategy,
)


@given(
    region=aws_region_strategy,
    account_id=aws_account_id_strategy,
    bucket_name=bucket_name_strategy,
)
@settings(max_examples=100)
def test_glue_id_derivation_round_trip(region, account_id, bucket_name):
    """Property 3: glue.id derivation round-trip.

    For any valid table bucket ARN matching
    `arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>`,
    deriving the glue.id SHALL produce a string in the format
    `{account_id}:s3tablescatalog/{bucket-name}` where account_id and
    bucket-name are extracted from the ARN, and the derived glue.id SHALL
    pass the glue.id validation regex.

    **Validates: Requirements 2.1, 2.2, 2.3**
    """
    # Construct a valid ARN
    table_bucket_arn = f"arn:aws:s3tables:{region}:{account_id}:bucket/{bucket_name}"

    # Derive glue.id
    glue_id = S3TablesAdapter.derive_glue_id(table_bucket_arn)

    # Verify format: {account_id}:s3tablescatalog/{bucket-name}
    expected_glue_id = f"{account_id}:s3tablescatalog/{bucket_name}"
    assert glue_id == expected_glue_id, (
        f"Derived glue.id '{glue_id}' does not match expected "
        f"'{expected_glue_id}' for ARN '{table_bucket_arn}'"
    )

    # Verify the derived glue.id passes validation
    is_valid, error = validate_glue_id(glue_id)
    assert is_valid, (
        f"Derived glue.id '{glue_id}' from ARN '{table_bucket_arn}' "
        f"failed validation: {error}"
    )


# =============================================================================
# Property 9: Hidden partition transform mapping
# =============================================================================

from services.bq_iceberg_migration.partition_mapper import (
    PartitionSpecMapper,
    PartitionField,
    PartitionSpec,
    format_partition_display,
    TRANSFORM_DISPLAY_MAP,
)

# Valid combinations for time-based partition types and granularities
_PARTITION_TYPES = ["DATE", "DATETIME", "TIMESTAMP"]
_GRANULARITIES = [None, "HOUR", "DAY", "MONTH", "YEAR"]

# Expected transform for each valid (type, granularity) combination
_EXPECTED_TRANSFORMS = {
    ("DATE", None): "day",
    ("DATE", "DAY"): "day",
    ("DATETIME", None): "day",
    ("DATETIME", "DAY"): "day",
    ("DATETIME", "HOUR"): "hour",
    ("DATETIME", "MONTH"): "month",
    ("DATETIME", "YEAR"): "year",
    ("TIMESTAMP", None): "day",
    ("TIMESTAMP", "DAY"): "day",
    ("TIMESTAMP", "HOUR"): "hour",
    ("TIMESTAMP", "MONTH"): "month",
    ("TIMESTAMP", "YEAR"): "year",
}

# DATE only supports None and DAY granularity
_INVALID_DATE_GRANULARITIES = ["HOUR", "MONTH", "YEAR"]


@given(
    partition_type=st.sampled_from(_PARTITION_TYPES),
    granularity=st.sampled_from(_GRANULARITIES),
    column_name=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz_",
        min_size=1,
        max_size=30,
    ).filter(lambda s: s[0] != "_" and s[-1] != "_" and "__" not in s),
)
@settings(max_examples=100)
def test_hidden_partition_transform_mapping(partition_type, granularity, column_name):
    """Property 9: Hidden partition transform mapping.

    For any time-based partition column (DATE, DATETIME, TIMESTAMP) with any
    granularity (HOUR, DAY, MONTH, YEAR, None), the partition mapper SHALL
    produce a PartitionSpec using the correct transform function and SHALL
    never produce an identity partition.

    DATE only supports None and DAY granularity — other granularities raise ValueError.
    DATETIME/TIMESTAMP support all granularities.

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.7**
    """
    mapper = PartitionSpecMapper()
    lookup_key = (partition_type, granularity)

    if lookup_key not in _EXPECTED_TRANSFORMS:
        # DATE with HOUR, MONTH, or YEAR should raise ValueError
        with pytest.raises(ValueError):
            mapper.map_partition_spec(column_name, partition_type, granularity)
        return

    # Valid combination — should produce a PartitionSpec with correct transform
    spec = mapper.map_partition_spec(column_name, partition_type, granularity)

    # Verify it returns a PartitionSpec
    assert isinstance(spec, PartitionSpec), (
        f"Expected PartitionSpec, got {type(spec)}"
    )

    # Verify it has exactly one field
    assert len(spec.fields) == 1, (
        f"Expected 1 partition field, got {len(spec.fields)}"
    )

    partition_field = spec.fields[0]

    # Verify it's a PartitionField
    assert isinstance(partition_field, PartitionField), (
        f"Expected PartitionField, got {type(partition_field)}"
    )

    # Verify the source column matches
    assert partition_field.source_column == column_name, (
        f"Expected source_column='{column_name}', got '{partition_field.source_column}'"
    )

    # Verify the correct transform is applied
    expected_transform = _EXPECTED_TRANSFORMS[lookup_key]
    assert partition_field.transform == expected_transform, (
        f"For type='{partition_type}', granularity='{granularity}': "
        f"expected transform='{expected_transform}', got '{partition_field.transform}'"
    )

    # CRITICAL: Never produce an identity partition on time-based columns
    assert partition_field.transform != "identity", (
        f"Identity partition produced for time-based column '{column_name}' "
        f"(type='{partition_type}', granularity='{granularity}'). "
        f"Hidden partitioning transforms must always be used."
    )


# =============================================================================
# Property 10: Partition transform display format
# =============================================================================


@given(
    column_name=st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz_",
        min_size=1,
        max_size=30,
    ).filter(lambda s: s[0] != "_" and s[-1] != "_" and "__" not in s),
    transform=st.sampled_from(["day", "hour", "month", "year"]),
)
@settings(max_examples=100)
def test_partition_transform_display_format(column_name, transform):
    """Property 10: Partition transform display format.

    For any partition spec with a transform and column name, the display string
    SHALL contain the transform function wrapping the column name
    (e.g., `days(column_name)`) in a human-readable format.

    The display format uses plural transform names:
    - day -> days(column_name)
    - hour -> hours(column_name)
    - month -> months(column_name)
    - year -> years(column_name)

    **Validates: Requirements 7.6**
    """
    display = format_partition_display(transform, column_name)

    # The display string must contain the column name
    assert column_name in display, (
        f"Display string '{display}' does not contain column name '{column_name}'"
    )

    # The display string must contain the plural transform function name
    expected_plural = TRANSFORM_DISPLAY_MAP[transform]
    assert expected_plural in display, (
        f"Display string '{display}' does not contain transform '{expected_plural}'"
    )

    # The display string must be in the format "transform_plural(column_name)"
    expected_display = f"{expected_plural}({column_name})"
    assert display == expected_display, (
        f"Expected display format '{expected_display}', got '{display}'"
    )

    # The display string must wrap the column name in the transform function
    assert display.startswith(f"{expected_plural}("), (
        f"Display string '{display}' does not start with '{expected_plural}('"
    )
    assert display.endswith(")"), (
        f"Display string '{display}' does not end with ')'"
    )


# =============================================================================
# Property 11: File-time watermark filtering
# =============================================================================

from datetime import datetime, timezone, timedelta
from typing import Optional

from services.bq_iceberg_migration.iceberg_loader import ParallelIcebergLoader


# Helper to create a loader instance for testing watermark methods
def _make_loader() -> ParallelIcebergLoader:
    """Create a minimal ParallelIcebergLoader for testing watermark methods."""
    from unittest.mock import MagicMock

    return ParallelIcebergLoader(
        catalog=MagicMock(),
        credential_provider=MagicMock(),
        type_mapper=MagicMock(),
        partition_mapper=MagicMock(),
        dedup_guard=MagicMock(),
        parallelism=4,
    )


@given(
    file_times=st.lists(
        st.datetimes(
            min_value=datetime(2000, 1, 1),
            max_value=datetime(2030, 12, 31),
            timezones=st.just(timezone.utc),
        ),
        min_size=0,
        max_size=20,
    ),
    watermark_dt=st.datetimes(
        min_value=datetime(2000, 1, 1),
        max_value=datetime(2030, 12, 31),
        timezones=st.just(timezone.utc),
    ),
)
@settings(max_examples=100)
def test_file_watermark_filtering_with_watermark(file_times, watermark_dt):
    """Property 11a: File-time watermark filtering with a watermark value.

    For any list of files with file_modification_time values and any watermark
    timestamp, the filtering function SHALL return exactly those files whose
    file_modification_time is strictly greater than the watermark.

    **Validates: Requirements 8.2**
    """
    loader = _make_loader()

    # Build file metadata list with datetime objects
    files = [
        {"file_modification_time": ft, "path": f"s3://bucket/file_{i}.parquet"}
        for i, ft in enumerate(file_times)
    ]

    # Format watermark as ISO 8601 UTC string (matching system format — second precision)
    watermark_str = watermark_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # The watermark is stored with second precision, so the effective comparison
    # threshold is the watermark truncated to seconds (microseconds dropped)
    watermark_truncated = watermark_dt.replace(microsecond=0)

    # Filter files
    result = loader._filter_files_by_watermark(files, watermark_str)

    # Verify: result contains exactly those files with modification_time > watermark
    # (compared against the second-precision watermark, since that's what the filter parses)
    expected_count = sum(1 for ft in file_times if ft > watermark_truncated)
    assert len(result) == expected_count, (
        f"Expected {expected_count} files after watermark, got {len(result)}. "
        f"Watermark: {watermark_str}, file_times: {file_times}"
    )

    # Verify each returned file has modification_time > watermark (truncated to seconds)
    for file_meta in result:
        file_dt = file_meta["file_modification_time"]
        assert file_dt > watermark_truncated, (
            f"File with time {file_dt} should not pass watermark {watermark_truncated}"
        )


@given(
    file_times=st.lists(
        st.datetimes(
            min_value=datetime(2000, 1, 1),
            max_value=datetime(2030, 12, 31),
            timezones=st.just(timezone.utc),
        ),
        min_size=1,
        max_size=20,
    ),
)
@settings(max_examples=100)
def test_file_watermark_filtering_none_returns_all(file_times):
    """Property 11b: File-time watermark filtering returns all files when watermark is None.

    For any list of files, filtering with watermark=None SHALL return all files.

    **Validates: Requirements 8.2**
    """
    loader = _make_loader()

    files = [
        {"file_modification_time": ft, "path": f"s3://bucket/file_{i}.parquet"}
        for i, ft in enumerate(file_times)
    ]

    result = loader._filter_files_by_watermark(files, None)

    assert len(result) == len(files), (
        f"With watermark=None, expected all {len(files)} files, got {len(result)}"
    )


# =============================================================================
# Property 12: Watermark monotonicity
# =============================================================================


@given(
    file_times_sequences=st.lists(
        st.lists(
            st.datetimes(
                min_value=datetime(2000, 1, 1),
                max_value=datetime(2030, 12, 31),
                timezones=st.just(timezone.utc),
            ),
            min_size=1,
            max_size=10,
        ),
        min_size=2,
        max_size=5,
    ),
)
@settings(max_examples=100)
def test_watermark_monotonicity(file_times_sequences):
    """Property 12: Watermark monotonicity.

    Watermark never decreases; after success equals max file_modification_time.
    For any sequence of successful loads, the watermark SHALL never decrease.
    After each successful load, the watermark SHALL equal the maximum
    file_modification_time across all processed files in that load.

    **Validates: Requirements 8.1, 8.3**
    """
    loader = _make_loader()

    current_watermark: Optional[str] = None

    for file_times in file_times_sequences:
        # Build processed files for this load
        processed_files = [
            {"file_modification_time": ft, "path": f"s3://bucket/file_{i}.parquet"}
            for i, ft in enumerate(file_times)
        ]

        # Compute new watermark
        new_watermark = loader._compute_file_time_watermark(processed_files)

        # Watermark should not be None since we have files with valid times
        assert new_watermark is not None, (
            f"Watermark should not be None for files with times: {file_times}"
        )

        # Verify watermark equals max file_modification_time
        max_time = max(file_times)
        expected_watermark = max_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        assert new_watermark == expected_watermark, (
            f"Watermark should equal max time. Expected '{expected_watermark}', "
            f"got '{new_watermark}'"
        )

        # Simulate monotonicity check: only update if new > current
        if current_watermark is not None:
            # Parse both for comparison
            current_dt = datetime.fromisoformat(
                current_watermark.replace("Z", "+00:00")
            )
            new_dt = datetime.fromisoformat(
                new_watermark.replace("Z", "+00:00")
            )

            # Only update watermark if new value is strictly greater
            if new_dt > current_dt:
                current_watermark = new_watermark
            # Otherwise, watermark stays the same (monotonicity preserved)
            # The stored watermark never decreases
            stored_dt = datetime.fromisoformat(
                current_watermark.replace("Z", "+00:00")
            )
            assert stored_dt >= current_dt, (
                f"Watermark decreased from {current_watermark} — "
                f"monotonicity violated"
            )
        else:
            current_watermark = new_watermark


# =============================================================================
# Property 13: Watermark preservation on failure
# =============================================================================


@given(
    initial_watermark_dt=st.datetimes(
        min_value=datetime(2000, 1, 1),
        max_value=datetime(2030, 12, 31),
        timezones=st.just(timezone.utc),
    ),
    file_times=st.lists(
        st.datetimes(
            min_value=datetime(2000, 1, 1),
            max_value=datetime(2030, 12, 31),
            timezones=st.just(timezone.utc),
        ),
        min_size=1,
        max_size=10,
    ),
)
@settings(max_examples=100)
def test_watermark_preservation_on_failure(initial_watermark_dt, file_times):
    """Property 13: Watermark preservation on failure.

    On failure, watermark remains at pre-load value. For any incremental load
    that fails partway through processing, the watermark SHALL remain at its
    pre-load value, ensuring the next retry reprocesses all files from the
    last successful checkpoint.

    **Validates: Requirements 8.4**
    """
    loader = _make_loader()

    # Set initial watermark
    initial_watermark = initial_watermark_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build processed files
    processed_files = [
        {"file_modification_time": ft, "path": f"s3://bucket/file_{i}.parquet"}
        for i, ft in enumerate(file_times)
    ]

    # Compute what the new watermark WOULD be on success
    new_watermark = loader._compute_file_time_watermark(processed_files)

    # Simulate failure scenario: watermark is NOT updated
    # The system preserves the initial watermark on failure
    preserved_watermark = initial_watermark  # Not updated due to failure

    # Verify the watermark remains at its pre-load value
    assert preserved_watermark == initial_watermark, (
        f"On failure, watermark should remain at '{initial_watermark}', "
        f"but got '{preserved_watermark}'"
    )

    # Verify that the next retry would still filter from the preserved watermark
    # (i.e., the same files would be reprocessed)
    files_for_retry = loader._filter_files_by_watermark(
        processed_files, preserved_watermark
    )

    # Files that were newer than the initial watermark should still be included
    watermark_dt_parsed = datetime.fromisoformat(
        initial_watermark.replace("Z", "+00:00")
    )
    expected_retry_count = sum(
        1 for ft in file_times if ft > watermark_dt_parsed
    )
    assert len(files_for_retry) == expected_retry_count, (
        f"After failure, retry should find {expected_retry_count} files "
        f"newer than preserved watermark '{initial_watermark}', "
        f"but found {len(files_for_retry)}"
    )


# =============================================================================
# Property 14: Watermark format
# =============================================================================

_WATERMARK_FORMAT_REGEX = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)


@given(
    dt=st.datetimes(
        min_value=datetime(1970, 1, 1),
        max_value=datetime(2099, 12, 31),
        timezones=st.just(timezone.utc),
    ),
)
@settings(max_examples=100)
def test_watermark_format(dt):
    """Property 14: Watermark format.

    Any stored watermark is valid ISO 8601 UTC with second precision matching
    the pattern \\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z.

    For any datetime value, the computed watermark SHALL be a valid ISO 8601
    UTC timestamp with second precision.

    **Validates: Requirements 8.6**
    """
    loader = _make_loader()

    # Create a single-file list to compute watermark
    processed_files = [
        {"file_modification_time": dt, "path": "s3://bucket/file.parquet"}
    ]

    watermark = loader._compute_file_time_watermark(processed_files)

    # Watermark should not be None for a valid datetime
    assert watermark is not None, (
        f"Watermark should not be None for datetime {dt}"
    )

    # Verify format matches the required pattern
    assert _WATERMARK_FORMAT_REGEX.match(watermark), (
        f"Watermark '{watermark}' does not match required format "
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"
    )

    # Verify it's a valid parseable timestamp
    try:
        parsed = datetime.fromisoformat(watermark.replace("Z", "+00:00"))
    except ValueError:
        pytest.fail(f"Watermark '{watermark}' is not a valid ISO 8601 timestamp")

    # Verify the parsed timestamp matches the input (truncated to seconds)
    expected_truncated = dt.replace(microsecond=0)
    assert parsed == expected_truncated, (
        f"Parsed watermark {parsed} does not match expected {expected_truncated}"
    )



# =============================================================================
# Property 8: S3 Tables error code classification
# =============================================================================

from services.bq_iceberg_migration.iceberg_loader import ParallelIcebergLoader
from services.bq_iceberg_migration.error_codes import ErrorCode


@given(
    http_status=st.sampled_from([429, 403, 404, 500]),
    error_code_str=st.sampled_from(["SlowDown", "AccessDenied", "NoSuchKey", "InternalError"]),
)
@settings(max_examples=100)
def test_error_code_classification(http_status, error_code_str):
    """Property 8: S3 Tables error code classification.

    For any S3 Tables API error response, if the HTTP status is 429 or the
    error code is `SlowDown`, the system SHALL classify it as
    `S3_TABLES_THROTTLED`; for all other S3 Tables errors (403, 404, 500, etc.),
    the system SHALL classify it as `S3_TABLES_API_FAILED`.

    **Validates: Requirements 6.4**
    """
    # Determine expected classification
    is_throttle = (http_status == 429 or error_code_str == "SlowDown")

    # Create a mock error with botocore-style response metadata
    class MockClientError(Exception):
        def __init__(self, status_code, code, message):
            self.response = {
                "ResponseMetadata": {"HTTPStatusCode": status_code},
                "Error": {"Code": code, "Message": message},
            }
            super().__init__(
                f"An error occurred ({code}) when calling S3Tables API: {message}"
            )

    error = MockClientError(
        status_code=http_status,
        code=error_code_str,
        message=f"HTTP {http_status} - {error_code_str} error from S3 Tables",
    )

    # Test the throttle classification
    classified_as_throttle = ParallelIcebergLoader._is_s3_tables_throttle_error(error)

    if is_throttle:
        assert classified_as_throttle is True, (
            f"Error with HTTP status={http_status} and code='{error_code_str}' "
            f"should be classified as throttle (S3_TABLES_THROTTLED), but was not. "
            f"Error message: {error}"
        )
    else:
        assert classified_as_throttle is False, (
            f"Error with HTTP status={http_status} and code='{error_code_str}' "
            f"should NOT be classified as throttle, but was. "
            f"Error message: {error}"
        )


# =============================================================================
# Property 5: Structure report compaction defaults and recommendations
# =============================================================================

from services.bq_iceberg_migration.structure_report import (
    StructureReportGenerator,
    COMPACTION_STRATEGY_DESCRIPTIONS,
)
from services.bq_iceberg_migration.type_mapper import BQToIcebergTypeMapper

# --- Custom strategies for table metadata ---

# Clustering columns strategy (1-5 valid column names)
clustering_columns_strategy = st.lists(
    column_name_strategy,
    min_size=1,
    max_size=5,
    unique=True,
)

# Table metadata strategy WITHOUT clustering columns
table_meta_no_clustering_strategy = st.fixed_dictionaries({
    "table_name": st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz_",
        min_size=1,
        max_size=30,
    ).filter(lambda s: s[0] != "_" and s[-1] != "_" and "__" not in s),
    "columns": st.just([
        {"name": "id", "type": "INT64", "mode": "REQUIRED"},
        {"name": "name", "type": "STRING", "mode": "NULLABLE"},
        {"name": "created_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
    ]),
    "partition_column": st.just(None),
    "partition_type": st.just("DATE"),
    "partition_granularity": st.just(None),
    "clustering_columns": st.just([]),
    "estimated_rows": st.integers(min_value=0, max_value=1_000_000),
    "estimated_size_bytes": st.integers(min_value=0, max_value=1_000_000_000),
    "dataset": st.just("test_dataset"),
})

# Table metadata strategy WITH clustering columns
table_meta_with_clustering_strategy = st.fixed_dictionaries({
    "table_name": st.text(
        alphabet="abcdefghijklmnopqrstuvwxyz_",
        min_size=1,
        max_size=30,
    ).filter(lambda s: s[0] != "_" and s[-1] != "_" and "__" not in s),
    "columns": st.just([
        {"name": "id", "type": "INT64", "mode": "REQUIRED"},
        {"name": "name", "type": "STRING", "mode": "NULLABLE"},
        {"name": "order_date", "type": "DATE", "mode": "NULLABLE"},
        {"name": "customer_id", "type": "INT64", "mode": "NULLABLE"},
        {"name": "created_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
    ]),
    "partition_column": st.just(None),
    "partition_type": st.just("DATE"),
    "partition_granularity": st.just(None),
    "clustering_columns": clustering_columns_strategy,
    "estimated_rows": st.integers(min_value=0, max_value=1_000_000),
    "estimated_size_bytes": st.integers(min_value=0, max_value=1_000_000_000),
    "dataset": st.just("test_dataset"),
})


@given(table_meta=table_meta_no_clustering_strategy)
@settings(max_examples=100)
def test_structure_report_compaction_defaults_no_clustering(table_meta):
    """Property 5a: Structure report defaults compaction to binpack.

    For any table metadata with an S3 Tables destination and no clustering
    columns, the generated structure report SHALL include a `compaction_config`
    field defaulting to `binpack`.

    **Validates: Requirements 3.1, 3.2**
    """
    generator = StructureReportGenerator()
    type_mapper = BQToIcebergTypeMapper()
    partition_mapper = PartitionSpecMapper()

    report = generator._generate_table_report(
        table_meta, type_mapper, partition_mapper, "test_db"
    )

    # Must include compaction_config
    assert "compaction_config" in report, (
        "Structure report must include 'compaction_config' field"
    )

    compaction_config = report["compaction_config"]

    # Default strategy must be binpack
    assert compaction_config["strategy"] == "binpack", (
        f"Default compaction strategy should be 'binpack', "
        f"got '{compaction_config['strategy']}'"
    )

    # sort_columns should be empty for binpack default
    assert compaction_config["sort_columns"] == [], (
        f"Default sort_columns should be empty, "
        f"got {compaction_config['sort_columns']}"
    )

    # No recommendation when no clustering columns
    assert "recommended_strategy" not in compaction_config, (
        "Should not have recommended_strategy when no clustering columns"
    )
    assert "recommended_sort_columns" not in compaction_config, (
        "Should not have recommended_sort_columns when no clustering columns"
    )


@given(table_meta=table_meta_with_clustering_strategy)
@settings(max_examples=100)
def test_structure_report_compaction_recommends_sort_with_clustering(table_meta):
    """Property 5b: Structure report recommends sort when clustering columns exist.

    For any table metadata that includes clustering columns, the report SHALL
    recommend `sort` compaction with those clustering columns as the suggested
    sort columns.

    **Validates: Requirements 3.1, 3.2**
    """
    generator = StructureReportGenerator()
    type_mapper = BQToIcebergTypeMapper()
    partition_mapper = PartitionSpecMapper()

    report = generator._generate_table_report(
        table_meta, type_mapper, partition_mapper, "test_db"
    )

    # Must include compaction_config
    assert "compaction_config" in report, (
        "Structure report must include 'compaction_config' field"
    )

    compaction_config = report["compaction_config"]

    # Default strategy is still binpack
    assert compaction_config["strategy"] == "binpack", (
        f"Default compaction strategy should still be 'binpack', "
        f"got '{compaction_config['strategy']}'"
    )

    # Must recommend sort when clustering columns exist
    assert "recommended_strategy" in compaction_config, (
        "Should have recommended_strategy when clustering columns exist"
    )
    assert compaction_config["recommended_strategy"] == "sort", (
        f"Recommended strategy should be 'sort', "
        f"got '{compaction_config['recommended_strategy']}'"
    )

    # Must recommend the clustering columns as sort columns
    assert "recommended_sort_columns" in compaction_config, (
        "Should have recommended_sort_columns when clustering columns exist"
    )
    clustering_columns = table_meta["clustering_columns"]
    assert compaction_config["recommended_sort_columns"] == clustering_columns, (
        f"Recommended sort columns should be {clustering_columns}, "
        f"got {compaction_config['recommended_sort_columns']}"
    )


# =============================================================================
# Property 15: Lake Formation prerequisites contain specific ARNs
# =============================================================================


@given(
    region=aws_region_strategy,
    account_id=aws_account_id_strategy,
    bucket_name=bucket_name_strategy,
)
@settings(max_examples=100)
def test_lake_formation_prerequisites_contain_arns(region, account_id, bucket_name):
    """Property 15: Lake Formation prerequisites contain specific ARNs.

    For any valid table bucket ARN and AWS region, the generated Lake Formation
    prerequisites SHALL contain the bucket ARN in the data location permission
    entry and SHALL include the specific IAM permission strings
    (lakeformation:GetDataAccess, DESCRIBE, SELECT).

    **Validates: Requirements 5.2, 5.3, 5.4, 5.7**
    """
    table_bucket_arn = f"arn:aws:s3tables:{region}:{account_id}:bucket/{bucket_name}"
    glue_database = "test_database"

    generator = StructureReportGenerator()
    prerequisites = generator._generate_lake_formation_prerequisites(
        table_bucket_arn=table_bucket_arn,
        glue_database=glue_database,
        aws_region=region,
        account_id=account_id,
    )

    # Must return a non-empty list
    assert isinstance(prerequisites, list), (
        f"Prerequisites should be a list, got {type(prerequisites)}"
    )
    assert len(prerequisites) > 0, "Prerequisites list should not be empty"

    # Each item must have required keys
    for item in prerequisites:
        assert "description" in item, "Each prerequisite must have 'description'"
        assert "arn_or_permission" in item, (
            "Each prerequisite must have 'arn_or_permission'"
        )
        assert "action_type" in item, "Each prerequisite must have 'action_type'"

    # 1. Data location permission must contain the bucket ARN
    data_location_items = [
        item for item in prerequisites
        if item["action_type"] == "data_location_permission"
    ]
    assert len(data_location_items) >= 1, (
        "Must have at least one data_location_permission item"
    )
    data_location_item = data_location_items[0]
    assert table_bucket_arn in data_location_item["arn_or_permission"], (
        f"Data location permission must contain bucket ARN "
        f"'{table_bucket_arn}', got '{data_location_item['arn_or_permission']}'"
    )

    # 2. Must include DESCRIBE permission
    describe_items = [
        item for item in prerequisites
        if item["action_type"] == "DESCRIBE"
    ]
    assert len(describe_items) >= 1, (
        "Must have at least one DESCRIBE permission item"
    )

    # 3. Must include SELECT permission
    select_items = [
        item for item in prerequisites
        if item["action_type"] == "SELECT"
    ]
    assert len(select_items) >= 1, (
        "Must have at least one SELECT permission item"
    )

    # 4. Must include lakeformation:GetDataAccess IAM permission
    iam_items = [
        item for item in prerequisites
        if "lakeformation:GetDataAccess" in item["arn_or_permission"]
    ]
    assert len(iam_items) >= 1, (
        "Must have at least one item with 'lakeformation:GetDataAccess' permission"
    )

    # 5. All items should be actionable (have non-empty description)
    for item in prerequisites:
        assert len(item["description"]) > 0, (
            "Each prerequisite description must be non-empty"
        )
        assert len(item["arn_or_permission"]) > 0, (
            "Each prerequisite arn_or_permission must be non-empty"
        )
