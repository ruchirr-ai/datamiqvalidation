"""
Integration tests for BQ-to-Iceberg Migration API endpoints.

Uses a real in-memory SQLite database with SQLAlchemy and the actual
router → DB stack. External services (KMS, AWS) are mocked so the tests
can run without cloud credentials.

Tests cover:
- CRUD endpoints with valid and invalid payloads
- Lifecycle endpoints with state transitions
- Structure report and approval flow
- Cost analysis endpoints
- Workspace isolation (cannot access other workspace's migrations)
- Authentication and authorization
"""

import pytest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from database import Base, get_db
from models.migration_bq_iceberg import MigrationBQIceberg  # noqa: F401
from models.iceberg_table_validation import IcebergTableValidation  # noqa: F401
from models.bq_redshift_migration import MigrationLog  # noqa: F401
from models.bq_redshift_migration import Base as BQRedshiftBase  # noqa: F401

from routers.bq_iceberg_migration import router, connection_test_router
from shared.middleware.auth_middleware import CurrentUser, get_current_user, get_workspace_id


# ---------------------------------------------------------------------------
# SQLite Compatibility: Register type compilers for PostgreSQL-specific types
# ---------------------------------------------------------------------------

from sqlalchemy.ext.compiler import compiles


@compiles(ARRAY, "sqlite")
def _compile_array_sqlite(type_, compiler, **kw):
    """Compile PostgreSQL ARRAY as TEXT in SQLite."""
    return "TEXT"


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    """Compile PostgreSQL JSONB as TEXT in SQLite."""
    return "TEXT"


# ---------------------------------------------------------------------------
# Sample Payloads
# ---------------------------------------------------------------------------

VALID_CREATE_PAYLOAD_S3 = {
    "migration_name": "BQ to Iceberg S3 Migration",
    "pathway": "A",
    "source_project_id": "my-gcp-project",
    "source_dataset": "analytics",
    "destination_type": "iceberg_s3",
    "s3_bucket": "my-data-lake-bucket",
    "s3_path_prefix": "iceberg/analytics/",
    "aws_region": "us-east-1",
    "glue_database_name": "analytics_db",
}

VALID_CREATE_PAYLOAD_S3_TABLES = {
    "migration_name": "BQ to S3 Tables Migration",
    "pathway": "B",
    "source_project_id": "another-gcp-project",
    "source_dataset": "warehouse",
    "destination_type": "iceberg_s3_tables",
    "table_bucket_arn": "arn:aws:s3tables:us-east-1:123456789012:bucket/my-table-bucket",
    "s3_tables_namespace": "warehouse_ns",
    "aws_region": "us-east-1",
    "glue_database_name": "warehouse_db",
    "aws_role_arn": "arn:aws:iam::123456789012:role/DataMIQIcebergRole",
    "gcs_bucket": "gcs-export-bucket",
    "gcs_path": "exports/warehouse/",
    "gcs_region": "us-central1",
    "load_type": "incremental",
    "parallelism": 8,
    "enable_load_stage_verification": True,
}

VALID_CREATE_PAYLOAD_MINIMAL = {
    "migration_name": "Minimal Migration",
    "pathway": "C",
    "destination_type": "iceberg_s3",
    "aws_region": "eu-west-1",
    "glue_database_name": "default_db",
}

INVALID_PAYLOAD_MISSING_REQUIRED = {
    "migration_name": "Missing Fields",
    # Missing pathway, destination_type, aws_region, glue_database_name
}

INVALID_PAYLOAD_BAD_PATHWAY = {
    "migration_name": "Bad Pathway",
    "pathway": "X",
    "destination_type": "iceberg_s3",
    "aws_region": "us-east-1",
    "glue_database_name": "test_db",
}

INVALID_PAYLOAD_BAD_DESTINATION = {
    "migration_name": "Bad Destination",
    "pathway": "A",
    "destination_type": "invalid_type",
    "aws_region": "us-east-1",
    "glue_database_name": "test_db",
}

INVALID_PAYLOAD_BAD_GLUE_DB = {
    "migration_name": "Bad Glue DB",
    "pathway": "A",
    "destination_type": "iceberg_s3",
    "aws_region": "us-east-1",
    "glue_database_name": "INVALID-DB-NAME!",
}

INVALID_PAYLOAD_BAD_PARALLELISM = {
    "migration_name": "Bad Parallelism",
    "pathway": "A",
    "destination_type": "iceberg_s3",
    "aws_region": "us-east-1",
    "glue_database_name": "test_db",
    "parallelism": 20,  # Max is 16
}

