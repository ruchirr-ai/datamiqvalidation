# Feature: data-validation-module, Property 2: DDL comparison with identical schemas produces zero discrepancies
"""
Property test: DDL comparison identity.

For any randomly generated set of column definitions (name, BigQuery type,
nullability), creating identical source and target column sets and running
_validate_ddl MUST always produce zero discrepancies and a 'passed' status.

This exercises the full DDL comparison path including DataTypeMapper
equivalence logic, column matching by name, and nullability comparison.

**Validates: Requirements 18.2, 18.8**
"""

from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from services.data_type_mapper import DEFAULT_BQ_TO_REDSHIFT_TYPE_MAP, DataTypeMapper
from services.validation_service import ValidationService

# --- Strategies ---

# Column names: lowercase alpha strings (1-20 chars), no duplicates handled via st.lists(unique_by=...)
column_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Ll",)),
    min_size=1,
    max_size=20,
)

# BigQuery types drawn from the 12 known types in the default mapping
bq_type_strategy = st.sampled_from(list(DEFAULT_BQ_TO_REDSHIFT_TYPE_MAP.keys()))

# Nullability
nullable_strategy = st.booleans()

# A single column definition: (name, bq_type, is_nullable)
column_def_strategy = st.tuples(column_name_strategy, bq_type_strategy, nullable_strategy)

# A list of 1-15 column definitions with unique names
column_list_strategy = st.lists(
    column_def_strategy,
    min_size=1,
    max_size=15,
    unique_by=lambda c: c[0],
)


# --- Helpers ---

def _make_assessment_column_mock(column_name, data_type, is_nullable, ordinal_position):
    """Build a mock AssessmentColumn object matching the ORM interface."""
    col = MagicMock()
    col.column_name = column_name
    col.data_type = data_type
    col.is_nullable = is_nullable
    col.ordinal_position = ordinal_position
    return col


def _build_target_rows(columns, mapper):
    """Convert generated column defs into Redshift information_schema rows.

    Each row is a tuple: (column_name, data_type, is_nullable_str, ordinal_position)
    where data_type is the expected Redshift equivalent from the mapper and
    is_nullable_str is 'YES' or 'NO'.
    """
    rows = []
    for idx, (name, bq_type, is_nullable) in enumerate(columns, start=1):
        redshift_type = mapper.get_expected_redshift_type(bq_type)
        # Redshift information_schema returns lowercase types
        rows.append((
            name,
            redshift_type.lower() if redshift_type else bq_type.lower(),
            "YES" if is_nullable else "NO",
            idx,
        ))
    return rows


def _build_ddl_service_for_property(mock_db, mock_cache, source_columns, target_rows):
    """Wire a ValidationService with mocked DB queries for DDL comparison."""
    from models.assessment import AssessmentTable as AT, AssessmentColumn as AC

    svc = ValidationService(mock_db, mock_cache)
    svc.repo = MagicMock()

    assessment_table = MagicMock()
    assessment_table.id = 100
    assessment_table.assessment_id = 5
    assessment_table.dataset_name = "test_dataset"
    assessment_table.table_name = "test_table"

    def _query_side_effect(model):
        mock_q = MagicMock()
        if model is AT:
            mock_q.filter.return_value.first.return_value = assessment_table
        elif model is AC:
            mock_q.filter.return_value.order_by.return_value.all.return_value = source_columns
        return mock_q

    mock_db.query.side_effect = _query_side_effect
    return svc


# --- Property Test ---

@given(columns=column_list_strategy)
@settings(max_examples=150)
@patch("services.validation_service.psycopg2")
def test_ddl_identical_schemas_zero_discrepancies(mock_psycopg2, columns):
    """Property 2: Identical source and target schemas always produce zero discrepancies.

    For any randomly generated list of column definitions, when the target
    Redshift columns are constructed using the DataTypeMapper to translate
    BigQuery types to their expected Redshift equivalents (with matching
    nullability), _validate_ddl must return status 'passed' with an empty
    discrepancies list.

    **Validates: Requirements 18.2, 18.8**
    """
    mapper = DataTypeMapper()

    # Build source AssessmentColumn mocks
    source_cols = [
        _make_assessment_column_mock(name, bq_type, is_nullable, idx)
        for idx, (name, bq_type, is_nullable) in enumerate(columns, start=1)
    ]

    # Build matching target rows using the mapper for type translation
    target_rows = _build_target_rows(columns, mapper)

    # Set up mocks
    mock_db = MagicMock()
    mock_cache = MagicMock()
    svc = _build_ddl_service_for_property(mock_db, mock_cache, source_cols, target_rows)

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = target_rows
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_psycopg2.connect.return_value = mock_conn

    # Act
    result = svc._validate_ddl(
        run_id=1,
        table_name="test_table",
        dataset_name="test_dataset",
        assessment_id=5,
        target_conn_params={
            "host": "test-host",
            "port": 5439,
            "database": "testdb",
            "username": "user",
            "password": "pass",
        },
        type_mapping_overrides=None,
        workspace_id=1,
    )

    # Assert
    assert result["status"] == "passed", (
        f"Expected 'passed' but got '{result['status']}'. "
        f"Discrepancies: {result['result']['discrepancies']}"
    )
    assert len(result["result"]["discrepancies"]) == 0, (
        f"Expected zero discrepancies but found {len(result['result']['discrepancies'])}: "
        f"{result['result']['discrepancies']}"
    )
    assert result["result"]["source_column_count"] == len(columns)
    assert result["result"]["target_column_count"] == len(columns)
    assert result["result"]["columns_compared"] == len(columns)

