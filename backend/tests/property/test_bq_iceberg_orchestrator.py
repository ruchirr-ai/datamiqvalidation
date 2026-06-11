# Feature: bq-to-iceberg-migration, Properties 9, 13, 14, 16, 18
"""
Property tests for BQ-to-Iceberg orchestrator and parallel loading:

- Property 9: Progress percentage calculation with parallelism
  Generate arbitrary N total tables and M completed; verify progress = floor((M/N)*100).
  **Validates: Requirements 5.8, 12.3**

- Property 13: State machine transition validity
  Generate arbitrary status transitions; verify only valid transitions succeed
  and cancel preserves config.
  **Validates: Requirements 7.4, 7.5**

- Property 14: Checkpoint-based resume skips completed tables
  Generate arbitrary table load statuses; verify only non-completed tables are processed on resume.
  **Validates: Requirements 7.3**

- Property 16: Error code categorization
  Generate arbitrary operation failures; verify correct error_code from defined set is logged.
  **Validates: Requirements 11.3**

- Property 18: Parallel worker isolation
  Simulate parallel workers with injected failures; verify non-failing workers complete successfully.
  **Validates: Requirements 12.2, 12.4**
"""

import asyncio
import math
from unittest.mock import MagicMock, AsyncMock, patch

from hypothesis import given, settings, strategies as st, assume

from services.bq_iceberg_migration.orchestrator import (
    IcebergMigrationOrchestrator,
    VALID_TRANSITIONS,
    PRESERVED_CONFIG_FIELDS,
    calculate_progress_percentage,
)
from services.bq_iceberg_migration.error_codes import (
    ErrorCode,
    MigrationLogger,
    ERROR_CODE_REGISTRY,
)
from services.bq_iceberg_migration.iceberg_loader import (
    ParallelIcebergLoader,
    LoadResult,
    TableLoadResult,
)


# =============================================================================
# Strategies
# =============================================================================

# Strategy for total tables (at least 1 to avoid division by zero)
total_tables_strategy = st.integers(min_value=1, max_value=1000)

# Strategy for completed tables (will be constrained to <= total)
completed_tables_strategy = st.integers(min_value=0, max_value=1000)

# All valid migration statuses
ALL_STATUSES = list(VALID_TRANSITIONS.keys())
status_strategy = st.sampled_from(ALL_STATUSES)

# Strategy for arbitrary status pairs (including invalid transitions)
all_possible_statuses = ALL_STATUSES + ["unknown", "invalid", "processing"]
any_status_strategy = st.sampled_from(all_possible_statuses)

# Strategy for table names
table_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
    min_size=1,
    max_size=50,
)

# Strategy for table load statuses
table_load_status_strategy = st.sampled_from(["pending", "completed", "failed", "running"])

# Strategy for error-producing operations
error_operations = [
    ("glue_permission", "Access denied for glue:CreateDatabase", ErrorCode.GLUE_PERMISSION_DENIED),
    ("glue_registration", "Failed to register table in glue catalog", ErrorCode.GLUE_REGISTRATION_FAILED),
    ("iceberg_create", "Failed to create iceberg table", ErrorCode.ICEBERG_TABLE_CREATE_FAILED),
    ("iceberg_append", "Failed to append data files to iceberg table", ErrorCode.ICEBERG_APPEND_FAILED),
    ("s3_access", "S3 bucket access denied: 403 forbidden", ErrorCode.ICEBERG_S3_ACCESS_ERROR),
    ("schema_evolution", "Schema evolution operation failed", ErrorCode.ICEBERG_SCHEMA_EVOLUTION_FAILED),
    ("schema_incompatible", "Incompatible schema change: STRING to INTEGER", ErrorCode.SCHEMA_EVOLUTION_INCOMPATIBLE),
    ("s3_tables", "S3Tables API call failed: CreateTable", ErrorCode.S3_TABLES_API_FAILED),
    ("athena_timeout", "Athena verification query timed out after 120s", ErrorCode.ATHENA_VERIFICATION_TIMEOUT),
    ("cost_calc", "Cost calculation failed: invalid data size", ErrorCode.COST_CALCULATION_FAILED),
    ("custom_invalid", "Custom structure invalid: missing columns", ErrorCode.CUSTOM_STRUCTURE_INVALID),
]

error_operation_strategy = st.sampled_from(error_operations)


# =============================================================================
# Property 9: Progress percentage calculation with parallelism
# =============================================================================


