"""
Partition Spec Mapper Service

Converts BigQuery partitioning configuration to Iceberg PartitionSpec
and BigQuery clustering columns to Iceberg SortOrder.

Enforces hidden partitioning transforms for all time-based columns.
Never creates identity partitions on time columns — always uses transform
functions (day, hour, month, year) to enable automatic partition pruning.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Time-based column types that support partition transforms
TIME_BASED_TYPES = {"DATE", "DATETIME", "TIMESTAMP"}


@dataclass
class PartitionField:
    """Represents a single field in an Iceberg partition spec.

    Attributes:
        source_column: The source column name to partition on.
        transform: The partition transform to apply (e.g., day, hour, month, year).
    """

    source_column: str
    transform: str


@dataclass
class PartitionSpec:
    """Represents an Iceberg partition specification.

    A partition spec defines how a table's data is organized into partitions.
    Each field specifies a source column and a transform function.

    Attributes:
        fields: List of partition fields defining the partitioning strategy.
    """

    fields: list[PartitionField] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize the partition spec to a JSON-compatible dict."""
        return {
            "fields": [
                {"source_column": f.source_column, "transform": f.transform}
                for f in self.fields
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PartitionSpec":
        """Deserialize a partition spec from a dict.

        Args:
            data: Dict with a 'fields' key containing partition field definitions.

        Returns:
            A new PartitionSpec instance.
        """
        fields = [
            PartitionField(
                source_column=f["source_column"],
                transform=f["transform"],
            )
            for f in data.get("fields", [])
        ]
        return cls(fields=fields)


@dataclass
class SortField:
    """Represents a single field in an Iceberg sort order.

    Attributes:
        source_column: The column name to sort on.
        direction: Sort direction, either 'asc' or 'desc'.
        null_order: Where nulls appear in sort, either 'nulls_first' or 'nulls_last'.
    """

    source_column: str
    direction: str = "asc"
    null_order: str = "nulls_last"


@dataclass
class SortOrder:
    """Represents an Iceberg sort order specification.

    Sort order defines how data files are organized within partitions,
    preserving the clustering column sequence from BigQuery.

    Attributes:
        fields: List of sort fields in ordinal sequence.
    """

    fields: list[SortField] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize the sort order to a JSON-compatible dict."""
        return {
            "fields": [
                {
                    "source_column": f.source_column,
                    "direction": f.direction,
                    "null_order": f.null_order,
                }
                for f in self.fields
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SortOrder":
        """Deserialize a sort order from a dict.

        Args:
            data: Dict with a 'fields' key containing sort field definitions.

        Returns:
            A new SortOrder instance.
        """
        fields = [
            SortField(
                source_column=f["source_column"],
                direction=f.get("direction", "asc"),
                null_order=f.get("null_order", "nulls_last"),
            )
            for f in data.get("fields", [])
        ]
        return cls(fields=fields)


# Mapping from internal transform names to their plural display forms
# Used for human-readable partition display strings (e.g., "days(column_name)")
TRANSFORM_DISPLAY_MAP: dict[str, str] = {
    "day": "days",
    "hour": "hours",
    "month": "months",
    "year": "years",
}


def format_partition_display(transform: str, column_name: str) -> str:
    """Format a partition spec as a human-readable display string.

    Converts internal transform names to their plural display forms and
    wraps the column name in the transform function call syntax.

    Examples:
        format_partition_display("day", "created_at") -> "days(created_at)"
        format_partition_display("hour", "event_ts") -> "hours(event_ts)"

    Args:
        transform: Internal transform name (day, hour, month, year).
        column_name: The partition column name.

    Returns:
        Display string in format "{transform_plural}({column_name})".
    """
    display_transform = TRANSFORM_DISPLAY_MAP.get(transform, transform)
    return f"{display_transform}({column_name})"


class PartitionSpecMapper:
    """Maps BQ partitioning and clustering to Iceberg partition specs and sort orders.

    Enforces hidden partitioning transforms for all time-based columns.
    Never creates identity partitions on time columns — always uses transform
    functions (day, hour, month, year) to enable automatic partition pruning.

    Attributes:
        TRANSFORM_MAP: Mapping from (partition_type, granularity) tuples to Iceberg
            transform functions. Covers all valid combinations of time-based types
            and granularities.
    """

    # Mapping: (partition_type, granularity) → transform
    # Ensures hidden partitioning is always used for time-based columns.
    TRANSFORM_MAP: dict[tuple[str, Optional[str]], str] = {
        ("DATE", None): "day",
        ("DATE", "DAY"): "day",
        ("DATETIME", None): "day",
        ("DATETIME", "DAY"): "day",
        ("DATETIME", "HOUR"): "hour",
        ("DATETIME", "MONTH"): "month",
        ("DATETIME", "YEAR"): "year",
        ("TIMESTAMP", None): "day",
        ("TIMESTAMP", "DAY"): "day",
        ("TIMESTAMP", "HOUR"): "hour",
        ("TIMESTAMP", "MONTH"): "month",
        ("TIMESTAMP", "YEAR"): "year",
    }

    def map_partition_spec(
        self,
        partition_column: str,
        partition_type: str,
        granularity: Optional[str] = None,
    ) -> PartitionSpec:
        """Map BQ partitioning to Iceberg hidden partition transform.

        Always uses transform functions (days, hours, months, years).
        Never creates identity partitions on time-based columns.

        Args:
            partition_column: Source column name.
            partition_type: BQ type (DATE, DATETIME, TIMESTAMP).
            granularity: BQ granularity (HOUR, DAY, MONTH, YEAR) or None.

        Returns:
            PartitionSpec with the appropriate transform.

        Raises:
            ValueError: If partition_column is empty, if the partition_type is a
                time-based type but the (type, granularity) combination is not in
                TRANSFORM_MAP, or if an identity partition would be created on a
                time-based column.
        """
        if not partition_column:
            raise ValueError("partition_column must not be empty")

        # Normalize inputs for lookup
        normalized_type = partition_type.strip().upper() if partition_type else ""
        normalized_granularity: Optional[str] = None
        if granularity:
            normalized_granularity = granularity.strip().upper()

        # Guard: time-based columns must always use hidden partitioning transforms
        if normalized_type in TIME_BASED_TYPES:
            lookup_key = (normalized_type, normalized_granularity)
            transform = self.TRANSFORM_MAP.get(lookup_key)

            if transform is None:
                raise ValueError(
                    f"Unsupported partition configuration: type='{normalized_type}', "
                    f"granularity='{normalized_granularity}'. "
                    f"Time-based columns must use hidden partitioning transforms "
                    f"(day, hour, month, year). Identity partitions are not allowed."
                )

            # Explicit guard: never allow identity on time-based columns
            if transform == "identity":
                raise ValueError(
                    f"Identity partitions are not allowed on time-based column "
                    f"'{partition_column}' (type='{normalized_type}'). "
                    f"Use hidden partitioning transforms (day, hour, month, year) instead."
                )
        else:
            # For non-time-based columns, use identity transform
            transform = "identity"
            logger.warning(
                "Column '%s' has non-time-based type '%s'; "
                "using identity transform for partition spec",
                partition_column,
                partition_type,
            )

        partition_field = PartitionField(
            source_column=partition_column,
            transform=transform,
        )

        logger.info(
            "Mapped partition spec: column='%s', type='%s', granularity='%s' -> transform='%s'",
            partition_column,
            partition_type,
            granularity,
            transform,
        )

        return PartitionSpec(fields=[partition_field])

    def map_sort_order(self, clustering_columns: list[str]) -> SortOrder:
        """Create an Iceberg SortOrder preserving BigQuery clustering column sequence.

        Each clustering column is mapped to an ascending sort field with nulls last,
        maintaining the exact ordinal sequence defined in BigQuery.

        Args:
            clustering_columns: List of column names in the order defined by
                                BigQuery clustering configuration.

        Returns:
            A SortOrder with fields in the same sequence as the input columns.
            Returns an empty SortOrder if the input list is empty.
        """
        sort_fields = [
            SortField(
                source_column=col,
                direction="asc",
                null_order="nulls_last",
            )
            for col in clustering_columns
            if col  # Skip empty strings
        ]

        if clustering_columns:
            logger.info(
                "Mapped sort order from %d clustering column(s): %s",
                len(sort_fields),
                [f.source_column for f in sort_fields],
            )

        return SortOrder(fields=sort_fields)
