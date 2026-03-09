"""
Dashboard Router

Provides aggregated summary data for the dashboard page.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models.connection import Connection
from models.assessment import Assessment
from models.bq_redshift_migration import MigrationBQRedshift
from models.copy_history import CopyHistory
from models.task_history import TaskHistory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class DashboardSummary(BaseModel):
    # Connections
    total_connections: int = 0
    source_connections: int = 0
    target_connections: int = 0
    connected_count: int = 0

    # Assessments
    total_assessments: int = 0
    completed_assessments: int = 0
    running_assessments: int = 0
    failed_assessments: int = 0
    total_tables_discovered: int = 0
    total_views_discovered: int = 0
    total_routines_discovered: int = 0
    total_size_mb: float = 0

    # Migrations
    total_migrations: int = 0
    completed_migrations: int = 0
    running_migrations: int = 0
    failed_migrations: int = 0
    scheduled_migrations: int = 0

    # Conversions
    total_batches: int = 0
    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0

    # Copy History
    total_copies: int = 0
    completed_copies: int = 0
    total_rows_copied: int = 0
    total_bytes_copied: int = 0

    # Recent activity
    recent_assessments: list = []
    recent_migrations: list = []
    recent_copies: list = []


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """Get aggregated dashboard summary data."""
    try:
        summary = DashboardSummary()

        # --- Connections ---
        conns = db.query(Connection).filter(Connection.is_active == True).all()
        summary.total_connections = len(conns)
        summary.source_connections = sum(1 for c in conns if c.type == 'source')
        summary.target_connections = sum(1 for c in conns if c.type == 'target')
        summary.connected_count = sum(1 for c in conns if c.status == 'connected')

        # --- Assessments ---
        assessments = db.query(Assessment).all()
        summary.total_assessments = len(assessments)
        summary.completed_assessments = sum(1 for a in assessments if a.status == 'completed')
        summary.running_assessments = sum(1 for a in assessments if a.status == 'running')
        summary.failed_assessments = sum(1 for a in assessments if a.status == 'failed')
        summary.total_tables_discovered = sum(a.total_tables or 0 for a in assessments)
        summary.total_views_discovered = sum(a.total_views or 0 for a in assessments)
        summary.total_routines_discovered = sum(a.total_routines or 0 for a in assessments)
        summary.total_size_mb = sum(a.total_size_mb or 0 for a in assessments)

        # Recent assessments (last 5)
        recent_a = db.query(Assessment).order_by(Assessment.id.desc()).limit(5).all()
        summary.recent_assessments = [
            {
                "id": a.id,
                "name": a.name,
                "status": a.status,
                "total_tables": a.total_tables,
                "total_size_mb": a.total_size_mb,
                "started_at": a.started_at.isoformat() if a.started_at else None,
            }
            for a in recent_a
        ]

        # --- Migrations ---
        migrations = db.query(MigrationBQRedshift).all()
        summary.total_migrations = len(migrations)
        summary.completed_migrations = sum(1 for m in migrations if m.status == 'completed')
        summary.running_migrations = sum(1 for m in migrations if m.status == 'running')
        summary.failed_migrations = sum(1 for m in migrations if m.status == 'failed')
        summary.scheduled_migrations = sum(1 for m in migrations if m.status == 'scheduled')

        # Recent migrations (last 5)
        recent_m = db.query(MigrationBQRedshift).order_by(MigrationBQRedshift.id.desc()).limit(5).all()
        summary.recent_migrations = [
            {
                "id": m.id,
                "name": m.migration_name,
                "status": m.status,
                "pathway": m.pathway,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in recent_m
        ]

        # --- Conversions ---
        try:
            from models.conversion_job_db import ConversionJob, ConversionBatch
            batches = db.query(ConversionBatch).all()
            summary.total_batches = len(batches)
            jobs = db.query(ConversionJob).all()
            summary.total_jobs = len(jobs)
            summary.completed_jobs = sum(1 for j in jobs if j.status == 'completed')
            summary.failed_jobs = sum(1 for j in jobs if j.status == 'failed')
        except Exception:
            pass  # Conversion tables may not exist

        # --- Copy History ---
        try:
            copies = db.query(CopyHistory).all()
            summary.total_copies = len(copies)
            summary.completed_copies = sum(1 for c in copies if c.status == 'completed')
            summary.total_rows_copied = sum(c.rows_loaded or 0 for c in copies)
            summary.total_bytes_copied = sum(c.bytes_loaded or 0 for c in copies)

            recent_c = db.query(CopyHistory).order_by(CopyHistory.id.desc()).limit(5).all()
            summary.recent_copies = [
                {
                    "id": c.id,
                    "table_name": c.table_name,
                    "status": c.status,
                    "rows_loaded": c.rows_loaded,
                    "started_at": c.started_at.isoformat() if c.started_at else None,
                }
                for c in recent_c
            ]
        except Exception:
            pass

        return summary

    except Exception as e:
        logger.error(f"Dashboard summary error: {e}")
        return DashboardSummary()
