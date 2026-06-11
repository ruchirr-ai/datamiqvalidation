"""
Iceberg Validation Service

Validates migrated data correctness for both full and incremental loads
by comparing source and target row counts.

Full load validation requires an exact match (source == target).
Incremental load validation verifies that the row count delta between
snapshots is at least the batch export count.

Requirements: 10.1, 10.2
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a row count validation check.

    Attributes:
        passed: Whether the validation passed.
        source: Source row count (for full load) or expected delta (for incremental).
        target: Target row count (for full load) or actual delta (for incremental).
        delta: The difference between target and source (full load) or
               the actual row count change (incremental load).
        validation_type: Either 'full' or 'incremental'.
        message: Optional human-readable description of the result.
    """

    passed: bool
    source: int
    target: int
    delta: int
    validation_type: str = "full"
    message: Optional[str] = None


class IcebergValidationService:
    """Validates migrated data correctness for both full and incremental loads.

    For full loads, an exact row count match is required between source and target.
    For incremental loads, the delta between the previous and current Iceberg
    snapshot row counts must be at least the number of rows exported in the batch.

    Usage:
        service = IcebergValidationService()

        # Full load validation
        result = service.validate_full_load(source_count=1000, target_count=1000)
        assert result.passed is True

        # Incremental load validation
        result = service.validate_incremental_load(
            previous_snapshot_count=5000,
            current_snapshot_count=5500,
            batch_export_count=500,
        )
        assert result.passed is True
    """

    def validate_full_load(
        self,
        source_count: int,
        target_count: int,
    ) -> ValidationResult:
        """Validate a full load migration by comparing row counts.

        Full load requires an exact match: source row count must equal
        target row count (difference must be 0).

        Args:
            source_count: The row count from the BigQuery source table
                          (from assessment data).
            target_count: The row count from the Iceberg target table
                          (from snapshot metadata).

        Returns:
            A ValidationResult indicating whether the counts match exactly.
        """
        delta = target_count - source_count
        passed = source_count == target_count

        if passed:
            logger.info(
                "Full load validation PASSED: source=%d, target=%d (exact match)",
                source_count,
                target_count,
            )
            message = f"Row counts match exactly: {source_count} rows"
        else:
            logger.warning(
                "Full load validation FAILED: source=%d, target=%d, delta=%d",
                source_count,
                target_count,
                delta,
            )
            message = (
                f"Row count mismatch: source={source_count}, "
                f"target={target_count}, delta={delta}"
            )

        return ValidationResult(
            passed=passed,
            source=source_count,
            target=target_count,
            delta=delta,
            validation_type="full",
            message=message,
        )

    def validate_incremental_load(
        self,
        previous_snapshot_count: int,
        current_snapshot_count: int,
        batch_export_count: int,
    ) -> ValidationResult:
        """Validate an incremental load by comparing snapshot deltas.

        Incremental validation verifies that the target row count increased
        by at least the number of new rows exported in the current batch.
        The delta between the previous and current Iceberg snapshot row counts
        must be >= batch_export_count.

        Args:
            previous_snapshot_count: Row count from the previous Iceberg snapshot
                                     (before the incremental load).
            current_snapshot_count: Row count from the current Iceberg snapshot
                                    (after the incremental load).
            batch_export_count: Number of rows exported in the current batch.

        Returns:
            A ValidationResult indicating whether the delta meets the threshold.
        """
        delta = current_snapshot_count - previous_snapshot_count
        passed = delta >= batch_export_count

        if passed:
            logger.info(
                "Incremental load validation PASSED: delta=%d >= batch_export_count=%d "
                "(previous=%d, current=%d)",
                delta,
                batch_export_count,
                previous_snapshot_count,
                current_snapshot_count,
            )
            message = (
                f"Incremental delta ({delta}) meets or exceeds "
                f"batch export count ({batch_export_count})"
            )
        else:
            logger.warning(
                "Incremental load validation FAILED: delta=%d < batch_export_count=%d "
                "(previous=%d, current=%d)",
                delta,
                batch_export_count,
                previous_snapshot_count,
                current_snapshot_count,
            )
            message = (
                f"Incremental delta ({delta}) is less than "
                f"batch export count ({batch_export_count})"
            )

        return ValidationResult(
            passed=passed,
            source=batch_export_count,
            target=delta,
            delta=delta,
            validation_type="incremental",
            message=message,
        )
