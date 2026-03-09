"""
Unit tests for ConversionRepository.

Uses an in-memory SQLite database to validate CRUD operations,
workspace isolation, pagination, and filtering.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models.conversion_job import ConversionJob
from models.conversion_batch import ConversionBatch
from models.conversion_log import ConversionLog
from models.connection import Connection
from repositories.conversion_repository import ConversionRepository


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def db_session():
    """Create a fresh in-memory SQLite session for each test."""
    from sqlalchemy import event

    engine = create_engine("sqlite:///:memory:")

    # Enable FK enforcement so ON DELETE SET NULL works in SQLite
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
def repo(db_session):
    return ConversionRepository(db_session)


# Sample payloads ─────────────────────────────────────────────────────

JOB_DEFAULTS = {
    "workspace_id": 1,
    "source_code": "SELECT * FROM dataset.my_table",
    "source_dialect": "bigquery",
    "target_dialect": "redshift",
    "asset_type": "TABLE_DDL",
    "asset_name": "my_table",
    "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "aws_region": "us-east-1",
    "prompt_template_path": "s3://bucket/template.txt",
    "use_sqlglot": False,
    "status": "pending",
    "retry_count": 0,
    "created_by": "testuser",
}

BATCH_DEFAULTS = {
    "workspace_id": 1,
    "migration_project_id": 1,
    "source_connection_id": 10,
    "target_connection_id": 20,
    "bedrock_model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "aws_region": "us-east-1",
    "prompt_template_path": "s3://bucket/template.txt",
    "use_sqlglot": False,
    "max_retries": 3,
    "status": "pending",
    "total_assets": 2,
    "completed_assets": 0,
    "failed_assets": 0,
    "created_by": "testuser",
}


# ── ConversionJob CRUD tests ─────────────────────────────────────────

class TestCreateJob:
    """Test ConversionRepository.create_job"""

    def test_create_job_returns_persisted_instance(self, repo):
        """Creating a job persists it and returns an object with an id."""
        job = repo.create_job(**JOB_DEFAULTS)

        assert job.id is not None
        assert job.workspace_id == 1
        assert job.status == "pending"
        assert job.source_dialect == "bigquery"
        assert job.created_by == "testuser"

    def test_create_job_sets_defaults(self, repo):
        """Default values for use_sqlglot, retry_count, status are applied."""
        job = repo.create_job(**JOB_DEFAULTS)

        assert job.use_sqlglot is False
        assert job.retry_count == 0
        assert job.target_code is None
        assert job.error_message is None

    def test_create_multiple_jobs_unique_ids(self, repo):
        """Each created job gets a unique auto-incremented id."""
        j1 = repo.create_job(**JOB_DEFAULTS)
        j2 = repo.create_job(**{**JOB_DEFAULTS, "asset_name": "other_table"})

        assert j1.id != j2.id


class TestGetJob:
    """Test ConversionRepository.get_job"""

    def test_get_existing_job(self, repo):
        """Retrieving an existing job by id and workspace_id returns it."""
        created = repo.create_job(**JOB_DEFAULTS)
        fetched = repo.get_job(created.id, workspace_id=1)

        assert fetched is not None
        assert fetched.id == created.id

    def test_get_nonexistent_job_returns_none(self, repo):
        """Querying a non-existent id returns None."""
        assert repo.get_job(9999, workspace_id=1) is None

    def test_get_job_wrong_workspace_returns_none(self, repo):
        """Workspace isolation: job in workspace 1 is invisible to workspace 2."""
        created = repo.create_job(**JOB_DEFAULTS)
        assert repo.get_job(created.id, workspace_id=2) is None


class TestListJobs:
    """Test ConversionRepository.list_jobs with pagination and filtering."""

    def _seed_jobs(self, repo, count=5, **overrides):
        """Helper to create multiple jobs."""
        jobs = []
        for i in range(count):
            data = {**JOB_DEFAULTS, "asset_name": f"table_{i}", **overrides}
            jobs.append(repo.create_job(**data))
        return jobs

    def test_list_returns_jobs_and_total(self, repo):
        """list_jobs returns a (list, total_count) tuple."""
        self._seed_jobs(repo, count=3)
        jobs, total = repo.list_jobs(workspace_id=1)

        assert total == 3
        assert len(jobs) == 3

    def test_list_pagination(self, repo):
        """Pagination returns the correct slice and total."""
        self._seed_jobs(repo, count=5)

        page1, total = repo.list_jobs(workspace_id=1, page=1, page_size=2)
        page2, _ = repo.list_jobs(workspace_id=1, page=2, page_size=2)
        page3, _ = repo.list_jobs(workspace_id=1, page=3, page_size=2)

        assert total == 5
        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1

    def test_list_filter_by_status(self, repo):
        """Filtering by status returns only matching jobs."""
        self._seed_jobs(repo, count=2, status="pending")
        self._seed_jobs(repo, count=3, status="completed")

        pending, pending_total = repo.list_jobs(workspace_id=1, status="pending")
        completed, completed_total = repo.list_jobs(workspace_id=1, status="completed")

        assert pending_total == 2
        assert completed_total == 3

    def test_list_filter_by_asset_type(self, repo):
        """Filtering by asset_type returns only matching jobs."""
        self._seed_jobs(repo, count=2, asset_type="TABLE_DDL")
        self._seed_jobs(repo, count=1, asset_type="VIEW")

        ddl_jobs, ddl_total = repo.list_jobs(workspace_id=1, asset_type="TABLE_DDL")
        view_jobs, view_total = repo.list_jobs(workspace_id=1, asset_type="VIEW")

        assert ddl_total == 2
        assert view_total == 1

    def test_list_filter_by_source_dialect(self, repo):
        """Filtering by source_dialect returns only matching jobs."""
        self._seed_jobs(repo, count=2, source_dialect="bigquery")
        self._seed_jobs(repo, count=1, source_dialect="mongodb")

        bq_jobs, bq_total = repo.list_jobs(workspace_id=1, source_dialect="bigquery")
        mongo_jobs, mongo_total = repo.list_jobs(workspace_id=1, source_dialect="mongodb")

        assert bq_total == 2
        assert mongo_total == 1

    def test_list_workspace_isolation(self, repo):
        """Jobs in workspace 1 are not visible to workspace 2."""
        self._seed_jobs(repo, count=3, workspace_id=1)
        self._seed_jobs(repo, count=2, workspace_id=2)

        ws1_jobs, ws1_total = repo.list_jobs(workspace_id=1)
        ws2_jobs, ws2_total = repo.list_jobs(workspace_id=2)

        assert ws1_total == 3
        assert ws2_total == 2

    def test_list_empty_result(self, repo):
        """Listing with no matching jobs returns empty list and zero total."""
        jobs, total = repo.list_jobs(workspace_id=99)

        assert jobs == []
        assert total == 0


class TestUpdateJob:
    """Test ConversionRepository.update_job"""

    def test_update_existing_job(self, repo):
        """Updating fields on an existing job persists the changes."""
        job = repo.create_job(**JOB_DEFAULTS)
        updated = repo.update_job(
            job.id, workspace_id=1,
            status="completed",
            target_code="SELECT * FROM my_schema.my_table",
        )

        assert updated is not None
        assert updated.status == "completed"
        assert updated.target_code == "SELECT * FROM my_schema.my_table"

    def test_update_nonexistent_job_returns_none(self, repo):
        """Updating a non-existent job returns None."""
        assert repo.update_job(9999, workspace_id=1, status="failed") is None

    def test_update_wrong_workspace_returns_none(self, repo):
        """Workspace isolation: cannot update a job from another workspace."""
        job = repo.create_job(**JOB_DEFAULTS)
        assert repo.update_job(job.id, workspace_id=2, status="failed") is None

    def test_update_sets_updated_at(self, repo):
        """updated_at is refreshed on update."""
        job = repo.create_job(**JOB_DEFAULTS)
        original_updated = job.updated_at

        updated = repo.update_job(job.id, workspace_id=1, retry_count=1)
        assert updated.updated_at >= original_updated


class TestDeleteJob:
    """Test ConversionRepository.delete_job"""

    def test_delete_existing_job(self, repo):
        """Deleting an existing job removes it from the database."""
        job = repo.create_job(**JOB_DEFAULTS)
        result = repo.delete_job(job.id, workspace_id=1)

        assert result is True
        assert repo.get_job(job.id, workspace_id=1) is None

    def test_delete_nonexistent_job_returns_false(self, repo):
        """Deleting a non-existent job returns False."""
        assert repo.delete_job(9999, workspace_id=1) is False

    def test_delete_wrong_workspace_returns_false(self, repo):
        """Workspace isolation: cannot delete a job from another workspace."""
        job = repo.create_job(**JOB_DEFAULTS)
        assert repo.delete_job(job.id, workspace_id=2) is False
        # Job still exists in workspace 1
        assert repo.get_job(job.id, workspace_id=1) is not None


# ── ConversionBatch CRUD tests ───────────────────────────────────────

class TestCreateBatch:
    """Test ConversionRepository.create_batch"""

    def test_create_batch_returns_persisted_instance(self, repo):
        """Creating a batch persists it and returns an object with an id."""
        batch = repo.create_batch(**BATCH_DEFAULTS)

        assert batch.id is not None
        assert batch.workspace_id == 1
        assert batch.status == "pending"
        assert batch.total_assets == 2

    def test_create_batch_defaults(self, repo):
        """Default counters start at zero."""
        batch = repo.create_batch(**BATCH_DEFAULTS)

        assert batch.completed_assets == 0
        assert batch.failed_assets == 0


class TestGetBatch:
    """Test ConversionRepository.get_batch"""

    def test_get_existing_batch(self, repo):
        """Retrieving an existing batch by id and workspace_id returns it."""
        created = repo.create_batch(**BATCH_DEFAULTS)
        fetched = repo.get_batch(created.id, workspace_id=1)

        assert fetched is not None
        assert fetched.id == created.id

    def test_get_batch_wrong_workspace_returns_none(self, repo):
        """Workspace isolation: batch in workspace 1 is invisible to workspace 2."""
        created = repo.create_batch(**BATCH_DEFAULTS)
        assert repo.get_batch(created.id, workspace_id=2) is None


class TestListBatchJobs:
    """Test ConversionRepository.list_batch_jobs"""

    def test_list_batch_jobs(self, repo):
        """list_batch_jobs returns only jobs belonging to the given batch."""
        batch = repo.create_batch(**BATCH_DEFAULTS)
        repo.create_job(**{**JOB_DEFAULTS, "batch_id": batch.id})
        repo.create_job(**{**JOB_DEFAULTS, "batch_id": batch.id, "asset_name": "t2"})
        # Job without batch
        repo.create_job(**JOB_DEFAULTS)

        jobs = repo.list_batch_jobs(batch.id, workspace_id=1)
        assert len(jobs) == 2

    def test_list_batch_jobs_workspace_isolation(self, repo):
        """Batch jobs are filtered by workspace_id."""
        batch = repo.create_batch(**BATCH_DEFAULTS)
        repo.create_job(**{**JOB_DEFAULTS, "batch_id": batch.id})

        jobs = repo.list_batch_jobs(batch.id, workspace_id=2)
        assert len(jobs) == 0


class TestUpdateBatch:
    """Test ConversionRepository.update_batch"""

    def test_update_existing_batch(self, repo):
        """Updating fields on an existing batch persists the changes."""
        batch = repo.create_batch(**BATCH_DEFAULTS)
        updated = repo.update_batch(
            batch.id, workspace_id=1,
            status="in_progress",
            completed_assets=1,
        )

        assert updated is not None
        assert updated.status == "in_progress"
        assert updated.completed_assets == 1

    def test_update_batch_wrong_workspace_returns_none(self, repo):
        """Workspace isolation: cannot update a batch from another workspace."""
        batch = repo.create_batch(**BATCH_DEFAULTS)
        assert repo.update_batch(batch.id, workspace_id=2, status="failed") is None


class TestGetCompletedBatchJobs:
    """Test ConversionRepository.get_completed_batch_jobs"""

    def test_returns_only_completed_jobs(self, repo):
        """Only jobs with status='completed' are returned."""
        batch = repo.create_batch(**BATCH_DEFAULTS)
        repo.create_job(**{**JOB_DEFAULTS, "batch_id": batch.id, "status": "completed"})
        repo.create_job(**{**JOB_DEFAULTS, "batch_id": batch.id, "status": "failed", "asset_name": "t2"})
        repo.create_job(**{**JOB_DEFAULTS, "batch_id": batch.id, "status": "pending", "asset_name": "t3"})

        completed = repo.get_completed_batch_jobs(batch.id, workspace_id=1)
        assert len(completed) == 1
        assert completed[0].status == "completed"

    def test_completed_batch_jobs_workspace_isolation(self, repo):
        """Completed jobs are filtered by workspace_id."""
        batch = repo.create_batch(**BATCH_DEFAULTS)
        repo.create_job(**{**JOB_DEFAULTS, "batch_id": batch.id, "status": "completed"})

        completed = repo.get_completed_batch_jobs(batch.id, workspace_id=2)
        assert len(completed) == 0


# ── Cascade and edge-case tests ──────────────────────────────────────

class TestBatchDeletionCascade:
    """Test ON DELETE SET NULL cascade when a batch is deleted."""

    def test_deleting_batch_sets_job_batch_id_to_null(self, repo, db_session):
        """When a batch row is deleted, child jobs' batch_id becomes NULL (SET NULL)."""
        batch = repo.create_batch(**BATCH_DEFAULTS)
        job = repo.create_job(**{**JOB_DEFAULTS, "batch_id": batch.id})

        # Delete the batch directly via session to trigger FK cascade
        db_session.delete(batch)
        db_session.commit()
        db_session.refresh(job)

        assert job.batch_id is None
        # Job itself still exists
        assert repo.get_job(job.id, workspace_id=1) is not None

    def test_deleting_batch_preserves_all_child_jobs(self, repo, db_session):
        """All child jobs survive batch deletion with batch_id set to NULL."""
        batch = repo.create_batch(**BATCH_DEFAULTS)
        j1 = repo.create_job(**{**JOB_DEFAULTS, "batch_id": batch.id, "asset_name": "t1"})
        j2 = repo.create_job(**{**JOB_DEFAULTS, "batch_id": batch.id, "asset_name": "t2"})
        j3 = repo.create_job(**{**JOB_DEFAULTS, "batch_id": batch.id, "asset_name": "t3"})

        db_session.delete(batch)
        db_session.commit()

        for j in [j1, j2, j3]:
            db_session.refresh(j)
            assert j.batch_id is None

        # All three jobs still queryable
        jobs, total = repo.list_jobs(workspace_id=1)
        assert total == 3


