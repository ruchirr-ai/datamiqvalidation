# Feature: code-conversion-enhancements, Property 12: Batch delete cascades to associated jobs
"""
Property test: Batch delete cascades to associated jobs.

For any batch ID and workspace, deleting the batch should also delete all
ConversionJob records with that batch_id. No jobs from other batches or
workspaces should be affected.

**Validates: Requirements 13.5**

NOTE: The production schema (after migration 019) uses ON DELETE CASCADE on
conversion_jobs.batch_id. The SQLAlchemy model still declares SET NULL for
backward compatibility, so this test creates its own schema with CASCADE
to match the post-migration production behavior.
"""

import pytest
from hypothesis import given, settings, strategies as st
from sqlalchemy import (
    create_engine, event, Column, Integer, String, Text, Boolean,
    DateTime, ForeignKey, Index, MetaData, Table, text as sa_text,
)
from sqlalchemy.orm import sessionmaker, registry, relationship
from datetime import datetime

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

BATCH_DEFAULTS = {
    "source_connection_id": 10,
    "target_connection_id": 20,
    "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "aws_region": "us-east-1",
    "prompt_template_path": "s3://bucket/template.txt",
    "use_sqlglot": False,
    "max_retries": 3,
    "status": "pending",
    "total_assets": 0,
    "completed_assets": 0,
    "failed_assets": 0,
    "created_by": "testuser",
}


def make_session():
    """Create a fresh in-memory SQLite session with FK enforcement.

    After creating all tables from Base metadata, we drop and recreate the
    conversion_jobs.batch_id FK with ON DELETE CASCADE to match the
    post-migration 019 production schema.
    """
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    # SQLite doesn't support ALTER TABLE DROP CONSTRAINT, so we recreate
    # the jobs table with CASCADE. Since this is a fresh in-memory DB,
    # we can safely do this by recreating with the correct FK.
    # However, SQLAlchemy's create_all already created the table with SET NULL.
    # For SQLite, we need to recreate the table. Instead, we'll use a
    # workaround: since PRAGMA foreign_keys=ON is set, SQLite will honor
    # the FK action. We'll use raw SQL to recreate the table.
    with engine.connect() as conn:
        # Get existing data (none, fresh DB)
        # Drop old table and recreate with CASCADE
        conn.execute(sa_text("DROP TABLE IF EXISTS conversion_jobs"))
        conn.execute(sa_text("""
            CREATE TABLE conversion_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id INTEGER NOT NULL,
                batch_id INTEGER REFERENCES conversion_batches(id) ON DELETE CASCADE,
                source_code TEXT NOT NULL,
                target_code TEXT,
                source_dialect VARCHAR(50) NOT NULL,
                target_dialect VARCHAR(50) NOT NULL,
                asset_type VARCHAR(50) NOT NULL,
                asset_name VARCHAR(255),
                bedrock_model VARCHAR(255) NOT NULL,
                aws_region VARCHAR(50) NOT NULL,
                prompt_template_path VARCHAR(1024) NOT NULL,
                use_sqlglot BOOLEAN NOT NULL DEFAULT 0,
                sqlglot_success BOOLEAN,
                status VARCHAR(50) NOT NULL DEFAULT 'pending',
                error_message TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                created_by VARCHAR(255) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()

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
def batch_cascade_scenario(draw):
    """Generate a scenario with multiple batches, each with random job counts,
    plus standalone jobs (no batch). One batch is selected for deletion."""
    num_batches = draw(st.integers(min_value=1, max_value=5))
    jobs_per_batch = [
        draw(st.integers(min_value=0, max_value=8))
        for _ in range(num_batches)
    ]
    standalone_count = draw(st.integers(min_value=0, max_value=5))
    # Index of batch to delete (0-based)
    delete_index = draw(st.integers(min_value=0, max_value=num_batches - 1))
    # Also test cross-workspace: jobs in workspace 2
    ws2_job_count = draw(st.integers(min_value=0, max_value=3))
    return num_batches, jobs_per_batch, standalone_count, delete_index, ws2_job_count


@settings(max_examples=20)
@given(scenario=batch_cascade_scenario())
def test_batch_delete_cascades_to_associated_jobs(scenario):
    """Property 12: Batch delete cascades to associated jobs.

    **Validates: Requirements 13.5**
    """
    num_batches, jobs_per_batch, standalone_count, delete_index, ws2_job_count = scenario

    session = make_session()
    try:
        repo = ConversionRepository(session)

        # Create batches in workspace 1
        batches = []
        for i in range(num_batches):
            batch_data = {**BATCH_DEFAULTS, "workspace_id": 1, "total_assets": jobs_per_batch[i]}
            batch = repo.create_batch(**batch_data)
            batches.append(batch)

        # Create jobs for each batch
        batch_job_ids = {}  # batch_id -> list of job ids
        for i, batch in enumerate(batches):
            job_ids = []
            for j in range(jobs_per_batch[i]):
                job = repo.create_job(
                    **JOB_DEFAULTS,
                    workspace_id=1,
                    batch_id=batch.id,
                    asset_name=f"batch{i}_job{j}",
                )
                job_ids.append(job.id)
            batch_job_ids[batch.id] = job_ids

        # Create standalone jobs (no batch) in workspace 1
        standalone_ids = []
        for i in range(standalone_count):
            job = repo.create_job(
                **JOB_DEFAULTS,
                workspace_id=1,
                asset_name=f"standalone_{i}",
            )
            standalone_ids.append(job.id)

        # Create jobs in workspace 2
        ws2_ids = []
        for i in range(ws2_job_count):
            job = repo.create_job(
                **JOB_DEFAULTS,
                workspace_id=2,
                asset_name=f"ws2_job_{i}",
            )
            ws2_ids.append(job.id)

        # Record the batch to delete and its expected cascaded job IDs
        target_batch = batches[delete_index]
        target_job_ids = batch_job_ids[target_batch.id]

        # Collect IDs of jobs that should survive
        surviving_batch_job_ids = []
        for i, batch in enumerate(batches):
            if i != delete_index:
                surviving_batch_job_ids.extend(batch_job_ids[batch.id])

        # Delete the target batch
        result = repo.delete_batch(target_batch.id, workspace_id=1)
        assert result is True

        # Verify: batch is gone
        assert repo.get_batch(target_batch.id, workspace_id=1) is None

        # Verify: cascaded jobs are gone
        for job_id in target_job_ids:
            assert repo.get_job(job_id, workspace_id=1) is None

        # Verify: other batch jobs still exist
        for job_id in surviving_batch_job_ids:
            assert repo.get_job(job_id, workspace_id=1) is not None

        # Verify: standalone jobs still exist
        for job_id in standalone_ids:
            assert repo.get_job(job_id, workspace_id=1) is not None

        # Verify: workspace 2 jobs are untouched
        for job_id in ws2_ids:
            assert repo.get_job(job_id, workspace_id=2) is not None
    finally:
        session.close()
