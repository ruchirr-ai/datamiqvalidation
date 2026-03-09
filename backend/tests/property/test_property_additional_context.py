# Feature: code-conversion-enhancements, Property 6 & 7: Additional context
"""
Property tests for additional context prompt construction and non-persistence.

Property 6: For any non-empty additional_context string of at most 50,000
characters, the rendered prompt should contain the additional context. For any
additional_context string exceeding 50,000 characters, the ConversionService
should reject the request with a ValueError (or Pydantic ValidationError).

Property 7: For any standalone conversion request that includes an
additional_context field, the resulting ConversionJob record should not contain
the additional_context value in any persisted column.

**Validates: Requirements 8.4, 8.5, 8.7**
"""

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import MagicMock, patch
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database import Base
from models.conversion_job import ConversionJob
from models.conversion_log import ConversionLog
from models.conversion_schemas import (
    StandaloneConversionRequest,
    AssetType,
)
from models.connection import Connection
from services.conversion_service import ConversionService
from services.conversion_cache import ConversionCache
from services.bedrock_client import BedrockClient
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


def _make_service(session):
    """Create a ConversionService with mocked external dependencies."""
    cache = MagicMock(spec=ConversionCache)
    svc = ConversionService(session, cache)
    svc.bedrock_client = MagicMock()
    svc.bedrock_client.fetch_prompt_template.return_value = (
        "Convert {source_code} from {source_dialect} to {target_dialect} "
        "for {asset_type}. sqlglot: {sqlglot_output}"
    )
    svc.bedrock_client.invoke_model.return_value = "SELECT 1"
    # Make render_prompt use the real implementation so we can verify context
    svc.bedrock_client.render_prompt = BedrockClient.render_prompt
    svc.sqlglot_parser = MagicMock()
    svc.sqlglot_parser.parse_and_transpile.return_value = SqlGlotResult(
        transpiled_code="SELECT 1", success=True, warning=None,
    )
    svc.audit_logger = MagicMock()
    return svc


# ---------------------------------------------------------------------------
# Property 6: Additional context prompt construction
# ---------------------------------------------------------------------------

@given(context=st.text(min_size=1, max_size=50_000))
@settings(max_examples=20)
def test_additional_context_included_in_prompt(context):
    """Property 6: Valid additional_context (1-50,000 chars) is included in the prompt.

    **Validates: Requirements 8.4, 8.5**
    """
    session = _make_session()
    try:
        svc = _make_service(session)

        # Track the prompt passed to invoke_model
        captured_prompts = []
        original_invoke = svc.bedrock_client.invoke_model

        def capture_invoke(prompt, **kwargs):
            captured_prompts.append(prompt)
            return "SELECT 1"

        svc.bedrock_client.invoke_model = MagicMock(side_effect=capture_invoke)

        request = StandaloneConversionRequest(
            source_code="SELECT 1",
            source_dialect="Bigquery",
            target_dialect="Redshift",
            asset_type=AssetType.QUERY,
            asset_name="ctx_test",
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="prompts/test.txt",
            max_retries=0,
            use_sqlglot=False,
            additional_context=context,
        )

        job = svc.create_standalone_conversion(request, workspace_id=1, user_id="tester")
        assert job.status == "completed"

        # The prompt passed to invoke_model should contain the context
        assert len(captured_prompts) == 1
        assert context in captured_prompts[0]
    finally:
        session.close()


@given(extra_len=st.integers(min_value=1, max_value=10_000))
@settings(max_examples=20)
def test_additional_context_exceeding_limit_rejected(extra_len):
    """Property 6: additional_context exceeding 50,000 chars is rejected.

    **Validates: Requirements 8.4, 8.5**
    """
    # Build a string that is exactly 50_000 + extra_len characters long
    context = "x" * (50_000 + extra_len)
    with pytest.raises((ValueError, ValidationError)):
        StandaloneConversionRequest(
            source_code="SELECT 1",
            source_dialect="Bigquery",
            target_dialect="Redshift",
            asset_type=AssetType.QUERY,
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="prompts/test.txt",
            additional_context=context,
        )


# ---------------------------------------------------------------------------
# Property 7: Additional context is not persisted
# ---------------------------------------------------------------------------

@given(context=st.text(min_size=1, max_size=50_000))
@settings(max_examples=20)
def test_additional_context_not_persisted(context):
    """Property 7: additional_context is NOT stored on the ConversionJob record.

    **Validates: Requirements 8.7**
    """
    session = _make_session()
    try:
        svc = _make_service(session)

        request = StandaloneConversionRequest(
            source_code="SELECT 1",
            source_dialect="Bigquery",
            target_dialect="Redshift",
            asset_type=AssetType.QUERY,
            asset_name="persist_test",
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="prompts/test.txt",
            max_retries=0,
            use_sqlglot=False,
            additional_context=context,
        )

        job = svc.create_standalone_conversion(request, workspace_id=1, user_id="tester")

        # Verify the ConversionJob model does not have an additional_context attribute
        assert not hasattr(job, "additional_context"), (
            "ConversionJob should not have an additional_context attribute"
        )

        # Double-check: the persisted record's columns should not contain the context
        job_dict = job.to_dict()
        for key, value in job_dict.items():
            if isinstance(value, str) and len(context) > 0:
                # source_code and target_code are expected fields; context should
                # not appear as a dedicated column value
                if key not in ("source_code", "target_code", "error_message"):
                    assert value != context, (
                        f"additional_context was persisted in column '{key}'"
                    )
    finally:
        session.close()
