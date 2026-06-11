"""
Lightweight Iceberg type representations mirroring PyIceberg's type system.

These classes provide a compatible interface for type mapping without requiring
the full PyIceberg dependency. When PyIceberg is added to the project, these
can be replaced with imports from `pyiceberg.types`.

Reference: https://py.iceberg.apache.org/api/#types
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


class IcebergType:
    """Base class for all Iceberg types."""

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other)

    def __hash__(self) -> int:
        return hash(type(self).__name__)

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


class BooleanType(IcebergType):
    """Iceberg boolean type."""
    pass


class IntegerType(IcebergType):
    """Iceberg 32-bit integer type."""
    pass


class LongType(IcebergType):
    """Iceberg 64-bit long type."""
    pass


class FloatType(IcebergType):
    """Iceberg 32-bit float type."""
    pass


class DoubleType(IcebergType):
    """Iceberg 64-bit double type."""
    pass


class DateType(IcebergType):
    """Iceberg date type (days since epoch)."""
    pass


class TimeType(IcebergType):
    """Iceberg time type (microseconds since midnight)."""
    pass


class TimestampType(IcebergType):
    """Iceberg timestamp without timezone."""
    pass


class TimestamptzType(IcebergType):
    """Iceberg timestamp with timezone."""
    pass


class StringType(IcebergType):
    """Iceberg string (UTF-8) type."""
    pass


class BinaryType(IcebergType):
    """Iceberg binary type."""
    pass


@dataclass(frozen=True)
class DecimalType(IcebergType):
    """Iceberg decimal type with precision and scale.

    Args:
        precision: Total number of digits (1-38).
        scale: Number of digits after the decimal point.
    """
    precision: int
    scale: int

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DecimalType):
            return False
        return self.precision == other.precision and self.scale == other.scale

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.precision, self.scale))

    def __repr__(self) -> str:
        return f"DecimalType(precision={self.precision}, scale={self.scale})"


@dataclass
class NestedField:
    """A field within a StructType or Schema.

    Args:
        field_id: Unique field identifier within the schema.
        name: Field name.
        field_type: The Iceberg type of this field.
        required: Whether the field is required (non-nullable).
        doc: Optional documentation string.
    """
    field_id: int
    name: str
    field_type: IcebergType
    required: bool = False
    doc: Optional[str] = None

    def __repr__(self) -> str:
        req = "required" if self.required else "optional"
        return f"NestedField(id={self.field_id}, name='{self.name}', type={self.field_type}, {req})"


@dataclass
class StructType(IcebergType):
    """Iceberg struct type containing named fields.

    Args:
        fields: Tuple of NestedField instances.
    """
    fields: tuple[NestedField, ...] = field(default_factory=tuple)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StructType):
            return False
        return self.fields == other.fields

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.fields))

    def __repr__(self) -> str:
        return f"StructType(fields={self.fields})"


@dataclass
class ListType(IcebergType):
    """Iceberg list (array) type.

    Args:
        element_id: Unique field ID for the list element.
        element_type: The Iceberg type of list elements.
        element_required: Whether elements are required (non-nullable).
    """
    element_id: int
    element_type: IcebergType
    element_required: bool = False

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ListType):
            return False
        return (
            self.element_id == other.element_id
            and self.element_type == other.element_type
            and self.element_required == other.element_required
        )

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.element_id, self.element_type))

    def __repr__(self) -> str:
        return f"ListType(element_id={self.element_id}, element_type={self.element_type})"


@dataclass
class Schema:
    """Iceberg table schema containing top-level fields.

    Args:
        fields: Tuple of NestedField instances representing columns.
        schema_id: Optional schema version identifier.
    """
    fields: tuple[NestedField, ...] = field(default_factory=tuple)
    schema_id: int = 0

    def __repr__(self) -> str:
        return f"Schema(fields={self.fields}, schema_id={self.schema_id})"

    def __len__(self) -> int:
        return len(self.fields)

    def __iter__(self):
        return iter(self.fields)
