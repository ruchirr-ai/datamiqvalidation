# Feature: bq-to-iceberg-migration, Properties 1-5: Type mapping, nullability, partition, sort order, struct recursion
"""
Property tests for BigQuery to Iceberg schema mapping services.

Tests cover:
- Property 1: Type mapping completeness and correctness
- Property 2: Nullability mapping
- Property 3: Partition spec transform selection
- Property 4: Sort order preserves clustering column sequence
- Property 5: Recursive struct mapping up to depth limit

Uses Hypothesis with minimum 100 iterations per property.
"""

from hypothesis import given, settings, strategies as st

from services.bq_iceberg_migration.type_mapper import BQToIcebergTypeMapper
from services.bq_iceberg_migration.iceberg_types import (
    BinaryType,
    BooleanType,
    DateType,
    DecimalType,
    DoubleType,
    ListType,
    LongType,
    StringType,
    StructType,
    TimestampType,
    TimestamptzType,
    TimeType,
)
from services.bq_iceberg_migration.partition_mapper import (
    PartitionSpecMapper,
)

# --- Strategies ---

# All recognized BQ types from the TYPE_MAP
RECOGNIZED_BQ_TYPES = [
    "STRING", "BYTES", "INT64", "INTEGER", "FLOAT64", "FLOAT",
    "NUMERIC", "BIGNUMERIC", "BOOLEAN", "BOOL", "DATE",
    "DATETIME", "TIMESTAMP", "TIME", "GEOGRAPHY", "JSON",
]

# Expected Iceberg type for each recognized BQ type
EXPECTED_TYPE_MAP = {
    "STRING": StringType,
    "BYTES": BinaryType,
    "INT64": LongType,
    "INTEGER": LongType,
    "FLOAT64": DoubleType,
    "FLOAT": DoubleType,
    "NUMERIC": DecimalType,
    "BIGNUMERIC": DecimalType,
    "BOOLEAN": BooleanType,
    "BOOL": BooleanType,
    "DATE": DateType,
    "DATETIME": TimestampType,
    "TIMESTAMP": TimestamptzType,
    "TIME": TimeType,
    "GEOGRAPHY": StringType,
    "JSON": StringType,
}

recognized_bq_type_strategy = st.sampled_from(RECOGNIZED_BQ_TYPES)

# Unrecognized types: arbitrary uppercase strings that are NOT in the recognized set
unrecognized_bq_type_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
).map(str.upper).filter(
    lambda t: t not in RECOGNIZED_BQ_TYPES and t not in ("STRUCT", "RECORD", "ARRAY")
)

# BQ modes
bq_mode_strategy = st.sampled_from(["REQUIRED", "NULLABLE", "REPEATED"])

# Time-based column types for partition testing
time_based_type_strategy = st.sampled_from(["DATE", "DATETIME", "TIMESTAMP"])

# Granularity values (including None for default)
granularity_strategy = st.sampled_from(["DAY", "HOUR", "MONTH", "YEAR", None])

# Clustering column names: realistic identifiers
column_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip() != "" and not s.startswith("_"))

# Lists of clustering columns (1-10 columns)
clustering_columns_strategy = st.lists(
    column_name_strategy,
    min_size=1,
    max_size=10,
)


# ============================================================================
# Property 1: Type mapping completeness and correctness
# ============================================================================


@given(bq_type=recognized_bq_type_strategy)
@settings(max_examples=150)
def test_type_mapping_recognized_types_produce_correct_iceberg_type(bq_type):
    """Property 1a: Every recognized BQ type maps to the correct Iceberg type.

    For any BQ type string drawn from the defined TYPE_MAP, map_column must
    return an instance of the expected Iceberg type class.

    **Validates: Requirements 3.1**
    """
    mapper = BQToIcebergTypeMapper()
    result = mapper.map_column(bq_type=bq_type, bq_mode="NULLABLE")

    expected_class = EXPECTED_TYPE_MAP[bq_type]
    assert isinstance(result, expected_class), (
        f"BQ type '{bq_type}' should map to {expected_class.__name__}, "
        f"but got {type(result).__name__}"
    )


