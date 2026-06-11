"""
Schema Evolution Service for BigQuery to Iceberg Migrations

Manages Iceberg schema evolution for incremental loads. Detects new columns,
validates type promotions, and applies compatible schema changes to existing
Iceberg tables.

Only valid type promotions are supported:
- int → long
- float → double
- decimal(P, S) → decimal(P', S) where P' > P and scale remains the same

All new columns are added as optional (nullable) regardless of their BigQuery
mode, to maintain backward compatibility with existing data files.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

from .iceberg_types import (
    DecimalType,
    DoubleType,
    FloatType,
    IcebergType,
    IntegerType,
    LongType,
    NestedField,
    Schema,
)
from .type_mapper import BQToIcebergTypeMapper

logger = logging.getLogger(__name__)


@dataclass
class ColumnAddition:
    """Represents a new column to be added to the Iceberg table.

    Attributes:
        name: Column name.
        iceberg_type: The mapped Iceberg type for the new column.
        bq_mode: Original BigQuery mode (REQUIRED, NULLABLE, REPEATED).
    """

    name: str
    iceberg_type: IcebergType
    bq_mode: str


@dataclass
class TypePromotion:
    """Represents a compatible type promotion for an existing column.

    Attributes:
        name: Column name.
        old_type: The current Iceberg type.
        new_type: The promoted Iceberg type.
    """

    name: str
    old_type: IcebergType
    new_type: IcebergType


@dataclass
class IncompatibleChange:
    """Represents an incompatible schema change that cannot be applied.

    Attributes:
        name: Column name.
        reason: Description of why the change is incompatible.
        old_type: The current Iceberg type (if applicable).
        new_type: The new type that was detected (if applicable).
    """

    name: str
    reason: str
    old_type: Optional[IcebergType] = None
    new_type: Optional[IcebergType] = None


@dataclass
class SchemaChanges:
    """Aggregated schema changes detected between existing and new schemas.

    Attributes:
        new_columns: Columns present in source but not in the existing Iceberg table.
        type_promotions: Columns with compatible type changes.
        incompatible_changes: Columns with changes that cannot be applied.
    """

    new_columns: List[ColumnAddition] = field(default_factory=list)
    type_promotions: List[TypePromotion] = field(default_factory=list)
    incompatible_changes: List[IncompatibleChange] = field(default_factory=list)

    @property
    def has_incompatible_changes(self) -> bool:
        """Return True if any incompatible changes were detected."""
        return len(self.incompatible_changes) > 0

    @property
    def has_changes(self) -> bool:
        """Return True if any schema changes were detected."""
        return bool(self.new_columns or self.type_promotions or self.incompatible_changes)


class SchemaEvolutionService:
    """Manages Iceberg schema evolution for incremental loads.

    Detects schema differences between an existing Iceberg table and a new
    BigQuery source schema, then applies compatible changes (new columns,
    type promotions) while rejecting incompatible changes.

    Only valid type promotions are:
    - int → long
    - float → double
    - decimal(P, S) → decimal(P', S) where P' > P and S == S

    Any other type change is treated as incompatible.

    Attributes:
        VALID_PROMOTIONS: Mapping of source types to their valid promotion targets.
    """

    VALID_PROMOTIONS: dict[type, set[type]] = {
        IntegerType: {LongType},
        FloatType: {DoubleType},
        # DecimalType promotions are checked dynamically (P' > P, same S)
    }

    def __init__(self, type_mapper: Optional[BQToIcebergTypeMapper] = None) -> None:
        """Initialize the schema evolution service.

        Args:
            type_mapper: Optional BQToIcebergTypeMapper instance for mapping
                         new BigQuery columns to Iceberg types. If not provided,
                         a new instance is created.
        """
        self._type_mapper = type_mapper or BQToIcebergTypeMapper()

    def detect_changes(
        self,
        existing_schema: Schema,
        new_bq_columns: List[dict],
    ) -> SchemaChanges:
        """Detect schema changes between existing Iceberg schema and new BQ columns.

        Compares the existing Iceberg table schema against the latest BigQuery
        source schema to identify:
        - New columns (present in source, absent in Iceberg)
        - Type promotions (compatible type widening)
        - Incompatible changes (type changes not in valid promotion list,
          or columns removed from source)

        Args:
            existing_schema: The current Iceberg table Schema.
            new_bq_columns: List of BigQuery column definitions from the source.
                Each dict should contain "name", "type", "mode", and optionally "fields".

        Returns:
            A SchemaChanges instance with categorized changes.
        """
        changes = SchemaChanges()

        # Build lookup of existing fields by name
        existing_fields: dict[str, NestedField] = {
            f.name: f for f in existing_schema.fields
        }

        # Map new BQ columns to Iceberg types for comparison
        for bq_col in new_bq_columns:
            col_name = bq_col.get("name", "")
            col_type = bq_col.get("type", "STRING")
            col_mode = bq_col.get("mode", "NULLABLE")
            col_fields = bq_col.get("fields", None)

            # Map the BQ column to an Iceberg type
            new_iceberg_type = self._type_mapper.map_column(
                bq_type=col_type,
                bq_mode=col_mode,
                fields=col_fields,
                depth=0,
            )

            if col_name not in existing_fields:
                # New column detected
                changes.new_columns.append(
                    ColumnAddition(
                        name=col_name,
                        iceberg_type=new_iceberg_type,
                        bq_mode=col_mode,
                    )
                )
            else:
                # Column exists — check for type changes
                existing_field = existing_fields[col_name]
                existing_type = existing_field.field_type

                if existing_type != new_iceberg_type:
                    # Type has changed — check if it's a valid promotion
                    if self.is_compatible_promotion(existing_type, new_iceberg_type):
                        changes.type_promotions.append(
                            TypePromotion(
                                name=col_name,
                                old_type=existing_type,
                                new_type=new_iceberg_type,
                            )
                        )
                    else:
                        changes.incompatible_changes.append(
                            IncompatibleChange(
                                name=col_name,
                                reason=(
                                    f"Incompatible type change: "
                                    f"{type(existing_type).__name__} → "
                                    f"{type(new_iceberg_type).__name__}"
                                ),
                                old_type=existing_type,
                                new_type=new_iceberg_type,
                            )
                        )

        # Check for columns removed from source (present in Iceberg but not in BQ)
        new_col_names = {col.get("name", "") for col in new_bq_columns}
        for existing_name in existing_fields:
            if existing_name not in new_col_names:
                changes.incompatible_changes.append(
                    IncompatibleChange(
                        name=existing_name,
                        reason="Column removed from source schema",
                        old_type=existing_fields[existing_name].field_type,
                        new_type=None,
                    )
                )

        # Log summary of detected changes
        if changes.has_changes:
            logger.info(
                "Schema evolution detected: %d new column(s), %d type promotion(s), "
                "%d incompatible change(s)",
                len(changes.new_columns),
                len(changes.type_promotions),
                len(changes.incompatible_changes),
            )

        return changes

    def apply_evolution(self, table: Any, changes: SchemaChanges) -> None:
        """Apply compatible schema changes to the Iceberg table.

        Adds new columns as optional (nullable) fields regardless of their
        original BigQuery mode, and applies valid type promotions.

        Each operation is logged as an INFO-level entry including the table name,
        column name, and type information.

        Args:
            table: PyIceberg Table object to evolve.
            changes: The SchemaChanges to apply (only new_columns and
                     type_promotions are applied; incompatible changes are skipped).

        Raises:
            RuntimeError: If the table's schema evolution API call fails.
        """
        if not changes.new_columns and not changes.type_promotions:
            logger.debug("No compatible schema changes to apply")
            return

        table_name = getattr(table, "name", "unknown")

        try:
            with table.update_schema() as update:
                # Add new columns as optional (nullable) regardless of BQ mode
                for col_addition in changes.new_columns:
                    update.add_column(
                        path=col_addition.name,
                        field_type=col_addition.iceberg_type,
                        required=False,  # Always optional for backward compatibility
                    )
                    logger.info(
                        "Schema evolution: added column '%s' as optional "
                        "(type=%s, original_bq_mode=%s) to table '%s'",
                        col_addition.name,
                        type(col_addition.iceberg_type).__name__,
                        col_addition.bq_mode,
                        table_name,
                    )

                # Apply type promotions
                for promotion in changes.type_promotions:
                    update.update_column(
                        path=promotion.name,
                        field_type=promotion.new_type,
                    )
                    logger.info(
                        "Schema evolution: promoted column '%s' from %s to %s "
                        "in table '%s'",
                        promotion.name,
                        type(promotion.old_type).__name__,
                        type(promotion.new_type).__name__,
                        table_name,
                    )

        except Exception as e:
            logger.error(
                "Schema evolution failed for table '%s': %s",
                table_name,
                e,
            )
            raise RuntimeError(
                f"Schema evolution failed for table '{table_name}': {e}"
            ) from e

    def is_compatible_promotion(
        self,
        old_type: IcebergType,
        new_type: IcebergType,
    ) -> bool:
        """Check if a type change is a valid Iceberg type promotion.

        Valid promotions:
        - IntegerType → LongType
        - FloatType → DoubleType
        - DecimalType(P, S) → DecimalType(P', S) where P' > P and S == S

        All other type changes are considered incompatible.

        Args:
            old_type: The current Iceberg type of the column.
            new_type: The proposed new Iceberg type.

        Returns:
            True if the type change is a valid promotion, False otherwise.
        """
        # Handle DecimalType promotions dynamically
        if isinstance(old_type, DecimalType) and isinstance(new_type, DecimalType):
            return (
                new_type.precision > old_type.precision
                and new_type.scale == old_type.scale
            )

        # Check static promotion map
        valid_targets = self.VALID_PROMOTIONS.get(type(old_type), set())
        return type(new_type) in valid_targets
