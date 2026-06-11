"""
Unit tests for PartitionSpecMapper service.

Tests cover:
- Partition spec mapping with day() default for time-based columns
- Explicit granularity overrides (HOUR, MONTH, YEAR)
- Sort order preservation of BQ clustering column sequence
- Edge cases: empty inputs, non-time-based types, unrecognized granularity
"""

import pytest

from services.bq_iceberg_migration.partition_mapper import (
    PartitionField,
    PartitionSpec,
    PartitionSpecMapper,
    SortField,
    SortOrder,
)


class TestPartitionSpecMapper:
    """Tests for PartitionSpecMapper.map_partition_spec()."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mapper = PartitionSpecMapper()

    # --- Default day() transform tests ---

    def test_date_column_defaults_to_day(self):
        """DATE column with no granularity uses day() transform."""
        result = self.mapper.map_partition_spec("event_date", "DATE")

        assert len(result.fields) == 1
        assert result.fields[0].source_column == "event_date"
        assert result.fields[0].transform == "day"

    def test_datetime_column_defaults_to_day(self):
        """DATETIME column with no granularity uses day() transform."""
        result = self.mapper.map_partition_spec("created_at", "DATETIME")

        assert len(result.fields) == 1
        assert result.fields[0].source_column == "created_at"
        assert result.fields[0].transform == "day"

    def test_timestamp_column_defaults_to_day(self):
        """TIMESTAMP column with no granularity uses day() transform."""
        result = self.mapper.map_partition_spec("updated_at", "TIMESTAMP")

        assert len(result.fields) == 1
        assert result.fields[0].source_column == "updated_at"
        assert result.fields[0].transform == "day"

    def test_date_column_with_none_granularity(self):
        """DATE column with explicit None granularity uses day() default."""
        result = self.mapper.map_partition_spec("event_date", "DATE", None)

        assert result.fields[0].transform == "day"

    # --- Explicit granularity override tests ---

    def test_hour_granularity(self):
        """Explicit HOUR granularity produces hour() transform."""
        result = self.mapper.map_partition_spec("event_time", "TIMESTAMP", "HOUR")

        assert result.fields[0].transform == "hour"

    def test_month_granularity(self):
        """Explicit MONTH granularity produces month() transform."""
        result = self.mapper.map_partition_spec("created_at", "DATETIME", "MONTH")

        assert result.fields[0].transform == "month"

    def test_year_granularity(self):
        """Explicit YEAR granularity produces year() transform."""
        result = self.mapper.map_partition_spec("created_at", "DATETIME", "YEAR")

        assert result.fields[0].transform == "year"

    def test_day_granularity_explicit(self):
        """Explicit DAY granularity produces day() transform (same as default)."""
        result = self.mapper.map_partition_spec("event_date", "DATE", "DAY")

        assert result.fields[0].transform == "day"

    def test_unrecognized_granularity_raises_error(self):
        """Unrecognized granularity string raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported partition configuration"):
            self.mapper.map_partition_spec("event_date", "DATE", "WEEKLY")

    # --- Case insensitivity tests ---

    def test_lowercase_column_type(self):
        """Column type comparison is case-insensitive."""
        result = self.mapper.map_partition_spec("event_date", "date")

        assert result.fields[0].transform == "day"

    def test_lowercase_granularity(self):
        """Granularity comparison is case-insensitive."""
        result = self.mapper.map_partition_spec("event_time", "TIMESTAMP", "hour")

        assert result.fields[0].transform == "hour"

    def test_mixed_case_column_type(self):
        """Mixed case column type is handled correctly."""
        result = self.mapper.map_partition_spec("ts", "Timestamp")

        assert result.fields[0].transform == "day"

    # --- Non-time-based column tests ---

    def test_string_column_uses_identity(self):
        """Non-time-based STRING column uses identity transform."""
        result = self.mapper.map_partition_spec("country", "STRING")

        assert result.fields[0].source_column == "country"
        assert result.fields[0].transform == "identity"

    def test_integer_column_uses_identity(self):
        """Non-time-based INT64 column uses identity transform."""
        result = self.mapper.map_partition_spec("user_id", "INT64")

        assert result.fields[0].transform == "identity"

    # --- Error handling tests ---

    def test_empty_partition_column_raises_error(self):
        """Empty partition column name raises ValueError."""
        with pytest.raises(ValueError, match="partition_column must not be empty"):
            self.mapper.map_partition_spec("", "DATE")

    # --- Serialization tests ---

    def test_partition_spec_to_dict(self):
        """PartitionSpec serializes to dict correctly."""
        result = self.mapper.map_partition_spec("created_at", "DATETIME", "MONTH")
        d = result.to_dict()

        assert d == {
            "fields": [{"source_column": "created_at", "transform": "month"}]
        }

    def test_partition_spec_round_trip(self):
        """PartitionSpec serializes and deserializes correctly."""
        original = self.mapper.map_partition_spec("event_date", "TIMESTAMP", "HOUR")
        serialized = original.to_dict()
        restored = PartitionSpec.from_dict(serialized)

        assert len(restored.fields) == len(original.fields)
        assert restored.fields[0].source_column == original.fields[0].source_column
        assert restored.fields[0].transform == original.fields[0].transform