VALID_UPDATE_PAYLOAD = {
    "migration_name": "Updated Migration Name",
    "parallelism": 8,
    "glue_database_name": "updated_db",
}

VALID_APPROVE_STRUCTURE_PAYLOAD = {
    "overrides": {"users": {"partition_spec": {"column": "created_at", "transform": "month"}}},
    "dataset_to_db_mapping": {"analytics": "analytics_iceberg_db"},
    "excluded_tables": ["temp_table"],
}

VALID_REQUEST_CHANGES_PAYLOAD = {
    "table_overrides": {
        "users": {"partition_spec": {"column": "signup_date", "transform": "day"}},
        "orders": {"sort_order": ["order_date", "customer_id"]},
    },
    "dataset_to_db_mapping": {"analytics": "new_analytics_db"},
}

VALID_CUSTOM_STRUCTURE_PAYLOAD = {
    "table_name": "custom_users",
    "columns": [
        {"name": "id", "iceberg_type": "long", "nullable": False},
        {"name": "name", "iceberg_type": "string", "nullable": True},
        {"name": "created_at", "iceberg_type": "timestamptz", "nullable": True},
    ],
    "partition_spec": {"column": "created_at", "transform": "day"},
    "sort_order": [{"column": "id", "direction": "asc"}],
    "table_properties": {"write.format.default": "parquet"},
}

