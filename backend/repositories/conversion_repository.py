"""
Conversion Repository

Database operations for ConversionJob and ConversionBatch models.
All queries include workspace_id filter for tenant isolation.
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Tuple

from models.conversion_job_db import ConversionJob
from models.conversion_batch import ConversionBatch
from models.conversion_log import ConversionLog

logger = logging.getLogger(__name__)


class ConversionRepository:
    """Repository for conversion job and batch CRUD operations."""

    def __init__(self, db: Session):
        self.db = db

    # ── ConversionJob operations ──────────────────────────────────────

    def create_job(self, **kwargs) -> ConversionJob:
        """Create a new conversion job.

        Args:
            **kwargs: ConversionJob field values. Must include workspace_id.

        Returns:
            The persisted ConversionJob instance.
        """
        job = ConversionJob(**kwargs)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        logger.info(
            "Created conversion job id=%s workspace_id=%s asset_type=%s",
            job.id, job.workspace_id, job.asset_type,
        )
        return job

    def get_job(self, job_id: int, workspace_id: int) -> Optional[ConversionJob]:
        """Get a conversion job by ID scoped to a workspace."""
        return self.db.query(ConversionJob).filter(
            ConversionJob.id == job_id,
            ConversionJob.workspace_id == workspace_id,
        ).first()

    def list_jobs(
        self,
        workspace_id: int,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        asset_type: Optional[str] = None,
        source_dialect: Optional[str] = None,
        standalone_only: bool = False,
    ) -> Tuple[List[ConversionJob], int]:
        """List conversion jobs with pagination and optional filters.

        Args:
            workspace_id: Tenant isolation filter.
            page: 1-based page number.
            page_size: Number of results per page.
            status: Optional filter by job status.
            asset_type: Optional filter by asset type.
            source_dialect: Optional filter by source dialect.
            standalone_only: If True, only return jobs with no batch_id.

        Returns:
            Tuple of (list of jobs, total count matching filters).
        """
        query = self.db.query(ConversionJob).filter(
            ConversionJob.workspace_id == workspace_id,
        )

        if standalone_only:
            query = query.filter(ConversionJob.batch_id == None)
        if status:
            query = query.filter(ConversionJob.status == status)
        if asset_type:
            query = query.filter(ConversionJob.asset_type == asset_type)
        if source_dialect:
            query = query.filter(ConversionJob.source_dialect == source_dialect)

        total_count = query.count()

        jobs = (
            query
            .order_by(ConversionJob.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return jobs, total_count

    def update_job(self, job_id: int, workspace_id: int, **kwargs) -> Optional[ConversionJob]:
        """Update fields on a conversion job.

        Args:
            job_id: The job primary key.
            workspace_id: Tenant isolation filter.
            **kwargs: Fields to update.

        Returns:
            Updated ConversionJob or None if not found.
        """
        job = self.get_job(job_id, workspace_id)
        if not job:
            return None

        for key, value in kwargs.items():
            if hasattr(job, key):
                setattr(job, key, value)

        job.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(job)
        logger.info(
            "Updated conversion job id=%s workspace_id=%s fields=%s",
            job_id, workspace_id, list(kwargs.keys()),
        )
        return job

    def delete_job(self, job_id: int, workspace_id: int) -> bool:
        """Delete a conversion job scoped to a workspace.

        Args:
            job_id: The job primary key.
            workspace_id: Tenant isolation filter.

        Returns:
            True if deleted, False if not found.
        """
        job = self.get_job(job_id, workspace_id)
        if not job:
            return False

        self.db.delete(job)
        self.db.commit()
        logger.info(
            "Deleted conversion job id=%s workspace_id=%s",
            job_id, workspace_id,
        )
        return True

    # ── ConversionBatch operations ────────────────────────────────────

    def create_batch(self, **kwargs) -> ConversionBatch:
        """Create a new conversion batch.

        Args:
            **kwargs: ConversionBatch field values. Must include workspace_id.

        Returns:
            The persisted ConversionBatch instance.
        """
        batch = ConversionBatch(**kwargs)
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        logger.info(
            "Created conversion batch id=%s workspace_id=%s total_assets=%s",
            batch.id, batch.workspace_id, batch.total_assets,
        )
        return batch

    def get_batch(self, batch_id: int, workspace_id: int) -> Optional[ConversionBatch]:
        """Get a conversion batch by ID scoped to a workspace."""
        return self.db.query(ConversionBatch).filter(
            ConversionBatch.id == batch_id,
            ConversionBatch.workspace_id == workspace_id,
        ).first()

    def list_batch_jobs(self, batch_id: int, workspace_id: int, page: int = 1, page_size: int = 50) -> List[ConversionJob]:
        """List all conversion jobs belonging to a batch with pagination.

        Args:
            batch_id: The parent batch ID.
            workspace_id: Tenant isolation filter.
            page: Page number (1-indexed)
            page_size: Number of results per page

        Returns:
            List of ConversionJob instances in the batch.
        """
        offset = (page - 1) * page_size
        return (
            self.db.query(ConversionJob)
            .filter(
                ConversionJob.batch_id == batch_id,
                ConversionJob.workspace_id == workspace_id,
            )
            .order_by(ConversionJob.id.asc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

    def update_batch(self, batch_id: int, workspace_id: int, **kwargs) -> Optional[ConversionBatch]:
        """Update fields on a conversion batch.

        Args:
            batch_id: The batch primary key.
            workspace_id: Tenant isolation filter.
            **kwargs: Fields to update.

        Returns:
            Updated ConversionBatch or None if not found.
        """
        batch = self.get_batch(batch_id, workspace_id)
        if not batch:
            return None

        for key, value in kwargs.items():
            if hasattr(batch, key):
                setattr(batch, key, value)

        batch.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(batch)
        logger.info(
            "Updated conversion batch id=%s workspace_id=%s fields=%s",
            batch_id, workspace_id, list(kwargs.keys()),
        )
        return batch

    def get_completed_batch_jobs(self, batch_id: int, workspace_id: int) -> List[ConversionJob]:
        """Get all successfully completed jobs in a batch.

        Args:
            batch_id: The parent batch ID.
            workspace_id: Tenant isolation filter.

        Returns:
            List of completed ConversionJob instances.
        """
        return (
            self.db.query(ConversionJob)
            .filter(
                ConversionJob.batch_id == batch_id,
                ConversionJob.workspace_id == workspace_id,
                ConversionJob.status == 'completed',
            )
            .order_by(ConversionJob.id.asc())
            .all()
        )

    # ── ConversionLog operations ──────────────────────────────────────

    def create_log(self, log_data: dict) -> ConversionLog:
        """Create a new conversion log entry.

        Args:
            log_data: Dictionary with fields matching ConversionLog model.
                      Must include job_id, workspace_id, step_name, message.

        Returns:
            The persisted ConversionLog instance.
        """
        log_entry = ConversionLog(**log_data)
        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(log_entry)
        logger.debug(
            "Created conversion log id=%s job_id=%s step=%s",
            log_entry.id, log_entry.job_id, log_entry.step_name,
        )
        return log_entry

    def list_logs_by_job(self, job_id: int, workspace_id: int) -> List[ConversionLog]:
        """List all conversion logs for a job, ordered by timestamp ascending.

        Args:
            job_id: The parent conversion job ID.
            workspace_id: Tenant isolation filter.

        Returns:
            List of ConversionLog instances ordered by timestamp ascending.
        """
        return (
            self.db.query(ConversionLog)
            .filter(
                ConversionLog.job_id == job_id,
                ConversionLog.workspace_id == workspace_id,
            )
            .order_by(ConversionLog.timestamp.asc())
            .all()
        )

    # ── Additional batch / bulk operations ────────────────────────────

    def list_batches(
        self,
        workspace_id: int,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ConversionBatch], int]:
        """List conversion batches with pagination, ordered by created_at descending.

        Args:
            workspace_id: Tenant isolation filter.
            page: 1-based page number.
            page_size: Number of results per page.

        Returns:
            Tuple of (list of batches, total count).
        """
        query = self.db.query(ConversionBatch).filter(
            ConversionBatch.workspace_id == workspace_id,
        )

        total_count = query.count()

        batches = (
            query
            .order_by(ConversionBatch.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return batches, total_count

    def delete_batch(self, batch_id: int, workspace_id: int) -> bool:
        """Delete a conversion batch scoped to a workspace.

        The CASCADE foreign key on conversion_jobs.batch_id ensures
        associated jobs are also deleted.

        Args:
            batch_id: The batch primary key.
            workspace_id: Tenant isolation filter.

        Returns:
            True if deleted, False if not found.
        """
        batch = self.get_batch(batch_id, workspace_id)
        if not batch:
            return False

        self.db.delete(batch)
        self.db.commit()
        logger.info(
            "Deleted conversion batch id=%s workspace_id=%s",
            batch_id, workspace_id,
        )
        return True

    def bulk_delete_jobs(self, job_ids: List[int], workspace_id: int) -> int:
        """Delete multiple conversion jobs scoped to a workspace.

        Args:
            job_ids: List of job primary keys to delete.
            workspace_id: Tenant isolation filter.

        Returns:
            Count of deleted jobs.
        """
        if not job_ids:
            return 0

        deleted_count = (
            self.db.query(ConversionJob)
            .filter(
                ConversionJob.id.in_(job_ids),
                ConversionJob.workspace_id == workspace_id,
            )
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        logger.info(
            "Bulk deleted %s conversion jobs workspace_id=%s requested_ids=%s",
            deleted_count, workspace_id, job_ids,
        )
        return deleted_count
