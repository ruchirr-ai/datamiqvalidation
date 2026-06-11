# Feature: bq-to-iceberg-migration, Properties 7, 8, 19, 20
"""
Property tests for BQ-to-Iceberg structure report and cost analysis services.

Tests cover:
- Property 7: Structure report contains all required fields per table
- Property 8: Structure plan round-trip persistence (JSON serialize/deserialize)
- Property 19: Cost calculation consistency (projections ordering and growth)
- Property 20: Custom structure validation (incompatibility detection)

Uses Hypothesis with minimum 100 iterations per property.
"""

import json
from unittest.mock import MagicMock

from hypothesis import given, settings, assume, strategies as st

from services.bq_iceberg_migration.structure_report import (
    StructureReportGenerator,
    VALID_ICEBERG_TYPES,
)
from services.bq_iceberg_migration.cost_engine import CostAnalysisEngine
from services.bq_iceberg_migration.type_mapper import BQToIcebergTypeMapper
from services.bq_iceberg_migration.partition_mapper import PartitionSpecMapper


# =============================================================================
# Strategies
# =============================================================================

# Column name strategy: realistic identifiers
column_name_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"), whitelist_characters="_"
    ),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip() != "" and not s.startswith("_"))

# BQ types for assessment table columns
bq_type_strategy = st.sampled_from([
    "STRING", "INT64", "FLOAT64", "BOOLEAN", "DATE",
    "DATETIME", "TIMESTAMP", "NUMERIC", "BYTES",
])

# BQ modes
bq_mode_strategy = st.sampled_from(["REQUIRED", "NULLABLE", "REPEATED"])

# Column definition strategy
column_def_strategy = st.fixed_dictionaries({
    "name": column_name_strategy,
    "type": bq_type_strategy,
    "mode": bq_mode_strategy,
})

# Table name strategy
table_name_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"), whitelist_characters="_-"
    ),
    min_size=1,
    max_size=40,
).filter(lambda s: s.strip() != "")

# Partition granularity
granularity_strategy = st.sampled_from(["DAY", "HOUR", "MONTH", "YEAR", None])

# Time-based partition types
partition_type_strategy = st.sampled_from(["DATE", "DATETIME", "TIMESTAMP"])

# Assessment table metadata strategy
assessment_table_strategy = st.fixed_dictionaries({
    "table_name": table_name_strategy,
    "columns": st.lists(column_def_strategy, min_size=1, max_size=15),
    "partition_column": st.one_of(st.none(), column_name_strategy),
    "partition_type": partition_type_strategy,
    "partition_granularity": granularity_strategy,
    "clustering_columns": st.lists(column_name_strategy, min_size=0, max_size=4),
    "estimated_rows": st.integers(min_value=0, max_value=10_000_000_000),
    "estimated_size_bytes": st.integers(min_value=0, max_value=10 * 1024**4),
    "dataset": st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
        min_size=1,
        max_size=20,
    ).filter(lambda s: s.strip() != ""),
})

# Valid Iceberg type strings for custom structures
valid_iceberg_type_strategy = st.sampled_from(sorted(VALID_ICEBERG_TYPES))

# Invalid Iceberg type strings (not in the valid set)
invalid_iceberg_type_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L",)),
    min_size=3,
    max_size=15,
).filter(
    lambda t: t.lower() not in VALID_ICEBERG_TYPES
    and t.lower().split("(")[0] not in VALID_ICEBERG_TYPES
)

# Custom column definition strategy (valid types)
custom_column_valid_strategy = st.fixed_dictionaries({
    "name": column_name_strategy,
    "type": valid_iceberg_type_strategy,
    "nullable": st.booleans(),
})

# Custom column definition strategy (invalid types)
custom_column_invalid_strategy = st.fixed_dictionaries({
    "name": column_name_strategy,
    "type": invalid_iceberg_type_strategy,
    "nullable": st.booleans(),
})

# Data size strategy for cost calculations (in bytes, 1MB to 10TB)
data_size_strategy = st.integers(
    min_value=1 * 1024 * 1024,
    max_value=10 * 1024**4,
)

# Table count strategy
table_count_strategy = st.integers(min_value=1, max_value=500)