VALID_COST_RECALCULATE_PAYLOAD = {
    "growth_rate_monthly": 0.1,
}


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
    BQRedshiftBase.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db_session(db_engine):
    """Provide a DB session for tests."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def fake_user():
    """A fake authenticated user for dependency override."""
    return CurrentUser(user_id=1, username="testuser", role="user", organization_id=1)


@pytest.fixture()
def fake_admin():
    """A fake admin user for dependency override."""
    return CurrentUser(user_id=2, username="admin", role="admin", organization_id=1)


def _make_app(db_session, fake_user, workspace_id=1):
    """Build a FastAPI app wired to the given session and workspace."""
    app = FastAPI()
    app.include_router(router)
    app.include_router(connection_test_router)

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_workspace_id] = lambda: workspace_id
    return app


@pytest.fixture()
def client(db_session, fake_user):
    """TestClient wired to a real SQLite DB (workspace 1)."""
    app = _make_app(db_session, fake_user, workspace_id=1)
    with patch(
        "routers.bq_iceberg_migration._encrypt_secret",
        side_effect=lambda v: f"encrypted:{v}",
    ):
        yield TestClient(app)


@pytest.fixture()
def client_workspace2(db_session, fake_user):
    """TestClient with workspace_id=2 for isolation tests."""
    app = _make_app(db_session, fake_user, workspace_id=2)
    with patch(
        "routers.bq_iceberg_migration._encrypt_secret",
        side_effect=lambda v: f"encrypted:{v}",
    ):
        yield TestClient(app)


@pytest.fixture()
def unauthenticated_app(db_session):
    """App without auth override — simulates missing authentication."""
    app = FastAPI()
    app.include_router(router)

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    # No override for get_current_user — will require real auth
    return app


def _create_migration(client, payload=None):
    """Helper to create a migration and return the response body."""
    payload = payload or VALID_CREATE_PAYLOAD_S3
    resp = client.post("/api/migrations/bq-iceberg/create", json=payload)
    assert resp.status_code == 201, f"Create failed: {resp.json()}"
    return resp.json()


# ---------------------------------------------------------------------------
# CRUD Endpoint Tests
# ---------------------------------------------------------------------------


class TestCreateMigration:
    """Integration tests for POST /api/migrations/bq-iceberg/create."""

    def test_create_with_valid_s3_payload(self, client):
        """Test creating an Iceberg S3 migration with valid payload."""
        resp = client.post("/api/migrations/bq-iceberg/create", json=VALID_CREATE_PAYLOAD_S3)

        assert resp.status_code == 201
        body = resp.json()
        assert body["migration_name"] == "BQ to Iceberg S3 Migration"
        assert body["pathway"] == "A"
        assert body["target"]["destination_type"] == "iceberg_s3"
        assert body["target"]["aws_region"] == "us-east-1"
        assert body["target"]["glue_database_name"] == "analytics_db"
        assert body["state"]["status"] == "pending"
        assert body["workspace_id"] == 1

    def test_create_with_valid_s3_tables_payload(self, client):
        """Test creating an Iceberg S3 Tables migration with valid payload."""
        resp = client.post(
            "/api/migrations/bq-iceberg/create", json=VALID_CREATE_PAYLOAD_S3_TABLES
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["target"]["destination_type"] == "iceberg_s3_tables"
        assert body["target"]["s3_tables_namespace"] == "warehouse_ns"
        assert body["credentials"]["aws_role_arn"] is not None
        assert body["load_config"]["parallelism"] == 8
        assert body["load_config"]["enable_load_stage_verification"] is True

    def test_create_with_minimal_payload(self, client):
        """Test creating a migration with only required fields."""
        resp = client.post(
            "/api/migrations/bq-iceberg/create", json=VALID_CREATE_PAYLOAD_MINIMAL
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["migration_name"] == "Minimal Migration"
        assert body["pathway"] == "C"
        assert body["load_config"]["parallelism"] == 4  # default

    def test_create_missing_required_fields_returns_422(self, client):
        """Test creating a migration with missing required fields returns 422."""
        resp = client.post(
            "/api/migrations/bq-iceberg/create", json=INVALID_PAYLOAD_MISSING_REQUIRED
        )
        assert resp.status_code == 422

    def test_create_invalid_pathway_returns_422(self, client):
        """Test creating a migration with invalid pathway returns 422."""
        resp = client.post(
            "/api/migrations/bq-iceberg/create", json=INVALID_PAYLOAD_BAD_PATHWAY
        )
        assert resp.status_code == 422

    def test_create_invalid_destination_type_returns_422(self, client):
        """Test creating a migration with invalid destination type returns 422."""
        resp = client.post(
            "/api/migrations/bq-iceberg/create", json=INVALID_PAYLOAD_BAD_DESTINATION
        )
        assert resp.status_code == 422

    def test_create_invalid_glue_db_name_returns_422(self, client):
        """Test creating a migration with invalid Glue DB name returns 422."""
        resp = client.post(
            "/api/migrations/bq-iceberg/create", json=INVALID_PAYLOAD_BAD_GLUE_DB
        )
        assert resp.status_code == 422

    def test_create_invalid_parallelism_returns_422(self, client):
        """Test creating a migration with parallelism > 16 returns 422."""
        resp = client.post(
            "/api/migrations/bq-iceberg/create", json=INVALID_PAYLOAD_BAD_PARALLELISM
        )
        assert resp.status_code == 422

    def test_create_duplicate_name_returns_400(self, client):
        """Test creating a migration with duplicate name in same workspace returns 400."""
        _create_migration(client, VALID_CREATE_PAYLOAD_S3)

        resp = client.post("/api/migrations/bq-iceberg/create", json=VALID_CREATE_PAYLOAD_S3)
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"]

    def test_create_encrypts_secret_key(self, client):
        """Test that aws_secret_access_key is encrypted before storage."""
        payload = {
            **VALID_CREATE_PAYLOAD_S3,
            "migration_name": "Encrypted Secret Test",
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        }
        resp = client.post("/api/migrations/bq-iceberg/create", json=payload)

        assert resp.status_code == 201
        body = resp.json()
        # Secret should not be exposed in response
        assert body["credentials"]["has_aws_secret_access_key"] is True
        assert "wJalrXUtnFEMI" not in str(body)


class TestListMigrations:
    """Integration tests for GET /api/migrations/bq-iceberg/list."""

    def test_list_returns_empty_initially(self, client):
        """Test listing migrations returns empty when none exist."""
        resp = client.get("/api/migrations/bq-iceberg/list")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["migrations"] == []

    def test_list_returns_created_migrations(self, client):
        """Test listing migrations returns created records."""
        _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        _create_migration(client, {**VALID_CREATE_PAYLOAD_MINIMAL, "migration_name": "Second"})

        resp = client.get("/api/migrations/bq-iceberg/list")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["migrations"]) == 2

    def test_list_with_status_filter(self, client):
        """Test listing migrations with status filter."""
        _create_migration(client, VALID_CREATE_PAYLOAD_S3)

        resp = client.get("/api/migrations/bq-iceberg/list", params={"status": "pending"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp = client.get("/api/migrations/bq-iceberg/list", params={"status": "running"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_list_with_destination_type_filter(self, client):
        """Test listing migrations with destination_type filter."""
        _create_migration(client, VALID_CREATE_PAYLOAD_S3)

        resp = client.get(
            "/api/migrations/bq-iceberg/list",
            params={"destination_type": "iceberg_s3"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp = client.get(
            "/api/migrations/bq-iceberg/list",
            params={"destination_type": "iceberg_s3_tables"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_list_pagination(self, client):
        """Test listing migrations respects limit and offset."""
        for i in range(5):
            _create_migration(
                client,
                {**VALID_CREATE_PAYLOAD_MINIMAL, "migration_name": f"Migration {i}"},
            )

        resp = client.get(
            "/api/migrations/bq-iceberg/list", params={"limit": 2, "offset": 0}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert len(body["migrations"]) == 2


class TestGetMigration:
    """Integration tests for GET /api/migrations/bq-iceberg/{id}."""

    def test_get_existing_migration(self, client):
        """Test getting a migration by ID returns full details."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client.get(f"/api/migrations/bq-iceberg/{migration_id}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == migration_id
        assert body["migration_name"] == "BQ to Iceberg S3 Migration"
        assert body["source"]["project_id"] == "my-gcp-project"
        assert body["target"]["s3_bucket"] == "my-data-lake-bucket"
        assert body["target"]["glue_database_name"] == "analytics_db"

    def test_get_nonexistent_migration_returns_404(self, client):
        """Test getting a non-existent migration returns 404."""
        resp = client.get("/api/migrations/bq-iceberg/99999")
        assert resp.status_code == 404