class TestGetBatchEdgeCases:
    """Additional edge-case tests for batch retrieval."""

    def test_get_nonexistent_batch_returns_none(self, repo):
        """Querying a non-existent batch id returns None."""
        assert repo.get_batch(9999, workspace_id=1) is None

    def test_get_batch_nonexistent_workspace_returns_none(self, repo):
        """Querying a valid batch with a non-existent workspace returns None."""
        batch = repo.create_batch(**BATCH_DEFAULTS)
        assert repo.get_batch(batch.id, workspace_id=999) is None


class TestListJobsCombinedFilters:
    """Test list_jobs with multiple filters applied simultaneously."""

    def _seed(self, repo):
        """Seed a mix of jobs for combined filter testing."""
        combos = [
            {"status": "pending", "asset_type": "TABLE_DDL", "source_dialect": "bigquery"},
            {"status": "pending", "asset_type": "VIEW", "source_dialect": "bigquery"},
            {"status": "completed", "asset_type": "TABLE_DDL", "source_dialect": "bigquery"},
            {"status": "completed", "asset_type": "TABLE_DDL", "source_dialect": "mongodb"},
            {"status": "failed", "asset_type": "FUNCTION", "source_dialect": "mongodb"},
        ]
        for i, overrides in enumerate(combos):
            repo.create_job(**{**JOB_DEFAULTS, "asset_name": f"asset_{i}", **overrides})

    def test_filter_status_and_asset_type(self, repo):
        """Combining status + asset_type narrows results correctly."""
        self._seed(repo)
        jobs, total = repo.list_jobs(workspace_id=1, status="completed", asset_type="TABLE_DDL")
        assert total == 2  # bigquery + mongodb TABLE_DDL completed

    def test_filter_status_and_source_dialect(self, repo):
        """Combining status + source_dialect narrows results correctly."""
        self._seed(repo)
        jobs, total = repo.list_jobs(workspace_id=1, status="pending", source_dialect="bigquery")
        assert total == 2  # TABLE_DDL + VIEW pending bigquery

    def test_filter_all_three(self, repo):
        """Combining status + asset_type + source_dialect narrows to exact match."""
        self._seed(repo)
        jobs, total = repo.list_jobs(
            workspace_id=1, status="completed",
            asset_type="TABLE_DDL", source_dialect="mongodb",
        )
        assert total == 1

    def test_combined_filter_no_match(self, repo):
        """Combined filters that match nothing return empty."""
        self._seed(repo)
        jobs, total = repo.list_jobs(
            workspace_id=1, status="failed",
            asset_type="TABLE_DDL", source_dialect="bigquery",
        )
        assert total == 0
        assert jobs == []