@given(
    total=total_tables_strategy,
    completed=completed_tables_strategy,
)
@settings(max_examples=200)
def test_progress_percentage_calculation(total, completed):
    """Property 9: Progress percentage calculation with parallelism.

    For any migration with N total tables where M have completed (0 ≤ M ≤ N, N > 0),
    progress_percentage SHALL equal floor((M / N) * 100) regardless of parallel
    execution order.

    **Validates: Requirements 5.8, 12.3**
    """
    # Constrain completed to be <= total
    completed = min(completed, total)

    result = calculate_progress_percentage(completed, total)

    expected = math.floor((completed / total) * 100)

    assert result == expected, (
        f"Progress mismatch: completed={completed}, total={total}, "
        f"expected={expected}, got={result}"
    )


@given(total=total_tables_strategy)
@settings(max_examples=100)
def test_progress_percentage_zero_completed(total):
    """Property 9 (boundary): Zero completed tables gives 0%.

    **Validates: Requirements 5.8, 12.3**
    """
    result = calculate_progress_percentage(0, total)
    assert result == 0, f"Expected 0% for 0/{total} completed, got {result}%"


@given(total=total_tables_strategy)
@settings(max_examples=100)
def test_progress_percentage_all_completed(total):
    """Property 9 (boundary): All tables completed gives 100%.

    **Validates: Requirements 5.8, 12.3**
    """
    result = calculate_progress_percentage(total, total)
    assert result == 100, f"Expected 100% for {total}/{total} completed, got {result}%"


def test_progress_percentage_zero_total():
    """Property 9 (edge case): Zero total tables gives 0%.

    **Validates: Requirements 5.8, 12.3**
    """
    result = calculate_progress_percentage(0, 0)
    assert result == 0, f"Expected 0% for 0/0, got {result}%"


# =============================================================================
# Property 13: State machine transition validity
# =============================================================================


def _create_mock_migration(status="pending"):
    """Create a mock migration object with the given status."""
    migration = MagicMock()
    migration.status = status
    migration.id = 1
    migration.source_connection_id = 10
    migration.source_project_id = "my-project"
    migration.source_dataset = "my_dataset"
    migration.source_tables = ["table1", "table2"]
    migration.target_connection_id = 20
    migration.destination_type = "iceberg_s3"
    migration.s3_bucket = "my-bucket"
    migration.s3_path_prefix = "iceberg/"
    migration.aws_region = "us-east-1"
    migration.glue_database_name = "analytics_db"
    migration.checkpoint_data = {"assessment_tables": []}
    migration.structure_report = {"tables": []}
    migration.cost_analysis_report = {"setup_costs": {}}
    migration.table_load_configs = {"events": {"load_type": "full"}}
    migration.aws_access_key_id = "AKIAEXAMPLE"
    migration.aws_secret_access_key_encrypted = "encrypted_secret"
    migration.aws_role_arn = None
    migration.load_type = "full"
    migration.parallelism = 4
    migration.enable_load_stage_verification = False
    migration.structure_approved_at = None
    migration.structure_approved_by = None
    return migration


def _create_orchestrator():
    """Create an orchestrator with mock dependencies."""
    return IcebergMigrationOrchestrator(
        loader=MagicMock(),
        structure_report_generator=MagicMock(),
        cost_engine=MagicMock(),
        schema_evolution_service=MagicMock(),
        validation_service=MagicMock(),
        athena_verifier=MagicMock(),
        migration_logger=None,
    )


@given(
    current_status=status_strategy,
    target_status=any_status_strategy,
)
@settings(max_examples=300)
def test_state_machine_transition_validity(current_status, target_status):
    """Property 13: State machine transition validity.

    For any current status and target status, the orchestrator SHALL allow
    the transition if and only if it is in the valid transitions map.

    **Validates: Requirements 7.4, 7.5**
    """
    orchestrator = _create_orchestrator()
    migration = _create_mock_migration(status=current_status)

    valid_targets = VALID_TRANSITIONS.get(current_status, set())
    expected_valid = target_status in valid_targets

    result = orchestrator.is_valid_transition(current_status, target_status)

    assert result == expected_valid, (
        f"Transition {current_status} → {target_status}: "
        f"expected valid={expected_valid}, got={result}"
    )


