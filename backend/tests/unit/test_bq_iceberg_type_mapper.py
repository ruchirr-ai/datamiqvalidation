"""
Unit tests for BQToIcebergTypeMapper service.

Tests all BigQuery-to-Iceberg type mappings, recursive STRUCT/ARRAY handling,
nullability mapping, depth limit flattening, and unrecognized type fallback.

Requirements: 3.1, 3.4, 3.5, 3.6, 3.7
"""

import logging

import pytest

from services.bq_iceberg_migration.type_mapper import BQToIcebergTypeMapper
from services.bq_iceberg_migration.iceberg_types import (
    BinaryType,
    BooleanType,
    DateType,
    DecimalType,
    DoubleType,
    ListType,
    LongType,
    NestedField,
    Schema,
    StringType,
    StructType,
    TimestampType,
    TimestamptzType,
    TimeType,
)


# --- Sample payloads ---

SIMPLE_SCHEMA_PAYLOAD = [
    {"name": "id", "type": "INT64", "mode": "REQUIRED"},
    {"name": "name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "created_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
]

NESTED_STRUCT_PAYLOAD = [
    {
        "name": "address",
        "type": "STRUCT",
        "mode": "NULLABLE",
        "fields": [
            {"name": "street", "type": "STRING", "mode": "NULLABLE"},
            {"name": "city", "type": "STRING", "mode": "NULLABLE"},
            {"name": "zip", "type": "STRING", "mode": "REQUIRED"},
        ],
    }
]

REPEATED_FIELD_PAYLOAD = [
    {"name": "tags", "type": "STRING", "mode": "REPEATED"},
]

DEEPLY_NESTED_STRUCT_PAYLOAD = {
    "name": "level_0",
    "type": "STRUCT",
    "mode": "NULLABLE",
    "fields": None,  # Will be built dynamically in tests
}


class TestTypeMapCompleteness:
    """Test all defined BigQuery-to-Iceberg type mappings (Requirement 3.1)."""

    @pytest.mark.parametrize(
        "bq_type, expected_type",
        [
            ("STRING", StringType()),
            ("BYTES", BinaryType()),
            ("INT64", LongType()),
            ("INTEGER", LongType()),
            ("FLOAT64", DoubleType()),
            ("FLOAT", DoubleType()),
            ("NUMERIC", DecimalType(38, 9)),
            ("BIGNUMERIC", DecimalType(38, 18)),
            ("BOOLEAN", BooleanType()),
            ("BOOL", BooleanType()),
            ("DATE", DateType()),
            ("DATETIME", TimestampType()),
            ("TIMESTAMP", TimestamptzType()),
            ("TIME", TimeType()),
            ("GEOGRAPHY", StringType()),
            ("JSON", StringType()),
        ],
    )
    def test_primitive_type_mapping(self, bq_type, expected_type):
        """Each BQ primitive type maps to the correct Iceberg type."""
        mapper = BQToIcebergTypeMapper()
        result = mapper.map_column(bq_type, "NULLABLE")
        assert result == expected_type

    def test_type_map_has_all_entries(self):
        """TYPE_MAP should contain all 16 defined mappings."""
        assert len(BQToIcebergTypeMapper.TYPE_MAP) == 16

    def test_case_insensitive_type_lookup(self):
        """Type lookup should be case-insensitive."""
        mapper = BQToIcebergTypeMapper()
        assert mapper.map_column("string", "NULLABLE") == StringType()
        assert mapper.map_column("Int64", "NULLABLE") == LongType()
        assert mapper.map_column("  BOOLEAN  ", "NULLABLE") == BooleanType()


class TestUnrecognizedTypes:
    """Test fallback behavior for unrecognized types (Requirement 3.5)."""

    def test_unrecognized_type_maps_to_string(self):
        """Unrecognized BQ type should map to StringType."""
        mapper = BQToIcebergTypeMapper()
        result = mapper.map_column("UNKNOWN_TYPE", "NULLABLE")
        assert result == StringType()

    def test_unrecognized_type_logs_warning(self, caplog):
        """Unrecognized BQ type should log a warning."""
        mapper = BQToIcebergTypeMapper()
        with caplog.at_level(logging.WARNING):
            mapper.map_column("CUSTOM_TYPE_XYZ", "NULLABLE")
        assert "Unrecognized BigQuery type 'CUSTOM_TYPE_XYZ'" in caplog.text

    def test_empty_type_maps_to_string(self):
        """Empty type string should map to StringType."""
        mapper = BQToIcebergTypeMapper()
        result = mapper.map_column("", "NULLABLE")
        assert result == StringType()


class TestNullabilityMapping:
    """Test is_nullable for all BQ modes (Requirement 3.4)."""

    def test_required_is_not_nullable(self):
        """REQUIRED mode maps to non-nullable (False)."""
        mapper = BQToIcebergTypeMapper()
        assert mapper.is_nullable("REQUIRED") is False

    def test_nullable_is_nullable(self):
        """NULLABLE mode maps to nullable (True)."""
        mapper = BQToIcebergTypeMapper()
        assert mapper.is_nullable("NULLABLE") is True

    def test_repeated_is_nullable(self):
        """REPEATED mode maps to nullable (True)."""
        mapper = BQToIcebergTypeMapper()
        assert mapper.is_nullable("REPEATED") is True

    def test_case_insensitive_mode(self):
        """Mode comparison should be case-insensitive."""
        mapper = BQToIcebergTypeMapper()
        assert mapper.is_nullable("required") is False
        assert mapper.is_nullable("Required") is False
        assert mapper.is_nullable("nullable") is True

    def test_whitespace_trimmed(self):
        """Leading/trailing whitespace should be trimmed from mode."""
        mapper = BQToIcebergTypeMapper()
        assert mapper.is_nullable("  REQUIRED  ") is False
        assert mapper.is_nullable("  NULLABLE  ") is True


class TestStructMapping:
    """Test recursive STRUCT/RECORD mapping (Requirement 3.6)."""

    def test_simple_struct(self):
        """STRUCT with flat fields maps to StructType with NestedFields."""
        mapper = BQToIcebergTypeMapper()
        result = mapper.map_column(
            "STRUCT",
            "NULLABLE",
            fields=[
                {"name": "street", "type": "STRING", "mode": "NULLABLE"},
                {"name": "zip", "type": "INT64", "mode": "REQUIRED"},
            ],
        )
        assert isinstance(result, StructType)
        assert len(result.fields) == 2
        assert result.fields[0].name == "street"
        assert result.fields[0].field_type == StringType()
        assert result.fields[0].required is False
        assert result.fields[1].name == "zip"
        assert result.fields[1].field_type == LongType()
        assert result.fields[1].required is True

    def test_record_alias(self):
        """RECORD is treated the same as STRUCT."""
        mapper = BQToIcebergTypeMapper()
        result = mapper.map_column(
            "RECORD",
            "NULLABLE",
            fields=[{"name": "x", "type": "STRING", "mode": "NULLABLE"}],
        )
        assert isinstance(result, StructType)
        assert len(result.fields) == 1

    def test_nested_struct(self):
        """Nested STRUCT within STRUCT maps correctly."""
        mapper = BQToIcebergTypeMapper()
        result = mapper.map_column(
            "STRUCT",
            "NULLABLE",
            fields=[
                {
                    "name": "inner",
                    "type": "STRUCT",
                    "mode": "NULLABLE",
                    "fields": [
                        {"name": "value", "type": "FLOAT64", "mode": "NULLABLE"},
                    ],
                }
            ],
        )
        assert isinstance(result, StructType)
        inner = result.fields[0].field_type
        assert isinstance(inner, StructType)
        assert inner.fields[0].name == "value"
        assert inner.fields[0].field_type == DoubleType()

    def test_struct_with_no_fields(self, caplog):
        """STRUCT with no fields maps to empty StructType with warning."""
        mapper = BQToIcebergTypeMapper()
        with caplog.at_level(logging.WARNING):
            result = mapper.map_column("STRUCT", "NULLABLE", fields=None)
        assert isinstance(result, StructType)
        assert len(result.fields) == 0
        assert "no nested fields" in caplog.text


class TestArrayMapping:
    """Test REPEATED mode (ARRAY) mapping."""

    def test_repeated_string_creates_list(self):
        """REPEATED STRING maps to ListType with StringType element."""
        mapper = BQToIcebergTypeMapper()
        result = mapper.map_column("STRING", "REPEATED")
        assert isinstance(result, ListType)
        assert result.element_type == StringType()

    def test_repeated_struct_creates_list_of_struct(self):
        """REPEATED STRUCT maps to ListType with StructType element."""
        mapper = BQToIcebergTypeMapper()
        result = mapper.map_column(
            "STRUCT",
            "REPEATED",
            fields=[{"name": "x", "type": "INT64", "mode": "NULLABLE"}],
        )
        assert isinstance(result, ListType)
        assert isinstance(result.element_type, StructType)
        assert result.element_type.fields[0].field_type == LongType()

    def test_repeated_int_creates_list(self):
        """REPEATED INT64 maps to ListType with LongType element."""
        mapper = BQToIcebergTypeMapper()
        result = mapper.map_column("INT64", "REPEATED")
        assert isinstance(result, ListType)
        assert result.element_type == LongType()


class TestDepthLimit:
    """Test MAX_STRUCT_DEPTH flattening (Requirement 3.7)."""

    def _build_nested_struct(self, depth: int) -> dict:
        """Build a nested STRUCT payload to a given depth."""
        if depth == 0:
            return {"name": "leaf", "type": "STRING", "mode": "NULLABLE"}
        return {
            "name": f"level_{depth}",
            "type": "STRUCT",
            "mode": "NULLABLE",
            "fields": [self._build_nested_struct(depth - 1)],
        }

    def test_depth_at_limit_maps_correctly(self):
        """STRUCT at exactly MAX_STRUCT_DEPTH (15) should still map as struct."""
        mapper = BQToIcebergTypeMapper()
        # Build a struct that is 15 levels deep (depth 0 to 14)
        nested = self._build_nested_struct(14)
        result = mapper.map_column(
            nested["type"], nested["mode"], fields=nested.get("fields"), depth=0
        )
        # Should be a valid StructType (not flattened)
        assert isinstance(result, StructType)

    def test_depth_exceeds_limit_flattens_to_string(self, caplog):
        """STRUCT exceeding MAX_STRUCT_DEPTH should flatten to StringType."""
        mapper = BQToIcebergTypeMapper()
        # Call map_column at depth=15 (exceeds limit)
        with caplog.at_level(logging.WARNING):
            result = mapper.map_column(
                "STRUCT",
                "NULLABLE",
                fields=[{"name": "x", "type": "STRING", "mode": "NULLABLE"}],
                depth=15,
            )
        assert result == StringType()
        assert "exceeds maximum of 15" in caplog.text

    def test_depth_well_beyond_limit(self, caplog):
        """STRUCT at depth 20 should flatten to StringType."""
        mapper = BQToIcebergTypeMapper()
        with caplog.at_level(logging.WARNING):
            result = mapper.map_column(
                "STRUCT",
                "NULLABLE",
                fields=[{"name": "x", "type": "STRING", "mode": "NULLABLE"}],
                depth=20,
            )
        assert result == StringType()


class TestMapSchema:
    """Test full schema mapping via map_schema()."""

    def test_simple_schema(self):
        """Simple schema with primitive types maps correctly."""
        mapper = BQToIcebergTypeMapper()
        schema = mapper.map_schema(SIMPLE_SCHEMA_PAYLOAD)
        assert isinstance(schema, Schema)
        assert len(schema.fields) == 3

        # Check field types
        assert schema.fields[0].name == "id"
        assert schema.fields[0].field_type == LongType()
        assert schema.fields[0].required is True

        assert schema.fields[1].name == "name"
        assert schema.fields[1].field_type == StringType()
        assert schema.fields[1].required is False

        assert schema.fields[2].name == "created_at"
        assert schema.fields[2].field_type == TimestamptzType()
        assert schema.fields[2].required is False

    def test_schema_with_struct(self):
        """Schema with STRUCT column maps to StructType."""
        mapper = BQToIcebergTypeMapper()
        schema = mapper.map_schema(NESTED_STRUCT_PAYLOAD)
        assert len(schema.fields) == 1
        assert schema.fields[0].name == "address"
        assert isinstance(schema.fields[0].field_type, StructType)
        assert len(schema.fields[0].field_type.fields) == 3

    def test_schema_with_repeated_field(self):
        """Schema with REPEATED field maps to ListType."""
        mapper = BQToIcebergTypeMapper()
        schema = mapper.map_schema(REPEATED_FIELD_PAYLOAD)
        assert len(schema.fields) == 1
        assert schema.fields[0].name == "tags"
        assert isinstance(schema.fields[0].field_type, ListType)
        assert schema.fields[0].field_type.element_type == StringType()

    def test_empty_schema(self):
        """Empty column list produces empty Schema."""
        mapper = BQToIcebergTypeMapper()
        schema = mapper.map_schema([])
        assert isinstance(schema, Schema)
        assert len(schema.fields) == 0

    def test_schema_field_ids_are_unique(self):
        """All field IDs in a schema should be unique."""
        mapper = BQToIcebergTypeMapper()
        schema = mapper.map_schema(SIMPLE_SCHEMA_PAYLOAD)
        field_ids = [f.field_id for f in schema.fields]
        assert len(field_ids) == len(set(field_ids))

    def test_schema_field_ids_reset_between_calls(self):
        """Field IDs should reset between separate map_schema calls."""
        mapper = BQToIcebergTypeMapper()
        schema1 = mapper.map_schema(SIMPLE_SCHEMA_PAYLOAD)
        schema2 = mapper.map_schema(SIMPLE_SCHEMA_PAYLOAD)
        # Both schemas should have the same field IDs
        ids1 = [f.field_id for f in schema1.fields]
        ids2 = [f.field_id for f in schema2.fields]
        assert ids1 == ids2

    def test_complex_schema(self):
        """Complex schema with mixed types maps correctly."""
        payload = [
            {"name": "id", "type": "INT64", "mode": "REQUIRED"},
            {"name": "data", "type": "JSON", "mode": "NULLABLE"},
            {"name": "location", "type": "GEOGRAPHY", "mode": "NULLABLE"},
            {
                "name": "metadata",
                "type": "STRUCT",
                "mode": "NULLABLE",
                "fields": [
                    {"name": "version", "type": "INT64", "mode": "REQUIRED"},
                    {"name": "labels", "type": "STRING", "mode": "REPEATED"},
                ],
            },
            {"name": "scores", "type": "FLOAT64", "mode": "REPEATED"},
        ]
        mapper = BQToIcebergTypeMapper()
        schema = mapper.map_schema(payload)
        assert len(schema.fields) == 5
        assert schema.fields[0].field_type == LongType()
        assert schema.fields[1].field_type == StringType()  # JSON → String
        assert schema.fields[2].field_type == StringType()  # GEOGRAPHY → String
        assert isinstance(schema.fields[3].field_type, StructType)
        assert isinstance(schema.fields[4].field_type, ListType)
