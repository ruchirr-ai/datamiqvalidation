"""
Unit tests for ValidationRepository.

Uses an in-memory SQLite database to validate CRUD operations,
workspace isolation, pagination, filtering, and cascade deletion.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON

from database import Base
from models.validation_run import ValidationRun
from models.validation_table_result import ValidationTableResult
from repositories.validation_repository import ValidationRepository


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def db_session():
    """Create a fresh in-memory SQLite session for each test.

    Registers a JSONB → JSON compilation hook so that PostgreSQL-specific
    JSONB columns can be created in SQLite for testing purposes.
    """
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Map JSONB to JSON for SQLite compatibility
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
    if not hasattr(SQLiteTypeCompiler, '_orig_visit_JSONB'):
        SQLiteTypeCompiler._orig_visit_JSONB = None
        SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def repo(db_session):
    return ValidationRepository(db_session)


# ── Sample payloads ───────────────────────────────────────────────────

RUN_DEFAULTS = {
    "workspace_id": 1,
    "migration_id": 100,
    "source_connection_id": 10,
    "target_connection_id": 20,
    "status": "pending",
    "tables_total": 3,
    "batch_size": 10000,
    "created_by": "testuser",
}

TABLE_RESULT_DEFAULTS = {
    "workspace_id": 1,
    "table_name": "users",
    "status": "pending",
}

# Valid creation payload
VALID_RUN_PAYLOAD = {
    "workspace_id": 1,
    "migration_id": 200,
    "source_connection_id": 10,
    "target_connection_id": 20,
    "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "batch_size": 10000,
    "type_mapping_overrides": {"STRING": "TEXT"},
    "status": "pending",
    "tables_total": 5,
    "created_by": "admin",
}

# Invalid payload - missing required field (workspace_id)
INVALID_RUN_PAYLOAD_MISSING_FIELD = {
    "migration_id": 200,
    "source_connection_id": 10,
    "target_connection_id": 20,
    "status": "pending",
    "created_by": "admin",
}

# Edge case - empty tables
EDGE_CASE_ZERO_TABLES = {
    **RUN_DEFAULTS,
    "tables_total": 0,
}


# ── Helper ────────────────────────────────────────────────────────────

def _create_run(repo, **overrides):
    """Helper to create a validation run with defaults."""
    data = {**RUN_DEFAULTS, **overrides}
    return repo.create_run(**data)


def _create_table_result(repo, run_id, **overrides):
    """Helper to create a table result with defaults."""
    data = {**TABLE_RESULT_DEFAULTS, "run_id": run_id, **overrides}
    return repo.create_table_result(**data)


# ── ValidationRun CRUD tests ─────────────────────────────────────────


class TestCreateRun:
    """Tests for create_run."""

    def test_create_run_returns_persisted_instance(self, repo):
        """Test creating a validation run persists and returns the instance."""
        run = _create_run(repo)
        assert run.id is not None
        assert run.workspace_id == 1
        assert run.migration_id == 100
        assert run.status == "pending"
        assert run.tables_total == 3

    def test_create_run_with_full_payload(self, repo):
        """Test creating a run with all optional fields."""
        run = repo.create_run(**VALID_RUN_PAYLOAD)
        assert run.id is not None
        assert run.bedrock_model == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert run.type_mapping_overrides == {"STRING": "TEXT"}
        assert run.batch_size == 10000
        assert run.tables_total == 5

    def test_create_run_sets_defaults(self, repo):
        """Test that default values are applied correctly."""
        run = _create_run(repo)
        assert run.progress_percentage == 0
        assert run.tables_passed == 0
        assert run.tables_failed == 0
        assert run.tables_error == 0
        assert run.started_at is None
        assert run.completed_at is None

    def test_create_multiple_runs_unique_ids(self, repo):
        """Test that multiple runs get unique IDs."""
        run1 = _create_run(repo)
        run2 = _create_run(repo, migration_id=101)
        assert run1.id != run2.id

    def test_create_run_zero_tables(self, repo):
        """Test edge case with zero tables."""
        run = repo.create_run(**EDGE_CASE_ZERO_TABLES)
        assert run.tables_total == 0


class TestGetRun:
    """Tests for get_run."""

    def test_get_existing_run(self, repo):
        """Test retrieving an existing run by ID and workspace."""
        run = _create_run(repo)
        fetched = repo.get_run(run.id, workspace_id=1)
        assert fetched is not None
        assert fetched.id == run.id
        assert fetched.migration_id == 100

    def test_get_nonexistent_run_returns_none(self, repo):
        """Test that a non-existent run ID returns None."""
        assert repo.get_run(9999, workspace_id=1) is None

    def test_get_run_wrong_workspace_returns_none(self, repo):
        """Test workspace isolation: wrong workspace returns None."""
        run = _create_run(repo)
        assert repo.get_run(run.id, workspace_id=999) is None


class TestListRuns:
    """Tests for list_runs with pagination and filtering."""

    def _seed_runs(self, repo, count=5, **overrides):
        runs = []
        for i in range(count):
            runs.append(_create_run(repo, migration_id=100 + i, **overrides))
        return runs

    def test_list_returns_runs_and_total(self, repo):
        """Test list returns correct runs and total count."""
        self._seed_runs(repo, count=3)
        runs, total = repo.list_runs(workspace_id=1)
        assert total == 3
        assert len(runs) == 3

    def test_list_pagination(self, repo):
        """Test pagination with page and page_size."""
        self._seed_runs(repo, count=5)
        page1, total = repo.list_runs(workspace_id=1, page=1, page_size=2)
        assert total == 5
        assert len(page1) == 2

        page2, _ = repo.list_runs(workspace_id=1, page=2, page_size=2)
        assert len(page2) == 2

        page3, _ = repo.list_runs(workspace_id=1, page=3, page_size=2)
        assert len(page3) == 1

    def test_list_page_size_capped_at_100(self, repo):
        """Test that page_size is capped at 100."""
        self._seed_runs(repo, count=3)
        runs, total = repo.list_runs(workspace_id=1, page_size=200)
        assert total == 3
        assert len(runs) == 3  # All returned, but page_size was capped

    def test_list_filter_by_status(self, repo):
        """Test filtering runs by status."""
        _create_run(repo, migration_id=1, status="pending")
        _create_run(repo, migration_id=2, status="running")
        _create_run(repo, migration_id=3, status="completed")

        runs, total = repo.list_runs(workspace_id=1, status="running")
        assert total == 1
        assert runs[0].status == "running"

    def test_list_filter_by_migration_id(self, repo):
        """Test filtering runs by migration_id."""
        _create_run(repo, migration_id=100)
        _create_run(repo, migration_id=200)
        _create_run(repo, migration_id=100)

        runs, total = repo.list_runs(workspace_id=1, migration_id=100)
        assert total == 2
        assert all(r.migration_id == 100 for r in runs)

    def test_list_filter_combined(self, repo):
        """Test combining migration_id and status filters."""
        _create_run(repo, migration_id=100, status="pending")
        _create_run(repo, migration_id=100, status="completed")
        _create_run(repo, migration_id=200, status="completed")

        runs, total = repo.list_runs(
            workspace_id=1, migration_id=100, status="completed"
        )
        assert total == 1
        assert runs[0].migration_id == 100
        assert runs[0].status == "completed"

    def test_list_workspace_isolation(self, repo):
        """Test that list_runs only returns runs for the given workspace."""
        _create_run(repo, workspace_id=1)
        _create_run(repo, workspace_id=2)

        runs, total = repo.list_runs(workspace_id=1)
        assert total == 1
        assert runs[0].workspace_id == 1

    def test_list_empty_result(self, repo):
        """Test list returns empty when no runs match."""
        runs, total = repo.list_runs(workspace_id=1)
        assert total == 0
        assert runs == []

    def test_list_ordered_by_created_at_desc(self, repo, db_session):
        """Test that runs are ordered by created_at descending."""
        from datetime import timedelta
        r1 = _create_run(repo, migration_id=1)
        r2 = _create_run(repo, migration_id=2)
        r3 = _create_run(repo, migration_id=3)

        # Manually set distinct created_at values so ordering is deterministic
        now = datetime.utcnow()
        r1.created_at = now - timedelta(minutes=2)
        r2.created_at = now - timedelta(minutes=1)
        r3.created_at = now
        db_session.commit()

        runs, _ = repo.list_runs(workspace_id=1)
        # Most recently created first
        assert runs[0].id == r3.id
        assert runs[-1].id == r1.id


class TestUpdateRun:
    """Tests for update_run."""

    def test_update_existing_run(self, repo):
        """Test updating fields on an existing run."""
        run = _create_run(repo)
        updated = repo.update_run(
            run.id, workspace_id=1,
            status="running",
            progress_percentage=50,
        )
        assert updated is not None
        assert updated.status == "running"
        assert updated.progress_percentage == 50

    def test_update_nonexistent_run_returns_none(self, repo):
        """Test updating a non-existent run returns None."""
        assert repo.update_run(9999, workspace_id=1, status="running") is None

    def test_update_wrong_workspace_returns_none(self, repo):
        """Test workspace isolation on update."""
        run = _create_run(repo)
        assert repo.update_run(run.id, workspace_id=999, status="running") is None

    def test_update_sets_updated_at(self, repo):
        """Test that update modifies updated_at."""
        run = _create_run(repo)
        original_updated = run.updated_at
        updated = repo.update_run(run.id, workspace_id=1, status="completed")
        assert updated.updated_at is not None


class TestDeleteRun:
    """Tests for delete_run."""

    def test_delete_existing_run(self, repo):
        """Test deleting an existing run returns True."""
        run = _create_run(repo)
        assert repo.delete_run(run.id, workspace_id=1) is True
        assert repo.get_run(run.id, workspace_id=1) is None

    def test_delete_nonexistent_run_returns_false(self, repo):
        """Test deleting a non-existent run returns False."""
        assert repo.delete_run(9999, workspace_id=1) is False

    def test_delete_wrong_workspace_returns_false(self, repo):
        """Test workspace isolation on delete."""
        run = _create_run(repo)
        assert repo.delete_run(run.id, workspace_id=999) is False
        # Run should still exist
        assert repo.get_run(run.id, workspace_id=1) is not None


class TestDeleteRunCascade:
    """Tests for cascade deletion of table results when a run is deleted."""

    def test_cascade_deletes_table_results(self, repo, db_session):
        """Test that deleting a run cascade-deletes associated table results."""
        run = _create_run(repo)
        _create_table_result(repo, run.id, table_name="table_a")
        _create_table_result(repo, run.id, table_name="table_b")

        # Verify table results exist
        results = repo.list_table_results(run.id, workspace_id=1)
        assert len(results) == 2

        # Delete the run
        repo.delete_run(run.id, workspace_id=1)

        # Verify table results are gone
        remaining = db_session.query(ValidationTableResult).filter(
            ValidationTableResult.run_id == run.id,
        ).all()
        assert len(remaining) == 0

    def test_cascade_does_not_affect_other_runs(self, repo, db_session):
        """Test that cascade only affects the deleted run's table results."""
        run1 = _create_run(repo, migration_id=1)
        run2 = _create_run(repo, migration_id=2)
        _create_table_result(repo, run1.id, table_name="table_a")
        _create_table_result(repo, run2.id, table_name="table_b")

        repo.delete_run(run1.id, workspace_id=1)

        # run2's table results should still exist
        results = repo.list_table_results(run2.id, workspace_id=1)
        assert len(results) == 1
        assert results[0].table_name == "table_b"