# ---------------------------------------------------------------------------
# Property 3: DDL discrepancy count is bounded by total columns compared
# ---------------------------------------------------------------------------

# Redshift types for generating independent target columns
REDSHIFT_TYPES = [
    "VARCHAR", "BIGINT", "DOUBLE PRECISION", "DECIMAL", "BOOLEAN",
    "TIMESTAMP", "DATE", "TIME", "VARBYTE", "SUPER", "INTEGER",
    "TEXT", "REAL",
]

redshift_type_strategy = st.sampled_from(REDSHIFT_TYPES)

# A single target column definition: (name, redshift_type, is_nullable)
target_column_def_strategy = st.tuples(
    column_name_strategy, redshift_type_strategy, nullable_strategy,
)

# Independent source and target column lists (1-15 each, unique names within each list)
source_column_list_strategy = st.lists(
    column_def_strategy, min_size=1, max_size=15, unique_by=lambda c: c[0],
)
target_column_list_strategy = st.lists(
    target_column_def_strategy, min_size=1, max_size=15, unique_by=lambda c: c[0],
)


def _build_target_rows_raw(target_columns):
    """Convert target column defs into Redshift information_schema rows.

    Unlike _build_target_rows, this does NOT translate via the mapper –
    it uses the Redshift types directly as generated.
    """
    rows = []
    for idx, (name, rs_type, is_nullable) in enumerate(target_columns, start=1):
        rows.append((
            name,
            rs_type.lower(),
            "YES" if is_nullable else "NO",
            idx,
        ))
    return rows


@given(
    source_columns=source_column_list_strategy,
    target_columns=target_column_list_strategy,
)
@settings(max_examples=150)
@patch("services.validation_service.psycopg2")
def test_ddl_discrepancy_count_bounded_by_columns_compared(
    mock_psycopg2, source_columns, target_columns,
):
    """Property 3: DDL discrepancy count is bounded by total columns compared.

    For any two independently generated source (BQ types) and target
    (Redshift types) column sets, the number of discrepancies returned
    by _validate_ddl must be ≤ 2 × columns_compared, where
    columns_compared equals the union of all column names from both sets.

    Each column can produce at most:
      - 1 discrepancy if it only exists in source (missing_column) or
        only in target (extra_column)
      - 2 discrepancies if it exists in both (type_mismatch +
        nullability_mismatch)

    **Validates: Requirements 18.5, 18.8**
    """
    # Build source AssessmentColumn mocks
    source_mocks = [
        _make_assessment_column_mock(name, bq_type, is_nullable, idx)
        for idx, (name, bq_type, is_nullable) in enumerate(source_columns, start=1)
    ]

    # Build target rows using raw Redshift types (not translated)
    target_rows = _build_target_rows_raw(target_columns)

    # Set up mocks
    mock_db = MagicMock()
    mock_cache = MagicMock()
    svc = _build_ddl_service_for_property(mock_db, mock_cache, source_mocks, target_rows)

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = target_rows
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_psycopg2.connect.return_value = mock_conn

    # Act
    result = svc._validate_ddl(
        run_id=1,
        table_name="test_table",
        dataset_name="test_dataset",
        assessment_id=5,
        target_conn_params={
            "host": "test-host",
            "port": 5439,
            "database": "testdb",
            "username": "user",
            "password": "pass",
        },
        type_mapping_overrides=None,
        workspace_id=1,
    )

    # Assert
    discrepancy_count = len(result["result"]["discrepancies"])
    columns_compared = result["result"]["columns_compared"]

    # columns_compared should equal the union of source and target column names
    source_names = {name.lower() for name, _, _ in source_columns}
    target_names = {name.lower() for name, _, _ in target_columns}
    expected_columns_compared = len(source_names | target_names)
    assert columns_compared == expected_columns_compared, (
        f"columns_compared={columns_compared} != expected union size={expected_columns_compared}"
    )

    # Each column can generate at most 2 discrepancies
    assert discrepancy_count <= 2 * columns_compared, (
        f"discrepancy_count={discrepancy_count} exceeds 2 * columns_compared="
        f"{2 * columns_compared}. Discrepancies: {result['result']['discrepancies']}"
    )

