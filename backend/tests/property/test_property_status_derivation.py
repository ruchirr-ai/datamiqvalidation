# Feature: validation-ux-redesign, Property 2: Status Derivation Consistency
"""
Property test: Status derivation consistency.

For any set of table results with step statuses drawn from
{passed, failed, error}:
  - If all step statuses are "passed" → run status = "completed"
  - If any step status is "failed" → run status = "failed"
  - If any table has "error" and no step is "failed" → run status = "failed"

This exercises the per-table status derivation logic and the run-level
status derivation via ``_compute_overall_status``.

**Validates: Requirements 2.1, 2.2, 2.3**
"""

from types import SimpleNamespace

from hypothesis import given, settings, strategies as st

from services.validation_service import ValidationService


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Each validation step can produce one of these statuses
step_status_strategy = st.sampled_from(["passed", "failed", "error"])

# A single table result is a triple of (ddl_status, row_count_status, data_match_status)
table_step_strategy = st.tuples(
    step_status_strategy, step_status_strategy, step_status_strategy
)

# A validation run has 1+ tables, each with 3 step statuses
table_results_strategy = st.lists(table_step_strategy, min_size=1, max_size=30)


# ---------------------------------------------------------------------------
# Helpers — replicate the production derivation logic as pure functions
# ---------------------------------------------------------------------------

def derive_table_status(ddl: str, row_count: str, data_match: str) -> str:
    """Derive per-table overall status from its three step statuses.

    Mirrors the logic in ``ValidationService.run_validation_background``:
      - All three "error" → "error"
      - Any failure or error (mixed) → "failed"
      - All "passed" → "completed"
    """
    all_error = ddl == "error" and row_count == "error" and data_match == "error"
    has_failure = "failed" in (ddl, row_count, data_match)
    has_error = "error" in (ddl, row_count, data_match)

    if all_error:
        return "error"
    if has_failure or has_error:
        return "failed"
    return "completed"


def derive_run_counters(table_statuses: list[str]) -> tuple[int, int, int, int]:
    """Compute (tables_total, tables_passed, tables_failed, tables_error).

    Mirrors the counter accumulation in ``run_validation_background``:
      - "completed" → passed
      - "error"     → error
      - anything else → failed
    """
    total = len(table_statuses)
    passed = sum(1 for s in table_statuses if s == "completed")
    error = sum(1 for s in table_statuses if s == "error")
    failed = total - passed - error
    return total, passed, failed, error


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------

@given(tables=table_results_strategy)
@settings(max_examples=200)
def test_all_passed_yields_completed(tables):
    """Property 2a: When every step of every table is "passed", the run
    status must be "completed" (reported as "passed" by _compute_overall_status).

    **Validates: Requirements 2.1**
    """
    table_statuses = [derive_table_status(*t) for t in tables]
    total, passed, failed, error = derive_run_counters(table_statuses)

    all_steps_passed = all(
        s == "passed" for ddl, rc, dm in tables for s in (ddl, rc, dm)
    )

    if all_steps_passed:
        # Every table should be "completed"
        assert all(s == "completed" for s in table_statuses), (
            f"Expected all table statuses 'completed' but got {table_statuses}"
        )
        # Run counters: all passed, none failed/error
        assert passed == total and failed == 0 and error == 0

        # _compute_overall_status should return "passed"
        run = SimpleNamespace(
            status="completed",
            tables_total=total,
            tables_passed=passed,
            tables_failed=failed,
            tables_error=error,
        )
        assert ValidationService._compute_overall_status(run) == "passed"


@given(tables=table_results_strategy)
@settings(max_examples=200)
def test_any_failed_yields_failed(tables):
    """Property 2b: When any step of any table is "failed", the run
    status must be "failed".

    **Validates: Requirements 2.2**
    """
    table_statuses = [derive_table_status(*t) for t in tables]
    total, passed, failed, error = derive_run_counters(table_statuses)

    any_step_failed = any(
        s == "failed" for ddl, rc, dm in tables for s in (ddl, rc, dm)
    )

    if any_step_failed:
        # At least one table must NOT be "completed"
        assert failed > 0 or error > 0, (
            f"Expected some failed/error tables but got passed={passed}, "
            f"failed={failed}, error={error}"
        )

        # _compute_overall_status should return "failed"
        run = SimpleNamespace(
            status="completed",
            tables_total=total,
            tables_passed=passed,
            tables_failed=failed,
            tables_error=error,
        )
        assert ValidationService._compute_overall_status(run) == "failed"


