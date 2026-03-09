"""
Unit tests for ExportService and DeployService.

Tests cover:
- Single .sql generation (correct filename and content)
- Batch .sql generation (comment headers separating assets)
- S3 export with mocked boto3 S3 client
- Deploy ordering (TABLE_DDL → VIEW → procedures → materialized views → scheduled queries)
- Deploy stops on first failure and reports partial results
"""

import json
import pytest
from unittest.mock import MagicMock, patch, call

from services.conversion_export_service import ExportService
from services.conversion_deploy_service import DeployService, DeployResult, ASSET_DEPLOY_ORDER


# ── Helpers ───────────────────────────────────────────────────────────

def _make_job(**overrides):
    """Create a mock ConversionJob with sensible defaults."""
    defaults = {
        "id": 1,
        "workspace_id": 1,
        "batch_id": 10,
        "source_code": "SELECT 1",
        "target_code": "SELECT 1",
        "source_dialect": "bigquery",
        "target_dialect": "redshift",
        "asset_type": "TABLE_DDL",
        "asset_name": "my_table",
        "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
        "aws_region": "us-east-1",
        "prompt_template_path": "s3://bucket/template.txt",
        "use_sqlglot": False,
        "sqlglot_success": None,
        "status": "completed",
        "error_message": None,
        "retry_count": 0,
        "created_by": "testuser",
    }
    defaults.update(overrides)
    job = MagicMock()
    for k, v in defaults.items():
        setattr(job, k, v)
    return job


def _make_batch(**overrides):
    """Create a mock ConversionBatch with sensible defaults."""
    defaults = {
        "id": 10,
        "workspace_id": 1,
        "migration_project_id": 1,
        "source_connection_id": 10,
        "target_connection_id": 20,
        "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
        "aws_region": "us-east-1",
        "prompt_template_path": "s3://bucket/template.txt",
        "use_sqlglot": False,
        "max_retries": 3,
        "status": "completed",
        "total_assets": 3,
        "completed_assets": 3,
        "failed_assets": 0,
        "created_by": "testuser",
    }
    defaults.update(overrides)
    batch = MagicMock()
    for k, v in defaults.items():
        setattr(batch, k, v)
    return batch


def _make_connection(**overrides):
    """Create a mock Connection with sensible defaults."""
    defaults = {
        "id": 20,
        "name": "target_db",
        "type": "postgresql",
        "database": "mydb",
        "connection_params": {
            "host": "localhost",
            "port": 5432,
            "database": "mydb",
            "username": "dbuser",
            "password": "DbPass123!",
        },
        "connection_params_encrypted": None,
    }
    defaults.update(overrides)
    conn = MagicMock()
    for k, v in defaults.items():
        setattr(conn, k, v)
    return conn


# ── ExportService Tests ───────────────────────────────────────────────

class TestGenerateSingleSql:
    """Test ExportService.generate_single_sql."""

    def test_produces_correct_filename_and_content(self):
        """Single .sql export returns target_code bytes and descriptive filename."""
        job = _make_job(
            asset_name="users_table",
            target_dialect="redshift",
            target_code="CREATE TABLE users (id INT);",
        )
        svc = ExportService()

        content, filename = svc.generate_single_sql(job)

        assert filename == "users_table_redshift.sql"
        assert content == b"CREATE TABLE users (id INT);"

    def test_uses_job_id_fallback_when_no_asset_name(self):
        """When asset_name is None, filename uses job_{id} as fallback."""
        job = _make_job(id=42, asset_name=None, target_dialect="postgresql")
        svc = ExportService()

        content, filename = svc.generate_single_sql(job)

        assert filename == "job_42_postgresql.sql"

    def test_raises_when_no_target_code(self):
        """Raises ValueError when job has no converted code."""
        job = _make_job(target_code=None)
        svc = ExportService()

        with pytest.raises(ValueError, match="no converted code"):
            svc.generate_single_sql(job)

    def test_handles_unicode_content(self):
        """Target code with unicode characters is encoded correctly."""
        job = _make_job(target_code="SELECT '日本語' FROM tbl;")
        svc = ExportService()

        content, _ = svc.generate_single_sql(job)

        assert content == "SELECT '日本語' FROM tbl;".encode("utf-8")


