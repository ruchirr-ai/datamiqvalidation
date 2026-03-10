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
