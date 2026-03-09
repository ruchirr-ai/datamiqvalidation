# Feature: code-conversion-enhancements, Property 4: Asset type normalization
"""
Property test: Asset type normalization.

For any ConversionJob with asset_type equal to "QUERY" or "SCHEDULED_QUERY",
the ConversionService should accept both values and treat them equivalently
(both result in completed jobs).

**Validates: Requirements 5.4, 5.5**
"""

import pytest
from hypothesis import given, settings, strategies as st
from unittest.mock import MagicMock
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
    svc.sqlglot_parser = MagicMock()
    svc.sqlglot_parser.parse_and_transpile.return_value = SqlGlotResult(
        transpiled_code="SELECT 1", success=True, warning=None,
    )
    svc.audit_logger = MagicMock()
    return svc


@given(asset_type=st.sampled_from([AssetType.QUERY, AssetType.SCHEDULED_QUERY]))
@settings(max_examples=20)
def test_query_and_scheduled_query_both_complete(asset_type):
    """Property 4: Both QUERY and SCHEDULED_QUERY are accepted and produce completed jobs.

    **Validates: Requirements 5.4, 5.5**
    """
    session = _make_session()
    try:
        svc = _make_service(session)
        request = StandaloneConversionRequest(
            source_code="SELECT 1",
            source_dialect="Bigquery",
            target_dialect="Redshift",
            asset_type=asset_type,
            asset_name="test_asset",
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="prompts/test.txt",
            max_retries=0,
            use_sqlglot=False,
        )

        job = svc.create_standalone_conversion(request, workspace_id=1, user_id="tester")

        assert job.status == "completed"
        assert job.asset_type in ("QUERY", "SCHEDULED_QUERY")
    finally:
        session.close()
