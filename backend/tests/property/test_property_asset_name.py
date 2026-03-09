# Feature: code-conversion-enhancements, Property 2: Asset name round-trip persistence
"""
Property test: Asset name round-trip persistence.

For any valid asset name string (1-255 characters), when submitted as part of a
standalone conversion request, the resulting ConversionJob record should have
asset_name equal to the submitted value exactly.

**Validates: Requirements 2.3, 2.4**
"""

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


# Strategy: printable strings 1-255 chars (asset_name max_length=255)
asset_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=255,
)


@given(name=asset_name_strategy)
@settings(max_examples=20)
def test_asset_name_round_trip(name):
    """Property 2: asset_name submitted in request matches persisted ConversionJob.asset_name.

    **Validates: Requirements 2.3, 2.4**
    """
    session = _make_session()
    try:
        svc = _make_service(session)

        request = StandaloneConversionRequest(
            source_code="SELECT 1",
            source_dialect="Bigquery",
            target_dialect="Redshift",
            asset_type=AssetType.QUERY,
            asset_name=name,
            aws_region="us-east-1",
            bedrock_model="anthropic.claude-3-sonnet-20240229-v1:0",
            prompt_template_path="prompts/test.txt",
            max_retries=0,
            use_sqlglot=False,
        )

        job = svc.create_standalone_conversion(request, workspace_id=1, user_id="tester")

        assert job.status == "completed"
        assert job.asset_name == name, (
            f"Expected asset_name={name!r}, got {job.asset_name!r}"
        )
    finally:
        session.close()
