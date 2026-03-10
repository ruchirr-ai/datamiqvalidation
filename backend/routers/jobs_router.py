"""
Jobs Router

Provides a unified view of all assessment and migration jobs.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/")
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status: running, completed, failed, pending, queued"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """List all jobs (assessments + migrations) with unified format."""
    try:
        from models.assessment import Assessment
        from models.bq_redshift_migration import MigrationBQRedshift

        jobs: List[Dict[str, Any]] = []

        # Assessment jobs
        assessments = db.query(Assessment).order_by(Assessment.id.desc()).all()
        for a in assessments:
            job_status = a.status or 'pending'
            if status and job_status != status:
                continue
            jobs.append({
                "id": f"assessment-{a.id}",
                "resource_id": a.id,
                "type": "assessment",
                "name": a.name,
                "status": job_status,
                "started_at": a.started_at.isoformat() if a.started_at else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                "error_message": a.error_message,
                "details": {
                    "datasets": a.total_datasets or 0,
                    "tables": a.total_tables or 0,
                    "size_mb": float(a.total_size_mb or 0),
                },
                "progress": 100 if job_status == 'completed' else (50 if job_status == 'running' else 0),
            })

        # Migration jobs
        migrations = db.query(MigrationBQRedshift).order_by(MigrationBQRedshift.id.desc()).all()
        for m in migrations:
            job_status = m.status or 'pending'
            if status and job_status != status:
                continue
            jobs.append({
                "id": f"migration-{m.id}",
                "resource_id": m.id,
                "type": "migration",
                "name": m.migration_name,
                "status": job_status,
                "started_at": m.start_time.isoformat() if m.start_time else (m.created_at.isoformat() if m.created_at else None),
                "completed_at": m.end_time.isoformat() if m.end_time else None,
                "error_message": None,
                "details": {
                    "pathway": m.pathway,
                    "stage": m.current_stage,
                    "source": m.source_dataset,
                    "target": m.target_schema,
                    "rows_source": m.total_rows_source or 0,
                    "rows_target": m.total_rows_target or 0,
                },
                "progress": m.progress_percentage or 0,
            })

        # Sort by started_at descending (most recent first)
        jobs.sort(key=lambda j: j["started_at"] or "", reverse=True)

        # Summary counts
        summary = {
            "total": len(jobs),
            "running": sum(1 for j in jobs if j["status"] == "running"),
            "completed": sum(1 for j in jobs if j["status"] == "completed"),
            "failed": sum(1 for j in jobs if j["status"] == "failed"),
            "pending": sum(1 for j in jobs if j["status"] in ("pending", "queued", "ready")),
        }

        return {"jobs": jobs, "summary": summary}

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        return {"jobs": [], "summary": {"total": 0, "running": 0, "completed": 0, "failed": 0, "pending": 0}}