@given(tables=table_results_strategy)
@settings(max_examples=200)
def test_error_no_failed_yields_failed(tables):
    """Property 2c: When any table has "error" steps and NO step is "failed",
    the run status must still be "failed".

    **Validates: Requirements 2.3**
    """
    table_statuses = [derive_table_status(*t) for t in tables]
    total, passed, failed, error = derive_run_counters(table_statuses)

    any_step_error = any(
        s == "error" for ddl, rc, dm in tables for s in (ddl, rc, dm)
    )
    no_step_failed = not any(
        s == "failed" for ddl, rc, dm in tables for s in (ddl, rc, dm)
    )

    if any_step_error and no_step_failed:
        # Tables with errors (but no failures) become either "error" or
        # "failed" at the table level — either way the run is "failed"
        assert error > 0 or failed > 0, (
            f"Expected error or failed tables but got passed={passed}, "
            f"failed={failed}, error={error}"
        )

        # _compute_overall_status should return "failed"
        run = SimpleNamespace(
            status="completed",
            tables_total=total,
            tables_passed=passed,
            tables_failed=failed,
            tables_error=error,
        )
        assert ValidationService._compute_overall_status(run) == "failed"


@given(tables=table_results_strategy)
@settings(max_examples=200)
def test_per_table_status_derivation_consistency(tables):
    """Property 2 (combined): For any combination of step statuses, the
    per-table derivation and run-level derivation are consistent.

    - All steps passed → table "completed"
    - All steps error → table "error"
    - Mixed failures/errors → table "failed"

    **Validates: Requirements 2.1, 2.2, 2.3**
    """
    for ddl, rc, dm in tables:
        status = derive_table_status(ddl, rc, dm)
        steps = (ddl, rc, dm)

        if all(s == "passed" for s in steps):
            assert status == "completed", (
                f"All passed but table status={status}"
            )
        elif all(s == "error" for s in steps):
            assert status == "error", (
                f"All error but table status={status}"
            )
        else:
            assert status == "failed", (
                f"Mixed steps {steps} but table status={status}"
            )


def test_single_table_all_passed():
    """Concrete example: single table, all steps passed → run "passed".

    **Validates: Requirements 2.1**
    """
    run = SimpleNamespace(
        status="completed",
        tables_total=1,
        tables_passed=1,
        tables_failed=0,
        tables_error=0,
    )
    assert ValidationService._compute_overall_status(run) == "passed"


def test_single_table_one_failed():
    """Concrete example: single table with a failed step → run "failed".

    **Validates: Requirements 2.2**
    """
    run = SimpleNamespace(
        status="completed",
        tables_total=1,
        tables_passed=0,
        tables_failed=1,
        tables_error=0,
    )
    assert ValidationService._compute_overall_status(run) == "failed"


def test_single_table_all_error():
    """Concrete example: single table, all steps error → run "failed".

    **Validates: Requirements 2.3**
    """
    run = SimpleNamespace(
        status="completed",
        tables_total=1,
        tables_passed=0,
        tables_failed=0,
        tables_error=1,
    )
    assert ValidationService._compute_overall_status(run) == "failed"


def test_mixed_tables_some_passed_some_failed():
    """Concrete example: 3 tables — 2 passed, 1 failed → run "failed".

    **Validates: Requirements 2.2**
    """
    run = SimpleNamespace(
        status="completed",
        tables_total=3,
        tables_passed=2,
        tables_failed=1,
        tables_error=0,
    )
    assert ValidationService._compute_overall_status(run) == "failed"


def test_mixed_tables_passed_and_error():
    """Concrete example: 2 passed, 1 error, 0 failed → run "failed".

    **Validates: Requirements 2.3**
    """
    run = SimpleNamespace(
        status="completed",
        tables_total=3,
        tables_passed=2,
        tables_failed=0,
        tables_error=1,
    )
    assert ValidationService._compute_overall_status(run) == "failed"
