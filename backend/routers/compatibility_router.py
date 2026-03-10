"""
Compatibility Check Router

API endpoints for running BigQuery → Redshift compatibility analysis.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import logging

from database import get_db
from services.compatibility_engine import CompatibilityEngine
from repositories.assessment_repository import AssessmentRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/compatibility", tags=["compatibility"])


class CompatibilityCheckRequest(BaseModel):
    assessment_id: int


@router.post("/check")
async def run_compatibility_check(
    request: CompatibilityCheckRequest,
    db: Session = Depends(get_db),
):
    """
    Run a full compatibility check on a completed assessment.
    Analyzes data types, feature gaps, SQL syntax, and optionally
    enhances with LLM insights.
    """
    try:
        # Validate assessment exists and is completed
        repo = AssessmentRepository(db)
        assessment = repo.get_by_id(request.assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        if assessment.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Assessment must be completed before running compatibility check. Current status: {assessment.status}",
            )

        engine = CompatibilityEngine()
        report = engine.run_compatibility_check(request.assessment_id, db)
        return report

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Compatibility check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/save")
async def save_compatibility_result(
    request: dict,
    db: Session = Depends(get_db),
):
    """Save a compatibility check result to the assessment's assessment_data JSONB field."""
    try:
        assessment_id = request.get("assessment_id")
        report_data = request.get("report")
        if not assessment_id or not report_data:
            raise HTTPException(status_code=400, detail="assessment_id and report are required")

        repo = AssessmentRepository(db)
        assessment = repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        # Store compatibility report in assessment_data JSONB
        existing_data = assessment.assessment_data or {}
        existing_data["compatibility_report"] = report_data
        assessment.assessment_data = existing_data
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(assessment, "assessment_data")
        db.commit()

        return {"success": True, "message": "Compatibility report saved"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save compatibility result: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/saved/{assessment_id}")
async def get_saved_compatibility(
    assessment_id: int,
    db: Session = Depends(get_db),
):
    """Get a previously saved compatibility report for an assessment."""
    try:
        repo = AssessmentRepository(db)
        assessment = repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        data = assessment.assessment_data or {}
        report = data.get("compatibility_report")
        if not report:
            return {"found": False, "report": None}

        return {"found": True, "report": report}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get saved compatibility: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