class TestListJobsOrdering:
    """Test that list_jobs returns results ordered by created_at descending."""

    def test_jobs_ordered_by_created_at_desc(self, repo):
        """Most recently created jobs appear first."""
        j1 = repo.create_job(**{**JOB_DEFAULTS, "asset_name": "first"})
        j2 = repo.create_job(**{**JOB_DEFAULTS, "asset_name": "second"})
        j3 = repo.create_job(**{**JOB_DEFAULTS, "asset_name": "third"})

        jobs, _ = repo.list_jobs(workspace_id=1)

        # SQLite auto-increment means later inserts have higher ids / later created_at
        assert jobs[0].id == j3.id
        assert jobs[-1].id == j1.id


class TestUpdateBatchEdgeCases:
    """Additional edge-case tests for batch updates."""

    def test_update_batch_sets_updated_at(self, repo):
        """updated_at is refreshed on batch update."""
        batch = repo.create_batch(**BATCH_DEFAULTS)
        original = batch.updated_at

        updated = repo.update_batch(batch.id, workspace_id=1, completed_assets=3)
        assert updated.updated_at >= original

    def test_update_nonexistent_batch_returns_none(self, repo):
        """Updating a non-existent batch returns None."""
        assert repo.update_batch(9999, workspace_id=1, status="failed") is None


