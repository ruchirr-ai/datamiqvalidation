"""
Copy History API Router

REST API endpoints for viewing Redshift COPY command history.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional
import logging

from database import get_db
from models.copy_history import CopyHistory
from shared.middleware.auth_middleware import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copy-history", tags=["Copy History"])


@router.get("/list")
async def list_copy_history(
    status_filter: Optional[str] = Query(None),
    migration_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all COPY command history with optional filters."""
    query = db.query(CopyHistory)

    if status_filter and status_filter != 'all':
        query = query.filter(CopyHistory.status == status_filter)

    if migration_id:
        query = query.filter(CopyHistory.migration_id == migration_id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (CopyHistory.migration_name.ilike(search_term)) |
            (CopyHistory.table_name.ilike(search_term)) |
            (CopyHistory.schema_name.ilike(search_term))
        )

    total = query.count()
    records = query.order_by(desc(CopyHistory.started_at)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "records": [r.to_dict() for r in records],
    }


@router.get("/{record_id}")
async def get_copy_record(
    record_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single COPY history record with full details."""
    record = db.query(CopyHistory).filter(CopyHistory.id == record_id).first()
    if not record:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Record not found")
    return record.to_dict()
