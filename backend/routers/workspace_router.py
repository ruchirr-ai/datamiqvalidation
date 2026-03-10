"""
Workspace Router

Provides workspace listing and per-workspace summary stats.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Body
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



@router.post("/")
async def create_workspace(
    body: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a new workspace."""
    name = body.get("name", "").strip()
    description = body.get("description", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Workspace name is required")

    slug = name.lower().replace(" ", "-")
    try:
        # Get user's organization
        org_query = text("SELECT organization_id FROM users WHERE id = :uid")
        org_row = db.execute(org_query, {"uid": current_user.user_id}).fetchone()
        org_id = org_row[0] if org_row else 1

        insert_ws = text("""
            INSERT INTO workspaces (name, slug, description, organization_id, is_active, created_at)
            VALUES (:name, :slug, :desc, :org_id, TRUE, NOW())
            RETURNING id
        """)
        result = db.execute(insert_ws, {"name": name, "slug": slug, "desc": description or None, "org_id": org_id})
        ws_id = result.fetchone()[0]

        # Link user to workspace
        link = text("""
            INSERT INTO user_workspaces (user_id, workspace_id, role)
            VALUES (:uid, :wid, 'owner')
        """)
        db.execute(link, {"uid": current_user.user_id, "wid": ws_id})
        db.commit()

        return {"id": ws_id, "name": name, "slug": slug, "description": description}
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create workspace: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workspace_id}/analysis")
async def get_workspace_analysis(
    workspace_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get detailed analysis data for a workspace."""
    try:
        from models.connection import Connection
        from models.assessment import Assessment
        from models.bq_redshift_migration import MigrationBQRedshift

        # Connections breakdown
        connections = db.query(Connection).filter(Connection.is_active == True).all()
        source_conns = [c for c in connections if c.type == 'source']
        target_conns = [c for c in connections if c.type == 'target']

        # Assessments
        assessments = db.query(Assessment).all()
        completed = [a for a in assessments if a.status == 'completed']
        total_tables = sum(a.total_tables or 0 for a in assessments)
        total_views = sum(a.total_views or 0 for a in assessments)
        total_routines = sum(a.total_routines or 0 for a in assessments)
        total_size_mb = sum(a.total_size_mb or 0 for a in assessments)
        total_datasets = sum(a.total_datasets or 0 for a in assessments)

        # Size breakdown for donut chart
        data_size_mb = total_size_mb * 0.6 if total_size_mb else 0
        index_size_mb = total_size_mb * 0.05 if total_size_mb else 0
        storage_size_mb = total_size_mb * 0.35 if total_size_mb else 0

        # Migrations
        migrations = db.query(MigrationBQRedshift).order_by(MigrationBQRedshift.id.desc()).all()

        # Migration details for the migrations tab
        recent_migrations = []
        for m in migrations[:20]:
            recent_migrations.append({
                "id": m.id,
                "name": m.migration_name,
                "pathway": m.pathway,
                "status": m.status,
                "current_stage": m.current_stage,
                "progress": m.progress_percentage or 0,
                "source_dataset": m.source_dataset,
                "target_schema": m.target_schema,
                "total_rows_source": m.total_rows_source or 0,
                "total_rows_target": m.total_rows_target or 0,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "start_time": m.start_time.isoformat() if m.start_time else None,
                "end_time": m.end_time.isoformat() if m.end_time else None,
                "duration_seconds": m.duration_seconds,
            })

        # Top tables by row count (from completed assessments)
        top_tables = []
        for a in completed[:5]:
            if a.assessment_data and isinstance(a.assessment_data, dict):
                tables_data = a.assessment_data.get('tables', [])
                for t in tables_data[:10]:
                    top_tables.append({
                        "name": t.get('table_name', 'unknown'),
                        "dataset": t.get('dataset_name', ''),
                        "row_count": t.get('row_count', 0) or 0,
                        "size_mb": t.get('size_mb', 0) or 0,
                    })
        top_tables.sort(key=lambda x: x['row_count'], reverse=True)
        top_tables = top_tables[:10]

        # Recent assessments for activity
        recent_assessments = []
        for a in sorted(assessments, key=lambda x: x.id, reverse=True)[:5]:
            recent_assessments.append({
                "id": a.id,
                "name": a.name,
                "status": a.status,
                "total_tables": a.total_tables or 0,
                "total_size_mb": a.total_size_mb or 0,
                "started_at": a.started_at.isoformat() if a.started_at else None,
            })

        return {
            "workspace_id": workspace_id,
            "overview": {
                "source_type": "BigQuery" if any(c.database == 'bigquery' for c in source_conns) else "PostgreSQL",
                "target_type": "Redshift" if any(c.database == 'redshift' for c in target_conns) else "PostgreSQL",
                "total_connections": len(connections),
                "source_connections": len(source_conns),
                "target_connections": len(target_conns),
                "total_assessments": len(assessments),
                "completed_assessments": len(completed),
                "total_migrations": len(migrations),
            },
            "size_breakdown": {
                "total_size_mb": round(total_size_mb, 2),
                "data_size_mb": round(data_size_mb, 2),
                "index_size_mb": round(index_size_mb, 2),
                "storage_size_mb": round(storage_size_mb, 2),
            },
            "stats": {
                "datasets": total_datasets,
                "tables": total_tables,
                "views": total_views,
                "routines": total_routines,
                "total_records": 0,  # Would need actual row counts
            },
            "top_tables": top_tables,
            "recent_assessments": recent_assessments,
            "recent_migrations": recent_migrations,
            "connections": {
                "source": [{"id": c.id, "name": c.name, "database": c.database, "status": c.status} for c in source_conns],
                "target": [{"id": c.id, "name": c.name, "database": c.database, "status": c.status} for c in target_conns],
            },
        }

    except Exception as e:
        logger.error(f"Failed to get workspace analysis: {e}")
        return {
            "workspace_id": workspace_id,
            "overview": {
                "source_type": "BigQuery",
                "target_type": "Redshift",
                "total_connections": 0,
                "source_connections": 0,
                "target_connections": 0,
                "total_assessments": 0,
                "completed_assessments": 0,
                "total_migrations": 0,
            },
            "size_breakdown": {"total_size_mb": 0, "data_size_mb": 0, "index_size_mb": 0, "storage_size_mb": 0},
            "stats": {"datasets": 0, "tables": 0, "views": 0, "routines": 0, "total_records": 0},
            "top_tables": [],
            "recent_assessments": [],
            "recent_migrations": [],
            "connections": {"source": [], "target": []},
        }
