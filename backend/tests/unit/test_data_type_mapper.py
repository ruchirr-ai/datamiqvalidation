"""
Unit tests for DataTypeMapper service.
Tests all 12 default BigQuery-to-Redshift type mappings, override merging,
case-insensitive comparison, serialization round-trip, and edge cases.
"""

import pytest
from services.data_type_mapper import (
    DataTypeMapper,
    DEFAULT_BQ_TO_REDSHIFT_TYPE_MAP,
)


# --- Sample payloads ---

VALID_OVERRIDES = {"STRING": "TEXT", "CUSTOM_TYPE": "SUPER"}
EMPTY_OVERRIDES: dict[str, str] = {}


class TestDefaultMapping:
    """Test all 12 default BigQuery-to-Redshift type mappings."""

    @pytest.mark.parametrize(
        "bq_type, expected_redshift",
        [
            ("STRING", "VARCHAR"),
            ("INT64", "BIGINT"),
            ("FLOAT64", "DOUBLE PRECISION"),
            ("NUMERIC", "DECIMAL"),
            ("BIGNUMERIC", "DECIMAL"),
            ("BOOL", "BOOLEAN"),
            ("TIMESTAMP", "TIMESTAMP"),
            ("DATE", "DATE"),
            ("TIME", "TIME"),
            ("BYTES", "VARBYTE"),
            ("ARRAY", "SUPER"),
            ("STRUCT", "SUPER"),
        ],
    )
    def test_default_mapping_equivalence(self, bq_type, expected_redshift):
        """Each default BQ type should map to its expected Redshift equivalent."""
        mapper = DataTypeMapper()
        assert mapper.is_equivalent(bq_type, expected_redshift) is True

    @pytest.mark.parametrize(
        "bq_type, expected_redshift",
        [
            ("STRING", "VARCHAR"),
            ("INT64", "BIGINT"),
            ("FLOAT64", "DOUBLE PRECISION"),
            ("NUMERIC", "DECIMAL"),
            ("BIGNUMERIC", "DECIMAL"),
            ("BOOL", "BOOLEAN"),
            ("TIMESTAMP", "TIMESTAMP"),
            ("DATE", "DATE"),
            ("TIME", "TIME"),
            ("BYTES", "VARBYTE"),
            ("ARRAY", "SUPER"),
            ("STRUCT", "SUPER"),
        ],
    )
    def test_get_expected_redshift_type(self, bq_type, expected_redshift):
        """get_expected_redshift_type returns the correct Redshift type."""
        mapper = DataTypeMapper()
        assert mapper.get_expected_redshift_type(bq_type) == expected_redshift

    def test_default_mapping_has_12_entries(self):
        """The default constant should contain exactly 12 type pairs."""
        assert len(DEFAULT_BQ_TO_REDSHIFT_TYPE_MAP) == 12


class TestIsEquivalent:
    """Test is_equivalent behaviour for mapped and non-mapped pairs."""

    def test_returns_false_for_non_mapped_pair(self):
        """Non-mapped BQ type should not be equivalent to any Redshift type."""
        mapper = DataTypeMapper()
        assert mapper.is_equivalent("GEOGRAPHY", "VARCHAR") is False

    def test_returns_false_for_wrong_redshift_type(self):
        """A mapped BQ type paired with the wrong Redshift type should fail."""
        mapper = DataTypeMapper()
        assert mapper.is_equivalent("STRING", "BIGINT") is False

    def test_case_insensitive_bq_type(self):
        """BQ type lookup should be case-insensitive."""
        mapper = DataTypeMapper()
        assert mapper.is_equivalent("string", "VARCHAR") is True
        assert mapper.is_equivalent("String", "VARCHAR") is True
        assert mapper.is_equivalent("int64", "BIGINT") is True

    def test_case_insensitive_redshift_type(self):
        """Redshift type comparison should be case-insensitive."""
        mapper = DataTypeMapper()
        assert mapper.is_equivalent("STRING", "varchar") is True
        assert mapper.is_equivalent("FLOAT64", "double precision") is True

    def test_whitespace_trimmed(self):
        """Leading/trailing whitespace should be trimmed from both types."""
        mapper = DataTypeMapper()
        assert mapper.is_equivalent("  STRING  ", "  VARCHAR  ") is True