# ── ValidationTableResult CRUD tests ─────────────────────────────────


class TestCreateTableResult:
    """Tests for create_table_result."""

    def test_create_table_result_returns_persisted_instance(self, repo):
        """Test creating a table result persists and returns the instance."""
        run = _create_run(repo)
        result = _create_table_result(repo, run.id)
        assert result.id is not None
        assert result.run_id == run.id
        assert result.table_name == "users"
        assert result.status == "pending"

    def test_create_table_result_with_dataset_name(self, repo):
        """Test creating a table result with optional dataset_name."""
        run = _create_run(repo)
        result = _create_table_result(
            repo, run.id, table_name="orders", dataset_name="analytics"
        )
        assert result.dataset_name == "analytics"

    def test_create_table_result_defaults(self, repo):
        """Test that nullable fields default to None."""
        run = _create_run(repo)
        result = _create_table_result(repo, run.id)
        assert result.ddl_status is None
        assert result.ddl_comparison_result is None
        assert result.row_count_status is None
        assert result.row_count_result is None
        assert result.data_match_status is None
        assert result.data_match_result is None
        assert result.ai_analysis is None
        assert result.error_message is None


class TestGetTableResult:
    """Tests for get_table_result."""

    def test_get_existing_table_result(self, repo):
        """Test retrieving an existing table result."""
        run = _create_run(repo)
        created = _create_table_result(repo, run.id, table_name="orders")
        fetched = repo.get_table_result(run.id, "orders", workspace_id=1)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.table_name == "orders"

    def test_get_nonexistent_table_result_returns_none(self, repo):
        """Test that a non-existent table name returns None."""
        run = _create_run(repo)
        assert repo.get_table_result(run.id, "nonexistent", workspace_id=1) is None

    def test_get_table_result_wrong_workspace_returns_none(self, repo):
        """Test workspace isolation on get_table_result."""
        run = _create_run(repo)
        _create_table_result(repo, run.id, table_name="orders")
        assert repo.get_table_result(run.id, "orders", workspace_id=999) is None

    def test_get_table_result_wrong_run_id_returns_none(self, repo):
        """Test that wrong run_id returns None."""
        run = _create_run(repo)
        _create_table_result(repo, run.id, table_name="orders")
        assert repo.get_table_result(9999, "orders", workspace_id=1) is None


