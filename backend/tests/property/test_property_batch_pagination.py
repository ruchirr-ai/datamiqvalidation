# Feature: code-conversion-enhancements, Property 11: Batch listing is paginated and ordered
"""
Property test: Batch listing is paginated and ordered.

For any workspace with N batch records, the GET /api/conversions/batches
endpoint should return batches ordered by created_at descending, with
correct pagination (total count, page boundaries).

**Validates: Requirements 13.2**
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, settings, strategies as st

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from models.connection import Connection  # noqa: F401
from models.conversion_batch import ConversionBatch  # noqa: F401
from models.conversion_job import ConversionJob  # noqa: F401
from models.conversion_log import ConversionLog  # noqa: F401
from repositories.conversion_repository import ConversionRepository


BATCH_DEFAULTS = {
    "source_connection_id": 10,
    "target_connection_id": 20,
    "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "aws_region": "us-east-1",
    "prompt_template_path": "s3://bucket/template.txt",
    "use_sqlglot": False,
    "max_retries": 3,
    "status": "pending",
    "total_assets": 1,
    "completed_assets": 0,
    "failed_assets": 0,
    "created_by": "testuser",
}


def make_session():
    """Create a fresh in-memory SQLite session with FK enforcement."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_conn, _):
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
    return session


@st.composite
def pagination_scenario(draw):
    """Generate a scenario with random batch count, page, and page_size."""
    num_batches = draw(st.integers(min_value=0, max_value=20))
    page_size = draw(st.integers(min_value=1, max_value=10))
    max_page = max(1, (num_batches + page_size - 1) // page_size)
    page = draw(st.integers(min_value=1, max_value=max_page))
    return num_batches, page, page_size


@settings(max_examples=20)
@given(scenario=pagination_scenario())
def test_batch_listing_paginated_and_ordered(scenario):
    """Property 11: Batch listing is paginated and ordered.

    Generate random batch records, verify listing order (created_at desc)
    and pagination boundaries.

    **Validates: Requirements 13.2**
    """
    num_batches, page, page_size = scenario

    session = make_session()
    try:
        repo = ConversionRepository(session)

        # Create batches with distinct timestamps
        base_time = datetime(2026, 1, 1, 0, 0, 0)
        created_batches = []
        for i in range(num_batches):
            batch = repo.create_batch(
                **BATCH_DEFAULTS,
                workspace_id=1,
            )
            # Set distinct created_at to ensure deterministic ordering
            batch.created_at = base_time + timedelta(minutes=i)
            session.commit()
            created_batches.append(batch)

        # Query via repository
        batches, total = repo.list_batches(
            workspace_id=1,
            page=page,
            page_size=page_size,
        )

        # Property: total count matches number of created batches
        assert total == num_batches

        # Property: returned page size is correct
        expected_start = (page - 1) * page_size
        expected_count = min(page_size, max(0, num_batches - expected_start))
        assert len(batches) == expected_count

        # Property: batches are ordered by created_at descending
        for i in range(len(batches) - 1):
            assert batches[i].created_at >= batches[i + 1].created_at

        # Property: page boundaries are correct — first item on page
        # corresponds to the correct offset in the full descending list
        if len(batches) > 0:
            # All batches sorted descending by created_at
            all_sorted = sorted(created_batches, key=lambda b: b.created_at, reverse=True)
            expected_first = all_sorted[expected_start]
            assert batches[0].id == expected_first.id

    finally:
        session.close()


@settings(max_examples=20)
@given(
    num_batches=st.integers(min_value=1, max_value=15),
    ws2_batches=st.integers(min_value=0, max_value=5),
)
def test_batch_listing_workspace_isolation(num_batches, ws2_batches):
    """Property 11 (supplementary): Batch listing only returns batches for the queried workspace.

    **Validates: Requirements 13.2**
    """
    session = make_session()
    try:
        repo = ConversionRepository(session)

        # Create batches in workspace 1
        for _ in range(num_batches):
            repo.create_batch(**BATCH_DEFAULTS, workspace_id=1)

        # Create batches in workspace 2
        for _ in range(ws2_batches):
            repo.create_batch(**BATCH_DEFAULTS, workspace_id=2)

        # Query workspace 1
        batches_ws1, total_ws1 = repo.list_batches(workspace_id=1, page=1, page_size=100)
        assert total_ws1 == num_batches
        assert len(batches_ws1) == num_batches
        for b in batches_ws1:
            assert b.workspace_id == 1

        # Query workspace 2
        batches_ws2, total_ws2 = repo.list_batches(workspace_id=2, page=1, page_size=100)
        assert total_ws2 == ws2_batches
        assert len(batches_ws2) == ws2_batches
        for b in batches_ws2:
            assert b.workspace_id == 2

    finally:
        session.close()