class TestGenerateBatchSql:
    """Test ExportService.generate_batch_sql."""

    def test_includes_comment_headers_separating_assets(self):
        """Batch .sql output has comment headers for each asset."""
        jobs = [
            _make_job(id=1, asset_name="table_a", asset_type="TABLE_DDL", target_code="CREATE TABLE a;"),
            _make_job(id=2, asset_name="view_b", asset_type="VIEW", target_code="CREATE VIEW b AS SELECT 1;"),
        ]
        svc = ExportService()

        result = svc.generate_batch_sql(jobs)
        text = result.decode("utf-8")

        assert "-- Asset: table_a (TABLE_DDL)" in text
        assert "-- Asset: view_b (VIEW)" in text
        assert "CREATE TABLE a;" in text
        assert "CREATE VIEW b AS SELECT 1;" in text

    def test_skips_jobs_without_target_code(self):
        """Jobs with no target_code are excluded from the batch output."""
        jobs = [
            _make_job(id=1, asset_name="good", target_code="SELECT 1;"),
            _make_job(id=2, asset_name="bad", target_code=None),
            _make_job(id=3, asset_name="also_good", target_code="SELECT 2;"),
        ]
        svc = ExportService()

        text = svc.generate_batch_sql(jobs).decode("utf-8")

        assert "-- Asset: good" in text
        assert "-- Asset: also_good" in text
        assert "bad" not in text

    def test_empty_jobs_list_returns_empty_bytes(self):
        """An empty job list produces empty bytes."""
        svc = ExportService()

        assert svc.generate_batch_sql([]) == b""

    def test_single_job_has_no_leading_blank_lines(self):
        """A single job should not have leading blank lines."""
        jobs = [_make_job(asset_name="only", target_code="SELECT 1;")]
        svc = ExportService()

        text = svc.generate_batch_sql(jobs).decode("utf-8")

        assert text.startswith("-- Asset: only")


class TestExportToS3:
    """Test ExportService.export_to_s3 with mocked boto3."""

    @patch("services.conversion_export_service.boto3")
    def test_uploads_files_organized_by_asset_type(self, mock_boto3):
        """Each job is uploaded to {prefix}/{asset_type}/{asset_name}.sql."""
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3

        jobs = [
            _make_job(asset_name="tbl_a", asset_type="TABLE_DDL", target_code="CREATE TABLE a;"),
            _make_job(asset_name="view_b", asset_type="VIEW", target_code="CREATE VIEW b;"),
        ]
        svc = ExportService()

        svc.export_to_s3(jobs, "s3://my-bucket/exports/batch-1", "us-east-1")

        mock_boto3.client.assert_called_once_with("s3", region_name="us-east-1")
        assert mock_s3.put_object.call_count == 2

        calls = mock_s3.put_object.call_args_list
        keys = {c.kwargs["Key"] for c in calls}
        assert "exports/batch-1/TABLE_DDL/tbl_a.sql" in keys
        assert "exports/batch-1/VIEW/view_b.sql" in keys

        for c in calls:
            assert c.kwargs["Bucket"] == "my-bucket"
            assert c.kwargs["ContentType"] == "application/sql"

    @patch("services.conversion_export_service.boto3")
    def test_skips_jobs_without_target_code(self, mock_boto3):
        """Jobs with no target_code are not uploaded."""
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3

        jobs = [
            _make_job(asset_name="good", target_code="SELECT 1;"),
            _make_job(asset_name="bad", target_code=None),
        ]
        svc = ExportService()

        svc.export_to_s3(jobs, "s3://bucket/prefix", "us-east-1")

        assert mock_s3.put_object.call_count == 1

    @patch("services.conversion_export_service.boto3")
    def test_handles_s3_path_without_prefix(self, mock_boto3):
        """S3 path with only bucket (no prefix) uses asset_type as top-level key."""
        mock_s3 = MagicMock()
        mock_boto3.client.return_value = mock_s3

        jobs = [_make_job(asset_name="tbl", asset_type="TABLE_DDL", target_code="CREATE TABLE t;")]
        svc = ExportService()

        svc.export_to_s3(jobs, "s3://my-bucket", "us-east-1")

        key = mock_s3.put_object.call_args.kwargs["Key"]
        assert key == "TABLE_DDL/tbl.sql"

    def test_invalid_s3_path_raises_value_error(self):
        """An S3 path not starting with s3:// raises ValueError."""
        svc = ExportService()

        with pytest.raises(ValueError, match="Invalid S3 path"):
            svc.export_to_s3([], "https://bucket/path", "us-east-1")


