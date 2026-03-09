"""
Integration tests for ConversionRouter endpoints.

Uses a real in-memory SQLite database with SQLAlchemy and the actual
ConversionService / ConversionRepository layers.  External services
(AWS Bedrock, S3, Redis) are mocked so the tests can run without cloud
credentials.

These tests differ from the unit tests in ``test_conversion_router.py``
because they exercise the full router → service → repository → DB stack
rather than mocking the service layer.
"""

import pytest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db

# Import ALL models so Base.metadata knows about every table before create_all
from models.connection import Connection  # noqa: F401
from models.conversion_batch import ConversionBatch  # noqa: F401
from models.conversion_job import ConversionJob  # noqa: F401
from models.conversion_log import ConversionLog  # noqa: F401

from routers.conversion_router import router, get_workspace_id
from shared.middleware.auth_middleware import CurrentUser, get_current_user
from tests.fixtures.sample_payloads import (
    VALID_BATCH_CONVERSION,
    VALID_STANDALONE_CONVERSION,
    VALID_STANDALONE_WITH_CONTEXT,
    INVALID_DIALECT_PAYLOAD,
    BULK_DELETE_PAYLOAD,
    CONTEXT_EXCEEDS_LIMIT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine():
    """Create an in-memory SQLite engine shared across threads."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db_session(db_engine):
    """Provide a DB session with seed data for FK constraints."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    # Seed connection rows required by ConversionBatch FK constraints
    session.add_all([
        Connection(
            id=10, name="src_conn", type="bigquery", database="src_db",
            connection_params={"project": "test"}, created_by="system",
        ),
        Connection(
            id=20, name="tgt_conn", type="redshift", database="tgt_db",
            connection_params={"host": "localhost"}, created_by="system",
        ),
    ])
    session.commit()
    yield session
    session.close()


@pytest.fixture()
def fake_user():
    """A fake authenticated user for dependency override."""
    return CurrentUser(user_id=1, username="testuser", role="user", organization_id=1)


def _mock_bedrock_client():
    """Return a MagicMock that satisfies BedrockClient calls."""
    mock = MagicMock()
    mock.fetch_prompt_template.return_value = (
        "Convert {{source_code}} from {{source_dialect}} to {{target_dialect}}"
    )
    mock.render_prompt.return_value = "rendered prompt text"
    mock.invoke_model.return_value = "SELECT * FROM my_schema.my_table"
    return mock


def _mock_cache():
    """Return a MagicMock that satisfies ConversionCache (no Redis)."""
    mock = MagicMock()
    mock.get_batch_status.return_value = None
    mock.set_batch_status.return_value = None
    mock.invalidate_batch_status.return_value = None
    mock.get_discovered_assets.return_value = None
    mock.set_discovered_assets.return_value = None
    mock.invalidate_discovered_assets.return_value = None
    return mock


def _make_app(db_session, fake_user, workspace_id=1):
    """Build a FastAPI app wired to the given session and workspace."""
    app = FastAPI()
    app.include_router(router)

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_workspace_id] = lambda: workspace_id
    return app


@pytest.fixture()
def client(db_session, fake_user):
    """
    TestClient wired to a real SQLite DB (workspace 1).

    Mocks BedrockClient and ConversionCache at the service layer so
    no AWS or Redis calls are made.
    """
    app = _make_app(db_session, fake_user, workspace_id=1)
    with patch("services.conversion_service.BedrockClient", return_value=_mock_bedrock_client()), \
         patch("services.conversion_service.ConversionCache", return_value=_mock_cache()), \
         patch("routers.conversion_router.ConversionCache", return_value=_mock_cache()):
        yield TestClient(app)


@pytest.fixture()
def client_workspace2(db_session, fake_user):
    """
    TestClient identical to ``client`` but with workspace_id=2.

    Used to verify workspace isolation — records created under workspace 1
    should not be visible here.
    """
    app = _make_app(db_session, fake_user, workspace_id=2)
    with patch("services.conversion_service.BedrockClient", return_value=_mock_bedrock_client()), \
         patch("services.conversion_service.ConversionCache", return_value=_mock_cache()), \
         patch("routers.conversion_router.ConversionCache", return_value=_mock_cache()):
        yield TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/conversions/standalone
# ---------------------------------------------------------------------------