class TestUpdateMigration:
    """Integration tests for PUT /api/migrations/bq-iceberg/{id}/update."""

    def test_update_with_valid_payload(self, client):
        """Test updating a migration with valid fields."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client.put(
            f"/api/migrations/bq-iceberg/{migration_id}/update",
            json=VALID_UPDATE_PAYLOAD,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["migration_name"] == "Updated Migration Name"
        assert body["load_config"]["parallelism"] == 8

    def test_update_running_migration_returns_400(self, client, db_session):
        """Test updating a running migration returns 400."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        # Set status to running directly in DB
        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "running"
        db_session.commit()

        resp = client.put(
            f"/api/migrations/bq-iceberg/{migration_id}/update",
            json=VALID_UPDATE_PAYLOAD,
        )
        assert resp.status_code == 400
        assert "running" in resp.json()["detail"].lower()

    def test_update_nonexistent_migration_returns_404(self, client):
        """Test updating a non-existent migration returns 404."""
        resp = client.put(
            "/api/migrations/bq-iceberg/99999/update", json=VALID_UPDATE_PAYLOAD
        )
        assert resp.status_code == 404


class TestDeleteMigration:
    """Integration tests for DELETE /api/migrations/bq-iceberg/{id}."""

    def test_delete_existing_migration(self, client, db_session):
        """Test deleting a migration removes it from the database."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client.delete(f"/api/migrations/bq-iceberg/{migration_id}")

        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"].lower()

        # Verify it's gone
        db_session.expire_all()
        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        assert migration is None

    def test_delete_running_migration_returns_400(self, client, db_session):
        """Test deleting a running migration returns 400."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "running"
        db_session.commit()

        resp = client.delete(f"/api/migrations/bq-iceberg/{migration_id}")
        assert resp.status_code == 400

    def test_delete_nonexistent_migration_returns_404(self, client):
        """Test deleting a non-existent migration returns 404."""
        resp = client.delete("/api/migrations/bq-iceberg/99999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Lifecycle Endpoint Tests
# ---------------------------------------------------------------------------


class TestStartMigration:
    """Integration tests for POST /api/migrations/bq-iceberg/{id}/start."""

    def test_start_pending_migration(self, client):
        """Test starting a pending migration transitions to running."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/start")

        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_start_already_running_returns_400(self, client, db_session):
        """Test starting an already running migration returns 400."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "running"
        db_session.commit()

        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/start")
        assert resp.status_code == 400
        assert "already running" in resp.json()["detail"].lower()

    def test_start_from_invalid_status_returns_400(self, client, db_session):
        """Test starting from completed status returns 400."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "completed"
        db_session.commit()

        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/start")
        assert resp.status_code == 400


class TestPauseMigration:
    """Integration tests for POST /api/migrations/bq-iceberg/{id}/pause."""

    def test_pause_running_migration(self, client, db_session):
        """Test pausing a running migration transitions to paused."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "running"
        db_session.commit()

        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/pause")

        assert resp.status_code == 200
        assert "paused" in resp.json()["message"].lower()

    def test_pause_non_running_returns_400(self, client):
        """Test pausing a non-running migration returns 400."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/pause")
        assert resp.status_code == 400


class TestResumeMigration:
    """Integration tests for POST /api/migrations/bq-iceberg/{id}/resume."""

    def test_resume_paused_migration(self, client, db_session):
        """Test resuming a paused migration transitions to running."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "paused"
        db_session.commit()

        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/resume")

        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_resume_failed_migration(self, client, db_session):
        """Test resuming a failed migration transitions to running."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "failed"
        db_session.commit()

        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/resume")

        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_resume_from_invalid_status_returns_400(self, client):
        """Test resuming from pending status returns 400."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/resume")
        assert resp.status_code == 400


