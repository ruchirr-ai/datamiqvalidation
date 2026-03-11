# Feature: data-validation-module, Property 1: Data type mapping round-trip consistency
"""
Property test: Data type mapping round-trip consistency.

For any DataTypeMapper instance (with arbitrary user overrides merged into the
default BigQuery-to-Redshift mapping), serializing via to_dict() then
reconstructing via from_dict() MUST produce an equivalent mapping object —
meaning every type pair in the original is preserved exactly in the restored
mapper.

**Validates: Requirements 10.14, 18.1**
"""

from hypothesis import given, settings, strategies as st

from services.data_type_mapper import (
    DataTypeMapper,
    DEFAULT_BQ_TO_REDSHIFT_TYPE_MAP,
)

# --- Strategies ---

# BigQuery type keys: draw from the 12 known types plus arbitrary uppercase identifiers
# to exercise override paths.
bq_type_strategy = st.sampled_from(list(DEFAULT_BQ_TO_REDSHIFT_TYPE_MAP.keys())) | st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=30,
).map(str.upper)

# Redshift type values: realistic type names (uppercase, may contain spaces)
redshift_type_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
    min_size=1,
    max_size=40,
).filter(lambda s: len(s.strip()) > 0)

# Override dict: 0-10 arbitrary BQ→Redshift overrides
overrides_strategy = st.dictionaries(
    keys=bq_type_strategy,
    values=redshift_type_strategy,
    min_size=0,
    max_size=10,
)


@given(overrides=overrides_strategy)
@settings(max_examples=150)
def test_data_type_mapper_round_trip(overrides):
    """Property 1: to_dict → from_dict round-trip produces an equivalent mapping.

    For any set of user overrides, the mapping after a round-trip must equal
    the original mapping exactly (same keys, same values).

    **Validates: Requirements 10.14, 18.1**
    """
    original = DataTypeMapper(overrides=overrides if overrides else None)
    serialized = original.to_dict()
    restored = DataTypeMapper.from_dict(serialized)

    # 1. The restored mapping dict must equal the original mapping dict
    assert restored.to_dict() == original.to_dict(), (
        f"Round-trip mismatch.\n"
        f"  Original: {original.to_dict()}\n"
        f"  Restored: {restored.to_dict()}"
    )

    # 2. Every type pair in the original must be equivalent in the restored mapper
    for bq_type, redshift_type in original.to_dict().items():
        assert restored.is_equivalent(bq_type, redshift_type), (
            f"Restored mapper does not consider {bq_type}→{redshift_type} equivalent"
        )

    # 3. get_expected_redshift_type must agree for every key
    for bq_type in original.to_dict():
        assert restored.get_expected_redshift_type(bq_type) == original.get_expected_redshift_type(bq_type), (
            f"get_expected_redshift_type mismatch for {bq_type}"
        )