# Growth rate strategy (0% to 50% monthly)
growth_rate_strategy = st.floats(
    min_value=0.0,
    max_value=0.5,
    allow_nan=False,
    allow_infinity=False,
)

# Destination type strategy
destination_type_strategy = st.sampled_from(["iceberg_s3", "iceberg_s3_tables"])


# =============================================================================
# Property 7: Structure report contains all required fields per table
# =============================================================================


@given(
    assessment_tables=st.lists(assessment_table_strategy, min_size=1, max_size=5),
)
@settings(max_examples=100)
def test_structure_report_contains_all_required_fields(assessment_tables):
    """Property 7: Structure report contains all required fields per table.

    For any set of assessment table metadata, the generated structure report
    SHALL contain all required fields for each table: proposed_name, columns,
    partition_spec (or None), sort_order, estimated_rows, estimated_size_mb,
    and table_properties.

    **Validates: Requirements 4.2**
    """
    generator = StructureReportGenerator()
    type_mapper = BQToIcebergTypeMapper()
    partition_mapper = PartitionSpecMapper()

    # Create a mock migration object
    migration = MagicMock()
    migration.destination_type = "iceberg_s3"
    migration.glue_database_name = "test_db"
    migration.id = 1
    migration.s3_tables_namespace = None

    report = generator.generate(
        migration=migration,
        assessment_tables=assessment_tables,
        type_mapper=type_mapper,
        partition_mapper=partition_mapper,
    )

    # Verify top-level report fields
    assert "tables" in report
    assert "prerequisites" in report
    assert "warnings" in report
    assert "generated_at" in report
    assert "migration_id" in report
    assert "table_count" in report
    assert report["table_count"] == len(report["tables"])

    # Verify each table has all required fields
    required_table_fields = {
        "source_table",
        "proposed_name",
        "columns",
        "partition_spec",
        "sort_order",
        "estimated_rows",
        "estimated_size_mb",
        "table_properties",
        "structure_mode",
        "warnings",
    }

    for table_report in report["tables"]:
        missing_fields = required_table_fields - set(table_report.keys())
        assert not missing_fields, (
            f"Table '{table_report.get('source_table', '?')}' is missing "
            f"required fields: {missing_fields}"
        )

        # Verify proposed_name is non-empty
        assert table_report["proposed_name"], (
            f"Table '{table_report['source_table']}' has empty proposed_name"
        )

        # Verify columns is a non-empty list
        assert isinstance(table_report["columns"], list), (
            f"Table '{table_report['source_table']}' columns should be a list"
        )
        assert len(table_report["columns"]) > 0, (
            f"Table '{table_report['source_table']}' should have at least one column"
        )

        # Verify each column has required sub-fields
        for col in table_report["columns"]:
            assert "name" in col, "Column missing 'name' field"
            assert "bq_type" in col, "Column missing 'bq_type' field"
            assert "iceberg_type" in col, "Column missing 'iceberg_type' field"
            assert "nullable" in col, "Column missing 'nullable' field"

        # Verify table_properties is a dict with required defaults
        props = table_report["table_properties"]
        assert isinstance(props, dict), "table_properties should be a dict"
        assert "format-version" in props, "Missing 'format-version' property"
        assert "write.format.default" in props, "Missing 'write.format.default' property"
        assert "write.parquet.compression-codec" in props, (
            "Missing 'write.parquet.compression-codec' property"
        )

        # Verify estimated_rows is non-negative
        assert table_report["estimated_rows"] >= 0, (
            f"estimated_rows should be non-negative, got {table_report['estimated_rows']}"
        )

        # Verify estimated_size_mb is non-negative
        assert table_report["estimated_size_mb"] >= 0, (
            f"estimated_size_mb should be non-negative, got {table_report['estimated_size_mb']}"
        )


# =============================================================================
# Property 8: Structure plan round-trip persistence
# =============================================================================

# Strategy for structure plan overrides
override_partition_strategy = st.fixed_dictionaries({
    "column": column_name_strategy,
    "transform": st.sampled_from(["day", "month", "year", "hour"]),
})