# ── DeployService Tests ───────────────────────────────────────────────

class TestDeployOrdering:
    """Test that DeployService executes assets in dependency order."""

    @patch("services.conversion_deploy_service.DeployService._execute_sql")
    def test_table_ddl_before_views_before_procedures(self, mock_exec):
        """Assets are deployed in order: TABLE_DDL → VIEW → STORED_PROCEDURE → FUNCTION → MATERIALIZED_VIEW → SCHEDULED_QUERY."""
        jobs = [
            _make_job(id=1, asset_name="sp_proc", asset_type="STORED_PROCEDURE", target_code="CREATE PROC sp;"),
            _make_job(id=2, asset_name="my_view", asset_type="VIEW", target_code="CREATE VIEW v;"),
            _make_job(id=3, asset_name="my_table", asset_type="TABLE_DDL", target_code="CREATE TABLE t;"),
            _make_job(id=4, asset_name="my_func", asset_type="FUNCTION", target_code="CREATE FUNCTION f;"),
            _make_job(id=5, asset_name="mat_view", asset_type="MATERIALIZED_VIEW", target_code="CREATE MAT VIEW mv;"),
            _make_job(id=6, asset_name="sched_q", asset_type="SCHEDULED_QUERY", target_code="CREATE SCHEDULE s;"),
        ]
        batch = _make_batch()
        conn = _make_connection()
        svc = DeployService()

        result = svc.deploy_batch(batch, jobs, conn)

        assert result.success is True
        assert len(result.deployed_assets) == 6

        # Verify execution order via call sequence
        executed_sqls = [c.kwargs["sql"] for c in mock_exec.call_args_list]
        assert executed_sqls[0] == "CREATE TABLE t;"       # TABLE_DDL
        assert executed_sqls[1] == "CREATE VIEW v;"        # VIEW
        assert executed_sqls[2] == "CREATE PROC sp;"       # STORED_PROCEDURE
        assert executed_sqls[3] == "CREATE FUNCTION f;"    # FUNCTION
        assert executed_sqls[4] == "CREATE MAT VIEW mv;"   # MATERIALIZED_VIEW
        assert executed_sqls[5] == "CREATE SCHEDULE s;"    # SCHEDULED_QUERY

    @patch("services.conversion_deploy_service.DeployService._execute_sql")
    def test_deploy_result_contains_all_asset_names(self, mock_exec):
        """DeployResult.deployed_assets lists all successfully deployed asset names."""
        jobs = [
            _make_job(asset_name="tbl_a", asset_type="TABLE_DDL", target_code="CREATE TABLE a;"),
            _make_job(asset_name="view_b", asset_type="VIEW", target_code="CREATE VIEW b;"),
        ]
        svc = DeployService()

        result = svc.deploy_batch(_make_batch(), jobs, _make_connection())

        assert result.deployed_assets == ["tbl_a", "view_b"]