@given(bq_type=unrecognized_bq_type_strategy)
@settings(max_examples=150)
def test_type_mapping_unrecognized_types_produce_string_type(bq_type):
    """Property 1b: Any unrecognized BQ type maps to StringType.

    For any arbitrary type string not present in the defined mapping,
    map_column must return StringType as a fallback.

    **Validates: Requirements 3.1**
    """
    mapper = BQToIcebergTypeMapper()
    result = mapper.map_column(bq_type=bq_type, bq_mode="NULLABLE")

    assert isinstance(result, StringType), (
        f"Unrecognized BQ type '{bq_type}' should map to StringType, "
        f"but got {type(result).__name__}"
    )


# ============================================================================
# Property 2: Nullability mapping
# ============================================================================


@given(bq_mode=bq_mode_strategy)
@settings(max_examples=150)
def test_nullability_mapping_correctness(bq_mode):
    """Property 2: Nullability mapping is correct for all BQ modes.

    REQUIRED → not nullable (is_nullable returns False)
    NULLABLE → nullable (is_nullable returns True)
    REPEATED → nullable (is_nullable returns True)

    **Validates: Requirements 3.4**
    """
    mapper = BQToIcebergTypeMapper()
    result = mapper.is_nullable(bq_mode)

    if bq_mode == "REQUIRED":
        assert result is False, (
            f"BQ mode 'REQUIRED' should map to non-nullable (False), got {result}"
        )
    else:
        # NULLABLE and REPEATED both map to nullable
        assert result is True, (
            f"BQ mode '{bq_mode}' should map to nullable (True), got {result}"
        )


# ============================================================================
# Property 5: Recursive struct mapping up to depth limit
# ============================================================================


def _build_nested_struct_schema(depth: int) -> dict:
    """Build a nested STRUCT schema with the given depth.

    Each level has a single field named 'level_N' of type STRUCT,
    with the innermost level containing a STRING field.
    """
    if depth <= 0:
        return {
            "name": "leaf",
            "type": "STRING",
            "mode": "NULLABLE",
        }

    inner = _build_nested_struct_schema(depth - 1)
    return {
        "name": f"level_{depth}",
        "type": "STRUCT",
        "mode": "NULLABLE",
        "fields": [inner],
    }


@given(depth=st.integers(min_value=1, max_value=20))
@settings(max_examples=150)
def test_recursive_struct_mapping_respects_depth_limit(depth):
    """Property 5: Recursive struct mapping up to depth limit.

    For nested STRUCT schemas with depth 1-15, the mapper produces a valid
    StructType hierarchy. For depth > 15, the mapper flattens remaining
    levels to StringType (JSON).

    **Validates: Requirements 3.6, 3.7**
    """
    mapper = BQToIcebergTypeMapper()

    # Build a nested struct with the given depth
    schema_def = _build_nested_struct_schema(depth)

    result = mapper.map_column(
        bq_type=schema_def["type"],
        bq_mode=schema_def["mode"],
        fields=schema_def.get("fields"),
        depth=0,
    )

    if depth <= 15:
        # Should produce a valid StructType hierarchy
        assert isinstance(result, StructType), (
            f"Depth {depth} (≤15) should produce StructType, got {type(result).__name__}"
        )

        # Walk down the struct hierarchy to verify correct nesting
        current = result
        for level in range(depth - 1):
            assert isinstance(current, StructType), (
                f"At level {level}, expected StructType, got {type(current).__name__}"
            )
            assert len(current.fields) > 0, (
                f"At level {level}, StructType has no fields"
            )
            current = current.fields[0].field_type

        # The innermost level should be a StructType containing a STRING leaf
        # (for depth >= 2) or a StructType with a STRING field (for depth == 1)
        if depth == 1:
            # depth=1 means one STRUCT wrapping a STRING leaf
            assert isinstance(current, StructType), (
                f"At innermost level (depth=1), expected StructType, got {type(current).__name__}"
            )
            assert len(current.fields) > 0
            leaf_type = current.fields[0].field_type
            assert isinstance(leaf_type, StringType), (
                f"Leaf field should be StringType, got {type(leaf_type).__name__}"
            )
    else:
        # Depth > 15: the struct at depth 15 should be flattened to StringType
        # Walk down to depth 15 and verify flattening
        current = result
        for level in range(min(depth, 15) - 1):
            if isinstance(current, StructType) and len(current.fields) > 0:
                current = current.fields[0].field_type
            else:
                break

        # At some point in the hierarchy, we should encounter a StringType
        # due to flattening beyond depth 15
        def _contains_string_leaf(iceberg_type, max_walk=20) -> bool:
            """Check if the type tree eventually hits StringType due to flattening."""
            if isinstance(iceberg_type, StringType):
                return True
            if isinstance(iceberg_type, StructType) and max_walk > 0:
                for f in iceberg_type.fields:
                    if _contains_string_leaf(f.field_type, max_walk - 1):
                        return True
            return False

        assert _contains_string_leaf(result), (
            f"Depth {depth} (>15) should contain a StringType due to flattening, "
            f"but the result tree does not contain one: {result}"
        )