class TestStandaloneConversionIntegration:
    """Integration tests for POST /api/conversions/standalone."""

    def test_valid_payload_returns_201_with_persisted_job(self, client, db_session):
        """Test POST /standalone with valid payload creates a real DB record and returns 201."""
        resp = client.post("/api/conversions/standalone", json=VALID_STANDALONE_CONVERSION)

        assert resp.status_code == 201
        body = resp.json()
        assert body["source_dialect"] == "Bigquery"
        assert body["target_dialect"] == "Redshift"
        assert body["asset_type"] == "TABLE_DDL"
        assert body["workspace_id"] == 1
        assert body["status"] in ("completed", "failed")
        assert body["created_by"] == "1"

        # Verify the record actually exists in the database
        job = db_session.query(ConversionJob).filter_by(id=body["id"]).first()
        assert job is not None
        assert job.source_dialect == "Bigquery"

    def test_missing_required_field_returns_422(self, client):
        """Test POST /standalone with missing source_code returns 422 (Pydantic validation)."""
        payload = {**VALID_STANDALONE_CONVERSION}
        del payload["source_code"]

        resp = client.post("/api/conversions/standalone", json=payload)
        assert resp.status_code == 422

    def test_empty_source_code_returns_422(self, client):
        """Test POST /standalone with empty source_code returns 422."""
        payload = {**VALID_STANDALONE_CONVERSION, "source_code": ""}

        resp = client.post("/api/conversions/standalone", json=payload)
        assert resp.status_code == 422

    def test_invalid_asset_type_returns_422(self, client):
        """Test POST /standalone with invalid asset_type returns 422."""
        payload = {**VALID_STANDALONE_CONVERSION, "asset_type": "INVALID"}

        resp = client.post("/api/conversions/standalone", json=payload)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/conversions/jobs
# ---------------------------------------------------------------------------


class TestListJobsIntegration:
    """Integration tests for GET /api/conversions/jobs."""

    def test_returns_paginated_results(self, client):
        """Test GET /jobs returns paginated results from real DB."""
        client.post("/api/conversions/standalone", json=VALID_STANDALONE_CONVERSION)
        client.post("/api/conversions/standalone", json=VALID_STANDALONE_CONVERSION)

        resp = client.get("/api/conversions/jobs")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 2
        assert body["page"] == 1
        assert body["page_size"] == 20
        assert len(body["jobs"]) >= 2

    def test_empty_workspace_returns_empty_list(self, client_workspace2):
        """Test GET /jobs returns empty list when workspace has no jobs."""
        resp = client_workspace2.get("/api/conversions/jobs")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["jobs"] == []

    def test_pagination_params(self, client):
        """Test GET /jobs respects page and page_size query params."""
        for _ in range(3):
            client.post("/api/conversions/standalone", json=VALID_STANDALONE_CONVERSION)

        resp = client.get("/api/conversions/jobs", params={"page": 1, "page_size": 2})

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["jobs"]) == 2
        assert body["total"] >= 3
        assert body["page"] == 1
        assert body["page_size"] == 2


# ---------------------------------------------------------------------------
# GET /api/conversions/jobs/{job_id}
# ---------------------------------------------------------------------------