# ── ConversionLog tests ──────────────────────────────────────────────

LOG_ENTRY_DEFAULTS = {
    "job_id": None,  # set per test after creating a job
    "workspace_id": 1,
    "log_level": "INFO",
    "step_name": "template_loaded",
    "message": "Prompt template loaded successfully",
    "duration_ms": 42,
}


class TestCreateLog:
    """Test ConversionRepository.create_log"""

    def test_create_log_persists_correct_fields(self, repo):
        """create_log persists all fields and returns a ConversionLog with an id."""
        job = repo.create_job(**JOB_DEFAULTS)
        log_data = {**LOG_ENTRY_DEFAULTS, "job_id": job.id}

        log_entry = repo.create_log(log_data)

        assert log_entry.id is not None
        assert log_entry.job_id == job.id
        assert log_entry.workspace_id == 1
        assert log_entry.log_level == "INFO"
        assert log_entry.step_name == "template_loaded"
        assert log_entry.message == "Prompt template loaded successfully"
        assert log_entry.duration_ms == 42
        assert log_entry.timestamp is not None

    def test_create_log_without_duration(self, repo):
        """create_log works when duration_ms is None."""
        job = repo.create_job(**JOB_DEFAULTS)
        log_data = {**LOG_ENTRY_DEFAULTS, "job_id": job.id, "duration_ms": None}

        log_entry = repo.create_log(log_data)

        assert log_entry.id is not None
        assert log_entry.duration_ms is None


