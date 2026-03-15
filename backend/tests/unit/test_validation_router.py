"""Unit tests for ValidationRouter endpoints."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from database import get_db
from routers.validation_router import router, get_workspace_id
from shared.middleware.auth_middleware import CurrentUser, get_current_user

NOW = datetime(2026, 1, 25, 10, 0, 0)


@pytest.fixture()
def fake_current_user():
    return CurrentUser(user_id=1, username="testuser", role="user", organization_id=1)


@pytest.fixture()
def mock_db_session():
    return MagicMock()


@pytest.fixture()
def client(mock_db_session, fake_current_user):
    app = FastAPI()
    app.include_router(router)
    def _override_get_db():
        yield mock_db_session
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: fake_current_user
    app.dependency_overrides[get_workspace_id] = lambda: 1
    return TestClient(app)

def _run(**o):
    d = dict(id=1, workspace_id=1, migration_id=10, source_connection_id=100,
             target_connection_id=200, status="pending", progress_percentage=0,
             tables_total=3, tables_passed=0, tables_failed=0, tables_error=0,
             started_at=None, completed_at=None, duration_seconds=None,
             created_by="1", created_at=NOW, updated_at=NOW)
    d.update(o)
    return d


def _tbl(**o):
    d = dict(id=1, run_id=1, table_name="users", dataset_name="ds",
             ddl_status="passed", row_count_status="passed",
             data_match_status="passed", status="completed",
             error_message=None, started_at=NOW, completed_at=NOW, duration_seconds=10)
    d.update(o)
    return d


def _detail(**o):
    b = _tbl()
    b.update(
        ddl_comparison_result={"discrepancies": [], "source_column_count": 5,
                               "target_column_count": 5, "columns_compared": 5},
        row_count_result={"source_count": 1000, "target_count": 1000,
                          "difference": 0, "percentage_difference": 0.0},
        data_match_result={"total_compared": 1000, "matched_count": 1000,
                           "missing_count": 0, "extra_count": 0,
                           "mismatch_count": 0, "sample_discrepancies": []},
        ai_analysis=None)
    b.update(o)
    return b


def _report(**o):
    d = dict(run_id=1, migration_id=10, source_connection_name="BQ",
             target_connection_name="RS", overall_status="passed",
             total_tables=2, tables_passed=2, tables_failed=0, tables_error=0,
             started_at=NOW.isoformat() + "Z", completed_at=NOW.isoformat() + "Z",
             duration_seconds=30,
             tables=[_detail(), _detail(id=2, table_name="orders")])
    d.update(o)
    return d


PL = {"migration_id": 10, "source_connection_id": 100,
      "target_connection_id": 200, "tables": ["users", "orders"], "batch_size": 10000}

@patch("routers.validation_router._build_service")
class TestCreate:
    def test_201(self, mb, client):
        s = MagicMock(); s.create_validation_run.return_value = _run(); mb.return_value = s
        r = client.post("/api/validations/", json=PL)
        assert r.status_code == 201 and r.json()["id"] == 1 and r.json()["status"] == "pending"

    def test_bg_task(self, mb, client):
        s = MagicMock(); s.create_validation_run.return_value = _run(id=42); mb.return_value = s
        client.post("/api/validations/", json=PL)
        s.run_validation_background.assert_called_once_with(42, 1)

    def test_422_missing(self, mb, client):
        assert client.post("/api/validations/", json={"source_connection_id": 1}).status_code == 422

    def test_422_batch_low(self, mb, client):
        assert client.post("/api/validations/", json={**PL, "batch_size": 50}).status_code == 422

    def test_422_batch_high(self, mb, client):
        assert client.post("/api/validations/", json={**PL, "batch_size": 200000}).status_code == 422

    def test_400(self, mb, client):
        s = MagicMock(); s.create_validation_run.side_effect = ValueError("bad"); mb.return_value = s
        r = client.post("/api/validations/", json=PL)
        assert r.status_code == 400 and "bad" in r.json()["detail"]

    def test_429_rate_limit(self, mb, client):
        s = MagicMock(); s.create_validation_run.side_effect = RuntimeError("rate limit"); mb.return_value = s
        assert client.post("/api/validations/", json=PL).status_code == 429

    def test_500(self, mb, client):
        s = MagicMock(); s.create_validation_run.side_effect = TypeError("x"); mb.return_value = s
        assert client.post("/api/validations/", json=PL).status_code == 500

    def test_run_name_passed(self, mb, client):
        """Test POST /api/validations/ passes run_name from request body to service."""
        s = MagicMock(); s.create_validation_run.return_value = _run(run_name="Nightly check"); mb.return_value = s
        payload = {**PL, "run_name": "Nightly check"}
        r = client.post("/api/validations/", json=payload)
        assert r.status_code == 201
        assert s.create_validation_run.call_args[1]["run_name"] == "Nightly check"

    def test_run_name_omitted(self, mb, client):
        """Test POST /api/validations/ without run_name passes None to service."""
        s = MagicMock(); s.create_validation_run.return_value = _run(); mb.return_value = s
        r = client.post("/api/validations/", json=PL)
        assert r.status_code == 201
        assert s.create_validation_run.call_args[1]["run_name"] is None

@patch("routers.validation_router._build_service")
class TestList:
    def test_200(self, mb, client):
        s = MagicMock()
        s.list_runs.return_value = {"runs": [_run(), _run(id=2)], "total": 2, "page": 1, "page_size": 20}
        mb.return_value = s
        r = client.get("/api/validations/")
        assert r.status_code == 200 and r.json()["total"] == 2 and len(r.json()["runs"]) == 2

    def test_filters(self, mb, client):
        s = MagicMock()
        s.list_runs.return_value = {"runs": [_run(status="completed")], "total": 1, "page": 1, "page_size": 10}
        mb.return_value = s
        r = client.get("/api/validations/?migration_id=10&status_filter=completed&page=1&page_size=10")
        assert r.status_code == 200
        s.list_runs.assert_called_once_with(workspace_id=1, page=1, page_size=10, migration_id=10, status="completed", include_table_results=False)

    def test_include_table_results_true(self, mb, client):
        """Test GET /api/validations/?include_table_results=true passes param to service."""
        s = MagicMock()
        s.list_runs.return_value = {
            "runs": [_run(table_results=[])],
            "total": 1, "page": 1, "page_size": 20,
        }
        mb.return_value = s
        r = client.get("/api/validations/?include_table_results=true")
        assert r.status_code == 200
        s.list_runs.assert_called_once_with(
            workspace_id=1, page=1, page_size=20,
            migration_id=None, status=None, include_table_results=True,
        )

    def test_include_table_results_false(self, mb, client):
        """Test GET /api/validations/?include_table_results=false omits table_results."""
        s = MagicMock()
        s.list_runs.return_value = {
            "runs": [_run()], "total": 1, "page": 1, "page_size": 20,
        }
        mb.return_value = s
        r = client.get("/api/validations/?include_table_results=false")
        assert r.status_code == 200
        s.list_runs.assert_called_once_with(
            workspace_id=1, page=1, page_size=20,
            migration_id=None, status=None, include_table_results=False,
        )

    def test_empty(self, mb, client):
        s = MagicMock()
        s.list_runs.return_value = {"runs": [], "total": 0, "page": 1, "page_size": 20}
        mb.return_value = s
        r = client.get("/api/validations/")
        assert r.status_code == 200 and r.json()["runs"] == []

    def test_500(self, mb, client):
        s = MagicMock(); s.list_runs.side_effect = RuntimeError("x"); mb.return_value = s
        assert client.get("/api/validations/").status_code == 500

@patch("routers.validation_router._build_service")
class TestGetRun:
    def test_200(self, mb, client):
        s = MagicMock(); s.get_run.return_value = _run(id=5); mb.return_value = s
        r = client.get("/api/validations/5")
        assert r.status_code == 200 and r.json()["id"] == 5

    def test_404(self, mb, client):
        s = MagicMock(); s.get_run.return_value = None; mb.return_value = s
        r = client.get("/api/validations/999")
        assert r.status_code == 404 and "not found" in r.json()["detail"]

    def test_500(self, mb, client):
        s = MagicMock(); s.get_run.side_effect = RuntimeError("x"); mb.return_value = s
        assert client.get("/api/validations/1").status_code == 500


@patch("routers.validation_router._build_service")
class TestGetTables:
    def test_200(self, mb, client):
        s = MagicMock()
        s.get_table_results.return_value = [_tbl(table_name="users"), _tbl(id=2, table_name="orders")]
        mb.return_value = s
        r = client.get("/api/validations/1/tables")
        assert r.status_code == 200 and len(r.json()) == 2 and r.json()[0]["table_name"] == "users"

    def test_404(self, mb, client):
        s = MagicMock(); s.get_table_results.return_value = None; mb.return_value = s
        assert client.get("/api/validations/999/tables").status_code == 404

    def test_500(self, mb, client):
        s = MagicMock(); s.get_table_results.side_effect = RuntimeError("x"); mb.return_value = s
        assert client.get("/api/validations/1/tables").status_code == 500

@patch("routers.validation_router._build_service")
class TestGetDetail:
    def test_200(self, mb, client):
        s = MagicMock(); s.get_table_detail.return_value = _detail(); mb.return_value = s
        r = client.get("/api/validations/1/tables/users")
        d = r.json()
        assert r.status_code == 200 and d["table_name"] == "users"
        assert "ddl_comparison_result" in d and "row_count_result" in d and "data_match_result" in d

    def test_404(self, mb, client):
        s = MagicMock(); s.get_table_detail.return_value = None; mb.return_value = s
        r = client.get("/api/validations/1/tables/nonexistent")
        assert r.status_code == 404 and "not found" in r.json()["detail"]

    def test_500(self, mb, client):
        s = MagicMock(); s.get_table_detail.side_effect = RuntimeError("x"); mb.return_value = s
        assert client.get("/api/validations/1/tables/users").status_code == 500


@patch("routers.validation_router._build_service")
class TestGetReport:
    def test_200(self, mb, client):
        s = MagicMock(); s.get_report.return_value = _report(); mb.return_value = s
        r = client.get("/api/validations/1/report")
        d = r.json()
        assert r.status_code == 200 and d["run_id"] == 1
        assert d["overall_status"] == "passed" and d["total_tables"] == 2 and len(d["tables"]) == 2

    def test_404(self, mb, client):
        s = MagicMock(); s.get_report.return_value = None; mb.return_value = s
        assert client.get("/api/validations/999/report").status_code == 404

    def test_500(self, mb, client):
        s = MagicMock(); s.get_report.side_effect = RuntimeError("x"); mb.return_value = s
        assert client.get("/api/validations/1/report").status_code == 500

@patch("routers.validation_router._build_service")
class TestDelete:
    def test_204(self, mb, client):
        s = MagicMock(); s.delete_run.return_value = True; mb.return_value = s
        r = client.delete("/api/validations/1")
        assert r.status_code == 204
        s.delete_run.assert_called_once_with(run_id=1, workspace_id=1)

    def test_404(self, mb, client):
        s = MagicMock(); s.delete_run.return_value = False; mb.return_value = s
        assert client.delete("/api/validations/999").status_code == 404

    def test_500(self, mb, client):
        s = MagicMock(); s.delete_run.side_effect = RuntimeError("x"); mb.return_value = s
        assert client.delete("/api/validations/1").status_code == 500


@patch("routers.validation_router._build_service")
class TestWorkspace:
    def test_create_ws(self, mb, client):
        s = MagicMock(); s.create_validation_run.return_value = _run(); mb.return_value = s
        client.post("/api/validations/", json=PL)
        assert s.create_validation_run.call_args[1]["workspace_id"] == 1

    def test_list_ws(self, mb, client):
        s = MagicMock()
        s.list_runs.return_value = {"runs": [], "total": 0, "page": 1, "page_size": 20}
        mb.return_value = s
        client.get("/api/validations/")
        s.list_runs.assert_called_once_with(workspace_id=1, page=1, page_size=20, migration_id=None, status=None, include_table_results=False)

    def test_get_ws(self, mb, client):
        s = MagicMock(); s.get_run.return_value = _run(); mb.return_value = s
        client.get("/api/validations/1")
        s.get_run.assert_called_once_with(run_id=1, workspace_id=1)

    def test_delete_ws(self, mb, client):
        s = MagicMock(); s.delete_run.return_value = True; mb.return_value = s
        client.delete("/api/validations/1")
        s.delete_run.assert_called_once_with(run_id=1, workspace_id=1)


@patch("routers.validation_router._build_service")
class TestRateLimitResponse:
    """Test that rate limit errors return HTTP 429."""

    def test_429_on_rate_limit(self, mb, client):
        """RuntimeError from rate limiting returns 429 Too Many Requests."""
        s = MagicMock()
        s.create_validation_run.side_effect = RuntimeError(
            "Workspace 1 has reached the maximum of 10 concurrent validation runs."
        )
        mb.return_value = s
        r = client.post("/api/validations/", json=PL)
        assert r.status_code == 429
        assert "maximum of 10" in r.json()["detail"]

    def test_429_detail_includes_message(self, mb, client):
        """429 response detail contains the full error message."""
        s = MagicMock()
        s.create_validation_run.side_effect = RuntimeError("rate limit exceeded")
        mb.return_value = s
        r = client.post("/api/validations/", json=PL)
        assert r.status_code == 429
        assert "rate limit exceeded" in r.json()["detail"]