@given(current_status=status_strategy)
@settings(max_examples=100)
def test_state_machine_cancel_preserves_config(current_status):
    """Property 13 (cancel): Cancel from pending_review preserves all config.

    When the user cancels from pending_review, all configuration data
    (connections, source settings, target settings, assessment data,
    table selections) SHALL be preserved.

    **Validates: Requirements 7.4, 7.5**
    """
    orchestrator = _create_orchestrator()
    migration = _create_mock_migration(status="pending_review")

    # Record original config values
    original_values = {}
    for field_name in PRESERVED_CONFIG_FIELDS:
        if hasattr(migration, field_name):
            original_values[field_name] = getattr(migration, field_name)

    # Cancel from review
    orchestrator.handle_cancel_from_review(migration)

    # Verify status changed to cancelled
    assert migration.status == "cancelled", (
        f"Expected status 'cancelled', got '{migration.status}'"
    )

    # Verify all config fields are preserved (not cleared)
    for field_name, original_value in original_values.items():
        current_value = getattr(migration, field_name)
        assert current_value == original_value, (
            f"Field '{field_name}' was modified on cancel: "
            f"original={original_value}, current={current_value}"
        )


@given(
    current_status=status_strategy,
    target_status=status_strategy,
)
@settings(max_examples=200)
def test_state_machine_transition_applies_correctly(current_status, target_status):
    """Property 13 (apply): Valid transitions update the status field.

    When a valid transition is applied via transition_status(), the migration's
    status field SHALL be updated to the new status.

    **Validates: Requirements 7.4, 7.5**
    """
    orchestrator = _create_orchestrator()
    migration = _create_mock_migration(status=current_status)

    valid_targets = VALID_TRANSITIONS.get(current_status, set())
    is_valid = target_status in valid_targets

    result = orchestrator.transition_status(migration, target_status)

    if is_valid:
        assert result is True
        assert migration.status == target_status
    else:
        assert result is False
        assert migration.status == current_status


# =============================================================================
# Property 14: Checkpoint-based resume skips completed tables
# =============================================================================


@given(
    table_statuses=st.dictionaries(
        keys=table_name_strategy,
        values=table_load_status_strategy,
        min_size=1,
        max_size=20,
    ),
)
@settings(max_examples=200)
def test_checkpoint_resume_skips_completed(table_statuses):
    """Property 14: Checkpoint-based resume skips completed tables.

    For any set of table load statuses, resuming SHALL process only tables
    whose load_status is NOT 'completed'. Tables with status 'completed'
    SHALL be skipped.

    **Validates: Requirements 7.3**
    """
    orchestrator = _create_orchestrator()

    # Build a structure plan with all tables
    all_tables = [
        {"proposed_name": name, "source_table": name, "columns": []}
        for name in table_statuses.keys()
    ]

    structure_plan = {"tables": all_tables}

    # Set up migration with checkpoint data containing table statuses
    migration = _create_mock_migration()
    migration.checkpoint_data = {"table_load_statuses": table_statuses}

    # Filter tables for resume
    tables_to_load = orchestrator._filter_tables_for_resume(migration, structure_plan)

    # Verify: only non-completed tables are returned
    loaded_names = {t["proposed_name"] for t in tables_to_load}

    for table_name, status in table_statuses.items():
        if status == "completed":
            assert table_name not in loaded_names, (
                f"Completed table '{table_name}' should be skipped on resume"
            )
        else:
            assert table_name in loaded_names, (
                f"Non-completed table '{table_name}' (status='{status}') "
                f"should be included on resume"
            )


@given(
    table_names=st.lists(table_name_strategy, min_size=1, max_size=15, unique=True),
)
@settings(max_examples=100)
def test_checkpoint_resume_no_statuses_loads_all(table_names):
    """Property 14 (no checkpoint): Without checkpoint data, all tables are loaded.

    **Validates: Requirements 7.3**
    """
    orchestrator = _create_orchestrator()

    all_tables = [
        {"proposed_name": name, "source_table": name, "columns": []}
        for name in table_names
    ]
    structure_plan = {"tables": all_tables}

    migration = _create_mock_migration()
    migration.checkpoint_data = {}  # No table statuses

    tables_to_load = orchestrator._filter_tables_for_resume(migration, structure_plan)

    assert len(tables_to_load) == len(table_names), (
        f"Expected all {len(table_names)} tables to be loaded, "
        f"got {len(tables_to_load)}"
    )