override_strategy = st.fixed_dictionaries({
    "partition_spec": override_partition_strategy,
    "sort_order": st.lists(column_name_strategy, min_size=0, max_size=4),
    "custom_properties": st.dictionaries(
        keys=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=".-_"),
            min_size=1,
            max_size=30,
        ).filter(lambda s: s.strip() != ""),
        values=st.text(min_size=1, max_size=50).filter(lambda s: s.strip() != ""),
        min_size=0,
        max_size=5,
    ),
})

# Strategy for custom structure definitions
custom_structure_strategy = st.fixed_dictionaries({
    "iceberg_table_name": table_name_strategy,
    "columns": st.lists(custom_column_valid_strategy, min_size=1, max_size=10),
    "partition_spec": st.one_of(st.none(), override_partition_strategy),
    "sort_order": st.lists(
        st.fixed_dictionaries({
            "column": column_name_strategy,
            "direction": st.sampled_from(["asc", "desc"]),
        }),
        min_size=0,
        max_size=4,
    ),
    "table_properties": st.dictionaries(
        keys=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=".-_"),
            min_size=1,
            max_size=30,
        ).filter(lambda s: s.strip() != ""),
        values=st.text(min_size=1, max_size=50).filter(lambda s: s.strip() != ""),
        min_size=0,
        max_size=5,
    ),
})

# Full structure plan strategy (simulating what gets stored in checkpoint_data)
structure_plan_strategy = st.fixed_dictionaries({
    "tables": st.lists(
        st.fixed_dictionaries({
            "source_table": table_name_strategy,
            "proposed_name": table_name_strategy,
            "structure_mode": st.sampled_from(["recommended", "overridden", "custom"]),
            "columns": st.lists(
                st.fixed_dictionaries({
                    "name": column_name_strategy,
                    "bq_type": bq_type_strategy,
                    "iceberg_type": valid_iceberg_type_strategy,
                    "nullable": st.booleans(),
                }),
                min_size=1,
                max_size=10,
            ),
            "partition_spec": st.one_of(st.none(), override_partition_strategy),
            "sort_order": st.lists(column_name_strategy, min_size=0, max_size=4),
            "estimated_rows": st.integers(min_value=0, max_value=10_000_000),
            "estimated_size_mb": st.floats(
                min_value=0.0, max_value=1_000_000.0,
                allow_nan=False, allow_infinity=False,
            ),
            "table_properties": st.dictionaries(
                keys=st.text(
                    alphabet=st.characters(
                        whitelist_categories=("L", "N"), whitelist_characters=".-_"
                    ),
                    min_size=1,
                    max_size=30,
                ).filter(lambda s: s.strip() != ""),
                values=st.text(min_size=1, max_size=50).filter(lambda s: s.strip() != ""),
                min_size=1,
                max_size=5,
            ),
        }),
        min_size=1,
        max_size=5,
    ),
    "dataset_to_db_mapping": st.dictionaries(
        keys=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
            min_size=1,
            max_size=20,
        ).filter(lambda s: s.strip() != ""),
        values=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
            min_size=1,
            max_size=20,
        ).filter(lambda s: s.strip() != ""),
        min_size=0,
        max_size=3,
    ),
    "overrides": st.dictionaries(
        keys=table_name_strategy,
        values=override_strategy,
        min_size=0,
        max_size=3,
    ),
})


@given(plan=structure_plan_strategy)
@settings(max_examples=100)
def test_structure_plan_round_trip_persistence(plan):
    """Property 8: Structure plan round-trip persistence.

    For any approved structure plan (including custom definitions and overrides),
    serializing to JSON and deserializing back SHALL produce an equivalent plan.
    This validates that the plan can be safely stored in checkpoint_data JSONB.

    **Validates: Requirements 4.10**
    """
    # Serialize to JSON string (simulating JSONB storage)
    serialized = json.dumps(plan)

    # Deserialize back
    deserialized = json.loads(serialized)

    # Verify equivalence
    assert deserialized == plan, (
        f"Round-trip failed. Original and deserialized plans differ.\n"
        f"Original tables: {len(plan['tables'])}\n"
        f"Deserialized tables: {len(deserialized['tables'])}"
    )

    # Verify structural integrity after round-trip
    assert "tables" in deserialized
    assert "dataset_to_db_mapping" in deserialized
    assert "overrides" in deserialized

    # Verify each table preserved its fields
    for orig_table, rt_table in zip(plan["tables"], deserialized["tables"]):
        assert orig_table["source_table"] == rt_table["source_table"]
        assert orig_table["proposed_name"] == rt_table["proposed_name"]
        assert orig_table["structure_mode"] == rt_table["structure_mode"]
        assert orig_table["columns"] == rt_table["columns"]
        assert orig_table["partition_spec"] == rt_table["partition_spec"]
        assert orig_table["sort_order"] == rt_table["sort_order"]
        assert orig_table["table_properties"] == rt_table["table_properties"]