class TestListLogsByJob:
    """Test ConversionRepository.list_logs_by_job"""

    def test_returns_logs_for_given_job_and_workspace(self, repo):
        """list_logs_by_job returns only logs matching job_id AND workspace_id."""
        job1 = repo.create_job(**JOB_DEFAULTS)
        job2 = repo.create_job(**{**JOB_DEFAULTS, "asset_name": "other"})

        repo.create_log({**LOG_ENTRY_DEFAULTS, "job_id": job1.id, "step_name": "template_loaded"})
        repo.create_log({**LOG_ENTRY_DEFAULTS, "job_id": job1.id, "step_name": "bedrock_invocation_started"})
        repo.create_log({**LOG_ENTRY_DEFAULTS, "job_id": job2.id, "step_name": "template_loaded"})

        logs = repo.list_logs_by_job(job1.id, workspace_id=1)

        assert len(logs) == 2
        assert all(log.job_id == job1.id for log in logs)

    def test_returns_logs_ordered_by_timestamp_ascending(self, repo):
        """Logs are returned in chronological order (oldest first)."""
        from datetime import timedelta
        job = repo.create_job(**JOB_DEFAULTS)
        now = datetime.utcnow()

        repo.create_log({**LOG_ENTRY_DEFAULTS, "job_id": job.id, "step_name": "conversion_completed", "timestamp": now + timedelta(seconds=2)})
        repo.create_log({**LOG_ENTRY_DEFAULTS, "job_id": job.id, "step_name": "template_loaded", "timestamp": now})
        repo.create_log({**LOG_ENTRY_DEFAULTS, "job_id": job.id, "step_name": "bedrock_invocation_started", "timestamp": now + timedelta(seconds=1)})

        logs = repo.list_logs_by_job(job.id, workspace_id=1)

        assert len(logs) == 3
        assert logs[0].step_name == "template_loaded"
        assert logs[1].step_name == "bedrock_invocation_started"
        assert logs[2].step_name == "conversion_completed"

    def test_workspace_isolation(self, repo):
        """Logs in workspace 1 are not visible to workspace 2."""
        job = repo.create_job(**JOB_DEFAULTS)
        repo.create_log({**LOG_ENTRY_DEFAULTS, "job_id": job.id})

        logs = repo.list_logs_by_job(job.id, workspace_id=2)
        assert len(logs) == 0

    def test_empty_result_for_job_with_no_logs(self, repo):
        """A job with no logs returns an empty list."""
        job = repo.create_job(**JOB_DEFAULTS)
        logs = repo.list_logs_by_job(job.id, workspace_id=1)
        assert logs == []