@given(
    table_names=st.lists(table_name_strategy, min_size=1, max_size=15, unique=True),
)
@settings(max_examples=100)
def test_checkpoint_resume_all_completed_loads_none(table_names):
    """Property 14 (all completed): When all tables are completed, none are loaded.

    **Validates: Requirements 7.3**
    """
    orchestrator = _create_orchestrator()

    all_tables = [
        {"proposed_name": name, "source_table": name, "columns": []}
        for name in table_names
    ]
    structure_plan = {"tables": all_tables}

    # All tables marked as completed
    table_statuses = {name: "completed" for name in table_names}
    migration = _create_mock_migration()
    migration.checkpoint_data = {"table_load_statuses": table_statuses}

    tables_to_load = orchestrator._filter_tables_for_resume(migration, structure_plan)

    assert len(tables_to_load) == 0, (
        f"Expected 0 tables to load when all completed, got {len(tables_to_load)}"
    )


# =============================================================================
# Property 16: Error code categorization
# =============================================================================


@given(error_op=error_operation_strategy)
@settings(max_examples=150)
def test_error_code_categorization(error_op):
    """Property 16: Error code categorization.

    For any Iceberg operation failure, the system SHALL log an ERROR with the
    correct categorized error_code from the defined set.

    **Validates: Requirements 11.3**
    """
    operation_name, error_message, expected_code = error_op

    # Create a migration logger
    migration_logger = MigrationLogger(migration_id=1)

    # Log the error
    entry = migration_logger.log_error(
        error_code=expected_code,
        operation=operation_name,
        message=error_message,
        table_name="test_table",
    )

    # Verify the error code is correctly categorized
    assert entry.error_code == expected_code.value, (
        f"Expected error_code='{expected_code.value}', got='{entry.error_code}'"
    )

    # Verify it's logged at ERROR level
    assert entry.level == "ERROR", (
        f"Expected level='ERROR', got='{entry.level}'"
    )

    # Verify the error code is in the defined set
    all_valid_codes = {code.value for code in ErrorCode}
    assert entry.error_code in all_valid_codes, (
        f"Error code '{entry.error_code}' not in defined set: {all_valid_codes}"
    )

    # Verify metadata is available in the registry
    metadata = ERROR_CODE_REGISTRY.get(expected_code)
    assert metadata is not None, (
        f"Error code '{expected_code}' not found in ERROR_CODE_REGISTRY"
    )


@given(error_op=error_operation_strategy)
@settings(max_examples=100)
def test_error_code_no_credentials_logged(error_op):
    """Property 16 (security): Error logs SHALL NOT contain credential values.

    **Validates: Requirements 11.3**
    """
    operation_name, error_message, expected_code = error_op

    migration_logger = MigrationLogger(migration_id=1)

    # Include sensitive data in context
    sensitive_context = {
        "aws_secret_access_key": "SUPER_SECRET_KEY_12345",
        "password": "my_password_123",
        "table_name": "events",
        "operation": operation_name,
    }

    entry = migration_logger.log_error(
        error_code=expected_code,
        operation=operation_name,
        message=f"Error with secret_key=AKIAIOSFODNN7EXAMPLE: {error_message}",
        table_name="test_table",
        context=sensitive_context,
    )

    # Verify sensitive values are redacted in context
    entry_dict = entry.to_dict()
    context = entry_dict.get("context", {})

    assert context.get("aws_secret_access_key") != "SUPER_SECRET_KEY_12345", (
        "aws_secret_access_key should be redacted in log context"
    )
    assert context.get("password") != "my_password_123", (
        "password should be redacted in log context"
    )


# =============================================================================
# Property 18: Parallel worker isolation
# =============================================================================


