"""
Conversion Router

Handles API endpoints for code conversion operations:
- Standalone (single-snippet) conversion
- Conversion job listing, retrieval, and deletion
- Batch conversion
- Bedrock model listing
- Prompt template listing
"""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from models.connection import Connection
from models.conversion_schemas import (
    BatchConversionRequest,
    BedrockModelResponse,
    BulkDeleteRequest,
    ConversionBatchResponse,
    ConversionJobResponse,
    ConversionLogResponse,
    DeployRequest,
    PaginatedJobsResponse,
    S3ExportRequest,
    StandaloneConversionRequest,
)
from services.conversion_cache import ConversionCache
from services.conversion_deploy_service import DeployService
from services.conversion_export_service import ExportService
from services.conversion_service import ConversionService
from services.audit_logger import AuditLogger
from shared.middleware.auth_middleware import CurrentUser, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversions", tags=["conversions"])


def get_workspace_id(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> int:
    """Extract workspace ID from X-Workspace-ID header or default to 1."""
    workspace_id = request.headers.get("X-Workspace-ID")
    if workspace_id:
        return int(workspace_id)
    return 1


def _build_service(db: Session) -> ConversionService:
    """Instantiate ConversionService with its dependencies."""
    cache = ConversionCache()
    return ConversionService(db=db, cache=cache)


# ---------------------------------------------------------------------------
# Standalone conversion
# ---------------------------------------------------------------------------


@router.post(
    "/standalone",
    response_model=ConversionJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_standalone_conversion(
    request: StandaloneConversionRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Create a standalone (single-snippet) code conversion."""
    try:
        service = _build_service(db)
        job = service.create_standalone_conversion(
            request=request,
            workspace_id=workspace_id,
            user_id=str(current_user.user_id),
        )
        return ConversionJobResponse.model_validate(job)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(
            "Standalone conversion failed",
            extra={"workspace_id": workspace_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the conversion",
        )


# ---------------------------------------------------------------------------
# Job listing / retrieval / deletion
# ---------------------------------------------------------------------------


@router.get("/jobs", response_model=PaginatedJobsResponse)
async def list_jobs(
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    asset_type: Optional[str] = None,
    source_dialect: Optional[str] = None,
    standalone_only: bool = False,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """List conversion jobs with pagination and optional filters."""
    try:
        service = _build_service(db)
        result = service.list_jobs(
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
            status=status_filter,
            asset_type=asset_type,
            source_dialect=source_dialect,
            standalone_only=standalone_only,
        )
        return PaginatedJobsResponse(
            jobs=[ConversionJobResponse.model_validate(j) for j in result["jobs"]],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to list conversion jobs",
            extra={"workspace_id": workspace_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing conversion jobs",
        )


@router.delete("/jobs/bulk")
async def bulk_delete_jobs(
    request: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Bulk delete conversion jobs by a list of IDs."""
    try:
        service = _build_service(db)
        deleted_count = service.bulk_delete_jobs(
            job_ids=request.job_ids,
            workspace_id=workspace_id,
        )
        return {"deleted_count": deleted_count}
    except Exception as exc:
        logger.error(
            "Bulk delete jobs failed",
            extra={"workspace_id": workspace_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting conversion jobs",
        )


@router.get("/jobs/{job_id}", response_model=ConversionJobResponse)
async def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Retrieve a single conversion job by ID."""
    service = _build_service(db)
    job = service.get_job(job_id=job_id, workspace_id=workspace_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversion job {job_id} not found",
        )
    return ConversionJobResponse.model_validate(job)


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Delete a conversion job by ID."""
    service = _build_service(db)
    deleted = service.delete_job(job_id=job_id, workspace_id=workspace_id, user_id=str(current_user.user_id))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversion job {job_id} not found",
        )
    return {"message": f"Conversion job {job_id} deleted successfully"}


@router.get("/jobs/{job_id}/logs", response_model=list[ConversionLogResponse])
async def get_job_logs(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Retrieve conversion logs for a job."""
    service = _build_service(db)
    job = service.get_job(job_id=job_id, workspace_id=workspace_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversion job {job_id} not found",
        )
    logs = service.get_job_logs(job_id=job_id, workspace_id=workspace_id)
    return [ConversionLogResponse.model_validate(log) for log in logs]


# ---------------------------------------------------------------------------
# Batch conversion
# ---------------------------------------------------------------------------


@router.post(
    "/batch",
    response_model=ConversionBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_batch_conversion(
    request: BatchConversionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Create a batch conversion for multiple assets."""
    try:
        service = _build_service(db)
        batch = service.create_batch_conversion(
            request=request,
            workspace_id=workspace_id,
            user_id=str(current_user.user_id),
        )
        background_tasks.add_task(
            service.run_batch_background,
            batch_id=batch.id,
            workspace_id=workspace_id,
        )
        return ConversionBatchResponse.model_validate(batch)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(
            "Batch conversion creation failed",
            extra={"workspace_id": workspace_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the batch conversion",
        )


@router.get("/batches")
async def list_batches(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """List all conversion batches for the current workspace."""
    try:
        service = _build_service(db)
        batches, total = service.list_batches(
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
        )
        return {
            "batches": [
                ConversionBatchResponse.model_validate(b)
                for b in batches
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    except Exception as exc:
        logger.error(
            "Failed to list conversion batches",
            extra={"workspace_id": workspace_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing conversion batches",
        )


@router.delete("/batches/{batch_id}")
async def delete_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Delete a batch and its associated jobs."""
    service = _build_service(db)
    deleted = service.delete_batch(batch_id=batch_id, workspace_id=workspace_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversion batch {batch_id} not found",
        )
    return {"message": f"Conversion batch {batch_id} deleted successfully"}


@router.get("/batch/{batch_id}", response_model=ConversionBatchResponse)
async def get_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Retrieve batch conversion status and progress."""
    service = _build_service(db)
    batch = service.get_batch(batch_id=batch_id, workspace_id=workspace_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversion batch {batch_id} not found",
        )
    return ConversionBatchResponse.model_validate(batch)


@router.get("/batch/{batch_id}/jobs", response_model=list[ConversionJobResponse])
async def list_batch_jobs(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """List all conversion jobs within a batch."""
    service = _build_service(db)
    batch = service.get_batch(batch_id=batch_id, workspace_id=workspace_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversion batch {batch_id} not found",
        )
    jobs = service.list_batch_jobs(batch_id=batch_id, workspace_id=workspace_id)
    return [ConversionJobResponse.model_validate(j) for j in jobs]


@router.post("/batch/{batch_id}/export/sql")
async def export_batch_sql(
    batch_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Export batch conversion results as a downloadable .sql file."""
    service = _build_service(db)
    batch = service.get_batch(batch_id=batch_id, workspace_id=workspace_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversion batch {batch_id} not found",
        )
    jobs = service.list_batch_jobs(batch_id=batch_id, workspace_id=workspace_id)
    export_service = ExportService()
    sql_bytes = export_service.generate_batch_sql(jobs)

    import io

    audit_logger = AuditLogger(db)
    audit_logger.log_data_modification(
        user_id=current_user.user_id,
        username=current_user.username,
        workspace_id=workspace_id,
        resource_type="conversion_batch",
        resource_id=batch_id,
        action="export",
    )

    return StreamingResponse(
        io.BytesIO(sql_bytes),
        media_type="application/sql",
        headers={
            "Content-Disposition": f"attachment; filename=batch_{batch_id}_export.sql"
        },
    )


@router.post("/batch/{batch_id}/export/s3")
async def export_batch_s3(
    batch_id: int,
    request: S3ExportRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Export batch conversion results to an S3 path."""
    service = _build_service(db)
    batch = service.get_batch(batch_id=batch_id, workspace_id=workspace_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversion batch {batch_id} not found",
        )
    jobs = service.list_batch_jobs(batch_id=batch_id, workspace_id=workspace_id)
    try:
        export_service = ExportService()
        export_service.export_to_s3(
            jobs=jobs,
            s3_path=request.s3_path,
            region=request.region,
        )
        audit_logger = AuditLogger(db)
        audit_logger.log_data_modification(
            user_id=current_user.user_id,
            username=current_user.username,
            workspace_id=workspace_id,
            resource_type="conversion_batch",
            resource_id=batch_id,
            action="export",
        )
        return {"message": f"Batch {batch_id} exported to {request.s3_path}"}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(
            "S3 export failed",
            extra={"batch_id": batch_id, "workspace_id": workspace_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while exporting to S3",
        )


@router.post("/batch/{batch_id}/deploy")
async def deploy_batch(
    batch_id: int,
    request: DeployRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Deploy converted assets from a batch to the target database."""
    service = _build_service(db)
    batch = service.get_batch(batch_id=batch_id, workspace_id=workspace_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversion batch {batch_id} not found",
        )

    target_connection = db.query(Connection).filter(
        Connection.id == request.target_connection_id,
    ).first()
    if not target_connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target connection {request.target_connection_id} not found",
        )

    jobs = service.list_batch_jobs(batch_id=batch_id, workspace_id=workspace_id)
    try:
        deploy_service = DeployService()
        result = deploy_service.deploy_batch(
            batch=batch,
            jobs=jobs,
            target_connection=target_connection,
        )
        audit_logger = AuditLogger(db)
        audit_logger.log_data_modification(
            user_id=current_user.user_id,
            username=current_user.username,
            workspace_id=workspace_id,
            resource_type="conversion_batch",
            resource_id=batch_id,
            action="deploy",
        )
        return {
            "success": result.success,
            "deployed_assets": result.deployed_assets,
            "failed_asset": result.failed_asset,
            "error_message": result.error_message,
        }
    except Exception as exc:
        logger.error(
            "Batch deployment failed",
            extra={"batch_id": batch_id, "workspace_id": workspace_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deploying the batch",
        )


# ---------------------------------------------------------------------------
# Bedrock models listing
# ---------------------------------------------------------------------------


@router.get("/models", response_model=list[BedrockModelResponse])
async def list_bedrock_models(
    region: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """List available Bedrock foundation models for a given AWS region."""
    try:
        service = _build_service(db)
        models = service.list_bedrock_models(region=region)
        return [
            BedrockModelResponse(
                model_id=m.model_id,
                model_name=m.model_name,
                provider=m.provider,
            )
            for m in models
        ]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to list Bedrock models",
            extra={"workspace_id": workspace_id, "region": region, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing Bedrock models",
        )


@router.get("/templates")
async def list_prompt_templates(
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """List available local prompt templates."""
    try:
        from services.bedrock_client import BedrockClient

        templates = BedrockClient.list_local_templates()
        return templates
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to list prompt templates",
            extra={"workspace_id": workspace_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing prompt templates",
        )