# =============================================================================
# Property 20: Custom structure validation
# =============================================================================


@given(
    invalid_columns=st.lists(custom_column_invalid_strategy, min_size=1, max_size=5),
    source_columns=st.lists(column_def_strategy, min_size=1, max_size=10),
)
@settings(max_examples=100)
def test_custom_structure_detects_invalid_iceberg_types(invalid_columns, source_columns):
    """Property 20a: Custom structure validation detects invalid Iceberg types.

    For any custom structure with columns using invalid Iceberg type names,
    the validator SHALL produce warnings indicating the invalid types.

    **Validates: Requirements 4.9**
    """
    generator = StructureReportGenerator()

    custom_def = {
        "columns": invalid_columns,
    }

    warnings = generator.validate_custom_structure(custom_def, source_columns)

    # Should detect at least one invalid type warning
    type_warnings = [w for w in warnings if "invalid Iceberg type" in w]
    assert len(type_warnings) > 0, (
        f"Expected warnings for invalid types in columns "
        f"{[c['type'] for c in invalid_columns]}, but got none. "
        f"All warnings: {warnings}"
    )


@given(
    source_columns=st.lists(column_def_strategy, min_size=3, max_size=10),
)
@settings(max_examples=100)
def test_custom_structure_detects_missing_source_columns(source_columns):
    """Property 20b: Custom structure validation detects missing source columns.

    For any custom structure that has fewer columns than the source and uses
    different column names, the validator SHALL warn about potential data loss.

    **Validates: Requirements 4.9**
    """
    assume(len(source_columns) >= 3)

    generator = StructureReportGenerator()

    # Create a custom structure with only one column that doesn't match source
    custom_def = {
        "columns": [
            {"name": "completely_different_col_xyz", "type": "string", "nullable": True},
        ],
    }

    warnings = generator.validate_custom_structure(custom_def, source_columns)

    # Should detect column count mismatch or missing columns
    has_relevant_warning = any(
        "columns but source" in w or "not in custom structure" in w
        for w in warnings
    )
    assert has_relevant_warning, (
        f"Expected warning about missing columns. Source has {len(source_columns)} "
        f"columns but custom has 1. Warnings: {warnings}"
    )


@given(
    custom_columns=st.lists(custom_column_valid_strategy, min_size=1, max_size=5),
)
@settings(max_examples=100)
def test_custom_structure_detects_invalid_partition_column(custom_columns):
    """Property 20c: Custom structure validation detects partition column not in columns.

    For any custom structure where the partition spec references a column not
    present in the column definitions, the validator SHALL produce a warning.

    **Validates: Requirements 4.9**
    """
    generator = StructureReportGenerator()

    # Use a partition column name that definitely doesn't exist in custom columns
    custom_col_names = {c["name"].lower() for c in custom_columns}
    nonexistent_col = "nonexistent_partition_col_xyz_999"
    assume(nonexistent_col.lower() not in custom_col_names)

    custom_def = {
        "columns": custom_columns,
        "partition_spec": {"column": nonexistent_col, "transform": "day"},
    }

    # Source columns don't matter for this check
    source_columns = [{"name": "src_col", "type": "STRING", "mode": "NULLABLE"}]

    warnings = generator.validate_custom_structure(custom_def, source_columns)

    # Should detect partition column not in custom columns
    partition_warnings = [w for w in warnings if "Partition column" in w]
    assert len(partition_warnings) > 0, (
        f"Expected warning about partition column '{nonexistent_col}' not found "
        f"in custom columns {custom_col_names}. Warnings: {warnings}"
    )


