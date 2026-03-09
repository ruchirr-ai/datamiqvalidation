# Feature: code-conversion-enhancements, Property 3: Dialect validation rejects invalid values
"""
Property test: Dialect validation rejects invalid values.

For any string not in the allowed source dialect set {"Bigquery", "SQL Server",
"Redshift"}, the ConversionService should reject with ValueError. For any string
not in the allowed target dialect set {"Redshift", "SQL Server", "BigQuery"},
the ConversionService should reject with ValueError. For any string in the
respective allowed set, the request should be accepted.

**Validates: Requirements 3.5**
"""

import pytest
from hypothesis import given, settings, strategies as st, assume

from models.conversion_schemas import ALLOWED_SOURCE_DIALECTS, ALLOWED_TARGET_DIALECTS
from services.conversion_service import ConversionService


# Use a fixed valid target/source for cross-testing
VALID_TARGET = "Redshift"
VALID_SOURCE = "Bigquery"


@given(dialect=st.text(min_size=1, max_size=50))
@settings(max_examples=20)
def test_invalid_source_dialect_rejected(dialect):
    """Property 3: Random strings outside ALLOWED_SOURCE_DIALECTS are rejected.

    **Validates: Requirements 3.5**
    """
    assume(dialect not in ALLOWED_SOURCE_DIALECTS)
    with pytest.raises(ValueError, match="Invalid source_dialect"):
        ConversionService._validate_dialects(dialect, VALID_TARGET)


@given(dialect=st.text(min_size=1, max_size=50))
@settings(max_examples=20)
def test_invalid_target_dialect_rejected(dialect):
    """Property 3: Random strings outside ALLOWED_TARGET_DIALECTS are rejected.

    **Validates: Requirements 3.5**
    """
    assume(dialect not in ALLOWED_TARGET_DIALECTS)
    with pytest.raises(ValueError, match="Invalid target_dialect"):
        ConversionService._validate_dialects(VALID_SOURCE, dialect)


@given(
    source=st.sampled_from(sorted(ALLOWED_SOURCE_DIALECTS)),
    target=st.sampled_from(sorted(ALLOWED_TARGET_DIALECTS)),
)
@settings(max_examples=20)
def test_valid_dialects_accepted(source, target):
    """Property 3: All valid source/target dialect combinations are accepted.

    **Validates: Requirements 3.5**
    """
    # Should not raise
    ConversionService._validate_dialects(source, target)