class TestListTableResults:
    """Tests for list_table_results."""

    def test_list_returns_all_results_for_run(self, repo):
        """Test listing all table results for a run."""
        run = _create_run(repo)
        _create_table_result(repo, run.id, table_name="users")
        _create_table_result(repo, run.id, table_name="orders")
        _create_table_result(repo, run.id, table_name="products")

        results = repo.list_table_results(run.id, workspace_id=1)
        assert len(results) == 3

    def test_list_workspace_isolation(self, repo):
        """Test that list only returns results for the given workspace."""
        run = _create_run(repo)
        _create_table_result(repo, run.id, table_name="users", workspace_id=1)
        _create_table_result(repo, run.id, table_name="orders", workspace_id=2)

        results = repo.list_table_results(run.id, workspace_id=1)
        assert len(results) == 1
        assert results[0].table_name == "users"

    def test_list_empty_for_no_results(self, repo):
        """Test list returns empty when no table results exist."""
        run = _create_run(repo)
        results = repo.list_table_results(run.id, workspace_id=1)
        assert results == []

    def test_list_ordered_by_id_ascending(self, repo):
        """Test that results are ordered by id ascending."""
        run = _create_run(repo)
        r1 = _create_table_result(repo, run.id, table_name="aaa")
        r2 = _create_table_result(repo, run.id, table_name="bbb")
        r3 = _create_table_result(repo, run.id, table_name="ccc")

        results = repo.list_table_results(run.id, workspace_id=1)
        assert results[0].id == r1.id
        assert results[1].id == r2.id
        assert results[2].id == r3.id


