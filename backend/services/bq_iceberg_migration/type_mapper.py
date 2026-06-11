"""
BQ-to-Iceberg Type Mapper

Maps BigQuery column data types to Iceberg types using a PyIceberg-compatible
type system. Handles recursive STRUCT/ARRAY mapping up to a configurable depth
limit, with fallback to StringType (JSON) for deeply nested or unrecognized types.

Requirements: 3.1, 3.4, 3.5, 3.6, 3.7
"""

from __future__ import annotations

import logging
from typing import Optional

from .iceberg_types import (
    BinaryType,
    BooleanType,
    DateType,
    DecimalType,
    DoubleType,
    IcebergType,
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

logger = logging.getLogger(__name__)


class BQToIcebergTypeMapper:
    """Maps BigQuery data types to Iceberg types using PyIceberg type system.

    Supports all standard BigQuery types including recursive STRUCT/RECORD
    and ARRAY types. Unrecognized types fall back to StringType with a warning.
    Deeply nested STRUCTs beyond MAX_STRUCT_DEPTH are flattened to StringType (JSON).

    Attributes:
        TYPE_MAP: Static mapping of BigQuery type names to Iceberg type instances.
        MAX_STRUCT_DEPTH: Maximum recursion depth for nested STRUCT fields.
    """

    TYPE_MAP: dict[str, IcebergType] = {
        "STRING": StringType(),
        "BYTES": BinaryType(),
        "INT64": LongType(),
        "INTEGER": LongType(),
        "FLOAT64": DoubleType(),
        "FLOAT": DoubleType(),
        "NUMERIC": DecimalType(38, 9),
        "BIGNUMERIC": DecimalType(38, 18),
        "BOOLEAN": BooleanType(),
        "BOOL": BooleanType(),
        "DATE": DateType(),
        "DATETIME": TimestampType(),       # without timezone
        "TIMESTAMP": TimestamptzType(),    # with timezone
        "TIME": TimeType(),
        "GEOGRAPHY": StringType(),         # stored as GeoJSON string
        "JSON": StringType(),              # stored as JSON string
    }

    MAX_STRUCT_DEPTH: int = 15

    def __init__(self) -> None:
        """Initialize the type mapper.

        Uses a field ID counter to assign unique IDs to nested fields
        within a single schema mapping operation.
        """
        self._field_id_counter: int = 0

    def _next_field_id(self) -> int:
        """Generate the next unique field ID for schema construction.

        Returns:
            An incrementing integer field ID.
        """
        self._field_id_counter += 1
        return self._field_id_counter

    def map_column(
        self,
        bq_type: str,
        bq_mode: str,
        fields: Optional[list[dict]] = None,
        depth: int = 0,
    ) -> IcebergType:
        """Map a single BigQuery column to an Iceberg type.

        Handles STRUCT/RECORD types by recursively mapping nested fields,
        and ARRAY types by wrapping the element type in a ListType.

        Args:
            bq_type: BigQuery data type name (e.g., "STRING", "STRUCT", "ARRAY").
            bq_mode: BigQuery column mode ("REQUIRED", "NULLABLE", "REPEATED").
            fields: Nested field definitions for STRUCT/RECORD types. Each dict
                    should contain "name", "type", "mode", and optionally "fields".
            depth: Current recursion depth for nested STRUCT handling.

        Returns:
            The corresponding Iceberg type. Returns StringType for unrecognized
            types or when struct depth exceeds MAX_STRUCT_DEPTH.
        """
        upper_type = bq_type.strip().upper()
        upper_mode = bq_mode.strip().upper() if bq_mode else "NULLABLE"

        # Handle REPEATED mode as ARRAY wrapping
        if upper_mode == "REPEATED":
            element_type = self._map_type_internal(upper_type, fields, depth)
            element_id = self._next_field_id()
            return ListType(
                element_id=element_id,
                element_type=element_type,
                element_required=False,
            )

        return self._map_type_internal(upper_type, fields, depth)

    def _map_type_internal(
        self,
        bq_type: str,
        fields: Optional[list[dict]],
        depth: int,
    ) -> IcebergType:
        """Internal type mapping logic handling STRUCT/RECORD and primitive types.

        Args:
            bq_type: Uppercase BigQuery type name.
            fields: Nested field definitions for STRUCT types.
            depth: Current recursion depth.

        Returns:
            The mapped Iceberg type.
        """
        # Handle STRUCT/RECORD types
        if bq_type in ("STRUCT", "RECORD"):
            if depth >= self.MAX_STRUCT_DEPTH:
                logger.warning(
                    "STRUCT nesting depth %d exceeds maximum of %d. "
                    "Flattening remaining levels to JSON StringType.",
                    depth + 1,
                    self.MAX_STRUCT_DEPTH,
                )
                return StringType()

            if not fields:
                logger.warning(
                    "STRUCT/RECORD type encountered with no nested fields. "
                    "Mapping to empty StructType."
                )
                return StructType(fields=())

            nested_fields: list[NestedField] = []
            for sub_field in fields:
                field_name = sub_field.get("name", "unknown")
                field_type = sub_field.get("type", "STRING")
                field_mode = sub_field.get("mode", "NULLABLE")
                sub_fields = sub_field.get("fields", None)

                mapped_type = self.map_column(
                    bq_type=field_type,
                    bq_mode=field_mode,
                    fields=sub_fields,
                    depth=depth + 1,
                )

                nested_fields.append(
                    NestedField(
                        field_id=self._next_field_id(),
                        name=field_name,
                        field_type=mapped_type,
                        required=not self.is_nullable(field_mode),
                    )
                )

            return StructType(fields=tuple(nested_fields))

        # Handle primitive types via TYPE_MAP
        iceberg_type = self.TYPE_MAP.get(bq_type)
        if iceberg_type is not None:
            return iceberg_type

        # Unrecognized type: fall back to StringType with warning
        logger.warning(
            "Unrecognized BigQuery type '%s'. Mapping to StringType.",
            bq_type,
        )
        return StringType()

    def map_schema(self, bq_columns: list[dict]) -> Schema:
        """Map a full BigQuery table schema to an Iceberg Schema object.

        Resets the internal field ID counter before mapping to ensure
        consistent field IDs starting from 1.

        Args:
            bq_columns: List of BigQuery column definitions. Each dict should
                        contain "name", "type", "mode", and optionally "fields"
                        for STRUCT/RECORD columns.

        Returns:
            An Iceberg Schema object with all columns mapped.

        Example:
            >>> mapper = BQToIcebergTypeMapper()
            >>> schema = mapper.map_schema([
            ...     {"name": "id", "type": "INT64", "mode": "REQUIRED"},
            ...     {"name": "name", "type": "STRING", "mode": "NULLABLE"},
            ...     {"name": "created_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
            ... ])
        """
        # Reset field ID counter for each schema mapping
        self._field_id_counter = 0

        schema_fields: list[NestedField] = []
        for column in bq_columns:
            col_name = column.get("name", "unknown")
            col_type = column.get("type", "STRING")
            col_mode = column.get("mode", "NULLABLE")
            col_fields = column.get("fields", None)

            mapped_type = self.map_column(
                bq_type=col_type,
                bq_mode=col_mode,
                fields=col_fields,
                depth=0,
            )

            schema_fields.append(
                NestedField(
                    field_id=self._next_field_id(),
                    name=col_name,
                    field_type=mapped_type,
                    required=not self.is_nullable(col_mode),
                )
            )

        return Schema(fields=tuple(schema_fields))

    def is_nullable(self, bq_mode: str) -> bool:
        """Determine if a BigQuery column mode maps to nullable in Iceberg.

        Args:
            bq_mode: BigQuery column mode string.

        Returns:
            False if mode is REQUIRED, True otherwise (NULLABLE or REPEATED).
        """
        return bq_mode.strip().upper() != "REQUIRED"
