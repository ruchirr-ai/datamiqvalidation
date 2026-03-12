"""
Validation Repository

Database operations for ValidationRun and ValidationTableResult models.
All queries include workspace_id filter for tenant isolation.
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session
from typing import List, Optional, Tuple

from models.validation_run import ValidationRun
from models.validation_table_result import ValidationTableResult

logger = logging.getLogger(__name__)


class ValidationRepository:
    """Repository for validation run and table result CRUD operations."""

    def __init__(self, db: Session):
        self.db = db

    # ── ValidationRun operations ──────────────────────────────────────

    def create_run(self, **kwargs) -> ValidationRun:
        """Create a new validation run.

        Args:
            **kwargs: ValidationRun field values. Must include workspace_id.

        Returns:
            The persisted ValidationRun instance.
        """
        run = ValidationRun(**kwargs)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        logger.info(
            "Created validation run id=%s workspace_id=%s migration_id=%s",
            run.id, run.workspace_id, run.migration_id,
        )
        return run

    def get_run(self, run_id: int, workspace_id: int) -> Optional[ValidationRun]:
        """Get a validation run by ID scoped to a workspace."""
        return self.db.query(ValidationRun).filter(
            ValidationRun.id == run_id,
            ValidationRun.workspace_id == workspace_id,
        ).first()

    def list_runs(
        self,
        workspace_id: int,
        migration_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[ValidationRun], int]:
        """List validation runs with pagination and optional filters.

        Args:
            workspace_id: Tenant isolation filter.
            migration_id: Optional filter by migration ID.
            status: Optional filter by run status.
            page: 1-based page number.
            page_size: Number of results per page (default 20, max 100).

        Returns:
            Tuple of (list of runs, total count matching filters).
        """
        page_size = min(page_size, 100)

        query = self.db.query(ValidationRun).filter(
            ValidationRun.workspace_id == workspace_id,
        )

        if migration_id is not None:
            query = query.filter(ValidationRun.migration_id == migration_id)
        if status is not None:
            query = query.filter(ValidationRun.status == status)

        total_count = query.count()

        runs = (
            query
            .order_by(ValidationRun.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return runs, total_count

    def update_run(self, run_id: int, workspace_id: int, **kwargs) -> Optional[ValidationRun]:
        """Update fields on a validation run.

        Args:
            run_id: The run primary key.
            workspace_id: Tenant isolation filter.
            **kwargs: Fields to update.

        Returns:
            Updated ValidationRun or None if not found.
        """
        run = self.get_run(run_id, workspace_id)
        if not run:
            return None

        for key, value in kwargs.items():
            if hasattr(run, key):
                setattr(run, key, value)

        run.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(run)
        logger.info(
            "Updated validation run id=%s workspace_id=%s fields=%s",
            run_id, workspace_id, list(kwargs.keys()),
        )
        return run

    def count_active_runs(self, workspace_id: int) -> int:
        """Count active (pending or running) validation runs for a workspace.

        Used to enforce rate limiting of concurrent validation runs.

        Args:
            workspace_id: Tenant isolation filter.

        Returns:
            Number of active validation runs for the workspace.
        """
        return self.db.query(ValidationRun).filter(
            ValidationRun.workspace_id == workspace_id,
            ValidationRun.status.in_(["pending", "running"]),
        ).count()

    def delete_run(self, run_id: int, workspace_id: int) -> bool:
        """Delete a validation run scoped to a workspace.

        Associated validation_table_results are cascade-deleted via FK CASCADE.

        Args:
            run_id: The run primary key.
            workspace_id: Tenant isolation filter.

        Returns:
            True if deleted, False if not found.
        """
        run = self.get_run(run_id, workspace_id)
        if not run:
            return False

        self.db.delete(run)
        self.db.commit()
        logger.info(
            "Deleted validation run id=%s workspace_id=%s",
            run_id, workspace_id,
        )
        return True
    def count_active_runs(self, workspace_id: int) -> int:
        """Count active (pending or running) validation runs for a workspace.

        Used to enforce rate limiting of concurrent validation runs.

        Args:
            workspace_id: Tenant isolation filter.

        Returns:
            Number of active validation runs for the workspace.
        """
        return self.db.query(ValidationRun).filter(
            ValidationRun.workspace_id == workspace_id,
            ValidationRun.status.in_(["pending", "running"]),
        ).count()



    # ── ValidationTableResult operations ──────────────────────────────

    def create_table_result(self, **kwargs) -> ValidationTableResult:
        """Create a new validation table result.

        Args:
            **kwargs: ValidationTableResult field values.
                      Must include run_id and workspace_id.

        Returns:
            The persisted ValidationTableResult instance.
        """
        result = ValidationTableResult(**kwargs)
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        logger.info(
            "Created validation table result id=%s run_id=%s table_name=%s",
            result.id, result.run_id, result.table_name,
        )
        return result

    def get_table_result(
        self, run_id: int, table_name: str, workspace_id: int
    ) -> Optional[ValidationTableResult]:
        """Get a validation table result by run_id and table_name scoped to a workspace."""
        return self.db.query(ValidationTableResult).filter(
            ValidationTableResult.run_id == run_id,
            ValidationTableResult.table_name == table_name,
            ValidationTableResult.workspace_id == workspace_id,
        ).first()

    def list_table_results(
        self, run_id: int, workspace_id: int
    ) -> List[ValidationTableResult]:
        """List all validation table results for a run scoped to a workspace.

        Args:
            run_id: The parent validation run ID.
            workspace_id: Tenant isolation filter.

        Returns:
            List of ValidationTableResult instances ordered by id ascending.
        """
        return (
            self.db.query(ValidationTableResult)
            .filter(
                ValidationTableResult.run_id == run_id,
                ValidationTableResult.workspace_id == workspace_id,
            )
            .order_by(ValidationTableResult.id.asc())
            .all()
        )

    def update_table_result(
        self, result_id: int, workspace_id: int, **kwargs
    ) -> Optional[ValidationTableResult]:
        """Update fields on a validation table result.

        Args:
            result_id: The table result primary key.
            workspace_id: Tenant isolation filter.
            **kwargs: Fields to update.

        Returns:
            Updated ValidationTableResult or None if not found.
        """
        result = self.db.query(ValidationTableResult).filter(
            ValidationTableResult.id == result_id,
            ValidationTableResult.workspace_id == workspace_id,
        ).first()
        if not result:
            return None

        for key, value in kwargs.items():
            if hasattr(result, key):
                setattr(result, key, value)

        result.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(result)
        logger.info(
            "Updated validation table result id=%s workspace_id=%s fields=%s",
            result_id, workspace_id, list(kwargs.keys()),
        )
        return result
