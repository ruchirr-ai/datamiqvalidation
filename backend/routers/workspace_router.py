"""
Workspace Router

Provides workspace listing and per-workspace summary stats.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from shared.middleware.auth_middleware import CurrentUser, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.get("/")
async def list_workspaces(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List all workspaces the current user has access to, with summary stats."""
    try:
        # Get user workspaces
        query = text("""
            SELECT w.id, w.name, w.slug, w.description, w.organization_id,
                   uw.role, w.created_at, w.is_active
            FROM workspaces w
            JOIN user_workspaces uw ON w.id = uw.workspace_id
            WHERE uw.user_id = :user_id AND w.is_active = TRUE
            ORDER BY w.name
        """)
        result = db.execute(query, {"user_id": current_user.user_id})
        rows = result.fetchall()

        workspaces = []
        for row in rows:
            ws = {
                "id": row[0],
                "name": row[1],
                "slug": row[2],
                "description": row[3],
                "organization_id": row[4],
                "role": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
                "is_active": row[7],
                "stats": _get_workspace_stats(db),
            }
            workspaces.append(ws)

        # If no workspaces found, return a default one
        if not workspaces:
            workspaces = [
                {
                    "id": 1,
                    "name": "Default Workspace",
                    "slug": "default",
                    "description": "Default workspace for all resources",
                    "organization_id": 1,
                    "role": "owner",
                    "created_at": datetime.utcnow().isoformat(),
                    "is_active": True,
                    "stats": _get_workspace_stats(db),
                }
            ]

        return workspaces

    except Exception as e:
        logger.error(f"Failed to list workspaces: {e}")
        # Return default workspace on error
        return [
            {
                "id": 1,
                "name": "Default Workspace",
                "slug": "default",
                "description": "Default workspace for all resources",
                "organization_id": 1,
                "role": "owner",
                "created_at": datetime.utcnow().isoformat(),
                "is_active": True,
                "stats": _get_workspace_stats(db),
            }
        ]


def _get_workspace_stats(db: Session) -> Dict[str, Any]:
    """Get summary stats for a workspace."""
    stats: Dict[str, Any] = {
        "connections": 0,
        "assessments": 0,
        "migrations": 0,
        "conversions": 0,
        "members": 0,
    }
    try:
        from models.connection import Connection
        from models.assessment import Assessment
        from models.bq_redshift_migration import MigrationBQRedshift

        stats["connections"] = db.query(Connection).filter(Connection.is_active == True).count()
        stats["assessments"] = db.query(Assessment).count()
        stats["migrations"] = db.query(MigrationBQRedshift).count()

        try:
            from models.conversion_job_db import ConversionJob
            stats["conversions"] = db.query(ConversionJob).count()
        except Exception:
            pass

        try:
            result = db.execute(text("SELECT COUNT(*) FROM users WHERE is_active = TRUE"))
            stats["members"] = result.scalar() or 0
        except Exception:
            stats["members"] = 1
    except Exception as e:
        logger.error(f"Failed to get workspace stats: {e}")

    return stats
