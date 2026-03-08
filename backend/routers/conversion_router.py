"""
Conversion Router

API endpoints for SQL code conversion operations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from typing import Optional
import logging

from database import get_db
from models.conversion_job import (
    StandaloneConversionRequest,
    ConversionJobResponse,
    ConversionJobDetailResponse
)
from models.conversion_batch import (
    BatchConversionRequest,
    ConversionBatchResponse,
    ConversionBatchDetailResponse,
    ConversionJobListResponse
)
from models.conversion_log import ConversionLogListResponse
from services.conversion_service import ConversionService
from services.conversion_export_service import ConversionExportService
from services.conversion_deploy_service import ConversionDeployService
from shared.middleware.auth_middleware import get_current_user, get_workspace_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conversions", tags=["conversions"])


def get_conversion_service(db: Session = Depends(get_db)) -> ConversionService:
    """Dependency for ConversionService"""
    # TODO: Add Redis client
    return ConversionService(db=db, redis_client=None)


def get_export_service() -> ConversionExportService:
    """Dependency for ConversionExportService"""
    return ConversionExportService()


def get_deploy_service(db: Session = Depends(get_db)) -> ConversionDeployService:
    """Dependency for ConversionDeployService"""
    # TODO: Add KMS service
    return ConversionDeployService(db=db, kms_service=None)


@router.post("/standalone", response_model=ConversionJobResponse)
async def create_standalone_conversion(
    request: StandaloneConversionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
    conversion_service: ConversionService = Depends(get_conversion_service)
):
    """
    Create standalone SQL code conversion.
    
    Request Body:
    {
        "source_code": "SELECT * FROM table",
        "source_dialect": "bigquery",
        "target_dialect": "redshift",
        "asset_type": "view",
        "bedrock_model": "anthropic.claude-v2",
        "use_sqlglot": true
    }
    """
    try:
        result = await conversion_service.convert_standalone(
            workspace_id=workspace_id,
            user_id=current_user.user_id,
            source_code=request.source_code,
            source_dialect=request.source_dialect,
            target_dialect=request.target_dialect,
            asset_type=request.asset_type,
            bedrock_model=request.bedrock_model,
            use_sqlglot=request.use_sqlglot,
            prompt_template_path=request.prompt_template_path,
            asset_name=request.asset_name
        )
        
        return ConversionJobResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Conversion failed")


@router.post("/batch", response_model=ConversionBatchResponse)
async def create_batch_conversion(
    request: BatchConversionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
    conversion_service: ConversionService = Depends(get_conversion_service)
):
    """
    Create batch SQL code conversion.
    
    Request Body:
    {
        "source_connection_id": 1,
        "target_connection_id": 2,
        "asset_list": [
            {"asset_type": "view", "asset_name": "customer_view", "source_code": "..."}
        ],
        "bedrock_model": "anthropic.claude-v2",
        "use_sqlglot": true,
        "max_retries": 3
    }
    """
    try:
        result = await conversion_service.convert_batch(
            workspace_id=workspace_id,
            user_id=current_user.user_id,
            source_connection_id=request.source_connection_id,
            target_connection_id=request.target_connection_id,
            asset_list=request.asset_list,
            bedrock_model=request.bedrock_model,
            use_sqlglot=request.use_sqlglot,
            max_retries=request.max_retries
        )
        
        return ConversionBatchResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Batch conversion failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Batch conversion failed")


@router.get("/jobs/{job_id}", response_model=ConversionJobDetailResponse)
async def get_conversion_job(
    job_id: int,
    workspace_id: int = Depends(get_workspace_id),
    conversion_service: ConversionService = Depends(get_conversion_service)
):
    """Get conversion job details"""
    job = conversion_service.get_job(job_id, workspace_id)
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail="Conversion job not found or access denied"
        )
    
    return ConversionJobDetailResponse(**job)


@router.get("/batches/{batch_id}", response_model=ConversionBatchDetailResponse)
async def get_conversion_batch(
    batch_id: int,
    workspace_id: int = Depends(get_workspace_id),
    conversion_service: ConversionService = Depends(get_conversion_service)
):
    """Get conversion batch details with progress"""
    batch = conversion_service.get_batch(batch_id, workspace_id)
    
    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Conversion batch not found or access denied"
        )
    
    return ConversionBatchDetailResponse(**batch)


@router.get("/batches/{batch_id}/jobs")
async def get_batch_jobs(
    batch_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    workspace_id: int = Depends(get_workspace_id),
    db: Session = Depends(get_db)
):
    """Get paginated list of jobs for batch"""
    from models.conversion_job_db import ConversionJob as ConversionJobModel
    from models.conversion_job_db import ConversionBatch as ConversionBatchModel
    from sqlalchemy import and_
    
    # Verify batch belongs to workspace
    batch = db.query(ConversionBatchModel).filter(
        and_(
            ConversionBatchModel.id == batch_id,
            ConversionBatchModel.workspace_id == workspace_id
        )
    ).first()
    
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found or access denied")
    
    # Get jobs
    query = db.query(ConversionJobModel).filter(
        and_(
            ConversionJobModel.batch_id == batch_id,
            ConversionJobModel.workspace_id == workspace_id
        )
    )
    
    total = query.count()
    jobs = query.offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        'jobs': jobs,
        'total': total,
        'page': page,
        'page_size': page_size
    }


@router.get("/jobs/{job_id}/logs")
async def get_job_logs(
    job_id: int,
    workspace_id: int = Depends(get_workspace_id),
    db: Session = Depends(get_db)
):
    """Get conversion logs for debugging"""
    from models.conversion_job_db import ConversionLog as ConversionLogModel
    from sqlalchemy import and_
    
    logs = db.query(ConversionLogModel).filter(
        and_(
            ConversionLogModel.job_id == job_id,
            ConversionLogModel.workspace_id == workspace_id
        )
    ).order_by(ConversionLogModel.timestamp).all()
    
    return {
        'logs': logs,
        'total': len(logs)
    }


@router.post("/jobs/{job_id}/export")
async def export_conversion(
    job_id: int,
    export_format: str = Query("sql", pattern="^(sql|zip)$"),
    workspace_id: int = Depends(get_workspace_id),
    db: Session = Depends(get_db),
    export_service: ConversionExportService = Depends(get_export_service)
):
    """Export conversion job to file"""
    from models.conversion_job_db import ConversionJob as ConversionJobModel
    from sqlalchemy import and_
    
    # Get job
    job = db.query(ConversionJobModel).filter(
        and_(
            ConversionJobModel.id == job_id,
            ConversionJobModel.workspace_id == workspace_id
        )
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")
    
    # Export
    result = await export_service.export_single_job(job, workspace_id)
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error_message)
    
    # Return file content
    if result.file_content:
        return Response(
            content=result.file_content,
            media_type='application/octet-stream',
            headers={
                'Content-Disposition': f'attachment; filename="{result.file_path}"'
            }
        )
    
    return {'s3_url': result.s3_url}


@router.post("/jobs/{job_id}/deploy")
async def deploy_conversion(
    job_id: int,
    target_connection_id: int,
    dry_run: bool = Query(False),
    workspace_id: int = Depends(get_workspace_id),
    db: Session = Depends(get_db),
    deploy_service: ConversionDeployService = Depends(get_deploy_service)
):
    """Deploy converted code to target database"""
    from models.conversion_job_db import ConversionJob as ConversionJobModel
    from sqlalchemy import and_
    
    # Get job
    job = db.query(ConversionJobModel).filter(
        and_(
            ConversionJobModel.id == job_id,
            ConversionJobModel.workspace_id == workspace_id
        )
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")
    
    # Deploy
    result = await deploy_service.deploy_to_target(
        job, target_connection_id, workspace_id, dry_run
    )
    
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error_message)
    
    return result.to_dict()


@router.get("/jobs")
async def list_conversion_jobs(
    status: Optional[str] = None,
    asset_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    workspace_id: int = Depends(get_workspace_id),
    db: Session = Depends(get_db)
):
    """List conversion jobs with filters"""
    from models.conversion_job_db import ConversionJob as ConversionJobModel
    from sqlalchemy import and_
    
    query = db.query(ConversionJobModel).filter(
        ConversionJobModel.workspace_id == workspace_id
    )
    
    if status:
        query = query.filter(ConversionJobModel.status == status)
    
    if asset_type:
        query = query.filter(ConversionJobModel.asset_type == asset_type)
    
    total = query.count()
    jobs = query.order_by(ConversionJobModel.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    return {
        'jobs': jobs,
        'total': total,
        'page': page,
        'page_size': page_size
    }
