# Feature: validation-ux-redesign, Property 1: Run Name Persistence Round-Trip
"""
Property test: Run name round-trip.

For any string s of length 0–255, creating a ValidationRun with run_name=s
and calling to_dict() must return run_name == s. Creating without run_name
must return run_name == None.

This exercises the model column definition, to_dict() serialization, and
the Pydantic schema validation for run_name.

**Validates: Requirements 1.1, 1.3, 1.4**
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from hypothesis import given, settings, strategies as st

from models.validation_run import ValidationRun
from models.validation_schemas import CreateValidationRunRequest, ValidationRunResponse

# Import AssessmentLog so SQLAlchemy can resolve the Assessment.logs relationship
# when this test runs alongside other test files that trigger mapper configuration.
import models.assessment_log  # noqa: F401


# --- Strategies ---

# Run name: any text 0–255 characters (the column is VARCHAR(255))
run_name_strategy = st.text(min_size=0, max_size=255)


# --- Helpers ---

def _make_validation_run(run_name=None):
    """Build a ValidationRun instance with required fields and optional run_name.

    Uses dummy values for all required columns so the model can be
    instantiated without a database session.
    """
    now = datetime.now(timezone.utc)
    run = ValidationRun(
        id=1,
        workspace_id=1,
        migration_id=10,
        source_connection_id=100,
        target_connection_id=200,
        status="pending",
        progress_percentage=0,
        tables_total=5,
        tables_passed=0,
        tables_failed=0,
        tables_error=0,
        batch_size=10000,
        created_by="testuser",
        created_at=now,
        updated_at=now,
    )
    if run_name is not None:
        run.run_name = run_name
    return run


# --- Property Tests ---

@given(name=run_name_strategy)
@settings(max_examples=100)
def test_run_name_model_round_trip(name):
    """Property 1: Any string of length 0–255 survives the model round-trip.

    For any generated string *name*, setting run_name on a ValidationRun
    and calling to_dict() must return the exact same string under the
    'run_name' key.

    **Validates: Requirements 1.1, 1.3, 1.4**
    """
    run = _make_validation_run(run_name=name)

    result = run.to_dict()

    assert result["run_name"] == name, (
        f"Expected run_name={name!r} but got {result['run_name']!r}"
    )


@given(name=run_name_strategy)
@settings(max_examples=100)
def test_run_name_schema_round_trip(name):
    """Property 1 (schema layer): run_name survives Pydantic request→response.

    For any generated string *name* of length 0–255, constructing a
    CreateValidationRunRequest with run_name=name must accept it, and
    a ValidationRunResponse built with the same value must serialize
    run_name identically.

    **Validates: Requirements 1.1, 1.3, 1.4**
    """
    # Request schema accepts the run_name
    request = CreateValidationRunRequest(
        migration_id=10,
        run_name=name,
    )
    assert request.run_name == name, (
        f"Request schema mangled run_name: expected {name!r}, got {request.run_name!r}"
    )

    # Response schema preserves the run_name
    now = datetime.now(timezone.utc)
    response = ValidationRunResponse(
        id=1,
        workspace_id=1,
        migration_id=10,
        source_connection_id=100,
        target_connection_id=200,
        status="pending",
        progress_percentage=0,
        tables_total=5,
        tables_passed=0,
        tables_failed=0,
        tables_error=0,
        created_by="testuser",
        created_at=now,
        updated_at=now,
        run_name=name,
    )
    assert response.run_name == name, (
        f"Response schema mangled run_name: expected {name!r}, got {response.run_name!r}"
    )


def test_run_name_none_when_omitted():
    """Creating a ValidationRun without run_name must return None in to_dict().

    **Validates: Requirements 1.1, 1.4**
    """
    run = _make_validation_run(run_name=None)

    result = run.to_dict()

    assert result["run_name"] is None, (
        f"Expected run_name=None but got {result['run_name']!r}"
    )


def test_run_name_none_in_schema_when_omitted():
    """CreateValidationRunRequest without run_name defaults to None.

    **Validates: Requirements 1.1, 1.4**
    """
    request = CreateValidationRunRequest(migration_id=10)
    assert request.run_name is None, (
        f"Expected run_name=None but got {request.run_name!r}"
    )

    now = datetime.now(timezone.utc)
    response = ValidationRunResponse(
        id=1,
        workspace_id=1,
        migration_id=10,
        source_connection_id=100,
        target_connection_id=200,
        status="pending",
        progress_percentage=0,
        tables_total=5,
        tables_passed=0,
        tables_failed=0,
        tables_error=0,
        created_by="testuser",
        created_at=now,
        updated_at=now,
    )
    assert response.run_name is None, (
        f"Expected response run_name=None but got {response.run_name!r}"
    )
