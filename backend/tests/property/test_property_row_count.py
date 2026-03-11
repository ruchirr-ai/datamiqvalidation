# Feature: data-validation-module, Property 4: Row count comparison with equal counts always produces 'passed' status
"""
Property test: Row count equality.

For any randomly generated non-negative integer used as both source and
target row count, _validate_row_count MUST always return status 'passed'
with difference == 0 and percentage_difference == 0.0.

**Validates: Requirements 18.3**
"""

from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from services.validation_service import ValidationService


@given(count=st.integers(min_value=0, max_value=10**9))
@settings(max_examples=150)
@patch.object(ValidationService, "_get_redshift_row_count")
@patch.object(ValidationService, "_get_bigquery_row_count")
def test_row_count_equal_always_passed(mock_bq_count, mock_rs_count, count):
    """Property 4: Equal source and target row counts always produce 'passed'.

    For any non-negative integer *count*, when both BigQuery and Redshift
    return the same value, _validate_row_count must return:
      - status == 'passed'
      - result.difference == 0
      - result.percentage_difference == 0.0

    **Validates: Requirements 18.3**
    """
    mock_bq_count.return_value = count
    mock_rs_count.return_value = count

    mock_db = MagicMock()
    mock_cache = MagicMock()
    svc = ValidationService(mock_db, mock_cache)

    result = svc._validate_row_count(
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
        workspace_id=1,
    )

    assert result["status"] == "passed", (
        f"Expected 'passed' but got '{result['status']}' for count={count}. "
        f"Result: {result['result']}"
    )
    assert result["result"]["source_count"] == count
    assert result["result"]["target_count"] == count
    assert result["result"]["difference"] == 0, (
        f"Expected difference 0 but got {result['result']['difference']} for count={count}"
    )
    assert result["result"]["percentage_difference"] == 0.0, (
        f"Expected percentage_difference 0.0 but got "
        f"{result['result']['percentage_difference']} for count={count}"
    )
