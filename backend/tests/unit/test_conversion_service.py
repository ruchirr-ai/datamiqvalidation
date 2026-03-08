"""
Unit tests for ConversionService.

Uses an in-memory SQLite database with mocked BedrockClient and SqlGlotParser
to validate standalone conversion, batch conversion, retry logic, query/delete
methods, and workspace isolation.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database import Base
from models.conversion_job import ConversionJob
from models.conversion_batch import ConversionBatch
from models.connection import Connection
from models.conversion_log import ConversionLog, ConversionLogStepName
from models.conversion_schemas import (
    StandaloneConversionRequest,
    BatchConversionRequest,
    AssetSelection,
    AssetType,
    ALLOWED_SOURCE_DIALECTS,
    ALLOWED_TARGET_DIALECTS,
)
from services.conversion_service import ConversionService
from services.conversion_cache import ConversionCache
from services.sqlglot_parser import SqlGlotResult


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def db_session():
    """Create a fresh in-memory SQLite session for each test."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
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
def mock_cache():
    """Create a mock ConversionCache that behaves like a no-op cache."""
    cache = MagicMock(spec=ConversionCache)
    cache.get_batch_status.return_value = None
    cache.set_batch_status.return_value = None
    cache.invalidate_batch_status.return_value = None
    return cache


@pytest.fixture()
def service(db_session, mock_cache):
    """Create a ConversionService with mocked external dependencies."""
    svc = ConversionService(db_session, mock_cache)
    # Mock the BedrockClient
    svc.bedrock_client = MagicMock()
    svc.bedrock_client.fetch_prompt_template.return_value = (
        "Convert {source_code} from {source_dialect} to {target_dialect} "
        "for {asset_type}. sqlglot: {sqlglot_output}"
    )
    svc.bedrock_client.invoke_model.return_value = "SELECT * FROM my_schema.my_table"
    # Mock the SqlGlotParser
    svc.sqlglot_parser = MagicMock()
    svc.sqlglot_parser.parse_and_transpile.return_value = SqlGlotResult(
        transpiled_code="SELECT * FROM my_schema.my_table",
        success=True,
        warning=None,
    )
    # Mock the AuditLogger (audit_logs table not in SQLite test DB)
    svc.audit_logger = MagicMock()
    return svc


# ── Sample payloads ──────────────────────────────────────────────────

STANDALONE_REQUEST = StandaloneConversionRequest(
    source_code="SELECT * FROM dataset.my_table",
    source_dialect="Bigquery",
    target_dialect="Redshift",
    asset_type=AssetType.TABLE_DDL,
    asset_name="my_table",
    aws_region="us-east-1",
    bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
    prompt_template_path="s3://bucket/template.txt",
    max_retries=2,
    use_sqlglot=False,
)

STANDALONE_REQUEST_WITH_SQLGLOT = StandaloneConversionRequest(
    source_code="SELECT * FROM dataset.my_table",
    source_dialect="Bigquery",
    target_dialect="Redshift",
    asset_type=AssetType.TABLE_DDL,
    asset_name="my_table",
    aws_region="us-east-1",
    bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
    prompt_template_path="s3://bucket/template.txt",
    max_retries=2,
    use_sqlglot=True,
)

BATCH_REQUEST = BatchConversionRequest(
    migration_project_id=1,
    source_connection_id=10,
    target_connection_id=20,
    assets=[
        AssetSelection(
            asset_type=AssetType.TABLE_DDL,
            asset_name="table_a",
            source_code="CREATE TABLE dataset.table_a (id INT64)",
        ),
        AssetSelection(
            asset_type=AssetType.VIEW,
            asset_name="view_b",
            source_code="CREATE VIEW dataset.view_b AS SELECT * FROM dataset.table_a",
        ),
        AssetSelection(
            asset_type=AssetType.STORED_PROCEDURE,
            asset_name="proc_c",
            source_code="CREATE PROCEDURE dataset.proc_c() BEGIN SELECT 1; END",
        ),
    ],
    source_dialect="Bigquery",
    target_dialect="Redshift",
    aws_region="us-east-1",
    bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
    prompt_template_path="s3://bucket/template.txt",
    max_retries=1,
    use_sqlglot=False,
)


WORKSPACE_ID = 1
USER_ID = "testuser"


# ── Standalone conversion tests ───────────────────────────────────────

