# Feature: data-validation-module, Property 5: Record-level matching with identical datasets produces zero mismatches
"""
Property test: Record-level matching identity.

For any randomly generated list of row dicts (with consistent keys/types
and unique integer "id" column), comparing identical source and target
datasets via _validate_records MUST always produce:
  - status == 'passed'
  - matched_count == total_compared == len(rows)
  - missing_count == 0
  - extra_count == 0
  - mismatch_count == 0

**Validates: Requirements 18.4, 18.9**
"""

import copy
from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from services.validation_service import ValidationService

# --- Strategies ---

# Column names: lowercase alpha strings (1-15 chars), excluding "id" (reserved for PK)
_non_id_column_name = st.text(
    alphabet=st.characters(whitelist_categories=("Ll",)),
    min_size=1,
    max_size=15,
).filter(lambda s: s != "id")

# Column value: string, integer, or None
_column_value = st.one_of(
    st.text(min_size=0, max_size=50),
    st.integers(min_value=-10**6, max_value=10**6),
    st.none(),
)

# Generate a list of unique non-id column names (0-5 extra columns)
_extra_column_names = st.lists(
    _non_id_column_name,
    min_size=0,
    max_size=5,
    unique=True,
)


@st.composite
def row_data_strategy(draw):
    """Generate a list of row dicts with consistent keys, unique integer ids.

    Each row has an "id" column (unique integer) plus 0-5 additional
    columns with string, integer, or None values.
    """
    extra_cols = draw(_extra_column_names)
    num_rows = draw(st.integers(min_value=0, max_value=20))

    # Generate unique ids
    ids = draw(
        st.lists(
            st.integers(min_value=1, max_value=10**6),
            min_size=num_rows,
            max_size=num_rows,
            unique=True,
        )
    )

    rows = []
    for row_id in ids:
        row = {"id": row_id}
        for col_name in extra_cols:
            row[col_name] = draw(_column_value)
        rows.append(row)

    return rows


# --- Property Test ---

@given(rows=row_data_strategy())
@settings(max_examples=150)
@patch.object(ValidationService, "_read_redshift_rows")
@patch.object(ValidationService, "_read_bigquery_rows")
def test_record_matching_identical_datasets_zero_mismatches(
    mock_bq_rows, mock_rs_rows, rows,
):
    """Property 5: Identical source and target datasets always produce zero mismatches.

    For any randomly generated list of row dicts with unique integer "id"
    columns and consistent keys/types, when both BigQuery and Redshift
    return the exact same data, _validate_records must return:
      - status == 'passed'
      - matched_count == len(rows) == total_compared
      - missing_count == 0
      - extra_count == 0
      - mismatch_count == 0

    **Validates: Requirements 18.4, 18.9**
    """
    # Use deep copies so source and target are independent objects
    source_rows = copy.deepcopy(rows)
    target_rows = copy.deepcopy(rows)

    mock_bq_rows.return_value = source_rows
    mock_rs_rows.return_value = target_rows

    mock_db = MagicMock()
    mock_cache = MagicMock()
    svc = ValidationService(mock_db, mock_cache)

    result = svc._validate_records(
        run_id=1,
        table_name="test_table",
        dataset_name="test_dataset",
        source_conn_params={
            "credentials_json": '{"project_id": "proj"}',
            "project_id": "proj",
        },
        target_conn_params={
            "host": "test-host",
            "port": 5439,
            "database": "testdb",
            "username": "user",
            "password": "pass",
        },
        primary_key=["id"],
        batch_size=10000,
        type_mapping_overrides=None,
        workspace_id=1,
    )

    num_rows = len(rows)

    assert result["status"] == "passed", (
        f"Expected 'passed' but got '{result['status']}' for {num_rows} rows. "
        f"Result: {result['result']}"
    )
    assert result["result"]["matched_count"] == num_rows, (
        f"Expected matched_count={num_rows} but got "
        f"{result['result']['matched_count']}"
    )
    assert result["result"]["total_compared"] == num_rows, (
        f"Expected total_compared={num_rows} but got "
        f"{result['result']['total_compared']}"
    )
    assert result["result"]["missing_count"] == 0, (
        f"Expected missing_count=0 but got {result['result']['missing_count']}"
    )
    assert result["result"]["extra_count"] == 0, (
        f"Expected extra_count=0 but got {result['result']['extra_count']}"
    )
    assert result["result"]["mismatch_count"] == 0, (
        f"Expected mismatch_count=0 but got {result['result']['mismatch_count']}"
    )
