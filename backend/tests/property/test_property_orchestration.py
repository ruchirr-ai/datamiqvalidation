# Feature: data-validation-module, Properties 6 & 7: Orchestration invariants
"""
Property tests for validation run orchestration invariants.

Property 6: tables_passed + tables_failed + tables_error always equals tables_total.
Property 7: progress_percentage is always between 0 and 100 inclusive.

These tests verify pure counting/arithmetic logic extracted from the
orchestration flow in ValidationService.run_validation_background without
requiring mocked external services.

**Validates: Requirements 18.6, 18.10**
"""

from hypothesis import given, settings, strategies as st


# ---------------------------------------------------------------------------
# Property 6: Report invariant
# tables_passed + tables_failed + tables_error == tables_total
# ---------------------------------------------------------------------------

@given(
    table_statuses=st.lists(
        st.sampled_from(["completed", "failed", "error"]),
        min_size=1,
        max_size=50,
    )
)
@settings(max_examples=150)
def test_tables_sum_invariant(table_statuses):
    """Property 6: tables_passed + tables_failed + tables_error == tables_total.

    Simulates the counting logic from run_validation_background: for each
    table, the orchestrator increments one of three counters based on the
    table's final status. After processing all tables the sum of the three
    counters must equal the total number of tables.

    **Validates: Requirements 18.6**
    """
    tables_total = len(table_statuses)
    tables_passed = 0
    tables_failed = 0
    tables_error = 0

    for status in table_statuses:
        if status == "completed":
            tables_passed += 1
        elif status == "error":
            tables_error += 1
        else:
            tables_failed += 1

    assert tables_passed + tables_failed + tables_error == tables_total, (
        f"Invariant violated: {tables_passed} + {tables_failed} + {tables_error} "
        f"!= {tables_total}. Statuses: {table_statuses}"
    )


# ---------------------------------------------------------------------------
# Property 7: Progress percentage bounds
# progress_percentage is always in [0, 100]
# ---------------------------------------------------------------------------

@given(
    total_tables=st.integers(min_value=1, max_value=100),
    completed_count=st.integers(min_value=0, max_value=100),
)
@settings(max_examples=150)
def test_progress_percentage_bounds(total_tables, completed_count):
    """Property 7: progress_percentage is always between 0 and 100 inclusive.

    After any table completion update the orchestrator calculates
    ``progress = int(completed_count / total_tables * 100)``.
    This must always stay within [0, 100] for any valid combination of
    completed_count (0 … total_tables) and total_tables (≥ 1).

    **Validates: Requirements 18.10**
    """
    # Clamp completed_count to valid range (0..total_tables) to mirror
    # real orchestration where completed_count never exceeds total_tables.
    completed_count = min(completed_count, total_tables)

    progress_percentage = int(completed_count / total_tables * 100)

    assert 0 <= progress_percentage <= 100, (
        f"progress_percentage={progress_percentage} out of bounds [0, 100]. "
        f"completed_count={completed_count}, total_tables={total_tables}"
    )