class TestStandaloneConversion:
    """Test ConversionService.create_standalone_conversion end-to-end."""

    def test_standalone_conversion_success(self, service):
        """Standalone conversion with mocked Bedrock returns completed job."""
        job = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        assert job.status == "completed"
        assert job.target_code == "SELECT * FROM my_schema.my_table"
        assert job.workspace_id == WORKSPACE_ID
        assert job.source_dialect == "Bigquery"
        assert job.target_dialect == "Redshift"
        assert job.asset_type == "TABLE_DDL"
        assert job.created_by == USER_ID
        assert job.error_message is None

    def test_standalone_conversion_calls_bedrock(self, service):
        """Bedrock client is called with correct template and model."""
        service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        service.bedrock_client.fetch_prompt_template.assert_called_once_with(
            "s3://bucket/template.txt", "us-east-1",
        )
        service.bedrock_client.invoke_model.assert_called_once()
        call_kwargs = service.bedrock_client.invoke_model.call_args
        assert call_kwargs[1]["model_id"] == "anthropic.claude-3-sonnet-20240229-v1:0"
        assert call_kwargs[1]["region"] == "us-east-1"

    def test_standalone_conversion_sqlglot_not_called_when_disabled(self, service):
        """SqlGlotParser is not called when use_sqlglot=False."""
        service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        service.sqlglot_parser.parse_and_transpile.assert_not_called()

    def test_standalone_conversion_persists_job(self, service, db_session):
        """Job is persisted in the database after conversion."""
        job = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        persisted = db_session.query(ConversionJob).filter_by(id=job.id).first()
        assert persisted is not None
        assert persisted.status == "completed"
        assert persisted.target_code is not None


class TestStandaloneConversionWithSqlglot:
    """Test standalone conversion with sqlglot enabled."""

    def test_sqlglot_success_passes_output_to_prompt(self, service):
        """When sqlglot succeeds, transpiled code is passed to prompt rendering."""
        service.sqlglot_parser.parse_and_transpile.return_value = SqlGlotResult(
            transpiled_code="SELECT * FROM my_schema.my_table",
            success=True,
            warning=None,
        )

        job = service.create_standalone_conversion(
            STANDALONE_REQUEST_WITH_SQLGLOT, WORKSPACE_ID, USER_ID,
        )

        assert job.status == "completed"
        assert job.use_sqlglot is True
        assert job.sqlglot_success is True
        service.sqlglot_parser.parse_and_transpile.assert_called_once_with(
            STANDALONE_REQUEST_WITH_SQLGLOT.source_code,
            "Bigquery",
            "Redshift",
        )

    def test_sqlglot_failure_falls_back_to_raw_source(self, service):
        """When sqlglot fails, conversion proceeds with raw source code."""
        service.sqlglot_parser.parse_and_transpile.return_value = SqlGlotResult(
            transpiled_code=None,
            success=False,
            warning="sqlglot failed to parse source SQL",
        )

        job = service.create_standalone_conversion(
            STANDALONE_REQUEST_WITH_SQLGLOT, WORKSPACE_ID, USER_ID,
        )

        assert job.status == "completed"
        assert job.sqlglot_success is False
        # Bedrock was still called (fallback to raw source)
        service.bedrock_client.invoke_model.assert_called_once()

    def test_sqlglot_metadata_recorded_on_success(self, service):
        """sqlglot_success=True is recorded in job metadata."""
        job = service.create_standalone_conversion(
            STANDALONE_REQUEST_WITH_SQLGLOT, WORKSPACE_ID, USER_ID,
        )

        assert job.sqlglot_success is True

    def test_sqlglot_metadata_recorded_on_failure(self, service):
        """sqlglot_success=False is recorded in job metadata on parse failure."""
        service.sqlglot_parser.parse_and_transpile.return_value = SqlGlotResult(
            transpiled_code=None, success=False, warning="parse error",
        )

        job = service.create_standalone_conversion(
            STANDALONE_REQUEST_WITH_SQLGLOT, WORKSPACE_ID, USER_ID,
        )

        assert job.sqlglot_success is False


class TestStandaloneConversionRetry:
    """Test retry logic on Bedrock failure."""

    @patch("services.conversion_service.time.sleep", return_value=None)
    def test_retry_on_bedrock_failure_then_success(self, mock_sleep, service):
        """Retries on first failure, succeeds on second attempt."""
        service.bedrock_client.invoke_model.side_effect = [
            RuntimeError("Bedrock throttled"),
            "SELECT * FROM converted_table",
        ]

        job = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        assert job.status == "completed"
        assert job.target_code == "SELECT * FROM converted_table"
        assert service.bedrock_client.invoke_model.call_count == 2

    @patch("services.conversion_service.time.sleep", return_value=None)
    def test_all_retries_exhausted_marks_failed(self, mock_sleep, service):
        """When all retries fail, job is marked as failed with error message."""
        service.bedrock_client.invoke_model.side_effect = RuntimeError(
            "Bedrock service unavailable"
        )

        request = StandaloneConversionRequest(
            source_code="SELECT 1",
            source_dialect="Bigquery",
            target_dialect="Redshift",
            asset_type=AssetType.TABLE_DDL,
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="s3://bucket/template.txt",
            max_retries=2,
            use_sqlglot=False,
        )

        job = service.create_standalone_conversion(request, WORKSPACE_ID, USER_ID)

        assert job.status == "failed"
        assert "Bedrock service unavailable" in job.error_message
        # 1 initial + 2 retries = 3 total attempts
        assert service.bedrock_client.invoke_model.call_count == 3

    @patch("services.conversion_service.time.sleep", return_value=None)
    def test_retry_on_template_fetch_failure(self, mock_sleep, service):
        """Retries when prompt template fetch fails."""
        service.bedrock_client.fetch_prompt_template.side_effect = [
            ValueError("S3 access denied"),
            "Convert {source_code} from {source_dialect} to {target_dialect} for {asset_type}. sqlglot: {sqlglot_output}",
        ]

        job = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        assert job.status == "completed"
        assert service.bedrock_client.fetch_prompt_template.call_count == 2

    @patch("services.conversion_service.time.sleep", return_value=None)
    def test_zero_retries_fails_immediately(self, mock_sleep, service):
        """With max_retries=0, a single failure marks the job as failed."""
        service.bedrock_client.invoke_model.side_effect = RuntimeError("fail")

        request = StandaloneConversionRequest(
            source_code="SELECT 1",
            source_dialect="Bigquery",
            target_dialect="Redshift",
            asset_type=AssetType.TABLE_DDL,
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="s3://bucket/template.txt",
            max_retries=0,
            use_sqlglot=False,
        )

        job = service.create_standalone_conversion(request, WORKSPACE_ID, USER_ID)

        assert job.status == "failed"
        assert service.bedrock_client.invoke_model.call_count == 1