@given(
    num_tables=st.integers(min_value=2, max_value=10),
    failing_indices=st.lists(
        st.integers(min_value=0, max_value=9),
        min_size=1,
        max_size=5,
        unique=True,
    ),
)
@settings(max_examples=100)
def test_parallel_worker_isolation(num_tables, failing_indices):
    """Property 18: Parallel worker isolation.

    For any set of tables being loaded in parallel, a failure in one worker
    SHALL NOT affect the execution or result of any other worker. Non-failing
    workers must complete successfully.

    **Validates: Requirements 12.2, 12.4**
    """
    # Constrain failing indices to valid range
    failing_indices = [i for i in failing_indices if i < num_tables]
    assume(len(failing_indices) > 0)
    assume(len(failing_indices) < num_tables)  # At least one should succeed

    # Build table plans
    tables = [
        {
            "proposed_name": f"table_{i}",
            "source_table": f"table_{i}",
            "columns": [{"name": "id", "bq_type": "INT64", "iceberg_type": "long", "nullable": False}],
            "database": "test_db",
            "data_files": [f"s3://bucket/table_{i}/file.parquet"],
            "table_properties": {},
        }
        for i in range(num_tables)
    ]

    structure_plan = {"tables": tables}

    # Create mock dependencies
    mock_catalog = MagicMock()
    mock_cred_provider = MagicMock()
    mock_type_mapper = MagicMock()
    mock_partition_mapper = MagicMock()
    mock_dedup_guard = MagicMock()

    # Configure dedup guard to allow all appends
    mock_dedup_guard.is_safe_to_append.return_value = (True, ["s3://bucket/file.parquet"])

    loader = ParallelIcebergLoader(
        catalog=mock_catalog,
        credential_provider=mock_cred_provider,
        type_mapper=mock_type_mapper,
        partition_mapper=mock_partition_mapper,
        dedup_guard=mock_dedup_guard,
        parallelism=num_tables,  # All parallel
    )

    # Track which tables were processed
    processed_tables = []
    failed_tables_set = set(f"table_{i}" for i in failing_indices)

    # Mock the catalog to fail for specific tables
    def mock_load_namespace(db):
        pass  # Database exists

    mock_catalog.load_namespace_properties.side_effect = mock_load_namespace

    call_count = {"value": 0}

    def mock_create_table(identifier, schema=None, partition_spec=None, sort_order=None, properties=None):
        table_name = identifier.split(".")[-1] if "." in identifier else identifier
        if table_name in failed_tables_set:
            raise RuntimeError(f"Simulated S3 access error for {table_name}")
        mock_table = MagicMock()
        mock_table.name = table_name
        processed_tables.append(table_name)
        return mock_table

    def mock_load_table(identifier):
        # Table doesn't exist yet
        raise Exception("Table not found")

    mock_catalog.create_table.side_effect = mock_create_table
    mock_catalog.load_table.side_effect = mock_load_table

    # Create mock migration
    migration = MagicMock()
    migration.glue_database_name = "test_db"

    # Run the loader
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            loader.load_tables(migration, structure_plan)
        )
    finally:
        loop.close()

    # Verify: non-failing tables should succeed
    successful_names = {r.table_name for r in result.table_results if r.success}
    failed_names = {r.table_name for r in result.table_results if not r.success}

    expected_successful = set(f"table_{i}" for i in range(num_tables) if i not in failing_indices)

    # All non-failing tables should have succeeded
    for table_name in expected_successful:
        assert table_name in successful_names, (
            f"Non-failing table '{table_name}' should have succeeded. "
            f"Successful: {successful_names}, Failed: {failed_names}"
        )

    # All failing tables should have failed
    for table_name in failed_tables_set:
        assert table_name in failed_names, (
            f"Failing table '{table_name}' should have failed. "
            f"Successful: {successful_names}, Failed: {failed_names}"
        )

    # Total results should account for all tables
    assert result.total_tables == num_tables, (
        f"Expected {num_tables} total tables, got {result.total_tables}"
    )


@given(num_tables=st.integers(min_value=1, max_value=8))
@settings(max_examples=50)
def test_parallel_worker_all_succeed(num_tables):
    """Property 18 (all succeed): When no failures are injected, all workers complete.

    **Validates: Requirements 12.2, 12.4**
    """
    tables = [
        {
            "proposed_name": f"table_{i}",
            "source_table": f"table_{i}",
            "columns": [],
            "database": "test_db",
            "data_files": [],
            "table_properties": {},
        }
        for i in range(num_tables)
    ]

    structure_plan = {"tables": tables}

    mock_catalog = MagicMock()
    mock_cred_provider = MagicMock()
    mock_type_mapper = MagicMock()
    mock_partition_mapper = MagicMock()
    mock_dedup_guard = MagicMock()
    mock_dedup_guard.is_safe_to_append.return_value = (False, [])

    mock_catalog.load_namespace_properties.return_value = {}

    def mock_load_table(identifier):
        mock_table = MagicMock()
        mock_table.name = identifier
        return mock_table

    mock_catalog.load_table.side_effect = mock_load_table

    loader = ParallelIcebergLoader(
        catalog=mock_catalog,
        credential_provider=mock_cred_provider,
        type_mapper=mock_type_mapper,
        partition_mapper=mock_partition_mapper,
        dedup_guard=mock_dedup_guard,
        parallelism=num_tables,
    )

    migration = MagicMock()
    migration.glue_database_name = "test_db"

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            loader.load_tables(migration, structure_plan)
        )
    finally:
        loop.close()

    assert result.total_tables == num_tables
    assert result.successful_tables == num_tables
    assert result.failed_tables == 0
    assert result.all_succeeded is True