class TestGetExpectedRedshiftType:
    """Test get_expected_redshift_type for known and unknown types."""

    def test_returns_none_for_unknown_type(self):
        """Unknown BQ type should return None."""
        mapper = DataTypeMapper()
        assert mapper.get_expected_redshift_type("GEOGRAPHY") is None

    def test_case_insensitive_lookup(self):
        """Lookup should work regardless of case."""
        mapper = DataTypeMapper()
        assert mapper.get_expected_redshift_type("string") == "VARCHAR"
        assert mapper.get_expected_redshift_type("Bool") == "BOOLEAN"


class TestOverrides:
    """Test user-provided type_mapping_overrides merge with defaults."""

    def test_override_replaces_default(self):
        """User override should replace the default mapping for that key."""
        mapper = DataTypeMapper(overrides={"STRING": "TEXT"})
        assert mapper.get_expected_redshift_type("STRING") == "TEXT"
        assert mapper.is_equivalent("STRING", "TEXT") is True
        assert mapper.is_equivalent("STRING", "VARCHAR") is False

    def test_override_adds_new_mapping(self):
        """User override can add a mapping not in the defaults."""
        mapper = DataTypeMapper(overrides={"GEOGRAPHY": "GEOMETRY"})
        assert mapper.get_expected_redshift_type("GEOGRAPHY") == "GEOMETRY"
        assert mapper.is_equivalent("GEOGRAPHY", "GEOMETRY") is True

    def test_override_preserves_other_defaults(self):
        """Overriding one key should not affect other default mappings."""
        mapper = DataTypeMapper(overrides={"STRING": "TEXT"})
        assert mapper.get_expected_redshift_type("INT64") == "BIGINT"
        assert mapper.get_expected_redshift_type("BOOL") == "BOOLEAN"

    def test_empty_overrides_uses_defaults(self):
        """Empty overrides dict should produce the default mapping."""
        mapper = DataTypeMapper(overrides=EMPTY_OVERRIDES)
        assert mapper.to_dict() == DEFAULT_BQ_TO_REDSHIFT_TYPE_MAP

    def test_none_overrides_uses_defaults(self):
        """None overrides should produce the default mapping."""
        mapper = DataTypeMapper(overrides=None)
        assert mapper.to_dict() == DEFAULT_BQ_TO_REDSHIFT_TYPE_MAP


class TestSerialization:
    """Test to_dict and from_dict round-trip serialization."""

    def test_to_dict_returns_copy(self):
        """to_dict should return a copy, not the internal reference."""
        mapper = DataTypeMapper()
        d = mapper.to_dict()
        d["STRING"] = "MODIFIED"
        assert mapper.get_expected_redshift_type("STRING") == "VARCHAR"

    def test_from_dict_reconstructs_mapper(self):
        """from_dict should produce a mapper with the same mapping."""
        mapper = DataTypeMapper(overrides={"STRING": "TEXT"})
        serialized = mapper.to_dict()
        restored = DataTypeMapper.from_dict(serialized)
        assert restored.to_dict() == serialized

    def test_round_trip_default_mapping(self):
        """Default mapper round-trip through to_dict/from_dict is identity."""
        mapper = DataTypeMapper()
        restored = DataTypeMapper.from_dict(mapper.to_dict())
        assert restored.to_dict() == mapper.to_dict()

    def test_round_trip_with_overrides(self):
        """Mapper with overrides round-trips correctly."""
        mapper = DataTypeMapper(overrides=VALID_OVERRIDES)
        restored = DataTypeMapper.from_dict(mapper.to_dict())
        assert restored.to_dict() == mapper.to_dict()

    def test_from_dict_equivalence_check(self):
        """Restored mapper should produce same is_equivalent results."""
        mapper = DataTypeMapper(overrides={"STRING": "TEXT"})
        restored = DataTypeMapper.from_dict(mapper.to_dict())
        assert restored.is_equivalent("STRING", "TEXT") is True
        assert restored.is_equivalent("INT64", "BIGINT") is True