# ── Batch conversion tests ────────────────────────────────────────────

class TestBatchConversion:
    """Test ConversionService.create_batch_conversion."""

    def test_batch_creates_correct_number_of_jobs(self, service, db_session):
        """Batch creation creates one job per asset."""
        batch = service.create_batch_conversion(
            BATCH_REQUEST, WORKSPACE_ID, USER_ID,
        )

        assert batch.total_assets == 3
        assert batch.status == "pending"

        jobs = db_session.query(ConversionJob).filter_by(batch_id=batch.id).all()
        assert len(jobs) == 3

    def test_batch_jobs_have_correct_metadata(self, service, db_session):
        """Each batch job inherits dialect, model, and region from the request."""
        batch = service.create_batch_conversion(
            BATCH_REQUEST, WORKSPACE_ID, USER_ID,
        )

        jobs = db_session.query(ConversionJob).filter_by(batch_id=batch.id).all()
        for job in jobs:
            assert job.source_dialect == "Bigquery"
            assert job.target_dialect == "Redshift"
            assert job.bedrock_model == "anthropic.claude-3-sonnet-20240229-v1:0"
            assert job.aws_region == "us-east-1"
            assert job.workspace_id == WORKSPACE_ID
            assert job.created_by == USER_ID
            assert job.status == "pending"

    def test_batch_jobs_have_correct_asset_names(self, service, db_session):
        """Each batch job has the correct asset_name and asset_type."""
        batch = service.create_batch_conversion(
            BATCH_REQUEST, WORKSPACE_ID, USER_ID,
        )

        jobs = (
            db_session.query(ConversionJob)
            .filter_by(batch_id=batch.id)
            .order_by(ConversionJob.id)
            .all()
        )

        assert jobs[0].asset_name == "table_a"
        assert jobs[0].asset_type == "TABLE_DDL"
        assert jobs[1].asset_name == "view_b"
        assert jobs[1].asset_type == "VIEW"
        assert jobs[2].asset_name == "proc_c"
        assert jobs[2].asset_type == "STORED_PROCEDURE"

    def test_batch_records_connection_ids(self, service):
        """Batch stores source and target connection IDs."""
        batch = service.create_batch_conversion(
            BATCH_REQUEST, WORKSPACE_ID, USER_ID,
        )

        assert batch.source_connection_id == 10
        assert batch.target_connection_id == 20
        assert batch.migration_project_id == 1