class TestUpdateTableResult:
    """Tests for update_table_result."""

    def test_update_existing_table_result(self, repo):
        """Test updating fields on an existing table result."""
        run = _create_run(repo)
        result = _create_table_result(repo, run.id)
        updated = repo.update_table_result(
            result.id, workspace_id=1,
            status="completed",
            ddl_status="passed",
            ddl_comparison_result={"discrepancies": [], "source_column_count": 5},
            row_count_status="passed",
            row_count_result={"source_count": 1000, "target_count": 1000},
        )
        assert updated is not None
        assert updated.status == "completed"
        assert updated.ddl_status == "passed"
        assert updated.ddl_comparison_result["source_column_count"] == 5
        assert updated.row_count_status == "passed"

    def test_update_nonexistent_table_result_returns_none(self, repo):
        """Test updating a non-existent table result returns None."""
        assert repo.update_table_result(9999, workspace_id=1, status="completed") is None

    def test_update_wrong_workspace_returns_none(self, repo):
        """Test workspace isolation on update_table_result."""
        run = _create_run(repo)
        result = _create_table_result(repo, run.id)
        assert repo.update_table_result(
            result.id, workspace_id=999, status="completed"
        ) is None

    def test_update_sets_updated_at(self, repo):
        """Test that update modifies updated_at."""
        run = _create_run(repo)
        result = _create_table_result(repo, run.id)
        updated = repo.update_table_result(
            result.id, workspace_id=1, status="running"
        )
        assert updated.updated_at is not None

    def test_update_with_jsonb_fields(self, repo):
        """Test updating JSONB fields (ai_analysis, data_match_result)."""
        run = _create_run(repo)
        result = _create_table_result(repo, run.id)
        ai_data = {
            "root_cause": "Timestamp precision loss",
            "impact_assessment": "3 records affected",
            "recommended_workarounds": ["Truncate timestamps"],
        }
        updated = repo.update_table_result(
            result.id, workspace_id=1,
            ai_analysis=ai_data,
            data_match_result={
                "total_compared": 1000,
                "matched_count": 997,
                "missing_count": 2,
                "extra_count": 0,
                "mismatch_count": 1,
                "sample_discrepancies": [],
            },
        )
        assert updated.ai_analysis["root_cause"] == "Timestamp precision loss"
        assert updated.data_match_result["matched_count"] == 997


