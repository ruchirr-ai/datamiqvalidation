"""
Unit tests for SchemaEvolutionService.

Tests schema change detection, type promotion validation, and
schema evolution application for incremental loads.
"""

import pytest
from unittest.mock import MagicMock, patch, call

from services.bq_iceberg_migration.schema_evolution import (
    SchemaEvolutionService,
    SchemaChanges,
    ColumnAddition,
    TypePromotion,
    IncompatibleChange,
)
from services.bq_iceberg_migration.iceberg_types import (
    BooleanType,
    DateType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    LongType,
    NestedField,
    Schema,
    StringType,
    TimestampType,
)


# --- Sample payloads ---

SAMPLE_EXISTING_SCHEMA = Schema(
    fields=(
        NestedField(field_id=1, name="id", field_type=LongType(), required=True),
        NestedField(field_id=2, name="name", field_type=StringType(), required=False),
        NestedField(field_id=3, name="score", field_type=IntegerType(), required=False),
        NestedField(field_id=4, name="rating", field_type=FloatType(), required=False),
        NestedField(field_id=5, name="amount", field_type=DecimalType(10, 2), required=False),
        NestedField(field_id=6, name="created_at", field_type=TimestampType(), required=False),
    )
)

SAMPLE_BQ_COLUMNS_NO_CHANGES = [
    {"name": "id", "type": "INT64", "mode": "REQUIRED"},
    {"name": "name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "score", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "rating", "type": "FLOAT", "mode": "NULLABLE"},
    {"name": "amount", "type": "NUMERIC", "mode": "NULLABLE"},
    {"name": "created_at", "type": "DATETIME", "mode": "NULLABLE"},
]

SAMPLE_BQ_COLUMNS_WITH_NEW_COLUMN = [
    {"name": "id", "type": "INT64", "mode": "REQUIRED"},
    {"name": "name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "score", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "rating", "type": "FLOAT", "mode": "NULLABLE"},
    {"name": "amount", "type": "NUMERIC", "mode": "NULLABLE"},
    {"name": "created_at", "type": "DATETIME", "mode": "NULLABLE"},
    {"name": "email", "type": "STRING", "mode": "REQUIRED"},
]

SAMPLE_BQ_COLUMNS_WITH_PROMOTION = [
    {"name": "id", "type": "INT64", "mode": "REQUIRED"},
    {"name": "name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "score", "type": "INT64", "mode": "NULLABLE"},  # int → long
    {"name": "rating", "type": "FLOAT64", "mode": "NULLABLE"},  # float → double
    {"name": "amount", "type": "NUMERIC", "mode": "NULLABLE"},
    {"name": "created_at", "type": "DATETIME", "mode": "NULLABLE"},
]

SAMPLE_BQ_COLUMNS_INCOMPATIBLE = [
    {"name": "id", "type": "INT64", "mode": "REQUIRED"},
    {"name": "name", "type": "INTEGER", "mode": "NULLABLE"},  # string → int (incompatible)
    {"name": "score", "type": "INTEGER", "mode": "NULLABLE"},
    {"name": "rating", "type": "FLOAT", "mode": "NULLABLE"},
    {"name": "amount", "type": "NUMERIC", "mode": "NULLABLE"},
    {"name": "created_at", "type": "DATETIME", "mode": "NULLABLE"},
]


class TestIsCompatiblePromotion:
    """Test is_compatible_promotion validates type promotion rules."""

    def test_int_to_long_is_valid(self):
        """IntegerType → LongType is a valid promotion."""
        service = SchemaEvolutionService()
        assert service.is_compatible_promotion(IntegerType(), LongType()) is True

    def test_float_to_double_is_valid(self):
        """FloatType → DoubleType is a valid promotion."""
        service = SchemaEvolutionService()
        assert service.is_compatible_promotion(FloatType(), DoubleType()) is True

    def test_decimal_precision_widening_same_scale_is_valid(self):
        """DecimalType(10,2) → DecimalType(20,2) is valid (P' > P, same S)."""
        service = SchemaEvolutionService()
        old = DecimalType(10, 2)
        new = DecimalType(20, 2)
        assert service.is_compatible_promotion(old, new) is True

    def test_decimal_precision_widening_different_scale_is_invalid(self):
        """DecimalType(10,2) → DecimalType(20,5) is invalid (different scale)."""
        service = SchemaEvolutionService()
        old = DecimalType(10, 2)
        new = DecimalType(20, 5)
        assert service.is_compatible_promotion(old, new) is False

    def test_decimal_precision_narrowing_is_invalid(self):
        """DecimalType(20,2) → DecimalType(10,2) is invalid (P' < P)."""
        service = SchemaEvolutionService()
        old = DecimalType(20, 2)
        new = DecimalType(10, 2)
        assert service.is_compatible_promotion(old, new) is False

    def test_decimal_same_precision_same_scale_is_invalid(self):
        """DecimalType(10,2) → DecimalType(10,2) is not a promotion (same type)."""
        service = SchemaEvolutionService()
        old = DecimalType(10, 2)
        new = DecimalType(10, 2)
        assert service.is_compatible_promotion(old, new) is False

    def test_long_to_int_is_invalid(self):
        """LongType → IntegerType is not a valid promotion (narrowing)."""
        service = SchemaEvolutionService()
        assert service.is_compatible_promotion(LongType(), IntegerType()) is False

    def test_double_to_float_is_invalid(self):
        """DoubleType → FloatType is not a valid promotion (narrowing)."""
        service = SchemaEvolutionService()
        assert service.is_compatible_promotion(DoubleType(), FloatType()) is False

    def test_string_to_long_is_invalid(self):
        """StringType → LongType is not a valid promotion."""
        service = SchemaEvolutionService()
        assert service.is_compatible_promotion(StringType(), LongType()) is False

    def test_long_to_decimal_is_invalid(self):
        """LongType → DecimalType is not a valid promotion."""
        service = SchemaEvolutionService()
        assert service.is_compatible_promotion(LongType(), DecimalType(38, 9)) is False

    def test_int_to_double_is_invalid(self):
        """IntegerType → DoubleType is not a valid promotion (skip level)."""
        service = SchemaEvolutionService()
        assert service.is_compatible_promotion(IntegerType(), DoubleType()) is False

    def test_boolean_to_string_is_invalid(self):
        """BooleanType → StringType is not a valid promotion."""
        service = SchemaEvolutionService()
        assert service.is_compatible_promotion(BooleanType(), StringType()) is False

    def test_same_type_is_not_promotion(self):
        """Same type → same type is not a promotion."""
        service = SchemaEvolutionService()
        assert service.is_compatible_promotion(LongType(), LongType()) is False


class TestDetectChanges:
    """Test detect_changes identifies new columns, promotions, and incompatible changes."""

    def test_no_changes_detected(self):
        """When schemas match, no changes should be detected."""
        service = SchemaEvolutionService()

        # Use columns that match the existing schema exactly
        # Note: existing schema has IntegerType for score and FloatType for rating
        # but BQ INT64 maps to LongType and FLOAT maps to DoubleType
        # So we need to use columns that actually produce matching types
        matching_columns = [
            {"name": "id", "type": "INT64", "mode": "REQUIRED"},
            {"name": "name", "type": "STRING", "mode": "NULLABLE"},
            {"name": "created_at", "type": "DATETIME", "mode": "NULLABLE"},
        ]
        schema = Schema(
            fields=(
                NestedField(field_id=1, name="id", field_type=LongType(), required=True),
                NestedField(field_id=2, name="name", field_type=StringType(), required=False),
                NestedField(field_id=3, name="created_at", field_type=TimestampType(), required=False),
            )
        )

        changes = service.detect_changes(schema, matching_columns)

        assert not changes.has_changes

    def test_detects_new_columns(self):
        """Should detect columns present in source but not in Iceberg."""
        service = SchemaEvolutionService()
        schema = Schema(
            fields=(
                NestedField(field_id=1, name="id", field_type=LongType(), required=True),
            )
        )
        bq_columns = [
            {"name": "id", "type": "INT64", "mode": "REQUIRED"},
            {"name": "email", "type": "STRING", "mode": "NULLABLE"},
        ]

        changes = service.detect_changes(schema, bq_columns)

        assert len(changes.new_columns) == 1
        assert changes.new_columns[0].name == "email"
        assert isinstance(changes.new_columns[0].iceberg_type, StringType)

    def test_detects_type_promotion(self):
        """Should detect valid type promotions (int→long, float→double)."""
        service = SchemaEvolutionService()

        changes = service.detect_changes(SAMPLE_EXISTING_SCHEMA, SAMPLE_BQ_COLUMNS_WITH_PROMOTION)

        assert len(changes.type_promotions) == 2
        promotion_names = {p.name for p in changes.type_promotions}
        assert "score" in promotion_names
        assert "rating" in promotion_names

    def test_detects_incompatible_type_change(self):
        """Should detect incompatible type changes (string→int)."""
        service = SchemaEvolutionService()

        changes = service.detect_changes(SAMPLE_EXISTING_SCHEMA, SAMPLE_BQ_COLUMNS_INCOMPATIBLE)

        assert len(changes.incompatible_changes) >= 1
        incompatible_names = {c.name for c in changes.incompatible_changes}
        assert "name" in incompatible_names

    def test_detects_removed_columns(self):
        """Should detect columns removed from source as incompatible changes."""
        service = SchemaEvolutionService()
        schema = Schema(
            fields=(
                NestedField(field_id=1, name="id", field_type=LongType(), required=True),
                NestedField(field_id=2, name="old_col", field_type=StringType(), required=False),
            )
        )
        bq_columns = [
            {"name": "id", "type": "INT64", "mode": "REQUIRED"},
        ]

        changes = service.detect_changes(schema, bq_columns)

        assert len(changes.incompatible_changes) == 1
        assert changes.incompatible_changes[0].name == "old_col"
        assert "removed" in changes.incompatible_changes[0].reason.lower()

    def test_new_column_preserves_bq_mode(self):
        """New column additions should record the original BQ mode."""
        service = SchemaEvolutionService()
        schema = Schema(fields=())
        bq_columns = [
            {"name": "required_col", "type": "STRING", "mode": "REQUIRED"},
        ]

        changes = service.detect_changes(schema, bq_columns)

        assert len(changes.new_columns) == 1
        assert changes.new_columns[0].bq_mode == "REQUIRED"

    def test_has_incompatible_changes_property(self):
        """has_incompatible_changes should be True when incompatible changes exist."""
        service = SchemaEvolutionService()

        changes = service.detect_changes(SAMPLE_EXISTING_SCHEMA, SAMPLE_BQ_COLUMNS_INCOMPATIBLE)

        assert changes.has_incompatible_changes is True

    def test_has_changes_property_false_when_no_changes(self):
        """has_changes should be False when schemas match."""
        service = SchemaEvolutionService()
        schema = Schema(
            fields=(
                NestedField(field_id=1, name="id", field_type=LongType(), required=True),
            )
        )
        bq_columns = [{"name": "id", "type": "INT64", "mode": "REQUIRED"}]

        changes = service.detect_changes(schema, bq_columns)

        assert changes.has_changes is False


class TestApplyEvolution:
    """Test apply_evolution applies compatible changes to the Iceberg table."""

    def test_adds_new_columns_as_optional(self):
        """New columns should always be added as optional (nullable)."""
        service = SchemaEvolutionService()
        table = MagicMock()
        table.name = "test_table"
        update_schema_ctx = MagicMock()
        table.update_schema = MagicMock(return_value=update_schema_ctx)
        update_schema_ctx.__enter__ = MagicMock(return_value=update_schema_ctx)
        update_schema_ctx.__exit__ = MagicMock(return_value=False)

        changes = SchemaChanges(
            new_columns=[
                ColumnAddition(name="email", iceberg_type=StringType(), bq_mode="REQUIRED"),
                ColumnAddition(name="age", iceberg_type=LongType(), bq_mode="NULLABLE"),
            ]
        )

        service.apply_evolution(table, changes)

        # Both columns should be added as required=False regardless of BQ mode
        assert update_schema_ctx.add_column.call_count == 2
        for call_args in update_schema_ctx.add_column.call_args_list:
            assert call_args[1]["required"] is False

    def test_applies_type_promotions(self):
        """Type promotions should be applied via update_column."""
        service = SchemaEvolutionService()
        table = MagicMock()
        table.name = "test_table"
        update_schema_ctx = MagicMock()
        table.update_schema = MagicMock(return_value=update_schema_ctx)
        update_schema_ctx.__enter__ = MagicMock(return_value=update_schema_ctx)
        update_schema_ctx.__exit__ = MagicMock(return_value=False)

        changes = SchemaChanges(
            type_promotions=[
                TypePromotion(name="score", old_type=IntegerType(), new_type=LongType()),
            ]
        )

        service.apply_evolution(table, changes)

        update_schema_ctx.update_column.assert_called_once_with(
            path="score",
            field_type=LongType(),
        )

    def test_no_op_when_no_changes(self):
        """Should not call update_schema when there are no changes."""
        service = SchemaEvolutionService()
        table = MagicMock()
        table.name = "test_table"

        changes = SchemaChanges()

        service.apply_evolution(table, changes)

        table.update_schema.assert_not_called()

    def test_raises_on_table_api_failure(self):
        """Should raise RuntimeError when the table API fails."""
        service = SchemaEvolutionService()
        table = MagicMock()
        table.name = "test_table"
        update_schema_ctx = MagicMock()
        table.update_schema = MagicMock(return_value=update_schema_ctx)
        update_schema_ctx.__enter__ = MagicMock(return_value=update_schema_ctx)
        update_schema_ctx.__exit__ = MagicMock(side_effect=Exception("API error"))

        changes = SchemaChanges(
            new_columns=[
                ColumnAddition(name="email", iceberg_type=StringType(), bq_mode="NULLABLE"),
            ]
        )

        with pytest.raises(RuntimeError, match="Schema evolution failed"):
            service.apply_evolution(table, changes)

    def test_required_bq_column_added_as_optional(self):
        """A REQUIRED BQ column should still be added as optional in Iceberg."""
        service = SchemaEvolutionService()
        table = MagicMock()
        table.name = "test_table"
        update_schema_ctx = MagicMock()
        table.update_schema = MagicMock(return_value=update_schema_ctx)
        update_schema_ctx.__enter__ = MagicMock(return_value=update_schema_ctx)
        update_schema_ctx.__exit__ = MagicMock(return_value=False)

        changes = SchemaChanges(
            new_columns=[
                ColumnAddition(name="required_field", iceberg_type=LongType(), bq_mode="REQUIRED"),
            ]
        )

        service.apply_evolution(table, changes)

        update_schema_ctx.add_column.assert_called_once_with(
            path="required_field",
            field_type=LongType(),
            required=False,
        )