class TestBatchBackgroundProcessing:
    """Test ConversionService.run_batch_background."""

    @patch("services.conversion_service.time.sleep", return_value=None)
    def test_batch_background_completes_all_jobs(self, mock_sleep, service, db_session):
        """All jobs are processed and batch status is completed."""
        batch = service.create_batch_conversion(
            BATCH_REQUEST, WORKSPACE_ID, USER_ID,
        )

        service.run_batch_background(batch.id, WORKSPACE_ID)

        # Refresh batch from DB
        db_session.refresh(batch)
        assert batch.status == "completed"
        assert batch.completed_assets == 3
        assert batch.failed_assets == 0

        # All jobs should be completed
        jobs = db_session.query(ConversionJob).filter_by(batch_id=batch.id).all()
        for job in jobs:
            assert job.status == "completed"
            assert job.target_code is not None

    @patch("services.conversion_service.time.sleep", return_value=None)
    def test_batch_background_updates_cache_after_each_job(self, mock_sleep, service, mock_cache):
        """Redis cache is updated after each job completes."""
        batch = service.create_batch_conversion(
            BATCH_REQUEST, WORKSPACE_ID, USER_ID,
        )

        service.run_batch_background(batch.id, WORKSPACE_ID)

        # set_batch_status called once per job (3 jobs)
        assert mock_cache.set_batch_status.call_count == 3
        # invalidate called once at the end
        mock_cache.invalidate_batch_status.assert_called_once_with(batch.id)

    @patch("services.conversion_service.time.sleep", return_value=None)
    def test_batch_background_with_failures(self, mock_sleep, service, db_session):
        """When some jobs fail, batch status is completed_with_errors."""
        batch = service.create_batch_conversion(
            BATCH_REQUEST, WORKSPACE_ID, USER_ID,
        )

        # Make the second invocation fail (all retries)
        call_count = [0]
        original_invoke = service.bedrock_client.invoke_model

        def invoke_side_effect(*args, **kwargs):
            call_count[0] += 1
            # Fail calls for the second job (calls 2 and 3 with max_retries=1)
            if call_count[0] in (2, 3):
                raise RuntimeError("Bedrock error")
            return "SELECT * FROM converted"

        service.bedrock_client.invoke_model.side_effect = invoke_side_effect

        service.run_batch_background(batch.id, WORKSPACE_ID)

        db_session.refresh(batch)
        assert batch.status == "completed_with_errors"
        assert batch.completed_assets == 2
        assert batch.failed_assets == 1

    @patch("services.conversion_service.time.sleep", return_value=None)
    def test_batch_background_all_fail(self, mock_sleep, service, db_session):
        """When all jobs fail, batch status is failed."""
        batch = service.create_batch_conversion(
            BATCH_REQUEST, WORKSPACE_ID, USER_ID,
        )

        service.bedrock_client.invoke_model.side_effect = RuntimeError("total failure")

        service.run_batch_background(batch.id, WORKSPACE_ID)

        db_session.refresh(batch)
        assert batch.status == "failed"
        assert batch.completed_assets == 0
        assert batch.failed_assets == 3

    @patch("services.conversion_service.time.sleep", return_value=None)
    def test_batch_background_updates_progress_counters(self, mock_sleep, service, mock_cache):
        """Progress counters increment correctly during processing."""
        batch = service.create_batch_conversion(
            BATCH_REQUEST, WORKSPACE_ID, USER_ID,
        )

        service.run_batch_background(batch.id, WORKSPACE_ID)

        # Verify progressive cache updates
        calls = mock_cache.set_batch_status.call_args_list
        assert len(calls) == 3

        # First call: 1 completed, 0 failed
        assert calls[0][0][1]["completed_assets"] == 1
        assert calls[0][0][1]["failed_assets"] == 0

        # Second call: 2 completed, 0 failed
        assert calls[1][0][1]["completed_assets"] == 2
        assert calls[1][0][1]["failed_assets"] == 0

        # Third call: 3 completed, 0 failed
        assert calls[2][0][1]["completed_assets"] == 3
        assert calls[2][0][1]["failed_assets"] == 0

    def test_batch_background_nonexistent_batch(self, service):
        """Processing a non-existent batch returns without error."""
        # Should not raise
        service.run_batch_background(9999, WORKSPACE_ID)


# ── Query, delete, and listing tests ──────────────────────────────────

class TestGetJob:
    """Test ConversionService.get_job."""

    def test_get_existing_job(self, service):
        """Retrieving an existing job returns it."""
        created = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        fetched = service.get_job(created.id, WORKSPACE_ID)
        assert fetched is not None
        assert fetched.id == created.id

    def test_get_nonexistent_job_returns_none(self, service):
        """Querying a non-existent job returns None."""
        assert service.get_job(9999, WORKSPACE_ID) is None

    def test_get_job_workspace_isolation(self, service):
        """Job in workspace 1 is not visible to workspace 2."""
        created = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        assert service.get_job(created.id, workspace_id=2) is None


class TestListJobs:
    """Test ConversionService.list_jobs."""

    def test_list_returns_paginated_result(self, service):
        """list_jobs returns dict with jobs, total, page, page_size."""
        service.create_standalone_conversion(STANDALONE_REQUEST, WORKSPACE_ID, USER_ID)
        service.create_standalone_conversion(STANDALONE_REQUEST, WORKSPACE_ID, USER_ID)

        result = service.list_jobs(WORKSPACE_ID, page=1, page_size=10)

        assert "jobs" in result
        assert "total" in result
        assert "page" in result
        assert "page_size" in result
        assert result["total"] == 2
        assert len(result["jobs"]) == 2

    def test_list_jobs_with_status_filter(self, service):
        """Filtering by status returns only matching jobs."""
        service.create_standalone_conversion(STANDALONE_REQUEST, WORKSPACE_ID, USER_ID)

        result = service.list_jobs(WORKSPACE_ID, status="completed")
        assert result["total"] == 1

        result = service.list_jobs(WORKSPACE_ID, status="pending")
        assert result["total"] == 0

    def test_list_jobs_workspace_isolation(self, service):
        """Jobs in workspace 1 are not visible to workspace 2."""
        service.create_standalone_conversion(STANDALONE_REQUEST, WORKSPACE_ID, USER_ID)

        result = service.list_jobs(workspace_id=2)
        assert result["total"] == 0

    def test_list_jobs_pagination(self, service):
        """Pagination returns correct slices."""
        for _ in range(5):
            service.create_standalone_conversion(STANDALONE_REQUEST, WORKSPACE_ID, USER_ID)

        page1 = service.list_jobs(WORKSPACE_ID, page=1, page_size=2)
        page2 = service.list_jobs(WORKSPACE_ID, page=2, page_size=2)

        assert page1["total"] == 5
        assert len(page1["jobs"]) == 2
        assert len(page2["jobs"]) == 2