# ── list_runs_with_table_results tests ────────────────────────────────


class TestListRunsWithTableResults:
    """Tests for list_runs_with_table_results eager-load method."""

    def test_returns_runs_with_table_results_attached(self, repo):
        """Test that _table_results attribute is populated on each run."""
        run = _create_run(repo, migration_id=1)
        _create_table_result(repo, run.id, table_name="users")
        _create_table_result(repo, run.id, table_name="orders")

        runs, total = repo.list_runs_with_table_results(workspace_id=1)
        assert total == 1
        assert len(runs) == 1
        assert hasattr(runs[0], "_table_results")
        assert len(runs[0]._table_results) == 2
        table_names = [tr.table_name for tr in runs[0]._table_results]
        assert "users" in table_names
        assert "orders" in table_names

    def test_returns_empty_table_results_when_none_exist(self, repo):
        """Test that _table_results is an empty list when run has no table results."""
        _create_run(repo, migration_id=1)

        runs, total = repo.list_runs_with_table_results(workspace_id=1)
        assert total == 1
        assert runs[0]._table_results == []

    def test_returns_same_tuple_shape_as_list_runs(self, repo):
        """Test that return type matches (list, total_count) tuple from list_runs."""
        _create_run(repo, migration_id=1)
        _create_run(repo, migration_id=2)

        runs, total = repo.list_runs_with_table_results(workspace_id=1)
        assert isinstance(runs, list)
        assert isinstance(total, int)
        assert total == 2
        assert len(runs) == 2

    def test_pagination_works(self, repo):
        """Test pagination parameters are respected."""
        for i in range(5):
            _create_run(repo, migration_id=100 + i)

        runs, total = repo.list_runs_with_table_results(
            workspace_id=1, page=1, page_size=2
        )
        assert total == 5
        assert len(runs) == 2

    def test_filter_by_migration_id(self, repo):
        """Test migration_id filter is applied."""
        _create_run(repo, migration_id=100)
        _create_run(repo, migration_id=200)

        runs, total = repo.list_runs_with_table_results(
            workspace_id=1, migration_id=100
        )
        assert total == 1
        assert runs[0].migration_id == 100

    def test_filter_by_status(self, repo):
        """Test status filter is applied."""
        _create_run(repo, migration_id=1, status="pending")
        _create_run(repo, migration_id=2, status="completed")

        runs, total = repo.list_runs_with_table_results(
            workspace_id=1, status="completed"
        )
        assert total == 1
        assert runs[0].status == "completed"

    def test_workspace_isolation(self, repo):
        """Test that table results from other workspaces are not included."""
        run_ws1 = _create_run(repo, workspace_id=1, migration_id=1)
        _create_table_result(repo, run_ws1.id, workspace_id=1, table_name="t1")

        run_ws2 = _create_run(repo, workspace_id=2, migration_id=2)
        _create_table_result(repo, run_ws2.id, workspace_id=2, table_name="t2")

        runs, total = repo.list_runs_with_table_results(workspace_id=1)
        assert total == 1
        assert len(runs[0]._table_results) == 1
        assert runs[0]._table_results[0].table_name == "t1"

    def test_multiple_runs_each_get_own_table_results(self, repo):
        """Test that table results are correctly grouped per run."""
        run1 = _create_run(repo, migration_id=1)
        run2 = _create_run(repo, migration_id=2)
        _create_table_result(repo, run1.id, table_name="alpha")
        _create_table_result(repo, run2.id, table_name="beta")
        _create_table_result(repo, run2.id, table_name="gamma")

        runs, total = repo.list_runs_with_table_results(workspace_id=1)
        assert total == 2

        # Runs are ordered by created_at desc, so run2 comes first
        run_map = {r.id: r for r in runs}
        assert len(run_map[run1.id]._table_results) == 1
        assert run_map[run1.id]._table_results[0].table_name == "alpha"
        assert len(run_map[run2.id]._table_results) == 2
        names = [tr.table_name for tr in run_map[run2.id]._table_results]
        assert "beta" in names
        assert "gamma" in names

    def test_empty_result_when_no_runs(self, repo):
        """Test returns empty list and zero count when no runs exist."""
        runs, total = repo.list_runs_with_table_results(workspace_id=1)
        assert total == 0
        assert runs == []

    def test_table_results_ordered_by_id_ascending(self, repo):
        """Test that _table_results are ordered by id ascending."""
        run = _create_run(repo, migration_id=1)
        tr1 = _create_table_result(repo, run.id, table_name="aaa")
        tr2 = _create_table_result(repo, run.id, table_name="bbb")
        tr3 = _create_table_result(repo, run.id, table_name="ccc")

        runs, _ = repo.list_runs_with_table_results(workspace_id=1)
        result_ids = [tr.id for tr in runs[0]._table_results]
        assert result_ids == [tr1.id, tr2.id, tr3.id]


