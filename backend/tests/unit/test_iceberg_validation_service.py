"""
Unit tests for IcebergValidationService.

Tests full load validation (exact match) and incremental load validation
(delta >= batch_export_count).
"""

import pytest

from services.bq_iceberg_migration.validation_service import (
    IcebergValidationService,
    ValidationResult,
)


# --- Sample payloads ---

SAMPLE_FULL_LOAD_MATCH = {"source_count": 10000, "target_count": 10000}
SAMPLE_FULL_LOAD_MISMATCH = {"source_count": 10000, "target_count": 9500}
SAMPLE_FULL_LOAD_EXTRA_ROWS = {"source_count": 10000, "target_count": 10500}

SAMPLE_INCREMENTAL_PASS = {
    "previous_snapshot_count": 5000,
    "current_snapshot_count": 5500,
    "batch_export_count": 500,
}
SAMPLE_INCREMENTAL_FAIL = {
    "previous_snapshot_count": 5000,
    "current_snapshot_count": 5200,
    "batch_export_count": 500,
}
SAMPLE_INCREMENTAL_EXACT = {
    "previous_snapshot_count": 5000,
    "current_snapshot_count": 5500,
    "batch_export_count": 500,
}
SAMPLE_INCREMENTAL_EXCEEDS = {
    "previous_snapshot_count": 5000,
    "current_snapshot_count": 6000,
    "batch_export_count": 500,
}


class TestValidateFullLoad:
    """Test validate_full_load requires exact row count match."""

    def test_passes_when_counts_match(self):
        """Full load passes when source == target."""
        service = IcebergValidationService()

        result = service.validate_full_load(
            source_count=SAMPLE_FULL_LOAD_MATCH["source_count"],
            target_count=SAMPLE_FULL_LOAD_MATCH["target_count"],
        )

        assert result.passed is True
        assert result.source == 10000
        assert result.target == 10000
        assert result.delta == 0

    def test_fails_when_target_less_than_source(self):
        """Full load fails when target < source (missing rows)."""
        service = IcebergValidationService()

        result = service.validate_full_load(
            source_count=SAMPLE_FULL_LOAD_MISMATCH["source_count"],
            target_count=SAMPLE_FULL_LOAD_MISMATCH["target_count"],
        )

        assert result.passed is False
        assert result.source == 10000
        assert result.target == 9500
        assert result.delta == -500

    def test_fails_when_target_more_than_source(self):
        """Full load fails when target > source (extra rows)."""
        service = IcebergValidationService()

        result = service.validate_full_load(
            source_count=SAMPLE_FULL_LOAD_EXTRA_ROWS["source_count"],
            target_count=SAMPLE_FULL_LOAD_EXTRA_ROWS["target_count"],
        )

        assert result.passed is False
        assert result.source == 10000
        assert result.target == 10500
        assert result.delta == 500

    def test_passes_with_zero_rows(self):
        """Full load passes when both source and target have zero rows."""
        service = IcebergValidationService()

        result = service.validate_full_load(source_count=0, target_count=0)

        assert result.passed is True
        assert result.delta == 0

    def test_returns_validation_result_type(self):
        """Should return a ValidationResult dataclass."""
        service = IcebergValidationService()

        result = service.validate_full_load(source_count=100, target_count=100)

        assert isinstance(result, ValidationResult)

    def test_validation_type_is_full(self):
        """Validation type should be 'full' for full load validation."""
        service = IcebergValidationService()

        result = service.validate_full_load(source_count=100, target_count=100)

        assert result.validation_type == "full"

    def test_message_present_on_pass(self):
        """A human-readable message should be present on pass."""
        service = IcebergValidationService()

        result = service.validate_full_load(source_count=100, target_count=100)

        assert result.message is not None
        assert len(result.message) > 0

    def test_message_present_on_fail(self):
        """A human-readable message should be present on fail."""
        service = IcebergValidationService()

        result = service.validate_full_load(source_count=100, target_count=50)

        assert result.message is not None
        assert len(result.message) > 0


class TestValidateIncrementalLoad:
    """Test validate_incremental_load verifies delta >= batch_export_count."""

    def test_passes_when_delta_equals_batch(self):
        """Incremental passes when delta == batch_export_count."""
        service = IcebergValidationService()

        result = service.validate_incremental_load(
            previous_snapshot_count=SAMPLE_INCREMENTAL_EXACT["previous_snapshot_count"],
            current_snapshot_count=SAMPLE_INCREMENTAL_EXACT["current_snapshot_count"],
            batch_export_count=SAMPLE_INCREMENTAL_EXACT["batch_export_count"],
        )

        assert result.passed is True
        assert result.delta == 500

    def test_passes_when_delta_exceeds_batch(self):
        """Incremental passes when delta > batch_export_count."""
        service = IcebergValidationService()

        result = service.validate_incremental_load(
            previous_snapshot_count=SAMPLE_INCREMENTAL_EXCEEDS["previous_snapshot_count"],
            current_snapshot_count=SAMPLE_INCREMENTAL_EXCEEDS["current_snapshot_count"],
            batch_export_count=SAMPLE_INCREMENTAL_EXCEEDS["batch_export_count"],
        )

        assert result.passed is True
        assert result.delta == 1000

    def test_fails_when_delta_less_than_batch(self):
        """Incremental fails when delta < batch_export_count."""
        service = IcebergValidationService()

        result = service.validate_incremental_load(
            previous_snapshot_count=SAMPLE_INCREMENTAL_FAIL["previous_snapshot_count"],
            current_snapshot_count=SAMPLE_INCREMENTAL_FAIL["current_snapshot_count"],
            batch_export_count=SAMPLE_INCREMENTAL_FAIL["batch_export_count"],
        )

        assert result.passed is False
        assert result.delta == 200

    def test_fails_when_no_rows_added(self):
        """Incremental fails when delta is 0 and batch > 0."""
        service = IcebergValidationService()

        result = service.validate_incremental_load(
            previous_snapshot_count=5000,
            current_snapshot_count=5000,
            batch_export_count=100,
        )

        assert result.passed is False
        assert result.delta == 0

    def test_passes_with_zero_batch(self):
        """Incremental passes when batch_export_count is 0 (no-op batch)."""
        service = IcebergValidationService()

        result = service.validate_incremental_load(
            previous_snapshot_count=5000,
            current_snapshot_count=5000,
            batch_export_count=0,
        )

        assert result.passed is True
        assert result.delta == 0

    def test_validation_type_is_incremental(self):
        """Validation type should be 'incremental' for incremental validation."""
        service = IcebergValidationService()

        result = service.validate_incremental_load(
            previous_snapshot_count=100,
            current_snapshot_count=200,
            batch_export_count=50,
        )

        assert result.validation_type == "incremental"

    def test_source_field_contains_batch_export_count(self):
        """Source field should contain the batch_export_count for incremental."""
        service = IcebergValidationService()

        result = service.validate_incremental_load(
            previous_snapshot_count=100,
            current_snapshot_count=200,
            batch_export_count=50,
        )

        assert result.source == 50

    def test_target_field_contains_delta(self):
        """Target field should contain the actual delta for incremental."""
        service = IcebergValidationService()

        result = service.validate_incremental_load(
            previous_snapshot_count=100,
            current_snapshot_count=200,
            batch_export_count=50,
        )

        assert result.target == 100

    def test_negative_delta_fails(self):
        """Incremental fails when current < previous (negative delta)."""
        service = IcebergValidationService()

        result = service.validate_incremental_load(
            previous_snapshot_count=5000,
            current_snapshot_count=4500,
            batch_export_count=100,
        )

        assert result.passed is False
        assert result.delta == -500
