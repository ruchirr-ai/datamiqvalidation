# Feature: code-conversion-enhancements, Property 8: Conversion log completeness and persistence
"""
Property test: Conversion log completeness and persistence.

For any completed conversion job, querying logs by job_id and workspace_id
should return at least entries for template_loaded, bedrock_invocation_started,
bedrock_invocation_completed, and conversion_completed. Each log entry must
include timestamp, log_level, step_name, and message fields.

For any failed conversion job, the logs should include the corresponding
failure step entry.

**Validates: Requirements 9.1, 9.2, 9.7**
"""

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import MagicMock
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database import Base
from models.conversion_job import ConversionJob
from models.conversion_log import ConversionLog, ConversionLogStepName
from models.conversion_schemas import (
    StandaloneConversionRequest,
    AssetType,
)
from models.connection import Connection
from services.conversion_service import ConversionService
from services.conversion_cache import ConversionCache
from services.sqlglot_parser import SqlGlotResult


def _make_session():
    """Create a fresh in-memory SQLite session with FK enforcement."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add_all([
        Connection(
            id=10, name="src", type="bigquery", database="db",
            connection_params={"p": "t"}, created_by="sys",
        ),
        Connection(
            id=20, name="tgt", type="redshift", database="db",
            connection_params={"h": "l"}, created_by="sys",
        ),
    ])
    session.commit()
    return session


def _make_service(session, *, fail_bedrock=False):
    """Create a ConversionService with mocked external dependencies.

    Args:
        session: SQLAlchemy session.
        fail_bedrock: If True, mock Bedrock to raise an exception.
    """
    cache = MagicMock(spec=ConversionCache)
    svc = ConversionService(session, cache)
    svc.bedrock_client = MagicMock()
    svc.bedrock_client.fetch_prompt_template.return_value = (
        "Convert {source_code} from {source_dialect} to {target_dialect} "
        "for {asset_type}. sqlglot: {sqlglot_output}"
    )
    if fail_bedrock:
        svc.bedrock_client.invoke_model.side_effect = RuntimeError("Bedrock unavailable")
    else:
        svc.bedrock_client.invoke_model.return_value = "SELECT 1"
    svc.sqlglot_parser = MagicMock()
    svc.sqlglot_parser.parse_and_transpile.return_value = SqlGlotResult(
        transpiled_code="SELECT 1", success=True, warning=None,
    )
    svc.audit_logger = MagicMock()
    return svc


# Required steps for a successful conversion (no sqlglot)
REQUIRED_SUCCESS_STEPS = {
    ConversionLogStepName.TEMPLATE_LOADED.value,
    ConversionLogStepName.BEDROCK_INVOCATION_STARTED.value,
    ConversionLogStepName.BEDROCK_INVOCATION_COMPLETED.value,
    ConversionLogStepName.CONVERSION_COMPLETED.value,
}

# For a failed conversion, we expect at least the failure step
REQUIRED_FAILURE_STEPS = {
    ConversionLogStepName.BEDROCK_INVOCATION_FAILED.value,
    ConversionLogStepName.CONVERSION_FAILED.value,
}


@given(
    source_dialect=st.sampled_from(["Bigquery", "SQL Server", "Redshift"]),
    target_dialect=st.sampled_from(["Redshift", "SQL Server", "BigQuery"]),
    asset_type=st.sampled_from([AssetType.QUERY, AssetType.SCHEDULED_QUERY]),
)
@settings(max_examples=20)
def test_successful_conversion_logs_complete(source_dialect, target_dialect, asset_type):
    """Property 8: Successful conversions produce all required log steps.

    **Validates: Requirements 9.1, 9.2, 9.7**
    """
    session = _make_session()
    try:
        svc = _make_service(session)

        request = StandaloneConversionRequest(
            source_code="SELECT 1",
            source_dialect=source_dialect,
            target_dialect=target_dialect,
            asset_type=asset_type,
            asset_name="log_test",
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="prompts/test.txt",
            max_retries=0,
            use_sqlglot=False,
        )

        job = svc.create_standalone_conversion(request, workspace_id=1, user_id="tester")
        assert job.status == "completed"

        # Retrieve logs
        logs = svc.get_job_logs(job.id, workspace_id=1)
        step_names = {log.step_name for log in logs}

        # All required success steps must be present
        for step in REQUIRED_SUCCESS_STEPS:
            assert step in step_names, f"Missing required log step: {step}"

        # Each log entry must have required fields
        for log in logs:
            assert log.timestamp is not None
            assert log.log_level is not None and log.log_level != ""
            assert log.step_name is not None and log.step_name != ""
            assert log.message is not None and log.message != ""
    finally:
        session.close()


@given(
    source_dialect=st.sampled_from(["Bigquery", "SQL Server", "Redshift"]),
    target_dialect=st.sampled_from(["Redshift", "SQL Server", "BigQuery"]),
)
@settings(max_examples=20)
def test_failed_conversion_logs_contain_failure_steps(source_dialect, target_dialect):
    """Property 8: Failed conversions include failure step entries in logs.

    **Validates: Requirements 9.1, 9.2, 9.7**
    """
    session = _make_session()
    try:
        svc = _make_service(session, fail_bedrock=True)

        request = StandaloneConversionRequest(
            source_code="SELECT 1",
            source_dialect=source_dialect,
            target_dialect=target_dialect,
            asset_type=AssetType.QUERY,
            asset_name="fail_log_test",
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="prompts/test.txt",
            max_retries=0,
            use_sqlglot=False,
        )

        job = svc.create_standalone_conversion(request, workspace_id=1, user_id="tester")
        assert job.status == "failed"

        # Retrieve logs
        logs = svc.get_job_logs(job.id, workspace_id=1)
        step_names = {log.step_name for log in logs}

        # Failure steps must be present
        for step in REQUIRED_FAILURE_STEPS:
            assert step in step_names, f"Missing required failure log step: {step}"

        # Each log entry must have required fields
        for log in logs:
            assert log.timestamp is not None
            assert log.log_level is not None and log.log_level != ""
            assert log.step_name is not None and log.step_name != ""
            assert log.message is not None and log.message != ""
    finally:
        session.close()
