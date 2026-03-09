"""
Unit tests for ConversionRouter (standalone, job, and batch endpoints).

Uses FastAPI TestClient with an in-memory SQLite database and mocked
ConversionService to validate HTTP status codes, request validation,
workspace isolation, and response shapes.
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from models.connection import Connection
from models.conversion_batch import ConversionBatch
from models.conversion_job import ConversionJob
from routers.conversion_router import router, get_workspace_id
from shared.middleware.auth_middleware import CurrentUser, get_current_user
from tests.fixtures.sample_payloads import (
    VALID_BATCH_CONVERSION,
    VALID_DEPLOY_REQUEST,
    VALID_S3_EXPORT,
    VALID_STANDALONE_CONVERSION,
    VALID_STANDALONE_CONVERSION_MINIMAL,
)


# ── Test app setup ────────────────────────────────────────────────────

@pytest.fixture()
def db_engine():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    # Seed connection rows required by FK constraints
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
def fake_current_user():
    return CurrentUser(user_id=1, username="testuser", role="user", organization_id=1)


@pytest.fixture()
def client(db_session, fake_current_user):
    """Create a TestClient with overridden dependencies."""
    app = FastAPI()
    app.include_router(router)

    def _override_get_db():
        yield db_session

    def _override_get_current_user():
        return fake_current_user

    def _override_get_workspace_id():
        return 1

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_workspace_id] = _override_get_workspace_id

    return TestClient(app)


def _make_job(workspace_id=1, **overrides):
    """Helper to build a ConversionJob ORM instance for mocking."""
    defaults = dict(
        id=1,
        workspace_id=workspace_id,
        batch_id=None,
        source_code="SELECT 1",
        target_code="SELECT 1",
        source_dialect="bigquery",
        target_dialect="redshift",
        asset_type="TABLE_DDL",
        asset_name="my_table",
        bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
        aws_region="us-east-1",
        prompt_template_path="s3://bucket/template.txt",
        use_sqlglot=False,
        sqlglot_success=None,
        status="completed",
        error_message=None,
        retry_count=0,
        created_by="testuser",
        created_at=datetime(2026, 1, 25, 10, 0, 0),
        updated_at=datetime(2026, 1, 25, 10, 0, 0),
    )
    defaults.update(overrides)
    job = MagicMock(spec=ConversionJob)
    for k, v in defaults.items():
        setattr(job, k, v)
    return job


# ── POST /api/conversions/standalone ──────────────────────────────────


class TestCreateStandaloneConversion:
    """Tests for POST /api/conversions/standalone"""

    @patch("routers.conversion_router._build_service")
    def test_success_returns_201(self, mock_build, client):
        """Test POST /standalone with valid payload returns 201"""
        mock_svc = MagicMock()
        mock_svc.create_standalone_conversion.return_value = _make_job()
        mock_build.return_value = mock_svc

        resp = client.post("/api/conversions/standalone", json=VALID_STANDALONE_CONVERSION)

        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == 1
        assert body["status"] == "completed"
        assert body["source_dialect"] == "bigquery"
        assert body["target_dialect"] == "redshift"

    @patch("routers.conversion_router._build_service")
    def test_minimal_payload_returns_201(self, mock_build, client):
        """Test POST /standalone with minimal valid payload returns 201"""
        mock_svc = MagicMock()
        mock_svc.create_standalone_conversion.return_value = _make_job(
            asset_name=None, aws_region="us-west-2",
            bedrock_model="anthropic.claude-3-haiku-20240307-v1:0",
        )
        mock_build.return_value = mock_svc

        resp = client.post("/api/conversions/standalone", json=VALID_STANDALONE_CONVERSION_MINIMAL)

        assert resp.status_code == 201

    def test_missing_source_code_returns_422(self, client):
        """Test POST /standalone with missing required field returns 422"""
        payload = {**VALID_STANDALONE_CONVERSION}
        del payload["source_code"]

        resp = client.post("/api/conversions/standalone", json=payload)

        assert resp.status_code == 422

    def test_invalid_asset_type_returns_422(self, client):
        """Test POST /standalone with invalid asset_type returns 422"""
        payload = {**VALID_STANDALONE_CONVERSION, "asset_type": "INVALID_TYPE"}

        resp = client.post("/api/conversions/standalone", json=payload)

        assert resp.status_code == 422

    def test_empty_source_code_returns_422(self, client):
        """Test POST /standalone with empty source_code returns 422"""
        payload = {**VALID_STANDALONE_CONVERSION, "source_code": ""}

        resp = client.post("/api/conversions/standalone", json=payload)

        assert resp.status_code == 422

    @patch("routers.conversion_router._build_service")
    def test_value_error_returns_400(self, mock_build, client):
        """Test POST /standalone returns 400 when service raises ValueError"""
        mock_svc = MagicMock()
        mock_svc.create_standalone_conversion.side_effect = ValueError("Bad input")
        mock_build.return_value = mock_svc

        resp = client.post("/api/conversions/standalone", json=VALID_STANDALONE_CONVERSION)

        assert resp.status_code == 400
        assert "Bad input" in resp.json()["detail"]

    @patch("routers.conversion_router._build_service")
    def test_unexpected_error_returns_500(self, mock_build, client):
        """Test POST /standalone returns 500 on unexpected exception"""
        mock_svc = MagicMock()
        mock_svc.create_standalone_conversion.side_effect = RuntimeError("boom")
        mock_build.return_value = mock_svc

        resp = client.post("/api/conversions/standalone", json=VALID_STANDALONE_CONVERSION)

        assert resp.status_code == 500


# ── GET /api/conversions/jobs ─────────────────────────────────────────


class TestListJobs:
    """Tests for GET /api/conversions/jobs"""

    @patch("routers.conversion_router._build_service")
    def test_list_jobs_returns_200(self, mock_build, client):
        """Test GET /jobs returns paginated results"""
        mock_svc = MagicMock()
        mock_svc.list_jobs.return_value = {
            "jobs": [_make_job(id=1), _make_job(id=2)],
            "total": 2,
            "page": 1,
            "page_size": 20,
        }
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/jobs")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["page"] == 1
        assert body["page_size"] == 20
        assert len(body["jobs"]) == 2

    @patch("routers.conversion_router._build_service")
    def test_list_jobs_with_filters(self, mock_build, client):
        """Test GET /jobs passes query params to service"""
        mock_svc = MagicMock()
        mock_svc.list_jobs.return_value = {
            "jobs": [_make_job()],
            "total": 1,
            "page": 2,
            "page_size": 5,
        }
        mock_build.return_value = mock_svc

        resp = client.get(
            "/api/conversions/jobs",
            params={
                "page": 2,
                "page_size": 5,
                "status_filter": "completed",
                "asset_type": "TABLE_DDL",
                "source_dialect": "bigquery",
            },
        )

        assert resp.status_code == 200
        mock_svc.list_jobs.assert_called_once_with(
            workspace_id=1,
            page=2,
            page_size=5,
            status="completed",
            asset_type="TABLE_DDL",
            source_dialect="bigquery",
            standalone_only=False,
        )

    @patch("routers.conversion_router._build_service")
    def test_list_jobs_empty_returns_200(self, mock_build, client):
        """Test GET /jobs returns empty list when no jobs exist"""
        mock_svc = MagicMock()
        mock_svc.list_jobs.return_value = {
            "jobs": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
        }
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/jobs")

        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["jobs"] == []


# ── GET /api/conversions/jobs/{job_id} ────────────────────────────────


class TestGetJob:
    """Tests for GET /api/conversions/jobs/{job_id}"""

    @patch("routers.conversion_router._build_service")
    def test_get_job_returns_200(self, mock_build, client):
        """Test GET /jobs/{job_id} returns job detail"""
        mock_svc = MagicMock()
        mock_svc.get_job.return_value = _make_job(id=42)
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/jobs/42")

        assert resp.status_code == 200
        assert resp.json()["id"] == 42

    @patch("routers.conversion_router._build_service")
    def test_get_job_not_found_returns_404(self, mock_build, client):
        """Test GET /jobs/{job_id} returns 404 for non-existent job"""
        mock_svc = MagicMock()
        mock_svc.get_job.return_value = None
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/jobs/999")

        assert resp.status_code == 404
        assert "999" in resp.json()["detail"]


# ── DELETE /api/conversions/jobs/{job_id} ─────────────────────────────


class TestDeleteJob:
    """Tests for DELETE /api/conversions/jobs/{job_id}"""

    @patch("routers.conversion_router._build_service")
    def test_delete_job_returns_200(self, mock_build, client):
        """Test DELETE /jobs/{job_id} returns 200 on success"""
        mock_svc = MagicMock()
        mock_svc.delete_job.return_value = True
        mock_build.return_value = mock_svc

        resp = client.delete("/api/conversions/jobs/42")

        assert resp.status_code == 200
        assert "42" in resp.json()["message"]

    @patch("routers.conversion_router._build_service")
    def test_delete_job_not_found_returns_404(self, mock_build, client):
        """Test DELETE /jobs/{job_id} returns 404 for non-existent job"""
        mock_svc = MagicMock()
        mock_svc.delete_job.return_value = False
        mock_build.return_value = mock_svc

        resp = client.delete("/api/conversions/jobs/999")

        assert resp.status_code == 404
        assert "999" in resp.json()["detail"]


def _make_batch(workspace_id=1, **overrides):
    """Helper to build a ConversionBatch ORM instance for mocking."""
    defaults = dict(
        id=1,
        workspace_id=workspace_id,
        batch_name=None,
        migration_project_id=1,
        source_connection_id=10,
        target_connection_id=20,
        bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
        aws_region="us-east-1",
        prompt_template_path="s3://bucket/template.txt",
        use_sqlglot=False,
        max_retries=3,
        status="pending",
        total_assets=2,
        completed_assets=0,
        failed_assets=0,
        created_by="testuser",
        created_at=datetime(2026, 1, 25, 10, 0, 0),
        updated_at=datetime(2026, 1, 25, 10, 0, 0),
    )
    defaults.update(overrides)
    batch = MagicMock(spec=ConversionBatch)
    for k, v in defaults.items():
        setattr(batch, k, v)
    return batch


# ── POST /api/conversions/batch ───────────────────────────────────────


class TestCreateBatchConversion:
    """Tests for POST /api/conversions/batch"""

    @patch("routers.conversion_router._build_service")
    def test_success_returns_201(self, mock_build, client):
        """Test POST /batch with valid payload returns 201 and starts background task"""
        mock_svc = MagicMock()
        mock_svc.create_batch_conversion.return_value = _make_batch()
        mock_build.return_value = mock_svc

        resp = client.post("/api/conversions/batch", json=VALID_BATCH_CONVERSION)

        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == 1
        assert body["status"] == "pending"
        assert body["total_assets"] == 2
        assert body["workspace_id"] == 1

    @patch("routers.conversion_router._build_service")
    def test_batch_response_includes_connection_ids(self, mock_build, client):
        """Test POST /batch response includes source and target connection IDs"""
        mock_svc = MagicMock()
        mock_svc.create_batch_conversion.return_value = _make_batch()
        mock_build.return_value = mock_svc

        resp = client.post("/api/conversions/batch", json=VALID_BATCH_CONVERSION)

        body = resp.json()
        assert body["source_connection_id"] == 10
        assert body["target_connection_id"] == 20
        assert body["bedrock_model"] == "anthropic.claude-3-sonnet-20240229-v1:0"

    def test_missing_assets_returns_422(self, client):
        """Test POST /batch with missing assets field returns 422"""
        payload = {**VALID_BATCH_CONVERSION}
        del payload["assets"]

        resp = client.post("/api/conversions/batch", json=payload)

        assert resp.status_code == 422

    def test_empty_assets_returns_422(self, client):
        """Test POST /batch with empty assets list returns 422"""
        payload = {**VALID_BATCH_CONVERSION, "assets": []}

        resp = client.post("/api/conversions/batch", json=payload)

        assert resp.status_code == 422

    @patch("routers.conversion_router._build_service")
    def test_value_error_returns_400(self, mock_build, client):
        """Test POST /batch returns 400 when service raises ValueError"""
        mock_svc = MagicMock()
        mock_svc.create_batch_conversion.side_effect = ValueError("Invalid project")
        mock_build.return_value = mock_svc

        resp = client.post("/api/conversions/batch", json=VALID_BATCH_CONVERSION)

        assert resp.status_code == 400
        assert "Invalid project" in resp.json()["detail"]

    @patch("routers.conversion_router._build_service")
    def test_unexpected_error_returns_500(self, mock_build, client):
        """Test POST /batch returns 500 on unexpected exception"""
        mock_svc = MagicMock()
        mock_svc.create_batch_conversion.side_effect = RuntimeError("boom")
        mock_build.return_value = mock_svc

        resp = client.post("/api/conversions/batch", json=VALID_BATCH_CONVERSION)

        assert resp.status_code == 500


# ── GET /api/conversions/batch/{batch_id} ─────────────────────────────


class TestGetBatch:
    """Tests for GET /api/conversions/batch/{batch_id}"""

    @patch("routers.conversion_router._build_service")
    def test_get_batch_returns_200(self, mock_build, client):
        """Test GET /batch/{batch_id} returns batch status"""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = _make_batch(id=5, status="completed", completed_assets=2)
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/batch/5")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 5
        assert body["status"] == "completed"
        assert body["completed_assets"] == 2

    @patch("routers.conversion_router._build_service")
    def test_get_batch_not_found_returns_404(self, mock_build, client):
        """Test GET /batch/{batch_id} returns 404 for non-existent batch"""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = None
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/batch/999")

        assert resp.status_code == 404
        assert "999" in resp.json()["detail"]


# ── GET /api/conversions/batch/{batch_id}/jobs ────────────────────────


class TestListBatchJobs:
    """Tests for GET /api/conversions/batch/{batch_id}/jobs"""

    @patch("routers.conversion_router._build_service")
    def test_list_batch_jobs_returns_200(self, mock_build, client):
        """Test GET /batch/{batch_id}/jobs returns list of jobs"""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = _make_batch(id=1)
        mock_svc.list_batch_jobs.return_value = [
            _make_job(id=10, batch_id=1),
            _make_job(id=11, batch_id=1),
        ]
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/batch/1/jobs")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["id"] == 10
        assert body[1]["id"] == 11

    @patch("routers.conversion_router._build_service")
    def test_list_batch_jobs_empty(self, mock_build, client):
        """Test GET /batch/{batch_id}/jobs returns empty list when no jobs"""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = _make_batch(id=1)
        mock_svc.list_batch_jobs.return_value = []
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/batch/1/jobs")

        assert resp.status_code == 200
        assert resp.json() == []

    @patch("routers.conversion_router._build_service")
    def test_list_batch_jobs_batch_not_found(self, mock_build, client):
        """Test GET /batch/{batch_id}/jobs returns 404 when batch not found"""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = None
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/batch/999/jobs")

        assert resp.status_code == 404


# ── POST /api/conversions/batch/{batch_id}/export/sql ─────────────────


class TestExportBatchSql:
    """Tests for POST /api/conversions/batch/{batch_id}/export/sql"""

    @patch("routers.conversion_router.ExportService")
    @patch("routers.conversion_router._build_service")
    def test_export_sql_returns_streaming_response(self, mock_build, mock_export_cls, client):
        """Test POST /batch/{batch_id}/export/sql returns .sql file download"""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = _make_batch(id=1)
        mock_svc.list_batch_jobs.return_value = [_make_job(id=10, batch_id=1)]
        mock_build.return_value = mock_svc

        mock_export = MagicMock()
        mock_export.generate_batch_sql.return_value = b"-- Asset: my_table (TABLE_DDL)\nSELECT 1"
        mock_export_cls.return_value = mock_export

        resp = client.post("/api/conversions/batch/1/export/sql")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/sql"
        assert "batch_1_export.sql" in resp.headers["content-disposition"]
        assert b"SELECT 1" in resp.content

    @patch("routers.conversion_router._build_service")
    def test_export_sql_batch_not_found(self, mock_build, client):
        """Test POST /batch/{batch_id}/export/sql returns 404 when batch not found"""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = None
        mock_build.return_value = mock_svc

        resp = client.post("/api/conversions/batch/999/export/sql")

        assert resp.status_code == 404


# ── POST /api/conversions/batch/{batch_id}/export/s3 ──────────────────


class TestExportBatchS3:
    """Tests for POST /api/conversions/batch/{batch_id}/export/s3"""

    @patch("routers.conversion_router.ExportService")
    @patch("routers.conversion_router._build_service")
    def test_export_s3_returns_200(self, mock_build, mock_export_cls, client):
        """Test POST /batch/{batch_id}/export/s3 returns success message"""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = _make_batch(id=1)
        mock_svc.list_batch_jobs.return_value = [_make_job(id=10, batch_id=1)]
        mock_build.return_value = mock_svc

        mock_export = MagicMock()
        mock_export_cls.return_value = mock_export

        resp = client.post("/api/conversions/batch/1/export/s3", json=VALID_S3_EXPORT)

        assert resp.status_code == 200
        assert "exported" in resp.json()["message"].lower()

    @patch("routers.conversion_router._build_service")
    def test_export_s3_batch_not_found(self, mock_build, client):
        """Test POST /batch/{batch_id}/export/s3 returns 404 when batch not found"""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = None
        mock_build.return_value = mock_svc

        resp = client.post("/api/conversions/batch/999/export/s3", json=VALID_S3_EXPORT)

        assert resp.status_code == 404

    def test_export_s3_missing_s3_path_returns_422(self, client):
        """Test POST /batch/{batch_id}/export/s3 with missing s3_path returns 422"""
        resp = client.post("/api/conversions/batch/1/export/s3", json={"region": "us-east-1"})

        assert resp.status_code == 422

    @patch("routers.conversion_router.ExportService")
    @patch("routers.conversion_router._build_service")
    def test_export_s3_invalid_path_returns_400(self, mock_build, mock_export_cls, client):
        """Test POST /batch/{batch_id}/export/s3 returns 400 for invalid S3 path"""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = _make_batch(id=1)
        mock_svc.list_batch_jobs.return_value = []
        mock_build.return_value = mock_svc

        mock_export = MagicMock()
        mock_export.export_to_s3.side_effect = ValueError("Invalid S3 path")
        mock_export_cls.return_value = mock_export

        resp = client.post(
            "/api/conversions/batch/1/export/s3",
            json={"s3_path": "not-s3://bad", "region": "us-east-1"},
        )

        assert resp.status_code == 400


# ── POST /api/conversions/batch/{batch_id}/deploy ─────────────────────


class TestDeployBatch:
    """Tests for POST /api/conversions/batch/{batch_id}/deploy"""

    @staticmethod
    def _make_connection(**overrides):
        """Build a mock Connection object."""
        defaults = dict(
            id=20, name="tgt_conn", type="redshift", database="tgt_db",
            connection_params={"host": "localhost"}, connection_params_encrypted=None,
            created_by="system", status="connected", last_tested_at=None,
            created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
            is_active=True,
        )
        defaults.update(overrides)
        conn = MagicMock(spec=Connection)
        for k, v in defaults.items():
            setattr(conn, k, v)
        return conn

    @patch("routers.conversion_router.DeployService")
    @patch("routers.conversion_router._build_service")
    def test_deploy_success_returns_200(self, mock_build, mock_deploy_cls, client):
        """Test POST /batch/{batch_id}/deploy returns deploy result on success"""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = _make_batch(id=1)
        mock_svc.list_batch_jobs.return_value = [_make_job(id=10, batch_id=1)]
        mock_build.return_value = mock_svc

        from services.conversion_deploy_service import DeployResult
        mock_deploy = MagicMock()
        mock_deploy.deploy_batch.return_value = DeployResult(
            success=True,
            deployed_assets=["my_table"],
        )
        mock_deploy_cls.return_value = mock_deploy

        # Mock the db.query(Connection) call in the endpoint
        with patch("routers.conversion_router.Connection") as mock_conn_model:
            mock_query = MagicMock()
            mock_query.filter.return_value.first.return_value = self._make_connection()
            # The endpoint calls db.query(Connection), so we need to patch the
            # session's query method via the dependency override. Instead, we
            # patch at the module level so db.query(Connection) returns our mock.
            with patch("routers.conversion_router.Session") as _:
                pass  # not needed, we patch differently

        # Simpler approach: patch the db session's query
        with patch("routers.conversion_router.Connection") as mock_conn_cls:
            # We need the actual endpoint to find the connection. The endpoint
            # does db.query(Connection).filter(...).first(). Since db is the
            # overridden session, we mock it on the session object.
            pass

        # Best approach: use a client whose db_session has the connections table
        # But since the existing fixture already seeds connections, the issue is
        # that Base.metadata.create_all doesn't include Connection. Let's just
        # mock the entire db.query chain.
        resp = None
        with patch("routers.conversion_router.DeployService", mock_deploy_cls):
            with patch("routers.conversion_router._build_service", return_value=mock_svc):
                # We need to intercept the db.query call. The simplest way is
                # to create a new client with a mocked db.
                mock_db = MagicMock()
                mock_db.query.return_value.filter.return_value.first.return_value = self._make_connection()

                app = FastAPI()
                app.include_router(router)
                app.dependency_overrides[get_db] = lambda: (yield mock_db).__next__() or mock_db
                app.dependency_overrides[get_current_user] = lambda: CurrentUser(
                    user_id=1, username="testuser", role="user", organization_id=1,
                )
                app.dependency_overrides[get_workspace_id] = lambda: 1

                def _override_db():
                    yield mock_db

                app.dependency_overrides[get_db] = _override_db
                test_client = TestClient(app)
                resp = test_client.post("/api/conversions/batch/1/deploy", json=VALID_DEPLOY_REQUEST)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "my_table" in body["deployed_assets"]
        assert body["failed_asset"] is None

    @patch("routers.conversion_router.DeployService")
    @patch("routers.conversion_router._build_service")
    def test_deploy_partial_failure(self, mock_build, mock_deploy_cls, client):
        """Test POST /batch/{batch_id}/deploy returns partial failure result"""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = _make_batch(id=1)
        mock_svc.list_batch_jobs.return_value = [_make_job(id=10), _make_job(id=11)]
        mock_build.return_value = mock_svc

        from services.conversion_deploy_service import DeployResult
        mock_deploy = MagicMock()
        mock_deploy.deploy_batch.return_value = DeployResult(
            success=False,
            deployed_assets=["table_a"],
            failed_asset="view_b",
            error_message="syntax error",
        )
        mock_deploy_cls.return_value = mock_deploy

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = self._make_connection()

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: iter([mock_db])
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            user_id=1, username="testuser", role="user", organization_id=1,
        )
        app.dependency_overrides[get_workspace_id] = lambda: 1

        def _override_db():
            yield mock_db

        app.dependency_overrides[get_db] = _override_db
        test_client = TestClient(app)
        resp = test_client.post("/api/conversions/batch/1/deploy", json=VALID_DEPLOY_REQUEST)

        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is False
        assert body["failed_asset"] == "view_b"
        assert body["error_message"] == "syntax error"

    @patch("routers.conversion_router._build_service")
    def test_deploy_batch_not_found(self, mock_build, client):
        """Test POST /batch/{batch_id}/deploy returns 404 when batch not found"""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = None
        mock_build.return_value = mock_svc

        resp = client.post("/api/conversions/batch/999/deploy", json=VALID_DEPLOY_REQUEST)

        assert resp.status_code == 404

    @patch("routers.conversion_router._build_service")
    def test_deploy_connection_not_found(self, mock_build, client):
        """Test POST /batch/{batch_id}/deploy returns 404 when target connection not found"""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = _make_batch(id=1)
        mock_build.return_value = mock_svc

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        app = FastAPI()
        app.include_router(router)

        def _override_db():
            yield mock_db

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            user_id=1, username="testuser", role="user", organization_id=1,
        )
        app.dependency_overrides[get_workspace_id] = lambda: 1
        test_client = TestClient(app)

        resp = test_client.post(
            "/api/conversions/batch/1/deploy",
            json={"target_connection_id": 9999},
        )

        assert resp.status_code == 404
        assert "9999" in resp.json()["detail"]


# ── GET /api/conversions/models ───────────────────────────────────────


class TestListBedrockModels:
    """Tests for GET /api/conversions/models"""

    @patch("routers.conversion_router._build_service")
    def test_list_models_returns_200(self, mock_build, client):
        """Test GET /models?region=us-east-1 returns list of models"""
        from services.bedrock_client import BedrockModel

        mock_svc = MagicMock()
        mock_svc.list_bedrock_models.return_value = [
            BedrockModel(model_id="anthropic.claude-3-sonnet-20240229-v1:0", model_name="Claude 3 Sonnet", provider="Anthropic"),
            BedrockModel(model_id="amazon.titan-text-express-v1", model_name="Titan Text Express", provider="Amazon"),
        ]
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/models", params={"region": "us-east-1"})

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["model_id"] == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert body[0]["model_name"] == "Claude 3 Sonnet"
        assert body[0]["provider"] == "Anthropic"
        assert body[1]["model_id"] == "amazon.titan-text-express-v1"

    @patch("routers.conversion_router._build_service")
    def test_list_models_empty_returns_200(self, mock_build, client):
        """Test GET /models returns empty list when no models available"""
        mock_svc = MagicMock()
        mock_svc.list_bedrock_models.return_value = []
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/models", params={"region": "eu-west-1"})

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_models_missing_region_returns_422(self, client):
        """Test GET /models without region query param returns 422"""
        resp = client.get("/api/conversions/models")

        assert resp.status_code == 422

    @patch("routers.conversion_router._build_service")
    def test_list_models_passes_region_to_service(self, mock_build, client):
        """Test GET /models passes region query param to service"""
        mock_svc = MagicMock()
        mock_svc.list_bedrock_models.return_value = []
        mock_build.return_value = mock_svc

        client.get("/api/conversions/models", params={"region": "ap-southeast-1"})

        mock_svc.list_bedrock_models.assert_called_once_with(region="ap-southeast-1")

    @patch("routers.conversion_router._build_service")
    def test_list_models_service_error_returns_500(self, mock_build, client):
        """Test GET /models returns 500 when service raises unexpected error"""
        mock_svc = MagicMock()
        mock_svc.list_bedrock_models.side_effect = RuntimeError("AWS connection failed")
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/models", params={"region": "us-east-1"})

        assert resp.status_code == 500
        assert "error occurred" in resp.json()["detail"].lower()


# ── Audit logging tests for router-level operations ───────────────────


class TestRouterAuditLogging:
    """Test that router-level operations (export, deploy) log audit events."""

    @patch("routers.conversion_router.AuditLogger")
    @patch("routers.conversion_router.ExportService")
    @patch("routers.conversion_router._build_service")
    def test_export_sql_logs_audit(self, mock_build, mock_export_cls, mock_audit_cls, client):
        """Test POST /batch/{batch_id}/export/sql logs audit event."""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = _make_batch(id=1)
        mock_svc.list_batch_jobs.return_value = [_make_job(id=10, batch_id=1)]
        mock_build.return_value = mock_svc

        mock_export = MagicMock()
        mock_export.generate_batch_sql.return_value = b"SELECT 1"
        mock_export_cls.return_value = mock_export

        mock_audit = MagicMock()
        mock_audit_cls.return_value = mock_audit

        resp = client.post("/api/conversions/batch/1/export/sql")

        assert resp.status_code == 200
        mock_audit.log_data_modification.assert_called_once_with(
            user_id=1,
            username="testuser",
            workspace_id=1,
            resource_type="conversion_batch",
            resource_id=1,
            action="export",
        )

    @patch("routers.conversion_router.AuditLogger")
    @patch("routers.conversion_router.ExportService")
    @patch("routers.conversion_router._build_service")
    def test_export_s3_logs_audit(self, mock_build, mock_export_cls, mock_audit_cls, client):
        """Test POST /batch/{batch_id}/export/s3 logs audit event."""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = _make_batch(id=2)
        mock_svc.list_batch_jobs.return_value = [_make_job(id=10, batch_id=2)]
        mock_build.return_value = mock_svc

        mock_export = MagicMock()
        mock_export_cls.return_value = mock_export

        mock_audit = MagicMock()
        mock_audit_cls.return_value = mock_audit

        resp = client.post("/api/conversions/batch/2/export/s3", json=VALID_S3_EXPORT)

        assert resp.status_code == 200
        mock_audit.log_data_modification.assert_called_once_with(
            user_id=1,
            username="testuser",
            workspace_id=1,
            resource_type="conversion_batch",
            resource_id=2,
            action="export",
        )

    @patch("routers.conversion_router.AuditLogger")
    @patch("routers.conversion_router.DeployService")
    @patch("routers.conversion_router._build_service")
    def test_deploy_logs_audit(self, mock_build, mock_deploy_cls, mock_audit_cls, client):
        """Test POST /batch/{batch_id}/deploy logs audit event."""
        mock_svc = MagicMock()
        mock_svc.get_batch.return_value = _make_batch(id=3)
        mock_svc.list_batch_jobs.return_value = [_make_job(id=10, batch_id=3)]
        mock_build.return_value = mock_svc

        from services.conversion_deploy_service import DeployResult
        mock_deploy = MagicMock()
        mock_deploy.deploy_batch.return_value = DeployResult(
            success=True, deployed_assets=["my_table"],
        )
        mock_deploy_cls.return_value = mock_deploy

        mock_audit = MagicMock()
        mock_audit_cls.return_value = mock_audit

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(id=20)

        app = FastAPI()
        app.include_router(router)

        def _override_db():
            yield mock_db

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            user_id=1, username="testuser", role="user", organization_id=1,
        )
        app.dependency_overrides[get_workspace_id] = lambda: 1
        test_client = TestClient(app)

        resp = test_client.post("/api/conversions/batch/3/deploy", json=VALID_DEPLOY_REQUEST)

        assert resp.status_code == 200
        mock_audit.log_data_modification.assert_called_once_with(
            user_id=1,
            username="testuser",
            workspace_id=1,
            resource_type="conversion_batch",
            resource_id=3,
            action="deploy",
        )

    @patch("routers.conversion_router.AuditLogger")
    @patch("routers.conversion_router._build_service")
    def test_delete_job_passes_user_id(self, mock_build, mock_audit_cls, client):
        """Test DELETE /jobs/{job_id} passes user_id to service.delete_job."""
        mock_svc = MagicMock()
        mock_svc.delete_job.return_value = True
        mock_build.return_value = mock_svc

        resp = client.delete("/api/conversions/jobs/42")

        assert resp.status_code == 200
        mock_svc.delete_job.assert_called_once_with(
            job_id=42, workspace_id=1, user_id="1",
        )


# ── Helpers for new endpoints ─────────────────────────────────────────

def _make_log(job_id=1, **overrides):
    """Helper to build a ConversionLog ORM instance for mocking."""
    from models.conversion_log import ConversionLog

    defaults = dict(
        id=1,
        job_id=job_id,
        workspace_id=1,
        timestamp=datetime(2026, 1, 25, 10, 0, 0),
        log_level="INFO",
        step_name="template_loaded",
        message="Prompt template loaded",
        duration_ms=120,
    )
    defaults.update(overrides)
    log = MagicMock(spec=ConversionLog)
    for k, v in defaults.items():
        setattr(log, k, v)
    return log


# ── GET /api/conversions/jobs/{job_id}/logs ───────────────────────────


class TestGetJobLogs:
    """Tests for GET /api/conversions/jobs/{job_id}/logs"""

    @patch("routers.conversion_router._build_service")
    def test_get_logs_returns_200_with_entries(self, mock_build, client):
        """Test GET /jobs/{job_id}/logs returns 200 with log entries for valid job"""
        mock_svc = MagicMock()
        mock_svc.get_job.return_value = _make_job(id=1)
        mock_svc.get_job_logs.return_value = [
            _make_log(id=1, job_id=1, step_name="template_loaded", message="Template loaded"),
            _make_log(id=2, job_id=1, step_name="bedrock_invocation_started", message="Bedrock started"),
        ]
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/jobs/1/logs")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 2
        assert body[0]["step_name"] == "template_loaded"
        assert body[1]["step_name"] == "bedrock_invocation_started"
        assert body[0]["job_id"] == 1

    @patch("routers.conversion_router._build_service")
    def test_get_logs_returns_404_for_nonexistent_job(self, mock_build, client):
        """Test GET /jobs/{job_id}/logs returns 404 for non-existent job"""
        mock_svc = MagicMock()
        mock_svc.get_job.return_value = None
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/jobs/999/logs")

        assert resp.status_code == 404
        assert "999" in resp.json()["detail"]

    @patch("routers.conversion_router._build_service")
    def test_get_logs_returns_empty_list_for_job_with_no_logs(self, mock_build, client):
        """Test GET /jobs/{job_id}/logs returns empty list when job has no logs"""
        mock_svc = MagicMock()
        mock_svc.get_job.return_value = _make_job(id=5)
        mock_svc.get_job_logs.return_value = []
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/jobs/5/logs")

        assert resp.status_code == 200
        assert resp.json() == []

    @patch("routers.conversion_router._build_service")
    def test_get_logs_passes_workspace_id(self, mock_build, client):
        """Test GET /jobs/{job_id}/logs passes workspace_id to service"""
        mock_svc = MagicMock()
        mock_svc.get_job.return_value = _make_job(id=1)
        mock_svc.get_job_logs.return_value = []
        mock_build.return_value = mock_svc

        client.get("/api/conversions/jobs/1/logs")

        mock_svc.get_job.assert_called_once_with(job_id=1, workspace_id=1)
        mock_svc.get_job_logs.assert_called_once_with(job_id=1, workspace_id=1)


# ── GET /api/conversions/batches ──────────────────────────────────────


class TestListBatches:
    """Tests for GET /api/conversions/batches"""

    @patch("routers.conversion_router._build_service")
    def test_list_batches_returns_200_with_paginated_results(self, mock_build, client):
        """Test GET /batches returns paginated results with correct ordering"""
        mock_svc = MagicMock()
        mock_svc.list_batches.return_value = (
            [
                _make_batch(id=2, created_at=datetime(2026, 1, 26, 10, 0, 0)),
                _make_batch(id=1, created_at=datetime(2026, 1, 25, 10, 0, 0)),
            ],
            2,
        )
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/batches")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["page"] == 1
        assert body["page_size"] == 20
        assert len(body["batches"]) == 2
        assert body["batches"][0]["id"] == 2
        assert body["batches"][1]["id"] == 1

    @patch("routers.conversion_router._build_service")
    def test_list_batches_empty_returns_200(self, mock_build, client):
        """Test GET /batches returns empty list when no batches exist"""
        mock_svc = MagicMock()
        mock_svc.list_batches.return_value = ([], 0)
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/batches")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["batches"] == []

    @patch("routers.conversion_router._build_service")
    def test_list_batches_respects_pagination_params(self, mock_build, client):
        """Test GET /batches passes page and page_size to service"""
        mock_svc = MagicMock()
        mock_svc.list_batches.return_value = ([_make_batch(id=3)], 5)
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/batches", params={"page": 2, "page_size": 1})

        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 2
        assert body["page_size"] == 1
        mock_svc.list_batches.assert_called_once_with(
            workspace_id=1, page=2, page_size=1,
        )

    @patch("routers.conversion_router._build_service")
    def test_list_batches_service_error_returns_500(self, mock_build, client):
        """Test GET /batches returns 500 on unexpected exception"""
        mock_svc = MagicMock()
        mock_svc.list_batches.side_effect = RuntimeError("DB error")
        mock_build.return_value = mock_svc

        resp = client.get("/api/conversions/batches")

        assert resp.status_code == 500


# ── DELETE /api/conversions/batches/{batch_id} ────────────────────────


class TestDeleteBatch:
    """Tests for DELETE /api/conversions/batches/{batch_id}"""

    @patch("routers.conversion_router._build_service")
    def test_delete_batch_returns_200(self, mock_build, client):
        """Test DELETE /batches/{batch_id} returns 200 and removes batch"""
        mock_svc = MagicMock()
        mock_svc.delete_batch.return_value = True
        mock_build.return_value = mock_svc

        resp = client.delete("/api/conversions/batches/42")

        assert resp.status_code == 200
        assert "42" in resp.json()["message"]

    @patch("routers.conversion_router._build_service")
    def test_delete_batch_not_found_returns_404(self, mock_build, client):
        """Test DELETE /batches/{batch_id} returns 404 for non-existent batch"""
        mock_svc = MagicMock()
        mock_svc.delete_batch.return_value = False
        mock_build.return_value = mock_svc

        resp = client.delete("/api/conversions/batches/999")

        assert resp.status_code == 404
        assert "999" in resp.json()["detail"]

    @patch("routers.conversion_router._build_service")
    def test_delete_batch_passes_workspace_id(self, mock_build, client):
        """Test DELETE /batches/{batch_id} passes workspace_id to service"""
        mock_svc = MagicMock()
        mock_svc.delete_batch.return_value = True
        mock_build.return_value = mock_svc

        client.delete("/api/conversions/batches/7")

        mock_svc.delete_batch.assert_called_once_with(batch_id=7, workspace_id=1)


# ── DELETE /api/conversions/jobs/bulk ─────────────────────────────────


class TestBulkDeleteJobs:
    """Tests for DELETE /api/conversions/jobs/bulk"""

    @patch("routers.conversion_router._build_service")
    def test_bulk_delete_returns_200_with_count(self, mock_build, client):
        """Test DELETE /jobs/bulk returns 200 and removes specified jobs"""
        mock_svc = MagicMock()
        mock_svc.bulk_delete_jobs.return_value = 3
        mock_build.return_value = mock_svc

        resp = client.request(
            "DELETE",
            "/api/conversions/jobs/bulk",
            json={"job_ids": [1, 2, 3]},
        )

        assert resp.status_code == 200
        assert resp.json()["deleted_count"] == 3

    @patch("routers.conversion_router._build_service")
    def test_bulk_delete_empty_list_returns_200(self, mock_build, client):
        """Test DELETE /jobs/bulk with empty job_ids returns 200 with 0 deleted"""
        mock_svc = MagicMock()
        mock_svc.bulk_delete_jobs.return_value = 0
        mock_build.return_value = mock_svc

        resp = client.request(
            "DELETE",
            "/api/conversions/jobs/bulk",
            json={"job_ids": []},
        )

        assert resp.status_code == 200
        assert resp.json()["deleted_count"] == 0

    @patch("routers.conversion_router._build_service")
    def test_bulk_delete_passes_workspace_id(self, mock_build, client):
        """Test DELETE /jobs/bulk passes workspace_id to service"""
        mock_svc = MagicMock()
        mock_svc.bulk_delete_jobs.return_value = 2
        mock_build.return_value = mock_svc

        client.request(
            "DELETE",
            "/api/conversions/jobs/bulk",
            json={"job_ids": [10, 20]},
        )

        mock_svc.bulk_delete_jobs.assert_called_once_with(
            job_ids=[10, 20], workspace_id=1,
        )

    def test_bulk_delete_missing_body_returns_422(self, client):
        """Test DELETE /jobs/bulk without request body returns 422"""
        resp = client.request("DELETE", "/api/conversions/jobs/bulk")

        assert resp.status_code == 422

    @patch("routers.conversion_router._build_service")
    def test_bulk_delete_service_error_returns_500(self, mock_build, client):
        """Test DELETE /jobs/bulk returns 500 on unexpected exception"""
        mock_svc = MagicMock()
        mock_svc.bulk_delete_jobs.side_effect = RuntimeError("DB error")
        mock_build.return_value = mock_svc

        resp = client.request(
            "DELETE",
            "/api/conversions/jobs/bulk",
            json={"job_ids": [1]},
        )

        assert resp.status_code == 500


# ── Workspace isolation for new endpoints ─────────────────────────────


class TestNewEndpointsWorkspaceIsolation:
    """Test workspace isolation on all new endpoints."""

    @patch("routers.conversion_router._build_service")
    def test_get_logs_uses_workspace_id(self, mock_build, client):
        """Test GET /jobs/{job_id}/logs scopes to workspace_id"""
        mock_svc = MagicMock()
        mock_svc.get_job.return_value = _make_job(id=1)
        mock_svc.get_job_logs.return_value = []
        mock_build.return_value = mock_svc

        client.get("/api/conversions/jobs/1/logs")

        mock_svc.get_job.assert_called_once_with(job_id=1, workspace_id=1)

    @patch("routers.conversion_router._build_service")
    def test_list_batches_uses_workspace_id(self, mock_build, client):
        """Test GET /batches scopes to workspace_id"""
        mock_svc = MagicMock()
        mock_svc.list_batches.return_value = ([], 0)
        mock_build.return_value = mock_svc

        client.get("/api/conversions/batches")

        mock_svc.list_batches.assert_called_once_with(
            workspace_id=1, page=1, page_size=20,
        )

    @patch("routers.conversion_router._build_service")
    def test_delete_batch_uses_workspace_id(self, mock_build, client):
        """Test DELETE /batches/{batch_id} scopes to workspace_id"""
        mock_svc = MagicMock()
        mock_svc.delete_batch.return_value = True
        mock_build.return_value = mock_svc

        client.delete("/api/conversions/batches/1")

        mock_svc.delete_batch.assert_called_once_with(batch_id=1, workspace_id=1)

    @patch("routers.conversion_router._build_service")
    def test_bulk_delete_uses_workspace_id(self, mock_build, client):
        """Test DELETE /jobs/bulk scopes to workspace_id"""
        mock_svc = MagicMock()
        mock_svc.bulk_delete_jobs.return_value = 1
        mock_build.return_value = mock_svc

        client.request(
            "DELETE",
            "/api/conversions/jobs/bulk",
            json={"job_ids": [1]},
        )

        mock_svc.bulk_delete_jobs.assert_called_once_with(
            job_ids=[1], workspace_id=1,
        )