class TestDeployStopsOnFailure:
    """Test that deployment stops on first failure and reports partial results."""

    @patch("services.conversion_deploy_service.DeployService._execute_sql")
    def test_stops_on_first_failure(self, mock_exec):
        """When a deployment fails, subsequent assets are not attempted."""
        mock_exec.side_effect = [
            None,  # TABLE_DDL succeeds
            RuntimeError("VIEW creation failed"),  # VIEW fails
        ]

        jobs = [
            _make_job(id=1, asset_name="tbl", asset_type="TABLE_DDL", target_code="CREATE TABLE t;"),
            _make_job(id=2, asset_name="vw", asset_type="VIEW", target_code="CREATE VIEW v;"),
            _make_job(id=3, asset_name="sp", asset_type="STORED_PROCEDURE", target_code="CREATE PROC p;"),
        ]
        svc = DeployService()

        result = svc.deploy_batch(_make_batch(), jobs, _make_connection())

        assert result.success is False
        assert result.deployed_assets == ["tbl"]
        assert result.failed_asset == "vw"
        assert "VIEW creation failed" in result.error_message
        # Only 2 calls: tbl succeeded, vw failed, sp never attempted
        assert mock_exec.call_count == 2

    @patch("services.conversion_deploy_service.DeployService._execute_sql")
    def test_first_asset_failure_returns_empty_deployed(self, mock_exec):
        """When the very first asset fails, deployed_assets is empty."""
        mock_exec.side_effect = RuntimeError("immediate failure")

        jobs = [
            _make_job(asset_name="tbl", asset_type="TABLE_DDL", target_code="CREATE TABLE t;"),
        ]
        svc = DeployService()

        result = svc.deploy_batch(_make_batch(), jobs, _make_connection())

        assert result.success is False
        assert result.deployed_assets == []
        assert result.failed_asset == "tbl"

    @patch("services.conversion_deploy_service.DeployService._execute_sql")
    def test_no_deployable_assets_returns_success(self, mock_exec):
        """When all jobs lack target_code, result is success with empty list."""
        jobs = [
            _make_job(asset_name="bad", target_code=None),
        ]
        svc = DeployService()

        result = svc.deploy_batch(_make_batch(), jobs, _make_connection())

        assert result.success is True
        assert result.deployed_assets == []
        mock_exec.assert_not_called()


class TestDeployConnectionDecryption:
    """Test that DeployService decrypts encrypted connection params."""

    @patch("services.conversion_deploy_service.DeployService._execute_sql")
    @patch("services.conversion_deploy_service.get_encryption_service")
    def test_uses_encrypted_params_when_available(self, mock_get_enc, mock_exec):
        """When connection_params_encrypted is set, it is decrypted and used."""
        encrypted_params = json.dumps({
            "host": "secure-host",
            "port": 5439,
            "database": "prod_db",
            "username": "admin",
            "password": "SecretPass!",
        })
        mock_enc_svc = MagicMock()
        mock_enc_svc.decrypt.return_value = encrypted_params
        mock_get_enc.return_value = mock_enc_svc

        conn = _make_connection(
            connection_params_encrypted="encrypted_blob_here",
            connection_params={"host": "fallback"},
        )
        jobs = [_make_job(asset_name="tbl", asset_type="TABLE_DDL", target_code="CREATE TABLE t;")]
        svc = DeployService()

        svc.deploy_batch(_make_batch(), jobs, conn)

        mock_enc_svc.decrypt.assert_called_once_with("encrypted_blob_here")
        # _execute_sql should have been called with the decrypted params
        call_kwargs = mock_exec.call_args.kwargs
        assert call_kwargs["conn_params"]["host"] == "secure-host"

    @patch("services.conversion_deploy_service.DeployService._execute_sql")
    def test_uses_unencrypted_params_as_fallback(self, mock_exec):
        """When no encrypted params, unencrypted connection_params are used."""
        conn = _make_connection(
            connection_params_encrypted=None,
            connection_params={"host": "plain-host", "port": 5432, "database": "db", "username": "u", "password": "p"},
        )
        jobs = [_make_job(asset_name="tbl", asset_type="TABLE_DDL", target_code="CREATE TABLE t;")]
        svc = DeployService()

        svc.deploy_batch(_make_batch(), jobs, conn)

        call_kwargs = mock_exec.call_args.kwargs
        assert call_kwargs["conn_params"]["host"] == "plain-host"


class TestDeployResult:
    """Test DeployResult dataclass."""

    def test_success_result(self):
        """A successful DeployResult has expected defaults."""
        result = DeployResult(success=True, deployed_assets=["a", "b"])

        assert result.success is True
        assert result.deployed_assets == ["a", "b"]
        assert result.failed_asset is None
        assert result.error_message is None

    def test_failure_result(self):
        """A failed DeployResult captures the failed asset and error."""
        result = DeployResult(
            success=False,
            deployed_assets=["a"],
            failed_asset="b",
            error_message="syntax error",
        )

        assert result.success is False
        assert result.failed_asset == "b"
        assert result.error_message == "syntax error"