# ── list_batches tests ────────────────────────────────────────────────

class TestListBatches:
    """Test ConversionRepository.list_batches"""

    def _seed_batches(self, repo, count=3, **overrides):
        """Helper to create multiple batches."""
        batches = []
        for _ in range(count):
            data = {**BATCH_DEFAULTS, **overrides}
            batches.append(repo.create_batch(**data))
        return batches

    def test_returns_batches_and_total_count(self, repo):
        """list_batches returns (list, total_count) tuple."""
        self._seed_batches(repo, count=3)
        batches, total = repo.list_batches(workspace_id=1)

        assert total == 3
        assert len(batches) == 3

    def test_pagination(self, repo):
        """Pagination returns the correct slice and total."""
        self._seed_batches(repo, count=5)

        page1, total = repo.list_batches(workspace_id=1, page=1, page_size=2)
        page2, _ = repo.list_batches(workspace_id=1, page=2, page_size=2)
        page3, _ = repo.list_batches(workspace_id=1, page=3, page_size=2)

        assert total == 5
        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1

    def test_ordered_by_created_at_descending(self, repo):
        """Batches are returned newest first."""
        b1 = repo.create_batch(**BATCH_DEFAULTS)
        b2 = repo.create_batch(**BATCH_DEFAULTS)
        b3 = repo.create_batch(**BATCH_DEFAULTS)

        batches, _ = repo.list_batches(workspace_id=1)

        assert batches[0].id == b3.id
        assert batches[-1].id == b1.id

    def test_workspace_isolation(self, repo):
        """Batches in workspace 1 are not visible to workspace 2."""
        self._seed_batches(repo, count=3, workspace_id=1)
        self._seed_batches(repo, count=2, workspace_id=2)

        ws1_batches, ws1_total = repo.list_batches(workspace_id=1)
        ws2_batches, ws2_total = repo.list_batches(workspace_id=2)

        assert ws1_total == 3
        assert ws2_total == 2

    def test_empty_workspace(self, repo):
        """Empty workspace returns empty list and zero total."""
        batches, total = repo.list_batches(workspace_id=99)
        assert batches == []
        assert total == 0


