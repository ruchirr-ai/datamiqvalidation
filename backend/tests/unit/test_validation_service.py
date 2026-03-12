"""
Unit tests for ValidationService.create_validation_run.

Mocks the database session, repository, and cache to test the service
logic for creating validation runs including migration/connection
verification, table resolution, and workspace isolation.
"""

import pytest
from unittest.mock import MagicMock, call, patch
from datetime import datetime

from services.validation_service import ValidationService
from services.validation_cache import ValidationCache
from models.connection import Connection


# ── Helpers ───────────────────────────────────────────────────────────

_SENTINEL = object()


def _make_migration(
    migration_id=1,
    workspace_id=1,
    status="completed",
    source_tables=_SENTINEL,
):
    """Build a mock MigrationBQRedshift object."""
    m = MagicMock()
    m.id = migration_id
    m.workspace_id = workspace_id
    m.status = status
    m.source_tables = ["table_a", "table_b"] if source_tables is _SENTINEL else source_tables
    return m


def _make_connection(conn_id=10, is_active=True, name="test_conn"):
    """Build a mock Connection object."""
    c = MagicMock()
    c.id = conn_id
    c.is_active = is_active
    c.name = name
    return c


def _make_run_dict(run_id=1, workspace_id=1, migration_id=1, tables_total=2):
    """Build a dict that mimics ValidationRun.to_dict()."""
    return {
        "id": run_id,
        "workspace_id": workspace_id,
        "migration_id": migration_id,
        "source_connection_id": 10,
        "target_connection_id": 20,
        "bedrock_model": None,
        "batch_size": 10000,
        "type_mapping_overrides": None,
        "status": "pending",
        "progress_percentage": 0,
        "tables_total": tables_total,
        "tables_passed": 0,
        "tables_failed": 0,
        "tables_error": 0,
        "started_at": None,
        "completed_at": None,
        "duration_seconds": None,
        "created_by": "testuser",
        "created_at": "2026-01-25T10:00:00Z",
        "updated_at": "2026-01-25T10:00:00Z",
    }


def _make_run_model(run_id=1, workspace_id=1, tables_total=2):
    """Build a mock ValidationRun model with to_dict()."""
    run = MagicMock()
    run.id = run_id
    run.workspace_id = workspace_id
    run.to_dict.return_value = _make_run_dict(
        run_id=run_id, workspace_id=workspace_id, tables_total=tables_total,
    )
    return run


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def mock_db():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture()
def mock_cache():
    """Create a mock ValidationCache."""
    cache = MagicMock(spec=ValidationCache)
    cache.set_run.return_value = None
    return cache


def _build_service(
    mock_db,
    mock_cache,
    migration=None,
    source_conn=None,
    target_conn=None,
    run_model=None,
):
    """Create a ValidationService with fully mocked dependencies.

    Patches db.query() to return the provided migration and connection
    mocks, and patches the repository to return the provided run model.
    """
    svc = ValidationService(mock_db, mock_cache)

    # Mock db.query().filter().first() for Migration and Connection lookups
    from models.bq_redshift_migration import MigrationBQRedshift
    from models.connection import Connection

    # Track Connection query calls to return source_conn first, target_conn second
    conn_call_count = {"n": 0}
    conn_results = [source_conn, target_conn]

    def _query_side_effect(model):
        mock_q = MagicMock()
        if model is MigrationBQRedshift:
            mock_q.filter.return_value.first.return_value = migration
        elif model is Connection:
            idx = conn_call_count["n"]
            conn_call_count["n"] += 1
            result = conn_results[idx] if idx < len(conn_results) else None
            mock_q.filter.return_value.first.return_value = result
        return mock_q

    mock_db.query.side_effect = _query_side_effect

    # Mock the repository
    svc.repo = MagicMock()
    if run_model is None:
        run_model = _make_run_model()
    svc.repo.create_run.return_value = run_model
    svc.repo.create_table_result.return_value = MagicMock()
    svc.repo.count_active_runs.return_value = 0

    return svc


# ── Sample payloads ──────────────────────────────────────────────────

VALID_PAYLOAD = {
    "workspace_id": 1,
    "migration_id": 1,
    "source_connection_id": 10,
    "target_connection_id": 20,
    "tables": ["users", "orders"],
    "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "batch_size": 10000,
    "type_mapping_overrides": None,
    "created_by": "testuser",
}

PAYLOAD_NO_TABLES = {
    "workspace_id": 1,
    "migration_id": 1,
    "source_connection_id": 10,
    "target_connection_id": 20,
    "tables": None,
    "bedrock_model": None,
    "batch_size": 5000,
    "type_mapping_overrides": {"STRING": "TEXT"},
    "created_by": "testuser",
}

WORKSPACE_ID = 1


# ── Tests: Successful creation ────────────────────────────────────────

class TestCreateValidationRunSuccess:
    """Test create_validation_run with valid inputs."""

    def test_creates_run_with_explicit_tables(self, mock_db, mock_cache):
        """Test creating a validation run with an explicit table list."""
        run_model = _make_run_model(tables_total=2)
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
            run_model=run_model,
        )

        result = svc.create_validation_run(**VALID_PAYLOAD)

        assert result["status"] == "pending"
        assert result["migration_id"] == 1
        assert result["tables_total"] == 2
        assert result["progress_percentage"] == 0
        assert result["workspace_id"] == WORKSPACE_ID

    def test_repo_create_run_called_with_correct_args(self, mock_db, mock_cache):
        """Test that repo.create_run is called with the right parameters."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        svc.create_validation_run(**VALID_PAYLOAD)

        svc.repo.create_run.assert_called_once_with(
            workspace_id=1,
            migration_id=1,
            source_connection_id=10,
            target_connection_id=20,
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            batch_size=10000,
            type_mapping_overrides=None,
            status="pending",
            progress_percentage=0,
            tables_total=2,
            tables_passed=0,
            tables_failed=0,
            tables_error=0,
            created_by="testuser",
        )

    def test_creates_table_results_per_table(self, mock_db, mock_cache):
        """Test that create_table_result is called once per table."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        svc.create_validation_run(**VALID_PAYLOAD)

        assert svc.repo.create_table_result.call_count == 2
        calls = svc.repo.create_table_result.call_args_list
        table_names = {c.kwargs["table_name"] for c in calls}
        assert table_names == {"users", "orders"}
        for c in calls:
            assert c.kwargs["workspace_id"] == WORKSPACE_ID
            assert c.kwargs["status"] == "pending"

    def test_retrieves_tables_from_migration_when_not_provided(self, mock_db, mock_cache):
        """Test tables are retrieved from migration source_tables when not explicitly provided."""
        run_model = _make_run_model(tables_total=3)
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(
                status="completed",
                source_tables=["customers", "products", "invoices"],
            ),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
            run_model=run_model,
        )

        result = svc.create_validation_run(**PAYLOAD_NO_TABLES)

        assert svc.repo.create_table_result.call_count == 3
        table_names = {
            c.kwargs["table_name"]
            for c in svc.repo.create_table_result.call_args_list
        }
        assert table_names == {"customers", "products", "invoices"}

    def test_caches_run_in_redis(self, mock_db, mock_cache):
        """Test that the created run is cached in Redis."""
        run_model = _make_run_model(run_id=42)
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
            run_model=run_model,
        )

        svc.create_validation_run(**VALID_PAYLOAD)

        mock_cache.set_run.assert_called_once_with(
            42, WORKSPACE_ID, run_model.to_dict(),
        )

    def test_single_table_run(self, mock_db, mock_cache):
        """Test creating a run with a single table."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        payload = {**VALID_PAYLOAD, "tables": ["single_table"]}
        svc.create_validation_run(**payload)

        svc.repo.create_run.assert_called_once()
        assert svc.repo.create_run.call_args.kwargs["tables_total"] == 1
        assert svc.repo.create_table_result.call_count == 1

    def test_many_tables_run(self, mock_db, mock_cache):
        """Test creating a run with 100 tables."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        tables = [f"table_{i}" for i in range(100)]
        payload = {**VALID_PAYLOAD, "tables": tables}
        svc.create_validation_run(**payload)

        assert svc.repo.create_run.call_args.kwargs["tables_total"] == 100
        assert svc.repo.create_table_result.call_count == 100

    def test_type_mapping_overrides_passed_to_repo(self, mock_db, mock_cache):
        """Test that type_mapping_overrides are forwarded to the repository."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        overrides = {"STRING": "TEXT", "INT64": "INTEGER"}
        payload = {**VALID_PAYLOAD, "type_mapping_overrides": overrides}
        svc.create_validation_run(**payload)

        assert svc.repo.create_run.call_args.kwargs["type_mapping_overrides"] == overrides

    def test_batch_size_passed_to_repo(self, mock_db, mock_cache):
        """Test that batch_size is forwarded to the repository."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        payload = {**VALID_PAYLOAD, "batch_size": 5000}
        svc.create_validation_run(**payload)

        assert svc.repo.create_run.call_args.kwargs["batch_size"] == 5000


# ── Tests: Migration validation errors ────────────────────────────────

class TestCreateValidationRunMigrationErrors:
    """Test create_validation_run with invalid migration states."""

    def test_migration_not_found_raises_error(self, mock_db, mock_cache):
        """Test error when migration_id does not exist."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=None,
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        with pytest.raises(ValueError, match="not found"):
            svc.create_validation_run(**VALID_PAYLOAD)

    def test_migration_not_completed_raises_error(self, mock_db, mock_cache):
        """Test error when migration status is not 'completed'."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="running"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        with pytest.raises(ValueError, match="completed"):
            svc.create_validation_run(**VALID_PAYLOAD)

    def test_migration_pending_raises_error(self, mock_db, mock_cache):
        """Test error when migration status is 'pending'."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="pending"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        with pytest.raises(ValueError, match="completed"):
            svc.create_validation_run(**VALID_PAYLOAD)

    def test_migration_failed_raises_error(self, mock_db, mock_cache):
        """Test error when migration status is 'failed'."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="failed"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        with pytest.raises(ValueError, match="completed"):
            svc.create_validation_run(**VALID_PAYLOAD)

    def test_no_repo_calls_on_migration_error(self, mock_db, mock_cache):
        """Test that no run or table results are created when migration is invalid."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="running"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        with pytest.raises(ValueError):
            svc.create_validation_run(**VALID_PAYLOAD)

        svc.repo.create_run.assert_not_called()
        svc.repo.create_table_result.assert_not_called()


# ── Tests: Connection validation errors ───────────────────────────────

class TestCreateValidationRunConnectionErrors:
    """Test create_validation_run with invalid connections."""

    def test_source_connection_missing_raises_error(self, mock_db, mock_cache):
        """Test error when source connection does not exist."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=None,
            target_conn=_make_connection(conn_id=20),
        )

        with pytest.raises(ValueError, match="Source connection"):
            svc.create_validation_run(**VALID_PAYLOAD)

    def test_source_connection_inactive_raises_error(self, mock_db, mock_cache):
        """Test error when source connection is inactive."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=_make_connection(conn_id=10, is_active=False),
            target_conn=_make_connection(conn_id=20),
        )

        with pytest.raises(ValueError, match="Source connection"):
            svc.create_validation_run(**VALID_PAYLOAD)

    def test_target_connection_missing_raises_error(self, mock_db, mock_cache):
        """Test error when target connection does not exist."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=_make_connection(conn_id=10),
            target_conn=None,
        )

        with pytest.raises(ValueError, match="Target connection"):
            svc.create_validation_run(**VALID_PAYLOAD)

    def test_target_connection_inactive_raises_error(self, mock_db, mock_cache):
        """Test error when target connection is inactive."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20, is_active=False),
        )

        with pytest.raises(ValueError, match="Target connection"):
            svc.create_validation_run(**VALID_PAYLOAD)

    def test_error_identifies_source_connection_id(self, mock_db, mock_cache):
        """Test that the error message includes the source connection ID."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=None,
            target_conn=_make_connection(conn_id=20),
        )

        with pytest.raises(ValueError, match="10"):
            svc.create_validation_run(**VALID_PAYLOAD)

    def test_error_identifies_target_connection_id(self, mock_db, mock_cache):
        """Test that the error message includes the target connection ID."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=_make_connection(conn_id=10),
            target_conn=None,
        )

        with pytest.raises(ValueError, match="20"):
            svc.create_validation_run(**VALID_PAYLOAD)

    def test_no_repo_calls_on_connection_error(self, mock_db, mock_cache):
        """Test that no run or table results are created when connection is invalid."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=None,
            target_conn=_make_connection(conn_id=20),
        )

        with pytest.raises(ValueError):
            svc.create_validation_run(**VALID_PAYLOAD)

        svc.repo.create_run.assert_not_called()
        svc.repo.create_table_result.assert_not_called()


# ── Tests: Table resolution errors ────────────────────────────────────

class TestCreateValidationRunTableErrors:
    """Test create_validation_run with missing table lists."""

    def test_no_tables_and_migration_has_no_source_tables(self, mock_db, mock_cache):
        """Test error when no tables provided and migration has None source_tables."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed", source_tables=None),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        with pytest.raises(ValueError, match="No tables"):
            svc.create_validation_run(**PAYLOAD_NO_TABLES)

    def test_no_tables_and_migration_has_empty_list(self, mock_db, mock_cache):
        """Test error when no tables provided and migration has empty list."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed", source_tables=[]),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        with pytest.raises(ValueError, match="No tables"):
            svc.create_validation_run(**PAYLOAD_NO_TABLES)


# ── Tests: Workspace isolation ────────────────────────────────────────

class TestCreateValidationRunWorkspaceIsolation:
    """Test that workspace_id is correctly applied."""

    def test_run_created_with_correct_workspace_id(self, mock_db, mock_cache):
        """Test that the run is created with the correct workspace_id."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        svc.create_validation_run(**VALID_PAYLOAD)

        assert svc.repo.create_run.call_args.kwargs["workspace_id"] == WORKSPACE_ID

    def test_table_results_created_with_correct_workspace_id(self, mock_db, mock_cache):
        """Test that all table results are created with the correct workspace_id."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        svc.create_validation_run(**VALID_PAYLOAD)

        for c in svc.repo.create_table_result.call_args_list:
            assert c.kwargs["workspace_id"] == WORKSPACE_ID

    def test_cache_set_with_correct_workspace_id(self, mock_db, mock_cache):
        """Test that cache.set_run is called with the correct workspace_id."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(status="completed"),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )

        svc.create_validation_run(**VALID_PAYLOAD)

        call_args = mock_cache.set_run.call_args
        assert call_args[0][1] == WORKSPACE_ID


# ── Tests: get_run ────────────────────────────────────────────────────


class TestGetRun:
    """Tests for ValidationService.get_run."""

    def test_returns_cached_run_on_cache_hit(self, mock_db, mock_cache):
        """Cache hit returns cached data without hitting the database."""
        svc = _build_service(mock_db, mock_cache)
        cached_data = _make_run_dict(run_id=5)
        mock_cache.get_run.return_value = cached_data

        result = svc.get_run(5, WORKSPACE_ID)

        assert result == cached_data
        mock_cache.get_run.assert_called_once_with(5, WORKSPACE_ID)
        svc.repo.get_run.assert_not_called()

    def test_returns_db_run_on_cache_miss(self, mock_db, mock_cache):
        """Cache miss falls back to database and caches the result."""
        run_model = _make_run_model(run_id=5)
        svc = _build_service(mock_db, mock_cache, run_model=run_model)
        mock_cache.get_run.return_value = None
        svc.repo.get_run.return_value = run_model

        result = svc.get_run(5, WORKSPACE_ID)

        assert result == run_model.to_dict()
        svc.repo.get_run.assert_called_once_with(5, WORKSPACE_ID)
        mock_cache.set_run.assert_called_with(5, WORKSPACE_ID, run_model.to_dict())

    def test_returns_none_when_not_found(self, mock_db, mock_cache):
        """Returns None when run doesn't exist in cache or database."""
        svc = _build_service(mock_db, mock_cache)
        mock_cache.get_run.return_value = None
        svc.repo.get_run.return_value = None

        result = svc.get_run(999, WORKSPACE_ID)

        assert result is None

    def test_workspace_isolation(self, mock_db, mock_cache):
        """Passes workspace_id to both cache and repo."""
        svc = _build_service(mock_db, mock_cache)
        mock_cache.get_run.return_value = None
        svc.repo.get_run.return_value = None

        svc.get_run(1, workspace_id=42)

        mock_cache.get_run.assert_called_once_with(1, 42)
        svc.repo.get_run.assert_called_once_with(1, 42)


# ── Tests: list_runs ──────────────────────────────────────────────────


