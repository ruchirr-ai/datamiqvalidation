# Feature: code-conversion-enhancements, Property 1: Bulk delete removes exactly the selected jobs
"""
Property test: Bulk delete removes exactly the selected jobs.

For any workspace and any subset of job IDs belonging to that workspace,
calling bulk delete with those IDs should remove exactly those jobs from
the database, leaving all other jobs in the workspace (and all jobs in
other workspaces) unchanged.

**Validates: Requirements 1.4**
"""

import pytest
from hypothesis import given, settings, strategies as st
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from database import Base
from models.conversion_job import ConversionJob
from models.conversion_batch import ConversionBatch
from models.conversion_log import ConversionLog
from models.connection import Connection
from repositories.conversion_repository import ConversionRepository


JOB_DEFAULTS = {
    "source_code": "SELECT 1",
    "source_dialect": "bigquery",
    "target_dialect": "redshift",
    "asset_type": "TABLE_DDL",
    "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "aws_region": "us-east-1",
    "prompt_template_path": "s3://bucket/template.txt",
    "use_sqlglot": False,
    "status": "pending",
    "retry_count": 0,
    "created_by": "testuser",
}


def make_session():
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


# Strategy: generate a total job count (1-20) and a subset to delete
@st.composite
def bulk_delete_scenario(draw):
    """Generate a scenario with N jobs in workspace 1, a subset to delete,
    and M jobs in workspace 2 that must remain untouched."""
    ws1_count = draw(st.integers(min_value=1, max_value=20))
    ws2_count = draw(st.integers(min_value=0, max_value=5))
    # Indices of ws1 jobs to delete (subset of 0..ws1_count-1)
    delete_indices = draw(
        st.lists(
            st.integers(min_value=0, max_value=ws1_count - 1),
            unique=True,
            min_size=0,
            max_size=ws1_count,
        )
    )
    return ws1_count, ws2_count, sorted(delete_indices)


@settings(max_examples=20)
@given(scenario=bulk_delete_scenario())
def test_bulk_delete_removes_exactly_selected_jobs(scenario):
    """Property 1: Bulk delete removes exactly the selected jobs.

    **Validates: Requirements 1.4**
    """
    ws1_count, ws2_count, delete_indices = scenario

    session = make_session()
    try:
        repo = ConversionRepository(session)

        # Create ws1 jobs
        ws1_jobs = []
        for i in range(ws1_count):
            job = repo.create_job(
                **JOB_DEFAULTS, workspace_id=1, asset_name=f"ws1_job_{i}",
            )
            ws1_jobs.append(job)

        # Create ws2 jobs
        ws2_jobs = []
        for i in range(ws2_count):
            job = repo.create_job(
                **JOB_DEFAULTS, workspace_id=2, asset_name=f"ws2_job_{i}",
            )
            ws2_jobs.append(job)

        # Determine IDs to delete
        ids_to_delete = [ws1_jobs[i].id for i in delete_indices]
        ids_to_keep = [ws1_jobs[i].id for i in range(ws1_count) if i not in delete_indices]

        # Execute bulk delete
        deleted_count = repo.bulk_delete_jobs(ids_to_delete, workspace_id=1)

        # Verify: exactly the selected count was deleted
        assert deleted_count == len(ids_to_delete)

        # Verify: deleted jobs are gone
        for job_id in ids_to_delete:
            assert repo.get_job(job_id, workspace_id=1) is None

        # Verify: remaining ws1 jobs still exist
        for job_id in ids_to_keep:
            assert repo.get_job(job_id, workspace_id=1) is not None

        # Verify: ws2 jobs are completely untouched
        for job in ws2_jobs:
            assert repo.get_job(job.id, workspace_id=2) is not None
    finally:
        session.close()