class TestSortOrderMapper:
    """Tests for PartitionSpecMapper.map_sort_order()."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mapper = PartitionSpecMapper()

    def test_single_clustering_column(self):
        """Single clustering column produces single sort field."""
        result = self.mapper.map_sort_order(["user_id"])

        assert len(result.fields) == 1
        assert result.fields[0].source_column == "user_id"
        assert result.fields[0].direction == "asc"
        assert result.fields[0].null_order == "nulls_last"

    def test_multiple_clustering_columns_preserve_order(self):
        """Multiple clustering columns preserve ordinal sequence."""
        columns = ["user_id", "event_date", "event_type"]
        result = self.mapper.map_sort_order(columns)

        assert len(result.fields) == 3
        assert result.fields[0].source_column == "user_id"
        assert result.fields[1].source_column == "event_date"
        assert result.fields[2].source_column == "event_type"

    def test_empty_clustering_columns(self):
        """Empty clustering columns list produces empty sort order."""
        result = self.mapper.map_sort_order([])

        assert len(result.fields) == 0

    def test_all_fields_ascending(self):
        """All sort fields default to ascending direction."""
        columns = ["col_a", "col_b", "col_c"]
        result = self.mapper.map_sort_order(columns)

        for f in result.fields:
            assert f.direction == "asc"

    def test_all_fields_nulls_last(self):
        """All sort fields default to nulls_last ordering."""
        columns = ["col_a", "col_b"]
        result = self.mapper.map_sort_order(columns)

        for f in result.fields:
            assert f.null_order == "nulls_last"

    def test_skips_empty_string_columns(self):
        """Empty string entries in clustering columns are skipped."""
        columns = ["user_id", "", "event_date"]
        result = self.mapper.map_sort_order(columns)

        assert len(result.fields) == 2
        assert result.fields[0].source_column == "user_id"
        assert result.fields[1].source_column == "event_date"

    def test_sort_order_to_dict(self):
        """SortOrder serializes to dict correctly."""
        result = self.mapper.map_sort_order(["user_id", "event_date"])
        d = result.to_dict()

        assert d == {
            "fields": [
                {
                    "source_column": "user_id",
                    "direction": "asc",
                    "null_order": "nulls_last",
                },
                {
                    "source_column": "event_date",
                    "direction": "asc",
                    "null_order": "nulls_last",
                },
            ]
        }

    def test_sort_order_round_trip(self):
        """SortOrder serializes and deserializes correctly."""
        original = self.mapper.map_sort_order(["a", "b", "c"])
        serialized = original.to_dict()
        restored = SortOrder.from_dict(serialized)

        assert len(restored.fields) == len(original.fields)
        for orig, rest in zip(original.fields, restored.fields):
            assert orig.source_column == rest.source_column
            assert orig.direction == rest.direction
            assert orig.null_order == rest.null_order

    def test_large_clustering_column_list(self):
        """Handles large number of clustering columns (BQ supports up to 4)."""
        columns = [f"col_{i}" for i in range(4)]
        result = self.mapper.map_sort_order(columns)

        assert len(result.fields) == 4
        for i, f in enumerate(result.fields):
            assert f.source_column == f"col_{i}"


class TestPartitionFieldDataclass:
    """Tests for PartitionField dataclass."""

    def test_creation(self):
        """PartitionField can be created with required fields."""
        field = PartitionField(source_column="event_date", transform="day")

        assert field.source_column == "event_date"
        assert field.transform == "day"

    def test_equality(self):
        """Two PartitionFields with same values are equal."""
        f1 = PartitionField(source_column="col", transform="day")
        f2 = PartitionField(source_column="col", transform="day")

        assert f1 == f2


class TestSortFieldDataclass:
    """Tests for SortField dataclass."""

    def test_defaults(self):
        """SortField has correct default values."""
        field = SortField(source_column="col")

        assert field.direction == "asc"
        assert field.null_order == "nulls_last"

    def test_custom_values(self):
        """SortField accepts custom direction and null_order."""
        field = SortField(source_column="col", direction="desc", null_order="nulls_first")

        assert field.direction == "desc"
        assert field.null_order == "nulls_first"


class TestTransformMap:
    """Tests for the TRANSFORM_MAP constant."""

    def test_all_time_types_have_default_mapping(self):
        """All time-based types have a (type, None) default mapping."""
        mapper = PartitionSpecMapper()

        assert ("DATE", None) in mapper.TRANSFORM_MAP
        assert ("DATETIME", None) in mapper.TRANSFORM_MAP
        assert ("TIMESTAMP", None) in mapper.TRANSFORM_MAP

    def test_all_defaults_are_day(self):
        """All default (None granularity) mappings produce 'day' transform."""
        mapper = PartitionSpecMapper()

        assert mapper.TRANSFORM_MAP[("DATE", None)] == "day"
        assert mapper.TRANSFORM_MAP[("DATETIME", None)] == "day"
        assert mapper.TRANSFORM_MAP[("TIMESTAMP", None)] == "day"

    def test_datetime_supports_all_granularities(self):
        """DATETIME type supports DAY, HOUR, MONTH, YEAR granularities."""
        mapper = PartitionSpecMapper()

        assert ("DATETIME", "DAY") in mapper.TRANSFORM_MAP
        assert ("DATETIME", "HOUR") in mapper.TRANSFORM_MAP
        assert ("DATETIME", "MONTH") in mapper.TRANSFORM_MAP
        assert ("DATETIME", "YEAR") in mapper.TRANSFORM_MAP

    def test_timestamp_supports_all_granularities(self):
        """TIMESTAMP type supports DAY, HOUR, MONTH, YEAR granularities."""
        mapper = PartitionSpecMapper()

        assert ("TIMESTAMP", "DAY") in mapper.TRANSFORM_MAP
        assert ("TIMESTAMP", "HOUR") in mapper.TRANSFORM_MAP
        assert ("TIMESTAMP", "MONTH") in mapper.TRANSFORM_MAP
        assert ("TIMESTAMP", "YEAR") in mapper.TRANSFORM_MAP

    def test_date_only_supports_day(self):
        """DATE type only supports None and DAY granularity."""
        mapper = PartitionSpecMapper()

        assert ("DATE", None) in mapper.TRANSFORM_MAP
        assert ("DATE", "DAY") in mapper.TRANSFORM_MAP
        assert ("DATE", "HOUR") not in mapper.TRANSFORM_MAP
        assert ("DATE", "MONTH") not in mapper.TRANSFORM_MAP
        assert ("DATE", "YEAR") not in mapper.TRANSFORM_MAP

    def test_no_identity_transforms_in_map(self):
        """TRANSFORM_MAP never contains identity transforms."""
        mapper = PartitionSpecMapper()

        for key, transform in mapper.TRANSFORM_MAP.items():
            assert transform != "identity", (
                f"TRANSFORM_MAP should never contain identity: {key} -> {transform}"
            )

    def test_unsupported_date_granularity_raises_error(self):
        """DATE with unsupported granularity (HOUR, MONTH, YEAR) raises ValueError."""
        mapper = PartitionSpecMapper()

        with pytest.raises(ValueError, match="Unsupported partition configuration"):
            mapper.map_partition_spec("event_date", "DATE", "HOUR")

        with pytest.raises(ValueError, match="Unsupported partition configuration"):
            mapper.map_partition_spec("event_date", "DATE", "MONTH")

        with pytest.raises(ValueError, match="Unsupported partition configuration"):
            mapper.map_partition_spec("event_date", "DATE", "YEAR")