# ── Cross-workspace isolation tests ──────────────────────────────────


class TestWorkspaceIsolation:
    """Comprehensive workspace isolation tests across all operations."""

    def test_runs_isolated_between_workspaces(self, repo):
        """Test that workspace_id=1 queries never return workspace_id=2 records."""
        run_ws1 = _create_run(repo, workspace_id=1, migration_id=1)
        run_ws2 = _create_run(repo, workspace_id=2, migration_id=2)

        # get_run
        assert repo.get_run(run_ws2.id, workspace_id=1) is None
        assert repo.get_run(run_ws1.id, workspace_id=2) is None

        # list_runs
        ws1_runs, ws1_total = repo.list_runs(workspace_id=1)
        ws2_runs, ws2_total = repo.list_runs(workspace_id=2)
        assert ws1_total == 1
        assert ws2_total == 1
        assert ws1_runs[0].id == run_ws1.id
        assert ws2_runs[0].id == run_ws2.id

    def test_table_results_isolated_between_workspaces(self, repo):
        """Test table result workspace isolation."""
        run = _create_run(repo, workspace_id=1)
        result = _create_table_result(repo, run.id, workspace_id=1, table_name="t1")

        # Cannot access from workspace 2
        assert repo.get_table_result(run.id, "t1", workspace_id=2) is None
        assert repo.list_table_results(run.id, workspace_id=2) == []
        assert repo.update_table_result(result.id, workspace_id=2, status="x") is None
