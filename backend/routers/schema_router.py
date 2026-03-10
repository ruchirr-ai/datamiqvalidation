"""
Schema Analysis Router

Provides detailed schema analysis data from completed assessments.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/schema", tags=["schema"])


@router.get("/analysis/{assessment_id}")
async def get_schema_analysis(
    assessment_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get full schema analysis for a completed assessment."""
    try:
        from models.assessment import (
            Assessment, AssessmentDataset, AssessmentTable,
            AssessmentColumn, AssessmentView, AssessmentRoutine
        )

        assessment = db.query(Assessment).filter(Assessment.id == assessment_id).first()
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        # Datasets
        datasets_db = db.query(AssessmentDataset).filter(
            AssessmentDataset.assessment_id == assessment_id
        ).order_by(AssessmentDataset.dataset_name).all()

        # Tables with columns
        tables_db = db.query(AssessmentTable).filter(
            AssessmentTable.assessment_id == assessment_id
        ).order_by(AssessmentTable.dataset_name, AssessmentTable.table_name).all()

        columns_db = db.query(AssessmentColumn).filter(
            AssessmentColumn.assessment_id == assessment_id
        ).order_by(AssessmentColumn.ordinal_position).all()

        # Views
        views_db = db.query(AssessmentView).filter(
            AssessmentView.assessment_id == assessment_id
        ).all()

        # Routines
        routines_db = db.query(AssessmentRoutine).filter(
            AssessmentRoutine.assessment_id == assessment_id
        ).all()

        # Build columns lookup by table_id
        cols_by_table: Dict[int, List[Dict]] = {}
        for c in columns_db:
            cols_by_table.setdefault(c.table_id, []).append({
                "name": c.column_name,
                "data_type": c.data_type,
                "is_nullable": c.is_nullable,
                "ordinal_position": c.ordinal_position or 0,
                "is_partitioning": c.is_partitioning_column or False,
                "clustering_position": c.clustering_ordinal_position,
                "max_length": c.max_length,
                "policy_tags": c.policy_tags or [],
            })

        # Build tables
        tables = []
        for t in tables_db:
            table_cols = cols_by_table.get(t.id, [])
            tables.append({
                "id": t.id,
                "dataset": t.dataset_name,
                "name": t.table_name,
                "full_name": f"{t.dataset_name}.{t.table_name}",
                "type": t.table_type or "BASE TABLE",
                "row_count": t.row_count or 0,
                "size_mb": float(t.size_mb or 0),
                "created_at": t.creation_time.isoformat() if t.creation_time else None,
                "partitioning_columns": t.partitioning_columns or [],
                "clustering_columns": t.clustering_columns or [],
                "has_column_security": t.has_column_security or False,
                "has_row_security": t.has_row_security or False,
                "is_sharded": t.is_sharded or False,
                "shard_group": t.shard_group,
                "column_count": len(table_cols),
                "columns": table_cols,
            })

        # Build datasets with table references
        datasets = []
        for d in datasets_db:
            ds_tables = [t for t in tables if t["dataset"] == d.dataset_name]
            datasets.append({
                "name": d.dataset_name,
                "table_count": d.table_count or len(ds_tables),
                "total_size_mb": float(d.total_size_mb or 0),
                "location": d.location,
                "created_at": d.creation_time.isoformat() if d.creation_time else None,
                "tables": [t["name"] for t in ds_tables],
            })

        # Views
        views = []
        for v in views_db:
            views.append({
                "name": v.view_name,
                "dataset": v.dataset_name if hasattr(v, 'dataset_name') else None,
                "type": v.view_type or "VIEW",
                "definition": v.view_definition,
                "is_materialized": v.is_materialized if hasattr(v, 'is_materialized') else (v.view_type == 'MATERIALIZED_VIEW' if hasattr(v, 'view_type') else False),
            })

        # Routines
        routines = []
        for r in routines_db:
            routines.append({
                "name": r.routine_name,
                "type": r.routine_type or "FUNCTION",
                "language": r.language if hasattr(r, 'language') else "SQL",
                "definition": r.definition if hasattr(r, 'definition') else None,
            })

        # Data type distribution
        type_counts: Dict[str, int] = {}
        for c in columns_db:
            base_type = (c.data_type or "UNKNOWN").split("(")[0].split("<")[0].upper().strip()
            type_counts[base_type] = type_counts.get(base_type, 0) + 1

        type_distribution = sorted(
            [{"type": k, "count": v} for k, v in type_counts.items()],
            key=lambda x: x["count"], reverse=True
        )

        # Summary stats
        total_columns = len(columns_db)
        total_rows = sum(t["row_count"] for t in tables)
        total_size = sum(t["size_mb"] for t in tables)
        partitioned_tables = sum(1 for t in tables if t["partitioning_columns"])
        clustered_tables = sum(1 for t in tables if t["clustering_columns"])
        secured_tables = sum(1 for t in tables if t["has_column_security"] or t["has_row_security"])
        sharded_tables = sum(1 for t in tables if t["is_sharded"])
        nullable_cols = sum(1 for c in columns_db if c.is_nullable)

        return {
            "assessment_id": assessment_id,
            "assessment_name": assessment.name,
            "status": assessment.status,
            "summary": {
                "datasets": len(datasets),
                "tables": len(tables),
                "columns": total_columns,
                "views": len(views),
                "routines": len(routines),
                "total_rows": total_rows,
                "total_size_mb": round(total_size, 2),
                "partitioned_tables": partitioned_tables,
                "clustered_tables": clustered_tables,
                "secured_tables": secured_tables,
                "sharded_tables": sharded_tables,
                "nullable_columns": nullable_cols,
                "non_nullable_columns": total_columns - nullable_cols,
            },
            "datasets": datasets,
            "tables": tables,
            "views": views,
            "routines": routines,
            "type_distribution": type_distribution,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get schema analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))