class TestDeleteJob:
    """Test ConversionService.delete_job."""

    def test_delete_existing_job(self, service):
        """Deleting an existing job returns True and removes it."""
        job = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        result = service.delete_job(job.id, WORKSPACE_ID)
        assert result is True
        assert service.get_job(job.id, WORKSPACE_ID) is None

    def test_delete_nonexistent_job_returns_false(self, service):
        """Deleting a non-existent job returns False."""
        assert service.delete_job(9999, WORKSPACE_ID) is False

    def test_delete_job_workspace_isolation(self, service):
        """Cannot delete a job from another workspace."""
        job = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        assert service.delete_job(job.id, workspace_id=2) is False
        # Job still exists in workspace 1
        assert service.get_job(job.id, WORKSPACE_ID) is not None


class TestGetBatch:
    """Test ConversionService.get_batch."""

    def test_get_existing_batch(self, service):
        """Retrieving an existing batch returns it."""
        batch = service.create_batch_conversion(
            BATCH_REQUEST, WORKSPACE_ID, USER_ID,
        )

        fetched = service.get_batch(batch.id, WORKSPACE_ID)
        assert fetched is not None
        assert fetched.id == batch.id

    def test_get_batch_nonexistent_returns_none(self, service):
        """Querying a non-existent batch returns None."""
        assert service.get_batch(9999, WORKSPACE_ID) is None


class TestListBatchJobs:
    """Test ConversionService.list_batch_jobs."""

    def test_list_batch_jobs_returns_all_jobs(self, service):
        """list_batch_jobs returns all jobs in the batch."""
        batch = service.create_batch_conversion(
            BATCH_REQUEST, WORKSPACE_ID, USER_ID,
        )

        jobs = service.list_batch_jobs(batch.id, WORKSPACE_ID)
        assert len(jobs) == 3

    def test_list_batch_jobs_workspace_isolation(self, service):
        """Batch jobs are filtered by workspace_id."""
        batch = service.create_batch_conversion(
            BATCH_REQUEST, WORKSPACE_ID, USER_ID,
        )

        jobs = service.list_batch_jobs(batch.id, workspace_id=2)
        assert len(jobs) == 0


class TestListBedrockModels:
    """Test ConversionService.list_bedrock_models."""

    def test_list_models_delegates_to_bedrock_client(self, service):
        """list_bedrock_models delegates to BedrockClient.list_models."""
        from services.bedrock_client import BedrockModel

        mock_models = [
            BedrockModel(model_id="model-1", model_name="Model One", provider="Anthropic"),
            BedrockModel(model_id="model-2", model_name="Model Two", provider="Amazon"),
        ]
        service.bedrock_client.list_models.return_value = mock_models

        result = service.list_bedrock_models("us-east-1")

        assert len(result) == 2
        assert result[0].model_id == "model-1"
        service.bedrock_client.list_models.assert_called_once_with("us-east-1")


# ── Audit logging tests ───────────────────────────────────────────────