class TestCancelMigration:
    """Integration tests for POST /api/migrations/bq-iceberg/{id}/cancel."""

    def test_cancel_running_migration(self, client, db_session):
        """Test cancelling a running migration preserves config."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "running"
        db_session.commit()

        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/cancel")

        assert resp.status_code == 200
        assert "cancelled" in resp.json()["message"].lower()

        # Verify config is preserved
        db_session.expire_all()
        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        assert migration.status == "cancelled"
        assert migration.migration_name == "BQ to Iceberg S3 Migration"
        assert migration.glue_database_name == "analytics_db"

    def test_cancel_pending_review_preserves_config(self, client, db_session):
        """Test cancelling from pending_review preserves all configuration."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "pending_review"
        migration.structure_report = {"tables": [{"name": "users"}]}
        db_session.commit()

        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/cancel")

        assert resp.status_code == 200
        db_session.expire_all()
        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        assert migration.status == "cancelled"
        assert migration.structure_report is not None

    def test_cancel_already_cancelled_returns_400(self, client, db_session):
        """Test cancelling an already cancelled migration returns 400."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "cancelled"
        db_session.commit()

        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/cancel")
        assert resp.status_code == 400


class TestRestartMigration:
    """Integration tests for POST /api/migrations/bq-iceberg/{id}/restart."""

    def test_restart_completed_migration(self, client, db_session):
        """Test restarting a completed migration resets state."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "completed"
        migration.progress_percentage = 100
        db_session.commit()

        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/restart")

        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

        db_session.expire_all()
        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        assert migration.progress_percentage == 0

    def test_restart_running_migration_returns_400(self, client, db_session):
        """Test restarting a running migration returns 400."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "running"
        db_session.commit()

        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/restart")
        assert resp.status_code == 400


class TestGetMigrationStatus:
    """Integration tests for GET /api/migrations/bq-iceberg/{id}/status."""

    def test_get_status_returns_progress(self, client, db_session):
        """Test getting migration status returns progress info."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "running"
        migration.current_stage = "load"
        migration.progress_percentage = 45
        db_session.commit()

        resp = client.get(f"/api/migrations/bq-iceberg/{migration_id}/status")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "running"
        assert body["current_stage"] == "load"
        assert body["progress_percentage"] == 45