# ── delete_batch tests ────────────────────────────────────────────────

class TestDeleteBatch:
    """Test ConversionRepository.delete_batch"""

    def test_delete_existing_batch(self, repo):
        """Deleting an existing batch returns True and removes it."""
        batch = repo.create_batch(**BATCH_DEFAULTS)
        result = repo.delete_batch(batch.id, workspace_id=1)

        assert result is True
        assert repo.get_batch(batch.id, workspace_id=1) is None

    def test_delete_nonexistent_batch_returns_false(self, repo):
        """Deleting a non-existent batch returns False."""
        assert repo.delete_batch(9999, workspace_id=1) is False

    def test_delete_wrong_workspace_returns_false(self, repo):
        """Workspace isolation: cannot delete a batch from another workspace."""
        batch = repo.create_batch(**BATCH_DEFAULTS)
        assert repo.delete_batch(batch.id, workspace_id=2) is False
        # Batch still exists in workspace 1
        assert repo.get_batch(batch.id, workspace_id=1) is not None


# ── bulk_delete_jobs tests ────────────────────────────────────────────

class TestBulkDeleteJobs:
    """Test ConversionRepository.bulk_delete_jobs"""

    def test_deletes_specified_jobs(self, repo):
        """bulk_delete_jobs removes exactly the specified jobs."""
        j1 = repo.create_job(**{**JOB_DEFAULTS, "asset_name": "t1"})
        j2 = repo.create_job(**{**JOB_DEFAULTS, "asset_name": "t2"})
        j3 = repo.create_job(**{**JOB_DEFAULTS, "asset_name": "t3"})

        deleted = repo.bulk_delete_jobs([j1.id, j2.id], workspace_id=1)

        assert deleted == 2
        assert repo.get_job(j1.id, workspace_id=1) is None
        assert repo.get_job(j2.id, workspace_id=1) is None
        assert repo.get_job(j3.id, workspace_id=1) is not None

    def test_returns_zero_for_empty_list(self, repo):
        """Passing an empty list returns 0 and deletes nothing."""
        repo.create_job(**JOB_DEFAULTS)
        deleted = repo.bulk_delete_jobs([], workspace_id=1)

        assert deleted == 0
        _, total = repo.list_jobs(workspace_id=1)
        assert total == 1

    def test_workspace_isolation(self, repo):
        """Jobs in other workspaces are not affected by bulk delete."""
        j_ws1 = repo.create_job(**{**JOB_DEFAULTS, "workspace_id": 1, "asset_name": "ws1_job"})
        j_ws2 = repo.create_job(**{**JOB_DEFAULTS, "workspace_id": 2, "asset_name": "ws2_job"})

        # Try to delete both IDs but scoped to workspace 1
        deleted = repo.bulk_delete_jobs([j_ws1.id, j_ws2.id], workspace_id=1)

        assert deleted == 1
        # ws2 job still exists
        assert repo.get_job(j_ws2.id, workspace_id=2) is not None

    def test_nonexistent_ids_ignored(self, repo):
        """Non-existent IDs in the list are silently ignored."""
        j1 = repo.create_job(**JOB_DEFAULTS)
        deleted = repo.bulk_delete_jobs([j1.id, 9999, 8888], workspace_id=1)

        assert deleted == 1

    def test_bulk_delete_sample_payload(self, repo):
        """Sample payload: bulk delete with job_ids [1, 2, 3]."""
        j1 = repo.create_job(**{**JOB_DEFAULTS, "asset_name": "a1"})
        j2 = repo.create_job(**{**JOB_DEFAULTS, "asset_name": "a2"})
        j3 = repo.create_job(**{**JOB_DEFAULTS, "asset_name": "a3"})

        deleted = repo.bulk_delete_jobs([j1.id, j2.id, j3.id], workspace_id=1)

        assert deleted == 3
        jobs, total = repo.list_jobs(workspace_id=1)
        assert total == 0