class TestAuditLogging:
    """Test that ConversionService logs audit events for conversion operations."""

    def test_standalone_conversion_logs_audit_on_success(self, service):
        """Audit log_data_modification is called after successful standalone conversion."""
        job = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        service.audit_logger.log_data_modification.assert_called_once_with(
            user_id=0,
            username=USER_ID,
            workspace_id=WORKSPACE_ID,
            resource_type="conversion_job",
            resource_id=job.id,
            action="create",
        )

    @patch("services.conversion_service.time.sleep", return_value=None)
    def test_standalone_conversion_no_audit_on_failure(self, mock_sleep, service):
        """Audit log is NOT called when standalone conversion fails."""
        service.bedrock_client.invoke_model.side_effect = RuntimeError("fail")

        request = StandaloneConversionRequest(
            source_code="SELECT 1",
            source_dialect="Bigquery",
            target_dialect="Redshift",
            asset_type=AssetType.TABLE_DDL,
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="s3://bucket/template.txt",
            max_retries=0,
            use_sqlglot=False,
        )

        job = service.create_standalone_conversion(request, WORKSPACE_ID, USER_ID)

        assert job.status == "failed"
        service.audit_logger.log_data_modification.assert_not_called()

    def test_batch_conversion_logs_audit_on_create(self, service):
        """Audit log_data_modification is called after batch creation."""
        batch = service.create_batch_conversion(
            BATCH_REQUEST, WORKSPACE_ID, USER_ID,
        )

        service.audit_logger.log_data_modification.assert_called_once_with(
            user_id=0,
            username=USER_ID,
            workspace_id=WORKSPACE_ID,
            resource_type="conversion_batch",
            resource_id=batch.id,
            action="create",
        )

    def test_delete_job_logs_audit_on_success(self, service):
        """Audit log_data_modification is called after successful job deletion."""
        job = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )
        # Reset mock after the create call
        service.audit_logger.log_data_modification.reset_mock()

        service.delete_job(job.id, WORKSPACE_ID, user_id=USER_ID)

        service.audit_logger.log_data_modification.assert_called_once_with(
            user_id=0,
            username=USER_ID,
            workspace_id=WORKSPACE_ID,
            resource_type="conversion_job",
            resource_id=job.id,
            action="delete",
        )

    def test_delete_job_no_audit_when_not_found(self, service):
        """Audit log is NOT called when job to delete is not found."""
        service.delete_job(9999, WORKSPACE_ID, user_id=USER_ID)

        service.audit_logger.log_data_modification.assert_not_called()

    def test_audit_log_includes_workspace_and_user(self, service):
        """Audit log entries include workspace_id and user_id."""
        job = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        call_kwargs = service.audit_logger.log_data_modification.call_args[1]
        assert call_kwargs["workspace_id"] == WORKSPACE_ID
        assert call_kwargs["username"] == USER_ID

    def test_audit_log_never_contains_source_or_target_code(self, service):
        """Audit log calls must never include source_code or target_code content."""
        service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        call_args = service.audit_logger.log_data_modification.call_args
        # Flatten all positional and keyword arguments into a string for inspection
        all_args_str = str(call_args)
        assert "SELECT * FROM dataset.my_table" not in all_args_str
        assert "SELECT * FROM my_schema.my_table" not in all_args_str


# ── Dialect validation tests ──────────────────────────────────────────

class TestDialectValidation:
    """Test ConversionService._validate_dialects and its integration
    with create_standalone_conversion."""

    def test_invalid_source_dialect_raises_value_error(self, service):
        """Invalid source_dialect raises ValueError."""
        request = StandaloneConversionRequest(
            source_code="SELECT 1",
            source_dialect="oracle",
            target_dialect="Redshift",
            asset_type=AssetType.QUERY,
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="s3://bucket/template.txt",
            use_sqlglot=False,
        )

        with pytest.raises(ValueError, match="Invalid source_dialect"):
            service.create_standalone_conversion(request, WORKSPACE_ID, USER_ID)

    def test_invalid_target_dialect_raises_value_error(self, service):
        """Invalid target_dialect raises ValueError."""
        request = StandaloneConversionRequest(
            source_code="SELECT 1",
            source_dialect="Bigquery",
            target_dialect="MySQL",
            asset_type=AssetType.QUERY,
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="s3://bucket/template.txt",
            use_sqlglot=False,
        )

        with pytest.raises(ValueError, match="Invalid target_dialect"):
            service.create_standalone_conversion(request, WORKSPACE_ID, USER_ID)

    def test_all_valid_source_dialects_accepted(self, service):
        """All allowed source dialects are accepted without error."""
        for dialect in ALLOWED_SOURCE_DIALECTS:
            request = StandaloneConversionRequest(
                source_code="SELECT 1",
                source_dialect=dialect,
                target_dialect="Redshift",
                asset_type=AssetType.QUERY,
                aws_region="us-east-1",
                bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
                prompt_template_path="s3://bucket/template.txt",
                use_sqlglot=False,
            )
            job = service.create_standalone_conversion(request, WORKSPACE_ID, USER_ID)
            assert job.status == "completed"

    def test_all_valid_target_dialects_accepted(self, service):
        """All allowed target dialects are accepted without error."""
        for dialect in ALLOWED_TARGET_DIALECTS:
            request = StandaloneConversionRequest(
                source_code="SELECT 1",
                source_dialect="Bigquery",
                target_dialect=dialect,
                asset_type=AssetType.QUERY,
                aws_region="us-east-1",
                bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
                prompt_template_path="s3://bucket/template.txt",
                use_sqlglot=False,
            )
            job = service.create_standalone_conversion(request, WORKSPACE_ID, USER_ID)
            assert job.status == "completed"


# ── Additional context tests ──────────────────────────────────────────