class TestGetJobIntegration:
    """Integration tests for GET /api/conversions/jobs/{job_id}."""

    def test_returns_job_detail(self, client):
        """Test GET /jobs/{job_id} returns full job detail from real DB."""
        create_resp = client.post("/api/conversions/standalone", json=VALID_STANDALONE_CONVERSION)
        assert create_resp.status_code == 201
        job_id = create_resp.json()["id"]

        resp = client.get(f"/api/conversions/jobs/{job_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == job_id
        assert body["source_dialect"] == "Bigquery"
        assert body["target_dialect"] == "Redshift"
        assert body["source_code"] == VALID_STANDALONE_CONVERSION["source_code"]

    def test_nonexistent_job_returns_404(self, client):
        """Test GET /jobs/{job_id} returns 404 for non-existent job."""
        resp = client.get("/api/conversions/jobs/99999")

        assert resp.status_code == 404
        assert "99999" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# DELETE /api/conversions/jobs/{job_id}
# ---------------------------------------------------------------------------


class TestDeleteJobIntegration:
    """Integration tests for DELETE /api/conversions/jobs/{job_id}."""

    def test_delete_existing_job_returns_200(self, client, db_session):
        """Test DELETE /jobs/{job_id} removes the record and returns 200."""
        create_resp = client.post("/api/conversions/standalone", json=VALID_STANDALONE_CONVERSION)
        assert create_resp.status_code == 201
        job_id = create_resp.json()["id"]

        resp = client.delete(f"/api/conversions/jobs/{job_id}")

        assert resp.status_code == 200
        assert str(job_id) in resp.json()["message"]

        # Verify the record is gone from the database
        db_session.expire_all()
        job = db_session.query(ConversionJob).filter_by(id=job_id).first()
        assert job is None

    def test_delete_nonexistent_job_returns_404(self, client):
        """Test DELETE /jobs/{job_id} returns 404 for non-existent job."""
        resp = client.delete("/api/conversions/jobs/99999")

        assert resp.status_code == 404
        assert "99999" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /api/conversions/batch
# ---------------------------------------------------------------------------


class TestBatchConversionIntegration:
    """Integration tests for POST /api/conversions/batch."""

    def test_valid_payload_returns_201_with_persisted_batch(self, client, db_session):
        """Test POST /batch creates a real batch and child jobs in the DB."""
        resp = client.post("/api/conversions/batch", json=VALID_BATCH_CONVERSION)

        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "pending"
        assert body["total_assets"] == 2
        assert body["workspace_id"] == 1
        assert body["source_connection_id"] == 10
        assert body["target_connection_id"] == 20

        # Verify batch record in DB
        db_session.expire_all()
        batch = db_session.query(ConversionBatch).filter_by(id=body["id"]).first()
        assert batch is not None
        assert batch.total_assets == 2

        # Verify child jobs were created
        jobs = db_session.query(ConversionJob).filter_by(batch_id=batch.id).all()
        assert len(jobs) == 2

    def test_missing_assets_returns_422(self, client):
        """Test POST /batch with missing assets field returns 422."""
        payload = {**VALID_BATCH_CONVERSION}
        del payload["assets"]

        resp = client.post("/api/conversions/batch", json=payload)
        assert resp.status_code == 422

    def test_empty_assets_returns_422(self, client):
        """Test POST /batch with empty assets list returns 422."""
        payload = {**VALID_BATCH_CONVERSION, "assets": []}

        resp = client.post("/api/conversions/batch", json=payload)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/conversions/batch/{batch_id}
# ---------------------------------------------------------------------------


class TestGetBatchIntegration:
    """Integration tests for GET /api/conversions/batch/{batch_id}."""

    def test_returns_batch_status(self, client):
        """Test GET /batch/{batch_id} returns batch status from real DB."""
        create_resp = client.post("/api/conversions/batch", json=VALID_BATCH_CONVERSION)
        assert create_resp.status_code == 201
        batch_id = create_resp.json()["id"]

        resp = client.get(f"/api/conversions/batch/{batch_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == batch_id
        assert body["total_assets"] == 2
        # Background task may run synchronously in TestClient, so the
        # batch could already be completed by the time we query it.
        assert body["status"] in ("pending", "in_progress", "completed", "completed_with_errors")

    def test_nonexistent_batch_returns_404(self, client):
        """Test GET /batch/{batch_id} returns 404 for non-existent batch."""
        resp = client.get("/api/conversions/batch/99999")

        assert resp.status_code == 404
        assert "99999" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Workspace isolation
# ---------------------------------------------------------------------------


class TestWorkspaceIsolationIntegration:
    """
    Verify that records created under workspace 1 are invisible to workspace 2.

    The workspace_id filter in the repository layer should exclude records
    belonging to a different workspace, resulting in 404 responses.
    """

    def test_job_not_visible_in_other_workspace(self, client, client_workspace2):
        """Job created in workspace 1 returns 404 when queried from workspace 2."""
        create_resp = client.post("/api/conversions/standalone", json=VALID_STANDALONE_CONVERSION)
        assert create_resp.status_code == 201
        job_id = create_resp.json()["id"]

        resp = client_workspace2.get(f"/api/conversions/jobs/{job_id}")
        assert resp.status_code == 404

    def test_delete_job_in_other_workspace_returns_404(self, client, client_workspace2):
        """Deleting a job from a different workspace returns 404."""
        create_resp = client.post("/api/conversions/standalone", json=VALID_STANDALONE_CONVERSION)
        assert create_resp.status_code == 201
        job_id = create_resp.json()["id"]

        resp = client_workspace2.delete(f"/api/conversions/jobs/{job_id}")
        assert resp.status_code == 404

    def test_batch_not_visible_in_other_workspace(self, client, client_workspace2):
        """Batch created in workspace 1 returns 404 when queried from workspace 2."""
        create_resp = client.post("/api/conversions/batch", json=VALID_BATCH_CONVERSION)
        assert create_resp.status_code == 201
        batch_id = create_resp.json()["id"]

        resp = client_workspace2.get(f"/api/conversions/batch/{batch_id}")
        assert resp.status_code == 404

    def test_list_jobs_excludes_other_workspace(self, client, client_workspace2):
        """GET /jobs from workspace 2 does not include workspace 1 jobs."""
        create_resp = client.post("/api/conversions/standalone", json=VALID_STANDALONE_CONVERSION)
        assert create_resp.status_code == 201

        resp = client_workspace2.get("/api/conversions/jobs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["jobs"] == []


# ---------------------------------------------------------------------------
# POST /api/conversions/standalone — enhanced fields
# ---------------------------------------------------------------------------


class TestStandaloneEnhancementsIntegration:
    """Integration tests for enhanced standalone conversion fields."""

    def test_additional_context_accepted(self, client, db_session):
        """Test POST /standalone with additional_context field returns 201."""
        resp = client.post("/api/conversions/standalone", json=VALID_STANDALONE_WITH_CONTEXT)

        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] in ("completed", "failed")
        # additional_context should NOT be persisted on the job record
        job = db_session.query(ConversionJob).filter_by(id=body["id"]).first()
        assert job is not None
        assert not hasattr(job, "additional_context") or getattr(job, "additional_context", None) is None

    def test_invalid_dialect_returns_400(self, client):
        """Test POST /standalone with invalid dialect returns 400."""
        resp = client.post("/api/conversions/standalone", json=INVALID_DIALECT_PAYLOAD)

        assert resp.status_code == 400
        assert "dialect" in resp.json()["detail"].lower()

    def test_query_asset_type_accepted(self, client):
        """Test POST /standalone with QUERY asset_type accepted."""
        payload = {
            **VALID_STANDALONE_WITH_CONTEXT,
            "asset_type": "QUERY",
        }
        resp = client.post("/api/conversions/standalone", json=payload)

        assert resp.status_code == 201
        assert resp.json()["asset_type"] == "QUERY"

    def test_scheduled_query_asset_type_accepted(self, client):
        """Test POST /standalone with SCHEDULED_QUERY asset_type accepted (backward compat)."""
        payload = {
            **VALID_STANDALONE_WITH_CONTEXT,
            "asset_type": "SCHEDULED_QUERY",
        }
        resp = client.post("/api/conversions/standalone", json=payload)

        assert resp.status_code == 201
        assert resp.json()["asset_type"] in ("QUERY", "SCHEDULED_QUERY")

    def test_additional_context_exceeding_limit_returns_422(self, client):
        """Test POST /standalone with additional_context exceeding 50,000 chars returns 422."""
        payload = {
            **VALID_STANDALONE_WITH_CONTEXT,
            "additional_context": CONTEXT_EXCEEDS_LIMIT,
        }
        resp = client.post("/api/conversions/standalone", json=payload)

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/conversions/jobs/{job_id}/logs
# ---------------------------------------------------------------------------


class TestGetJobLogsIntegration:
    """Integration tests for GET /api/conversions/jobs/{job_id}/logs."""

    def test_returns_log_entries_for_completed_job(self, client, db_session):
        """Test GET /jobs/{job_id}/logs returns correct log entries."""
        create_resp = client.post("/api/conversions/standalone", json=VALID_STANDALONE_WITH_CONTEXT)
        assert create_resp.status_code == 201
        job_id = create_resp.json()["id"]

        resp = client.get(f"/api/conversions/jobs/{job_id}/logs")

        assert resp.status_code == 200
        body = resp.json()
        # Should have at least some log entries from the conversion process
        assert isinstance(body, list)
        if len(body) > 0:
            log_entry = body[0]
            assert "step_name" in log_entry
            assert "log_level" in log_entry
            assert "message" in log_entry
            assert "timestamp" in log_entry

    def test_returns_404_for_nonexistent_job(self, client):
        """Test GET /jobs/{job_id}/logs returns 404 for non-existent job."""
        resp = client.get("/api/conversions/jobs/99999/logs")

        assert resp.status_code == 404
        assert "99999" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/conversions/batches
# ---------------------------------------------------------------------------


class TestListBatchesIntegration:
    """Integration tests for GET /api/conversions/batches."""

    # Batch payload with properly-cased dialects for integration tests
    _VALID_BATCH = {
        **VALID_BATCH_CONVERSION,
        "source_dialect": "Bigquery",
        "target_dialect": "Redshift",
    }

    def test_returns_paginated_results(self, client, db_session):
        """Test GET /batches returns paginated results."""
        # Create a batch first
        client.post("/api/conversions/batch", json=self._VALID_BATCH)

        resp = client.get("/api/conversions/batches")

        assert resp.status_code == 200
        body = resp.json()
        assert "batches" in body
        assert "total" in body
        assert "page" in body
        assert "page_size" in body
        assert body["total"] >= 1
        assert len(body["batches"]) >= 1

    def test_empty_workspace_returns_empty(self, client_workspace2):
        """Test GET /batches returns empty list for workspace with no batches."""
        resp = client_workspace2.get("/api/conversions/batches")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["batches"] == []


# ---------------------------------------------------------------------------
# DELETE /api/conversions/batches/{batch_id}
# ---------------------------------------------------------------------------


class TestDeleteBatchIntegration:
    """Integration tests for DELETE /api/conversions/batches/{batch_id}."""

    # Batch payload with properly-cased dialects for integration tests
    _VALID_BATCH = {
        **VALID_BATCH_CONVERSION,
        "source_dialect": "Bigquery",
        "target_dialect": "Redshift",
    }

    def test_delete_batch_cascades_to_jobs(self, client, db_session):
        """Test DELETE /batches/{batch_id} cascades to jobs."""
        create_resp = client.post("/api/conversions/batch", json=self._VALID_BATCH)
        assert create_resp.status_code == 201
        batch_id = create_resp.json()["id"]

        # Verify jobs exist
        db_session.expire_all()
        jobs_before = db_session.query(ConversionJob).filter_by(batch_id=batch_id).all()
        assert len(jobs_before) >= 1

        # Delete the batch
        resp = client.delete(f"/api/conversions/batches/{batch_id}")

        assert resp.status_code == 200
        assert str(batch_id) in resp.json()["message"]

        # Verify batch and jobs are gone
        db_session.expire_all()
        batch = db_session.query(ConversionBatch).filter_by(id=batch_id).first()
        assert batch is None
        jobs_after = db_session.query(ConversionJob).filter_by(batch_id=batch_id).all()
        assert len(jobs_after) == 0

    def test_delete_nonexistent_batch_returns_404(self, client):
        """Test DELETE /batches/{batch_id} returns 404 for non-existent batch."""
        resp = client.delete("/api/conversions/batches/99999")

        assert resp.status_code == 404
        assert "99999" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# DELETE /api/conversions/jobs/bulk
# ---------------------------------------------------------------------------


class TestBulkDeleteJobsIntegration:
    """Integration tests for DELETE /api/conversions/jobs/bulk."""

    def test_bulk_delete_removes_selected_jobs(self, client, db_session):
        """Test DELETE /jobs/bulk removes selected jobs."""
        # Create multiple jobs
        resp1 = client.post("/api/conversions/standalone", json=VALID_STANDALONE_WITH_CONTEXT)
        resp2 = client.post("/api/conversions/standalone", json=VALID_STANDALONE_WITH_CONTEXT)
        resp3 = client.post("/api/conversions/standalone", json=VALID_STANDALONE_WITH_CONTEXT)
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp3.status_code == 201

        job_id_1 = resp1.json()["id"]
        job_id_2 = resp2.json()["id"]
        job_id_3 = resp3.json()["id"]

        # Delete first two
        resp = client.request(
            "DELETE",
            "/api/conversions/jobs/bulk",
            json={"job_ids": [job_id_1, job_id_2]},
        )

        assert resp.status_code == 200
        assert resp.json()["deleted_count"] == 2

        # Verify deleted jobs are gone, third remains
        db_session.expire_all()
        assert db_session.query(ConversionJob).filter_by(id=job_id_1).first() is None
        assert db_session.query(ConversionJob).filter_by(id=job_id_2).first() is None
        assert db_session.query(ConversionJob).filter_by(id=job_id_3).first() is not None

    def test_bulk_delete_workspace_isolation(self, client, client_workspace2, db_session):
        """Test DELETE /jobs/bulk does not delete jobs from other workspaces."""
        # Create a job in workspace 1
        resp = client.post("/api/conversions/standalone", json=VALID_STANDALONE_WITH_CONTEXT)
        assert resp.status_code == 201
        job_id = resp.json()["id"]

        # Try to delete from workspace 2
        resp2 = client_workspace2.request(
            "DELETE",
            "/api/conversions/jobs/bulk",
            json={"job_ids": [job_id]},
        )

        assert resp2.status_code == 200
        assert resp2.json()["deleted_count"] == 0

        # Verify job still exists
        db_session.expire_all()
        assert db_session.query(ConversionJob).filter_by(id=job_id).first() is not None