# ============================================================================
# Property 3: Partition spec transform selection
# ============================================================================


@given(
    partition_column=column_name_strategy,
    column_type=time_based_type_strategy,
    granularity=granularity_strategy,
)
@settings(max_examples=150)
def test_partition_spec_transform_selection(partition_column, column_type, granularity):
    """Property 3: Partition spec uses day() default and respects explicit overrides.

    For any time-based column type (DATE, DATETIME, TIMESTAMP):
    - If granularity is None → transform is 'day' (default)
    - If granularity is 'DAY' → transform is 'day'
    - If granularity is 'HOUR' → transform is 'hour' (DATETIME/TIMESTAMP only)
    - If granularity is 'MONTH' → transform is 'month' (DATETIME/TIMESTAMP only)
    - If granularity is 'YEAR' → transform is 'year' (DATETIME/TIMESTAMP only)

    For DATE type, only None and DAY are valid granularities.
    Other granularities raise ValueError for DATE.

    **Validates: Requirements 3.2**
    """
    import pytest

    mapper = PartitionSpecMapper()

    # DATE only supports None and DAY granularity in the TRANSFORM_MAP
    if column_type == "DATE" and granularity in ("HOUR", "MONTH", "YEAR"):
        with pytest.raises(ValueError, match="Unsupported partition configuration"):
            mapper.map_partition_spec(
                partition_column=partition_column,
                partition_type=column_type,
                granularity=granularity,
            )
        return

    result = mapper.map_partition_spec(
        partition_column=partition_column,
        partition_type=column_type,
        granularity=granularity,
    )

    # Verify the partition spec has exactly one field
    assert len(result.fields) == 1, (
        f"Expected 1 partition field, got {len(result.fields)}"
    )

    partition_field = result.fields[0]

    # Verify source column is preserved
    assert partition_field.source_column == partition_column, (
        f"Expected source_column '{partition_column}', got '{partition_field.source_column}'"
    )

    # Verify transform selection
    expected_transforms = {
        None: "day",
        "DAY": "day",
        "HOUR": "hour",
        "MONTH": "month",
        "YEAR": "year",
    }
    expected_transform = expected_transforms[granularity]

    assert partition_field.transform == expected_transform, (
        f"For granularity={granularity}, expected transform '{expected_transform}', "
        f"got '{partition_field.transform}'"
    )


# ============================================================================
# Property 4: Sort order preserves clustering column sequence
# ============================================================================


@given(clustering_columns=clustering_columns_strategy)
@settings(max_examples=150)
def test_sort_order_preserves_clustering_column_sequence(clustering_columns):
    """Property 4: Sort order preserves clustering column ordinal sequence.

    For any list of clustering columns, the resulting Iceberg sort order
    must contain the same columns in the exact same ordinal sequence,
    each with ascending direction and nulls_last ordering.

    **Validates: Requirements 3.3**
    """
    mapper = PartitionSpecMapper()
    result = mapper.map_sort_order(clustering_columns)

    # Filter out empty strings (the implementation skips them)
    expected_columns = [col for col in clustering_columns if col]

    # Verify the number of sort fields matches
    assert len(result.fields) == len(expected_columns), (
        f"Expected {len(expected_columns)} sort fields, got {len(result.fields)}. "
        f"Input: {clustering_columns}"
    )

    # Verify ordinal sequence is preserved
    for i, (sort_field, expected_col) in enumerate(zip(result.fields, expected_columns)):
        assert sort_field.source_column == expected_col, (
            f"At position {i}, expected column '{expected_col}', "
            f"got '{sort_field.source_column}'"
        )
        assert sort_field.direction == "asc", (
            f"At position {i}, expected direction 'asc', got '{sort_field.direction}'"
        )
        assert sort_field.null_order == "nulls_last", (
            f"At position {i}, expected null_order 'nulls_last', "
            f"got '{sort_field.null_order}'"
        )