class TestGetMigrationLogs:
    """Integration tests for GET /api/migrations/bq-iceberg/{id}/logs."""

    def test_get_logs_empty(self, client):
        """Test getting logs for a migration with no logs."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client.get(f"/api/migrations/bq-iceberg/{migration_id}/logs")

        assert resp.status_code == 200
        body = resp.json()
        assert body["migration_id"] == migration_id
        assert body["logs"] == []


# ---------------------------------------------------------------------------
# Structure Report and Approval Flow Tests
# ---------------------------------------------------------------------------


class TestStructureReport:
    """Integration tests for structure report and approval endpoints."""

    def test_get_structure_report_not_generated_returns_404(self, client):
        """Test getting structure report before generation returns 404."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client.get(f"/api/migrations/bq-iceberg/{migration_id}/structure-report")
        assert resp.status_code == 404
        assert "not yet generated" in resp.json()["detail"].lower()

    def test_get_structure_report_when_available(self, client, db_session):
        """Test getting structure report when it has been generated."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        # Simulate report generation
        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "pending_review"
        migration.structure_report = {
            "tables": [
                {
                    "name": "users",
                    "columns": [{"name": "id", "bq_type": "INT64", "iceberg_type": "long"}],
                    "partition_spec": {"column": "created_at", "transform": "day"},
                }
            ],
            "prerequisites": {"iam_permissions": ["s3:PutObject", "glue:CreateTable"]},
            "warnings": [],
        }
        migration.cost_analysis_report = {"setup_costs": {"total": 5.0}}
        db_session.commit()

        resp = client.get(f"/api/migrations/bq-iceberg/{migration_id}/structure-report")

        assert resp.status_code == 200
        body = resp.json()
        assert body["migration_id"] == migration_id
        assert body["structure_report"]["tables"][0]["name"] == "users"
        assert body["cost_analysis_report"]["setup_costs"]["total"] == 5.0

    def test_approve_structure_transitions_to_approved(self, client, db_session):
        """Test approving structure transitions from pending_review to approved."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "pending_review"
        migration.structure_report = {"tables": [{"name": "users"}]}
        db_session.commit()

        resp = client.post(
            f"/api/migrations/bq-iceberg/{migration_id}/approve-structure",
            json=VALID_APPROVE_STRUCTURE_PAYLOAD,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "approved"
        assert body["approved_at"] is not None

        # Verify checkpoint_data contains the approved plan
        db_session.expire_all()
        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        assert migration.status == "approved"
        assert "iceberg_structure_plan" in migration.checkpoint_data

    def test_approve_from_wrong_status_returns_400(self, client):
        """Test approving structure from non-pending_review status returns 400."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client.post(
            f"/api/migrations/bq-iceberg/{migration_id}/approve-structure",
            json=VALID_APPROVE_STRUCTURE_PAYLOAD,
        )
        assert resp.status_code == 400
        assert "pending_review" in resp.json()["detail"]

    def test_request_changes_stores_overrides(self, client, db_session):
        """Test requesting changes stores overrides in the report."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "pending_review"
        migration.structure_report = {"tables": [{"name": "users"}]}
        db_session.commit()

        resp = client.post(
            f"/api/migrations/bq-iceberg/{migration_id}/request-changes",
            json=VALID_REQUEST_CHANGES_PAYLOAD,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert "users" in body["overrides_applied"]
        assert "orders" in body["overrides_applied"]

    def test_request_changes_from_wrong_status_returns_400(self, client):
        """Test requesting changes from non-pending_review status returns 400."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client.post(
            f"/api/migrations/bq-iceberg/{migration_id}/request-changes",
            json=VALID_REQUEST_CHANGES_PAYLOAD,
        )
        assert resp.status_code == 400

    def test_custom_structure_stores_definition(self, client, db_session):
        """Test defining custom structure stores it in the report."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "pending_review"
        migration.structure_report = {"tables": [{"name": "users"}]}
        db_session.commit()

        resp = client.post(
            f"/api/migrations/bq-iceberg/{migration_id}/custom-structure",
            json=VALID_CUSTOM_STRUCTURE_PAYLOAD,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["table_name"] == "custom_users"

        # Verify stored in DB
        db_session.expire_all()
        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        assert "custom_structures" in migration.structure_report
        assert "custom_users" in migration.structure_report["custom_structures"]

    def test_custom_structure_invalid_columns_returns_400(self, client, db_session):
        """Test defining custom structure with invalid columns returns 400."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "pending_review"
        migration.structure_report = {"tables": []}
        db_session.commit()

        invalid_payload = {
            "table_name": "bad_table",
            "columns": [{"missing_name": True}],  # Missing required 'name' field
        }
        resp = client.post(
            f"/api/migrations/bq-iceberg/{migration_id}/custom-structure",
            json=invalid_payload,
        )
        assert resp.status_code == 400

    def test_download_report_markdown(self, client, db_session):
        """Test downloading structure report as markdown."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.structure_report = {"tables": [{"name": "users", "columns": []}]}
        db_session.commit()

        resp = client.get(
            f"/api/migrations/bq-iceberg/{migration_id}/download-report",
            params={"format": "markdown"},
        )

        assert resp.status_code == 200
        assert "text/markdown" in resp.headers.get("content-type", "")

    def test_download_report_not_generated_returns_404(self, client):
        """Test downloading report when not generated returns 404."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client.get(
            f"/api/migrations/bq-iceberg/{migration_id}/download-report",
            params={"format": "markdown"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Cost Analysis Endpoint Tests
# ---------------------------------------------------------------------------


class TestCostAnalysis:
    """Integration tests for cost analysis endpoints."""

    def test_cost_analysis_included_in_structure_report(self, client, db_session):
        """Test that cost analysis is returned with structure report."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "pending_review"
        migration.structure_report = {"tables": [{"name": "users"}]}
        migration.cost_analysis_report = {
            "setup_costs": {"s3_storage": 2.30, "glue_api": 0.01, "total": 2.31},
            "recurring_monthly": {"s3_storage": 1.15, "glue_requests": 0.50, "total": 1.65},
            "projections": {"3_month": 5.0, "6_month": 10.5, "12_month": 22.0},
        }
        db_session.commit()

        resp = client.get(f"/api/migrations/bq-iceberg/{migration_id}/structure-report")

        assert resp.status_code == 200
        body = resp.json()
        assert body["cost_analysis_report"]["setup_costs"]["total"] == 2.31
        assert body["cost_analysis_report"]["projections"]["12_month"] == 22.0


# ---------------------------------------------------------------------------
# Workspace Isolation Tests
# ---------------------------------------------------------------------------


class TestWorkspaceIsolation:
    """
    Verify that records created under workspace 1 are invisible to workspace 2.

    The workspace_id filter in the router should exclude records belonging
    to a different workspace, resulting in 404 responses.
    """

    def test_migration_not_visible_in_other_workspace(self, client, client_workspace2):
        """Migration created in workspace 1 returns 404 from workspace 2."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client_workspace2.get(f"/api/migrations/bq-iceberg/{migration_id}")
        assert resp.status_code == 404

    def test_list_excludes_other_workspace_migrations(self, client, client_workspace2):
        """GET /list from workspace 2 does not include workspace 1 migrations."""
        _create_migration(client, VALID_CREATE_PAYLOAD_S3)

        resp = client_workspace2.get("/api/migrations/bq-iceberg/list")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["migrations"] == []

    def test_cannot_update_other_workspace_migration(self, client, client_workspace2):
        """Cannot update a migration belonging to another workspace."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client_workspace2.put(
            f"/api/migrations/bq-iceberg/{migration_id}/update",
            json=VALID_UPDATE_PAYLOAD,
        )
        assert resp.status_code == 404

    def test_cannot_delete_other_workspace_migration(self, client, client_workspace2):
        """Cannot delete a migration belonging to another workspace."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client_workspace2.delete(f"/api/migrations/bq-iceberg/{migration_id}")
        assert resp.status_code == 404

    def test_cannot_start_other_workspace_migration(self, client, client_workspace2):
        """Cannot start a migration belonging to another workspace."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client_workspace2.post(f"/api/migrations/bq-iceberg/{migration_id}/start")
        assert resp.status_code == 404

    def test_cannot_get_status_other_workspace_migration(self, client, client_workspace2):
        """Cannot get status of a migration belonging to another workspace."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client_workspace2.get(f"/api/migrations/bq-iceberg/{migration_id}/status")
        assert resp.status_code == 404

    def test_cannot_approve_other_workspace_migration(self, client, client_workspace2, db_session):
        """Cannot approve structure of a migration belonging to another workspace."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "pending_review"
        migration.structure_report = {"tables": []}
        db_session.commit()

        resp = client_workspace2.post(
            f"/api/migrations/bq-iceberg/{migration_id}/approve-structure",
            json=VALID_APPROVE_STRUCTURE_PAYLOAD,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Authentication and Authorization Tests
# ---------------------------------------------------------------------------


class TestAuthentication:
    """
    Verify that endpoints require authentication.

    When no auth override is provided, the real get_current_user dependency
    should reject requests without a valid token.
    """

    def test_create_without_auth_returns_401(self, unauthenticated_app):
        """Test creating a migration without auth returns 401."""
        client = TestClient(unauthenticated_app)
        resp = client.post(
            "/api/migrations/bq-iceberg/create", json=VALID_CREATE_PAYLOAD_S3
        )
        # Without auth header, should get 401 or 422 (missing header)
        assert resp.status_code in (401, 422)

    def test_list_without_auth_returns_401(self, unauthenticated_app):
        """Test listing migrations without auth returns 401."""
        client = TestClient(unauthenticated_app)
        resp = client.get("/api/migrations/bq-iceberg/list")
        assert resp.status_code in (401, 422)

    def test_get_without_auth_returns_401(self, unauthenticated_app):
        """Test getting a migration without auth returns 401."""
        client = TestClient(unauthenticated_app)
        resp = client.get("/api/migrations/bq-iceberg/1")
        assert resp.status_code in (401, 422)


# ---------------------------------------------------------------------------
# State Transition Flow Tests
# ---------------------------------------------------------------------------


class TestStateTransitionFlow:
    """Integration tests for complete state transition flows."""

    def test_full_lifecycle_pending_to_completed(self, client, db_session):
        """Test full lifecycle: pending → running → pending_review → approved → completed."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        # Start: pending → running
        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/start")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

        # Simulate reaching review stage
        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "pending_review"
        migration.structure_report = {"tables": [{"name": "users"}]}
        db_session.commit()

        # Approve: pending_review → approved
        resp = client.post(
            f"/api/migrations/bq-iceberg/{migration_id}/approve-structure",
            json={"overrides": None},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_pause_resume_flow(self, client, db_session):
        """Test pause and resume flow preserves state."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        # Start migration
        client.post(f"/api/migrations/bq-iceberg/{migration_id}/start")

        # Set progress
        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.progress_percentage = 50
        migration.current_stage = "load"
        db_session.commit()

        # Pause
        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/pause")
        assert resp.status_code == 200

        # Resume
        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_cancel_and_restart_flow(self, client, db_session):
        """Test cancel and restart flow resets progress."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        # Start and set progress
        client.post(f"/api/migrations/bq-iceberg/{migration_id}/start")
        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.progress_percentage = 75
        db_session.commit()

        # Cancel
        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/cancel")
        assert resp.status_code == 200

        # Restart
        resp = client.post(f"/api/migrations/bq-iceberg/{migration_id}/restart")
        assert resp.status_code == 200

        # Verify progress reset
        db_session.expire_all()
        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        assert migration.progress_percentage == 0
        assert migration.status == "running"


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Integration tests for edge cases and boundary conditions."""

    def test_create_with_max_parallelism(self, client):
        """Test creating a migration with maximum parallelism (16)."""
        payload = {
            **VALID_CREATE_PAYLOAD_MINIMAL,
            "migration_name": "Max Parallel",
            "parallelism": 16,
        }
        resp = client.post("/api/migrations/bq-iceberg/create", json=payload)
        assert resp.status_code == 201
        assert resp.json()["load_config"]["parallelism"] == 16

    def test_create_with_min_parallelism(self, client):
        """Test creating a migration with minimum parallelism (1)."""
        payload = {
            **VALID_CREATE_PAYLOAD_MINIMAL,
            "migration_name": "Min Parallel",
            "parallelism": 1,
        }
        resp = client.post("/api/migrations/bq-iceberg/create", json=payload)
        assert resp.status_code == 201
        assert resp.json()["load_config"]["parallelism"] == 1

    def test_create_with_empty_source_tables(self, client):
        """Test creating a migration with empty source tables list."""
        payload = {
            **VALID_CREATE_PAYLOAD_MINIMAL,
            "migration_name": "Empty Tables",
            "source_tables": [],
        }
        resp = client.post("/api/migrations/bq-iceberg/create", json=payload)
        assert resp.status_code == 201

    def test_create_with_long_migration_name(self, client):
        """Test creating a migration with maximum length name (255 chars)."""
        payload = {
            **VALID_CREATE_PAYLOAD_MINIMAL,
            "migration_name": "A" * 255,
        }
        resp = client.post("/api/migrations/bq-iceberg/create", json=payload)
        assert resp.status_code == 201

    def test_create_with_name_exceeding_max_returns_422(self, client):
        """Test creating a migration with name > 255 chars returns 422."""
        payload = {
            **VALID_CREATE_PAYLOAD_MINIMAL,
            "migration_name": "A" * 256,
        }
        resp = client.post("/api/migrations/bq-iceberg/create", json=payload)
        assert resp.status_code == 422

    def test_update_with_empty_body(self, client):
        """Test updating a migration with empty body succeeds (no changes)."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        resp = client.put(
            f"/api/migrations/bq-iceberg/{migration_id}/update", json={}
        )
        assert resp.status_code == 200

    def test_approve_with_empty_overrides(self, client, db_session):
        """Test approving structure with no overrides succeeds."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "pending_review"
        migration.structure_report = {"tables": [{"name": "users"}]}
        db_session.commit()

        resp = client.post(
            f"/api/migrations/bq-iceberg/{migration_id}/approve-structure",
            json={},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_dataset_to_db_mapping_stored_on_approve(self, client, db_session):
        """Test that dataset_to_db_mapping is stored when approving structure."""
        created = _create_migration(client, VALID_CREATE_PAYLOAD_S3)
        migration_id = created["id"]

        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        migration.status = "pending_review"
        migration.structure_report = {"tables": []}
        db_session.commit()

        resp = client.post(
            f"/api/migrations/bq-iceberg/{migration_id}/approve-structure",
            json={"dataset_to_db_mapping": {"analytics": "iceberg_analytics"}},
        )
        assert resp.status_code == 200

        db_session.expire_all()
        migration = db_session.query(MigrationBQIceberg).filter_by(id=migration_id).first()
        assert migration.dataset_to_db_mapping == {"analytics": "iceberg_analytics"}