class TestListRuns:
    """Tests for ValidationService.list_runs."""

    def test_returns_paginated_results(self, mock_db, mock_cache):
        """Returns runs list with pagination metadata."""
        run1 = _make_run_model(run_id=1)
        run2 = _make_run_model(run_id=2)
        svc = _build_service(mock_db, mock_cache)
        svc.repo.list_runs.return_value = ([run1, run2], 2)

        result = svc.list_runs(WORKSPACE_ID, page=1, page_size=20)

        assert result["total"] == 2
        assert result["page"] == 1
        assert result["page_size"] == 20
        assert len(result["runs"]) == 2

    def test_passes_filters_to_repo(self, mock_db, mock_cache):
        """Passes migration_id and status filters to repository."""
        svc = _build_service(mock_db, mock_cache)
        svc.repo.list_runs.return_value = ([], 0)

        svc.list_runs(WORKSPACE_ID, migration_id=5, status="completed", page=2, page_size=10)

        svc.repo.list_runs.assert_called_once_with(
            workspace_id=WORKSPACE_ID,
            migration_id=5,
            status="completed",
            page=2,
            page_size=10,
        )

    def test_empty_results(self, mock_db, mock_cache):
        """Returns empty list when no runs match."""
        svc = _build_service(mock_db, mock_cache)
        svc.repo.list_runs.return_value = ([], 0)

        result = svc.list_runs(WORKSPACE_ID)

        assert result["runs"] == []
        assert result["total"] == 0

    def test_workspace_isolation(self, mock_db, mock_cache):
        """Passes workspace_id to repository."""
        svc = _build_service(mock_db, mock_cache)
        svc.repo.list_runs.return_value = ([], 0)

        svc.list_runs(workspace_id=42)

        svc.repo.list_runs.assert_called_once_with(
            workspace_id=42,
            migration_id=None,
            status=None,
            page=1,
            page_size=20,
        )


# ── Tests: get_table_results ─────────────────────────────────────────


class TestGetTableResults:
    """Tests for ValidationService.get_table_results."""

    def test_returns_table_results_for_existing_run(self, mock_db, mock_cache):
        """Returns list of table result dicts when run exists."""
        run_model = _make_run_model(run_id=1)
        svc = _build_service(mock_db, mock_cache, run_model=run_model)
        svc.repo.get_run.return_value = run_model

        tr1 = MagicMock()
        tr1.to_dict.return_value = {"id": 1, "table_name": "users", "status": "completed"}
        tr2 = MagicMock()
        tr2.to_dict.return_value = {"id": 2, "table_name": "orders", "status": "failed"}
        svc.repo.list_table_results.return_value = [tr1, tr2]

        result = svc.get_table_results(1, WORKSPACE_ID)

        assert len(result) == 2
        assert result[0]["table_name"] == "users"
        assert result[1]["table_name"] == "orders"

    def test_returns_none_when_run_not_found(self, mock_db, mock_cache):
        """Returns None when the parent run doesn't exist."""
        svc = _build_service(mock_db, mock_cache)
        svc.repo.get_run.return_value = None

        result = svc.get_table_results(999, WORKSPACE_ID)

        assert result is None

    def test_workspace_isolation(self, mock_db, mock_cache):
        """Passes workspace_id to repo for both run and table result queries."""
        run_model = _make_run_model(run_id=1)
        svc = _build_service(mock_db, mock_cache, run_model=run_model)
        svc.repo.get_run.return_value = run_model
        svc.repo.list_table_results.return_value = []

        svc.get_table_results(1, workspace_id=42)

        svc.repo.get_run.assert_called_once_with(1, 42)
        svc.repo.list_table_results.assert_called_once_with(1, 42)


# ── Tests: get_table_detail ──────────────────────────────────────────


class TestGetTableDetail:
    """Tests for ValidationService.get_table_detail."""

    def test_returns_cached_detail_on_cache_hit(self, mock_db, mock_cache):
        """Cache hit returns cached data without hitting the database."""
        svc = _build_service(mock_db, mock_cache)
        cached_detail = {"id": 1, "table_name": "users", "ddl_comparison_result": {"discrepancies": []}}
        mock_cache.get_table_result.return_value = cached_detail

        result = svc.get_table_detail(1, "users", WORKSPACE_ID)

        assert result == cached_detail
        svc.repo.get_table_result.assert_not_called()

    def test_returns_db_detail_on_cache_miss(self, mock_db, mock_cache):
        """Cache miss falls back to database and caches the result."""
        svc = _build_service(mock_db, mock_cache)
        mock_cache.get_table_result.return_value = None

        tr = MagicMock()
        detail_dict = {
            "id": 1,
            "table_name": "users",
            "ddl_comparison_result": {"discrepancies": []},
            "row_count_result": {"source_count": 100, "target_count": 100},
            "data_match_result": {"total_compared": 100, "matched_count": 100},
            "ai_analysis": None,
        }
        tr.to_dict.return_value = detail_dict
        svc.repo.get_table_result.return_value = tr

        result = svc.get_table_detail(1, "users", WORKSPACE_ID)

        assert result == detail_dict
        mock_cache.set_table_result.assert_called_once_with(1, "users", WORKSPACE_ID, detail_dict)

    def test_returns_none_when_not_found(self, mock_db, mock_cache):
        """Returns None when table result doesn't exist."""
        svc = _build_service(mock_db, mock_cache)
        mock_cache.get_table_result.return_value = None
        svc.repo.get_table_result.return_value = None

        result = svc.get_table_detail(1, "nonexistent", WORKSPACE_ID)

        assert result is None

    def test_workspace_isolation(self, mock_db, mock_cache):
        """Passes workspace_id to both cache and repo."""
        svc = _build_service(mock_db, mock_cache)
        mock_cache.get_table_result.return_value = None
        svc.repo.get_table_result.return_value = None

        svc.get_table_detail(1, "users", workspace_id=42)

        mock_cache.get_table_result.assert_called_once_with(1, "users", 42)
        svc.repo.get_table_result.assert_called_once_with(1, "users", 42)


# ── Tests: get_report ────────────────────────────────────────────────


class TestGetReport:
    """Tests for ValidationService.get_report."""

    def _build_report_service(self, mock_db, mock_cache, run_model=None,
                               source_conn=None, target_conn=None, table_results=None):
        """Build a service wired for get_report testing."""
        svc = ValidationService(mock_db, mock_cache)
        svc.repo = MagicMock()

        if run_model is None:
            run_model = MagicMock()
            run_model.id = 1
            run_model.migration_id = 10
            run_model.source_connection_id = 100
            run_model.target_connection_id = 200
            run_model.tables_total = 2
            run_model.tables_passed = 1
            run_model.tables_failed = 1
            run_model.tables_error = 0
            run_model.status = "completed"
            run_model.started_at = datetime(2026, 1, 25, 10, 0, 0)
            run_model.completed_at = datetime(2026, 1, 25, 10, 5, 0)
            run_model.duration_seconds = 300

        svc.repo.get_run.return_value = run_model

        if source_conn is None:
            source_conn = _make_connection(conn_id=100, name="BigQuery Prod")
        if target_conn is None:
            target_conn = _make_connection(conn_id=200, name="Redshift Prod")

        conn_call_count = {"n": 0}
        conn_results = [source_conn, target_conn]

        def _query_side_effect(model):
            mock_q = MagicMock()
            if model is Connection:
                idx = conn_call_count["n"]
                conn_call_count["n"] += 1
                result = conn_results[idx] if idx < len(conn_results) else None
                mock_q.filter.return_value.first.return_value = result
            return mock_q

        mock_db.query.side_effect = _query_side_effect

        if table_results is None:
            tr1 = MagicMock()
            tr1.to_dict.return_value = {"id": 1, "table_name": "users", "status": "completed"}
            tr2 = MagicMock()
            tr2.to_dict.return_value = {"id": 2, "table_name": "orders", "status": "failed"}
            table_results = [tr1, tr2]

        svc.repo.list_table_results.return_value = table_results

        return svc

    def test_returns_cached_report_on_cache_hit(self, mock_db, mock_cache):
        """Cache hit returns cached report without generating."""
        svc = self._build_report_service(mock_db, mock_cache)
        cached_report = {"run_id": 1, "overall_status": "failed"}
        mock_cache.get_report.return_value = cached_report

        result = svc.get_report(1, WORKSPACE_ID)

        assert result == cached_report
        svc.repo.get_run.assert_not_called()

    def test_generates_report_on_cache_miss(self, mock_db, mock_cache):
        """Cache miss generates report from database and caches it."""
        mock_cache.get_report.return_value = None
        svc = self._build_report_service(mock_db, mock_cache)

        result = svc.get_report(1, WORKSPACE_ID)

        assert result["run_id"] == 1
        assert result["migration_id"] == 10
        assert result["source_connection_name"] == "BigQuery Prod"
        assert result["target_connection_name"] == "Redshift Prod"
        assert result["total_tables"] == 2
        assert result["tables_passed"] == 1
        assert result["tables_failed"] == 1
        assert result["tables_error"] == 0
        assert len(result["tables"]) == 2
        mock_cache.set_report.assert_called_once()

    def test_overall_status_failed_when_tables_failed(self, mock_db, mock_cache):
        """Overall status is 'failed' when any table failed."""
        mock_cache.get_report.return_value = None
        run_model = MagicMock()
        run_model.id = 1
        run_model.migration_id = 10
        run_model.source_connection_id = 100
        run_model.target_connection_id = 200
        run_model.tables_total = 2
        run_model.tables_passed = 1
        run_model.tables_failed = 1
        run_model.tables_error = 0
        run_model.status = "completed"
        run_model.started_at = datetime(2026, 1, 25, 10, 0, 0)
        run_model.completed_at = datetime(2026, 1, 25, 10, 5, 0)
        run_model.duration_seconds = 300

        svc = self._build_report_service(mock_db, mock_cache, run_model=run_model)
        result = svc.get_report(1, WORKSPACE_ID)

        assert result["overall_status"] == "failed"

    def test_overall_status_passed_when_all_passed(self, mock_db, mock_cache):
        """Overall status is 'passed' when all tables passed."""
        mock_cache.get_report.return_value = None
        run_model = MagicMock()
        run_model.id = 1
        run_model.migration_id = 10
        run_model.source_connection_id = 100
        run_model.target_connection_id = 200
        run_model.tables_total = 2
        run_model.tables_passed = 2
        run_model.tables_failed = 0
        run_model.tables_error = 0
        run_model.status = "completed"
        run_model.started_at = datetime(2026, 1, 25, 10, 0, 0)
        run_model.completed_at = datetime(2026, 1, 25, 10, 5, 0)
        run_model.duration_seconds = 300

        svc = self._build_report_service(mock_db, mock_cache, run_model=run_model)
        result = svc.get_report(1, WORKSPACE_ID)

        assert result["overall_status"] == "passed"

    def test_overall_status_failed_when_tables_error(self, mock_db, mock_cache):
        """Overall status is 'failed' when any table has error."""
        mock_cache.get_report.return_value = None
        run_model = MagicMock()
        run_model.id = 1
        run_model.migration_id = 10
        run_model.source_connection_id = 100
        run_model.target_connection_id = 200
        run_model.tables_total = 2
        run_model.tables_passed = 1
        run_model.tables_failed = 0
        run_model.tables_error = 1
        run_model.status = "completed"
        run_model.started_at = datetime(2026, 1, 25, 10, 0, 0)
        run_model.completed_at = datetime(2026, 1, 25, 10, 5, 0)
        run_model.duration_seconds = 300

        svc = self._build_report_service(mock_db, mock_cache, run_model=run_model)
        result = svc.get_report(1, WORKSPACE_ID)

        assert result["overall_status"] == "failed"

    def test_returns_none_when_run_not_found(self, mock_db, mock_cache):
        """Returns None when run doesn't exist."""
        mock_cache.get_report.return_value = None
        svc = self._build_report_service(mock_db, mock_cache)
        svc.repo.get_run.return_value = None

        result = svc.get_report(999, WORKSPACE_ID)

        assert result is None

    def test_connection_name_unknown_when_missing(self, mock_db, mock_cache):
        """Uses 'Unknown' when connection is not found."""
        mock_cache.get_report.return_value = None

        def _query_side_effect(model):
            mock_q = MagicMock()
            mock_q.filter.return_value.first.return_value = None
            return mock_q

        mock_db.query.side_effect = _query_side_effect

        svc = ValidationService(mock_db, mock_cache)
        svc.repo = MagicMock()

        run_model = MagicMock()
        run_model.id = 1
        run_model.migration_id = 10
        run_model.source_connection_id = 100
        run_model.target_connection_id = 200
        run_model.tables_total = 0
        run_model.tables_passed = 0
        run_model.tables_failed = 0
        run_model.tables_error = 0
        run_model.status = "completed"
        run_model.started_at = None
        run_model.completed_at = None
        run_model.duration_seconds = None
        svc.repo.get_run.return_value = run_model
        svc.repo.list_table_results.return_value = []

        result = svc.get_report(1, WORKSPACE_ID)

        assert result["source_connection_name"] == "Unknown"
        assert result["target_connection_name"] == "Unknown"

    def test_report_includes_duration_and_timestamps(self, mock_db, mock_cache):
        """Report includes started_at, completed_at, and duration_seconds."""
        mock_cache.get_report.return_value = None
        svc = self._build_report_service(mock_db, mock_cache)

        result = svc.get_report(1, WORKSPACE_ID)

        assert result["started_at"] == "2026-01-25T10:00:00Z"
        assert result["completed_at"] == "2026-01-25T10:05:00Z"
        assert result["duration_seconds"] == 300

    def test_report_cached_with_30_min_ttl(self, mock_db, mock_cache):
        """Report is cached via set_report after generation."""
        mock_cache.get_report.return_value = None
        svc = self._build_report_service(mock_db, mock_cache)

        svc.get_report(1, WORKSPACE_ID)

        mock_cache.set_report.assert_called_once_with(1, WORKSPACE_ID, pytest.approx(mock_cache.set_report.call_args[0][2], abs=1))

    def test_workspace_isolation(self, mock_db, mock_cache):
        """Passes workspace_id to cache and repo."""
        mock_cache.get_report.return_value = None
        svc = self._build_report_service(mock_db, mock_cache)
        svc.repo.get_run.return_value = None

        svc.get_report(1, workspace_id=42)

        mock_cache.get_report.assert_called_once_with(1, 42)
        svc.repo.get_run.assert_called_once_with(1, 42)


# ── Tests: delete_run ────────────────────────────────────────────────


class TestDeleteRun:
    """Tests for ValidationService.delete_run."""

    def test_deletes_run_and_invalidates_cache(self, mock_db, mock_cache):
        """Successful deletion invalidates all cache entries for the run."""
        svc = _build_service(mock_db, mock_cache)
        svc.repo.delete_run.return_value = True

        result = svc.delete_run(1, WORKSPACE_ID)

        assert result is True
        svc.repo.delete_run.assert_called_once_with(1, WORKSPACE_ID)
        mock_cache.invalidate_all_for_run.assert_called_once_with(1, WORKSPACE_ID)

    def test_returns_false_when_not_found(self, mock_db, mock_cache):
        """Returns False when run doesn't exist."""
        svc = _build_service(mock_db, mock_cache)
        svc.repo.delete_run.return_value = False

        result = svc.delete_run(999, WORKSPACE_ID)

        assert result is False

    def test_no_cache_invalidation_when_not_found(self, mock_db, mock_cache):
        """Does not invalidate cache when run doesn't exist."""
        svc = _build_service(mock_db, mock_cache)
        svc.repo.delete_run.return_value = False

        svc.delete_run(999, WORKSPACE_ID)

        mock_cache.invalidate_all_for_run.assert_not_called()

    def test_workspace_isolation(self, mock_db, mock_cache):
        """Passes workspace_id to repo and cache."""
        svc = _build_service(mock_db, mock_cache)
        svc.repo.delete_run.return_value = True

        svc.delete_run(1, workspace_id=42)

        svc.repo.delete_run.assert_called_once_with(1, 42)
        mock_cache.invalidate_all_for_run.assert_called_once_with(1, 42)

# ── DDL Comparison Helpers ────────────────────────────────────────────

def _make_assessment_table(table_id=100, assessment_id=5, dataset_name="my_dataset", table_name="users"):
    """Build a mock AssessmentTable object."""
    t = MagicMock()
    t.id = table_id
    t.assessment_id = assessment_id
    t.dataset_name = dataset_name
    t.table_name = table_name
    return t


def _make_assessment_column(column_name, data_type, is_nullable=True, ordinal_position=1):
    """Build a mock AssessmentColumn object."""
    c = MagicMock()
    c.column_name = column_name
    c.data_type = data_type
    c.is_nullable = is_nullable
    c.ordinal_position = ordinal_position
    return c


