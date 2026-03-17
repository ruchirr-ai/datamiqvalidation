"""
Integration tests for ValidationRouter endpoints.

Tests the full HTTP request/response cycle through the FastAPI app.
The ValidationService is mocked at the ``_build_service`` level since it
requires external BigQuery/Redshift connections that cannot be simulated
with SQLite.  This still exercises the router layer, dependency injection,
Pydantic validation, status-code mapping, and workspace isolation.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import get_db
from routers.validation_router import router, get_workspace_id
from shared.middleware.auth_middleware import CurrentUser, get_current_user

NOW = datetime(2026, 3, 11, 10, 0, 0)


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------

VALID_CREATE_PAYLOAD = {
    "migration_id": 10,
    "source_connection_id": 100,
    "target_connection_id": 200,
    "tables": ["users", "orders"],
    "batch_size": 10000,
}

INVALID_PAYLOAD_MISSING_FIELD = {
    "source_connection_id": 100,
}

INVALID_PAYLOAD_BATCH_LOW = {
    **VALID_CREATE_PAYLOAD,
    "batch_size": 50,
}

VALID_CREATE_PAYLOAD_WITH_RUN_NAME = {
    **VALID_CREATE_PAYLOAD,
    "run_name": "Pre-release check",
}

VALID_CREATE_PAYLOAD_WITHOUT_RUN_NAME = {
    **VALID_CREATE_PAYLOAD,
    # run_name intentionally omitted
}


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _run(**overrides):
    """Return a sample validation run dict."""
    d = dict(
        id=1, workspace_id=1, migration_id=10,
        source_connection_id=100, target_connection_id=200,
        status="pending", progress_percentage=0,
        tables_total=2, tables_passed=0, tables_failed=0, tables_error=0,
        started_at=None, completed_at=None, duration_seconds=None,
        created_by="1", created_at=NOW, updated_at=NOW,
    )
    d.update(overrides)
    return d


def _tbl(**overrides):
    """Return a sample table result dict."""
    d = dict(
        id=1, run_id=1, table_name="users", dataset_name="ds",
        ddl_status="passed", row_count_status="passed",
        data_match_status="passed", status="completed",
        error_message=None, started_at=NOW, completed_at=NOW,
        duration_seconds=10,
    )
    d.update(overrides)
    return d


def _detail(**overrides):
    """Return a sample table detail dict with JSONB fields."""
    b = _tbl()
    b.update(
        ddl_comparison_result={
            "discrepancies": [],
            "source_column_count": 5,
            "target_column_count": 5,
            "columns_compared": 5,
        },
        row_count_result={
            "source_count": 1000,
            "target_count": 1000,
            "difference": 0,
            "percentage_difference": 0.0,
        },
        data_match_result={
            "total_compared": 1000,
            "matched_count": 1000,
            "missing_count": 0,
            "extra_count": 0,
            "mismatch_count": 0,
            "sample_discrepancies": [],
        },
        ai_analysis=None,
    )
    b.update(overrides)
    return b


def _report(**overrides):
    """Return a sample report dict."""
    d = dict(
        run_id=1, migration_id=10,
        source_connection_name="BQ", target_connection_name="RS",
        overall_status="passed",
        total_tables=2, tables_passed=2, tables_failed=0, tables_error=0,
        started_at=NOW.isoformat() + "Z",
        completed_at=NOW.isoformat() + "Z",
        duration_seconds=30,
        tables=[_detail(), _detail(id=2, table_name="orders")],
    )
    d.update(overrides)
    return d


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_user():
    """A fake authenticated user for dependency override."""
    return CurrentUser(user_id=1, username="testuser", role="user", organization_id=1)


@pytest.fixture()
def mock_db_session():
    """MagicMock standing in for a real DB session."""
    return MagicMock()


def _make_app(mock_db_session, fake_user, workspace_id=1):
    """Build a FastAPI app with dependency overrides for the given workspace."""
    app = FastAPI()
    app.include_router(router)

    def _override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_workspace_id] = lambda: workspace_id
    return app


@pytest.fixture()
def client(mock_db_session, fake_user):
    """TestClient wired to workspace 1."""
    app = _make_app(mock_db_session, fake_user, workspace_id=1)
    return TestClient(app)


@pytest.fixture()
def client_workspace2(mock_db_session, fake_user):
    """TestClient wired to workspace 2 for isolation tests."""
    app = _make_app(mock_db_session, fake_user, workspace_id=2)
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/validations/
# ---------------------------------------------------------------------------


@patch("routers.validation_router._build_service")
class TestCreateValidationRunIntegration:
    """Integration tests for POST /api/validations/."""

    def test_valid_payload_returns_201(self, mb, client):
        """Test POST / with valid payload returns 201 and run details."""
        svc = MagicMock()
        svc.create_validation_run.return_value = _run()
        mb.return_value = svc

        resp = client.post("/api/validations/", json=VALID_CREATE_PAYLOAD)

        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == 1
        assert body["status"] == "pending"
        assert body["migration_id"] == 10
        assert body["workspace_id"] == 1
        assert body["tables_total"] == 2

    def test_background_task_started(self, mb, client):
        """Test POST / triggers background validation task."""
        svc = MagicMock()
        svc.create_validation_run.return_value = _run(id=42)
        mb.return_value = svc

        client.post("/api/validations/", json=VALID_CREATE_PAYLOAD)

        svc.run_validation_background.assert_called_once_with(42, 1)

    def test_missing_required_field_returns_422(self, mb, client):
        """Test POST / with missing migration_id returns 422."""
        resp = client.post("/api/validations/", json=INVALID_PAYLOAD_MISSING_FIELD)
        assert resp.status_code == 422

    def test_invalid_batch_size_returns_422(self, mb, client):
        """Test POST / with batch_size below minimum returns 422."""
        resp = client.post("/api/validations/", json=INVALID_PAYLOAD_BATCH_LOW)
        assert resp.status_code == 422

    def test_value_error_returns_400(self, mb, client):
        """Test POST / returns 400 when service raises ValueError."""
        svc = MagicMock()
        svc.create_validation_run.side_effect = ValueError("Migration not completed")
        mb.return_value = svc

        resp = client.post("/api/validations/", json=VALID_CREATE_PAYLOAD)

        assert resp.status_code == 400
        assert "Migration not completed" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/validations/
# ---------------------------------------------------------------------------


@patch("routers.validation_router._build_service")
class TestListValidationRunsIntegration:
    """Integration tests for GET /api/validations/."""

    def test_returns_paginated_results(self, mb, client):
        """Test GET / returns paginated list of runs."""
        svc = MagicMock()
        svc.list_runs.return_value = {
            "runs": [_run(), _run(id=2)],
            "total": 2, "page": 1, "page_size": 20,
        }
        mb.return_value = svc

        resp = client.get("/api/validations/")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["runs"]) == 2
        assert body["page"] == 1
        assert body["page_size"] == 20

    def test_filters_by_status_and_migration(self, mb, client):
        """Test GET / passes filter params to service."""
        svc = MagicMock()
        svc.list_runs.return_value = {
            "runs": [_run(status="completed")],
            "total": 1, "page": 1, "page_size": 10,
        }
        mb.return_value = svc

        resp = client.get(
            "/api/validations/",
            params={"migration_id": 10, "status_filter": "completed", "page": 1, "page_size": 10},
        )

        assert resp.status_code == 200
        svc.list_runs.assert_called_once_with(
            workspace_id=1, page=1, page_size=10, migration_id=10, status="completed",
            include_table_results=False,
        )

    def test_empty_list(self, mb, client):
        """Test GET / returns empty list when no runs exist."""
        svc = MagicMock()
        svc.list_runs.return_value = {
            "runs": [], "total": 0, "page": 1, "page_size": 20,
        }
        mb.return_value = svc

        resp = client.get("/api/validations/")

        assert resp.status_code == 200
        assert resp.json()["runs"] == []
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# GET /api/validations/{run_id}
# ---------------------------------------------------------------------------


@patch("routers.validation_router._build_service")
class TestGetValidationRunIntegration:
    """Integration tests for GET /api/validations/{run_id}."""

    def test_returns_run_details(self, mb, client):
        """Test GET /{run_id} returns full run details."""
        svc = MagicMock()
        svc.get_run.return_value = _run(id=5)
        mb.return_value = svc

        resp = client.get("/api/validations/5")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 5
        assert body["migration_id"] == 10
        assert body["status"] == "pending"

    def test_nonexistent_returns_404(self, mb, client):
        """Test GET /{run_id} returns 404 for non-existent run."""
        svc = MagicMock()
        svc.get_run.return_value = None
        mb.return_value = svc

        resp = client.get("/api/validations/999")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /api/validations/{run_id}/tables
# ---------------------------------------------------------------------------


@patch("routers.validation_router._build_service")
class TestGetTableResultsIntegration:
    """Integration tests for GET /api/validations/{run_id}/tables."""

    def test_returns_table_list(self, mb, client):
        """Test GET /{run_id}/tables returns per-table results."""
        svc = MagicMock()
        svc.get_table_results.return_value = [
            _tbl(table_name="users"),
            _tbl(id=2, table_name="orders"),
        ]
        mb.return_value = svc

        resp = client.get("/api/validations/1/tables")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["table_name"] == "users"
        assert body[1]["table_name"] == "orders"

    def test_nonexistent_run_returns_404(self, mb, client):
        """Test GET /{run_id}/tables returns 404 when run not found."""
        svc = MagicMock()
        svc.get_table_results.return_value = None
        mb.return_value = svc

        resp = client.get("/api/validations/999/tables")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/validations/{run_id}/tables/{table_name}
# ---------------------------------------------------------------------------


@patch("routers.validation_router._build_service")
class TestGetTableDetailIntegration:
    """Integration tests for GET /api/validations/{run_id}/tables/{table_name}."""

    def test_returns_detail_with_jsonb(self, mb, client):
        """Test GET /{run_id}/tables/{name} returns detail with JSONB fields."""
        svc = MagicMock()
        svc.get_table_detail.return_value = _detail()
        mb.return_value = svc

        resp = client.get("/api/validations/1/tables/users")

        assert resp.status_code == 200
        body = resp.json()
        assert body["table_name"] == "users"
        assert "ddl_comparison_result" in body
        assert body["ddl_comparison_result"]["columns_compared"] == 5
        assert "row_count_result" in body
        assert body["row_count_result"]["source_count"] == 1000
        assert "data_match_result" in body
        assert body["data_match_result"]["matched_count"] == 1000

    def test_nonexistent_returns_404(self, mb, client):
        """Test GET /{run_id}/tables/{name} returns 404 when table not found."""
        svc = MagicMock()
        svc.get_table_detail.return_value = None
        mb.return_value = svc

        resp = client.get("/api/validations/1/tables/nonexistent")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /api/validations/{run_id}/report
# ---------------------------------------------------------------------------


@patch("routers.validation_router._build_service")
class TestGetReportIntegration:
    """Integration tests for GET /api/validations/{run_id}/report."""

    def test_returns_full_report(self, mb, client):
        """Test GET /{run_id}/report returns full validation report."""
        svc = MagicMock()
        svc.get_report.return_value = _report()
        mb.return_value = svc

        resp = client.get("/api/validations/1/report")

        assert resp.status_code == 200
        body = resp.json()
        assert body["run_id"] == 1
        assert body["overall_status"] == "passed"
        assert body["total_tables"] == 2
        assert len(body["tables"]) == 2
        assert body["source_connection_name"] == "BQ"
        assert body["target_connection_name"] == "RS"

    def test_nonexistent_returns_404(self, mb, client):
        """Test GET /{run_id}/report returns 404 when run not found."""
        svc = MagicMock()
        svc.get_report.return_value = None
        mb.return_value = svc

        resp = client.get("/api/validations/999/report")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/validations/{run_id}
# ---------------------------------------------------------------------------


@patch("routers.validation_router._build_service")
class TestDeleteValidationRunIntegration:
    """Integration tests for DELETE /api/validations/{run_id}."""

    def test_delete_returns_204(self, mb, client):
        """Test DELETE /{run_id} returns 204 on success."""
        svc = MagicMock()
        svc.delete_run.return_value = True
        mb.return_value = svc

        resp = client.delete("/api/validations/1")

        assert resp.status_code == 204
        svc.delete_run.assert_called_once_with(run_id=1, workspace_id=1)

    def test_nonexistent_returns_404(self, mb, client):
        """Test DELETE /{run_id} returns 404 for non-existent run."""
        svc = MagicMock()
        svc.delete_run.return_value = False
        mb.return_value = svc

        resp = client.delete("/api/validations/999")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Workspace isolation
# ---------------------------------------------------------------------------


@patch("routers.validation_router._build_service")
class TestWorkspaceIsolationIntegration:
    """
    Verify that workspace_id is correctly propagated to the service layer.

    Each client fixture overrides ``get_workspace_id`` to return a different
    workspace, so we can assert the service receives the right value.
    """

    def test_create_passes_workspace_id(self, mb, client):
        """POST / passes workspace_id=1 to service.create_validation_run."""
        svc = MagicMock()
        svc.create_validation_run.return_value = _run()
        mb.return_value = svc

        client.post("/api/validations/", json=VALID_CREATE_PAYLOAD)

        assert svc.create_validation_run.call_args[1]["workspace_id"] == 1

    def test_list_passes_workspace_id(self, mb, client_workspace2):
        """GET / passes workspace_id=2 to service.list_runs."""
        svc = MagicMock()
        svc.list_runs.return_value = {
            "runs": [], "total": 0, "page": 1, "page_size": 20,
        }
        mb.return_value = svc

        client_workspace2.get("/api/validations/")

        svc.list_runs.assert_called_once_with(
            workspace_id=2, page=1, page_size=20, migration_id=None, status=None,
            include_table_results=False,
        )

    def test_get_passes_workspace_id(self, mb, client_workspace2):
        """GET /{run_id} passes workspace_id=2 to service.get_run."""
        svc = MagicMock()
        svc.get_run.return_value = _run(workspace_id=2)
        mb.return_value = svc

        client_workspace2.get("/api/validations/1")

        svc.get_run.assert_called_once_with(run_id=1, workspace_id=2)

    def test_delete_passes_workspace_id(self, mb, client_workspace2):
        """DELETE /{run_id} passes workspace_id=2 to service.delete_run."""
        svc = MagicMock()
        svc.delete_run.return_value = True
        mb.return_value = svc

        client_workspace2.delete("/api/validations/1")

        svc.delete_run.assert_called_once_with(run_id=1, workspace_id=2)


@patch("routers.validation_router._build_service")
class TestRateLimitingIntegration:
    """
    Integration tests for rate limiting of concurrent validation runs.

    Verifies the full HTTP request/response cycle when the service raises
    RuntimeError due to rate limiting.
    """

    def test_rate_limit_returns_429(self, mb, client):
        """POST / returns 429 when workspace has too many active runs."""
        svc = MagicMock()
        svc.create_validation_run.side_effect = RuntimeError(
            "Workspace 1 has reached the maximum of 10 concurrent validation runs. "
            "Please wait for existing runs to complete before starting a new one."
        )
        mb.return_value = svc

        response = client.post("/api/validations/", json=VALID_CREATE_PAYLOAD)

        assert response.status_code == 429
        assert "maximum of 10" in response.json()["detail"]

    def test_rate_limit_does_not_start_background_task(self, mb, client):
        """POST / does not start background task when rate limited."""
        svc = MagicMock()
        svc.create_validation_run.side_effect = RuntimeError("rate limit")
        mb.return_value = svc

        client.post("/api/validations/", json=VALID_CREATE_PAYLOAD)

        svc.run_validation_background.assert_not_called()

    def test_under_limit_returns_201(self, mb, client):
        """POST / returns 201 when workspace is under the rate limit."""
        svc = MagicMock()
        svc.create_validation_run.return_value = _run()
        mb.return_value = svc

        response = client.post("/api/validations/", json=VALID_CREATE_PAYLOAD)

        assert response.status_code == 201
        assert response.json()["id"] == 1


# ---------------------------------------------------------------------------
# run_name round-trip (POST → GET)
# ---------------------------------------------------------------------------


@patch("routers.validation_router._build_service")
class TestRunNameIntegration:
    """
    Integration tests for run_name persistence through the HTTP layer.

    Validates: Requirements 1.3
    """

    def test_create_with_run_name_returns_run_name(self, mb, client):
        """POST / with run_name → response includes run_name."""
        svc = MagicMock()
        svc.create_validation_run.return_value = _run(run_name="Pre-release check")
        mb.return_value = svc

        resp = client.post("/api/validations/", json=VALID_CREATE_PAYLOAD_WITH_RUN_NAME)

        assert resp.status_code == 201
        body = resp.json()
        assert body["run_name"] == "Pre-release check"

    def test_create_with_run_name_passes_to_service(self, mb, client):
        """POST / forwards run_name from request body to service layer."""
        svc = MagicMock()
        svc.create_validation_run.return_value = _run(run_name="Pre-release check")
        mb.return_value = svc

        client.post("/api/validations/", json=VALID_CREATE_PAYLOAD_WITH_RUN_NAME)

        assert svc.create_validation_run.call_args[1]["run_name"] == "Pre-release check"

    def test_create_without_run_name_returns_null(self, mb, client):
        """POST / without run_name → response has run_name=null."""
        svc = MagicMock()
        svc.create_validation_run.return_value = _run(run_name=None)
        mb.return_value = svc

        resp = client.post("/api/validations/", json=VALID_CREATE_PAYLOAD_WITHOUT_RUN_NAME)

        assert resp.status_code == 201
        assert resp.json()["run_name"] is None

    def test_get_run_returns_run_name(self, mb, client):
        """GET /{run_id} returns the persisted run_name."""
        svc = MagicMock()
        svc.get_run.return_value = _run(id=7, run_name="Nightly validation")
        mb.return_value = svc

        resp = client.get("/api/validations/7")

        assert resp.status_code == 200
        assert resp.json()["run_name"] == "Nightly validation"

    def test_get_run_returns_null_run_name(self, mb, client):
        """GET /{run_id} returns run_name=null when not set."""
        svc = MagicMock()
        svc.get_run.return_value = _run(id=8, run_name=None)
        mb.return_value = svc

        resp = client.get("/api/validations/8")

        assert resp.status_code == 200
        assert resp.json()["run_name"] is None


# ---------------------------------------------------------------------------
# include_table_results query parameter
# ---------------------------------------------------------------------------


@patch("routers.validation_router._build_service")
class TestIncludeTableResultsIntegration:
    """
    Integration tests for the include_table_results query parameter on
    GET /api/validations/.

    Validates: Requirements 6.1, 6.2, 6.3
    """

    def test_include_table_results_true_returns_array(self, mb, client):
        """GET /?include_table_results=true → each run has table_results array."""
        svc = MagicMock()
        svc.list_runs.return_value = {
            "runs": [
                _run(id=1, run_name="Run A", table_results=[
                    _tbl(id=10, table_name="users"),
                    _tbl(id=11, table_name="orders", ddl_status="failed", status="failed"),
                ]),
            ],
            "total": 1, "page": 1, "page_size": 20,
        }
        mb.return_value = svc

        resp = client.get("/api/validations/", params={"include_table_results": "true"})

        assert resp.status_code == 200
        body = resp.json()
        run = body["runs"][0]
        assert run["table_results"] is not None
        assert len(run["table_results"]) == 2
        assert run["table_results"][0]["table_name"] == "users"
        assert run["table_results"][1]["table_name"] == "orders"
        assert run["table_results"][1]["ddl_status"] == "failed"

    def test_include_table_results_true_passes_param_to_service(self, mb, client):
        """GET /?include_table_results=true forwards the flag to service.list_runs."""
        svc = MagicMock()
        svc.list_runs.return_value = {
            "runs": [], "total": 0, "page": 1, "page_size": 20,
        }
        mb.return_value = svc

        client.get("/api/validations/", params={"include_table_results": "true"})

        svc.list_runs.assert_called_once_with(
            workspace_id=1, page=1, page_size=20,
            migration_id=None, status=None,
            include_table_results=True,
        )

    def test_include_table_results_false_returns_no_table_results(self, mb, client):
        """GET /?include_table_results=false → runs have table_results=null."""
        svc = MagicMock()
        svc.list_runs.return_value = {
            "runs": [_run(id=1)],
            "total": 1, "page": 1, "page_size": 20,
        }
        mb.return_value = svc

        resp = client.get("/api/validations/", params={"include_table_results": "false"})

        assert resp.status_code == 200
        run = resp.json()["runs"][0]
        assert run.get("table_results") is None

    def test_include_table_results_omitted_defaults_false(self, mb, client):
        """GET / without include_table_results → defaults to false, no table_results."""
        svc = MagicMock()
        svc.list_runs.return_value = {
            "runs": [_run(id=2)],
            "total": 1, "page": 1, "page_size": 20,
        }
        mb.return_value = svc

        resp = client.get("/api/validations/")

        assert resp.status_code == 200
        run = resp.json()["runs"][0]
        assert run.get("table_results") is None
        # Verify service received include_table_results=False
        svc.list_runs.assert_called_once_with(
            workspace_id=1, page=1, page_size=20,
            migration_id=None, status=None,
            include_table_results=False,
        )

    def test_include_table_results_true_empty_tables(self, mb, client):
        """GET /?include_table_results=true with run having no table results → empty array."""
        svc = MagicMock()
        svc.list_runs.return_value = {
            "runs": [_run(id=3, table_results=[])],
            "total": 1, "page": 1, "page_size": 20,
        }
        mb.return_value = svc

        resp = client.get("/api/validations/", params={"include_table_results": "true"})

        assert resp.status_code == 200
        run = resp.json()["runs"][0]
        assert run["table_results"] == []
