"""
Data Type Mapper Service
Encapsulates BigQuery-to-Redshift type equivalence logic for DDL comparison
during post-migration data validation.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Default BigQuery-to-Redshift type mapping constant.
# This is the authoritative mapping used during DDL comparison.
# Users can override individual entries via type_mapping_overrides on a ValidationRun.
DEFAULT_BQ_TO_REDSHIFT_TYPE_MAP: dict[str, str] = {
    "STRING": "VARCHAR",
    "INT64": "BIGINT",
    "FLOAT64": "DOUBLE PRECISION",
    "NUMERIC": "DECIMAL",
    "BIGNUMERIC": "DECIMAL",
    "BOOL": "BOOLEAN",
    "TIMESTAMP": "TIMESTAMP",
    "DATE": "DATE",
    "TIME": "TIME",
    "BYTES": "VARBYTE",
    "ARRAY": "SUPER",
    "STRUCT": "SUPER",
}


class DataTypeMapper:
    """Maps BigQuery data types to their expected Redshift equivalents.

    Supports user-provided overrides that merge with the default mapping,
    allowing per-run customization of type equivalence rules.

    Args:
        overrides: Optional dict of BigQuery-type → Redshift-type overrides
                   that replace or extend the default mapping.
    """

    def __init__(self, overrides: Optional[dict[str, str]] = None):
        self.mapping: dict[str, str] = {
            **DEFAULT_BQ_TO_REDSHIFT_TYPE_MAP,
            **(overrides or {}),
        }
        if overrides:
            logger.info(
                f"DataTypeMapper initialized with {len(overrides)} override(s)"
            )

    def is_equivalent(self, bq_type: str, redshift_type: str) -> bool:
        """Check whether a BigQuery type and Redshift type are equivalent.

        Comparison is case-insensitive for both the BigQuery lookup key
        and the Redshift target value.

        Args:
            bq_type: The BigQuery column data type (e.g. "STRING").
            redshift_type: The Redshift column data type (e.g. "VARCHAR").

        Returns:
            True if the mapping considers them equivalent, False otherwise.
        """
        expected = self.get_expected_redshift_type(bq_type)
        if expected is None:
            return False
        return expected.strip().upper() == redshift_type.strip().upper()

    def get_expected_redshift_type(self, bq_type: str) -> Optional[str]:
        """Return the expected Redshift type for a given BigQuery type.

        Lookup is case-insensitive on the BigQuery type key.

        Args:
            bq_type: The BigQuery column data type.

        Returns:
            The mapped Redshift type string, or None if no mapping exists.
        """
        # Build a case-insensitive lookup
        upper_key = bq_type.strip().upper()
        for key, value in self.mapping.items():
            if key.upper() == upper_key:
                return value
        return None

    def to_dict(self) -> dict[str, str]:
        """Serialize the current mapping to a plain dict.

        Returns:
            A copy of the internal mapping dictionary.
        """
        return dict(self.mapping)

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "DataTypeMapper":
        """Reconstruct a DataTypeMapper from a serialized dict.

        The provided dict completely replaces the default mapping,
        which is the expected behaviour for round-trip serialization.

        Args:
            data: A dict of BigQuery-type → Redshift-type pairs.

        Returns:
            A new DataTypeMapper instance whose mapping equals *data*.
        """
        instance = cls.__new__(cls)
        instance.mapping = dict(data)
        return instance