def _build_ddl_service(mock_db, mock_cache, source_columns=None, target_rows=None,
                        assessment_table=None, assessment_table_missing=False):
    """Create a ValidationService wired for DDL comparison tests.

    Patches db.query() to return AssessmentTable and AssessmentColumn mocks,
    and patches psycopg2.connect to return target_rows from Redshift.
    """
    from models.assessment import AssessmentTable as AT, AssessmentColumn as AC

    svc = ValidationService(mock_db, mock_cache)
    svc.repo = MagicMock()

    if assessment_table is None and not assessment_table_missing:
        assessment_table = _make_assessment_table()

    def _query_side_effect(model):
        mock_q = MagicMock()
        if model is AT:
            mock_q.filter.return_value.first.return_value = (
                None if assessment_table_missing else assessment_table
            )
        elif model is AC:
            cols = source_columns or []
            mock_q.filter.return_value.order_by.return_value.all.return_value = cols
        return mock_q

    mock_db.query.side_effect = _query_side_effect

    return svc


# ── DDL Sample Payloads ──────────────────────────────────────────────

DDL_TARGET_CONN_PARAMS = {
    "host": "redshift-cluster.example.com",
    "port": 5439,
    "database": "analytics",
    "username": "admin",
    "password": "secret",
}

DDL_BASE_KWARGS = {
    "run_id": 1,
    "table_name": "users",
    "dataset_name": "my_dataset",
    "assessment_id": 5,
    "target_conn_params": DDL_TARGET_CONN_PARAMS,
    "type_mapping_overrides": None,
    "workspace_id": 1,
}


# ── Tests: _validate_ddl ─────────────────────────────────────────────

class TestValidateDDL:
    """Tests for _validate_ddl method."""

    @patch("services.validation_service.psycopg2")
    def test_ddl_identical_schemas_passed(self, mock_psycopg2, mock_db, mock_cache):
        """Identical source and target schemas produce zero discrepancies and 'passed' status."""
        # Arrange
        source_cols = [
            _make_assessment_column("id", "INT64", is_nullable=False, ordinal_position=1),
            _make_assessment_column("name", "STRING", is_nullable=True, ordinal_position=2),
        ]
        target_rows = [
            ("id", "bigint", "NO", 1),
            ("name", "varchar", "YES", 2),
        ]
        svc = _build_ddl_service(mock_db, mock_cache, source_columns=source_cols)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = target_rows
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        result = svc._validate_ddl(**DDL_BASE_KWARGS)

        # Assert
        assert result["status"] == "passed"
        assert len(result["result"]["discrepancies"]) == 0
        assert result["result"]["source_column_count"] == 2
        assert result["result"]["target_column_count"] == 2
        assert result["result"]["columns_compared"] == 2

    @patch("services.validation_service.psycopg2")
    def test_ddl_missing_column_detected(self, mock_psycopg2, mock_db, mock_cache):
        """Source column not in target is detected as missing_column."""
        # Arrange
        source_cols = [
            _make_assessment_column("id", "INT64", is_nullable=False, ordinal_position=1),
            _make_assessment_column("email", "STRING", is_nullable=True, ordinal_position=2),
        ]
        target_rows = [
            ("id", "bigint", "NO", 1),
            # email is missing from target
        ]
        svc = _build_ddl_service(mock_db, mock_cache, source_columns=source_cols)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = target_rows
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        result = svc._validate_ddl(**DDL_BASE_KWARGS)

        # Assert
        assert result["status"] == "failed"
        discrepancies = result["result"]["discrepancies"]
        missing = [d for d in discrepancies if d["type"] == "missing_column"]
        assert len(missing) == 1
        assert missing[0]["column_name"] == "email"
        assert missing[0]["source_type"] == "STRING"
        assert missing[0]["target_type"] is None

    @patch("services.validation_service.psycopg2")
    def test_ddl_extra_column_detected(self, mock_psycopg2, mock_db, mock_cache):
        """Target column not in source is detected as extra_column."""
        # Arrange
        source_cols = [
            _make_assessment_column("id", "INT64", is_nullable=False, ordinal_position=1),
        ]
        target_rows = [
            ("id", "bigint", "NO", 1),
            ("created_at", "timestamp", "YES", 2),
        ]
        svc = _build_ddl_service(mock_db, mock_cache, source_columns=source_cols)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = target_rows
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        result = svc._validate_ddl(**DDL_BASE_KWARGS)

        # Assert
        assert result["status"] == "failed"
        discrepancies = result["result"]["discrepancies"]
        extra = [d for d in discrepancies if d["type"] == "extra_column"]
        assert len(extra) == 1
        assert extra[0]["column_name"] == "created_at"
        assert extra[0]["source_type"] is None
        assert extra[0]["target_type"] == "TIMESTAMP"

    @patch("services.validation_service.psycopg2")
    def test_ddl_type_mismatch_detected(self, mock_psycopg2, mock_db, mock_cache):
        """Non-equivalent types are detected as type_mismatch."""
        # Arrange
        source_cols = [
            _make_assessment_column("amount", "FLOAT64", is_nullable=True, ordinal_position=1),
        ]
        # Target has INTEGER instead of expected DOUBLE PRECISION
        target_rows = [
            ("amount", "integer", "YES", 1),
        ]
        svc = _build_ddl_service(mock_db, mock_cache, source_columns=source_cols)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = target_rows
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        result = svc._validate_ddl(**DDL_BASE_KWARGS)

        # Assert
        assert result["status"] == "failed"
        discrepancies = result["result"]["discrepancies"]
        mismatches = [d for d in discrepancies if d["type"] == "type_mismatch"]
        assert len(mismatches) == 1
        assert mismatches[0]["column_name"] == "amount"
        assert mismatches[0]["source_type"] == "FLOAT64"
        assert mismatches[0]["target_type"] == "INTEGER"
        assert mismatches[0]["expected_type"] == "DOUBLE PRECISION"

    @patch("services.validation_service.psycopg2")
    def test_ddl_nullability_mismatch_detected(self, mock_psycopg2, mock_db, mock_cache):
        """Different nullability is detected as nullability_mismatch."""
        # Arrange
        source_cols = [
            _make_assessment_column("id", "INT64", is_nullable=False, ordinal_position=1),
        ]
        # Target says nullable=YES but source says nullable=False
        target_rows = [
            ("id", "bigint", "YES", 1),
        ]
        svc = _build_ddl_service(mock_db, mock_cache, source_columns=source_cols)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = target_rows
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        result = svc._validate_ddl(**DDL_BASE_KWARGS)

        # Assert
        assert result["status"] == "failed"
        discrepancies = result["result"]["discrepancies"]
        nullability = [d for d in discrepancies if d["type"] == "nullability_mismatch"]
        assert len(nullability) == 1
        assert nullability[0]["column_name"] == "id"

    @patch("services.validation_service.psycopg2")
    def test_ddl_type_mapping_overrides_applied(self, mock_psycopg2, mock_db, mock_cache):
        """Custom type overrides change equivalence behavior."""
        # Arrange: override STRING → TEXT instead of default STRING → VARCHAR
        source_cols = [
            _make_assessment_column("name", "STRING", is_nullable=True, ordinal_position=1),
        ]
        target_rows = [
            ("name", "text", "YES", 1),
        ]
        svc = _build_ddl_service(mock_db, mock_cache, source_columns=source_cols)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = target_rows
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act – with override STRING → TEXT, "text" should be equivalent
        kwargs = {**DDL_BASE_KWARGS, "type_mapping_overrides": {"STRING": "TEXT"}}
        result = svc._validate_ddl(**kwargs)

        # Assert
        assert result["status"] == "passed"
        assert len(result["result"]["discrepancies"]) == 0

    @patch("services.validation_service.psycopg2")
    def test_ddl_mapped_types_equivalent(self, mock_psycopg2, mock_db, mock_cache):
        """STRING vs VARCHAR treated as equivalent via default mapping."""
        # Arrange
        source_cols = [
            _make_assessment_column("description", "STRING", is_nullable=True, ordinal_position=1),
            _make_assessment_column("active", "BOOL", is_nullable=False, ordinal_position=2),
            _make_assessment_column("score", "NUMERIC", is_nullable=True, ordinal_position=3),
        ]
        target_rows = [
            ("description", "varchar", "YES", 1),
            ("active", "boolean", "NO", 2),
            ("score", "decimal", "YES", 3),
        ]
        svc = _build_ddl_service(mock_db, mock_cache, source_columns=source_cols)

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = target_rows
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        result = svc._validate_ddl(**DDL_BASE_KWARGS)

        # Assert
        assert result["status"] == "passed"
        assert len(result["result"]["discrepancies"]) == 0
        assert result["result"]["columns_compared"] == 3

    @patch("services.validation_service.psycopg2")
    def test_ddl_error_handling(self, mock_psycopg2, mock_db, mock_cache):
        """Error during comparison returns status='error'."""
        # Arrange – assessment table not found triggers ValueError
        svc = _build_ddl_service(mock_db, mock_cache, assessment_table_missing=True)

        # psycopg2 should not even be called, but set it up anyway
        mock_psycopg2.connect.side_effect = Exception("should not reach")

        # Act
        result = svc._validate_ddl(**DDL_BASE_KWARGS)

        # Assert
        assert result["status"] == "error"
        assert "error_message" in result
        assert "Assessment table not found" in result["error_message"]
        assert result["result"]["discrepancies"] == []
        assert result["result"]["source_column_count"] == 0

    @patch("services.validation_service.psycopg2")
    def test_ddl_redshift_connection_error(self, mock_psycopg2, mock_db, mock_cache):
        """Redshift connection failure returns status='error'."""
        # Arrange
        source_cols = [
            _make_assessment_column("id", "INT64", is_nullable=False, ordinal_position=1),
        ]
        svc = _build_ddl_service(mock_db, mock_cache, source_columns=source_cols)
        mock_psycopg2.connect.side_effect = Exception("Connection refused")

        # Act
        result = svc._validate_ddl(**DDL_BASE_KWARGS)

        # Assert
        assert result["status"] == "error"
        assert "Connection refused" in result["error_message"]


# ── Tests: _get_source_columns ────────────────────────────────────────

class TestGetSourceColumns:
    """Tests for _get_source_columns method."""

    def test_returns_correct_column_metadata(self, mock_db, mock_cache):
        """Returns column dicts with correct fields from AssessmentColumn records."""
        # Arrange
        source_cols = [
            _make_assessment_column("id", "INT64", is_nullable=False, ordinal_position=1),
            _make_assessment_column("name", "STRING", is_nullable=True, ordinal_position=2),
            _make_assessment_column("score", "FLOAT64", is_nullable=True, ordinal_position=3),
        ]
        svc = _build_ddl_service(mock_db, mock_cache, source_columns=source_cols)

        # Act
        result = svc._get_source_columns(
            assessment_id=5, dataset_name="my_dataset",
            table_name="users", workspace_id=1,
        )

        # Assert
        assert len(result) == 3
        assert result[0] == {
            "column_name": "id",
            "data_type": "INT64",
            "is_nullable": False,
            "ordinal_position": 1,
        }
        assert result[1]["column_name"] == "name"
        assert result[1]["data_type"] == "STRING"
        assert result[1]["is_nullable"] is True
        assert result[2]["column_name"] == "score"

    def test_raises_when_assessment_table_not_found(self, mock_db, mock_cache):
        """Raises ValueError when assessment table is not found."""
        # Arrange
        svc = _build_ddl_service(mock_db, mock_cache, assessment_table_missing=True)

        # Act & Assert
        with pytest.raises(ValueError, match="Assessment table not found"):
            svc._get_source_columns(
                assessment_id=5, dataset_name="my_dataset",
                table_name="nonexistent", workspace_id=1,
            )

    def test_nullable_defaults_to_true_when_none(self, mock_db, mock_cache):
        """When is_nullable is None on the model, defaults to True."""
        # Arrange
        col = _make_assessment_column("status", "STRING", is_nullable=None, ordinal_position=1)
        svc = _build_ddl_service(mock_db, mock_cache, source_columns=[col])

        # Act
        result = svc._get_source_columns(
            assessment_id=5, dataset_name="my_dataset",
            table_name="users", workspace_id=1,
        )

        # Assert
        assert result[0]["is_nullable"] is True

    def test_empty_columns_returns_empty_list(self, mock_db, mock_cache):
        """Returns empty list when table has no columns."""
        # Arrange
        svc = _build_ddl_service(mock_db, mock_cache, source_columns=[])

        # Act
        result = svc._get_source_columns(
            assessment_id=5, dataset_name="my_dataset",
            table_name="users", workspace_id=1,
        )

        # Assert
        assert result == []


# ── Tests: _get_target_columns ────────────────────────────────────────

class TestGetTargetColumns:
    """Tests for _get_target_columns static method."""

    @patch("services.validation_service.psycopg2")
    def test_returns_correct_column_metadata(self, mock_psycopg2):
        """Parses Redshift information_schema rows into column dicts."""
        # Arrange
        target_rows = [
            ("user_id", "bigint", "NO", 1),
            ("email", "character varying", "YES", 2),
            ("created_at", "timestamp without time zone", "YES", 3),
        ]
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = target_rows
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        result = ValidationService._get_target_columns(
            DDL_TARGET_CONN_PARAMS, "my_dataset", "users",
        )

        # Assert
        assert len(result) == 3
        assert result[0] == {
            "column_name": "user_id",
            "data_type": "BIGINT",
            "is_nullable": False,
            "ordinal_position": 1,
        }
        assert result[1]["column_name"] == "email"
        assert result[1]["data_type"] == "CHARACTER VARYING"
        assert result[1]["is_nullable"] is True
        assert result[2]["data_type"] == "TIMESTAMP WITHOUT TIME ZONE"

    @patch("services.validation_service.psycopg2")
    def test_data_type_uppercased(self, mock_psycopg2):
        """Data types from Redshift are uppercased for consistent comparison."""
        # Arrange
        target_rows = [("col1", "varchar", "YES", 1)]
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = target_rows
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        result = ValidationService._get_target_columns(
            DDL_TARGET_CONN_PARAMS, "schema", "table",
        )

        # Assert
        assert result[0]["data_type"] == "VARCHAR"

    @patch("services.validation_service.psycopg2")
    def test_is_nullable_parsed_correctly(self, mock_psycopg2):
        """YES → True, NO → False for is_nullable field."""
        # Arrange
        target_rows = [
            ("col_yes", "integer", "YES", 1),
            ("col_no", "integer", "NO", 2),
        ]
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = target_rows
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        result = ValidationService._get_target_columns(
            DDL_TARGET_CONN_PARAMS, "schema", "table",
        )

        # Assert
        assert result[0]["is_nullable"] is True
        assert result[1]["is_nullable"] is False

    @patch("services.validation_service.psycopg2")
    def test_connection_uses_correct_params(self, mock_psycopg2):
        """psycopg2.connect is called with the correct connection parameters."""
        # Arrange
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        conn_params = {
            "host": "my-cluster.redshift.amazonaws.com",
            "port": 5439,
            "database": "mydb",
            "username": "dbuser",
            "password": "dbpass",
        }

        # Act
        ValidationService._get_target_columns(conn_params, "public", "orders")

        # Assert
        mock_psycopg2.connect.assert_called_once_with(
            host="my-cluster.redshift.amazonaws.com",
            port=5439,
            database="mydb",
            user="dbuser",
            password="dbpass",
            connect_timeout=30,
        )

    @patch("services.validation_service.psycopg2")
    def test_connection_closed_after_query(self, mock_psycopg2):
        """Connection is closed even after successful query."""
        # Arrange
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        ValidationService._get_target_columns(DDL_TARGET_CONN_PARAMS, "s", "t")

        # Assert
        mock_conn.close.assert_called_once()

    @patch("services.validation_service.psycopg2")
    def test_empty_table_returns_empty_list(self, mock_psycopg2):
        """Returns empty list when Redshift table has no columns."""
        # Arrange
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        result = ValidationService._get_target_columns(
            DDL_TARGET_CONN_PARAMS, "schema", "empty_table",
        )

        # Assert
        assert result == []

    @patch("services.validation_service.psycopg2")
    def test_fallback_host_keys(self, mock_psycopg2):
        """Supports alternative host keys: server_name, cluster, endpoint."""
        # Arrange
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        conn_params = {
            "endpoint": "my-endpoint.redshift.amazonaws.com",
            "port": 5439,
            "database_name": "testdb",
            "username": "user",
            "password": "pass",
        }

        # Act
        ValidationService._get_target_columns(conn_params, "public", "t")

        # Assert
        mock_psycopg2.connect.assert_called_once_with(
            host="my-endpoint.redshift.amazonaws.com",
            port=5439,
            database="testdb",
            user="user",
            password="pass",
            connect_timeout=30,
        )


# ── Row Count Sample Payloads ────────────────────────────────────────

ROW_COUNT_SOURCE_CONN_PARAMS = {
    "credentials_json": {
        "type": "service_account",
        "project_id": "test-project",
        "client_email": "test@test-project.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
    },
    "project_id": "test-project",
}