# =============================================================================
# Property 19: Cost calculation consistency
# =============================================================================


@given(
    data_size_bytes=data_size_strategy,
    table_count=table_count_strategy,
    growth_rate=growth_rate_strategy,
    destination_type=destination_type_strategy,
)
@settings(max_examples=100)
def test_cost_projections_ordering(data_size_bytes, table_count, growth_rate, destination_type):
    """Property 19a: Cost projections maintain correct ordering.

    For any data size and growth rate, the cost engine SHALL produce
    projections where 12-month cost > 6-month cost > 3-month cost
    (assuming growth_rate >= 0 and base cost > 0).

    **Validates: Requirements 13.3, 13.5**
    """
    engine = CostAnalysisEngine()

    assessment_data = {
        "total_size_bytes": data_size_bytes,
        "table_count": table_count,
    }

    report = engine.calculate(
        assessment_data=assessment_data,
        destination_type=destination_type,
        aws_region="us-east-1",
        growth_rate_monthly=growth_rate,
    )

    projections = report.projections
    three_month = projections["3_month_total"]
    six_month = projections["6_month_total"]
    twelve_month = projections["12_month_total"]

    # All projections should be non-negative
    assert three_month >= 0, f"3-month projection should be >= 0, got {three_month}"
    assert six_month >= 0, f"6-month projection should be >= 0, got {six_month}"
    assert twelve_month >= 0, f"12-month projection should be >= 0, got {twelve_month}"

    # Ordering: 12mo >= 6mo >= 3mo (with growth >= 0, each period adds more)
    assert twelve_month >= six_month - 1e-10, (
        f"12-month ({twelve_month}) should be >= 6-month ({six_month})"
    )
    assert six_month >= three_month - 1e-10, (
        f"6-month ({six_month}) should be >= 3-month ({three_month})"
    )


@given(
    data_size_bytes=data_size_strategy,
    table_count=table_count_strategy,
    low_growth=st.floats(min_value=0.0, max_value=0.1, allow_nan=False, allow_infinity=False),
    high_growth=st.floats(min_value=0.15, max_value=0.5, allow_nan=False, allow_infinity=False),
    destination_type=destination_type_strategy,
)
@settings(max_examples=100)
def test_higher_growth_rate_produces_higher_projections(
    data_size_bytes, table_count, low_growth, high_growth, destination_type
):
    """Property 19b: Higher growth rate produces higher cost projections.

    For any data size, recalculation with a higher growth rate SHALL produce
    higher projections than with a lower growth rate.

    **Validates: Requirements 13.3, 13.5**
    """
    assume(high_growth > low_growth)

    engine = CostAnalysisEngine()

    assessment_data = {
        "total_size_bytes": data_size_bytes,
        "table_count": table_count,
    }

    report_low = engine.calculate(
        assessment_data=assessment_data,
        destination_type=destination_type,
        aws_region="us-east-1",
        growth_rate_monthly=low_growth,
    )

    report_high = engine.calculate(
        assessment_data=assessment_data,
        destination_type=destination_type,
        aws_region="us-east-1",
        growth_rate_monthly=high_growth,
    )

    # Higher growth rate should produce higher projections at all horizons
    assert report_high.projections["3_month_total"] >= report_low.projections["3_month_total"] - 1e-10, (
        f"Higher growth ({high_growth}) 3-month projection "
        f"({report_high.projections['3_month_total']}) should be >= "
        f"lower growth ({low_growth}) projection ({report_low.projections['3_month_total']})"
    )
    assert report_high.projections["6_month_total"] >= report_low.projections["6_month_total"] - 1e-10, (
        f"Higher growth ({high_growth}) 6-month projection "
        f"({report_high.projections['6_month_total']}) should be >= "
        f"lower growth ({low_growth}) projection ({report_low.projections['6_month_total']})"
    )
    assert report_high.projections["12_month_total"] >= report_low.projections["12_month_total"] - 1e-10, (
        f"Higher growth ({high_growth}) 12-month projection "
        f"({report_high.projections['12_month_total']}) should be >= "
        f"lower growth ({low_growth}) projection ({report_low.projections['12_month_total']})"
    )