class TestAdditionalContext:
    """Test additional_context handling in standalone conversion."""

    def test_additional_context_appended_to_prompt(self, service):
        """additional_context is passed to render_prompt when provided."""
        request = StandaloneConversionRequest(
            source_code="SELECT * FROM my_table",
            source_dialect="Bigquery",
            target_dialect="Redshift",
            asset_type=AssetType.QUERY,
            asset_name="My Test Query",
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="s3://bucket/template.txt",
            additional_context="Schema: users(id INT, name VARCHAR(255))",
            use_sqlglot=False,
        )

        job = service.create_standalone_conversion(request, WORKSPACE_ID, USER_ID)

        assert job.status == "completed"
        # Verify render_prompt was called — the invoke_model call receives
        # the rendered prompt which should include the additional context
        invoke_call = service.bedrock_client.invoke_model.call_args
        prompt_arg = invoke_call[1]["prompt"]
        assert "Schema: users(id INT, name VARCHAR(255))" in prompt_arg

    def test_additional_context_exceeding_limit_raises_value_error(self, service):
        """additional_context exceeding 50,000 chars raises ValueError."""
        request = StandaloneConversionRequest(
            source_code="SELECT 1",
            source_dialect="Bigquery",
            target_dialect="Redshift",
            asset_type=AssetType.QUERY,
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="s3://bucket/template.txt",
            additional_context="x" * 50000,  # at boundary — should pass
            use_sqlglot=False,
        )
        # Boundary (50,000) should succeed
        job = service.create_standalone_conversion(request, WORKSPACE_ID, USER_ID)
        assert job.status == "completed"

    def test_additional_context_over_limit_rejected_by_pydantic(self):
        """Pydantic validator rejects additional_context > 50,000 chars."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="additional_context"):
            StandaloneConversionRequest(
                source_code="SELECT 1",
                source_dialect="Bigquery",
                target_dialect="Redshift",
                asset_type=AssetType.QUERY,
                aws_region="us-east-1",
                bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
                prompt_template_path="s3://bucket/template.txt",
                additional_context="x" * 50001,
                use_sqlglot=False,
            )

    def test_additional_context_not_persisted_on_job(self, service, db_session):
        """additional_context is NOT stored on the ConversionJob record."""
        request = StandaloneConversionRequest(
            source_code="SELECT * FROM my_table",
            source_dialect="Bigquery",
            target_dialect="Redshift",
            asset_type=AssetType.QUERY,
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="s3://bucket/template.txt",
            additional_context="Schema: users(id INT, name VARCHAR(255))",
            use_sqlglot=False,
        )

        job = service.create_standalone_conversion(request, WORKSPACE_ID, USER_ID)

        persisted = db_session.query(ConversionJob).filter_by(id=job.id).first()
        assert persisted is not None
        # ConversionJob has no additional_context column
        assert not hasattr(persisted, "additional_context")

    def test_conversion_succeeds_without_additional_context(self, service):
        """Conversion works normally when additional_context is None."""
        request = StandaloneConversionRequest(
            source_code="SELECT 1",
            source_dialect="Bigquery",
            target_dialect="Redshift",
            asset_type=AssetType.QUERY,
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="s3://bucket/template.txt",
            use_sqlglot=False,
        )

        job = service.create_standalone_conversion(request, WORKSPACE_ID, USER_ID)
        assert job.status == "completed"


# ── Unescape tests ───────────────────────────────────────────────────

class TestUnescapeApplied:
    """Test that unescape_code_output is applied to target_code before persistence."""

    def test_unescape_applied_to_target_code(self, service, db_session):
        """Literal \\n in Bedrock response becomes actual newline in persisted job."""
        service.bedrock_client.invoke_model.return_value = (
            "SELECT *\\nFROM my_table\\nWHERE id = 1"
        )

        job = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        persisted = db_session.query(ConversionJob).filter_by(id=job.id).first()
        assert "\\n" not in persisted.target_code
        assert "\n" in persisted.target_code
        assert persisted.target_code == "SELECT *\nFROM my_table\nWHERE id = 1"

    def test_unescape_handles_tabs(self, service, db_session):
        """Literal \\t in Bedrock response becomes actual tab in persisted job."""
        service.bedrock_client.invoke_model.return_value = (
            "SELECT\\n\\tid,\\n\\tname\\nFROM users"
        )

        job = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        persisted = db_session.query(ConversionJob).filter_by(id=job.id).first()
        assert "\t" in persisted.target_code
        assert "\\t" not in persisted.target_code


# ── Conversion log tests ─────────────────────────────────────────────

class TestConversionLogGeneration:
    """Test that ConversionLog entries are created during conversion."""

    def test_successful_conversion_creates_expected_logs(self, service, db_session):
        """Successful standalone conversion creates log entries for key steps."""
        job = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        logs = (
            db_session.query(ConversionLog)
            .filter_by(job_id=job.id, workspace_id=WORKSPACE_ID)
            .order_by(ConversionLog.timestamp.asc())
            .all()
        )

        step_names = [log.step_name for log in logs]
        assert ConversionLogStepName.TEMPLATE_LOADED.value in step_names
        assert ConversionLogStepName.BEDROCK_INVOCATION_STARTED.value in step_names
        assert ConversionLogStepName.BEDROCK_INVOCATION_COMPLETED.value in step_names
        assert ConversionLogStepName.CONVERSION_COMPLETED.value in step_names

    @patch("services.conversion_service.time.sleep", return_value=None)
    def test_failed_conversion_creates_failure_log(self, mock_sleep, service, db_session):
        """Failed conversion creates a conversion_failed log entry."""
        service.bedrock_client.invoke_model.side_effect = RuntimeError("Bedrock error")

        request = StandaloneConversionRequest(
            source_code="SELECT 1",
            source_dialect="Bigquery",
            target_dialect="Redshift",
            asset_type=AssetType.QUERY,
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="s3://bucket/template.txt",
            max_retries=0,
            use_sqlglot=False,
        )

        job = service.create_standalone_conversion(request, WORKSPACE_ID, USER_ID)

        assert job.status == "failed"

        logs = (
            db_session.query(ConversionLog)
            .filter_by(job_id=job.id, workspace_id=WORKSPACE_ID)
            .all()
        )

        step_names = [log.step_name for log in logs]
        assert ConversionLogStepName.CONVERSION_FAILED.value in step_names
        assert ConversionLogStepName.BEDROCK_INVOCATION_FAILED.value in step_names

    def test_log_persistence_failure_does_not_break_conversion(self, service, db_session):
        """If log persistence fails, the conversion still completes."""
        original_create_log = service.repo.create_log
        service.repo.create_log = MagicMock(side_effect=RuntimeError("DB write failed"))

        job = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        # Conversion should still succeed despite log failures
        assert job.status == "completed"
        assert job.target_code is not None

        # Verify create_log was called (and failed)
        assert service.repo.create_log.call_count > 0

    def test_log_entries_have_correct_fields(self, service, db_session):
        """Each log entry has timestamp, log_level, step_name, and message."""
        job = service.create_standalone_conversion(
            STANDALONE_REQUEST, WORKSPACE_ID, USER_ID,
        )

        logs = (
            db_session.query(ConversionLog)
            .filter_by(job_id=job.id, workspace_id=WORKSPACE_ID)
            .all()
        )

        assert len(logs) > 0
        for log in logs:
            assert log.timestamp is not None
            assert log.log_level in ("INFO", "WARNING", "ERROR")
            assert log.step_name is not None
            assert log.message is not None
            assert log.workspace_id == WORKSPACE_ID


# ── Delegation method tests ──────────────────────────────────────────

class TestDelegationMethods:
    """Test that get_job_logs, list_batches, delete_batch, and
    bulk_delete_jobs delegate to the repository."""

    def test_get_job_logs_delegates_to_repo(self, service):
        """get_job_logs calls repo.list_logs_by_job with correct args."""
        mock_logs = [MagicMock(spec=ConversionLog)]
        service.repo.list_logs_by_job = MagicMock(return_value=mock_logs)

        result = service.get_job_logs(job_id=42, workspace_id=WORKSPACE_ID)

        service.repo.list_logs_by_job.assert_called_once_with(42, WORKSPACE_ID)
        assert result == mock_logs

    def test_list_batches_delegates_to_repo(self, service):
        """list_batches calls repo.list_batches with correct args."""
        mock_result = ([], 0)
        service.repo.list_batches = MagicMock(return_value=mock_result)

        result = service.list_batches(workspace_id=WORKSPACE_ID, page=2, page_size=10)

        service.repo.list_batches.assert_called_once_with(WORKSPACE_ID, 2, 10)
        assert result == mock_result

    def test_delete_batch_delegates_to_repo(self, service):
        """delete_batch calls repo.delete_batch with correct args."""
        service.repo.delete_batch = MagicMock(return_value=True)

        result = service.delete_batch(batch_id=5, workspace_id=WORKSPACE_ID)

        service.repo.delete_batch.assert_called_once_with(5, WORKSPACE_ID)
        assert result is True

    def test_delete_batch_returns_false_when_not_found(self, service):
        """delete_batch returns False when repo returns False."""
        service.repo.delete_batch = MagicMock(return_value=False)

        result = service.delete_batch(batch_id=999, workspace_id=WORKSPACE_ID)

        assert result is False

    def test_bulk_delete_jobs_delegates_to_repo(self, service):
        """bulk_delete_jobs calls repo.bulk_delete_jobs with correct args."""
        service.repo.bulk_delete_jobs = MagicMock(return_value=3)

        result = service.bulk_delete_jobs(job_ids=[1, 2, 3], workspace_id=WORKSPACE_ID)

        service.repo.bulk_delete_jobs.assert_called_once_with([1, 2, 3], WORKSPACE_ID)
        assert result == 3

    def test_bulk_delete_jobs_empty_list(self, service):
        """bulk_delete_jobs with empty list delegates and returns 0."""
        service.repo.bulk_delete_jobs = MagicMock(return_value=0)

        result = service.bulk_delete_jobs(job_ids=[], workspace_id=WORKSPACE_ID)

        service.repo.bulk_delete_jobs.assert_called_once_with([], WORKSPACE_ID)
        assert result == 0