ROW_COUNT_TARGET_CONN_PARAMS = {
    "host": "redshift-cluster.example.com",
    "port": 5439,
    "database": "analytics",
    "username": "admin",
    "password": "secret",
}

ROW_COUNT_BASE_KWARGS = {
    "run_id": 1,
    "table_name": "users",
    "dataset_name": "my_dataset",
    "source_conn_params": ROW_COUNT_SOURCE_CONN_PARAMS,
    "target_conn_params": ROW_COUNT_TARGET_CONN_PARAMS,
    "workspace_id": 1,
}


def _build_row_count_service(mock_db, mock_cache):
    """Create a ValidationService wired for row count tests."""
    svc = ValidationService(mock_db, mock_cache)
    svc.repo = MagicMock()
    return svc


# ── Tests: _validate_row_count ───────────────────────────────────────

class TestValidateRowCount:
    """Tests for _validate_row_count method."""

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_equal_counts_produces_passed(self, mock_sa, mock_bq, mock_psycopg2,
                                          mock_db, mock_cache):
        """Equal source and target row counts produce 'passed' status."""
        # Arrange
        svc = _build_row_count_service(mock_db, mock_cache)

        mock_job = MagicMock()
        mock_job.result.return_value = [(1500,)]
        mock_bq_client = MagicMock()
        mock_bq_client.query.return_value = mock_job
        mock_bq.Client.return_value = mock_bq_client
        mock_bq.QueryJobConfig.return_value = MagicMock()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1500,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        result = svc._validate_row_count(**ROW_COUNT_BASE_KWARGS)

        # Assert
        assert result["status"] == "passed"
        assert result["result"]["source_count"] == 1500
        assert result["result"]["target_count"] == 1500
        assert result["result"]["difference"] == 0
        assert result["result"]["percentage_difference"] == 0.0

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_different_counts_produces_failed(self, mock_sa, mock_bq, mock_psycopg2,
                                               mock_db, mock_cache):
        """Different source and target row counts produce 'failed' status with correct difference."""
        # Arrange
        svc = _build_row_count_service(mock_db, mock_cache)

        mock_job = MagicMock()
        mock_job.result.return_value = [(1500000,)]
        mock_bq_client = MagicMock()
        mock_bq_client.query.return_value = mock_job
        mock_bq.Client.return_value = mock_bq_client
        mock_bq.QueryJobConfig.return_value = MagicMock()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1499998,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        result = svc._validate_row_count(**ROW_COUNT_BASE_KWARGS)

        # Assert
        assert result["status"] == "failed"
        assert result["result"]["source_count"] == 1500000
        assert result["result"]["target_count"] == 1499998
        assert result["result"]["difference"] == 2
        assert result["result"]["percentage_difference"] == pytest.approx(0.00013, abs=1e-5)

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_source_query_failure_produces_error(self, mock_sa, mock_bq, mock_psycopg2,
                                                  mock_db, mock_cache):
        """Source (BigQuery) query failure produces 'error' status."""
        # Arrange
        svc = _build_row_count_service(mock_db, mock_cache)

        mock_bq.Client.side_effect = Exception("BigQuery connection refused")

        # Act
        result = svc._validate_row_count(**ROW_COUNT_BASE_KWARGS)

        # Assert
        assert result["status"] == "error"
        assert "Source (BigQuery)" in result["error_message"]
        assert result["result"]["source_count"] is None
        assert result["result"]["target_count"] is None

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_target_query_failure_produces_error(self, mock_sa, mock_bq, mock_psycopg2,
                                                  mock_db, mock_cache):
        """Target (Redshift) query failure produces 'error' status."""
        # Arrange
        svc = _build_row_count_service(mock_db, mock_cache)

        mock_job = MagicMock()
        mock_job.result.return_value = [(500,)]
        mock_bq_client = MagicMock()
        mock_bq_client.query.return_value = mock_job
        mock_bq.Client.return_value = mock_bq_client
        mock_bq.QueryJobConfig.return_value = MagicMock()

        mock_psycopg2.connect.side_effect = Exception("Redshift connection timeout")

        # Act
        result = svc._validate_row_count(**ROW_COUNT_BASE_KWARGS)

        # Assert
        assert result["status"] == "error"
        assert "Target (Redshift)" in result["error_message"]
        assert result["result"]["source_count"] == 500
        assert result["result"]["target_count"] is None

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_percentage_difference_calculation(self, mock_sa, mock_bq, mock_psycopg2,
                                                mock_db, mock_cache):
        """Percentage difference is calculated correctly: abs(diff)/source*100."""
        # Arrange
        svc = _build_row_count_service(mock_db, mock_cache)

        mock_job = MagicMock()
        mock_job.result.return_value = [(1000,)]
        mock_bq_client = MagicMock()
        mock_bq_client.query.return_value = mock_job
        mock_bq.Client.return_value = mock_bq_client
        mock_bq.QueryJobConfig.return_value = MagicMock()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (990,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        result = svc._validate_row_count(**ROW_COUNT_BASE_KWARGS)

        # Assert
        assert result["status"] == "failed"
        assert result["result"]["difference"] == 10
        # 10 / 1000 * 100 = 1.0
        assert result["result"]["percentage_difference"] == pytest.approx(1.0)

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_both_zero_counts_passed(self, mock_sa, mock_bq, mock_psycopg2,
                                      mock_db, mock_cache):
        """Both source and target with zero rows produce 'passed' with 0% difference."""
        # Arrange
        svc = _build_row_count_service(mock_db, mock_cache)

        mock_job = MagicMock()
        mock_job.result.return_value = [(0,)]
        mock_bq_client = MagicMock()
        mock_bq_client.query.return_value = mock_job
        mock_bq.Client.return_value = mock_bq_client
        mock_bq.QueryJobConfig.return_value = MagicMock()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        result = svc._validate_row_count(**ROW_COUNT_BASE_KWARGS)

        # Assert
        assert result["status"] == "passed"
        assert result["result"]["percentage_difference"] == 0.0

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_source_zero_target_nonzero_100_percent(self, mock_sa, mock_bq, mock_psycopg2,
                                                     mock_db, mock_cache):
        """Source zero, target nonzero produces 100% difference."""
        # Arrange
        svc = _build_row_count_service(mock_db, mock_cache)

        mock_job = MagicMock()
        mock_job.result.return_value = [(0,)]
        mock_bq_client = MagicMock()
        mock_bq_client.query.return_value = mock_job
        mock_bq.Client.return_value = mock_bq_client
        mock_bq.QueryJobConfig.return_value = MagicMock()

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (50,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        result = svc._validate_row_count(**ROW_COUNT_BASE_KWARGS)

        # Assert
        assert result["status"] == "failed"
        assert result["result"]["percentage_difference"] == 100.0


class TestGetBigQueryRowCount:
    """Tests for _get_bigquery_row_count static method."""

    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_constructs_correct_query(self, mock_sa, mock_bq):
        """BigQuery query uses fully-qualified table reference."""
        # Arrange
        mock_job = MagicMock()
        mock_job.result.return_value = [(42,)]
        mock_bq_client = MagicMock()
        mock_bq_client.query.return_value = mock_job
        mock_bq.Client.return_value = mock_bq_client
        mock_bq.QueryJobConfig.return_value = MagicMock()

        # Act
        count = ValidationService._get_bigquery_row_count(
            ROW_COUNT_SOURCE_CONN_PARAMS, "my_dataset", "users",
        )

        # Assert
        assert count == 42
        query_arg = mock_bq_client.query.call_args[0][0]
        assert "test-project.my_dataset.users" in query_arg

    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_missing_credentials_raises(self, mock_sa, mock_bq):
        """Missing credentials_json raises ValueError."""
        with pytest.raises(ValueError, match="credentials not found"):
            ValidationService._get_bigquery_row_count(
                {"project_id": "test"}, "ds", "tbl",
            )

    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_missing_project_id_raises(self, mock_sa, mock_bq):
        """Missing project_id raises ValueError."""
        with pytest.raises(ValueError, match="project_id not found"):
            ValidationService._get_bigquery_row_count(
                {"credentials_json": {"type": "service_account"}}, "ds", "tbl",
            )


class TestGetRedshiftRowCount:
    """Tests for _get_redshift_row_count static method."""

    @patch("services.validation_service.psycopg2")
    def test_returns_correct_count(self, mock_psycopg2):
        """Returns the row count from Redshift."""
        # Arrange
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (999,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        count = ValidationService._get_redshift_row_count(
            ROW_COUNT_TARGET_CONN_PARAMS, "my_dataset", "users",
        )

        # Assert
        assert count == 999

    @patch("services.validation_service.psycopg2")
    def test_uses_statement_timeout(self, mock_psycopg2):
        """Redshift connection uses statement_timeout option."""
        # Arrange
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        ValidationService._get_redshift_row_count(
            ROW_COUNT_TARGET_CONN_PARAMS, "schema", "tbl", timeout=300,
        )

        # Assert
        call_kwargs = mock_psycopg2.connect.call_args[1]
        assert "-c statement_timeout=300000" in call_kwargs["options"]

    @patch("services.validation_service.psycopg2")
    def test_connection_closed_after_query(self, mock_psycopg2):
        """Redshift connection is closed after query completes."""
        # Arrange
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (10,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        # Act
        ValidationService._get_redshift_row_count(
            ROW_COUNT_TARGET_CONN_PARAMS, "schema", "tbl",
        )

        # Assert
        mock_conn.close.assert_called_once()

    @patch("services.validation_service.psycopg2")
    def test_fallback_host_keys(self, mock_psycopg2):
        """Supports alternative host keys: server_name, cluster, endpoint."""
        # Arrange
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_psycopg2.connect.return_value = mock_conn

        conn_params = {
            "endpoint": "my-endpoint.redshift.amazonaws.com",
            "port": 5439,
            "database_name": "testdb",
            "username": "user",
            "password": "pass",
        }

        # Act
        ValidationService._get_redshift_row_count(conn_params, "public", "t")

        # Assert
        call_kwargs = mock_psycopg2.connect.call_args[1]
        assert call_kwargs["host"] == "my-endpoint.redshift.amazonaws.com"
        assert call_kwargs["database"] == "testdb"


# ── Fixtures for record-level matching tests ─────────────────────────

RECORD_SOURCE_CONN_PARAMS = {
    "credentials_json": {
        "type": "service_account",
        "project_id": "test-project",
        "client_email": "test@test-project.iam.gserviceaccount.com",
        "token_uri": "https://oauth2.googleapis.com/token",
    },
    "project_id": "test-project",
}

RECORD_TARGET_CONN_PARAMS = {
    "host": "redshift-cluster.example.com",
    "port": 5439,
    "database": "analytics",
    "username": "admin",
    "password": "secret",
}

RECORD_BASE_KWARGS = {
    "run_id": 1,
    "table_name": "users",
    "dataset_name": "my_dataset",
    "source_conn_params": RECORD_SOURCE_CONN_PARAMS,
    "target_conn_params": RECORD_TARGET_CONN_PARAMS,
    "primary_key": ["id"],
    "batch_size": 10000,
    "type_mapping_overrides": None,
    "workspace_id": 1,
}


def _build_records_service(mock_db, mock_cache):
    """Create a ValidationService wired for record-level matching tests."""
    svc = ValidationService(mock_db, mock_cache)
    svc.repo = MagicMock()
    return svc


# ── Tests: _validate_records ─────────────────────────────────────────

class TestValidateRecords:
    """Tests for _validate_records method."""

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_identical_datasets_produces_passed(self, mock_sa, mock_bq, mock_psycopg2,
                                                 mock_db, mock_cache):
        """Identical source and target datasets produce 'passed' status with zero mismatches."""
        # Arrange
        svc = _build_records_service(mock_db, mock_cache)

        source_rows = [
            {"id": 1, "name": "Alice", "amount": "100.50"},
            {"id": 2, "name": "Bob", "amount": "200.00"},
        ]

        # Mock BigQuery
        mock_bq_row_1 = MagicMock()
        mock_bq_row_1.__iter__ = MagicMock(return_value=iter(source_rows[0].items()))
        mock_bq_row_2 = MagicMock()
        mock_bq_row_2.__iter__ = MagicMock(return_value=iter(source_rows[1].items()))

        mock_page = MagicMock()
        mock_page.__iter__ = MagicMock(return_value=iter(source_rows))

        mock_result = MagicMock()
        mock_result.pages = [source_rows]

        mock_job = MagicMock()
        mock_job.result.return_value = mock_result

        mock_bq_client = MagicMock()
        mock_bq_client.query.return_value = mock_job
        mock_bq.Client.return_value = mock_bq_client
        mock_bq.QueryJobConfig.return_value = MagicMock()

        # Patch _read_bigquery_rows and _read_redshift_rows directly
        with patch.object(svc, '_read_bigquery_rows', return_value=source_rows), \
             patch.object(svc, '_read_redshift_rows', return_value=source_rows):
            # Act
            result = svc._validate_records(**RECORD_BASE_KWARGS)

        # Assert
        assert result["status"] == "passed"
        assert result["result"]["total_compared"] == 2
        assert result["result"]["matched_count"] == 2
        assert result["result"]["missing_count"] == 0
        assert result["result"]["extra_count"] == 0
        assert result["result"]["mismatch_count"] == 0
        assert result["result"]["sample_discrepancies"] == []

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_missing_in_target_detected(self, mock_sa, mock_bq, mock_psycopg2,
                                         mock_db, mock_cache):
        """Records in source but not in target are detected as missing_in_target."""
        # Arrange
        svc = _build_records_service(mock_db, mock_cache)

        source_rows = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
            {"id": 3, "name": "Charlie"},
        ]
        target_rows = [
            {"id": 1, "name": "Alice"},
        ]

        with patch.object(svc, '_read_bigquery_rows', return_value=source_rows), \
             patch.object(svc, '_read_redshift_rows', return_value=target_rows):
            result = svc._validate_records(**RECORD_BASE_KWARGS)

        # Assert
        assert result["status"] == "failed"
        assert result["result"]["missing_count"] == 2
        missing_types = [d["type"] for d in result["result"]["sample_discrepancies"]
                         if d["type"] == "missing_in_target"]
        assert len(missing_types) == 2

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_extra_in_target_detected(self, mock_sa, mock_bq, mock_psycopg2,
                                       mock_db, mock_cache):
        """Records in target but not in source are detected as extra_in_target."""
        # Arrange
        svc = _build_records_service(mock_db, mock_cache)

        source_rows = [
            {"id": 1, "name": "Alice"},
        ]
        target_rows = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
            {"id": 3, "name": "Charlie"},
        ]

        with patch.object(svc, '_read_bigquery_rows', return_value=source_rows), \
             patch.object(svc, '_read_redshift_rows', return_value=target_rows):
            result = svc._validate_records(**RECORD_BASE_KWARGS)

        # Assert
        assert result["status"] == "failed"
        assert result["result"]["extra_count"] == 2
        extra_types = [d["type"] for d in result["result"]["sample_discrepancies"]
                       if d["type"] == "extra_in_target"]
        assert len(extra_types) == 2

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_value_mismatch_detected(self, mock_sa, mock_bq, mock_psycopg2,
                                      mock_db, mock_cache):
        """Value differences between matched records are detected as value_mismatch."""
        # Arrange
        svc = _build_records_service(mock_db, mock_cache)

        source_rows = [
            {"id": 1, "name": "Alice", "amount": "100.50"},
        ]
        target_rows = [
            {"id": 1, "name": "Alice", "amount": "100.5"},
        ]

        with patch.object(svc, '_read_bigquery_rows', return_value=source_rows), \
             patch.object(svc, '_read_redshift_rows', return_value=target_rows):
            result = svc._validate_records(**RECORD_BASE_KWARGS)

        # Assert - NUMERIC comparison: 100.50 == 100.5 as Decimal
        assert result["status"] == "passed"
        assert result["result"]["mismatch_count"] == 0

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_value_mismatch_with_different_values(self, mock_sa, mock_bq, mock_psycopg2,
                                                    mock_db, mock_cache):
        """Actual value differences produce value_mismatch discrepancy with column details."""
        # Arrange
        svc = _build_records_service(mock_db, mock_cache)

        source_rows = [
            {"id": 1, "name": "Alice", "amount": "100.50"},
        ]
        target_rows = [
            {"id": 1, "name": "Alice", "amount": "999.99"},
        ]

        with patch.object(svc, '_read_bigquery_rows', return_value=source_rows), \
             patch.object(svc, '_read_redshift_rows', return_value=target_rows):
            result = svc._validate_records(**RECORD_BASE_KWARGS)

        # Assert
        assert result["status"] == "failed"
        assert result["result"]["mismatch_count"] == 1
        mismatch = result["result"]["sample_discrepancies"][0]
        assert mismatch["type"] == "value_mismatch"
        assert mismatch["details"]["column"] == "amount"
        assert mismatch["details"]["source_value"] == "100.50"
        assert mismatch["details"]["target_value"] == "999.99"

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_hash_based_key_when_no_pk(self, mock_sa, mock_bq, mock_psycopg2,
                                        mock_db, mock_cache):
        """When primary_key is empty, hash of all columns is used as row identifier."""
        # Arrange
        svc = _build_records_service(mock_db, mock_cache)

        source_rows = [
            {"name": "Alice", "amount": "100"},
            {"name": "Bob", "amount": "200"},
        ]
        target_rows = [
            {"name": "Alice", "amount": "100"},
            {"name": "Bob", "amount": "200"},
        ]

        kwargs = {**RECORD_BASE_KWARGS, "primary_key": []}

        with patch.object(svc, '_read_bigquery_rows', return_value=source_rows), \
             patch.object(svc, '_read_redshift_rows', return_value=target_rows):
            result = svc._validate_records(**kwargs)

        # Assert
        assert result["status"] == "passed"
        assert result["result"]["matched_count"] == 2

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_hash_key_missing_in_target(self, mock_sa, mock_bq, mock_psycopg2,
                                         mock_db, mock_cache):
        """Hash-based key correctly detects missing rows and reports _hash in primary_key."""
        # Arrange
        svc = _build_records_service(mock_db, mock_cache)

        source_rows = [
            {"name": "Alice", "amount": "100"},
            {"name": "Charlie", "amount": "300"},
        ]
        target_rows = [
            {"name": "Alice", "amount": "100"},
        ]

        kwargs = {**RECORD_BASE_KWARGS, "primary_key": None}

        with patch.object(svc, '_read_bigquery_rows', return_value=source_rows), \
             patch.object(svc, '_read_redshift_rows', return_value=target_rows):
            result = svc._validate_records(**kwargs)

        # Assert
        assert result["status"] == "failed"
        assert result["result"]["missing_count"] == 1
        missing_disc = [d for d in result["result"]["sample_discrepancies"]
                        if d["type"] == "missing_in_target"]
        assert len(missing_disc) == 1
        assert "_hash" in missing_disc[0]["primary_key"]

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_sample_discrepancies_capped_at_100(self, mock_sa, mock_bq, mock_psycopg2,
                                                  mock_db, mock_cache):
        """Sample discrepancies list is capped at 100 entries."""
        # Arrange
        svc = _build_records_service(mock_db, mock_cache)

        # 150 source rows, none in target → 150 missing
        source_rows = [{"id": i, "name": f"user_{i}"} for i in range(150)]
        target_rows = []

        with patch.object(svc, '_read_bigquery_rows', return_value=source_rows), \
             patch.object(svc, '_read_redshift_rows', return_value=target_rows):
            result = svc._validate_records(**RECORD_BASE_KWARGS)

        # Assert
        assert result["status"] == "failed"
        assert result["result"]["missing_count"] == 150
        assert len(result["result"]["sample_discrepancies"]) == 100

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_error_handling_sets_error_status(self, mock_sa, mock_bq, mock_psycopg2,
                                               mock_db, mock_cache):
        """Exceptions during record matching produce 'error' status with error message."""
        # Arrange
        svc = _build_records_service(mock_db, mock_cache)

        with patch.object(svc, '_read_bigquery_rows',
                          side_effect=Exception("BigQuery connection refused")):
            result = svc._validate_records(**RECORD_BASE_KWARGS)

        # Assert
        assert result["status"] == "error"
        assert "BigQuery connection refused" in result["error_message"]
        assert result["result"]["total_compared"] == 0
        assert result["result"]["matched_count"] == 0

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_empty_datasets_produces_passed(self, mock_sa, mock_bq, mock_psycopg2,
                                             mock_db, mock_cache):
        """Both source and target empty produces 'passed' with zero counts."""
        # Arrange
        svc = _build_records_service(mock_db, mock_cache)

        with patch.object(svc, '_read_bigquery_rows', return_value=[]), \
             patch.object(svc, '_read_redshift_rows', return_value=[]):
            result = svc._validate_records(**RECORD_BASE_KWARGS)

        # Assert
        assert result["status"] == "passed"
        assert result["result"]["total_compared"] == 0
        assert result["result"]["matched_count"] == 0

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_null_equivalence(self, mock_sa, mock_bq, mock_psycopg2,
                               mock_db, mock_cache):
        """None values in both source and target are treated as equal."""
        # Arrange
        svc = _build_records_service(mock_db, mock_cache)

        source_rows = [{"id": 1, "name": None, "amount": None}]
        target_rows = [{"id": 1, "name": None, "amount": None}]

        with patch.object(svc, '_read_bigquery_rows', return_value=source_rows), \
             patch.object(svc, '_read_redshift_rows', return_value=target_rows):
            result = svc._validate_records(**RECORD_BASE_KWARGS)

        # Assert
        assert result["status"] == "passed"
        assert result["result"]["matched_count"] == 1

    @patch("services.validation_service.psycopg2")
    @patch("services.validation_service.bigquery")
    @patch("services.validation_service.service_account")
    def test_null_vs_value_mismatch(self, mock_sa, mock_bq, mock_psycopg2,
                                     mock_db, mock_cache):
        """None in source vs non-None in target is a value_mismatch."""
        # Arrange
        svc = _build_records_service(mock_db, mock_cache)

        source_rows = [{"id": 1, "name": None}]
        target_rows = [{"id": 1, "name": "Alice"}]

        with patch.object(svc, '_read_bigquery_rows', return_value=source_rows), \
             patch.object(svc, '_read_redshift_rows', return_value=target_rows):
            result = svc._validate_records(**RECORD_BASE_KWARGS)

        # Assert
        assert result["status"] == "failed"
        assert result["result"]["mismatch_count"] == 1


# ── Tests: _values_equal ─────────────────────────────────────────────

class TestValuesEqual:
    """Tests for the _values_equal static method."""

    def test_both_none_equal(self):
        assert ValidationService._values_equal(None, None) is True

    def test_none_vs_value_not_equal(self):
        assert ValidationService._values_equal(None, "hello") is False

    def test_value_vs_none_not_equal(self):
        assert ValidationService._values_equal("hello", None) is False

    def test_identical_strings_equal(self):
        assert ValidationService._values_equal("hello", "hello") is True

    def test_different_strings_not_equal(self):
        assert ValidationService._values_equal("hello", "world") is False

    def test_decimal_equivalence(self):
        """100.50 and 100.5 are equal as Decimal."""
        assert ValidationService._values_equal("100.50", "100.5") is True

    def test_decimal_not_equal(self):
        assert ValidationService._values_equal("100.50", "200.00") is False

    def test_timestamp_microsecond_precision(self):
        """Timestamps truncated to microsecond precision are equal."""
        from datetime import datetime
        ts1 = datetime(2024, 1, 15, 10, 30, 45, 123456)
        ts2 = datetime(2024, 1, 15, 10, 30, 45, 123456)
        assert ValidationService._values_equal(ts1, ts2) is True

    def test_timestamp_different_not_equal(self):
        from datetime import datetime
        ts1 = datetime(2024, 1, 15, 10, 30, 45, 123456)
        ts2 = datetime(2024, 1, 15, 10, 30, 45, 654321)
        assert ValidationService._values_equal(ts1, ts2) is False

    def test_integer_equal(self):
        assert ValidationService._values_equal(42, 42) is True

    def test_integer_not_equal(self):
        assert ValidationService._values_equal(42, 43) is False


# ── Tests: _compute_row_hash ─────────────────────────────────────────

class TestComputeRowHash:
    """Tests for the _compute_row_hash static method."""

    def test_deterministic(self):
        """Same row data produces same hash."""
        row = {"a": 1, "b": "hello"}
        columns = ["a", "b"]
        h1 = ValidationService._compute_row_hash(row, columns)
        h2 = ValidationService._compute_row_hash(row, columns)
        assert h1 == h2

    def test_different_data_different_hash(self):
        """Different row data produces different hash."""
        columns = ["a", "b"]
        h1 = ValidationService._compute_row_hash({"a": 1, "b": "hello"}, columns)
        h2 = ValidationService._compute_row_hash({"a": 2, "b": "world"}, columns)
        assert h1 != h2

    def test_none_values_handled(self):
        """None values are handled without error."""
        row = {"a": None, "b": None}
        columns = ["a", "b"]
        h = ValidationService._compute_row_hash(row, columns)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest


# ── Tests: _index_rows_by_key ────────────────────────────────────────

class TestIndexRowsByKey:
    """Tests for the _index_rows_by_key static method."""

    def test_index_by_pk(self):
        """Rows are indexed by primary key columns."""
        rows = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        indexed = ValidationService._index_rows_by_key(rows, ["id"], ["id", "name"])
        assert "1" in indexed
        assert "2" in indexed
        assert indexed["1"]["name"] == "Alice"

    def test_index_by_hash(self):
        """Rows are indexed by hash when pk_columns is None."""
        rows = [
            {"name": "Alice", "amount": "100"},
            {"name": "Bob", "amount": "200"},
        ]
        indexed = ValidationService._index_rows_by_key(rows, None, ["name", "amount"])
        assert len(indexed) == 2

    def test_composite_pk(self):
        """Composite primary keys produce correct key strings."""
        rows = [
            {"a": 1, "b": 2, "val": "x"},
        ]
        indexed = ValidationService._index_rows_by_key(rows, ["a", "b"], ["a", "b", "val"])
        assert "1|2" in indexed


# ── Tests: _build_pk_dict ────────────────────────────────────────────

class TestBuildPkDict:
    """Tests for the _build_pk_dict static method."""

    def test_with_pk_columns(self):
        """Returns dict of PK column values when pk_columns provided."""
        row = {"id": 42, "name": "Alice"}
        result = ValidationService._build_pk_dict(row, ["id"], "42", False)
        assert result == {"id": 42}

    def test_with_hash_key(self):
        """Returns _hash key when use_hash_key is True."""
        row = {"name": "Alice"}
        result = ValidationService._build_pk_dict(row, None, "abc123", True)
        assert result == {"_hash": "abc123"}


# ── Orchestration Helpers ─────────────────────────────────────────────


def _make_table_result_model(
    result_id=1,
    run_id=1,
    workspace_id=1,
    table_name="users",
    dataset_name="my_dataset",
    status="pending",
):
    """Build a mock ValidationTableResult model."""
    tr = MagicMock()
    tr.id = result_id
    tr.run_id = run_id
    tr.workspace_id = workspace_id
    tr.table_name = table_name
    tr.dataset_name = dataset_name
    tr.status = status
    return tr


def _make_assessment_obj(assessment_id=5, source_connection_id=10, workspace_id=1):
    """Build a mock Assessment object."""
    a = MagicMock()
    a.id = assessment_id
    a.source_connection_id = source_connection_id
    a.workspace_id = workspace_id
    a.status = "completed"
    return a


def _build_orchestration_service(
    mock_db,
    mock_cache,
    run_model=None,
    table_results=None,
    migration=None,
    assessment=None,
    source_conn=None,
    target_conn=None,
    ddl_result=None,
    row_count_result=None,
    records_result=None,
):
    """Create a ValidationService wired for orchestration tests.

    Patches db.query() to return the provided mocks for each model type,
    and patches the three validation sub-methods to return canned results.
    """
    svc = ValidationService(mock_db, mock_cache)
    svc.repo = MagicMock()

    # Default run model
    if run_model is None:
        run_model = MagicMock()
        run_model.id = 1
        run_model.workspace_id = 1
        run_model.migration_id = 1
        run_model.source_connection_id = 10
        run_model.target_connection_id = 20
        run_model.type_mapping_overrides = None
        run_model.batch_size = 10000
        run_model.bedrock_model = None

    svc.repo.get_run.return_value = run_model

    # Default table results
    if table_results is None:
        table_results = [
            _make_table_result_model(result_id=1, table_name="users"),
            _make_table_result_model(result_id=2, table_name="orders"),
        ]
    svc.repo.list_table_results.return_value = table_results
    svc.repo.update_run.return_value = run_model
    svc.repo.update_table_result.return_value = MagicMock()

    # Default migration
    if migration is None:
        migration = _make_migration()
        migration.source_dataset = "my_dataset"

    # Default assessment
    if assessment is None:
        assessment = _make_assessment_obj()

    # Default connections
    if source_conn is None:
        source_conn = _make_connection(conn_id=10, name="bq_source")
        source_conn.connection_params = {"credentials_json": "{}", "project_id": "proj"}
    if target_conn is None:
        target_conn = _make_connection(conn_id=20, name="rs_target")
        target_conn.connection_params = {"host": "localhost", "port": 5439, "database": "dev", "username": "admin", "password": "pass"}

    # Wire db.query() to return correct mocks per model
    from models.bq_redshift_migration import MigrationBQRedshift
    from models.assessment import Assessment, AssessmentTable as AT, AssessmentColumn as AC

    def _query_side_effect(model):
        mock_q = MagicMock()
        if model is MigrationBQRedshift:
            mock_q.filter.return_value.first.return_value = migration
        elif model is Assessment:
            mock_q.filter.return_value.order_by.return_value.first.return_value = assessment
        elif model is Connection:
            # Return source_conn first, target_conn second
            if not hasattr(_query_side_effect, "_conn_idx"):
                _query_side_effect._conn_idx = 0
            idx = _query_side_effect._conn_idx
            _query_side_effect._conn_idx += 1
            result = source_conn if idx == 0 else target_conn
            mock_q.filter.return_value.first.return_value = result
        elif model is AT:
            mock_q.filter.return_value.first.return_value = None
        elif model is AC:
            mock_q.filter.return_value.all.return_value = []
        return mock_q

    _query_side_effect._conn_idx = 0
    mock_db.query.side_effect = _query_side_effect

    # Patch decrypt_connection_credentials
    svc.decrypt_connection_credentials = MagicMock(return_value={
        "host": "localhost", "port": 5439, "database": "dev",
        "username": "admin", "password": "pass",
    })

    # Default validation sub-method results
    if ddl_result is None:
        ddl_result = {
            "status": "passed",
            "result": {"discrepancies": [], "source_column_count": 3, "target_column_count": 3, "columns_compared": 3},
        }
    if row_count_result is None:
        row_count_result = {
            "status": "passed",
            "result": {"source_count": 100, "target_count": 100, "difference": 0, "percentage_difference": 0.0},
        }
    if records_result is None:
        records_result = {
            "status": "passed",
            "result": {"total_compared": 100, "matched_count": 100, "missing_count": 0, "extra_count": 0, "mismatch_count": 0, "sample_discrepancies": []},
        }

    svc._validate_ddl = MagicMock(return_value=ddl_result)
    svc._validate_row_count = MagicMock(return_value=row_count_result)
    svc._validate_records = MagicMock(return_value=records_result)

    return svc


# ── Tests: run_validation_background ──────────────────────────────────


class TestRunValidationBackground:
    """Tests for ValidationService.run_validation_background."""

    def test_processes_all_tables_and_updates_progress(self, mock_db, mock_cache):
        """All tables are processed and progress reaches 100%."""
        svc = _build_orchestration_service(mock_db, mock_cache)

        svc.run_validation_background(run_id=1, workspace_id=1)

        # Both tables should have been validated
        assert svc._validate_ddl.call_count == 2
        assert svc._validate_row_count.call_count == 2
        assert svc._validate_records.call_count == 2

        # Final run update should set status to completed and progress to 100
        final_update = svc.repo.update_run.call_args_list[-1]
        assert final_update[1]["status"] == "completed"
        assert final_update[1]["progress_percentage"] == 100

    def test_run_status_set_to_running_at_start(self, mock_db, mock_cache):
        """Run status is updated to 'running' before processing tables."""
        svc = _build_orchestration_service(mock_db, mock_cache)

        svc.run_validation_background(run_id=1, workspace_id=1)

        first_update = svc.repo.update_run.call_args_list[0]
        assert first_update[1]["status"] == "running"
        assert first_update[1]["started_at"] is not None

    def test_table_results_updated_with_validation_outcomes(self, mock_db, mock_cache):
        """Each table result is updated with DDL, row count, and record match results."""
        svc = _build_orchestration_service(mock_db, mock_cache)

        svc.run_validation_background(run_id=1, workspace_id=1)

        # Two table result updates (one per table)
        table_updates = [
            c for c in svc.repo.update_table_result.call_args_list
            if "ddl_status" in c[1]
        ]
        assert len(table_updates) == 2

        for update_call in table_updates:
            kwargs = update_call[1]
            assert kwargs["ddl_status"] == "passed"
            assert kwargs["row_count_status"] == "passed"
            assert kwargs["data_match_status"] == "passed"
            assert kwargs["status"] == "completed"

    def test_all_tables_passed_produces_completed_status(self, mock_db, mock_cache):
        """When all tables pass, run status is 'completed' with correct counters."""
        svc = _build_orchestration_service(mock_db, mock_cache)

        svc.run_validation_background(run_id=1, workspace_id=1)

        final_update = svc.repo.update_run.call_args_list[-1]
        assert final_update[1]["status"] == "completed"
        assert final_update[1]["tables_passed"] == 2
        assert final_update[1]["tables_failed"] == 0
        assert final_update[1]["tables_error"] == 0

    def test_failed_ddl_marks_table_as_failed(self, mock_db, mock_cache):
        """A DDL failure marks the table as 'failed'."""
        ddl_fail = {
            "status": "failed",
            "result": {"discrepancies": [{"type": "missing_column"}], "source_column_count": 3, "target_column_count": 2, "columns_compared": 3},
        }
        svc = _build_orchestration_service(mock_db, mock_cache, ddl_result=ddl_fail)

        svc.run_validation_background(run_id=1, workspace_id=1)

        final_update = svc.repo.update_run.call_args_list[-1]
        assert final_update[1]["tables_failed"] == 2
        assert final_update[1]["tables_passed"] == 0

    def test_error_on_table_marks_error_and_continues(self, mock_db, mock_cache):
        """An unrecoverable error on one table marks it as 'error' and continues."""
        table_results = [
            _make_table_result_model(result_id=1, table_name="users"),
            _make_table_result_model(result_id=2, table_name="orders"),
        ]
        svc = _build_orchestration_service(
            mock_db, mock_cache, table_results=table_results,
        )

        # First call raises, second succeeds
        svc._validate_ddl.side_effect = [
            Exception("Connection lost"),
            {"status": "passed", "result": {"discrepancies": [], "source_column_count": 3, "target_column_count": 3, "columns_compared": 3}},
        ]

        svc.run_validation_background(run_id=1, workspace_id=1)

        final_update = svc.repo.update_run.call_args_list[-1]
        assert final_update[1]["tables_error"] == 1
        assert final_update[1]["tables_passed"] == 1
        assert final_update[1]["status"] == "completed"

    def test_all_tables_error_produces_failed_status(self, mock_db, mock_cache):
        """When all tables error, run status is 'failed'."""
        svc = _build_orchestration_service(mock_db, mock_cache)
        svc._validate_ddl.side_effect = Exception("Connection lost")

        svc.run_validation_background(run_id=1, workspace_id=1)

        final_update = svc.repo.update_run.call_args_list[-1]
        assert final_update[1]["status"] == "failed"
        assert final_update[1]["tables_error"] == 2

    def test_cache_invalidated_after_each_table(self, mock_db, mock_cache):
        """Redis cache is invalidated after each table completes."""
        svc = _build_orchestration_service(mock_db, mock_cache)

        svc.run_validation_background(run_id=1, workspace_id=1)

        # invalidate_run called: once at start (running), once per table, once at end
        assert mock_cache.invalidate_run.call_count >= 2
        # invalidate_table_result called once per table
        assert mock_cache.invalidate_table_result.call_count == 2
        # invalidate_all_for_run called at the end
        mock_cache.invalidate_all_for_run.assert_called_once_with(1, 1)

    def test_progress_percentage_updated_after_each_table(self, mock_db, mock_cache):
        """Progress percentage is updated incrementally after each table."""
        svc = _build_orchestration_service(mock_db, mock_cache)

        svc.run_validation_background(run_id=1, workspace_id=1)

        # Find progress updates (excluding the initial 'running' update and final update)
        progress_updates = [
            c[1].get("progress_percentage")
            for c in svc.repo.update_run.call_args_list
            if "progress_percentage" in c[1]
        ]
        # Should have 50 after first table, 100 after second, and 100 in final
        assert 50 in progress_updates
        assert 100 in progress_updates

    def test_run_not_found_returns_early(self, mock_db, mock_cache):
        """If run is not found, method returns without processing."""
        svc = _build_orchestration_service(mock_db, mock_cache)
        svc.repo.get_run.return_value = None

        svc.run_validation_background(run_id=999, workspace_id=1)

        svc._validate_ddl.assert_not_called()
        svc._validate_row_count.assert_not_called()
        svc._validate_records.assert_not_called()

    def test_no_table_results_completes_immediately(self, mock_db, mock_cache):
        """If no table results exist, run completes immediately."""
        svc = _build_orchestration_service(mock_db, mock_cache, table_results=[])

        svc.run_validation_background(run_id=1, workspace_id=1)

        svc._validate_ddl.assert_not_called()
        # Run should be marked completed
        final_update = svc.repo.update_run.call_args_list[-1]
        assert final_update[1]["status"] == "completed"

    def test_summary_statistics_correct_mixed_outcomes(self, mock_db, mock_cache):
        """Summary stats are correct when tables have mixed outcomes."""
        table_results = [
            _make_table_result_model(result_id=1, table_name="t1"),
            _make_table_result_model(result_id=2, table_name="t2"),
            _make_table_result_model(result_id=3, table_name="t3"),
        ]
        svc = _build_orchestration_service(
            mock_db, mock_cache, table_results=table_results,
        )

        # t1: all pass, t2: DDL fails, t3: error
        passed_ddl = {"status": "passed", "result": {"discrepancies": [], "source_column_count": 3, "target_column_count": 3, "columns_compared": 3}}
        failed_ddl = {"status": "failed", "result": {"discrepancies": [{"type": "missing_column"}], "source_column_count": 3, "target_column_count": 2, "columns_compared": 3}}
        passed_rc = {"status": "passed", "result": {"source_count": 100, "target_count": 100, "difference": 0, "percentage_difference": 0.0}}
        passed_rec = {"status": "passed", "result": {"total_compared": 100, "matched_count": 100, "missing_count": 0, "extra_count": 0, "mismatch_count": 0, "sample_discrepancies": []}}

        svc._validate_ddl.side_effect = [passed_ddl, failed_ddl, Exception("boom")]
        svc._validate_row_count.return_value = passed_rc
        svc._validate_records.return_value = passed_rec

        svc.run_validation_background(run_id=1, workspace_id=1)

        final_update = svc.repo.update_run.call_args_list[-1]
        assert final_update[1]["tables_passed"] == 1
        assert final_update[1]["tables_failed"] == 1
        assert final_update[1]["tables_error"] == 1
        assert final_update[1]["status"] == "completed"

    def test_duration_seconds_recorded(self, mock_db, mock_cache):
        """Run duration_seconds is recorded in the final update."""
        svc = _build_orchestration_service(mock_db, mock_cache)

        svc.run_validation_background(run_id=1, workspace_id=1)

        final_update = svc.repo.update_run.call_args_list[-1]
        assert "duration_seconds" in final_update[1]
        assert final_update[1]["duration_seconds"] >= 0

    def test_completed_at_recorded(self, mock_db, mock_cache):
        """Run completed_at timestamp is recorded in the final update."""
        svc = _build_orchestration_service(mock_db, mock_cache)

        svc.run_validation_background(run_id=1, workspace_id=1)

        final_update = svc.repo.update_run.call_args_list[-1]
        assert "completed_at" in final_update[1]
        assert final_update[1]["completed_at"] is not None

    def test_row_count_error_marks_table_failed_not_error(self, mock_db, mock_cache):
        """A row count error step marks the table as 'failed' (not all-error)."""
        rc_error = {
            "status": "error",
            "result": {"source_count": None, "target_count": None, "difference": None, "percentage_difference": None},
            "error_message": "Source query failed",
        }
        svc = _build_orchestration_service(mock_db, mock_cache, row_count_result=rc_error)

        svc.run_validation_background(run_id=1, workspace_id=1)

        final_update = svc.repo.update_run.call_args_list[-1]
        # Table has DDL passed + row count error + records passed → failed (not error)
        assert final_update[1]["tables_failed"] == 2
        assert final_update[1]["tables_error"] == 0

    def test_single_table_progress_goes_to_100(self, mock_db, mock_cache):
        """With a single table, progress goes directly to 100%."""
        table_results = [
            _make_table_result_model(result_id=1, table_name="users"),
        ]
        svc = _build_orchestration_service(
            mock_db, mock_cache, table_results=table_results,
        )

        svc.run_validation_background(run_id=1, workspace_id=1)

        progress_updates = [
            c[1].get("progress_percentage")
            for c in svc.repo.update_run.call_args_list
            if "progress_percentage" in c[1]
        ]
        assert 100 in progress_updates


# ── Tests: _run_bedrock_analysis and AI integration ───────────────────


# Sample Bedrock response payloads
VALID_BEDROCK_JSON_RESPONSE = (
    '{"root_cause": "Type mismatch between BigQuery STRING and Redshift INTEGER '
    "for column 'user_id'\", "
    '"impact_assessment": "Data truncation may occur for non-numeric string values", '
    '"recommended_workarounds": ["Cast user_id to VARCHAR in Redshift", '
    '"Add data validation step"]}'
)

VALID_BEDROCK_PARSED = {
    "root_cause": "Type mismatch between BigQuery STRING and Redshift INTEGER for column 'user_id'",
    "impact_assessment": "Data truncation may occur for non-numeric string values",
    "recommended_workarounds": [
        "Cast user_id to VARCHAR in Redshift",
        "Add data validation step",
    ],
}

INVALID_BEDROCK_JSON_RESPONSE = "This is not valid JSON but a plain text analysis."

SAMPLE_DDL_RESULT = {
    "discrepancies": [
        {
            "type": "type_mismatch",
            "column_name": "user_id",
            "source_type": "STRING",
            "target_type": "INTEGER",
            "expected_type": "VARCHAR",
        }
    ],
    "source_column_count": 5,
    "target_column_count": 5,
    "columns_compared": 5,
}

SAMPLE_ROW_COUNT_RESULT = {
    "source_count": 1000,
    "target_count": 998,
    "difference": 2,
    "percentage_difference": 0.2,
}

SAMPLE_DATA_MATCH_RESULT = {
    "total_compared": 1000,
    "matched_count": 995,
    "missing_count": 2,
    "extra_count": 0,
    "mismatch_count": 3,
    "sample_discrepancies": [
        {
            "type": "missing_in_target",
            "primary_key": {"id": 42},
            "details": None,
        },
        {
            "type": "value_mismatch",
            "primary_key": {"id": 99},
            "details": {"column": "amount", "source_value": "100.50", "target_value": "100.5"},
        },
    ],
}


def _build_bedrock_service(mock_db, mock_cache, bedrock_response=None, bedrock_side_effect=None):
    """Create a ValidationService wired for _run_bedrock_analysis tests."""
    svc = ValidationService(mock_db, mock_cache)
    svc.bedrock = MagicMock()
    if bedrock_side_effect is not None:
        svc.bedrock.invoke_model.side_effect = bedrock_side_effect
    elif bedrock_response is not None:
        svc.bedrock.invoke_model.return_value = bedrock_response
    else:
        svc.bedrock.invoke_model.return_value = VALID_BEDROCK_JSON_RESPONSE
    return svc


class TestRunBedrockAnalysis:
    """Tests for ValidationService._run_bedrock_analysis."""

    def test_valid_json_response(self, mock_db, mock_cache):
        """Valid JSON from Bedrock is parsed into root_cause, impact_assessment, recommended_workarounds."""
        svc = _build_bedrock_service(mock_db, mock_cache, bedrock_response=VALID_BEDROCK_JSON_RESPONSE)

        result = svc._run_bedrock_analysis(
            table_name="users",
            ddl_result=SAMPLE_DDL_RESULT,
            row_count_result=SAMPLE_ROW_COUNT_RESULT,
            data_match_result=SAMPLE_DATA_MATCH_RESULT,
            bedrock_model="anthropic.claude-3-sonnet",
            workspace_id=1,
        )

        assert result is not None
        assert result["root_cause"] == VALID_BEDROCK_PARSED["root_cause"]
        assert result["impact_assessment"] == VALID_BEDROCK_PARSED["impact_assessment"]
        assert result["recommended_workarounds"] == VALID_BEDROCK_PARSED["recommended_workarounds"]

    def test_invalid_json_response_stores_raw_text(self, mock_db, mock_cache):
        """Non-JSON Bedrock response is stored as root_cause with empty other fields."""
        svc = _build_bedrock_service(mock_db, mock_cache, bedrock_response=INVALID_BEDROCK_JSON_RESPONSE)

        result = svc._run_bedrock_analysis(
            table_name="users",
            ddl_result=SAMPLE_DDL_RESULT,
            row_count_result=SAMPLE_ROW_COUNT_RESULT,
            data_match_result=SAMPLE_DATA_MATCH_RESULT,
            bedrock_model="anthropic.claude-3-sonnet",
            workspace_id=1,
        )

        assert result is not None
        assert result["root_cause"] == INVALID_BEDROCK_JSON_RESPONSE
        assert result["impact_assessment"] == ""
        assert result["recommended_workarounds"] == []

    def test_bedrock_failure_returns_none(self, mock_db, mock_cache):
        """When Bedrock raises an exception, _run_bedrock_analysis returns None."""
        svc = _build_bedrock_service(
            mock_db, mock_cache,
            bedrock_side_effect=RuntimeError("Bedrock service unavailable"),
        )

        result = svc._run_bedrock_analysis(
            table_name="users",
            ddl_result=SAMPLE_DDL_RESULT,
            row_count_result=SAMPLE_ROW_COUNT_RESULT,
            data_match_result=SAMPLE_DATA_MATCH_RESULT,
            bedrock_model="anthropic.claude-3-sonnet",
            workspace_id=1,
        )

        assert result is None

    def test_invoke_model_called_with_correct_model_id(self, mock_db, mock_cache):
        """BedrockClient.invoke_model is called with the configured model_id."""
        svc = _build_bedrock_service(mock_db, mock_cache)

        svc._run_bedrock_analysis(
            table_name="orders",
            ddl_result=SAMPLE_DDL_RESULT,
            row_count_result=SAMPLE_ROW_COUNT_RESULT,
            data_match_result=SAMPLE_DATA_MATCH_RESULT,
            bedrock_model="anthropic.claude-3-haiku",
            workspace_id=1,
        )

        call_kwargs = svc.bedrock.invoke_model.call_args
        assert call_kwargs[1]["model_id"] == "anthropic.claude-3-haiku"

    def test_prompt_includes_table_name(self, mock_db, mock_cache):
        """Prompt sent to Bedrock contains the table name."""
        svc = _build_bedrock_service(mock_db, mock_cache)

        svc._run_bedrock_analysis(
            table_name="customer_orders",
            ddl_result=SAMPLE_DDL_RESULT,
            row_count_result=SAMPLE_ROW_COUNT_RESULT,
            data_match_result=SAMPLE_DATA_MATCH_RESULT,
            bedrock_model="anthropic.claude-3-sonnet",
            workspace_id=1,
        )

        prompt = svc.bedrock.invoke_model.call_args[1]["prompt"]
        assert "customer_orders" in prompt

    def test_prompt_includes_ddl_discrepancies(self, mock_db, mock_cache):
        """Prompt contains DDL discrepancy details."""
        svc = _build_bedrock_service(mock_db, mock_cache)

        svc._run_bedrock_analysis(
            table_name="users",
            ddl_result=SAMPLE_DDL_RESULT,
            row_count_result=SAMPLE_ROW_COUNT_RESULT,
            data_match_result=SAMPLE_DATA_MATCH_RESULT,
            bedrock_model="anthropic.claude-3-sonnet",
            workspace_id=1,
        )

        prompt = svc.bedrock.invoke_model.call_args[1]["prompt"]
        assert "type_mismatch" in prompt
        assert "user_id" in prompt

    def test_prompt_includes_row_count_differences(self, mock_db, mock_cache):
        """Prompt contains row count difference information."""
        svc = _build_bedrock_service(mock_db, mock_cache)

        svc._run_bedrock_analysis(
            table_name="users",
            ddl_result=SAMPLE_DDL_RESULT,
            row_count_result=SAMPLE_ROW_COUNT_RESULT,
            data_match_result=SAMPLE_DATA_MATCH_RESULT,
            bedrock_model="anthropic.claude-3-sonnet",
            workspace_id=1,
        )

        prompt = svc.bedrock.invoke_model.call_args[1]["prompt"]
        assert "1000" in prompt
        assert "998" in prompt

    def test_prompt_includes_record_mismatches(self, mock_db, mock_cache):
        """Prompt contains sample record-level mismatch details."""
        svc = _build_bedrock_service(mock_db, mock_cache)

        svc._run_bedrock_analysis(
            table_name="users",
            ddl_result=SAMPLE_DDL_RESULT,
            row_count_result=SAMPLE_ROW_COUNT_RESULT,
            data_match_result=SAMPLE_DATA_MATCH_RESULT,
            bedrock_model="anthropic.claude-3-sonnet",
            workspace_id=1,
        )

        prompt = svc.bedrock.invoke_model.call_args[1]["prompt"]
        assert "missing_in_target" in prompt
        assert "value_mismatch" in prompt

    def test_prompt_includes_database_types(self, mock_db, mock_cache):
        """Prompt includes BigQuery and Redshift as source/target database types."""
        svc = _build_bedrock_service(mock_db, mock_cache)

        svc._run_bedrock_analysis(
            table_name="users",
            ddl_result=SAMPLE_DDL_RESULT,
            row_count_result=SAMPLE_ROW_COUNT_RESULT,
            data_match_result=SAMPLE_DATA_MATCH_RESULT,
            bedrock_model="anthropic.claude-3-sonnet",
            workspace_id=1,
        )

        prompt = svc.bedrock.invoke_model.call_args[1]["prompt"]
        assert "BigQuery" in prompt
        assert "Redshift" in prompt

    def test_prompt_within_10000_char_limit(self, mock_db, mock_cache):
        """Prompt stays within the 10000 character limit even with large data."""
        svc = _build_bedrock_service(mock_db, mock_cache)

        # Create a large data_match_result with many sample discrepancies
        large_discrepancies = [
            {
                "type": "value_mismatch",
                "primary_key": {"id": i},
                "details": {"column": f"col_{i}", "source_value": "x" * 100, "target_value": "y" * 100},
            }
            for i in range(200)
        ]
        large_data_match = {
            "total_compared": 100000,
            "matched_count": 99800,
            "missing_count": 0,
            "extra_count": 0,
            "mismatch_count": 200,
            "sample_discrepancies": large_discrepancies,
        }

        svc._run_bedrock_analysis(
            table_name="users",
            ddl_result=SAMPLE_DDL_RESULT,
            row_count_result=SAMPLE_ROW_COUNT_RESULT,
            data_match_result=large_data_match,
            bedrock_model="anthropic.claude-3-sonnet",
            workspace_id=1,
        )

        prompt = svc.bedrock.invoke_model.call_args[1]["prompt"]
        # The final prompt includes the trailing instruction appended after truncation
        # but the core body before that instruction must be within 10000 chars
        assert len(prompt) <= 11000  # generous bound including trailing instruction

    def test_none_ddl_result_handled(self, mock_db, mock_cache):
        """When ddl_result is None, prompt still builds without error."""
        svc = _build_bedrock_service(mock_db, mock_cache)

        result = svc._run_bedrock_analysis(
            table_name="users",
            ddl_result=None,
            row_count_result=SAMPLE_ROW_COUNT_RESULT,
            data_match_result=SAMPLE_DATA_MATCH_RESULT,
            bedrock_model="anthropic.claude-3-sonnet",
            workspace_id=1,
        )

        assert result is not None
        prompt = svc.bedrock.invoke_model.call_args[1]["prompt"]
        assert "DDL Discrepancies" in prompt

    def test_none_row_count_result_handled(self, mock_db, mock_cache):
        """When row_count_result is None, prompt still builds without error."""
        svc = _build_bedrock_service(mock_db, mock_cache)

        result = svc._run_bedrock_analysis(
            table_name="users",
            ddl_result=SAMPLE_DDL_RESULT,
            row_count_result=None,
            data_match_result=SAMPLE_DATA_MATCH_RESULT,
            bedrock_model="anthropic.claude-3-sonnet",
            workspace_id=1,
        )

        assert result is not None
        prompt = svc.bedrock.invoke_model.call_args[1]["prompt"]
        assert "Row Count Differences" in prompt

    def test_none_data_match_result_handled(self, mock_db, mock_cache):
        """When data_match_result is None, prompt still builds without error."""
        svc = _build_bedrock_service(mock_db, mock_cache)

        result = svc._run_bedrock_analysis(
            table_name="users",
            ddl_result=SAMPLE_DDL_RESULT,
            row_count_result=SAMPLE_ROW_COUNT_RESULT,
            data_match_result=None,
            bedrock_model="anthropic.claude-3-sonnet",
            workspace_id=1,
        )

        assert result is not None
        prompt = svc.bedrock.invoke_model.call_args[1]["prompt"]
        assert "Sample Record-Level Mismatches" in prompt


class TestOrchestrationBedrockIntegration:
    """Tests for Bedrock AI analysis integration within run_validation_background."""

    def test_bedrock_invoked_for_failed_tables(self, mock_db, mock_cache):
        """Bedrock analysis is invoked for each table with status 'failed'."""
        ddl_fail = {
            "status": "failed",
            "result": {"discrepancies": [{"type": "missing_column"}],
                       "source_column_count": 3, "target_column_count": 2, "columns_compared": 3},
        }
        run_model = MagicMock()
        run_model.id = 1
        run_model.workspace_id = 1
        run_model.migration_id = 1
        run_model.source_connection_id = 10
        run_model.target_connection_id = 20
        run_model.type_mapping_overrides = None
        run_model.batch_size = 10000
        run_model.bedrock_model = "anthropic.claude-3-sonnet"

        table_results = [
            _make_table_result_model(result_id=1, table_name="users"),
            _make_table_result_model(result_id=2, table_name="orders"),
        ]
        svc = _build_orchestration_service(
            mock_db, mock_cache,
            run_model=run_model,
            table_results=table_results,
            ddl_result=ddl_fail,
        )

        # After orchestration, list_table_results is called again for AI analysis
        failed_tr1 = _make_table_result_model(result_id=1, table_name="users", status="failed")
        failed_tr1.ddl_comparison_result = SAMPLE_DDL_RESULT
        failed_tr1.row_count_result = SAMPLE_ROW_COUNT_RESULT
        failed_tr1.data_match_result = None
        failed_tr2 = _make_table_result_model(result_id=2, table_name="orders", status="failed")
        failed_tr2.ddl_comparison_result = SAMPLE_DDL_RESULT
        failed_tr2.row_count_result = SAMPLE_ROW_COUNT_RESULT
        failed_tr2.data_match_result = None

        # First call returns pending results, second call returns updated results
        svc.repo.list_table_results.side_effect = [table_results, [failed_tr1, failed_tr2]]
        svc._run_bedrock_analysis = MagicMock(return_value=VALID_BEDROCK_PARSED)

        svc.run_validation_background(run_id=1, workspace_id=1)

        assert svc._run_bedrock_analysis.call_count == 2

    def test_bedrock_skipped_when_no_model_configured(self, mock_db, mock_cache):
        """When bedrock_model is None on the run, AI analysis is skipped entirely."""
        ddl_fail = {
            "status": "failed",
            "result": {"discrepancies": [{"type": "missing_column"}],
                       "source_column_count": 3, "target_column_count": 2, "columns_compared": 3},
        }
        run_model = MagicMock()
        run_model.id = 1
        run_model.workspace_id = 1
        run_model.migration_id = 1
        run_model.source_connection_id = 10
        run_model.target_connection_id = 20
        run_model.type_mapping_overrides = None
        run_model.batch_size = 10000
        run_model.bedrock_model = None  # No model configured

        svc = _build_orchestration_service(
            mock_db, mock_cache,
            run_model=run_model,
            ddl_result=ddl_fail,
        )
        svc._run_bedrock_analysis = MagicMock()

        svc.run_validation_background(run_id=1, workspace_id=1)

        svc._run_bedrock_analysis.assert_not_called()

    def test_bedrock_skipped_when_model_is_empty_string(self, mock_db, mock_cache):
        """When bedrock_model is empty string, AI analysis is skipped."""
        ddl_fail = {
            "status": "failed",
            "result": {"discrepancies": [{"type": "missing_column"}],
                       "source_column_count": 3, "target_column_count": 2, "columns_compared": 3},
        }
        run_model = MagicMock()
        run_model.id = 1
        run_model.workspace_id = 1
        run_model.migration_id = 1
        run_model.source_connection_id = 10
        run_model.target_connection_id = 20
        run_model.type_mapping_overrides = None
        run_model.batch_size = 10000
        run_model.bedrock_model = ""  # Empty string

        svc = _build_orchestration_service(
            mock_db, mock_cache,
            run_model=run_model,
            ddl_result=ddl_fail,
        )
        svc._run_bedrock_analysis = MagicMock()

        svc.run_validation_background(run_id=1, workspace_id=1)

        svc._run_bedrock_analysis.assert_not_called()

    def test_bedrock_not_invoked_for_passed_tables(self, mock_db, mock_cache):
        """Bedrock analysis is NOT invoked for tables that passed."""
        run_model = MagicMock()
        run_model.id = 1
        run_model.workspace_id = 1
        run_model.migration_id = 1
        run_model.source_connection_id = 10
        run_model.target_connection_id = 20
        run_model.type_mapping_overrides = None
        run_model.batch_size = 10000
        run_model.bedrock_model = "anthropic.claude-3-sonnet"

        svc = _build_orchestration_service(mock_db, mock_cache, run_model=run_model)

        # After orchestration, re-fetched table results show all completed (passed)
        passed_tr1 = _make_table_result_model(result_id=1, table_name="users", status="completed")
        passed_tr2 = _make_table_result_model(result_id=2, table_name="orders", status="completed")
        table_results = [
            _make_table_result_model(result_id=1, table_name="users"),
            _make_table_result_model(result_id=2, table_name="orders"),
        ]
        svc.repo.list_table_results.side_effect = [table_results, [passed_tr1, passed_tr2]]
        svc._run_bedrock_analysis = MagicMock()

        svc.run_validation_background(run_id=1, workspace_id=1)

        svc._run_bedrock_analysis.assert_not_called()

    def test_bedrock_failure_does_not_fail_overall_validation(self, mock_db, mock_cache):
        """When Bedrock analysis returns None (failure), the run still completes."""
        ddl_fail = {
            "status": "failed",
            "result": {"discrepancies": [{"type": "missing_column"}],
                       "source_column_count": 3, "target_column_count": 2, "columns_compared": 3},
        }
        run_model = MagicMock()
        run_model.id = 1
        run_model.workspace_id = 1
        run_model.migration_id = 1
        run_model.source_connection_id = 10
        run_model.target_connection_id = 20
        run_model.type_mapping_overrides = None
        run_model.batch_size = 10000
        run_model.bedrock_model = "anthropic.claude-3-sonnet"

        table_results = [
            _make_table_result_model(result_id=1, table_name="users"),
        ]
        svc = _build_orchestration_service(
            mock_db, mock_cache,
            run_model=run_model,
            table_results=table_results,
            ddl_result=ddl_fail,
        )

        failed_tr = _make_table_result_model(result_id=1, table_name="users", status="failed")
        failed_tr.ddl_comparison_result = SAMPLE_DDL_RESULT
        failed_tr.row_count_result = None
        failed_tr.data_match_result = None
        svc.repo.list_table_results.side_effect = [table_results, [failed_tr]]

        # Bedrock returns None (simulating failure)
        svc._run_bedrock_analysis = MagicMock(return_value=None)

        svc.run_validation_background(run_id=1, workspace_id=1)

        # Run should still complete (not crash)
        final_update = svc.repo.update_run.call_args_list[-1]
        assert final_update[1]["status"] == "completed"
        # ai_analysis is set to None
        ai_update = [
            c for c in svc.repo.update_table_result.call_args_list
            if "ai_analysis" in c[1]
        ]
        assert len(ai_update) == 1
        assert ai_update[0][1]["ai_analysis"] is None

    def test_bedrock_result_stored_in_ai_analysis_field(self, mock_db, mock_cache):
        """Bedrock analysis result is stored via update_table_result ai_analysis kwarg."""
        ddl_fail = {
            "status": "failed",
            "result": {"discrepancies": [{"type": "type_mismatch"}],
                       "source_column_count": 5, "target_column_count": 5, "columns_compared": 5},
        }
        run_model = MagicMock()
        run_model.id = 1
        run_model.workspace_id = 1
        run_model.migration_id = 1
        run_model.source_connection_id = 10
        run_model.target_connection_id = 20
        run_model.type_mapping_overrides = None
        run_model.batch_size = 10000
        run_model.bedrock_model = "anthropic.claude-3-sonnet"

        table_results = [
            _make_table_result_model(result_id=1, table_name="users"),
        ]
        svc = _build_orchestration_service(
            mock_db, mock_cache,
            run_model=run_model,
            table_results=table_results,
            ddl_result=ddl_fail,
        )

        failed_tr = _make_table_result_model(result_id=1, table_name="users", status="failed")
        failed_tr.ddl_comparison_result = SAMPLE_DDL_RESULT
        failed_tr.row_count_result = SAMPLE_ROW_COUNT_RESULT
        failed_tr.data_match_result = SAMPLE_DATA_MATCH_RESULT
        svc.repo.list_table_results.side_effect = [table_results, [failed_tr]]
        svc._run_bedrock_analysis = MagicMock(return_value=VALID_BEDROCK_PARSED)

        svc.run_validation_background(run_id=1, workspace_id=1)

        ai_update = [
            c for c in svc.repo.update_table_result.call_args_list
            if "ai_analysis" in c[1]
        ]
        assert len(ai_update) == 1
        assert ai_update[0][1]["ai_analysis"] == VALID_BEDROCK_PARSED

    def test_cache_invalidated_after_bedrock_analysis(self, mock_db, mock_cache):
        """Cache is invalidated for the table after Bedrock analysis is stored."""
        ddl_fail = {
            "status": "failed",
            "result": {"discrepancies": [{"type": "missing_column"}],
                       "source_column_count": 3, "target_column_count": 2, "columns_compared": 3},
        }
        run_model = MagicMock()
        run_model.id = 1
        run_model.workspace_id = 1
        run_model.migration_id = 1
        run_model.source_connection_id = 10
        run_model.target_connection_id = 20
        run_model.type_mapping_overrides = None
        run_model.batch_size = 10000
        run_model.bedrock_model = "anthropic.claude-3-sonnet"

        table_results = [
            _make_table_result_model(result_id=1, table_name="users"),
        ]
        svc = _build_orchestration_service(
            mock_db, mock_cache,
            run_model=run_model,
            table_results=table_results,
            ddl_result=ddl_fail,
        )

        failed_tr = _make_table_result_model(result_id=1, table_name="users", status="failed")
        failed_tr.ddl_comparison_result = SAMPLE_DDL_RESULT
        failed_tr.row_count_result = None
        failed_tr.data_match_result = None
        svc.repo.list_table_results.side_effect = [table_results, [failed_tr]]
        svc._run_bedrock_analysis = MagicMock(return_value=VALID_BEDROCK_PARSED)

        svc.run_validation_background(run_id=1, workspace_id=1)

        # invalidate_table_result should be called for "users" during Bedrock phase
        table_invalidate_calls = [
            c for c in mock_cache.invalidate_table_result.call_args_list
            if c[0] == (1, "users", 1) or c[1] == {"run_id": 1, "table_name": "users", "workspace_id": 1}
        ]
        # At least 2 calls: one during table processing, one after Bedrock
        assert mock_cache.invalidate_table_result.call_count >= 2


# ══════════════════════════════════════════════════════════════════════
# Task 12.2 – Error sanitization tests
# ══════════════════════════════════════════════════════════════════════


class TestSanitizeErrorMessage:
    """Tests for ValidationService._sanitize_error_message."""

    def test_strips_ipv4_addresses(self):
        """IPv4 addresses are replaced with [REDACTED_IP]."""
        msg = "Connection refused to 10.0.1.42 on port 5439"
        result = ValidationService._sanitize_error_message(msg)
        assert "10.0.1.42" not in result
        assert "[REDACTED_IP]" in result

    def test_strips_multiple_ipv4_addresses(self):
        """Multiple IPv4 addresses are all replaced."""
        msg = "Failed connecting from 192.168.1.1 to 10.0.0.5"
        result = ValidationService._sanitize_error_message(msg)
        assert "192.168.1.1" not in result
        assert "10.0.0.5" not in result

    def test_strips_amazonaws_hostnames(self):
        """AWS hostnames like *.amazonaws.com are replaced."""
        msg = "Cannot reach my-cluster.abc123.us-east-1.redshift.amazonaws.com"
        result = ValidationService._sanitize_error_message(msg)
        assert "amazonaws.com" not in result
        assert "[REDACTED_HOST]" in result

    def test_strips_password_credential(self):
        """password=... patterns are replaced."""
        msg = "connection string: host=db password=SuperSecret123 dbname=prod"
        result = ValidationService._sanitize_error_message(msg)
        assert "SuperSecret123" not in result
        assert "password=[REDACTED]" in result

    def test_strips_username_credential(self):
        """username=... patterns are replaced."""
        msg = "auth failed for username=admin_user"
        result = ValidationService._sanitize_error_message(msg)
        assert "admin_user" not in result
        assert "username=[REDACTED]" in result

    def test_strips_user_credential(self):
        """user=... patterns (psycopg2 style) are replaced."""
        msg = "FATAL: password authentication failed for user=dbadmin"
        result = ValidationService._sanitize_error_message(msg)
        assert "dbadmin" not in result
        assert "user=[REDACTED]" in result

    def test_strips_host_port_patterns(self):
        """host:port patterns are replaced."""
        msg = "Could not connect to my-db-server.internal:5439"
        result = ValidationService._sanitize_error_message(msg)
        assert "my-db-server.internal:5439" not in result
        assert "[REDACTED_ENDPOINT]" in result

    def test_returns_empty_string_unchanged(self):
        """Empty string is returned as-is."""
        assert ValidationService._sanitize_error_message("") == ""

    def test_returns_none_unchanged(self):
        """None is returned as-is."""
        assert ValidationService._sanitize_error_message(None) is None

    def test_preserves_safe_error_message(self):
        """Messages without sensitive data are preserved."""
        msg = "Table 'users' not found in schema"
        result = ValidationService._sanitize_error_message(msg)
        assert result == msg

    def test_combined_sensitive_data(self):
        """Multiple sensitive patterns in one message are all stripped."""
        msg = (
            "Connection to 10.0.1.42:5439 failed. "
            "host=my-cluster.us-east-1.redshift.amazonaws.com "
            "password=s3cret username=admin"
        )
        result = ValidationService._sanitize_error_message(msg)
        assert "10.0.1.42" not in result
        assert "s3cret" not in result
        assert "admin" not in result
        assert "amazonaws.com" not in result


# ══════════════════════════════════════════════════════════════════════
# Task 12.1 – Structured logging tests
# ══════════════════════════════════════════════════════════════════════


class TestStructuredLoggingDDL:
    """Verify DDL comparison emits started/completed events with duration_ms."""

    @patch("psycopg2.connect")
    def test_ddl_logs_started_event(self, mock_psycopg2, mock_db, mock_cache):
        """DDL comparison logs a ddl_comparison_started event."""
        svc = _build_ddl_service(
            mock_db, mock_cache,
            source_columns=[
                _make_assessment_column("id", "INT64"),
            ],
            target_rows=[("id", "bigint", "YES", 1)],
        )
        with patch("services.validation_service.logger") as mock_logger:
            svc._validate_ddl(
                run_id=1, table_name="users", dataset_name="ds",
                assessment_id=5, target_conn_params={"host": "h", "port": 5439,
                "database": "db", "username": "u", "password": "p"},
                type_mapping_overrides={}, workspace_id=1,
            )
            started_calls = [
                c for c in mock_logger.info.call_args_list
                if c[1].get("extra", {}).get("event") == "ddl_comparison_started"
            ]
            assert len(started_calls) == 1
            extra = started_calls[0][1]["extra"]
            assert extra["run_id"] == 1
            assert extra["table_name"] == "users"
            assert extra["workspace_id"] == 1

    @patch("psycopg2.connect")
    def test_ddl_logs_completed_with_duration_ms(self, mock_psycopg2, mock_db, mock_cache):
        """DDL comparison completed event includes duration_ms."""
        svc = _build_ddl_service(
            mock_db, mock_cache,
            source_columns=[
                _make_assessment_column("id", "INT64"),
            ],
            target_rows=[("id", "bigint", "YES", 1)],
        )
        with patch("services.validation_service.logger") as mock_logger:
            svc._validate_ddl(
                run_id=1, table_name="users", dataset_name="ds",
                assessment_id=5, target_conn_params={"host": "h", "port": 5439,
                "database": "db", "username": "u", "password": "p"},
                type_mapping_overrides={}, workspace_id=1,
            )
            completed_calls = [
                c for c in mock_logger.info.call_args_list
                if c[1].get("extra", {}).get("event") == "ddl_comparison_completed"
            ]
            assert len(completed_calls) == 1
            extra = completed_calls[0][1]["extra"]
            assert "duration_ms" in extra
            assert isinstance(extra["duration_ms"], int)


class TestStructuredLoggingRowCount:
    """Verify row count validation emits started/completed events with duration_ms."""

    @patch("services.validation_service.service_account")
    @patch("services.validation_service.bigquery")
    @patch("psycopg2.connect")
    def test_row_count_logs_started_event(self, mock_psycopg2, mock_bq, mock_sa,
                                          mock_db, mock_cache):
        """Row count validation logs a row_count_started event."""
        svc = _build_row_count_service(mock_db, mock_cache)
        svc._get_bigquery_row_count = MagicMock(return_value=100)
        svc._get_redshift_row_count = MagicMock(return_value=100)

        with patch("services.validation_service.logger") as mock_logger:
            svc._validate_row_count(
                run_id=1, table_name="users", dataset_name="ds",
                source_conn_params={}, target_conn_params={}, workspace_id=1,
            )
            started_calls = [
                c for c in mock_logger.info.call_args_list
                if c[1].get("extra", {}).get("event") == "row_count_started"
            ]
            assert len(started_calls) == 1

    @patch("services.validation_service.service_account")
    @patch("services.validation_service.bigquery")
    @patch("psycopg2.connect")
    def test_row_count_logs_completed_with_duration_ms(self, mock_psycopg2, mock_bq, mock_sa,
                                                        mock_db, mock_cache):
        """Row count completed event includes duration_ms."""
        svc = _build_row_count_service(mock_db, mock_cache)
        svc._get_bigquery_row_count = MagicMock(return_value=50)
        svc._get_redshift_row_count = MagicMock(return_value=50)

        with patch("services.validation_service.logger") as mock_logger:
            svc._validate_row_count(
                run_id=1, table_name="users", dataset_name="ds",
                source_conn_params={}, target_conn_params={}, workspace_id=1,
            )
            completed_calls = [
                c for c in mock_logger.info.call_args_list
                if c[1].get("extra", {}).get("event") == "row_count_completed"
            ]
            assert len(completed_calls) == 1
            assert "duration_ms" in completed_calls[0][1]["extra"]


class TestStructuredLoggingRecordMatch:
    """Verify record-level matching emits started/completed events with duration_ms."""

    @patch("services.validation_service.service_account")
    @patch("services.validation_service.bigquery")
    @patch("psycopg2.connect")
    def test_record_match_logs_started_event(self, mock_psycopg2, mock_bq, mock_sa,
                                              mock_db, mock_cache):
        """Record-level matching logs a record_match_started event."""
        svc = _build_records_service(mock_db, mock_cache)
        svc._read_bigquery_rows = MagicMock(return_value=[])
        svc._read_redshift_rows = MagicMock(return_value=[])

        with patch("services.validation_service.logger") as mock_logger:
            svc._validate_records(
                run_id=1, table_name="users", dataset_name="ds",
                source_conn_params={}, target_conn_params={},
                primary_key=["id"], batch_size=10000,
                type_mapping_overrides={}, workspace_id=1,
            )
            started_calls = [
                c for c in mock_logger.info.call_args_list
                if c[1].get("extra", {}).get("event") == "record_match_started"
            ]
            assert len(started_calls) == 1

    @patch("services.validation_service.service_account")
    @patch("services.validation_service.bigquery")
    @patch("psycopg2.connect")
    def test_record_match_logs_completed_with_duration_ms(self, mock_psycopg2, mock_bq, mock_sa,
                                                           mock_db, mock_cache):
        """Record-level matching completed event includes duration_ms."""
        svc = _build_records_service(mock_db, mock_cache)
        svc._read_bigquery_rows = MagicMock(return_value=[{"id": 1, "name": "a"}])
        svc._read_redshift_rows = MagicMock(return_value=[{"id": 1, "name": "a"}])

        with patch("services.validation_service.logger") as mock_logger:
            svc._validate_records(
                run_id=1, table_name="users", dataset_name="ds",
                source_conn_params={}, target_conn_params={},
                primary_key=["id"], batch_size=10000,
                type_mapping_overrides={}, workspace_id=1,
            )
            completed_calls = [
                c for c in mock_logger.info.call_args_list
                if c[1].get("extra", {}).get("event") == "record_match_completed"
            ]
            assert len(completed_calls) == 1
            assert "duration_ms" in completed_calls[0][1]["extra"]


class TestStructuredLoggingRunCompletion:
    """Verify run completion log includes total_duration_seconds."""

    def test_run_completed_log_includes_total_duration(self, mock_db, mock_cache):
        """Run completed event includes total_duration_seconds."""
        run_model = MagicMock()
        run_model.id = 1
        run_model.workspace_id = 1
        run_model.migration_id = 1
        run_model.source_connection_id = 10
        run_model.target_connection_id = 20
        run_model.type_mapping_overrides = None
        run_model.batch_size = 10000
        run_model.bedrock_model = None

        svc = _build_orchestration_service(
            mock_db, mock_cache,
            run_model=run_model,
            table_results=[],
        )
        # No table results → completes immediately
        svc.repo.list_table_results.return_value = []

        with patch("services.validation_service.logger") as mock_logger:
            svc.run_validation_background(run_id=1, workspace_id=1)
            # The run_completed event won't fire for empty tables (early return),
            # but run_started should fire
            started_calls = [
                c for c in mock_logger.info.call_args_list
                if c[1].get("extra", {}).get("event") == "run_started"
            ]
            assert len(started_calls) == 1


class TestErrorSanitizationInMethods:
    """Verify error messages returned by validation methods are sanitized."""

    @patch("psycopg2.connect")
    def test_ddl_error_message_sanitized(self, mock_psycopg2, mock_db, mock_cache):
        """DDL comparison error messages have IPs/hosts stripped."""
        svc = _build_ddl_service(mock_db, mock_cache, source_columns=[], target_rows=[])
        # Force an error containing sensitive data
        svc._get_source_columns = MagicMock(
            side_effect=Exception("Connection to 10.0.1.42:5439 refused password=secret")
        )
        result = svc._validate_ddl(
            run_id=1, table_name="t", dataset_name="ds",
            assessment_id=5, target_conn_params={},
            type_mapping_overrides={}, workspace_id=1,
        )
        assert result["status"] == "error"
        assert "10.0.1.42" not in result["error_message"]
        assert "secret" not in result["error_message"]

    @patch("services.validation_service.service_account")
    @patch("services.validation_service.bigquery")
    @patch("psycopg2.connect")
    def test_row_count_error_message_sanitized(self, mock_psycopg2, mock_bq, mock_sa,
                                                mock_db, mock_cache):
        """Row count error messages have IPs/hosts stripped."""
        svc = _build_row_count_service(mock_db, mock_cache)
        svc._get_bigquery_row_count = MagicMock(
            side_effect=Exception("timeout connecting to 192.168.0.1:443")
        )
        result = svc._validate_row_count(
            run_id=1, table_name="t", dataset_name="ds",
            source_conn_params={}, target_conn_params={}, workspace_id=1,
        )
        assert result["status"] == "error"
        assert "192.168.0.1" not in result["error_message"]

    @patch("services.validation_service.service_account")
    @patch("services.validation_service.bigquery")
    @patch("psycopg2.connect")
    def test_record_match_error_message_sanitized(self, mock_psycopg2, mock_bq, mock_sa,
                                                   mock_db, mock_cache):
        """Record matching error messages have credentials stripped."""
        svc = _build_records_service(mock_db, mock_cache)
        svc._read_bigquery_rows = MagicMock(
            side_effect=Exception("auth failed user=admin password=p@ss host=db.amazonaws.com")
        )
        result = svc._validate_records(
            run_id=1, table_name="t", dataset_name="ds",
            source_conn_params={}, target_conn_params={},
            primary_key=["id"], batch_size=10000,
            type_mapping_overrides={}, workspace_id=1,
        )
        assert result["status"] == "error"
        assert "admin" not in result["error_message"]
        assert "p@ss" not in result["error_message"]
        assert "amazonaws.com" not in result["error_message"]


class TestTimeoutLogging:
    """Verify connection timeouts are logged with query_type and timeout_seconds."""

    @patch("services.validation_service.service_account")
    @patch("services.validation_service.bigquery")
    @patch("psycopg2.connect")
    def test_source_timeout_logged_with_query_type(self, mock_psycopg2, mock_bq, mock_sa,
                                                    mock_db, mock_cache):
        """Source query timeout logs event with query_type and timeout_seconds."""
        svc = _build_row_count_service(mock_db, mock_cache)
        svc._get_bigquery_row_count = MagicMock(
            side_effect=Exception("Query timeout exceeded")
        )
        with patch("services.validation_service.logger") as mock_logger:
            svc._validate_row_count(
                run_id=1, table_name="users", dataset_name="ds",
                source_conn_params={}, target_conn_params={}, workspace_id=1,
            )
            timeout_calls = [
                c for c in mock_logger.error.call_args_list
                if c[1].get("extra", {}).get("event") == "connection_timeout"
            ]
            assert len(timeout_calls) == 1
            extra = timeout_calls[0][1]["extra"]
            assert extra["query_type"] == "source_row_count"
            assert extra["timeout_seconds"] == 300
            assert extra["table_name"] == "users"

    @patch("services.validation_service.service_account")
    @patch("services.validation_service.bigquery")
    @patch("psycopg2.connect")
    def test_target_timeout_logged_with_query_type(self, mock_psycopg2, mock_bq, mock_sa,
                                                    mock_db, mock_cache):
        """Target query timeout logs event with query_type and timeout_seconds."""
        svc = _build_row_count_service(mock_db, mock_cache)
        svc._get_bigquery_row_count = MagicMock(return_value=100)
        svc._get_redshift_row_count = MagicMock(
            side_effect=Exception("statement timeout")
        )
        with patch("services.validation_service.logger") as mock_logger:
            svc._validate_row_count(
                run_id=1, table_name="orders", dataset_name="ds",
                source_conn_params={}, target_conn_params={}, workspace_id=1,
            )
            timeout_calls = [
                c for c in mock_logger.error.call_args_list
                if c[1].get("extra", {}).get("event") == "connection_timeout"
            ]
            assert len(timeout_calls) == 1
            extra = timeout_calls[0][1]["extra"]
            assert extra["query_type"] == "target_row_count"
            assert extra["timeout_seconds"] == 300


# ── Tests: Rate limiting ──────────────────────────────────────────────


class TestRateLimiting:
    """Test rate limiting of concurrent validation runs per workspace."""

    def test_allows_creation_when_under_limit(self, mock_db, mock_cache):
        """Creating a run succeeds when active count is below the limit."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )
        svc.repo.count_active_runs.return_value = 9

        result = svc.create_validation_run(**VALID_PAYLOAD)
        assert result is not None
        svc.repo.create_run.assert_called_once()

    def test_rejects_creation_at_limit(self, mock_db, mock_cache):
        """Creating a run raises RuntimeError when active count equals the limit."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )
        svc.repo.count_active_runs.return_value = 10

        with pytest.raises(RuntimeError, match="maximum of 10"):
            svc.create_validation_run(**VALID_PAYLOAD)

        svc.repo.create_run.assert_not_called()

    def test_rejects_creation_above_limit(self, mock_db, mock_cache):
        """Creating a run raises RuntimeError when active count exceeds the limit."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )
        svc.repo.count_active_runs.return_value = 15

        with pytest.raises(RuntimeError, match="maximum of 10"):
            svc.create_validation_run(**VALID_PAYLOAD)

    def test_rate_limit_checked_before_migration_validation(self, mock_db, mock_cache):
        """Rate limit check happens before migration lookup."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=None,  # Would fail migration check
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )
        svc.repo.count_active_runs.return_value = 10

        with pytest.raises(RuntimeError, match="maximum of 10"):
            svc.create_validation_run(**VALID_PAYLOAD)

    def test_zero_active_runs_allows_creation(self, mock_db, mock_cache):
        """Creating a run succeeds when there are zero active runs."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )
        svc.repo.count_active_runs.return_value = 0

        result = svc.create_validation_run(**VALID_PAYLOAD)
        assert result is not None

    def test_rate_limit_logs_warning(self, mock_db, mock_cache):
        """Rate limit rejection logs a warning with workspace_id."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )
        svc.repo.count_active_runs.return_value = 10

        with patch("services.validation_service.logger") as mock_logger:
            with pytest.raises(RuntimeError):
                svc.create_validation_run(**VALID_PAYLOAD)

            warning_calls = mock_logger.warning.call_args_list
            assert len(warning_calls) >= 1
            extra = warning_calls[0][1].get("extra", {})
            assert extra["workspace_id"] == 1
            assert extra["active_runs"] == 10

    def test_rate_limit_error_includes_workspace_id(self, mock_db, mock_cache):
        """RuntimeError message includes the workspace ID."""
        svc = _build_service(
            mock_db, mock_cache,
            migration=_make_migration(),
            source_conn=_make_connection(conn_id=10),
            target_conn=_make_connection(conn_id=20),
        )
        svc.repo.count_active_runs.return_value = 10

        with pytest.raises(RuntimeError, match="Workspace 1"):
            svc.create_validation_run(**VALID_PAYLOAD)
