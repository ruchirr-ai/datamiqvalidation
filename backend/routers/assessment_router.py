"""
Assessment Router

Handles API endpoints for BigQuery assessments:
- Create new assessment
- List assessments
- Get assessment details
- Delete assessment
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime

from database import get_db
from services.bigquery_assessment_service import BigQueryAssessmentService
from services.recommendation_engine import RecommendationEngine
from services.tco_engine import TCOEngine
from repositories.assessment_repository import AssessmentRepository
from repositories.connection_repository import ConnectionRepository

router = APIRouter(prefix="/api/assessments", tags=["assessments"])


# Request/Response Models
class CreateAssessmentRequest(BaseModel):
    name: str
    source_connection_id: int
    target_connection_id: int


class UpdateAssessmentRequest(BaseModel):
    name: str | None = None
    source_connection_id: int | None = None
    target_connection_id: int | None = None


class AssessmentResponse(BaseModel):
    id: int
    name: str
    source_connection_id: int
    target_connection_id: int
    project_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    error_message: str | None
    total_datasets: int
    total_tables: int
    total_views: int
    total_routines: int
    total_ml_models: int
    total_size_mb: float
    created_by: str | None
    workspace_id: int

    class Config:
        from_attributes = True


class AssessmentListResponse(BaseModel):
    assessments: List[AssessmentResponse]
    total: int


class DatasetSummary(BaseModel):
    dataset_name: str
    creation_time: datetime | None
    location: str | None
    table_count: int
    total_size_mb: float


class AssessmentDetailResponse(BaseModel):
    assessment: AssessmentResponse
    datasets: List[DatasetSummary]


@router.get("/tco/regions")
async def get_tco_regions():
    """
    Get list of available AWS regions for TCO analysis.
    """
    tco_engine = TCOEngine()
    return {'regions': tco_engine.get_available_regions()}


@router.post("/", response_model=AssessmentResponse)
async def create_assessment(
    request: CreateAssessmentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Create a new BigQuery to Redshift assessment
    
    This endpoint:
    1. Validates source (BigQuery) and target (Redshift) connections
    2. Creates assessment record with 'pending' status
    3. Starts background task to collect metadata and analyze compatibility
    4. Returns assessment record immediately
    """
    try:
        # Initialize repositories
        assessment_repo = AssessmentRepository(db)
        connection_repo = ConnectionRepository(db)
        
        # Validate source connection
        source_conn = connection_repo.get_by_id(request.source_connection_id)
        if not source_conn:
            raise HTTPException(status_code=404, detail="Source connection not found")
        
        # Validate target connection
        target_conn = connection_repo.get_by_id(request.target_connection_id)
        if not target_conn:
            raise HTTPException(status_code=404, detail="Target connection not found")
        
        # Get project ID from source connection
        # For BigQuery, the database field contains the project ID
        # For other databases, use the database name as identifier
        project_id = source_conn.database or f"connection-{source_conn.id}"
        
        # Create assessment record with 'pending' status
        assessment = assessment_repo.create_assessment(
            name=request.name,
            source_connection_id=request.source_connection_id,
            target_connection_id=request.target_connection_id,
            project_id=project_id,
            status='pending',
            created_by='current_user'  # TODO: Get from auth context
        )
        
        # Create initial log entry
        assessment_repo.create_log(
            assessment_id=assessment.id,
            log_level='INFO',
            message=f"Assessment '{request.name}' created successfully",
            stage='creation',
            log_metadata={
                'source_connection_id': request.source_connection_id,
                'target_connection_id': request.target_connection_id,
                'project_id': project_id
            }
        )
        
        # Start background task to collect metadata
        background_tasks.add_task(
            run_assessment_background,
            assessment.id,
            request.source_connection_id,
            request.target_connection_id
        )
        
        return assessment
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating assessment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def run_assessment_background(
    assessment_id: int,
    source_connection_id: int,
    target_connection_id: int
):
    """
    Background task to run the assessment
    
    This collects all metadata from BigQuery and analyzes compatibility with Redshift
    """
    from database import db_instance
    import traceback
    import asyncio
    
    db = db_instance.SessionLocal()
    try:
        print(f"[BACKGROUND TASK] Starting assessment {assessment_id}")
        print(f"[BACKGROUND TASK] Source connection: {source_connection_id}, Target connection: {target_connection_id}")
        assessment_repo = AssessmentRepository(db)
        connection_repo = ConnectionRepository(db)
        
        # Log: Assessment started
        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message='Assessment execution started',
            stage='initialization'
        )
        
        # Update status to 'running'
        assessment_repo.update_status(assessment_id, 'running')
        
        # Log: Status updated
        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message='Assessment status updated to running',
            stage='initialization'
        )
        
        # Get source and target connections
        source_conn = connection_repo.get_by_id(source_connection_id)
        target_conn = connection_repo.get_by_id(target_connection_id)
        
        # Log: Connections retrieved
        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message=f'Retrieved source connection: {source_conn.name}',
            stage='initialization',
            log_metadata={'connection_id': source_connection_id, 'connection_name': source_conn.name}
        )
        
        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message=f'Retrieved target connection: {target_conn.name}',
            stage='initialization',
            log_metadata={'connection_id': target_connection_id, 'connection_name': target_conn.name}
        )
        
        # Initialize BigQuery assessment service
        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message='Initializing BigQuery assessment service',
            stage='initialization'
        )
        
        print(f"[BACKGROUND TASK] Creating BigQuery service with connection params")
        bq_service = BigQueryAssessmentService(source_conn.connection_params)
        
        # Log: Starting metadata collection
        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message='Starting metadata collection from BigQuery',
            stage='metadata_collection'
        )
        
        print(f"[BACKGROUND TASK] Starting full assessment execution")
        # Run the assessment (this collects all metadata)
        # Use asyncio.run to execute the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(bq_service.run_full_assessment(assessment_id, db))
        finally:
            loop.close()
        
        # Log: Metadata collection completed
        assessment = assessment_repo.get_by_id(assessment_id)
        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message=f'Metadata collection completed successfully',
            stage='metadata_collection',
            log_metadata={
                'total_datasets': assessment.total_datasets,
                'total_tables': assessment.total_tables,
                'total_views': assessment.total_views,
                'total_routines': assessment.total_routines,
                'total_ml_models': assessment.total_ml_models,
                'total_size_mb': assessment.total_size_mb
            }
        )
        
        # Update status to 'completed'
        assessment_repo.update_status(assessment_id, 'completed')
        
        # Log: Assessment completed
        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message=f'Assessment completed successfully. Collected {assessment.total_datasets} datasets, {assessment.total_tables} tables, {assessment.total_views} views',
            stage='completion'
        )
        
        print(f"Assessment {assessment_id} completed successfully")
        
    except Exception as e:
        error_msg = str(e)
        stack = traceback.format_exc()
        
        print(f"Error running assessment {assessment_id}: {error_msg}")
        print(f"Stack trace: {stack}")
        
        # Log: Error occurred
        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='ERROR',
            message=f'Assessment failed: {error_msg}',
            stage='error',
            stack_trace=stack
        )
        
        # Update status to 'failed' with error message
        assessment_repo.update_status(
            assessment_id, 
            'failed',
            error_message=error_msg
        )
    finally:
        db.close()


@router.get("/", response_model=AssessmentListResponse)
async def list_assessments(db: Session = Depends(get_db)):
    """
    List all assessments
    """
    try:
        assessment_repo = AssessmentRepository(db)
        assessments = assessment_repo.list_assessments()
        
        return {
            "assessments": assessments,
            "total": len(assessments)
        }
    except Exception as e:
        print(f"Error listing assessments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assessment_id}", response_model=AssessmentDetailResponse)
async def get_assessment(assessment_id: int, db: Session = Depends(get_db)):
    """
    Get assessment details including dataset summary
    """
    try:
        assessment_repo = AssessmentRepository(db)
        
        # Get assessment
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        # Get dataset summary
        datasets = assessment_repo.get_dataset_summary(assessment_id)
        
        return {
            "assessment": assessment,
            "datasets": datasets
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting assessment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{assessment_id}")
async def delete_assessment(assessment_id: int, db: Session = Depends(get_db)):
    """
    Delete an assessment and all its metadata
    """
    try:
        assessment_repo = AssessmentRepository(db)
        
        # Check if assessment exists
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        # Delete assessment (cascade will delete all related metadata)
        assessment_repo.delete_assessment(assessment_id)
        
        return {"message": "Assessment deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting assessment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{assessment_id}", response_model=AssessmentResponse)
async def update_assessment(
    assessment_id: int,
    request: UpdateAssessmentRequest,
    db: Session = Depends(get_db)
):
    """
    Update assessment details (name, connections)
    """
    try:
        assessment_repo = AssessmentRepository(db)
        connection_repo = ConnectionRepository(db)
        
        # Check if assessment exists
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        # Validate connections if provided
        if request.source_connection_id:
            source_conn = connection_repo.get_by_id(request.source_connection_id)
            if not source_conn:
                raise HTTPException(status_code=404, detail="Source connection not found")
        
        if request.target_connection_id:
            target_conn = connection_repo.get_by_id(request.target_connection_id)
            if not target_conn:
                raise HTTPException(status_code=404, detail="Target connection not found")
        
        # Update assessment
        updated_assessment = assessment_repo.update_assessment(
            assessment_id=assessment_id,
            name=request.name,
            source_connection_id=request.source_connection_id,
            target_connection_id=request.target_connection_id
        )
        
        return updated_assessment
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating assessment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{assessment_id}/run")
async def run_assessment(
    assessment_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Manually trigger assessment execution
    """
    try:
        assessment_repo = AssessmentRepository(db)
        
        # Check if assessment exists
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        # Check if assessment is already running
        if assessment.status == 'running':
            raise HTTPException(status_code=400, detail="Assessment is already running")
        
        # Reset status to pending
        assessment_repo.update_status(assessment_id, 'pending')
        
        # Create log entry
        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message='Assessment manually triggered for execution',
            stage='manual_trigger'
        )
        
        print(f"[API] About to add background task for assessment {assessment_id}")
        print(f"[API] Source connection: {assessment.source_connection_id}, Target: {assessment.target_connection_id}")
        
        # Start background task
        background_tasks.add_task(
            run_assessment_background,
            assessment_id,
            assessment.source_connection_id,
            assessment.target_connection_id
        )
        
        print(f"[API] Background task added successfully for assessment {assessment_id}")
        
        return {"message": "Assessment started successfully", "assessment_id": assessment_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error running assessment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assessment_id}/logs")
async def get_assessment_logs(assessment_id: int, db: Session = Depends(get_db)):
    """
    Get assessment execution logs from database
    """
    try:
        assessment_repo = AssessmentRepository(db)
        
        # Check if assessment exists
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        # Get logs from database
        try:
            logs = assessment_repo.get_logs(assessment_id)
        except Exception as log_error:
            # If logs table doesn't exist or other error, return empty logs
            print(f"Error fetching logs (table may not exist): {log_error}")
            logs = []
        
        # Convert to response format
        log_responses = []
        for log in logs:
            log_responses.append({
                "id": log.id,
                "assessment_id": log.assessment_id,
                "log_level": log.log_level,
                "message": log.message,
                "stage": log.stage,
                "error_code": log.error_code,
                "stack_trace": log.stack_trace,
                "log_metadata": log.log_metadata,
                "created_at": log.created_at.isoformat()
            })
        
        return {"logs": log_responses, "assessment_id": assessment_id}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting assessment logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assessment_id}/report")
async def get_assessment_report(assessment_id: int, db: Session = Depends(get_db)):
    """
    Get comprehensive assessment report with all metadata
    """
    try:
        assessment_repo = AssessmentRepository(db)
        
        # Get assessment
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        # Get all related data
        datasets = assessment_repo.get_datasets(assessment_id)
        tables = assessment_repo.get_tables(assessment_id)
        columns = assessment_repo.get_columns(assessment_id)
        views = assessment_repo.get_views(assessment_id)
        routines = assessment_repo.get_routines(assessment_id)
        ml_models = assessment_repo.get_ml_models(assessment_id)
        query_stats = assessment_repo.get_query_stats(assessment_id)
        security_policies = assessment_repo.get_security_policies(assessment_id)
        sharded_tables = assessment_repo.get_sharded_tables(assessment_id)
        
        # Build comprehensive report
        report = {
            "assessment": {
                "id": assessment.id,
                "name": assessment.name,
                "project_id": assessment.project_id,
                "status": assessment.status,
                "started_at": assessment.started_at.isoformat() if assessment.started_at else None,
                "completed_at": assessment.completed_at.isoformat() if assessment.completed_at else None,
                "total_datasets": assessment.total_datasets,
                "total_tables": assessment.total_tables,
                "total_views": assessment.total_views,
                "total_routines": assessment.total_routines,
                "total_ml_models": assessment.total_ml_models,
                "total_size_mb": assessment.total_size_mb
            },
            "datasets": [
                {
                    "dataset_name": d.dataset_name,
                    "location": d.location,
                    "creation_time": d.creation_time.isoformat() if d.creation_time else None,
                    "table_count": d.table_count,
                    "total_size_mb": d.total_size_mb
                }
                for d in datasets
            ],
            "tables": [
                {
                    "id": t.id,
                    "project_id": t.project_id,
                    "dataset_name": t.dataset_name,
                    "table_name": t.table_name,
                    "table_type": t.table_type,
                    "creation_time": t.creation_time.isoformat() if t.creation_time else None,
                    "row_count": t.row_count,
                    "size_mb": t.size_mb,
                    "partitioning_columns": t.partitioning_columns or [],
                    "clustering_columns": t.clustering_columns or [],
                    "has_column_security": t.has_column_security,
                    "has_row_security": t.has_row_security,
                    "is_sharded": t.is_sharded,
                    "update_frequency": t.update_frequency
                }
                for t in tables
            ],
            "columns": [
                {
                    "table_id": c.table_id,
                    "column_name": c.column_name,
                    "data_type": c.data_type,
                    "is_nullable": c.is_nullable,
                    "ordinal_position": c.ordinal_position,
                    "is_partitioning_column": c.is_partitioning_column,
                    "clustering_ordinal_position": c.clustering_ordinal_position,
                    "policy_tags": c.policy_tags or [],
                    "max_length": c.max_length
                }
                for c in columns
            ],
            "views": [
                {
                    "view_name": v.view_name,
                    "view_type": v.view_type,
                    "view_definition": v.view_definition,
                    "creation_time": v.creation_time.isoformat() if v.creation_time else None,
                    "dependencies": v.dependencies or [],
                    "dependent_tables": v.dependent_tables or [],
                    "dependent_views": v.dependent_views or [],
                    "dependent_functions": v.dependent_functions or [],
                    "dependency_depth": v.dependency_depth
                }
                for v in views
            ],
            "routines": [
                {
                    "routine_name": r.routine_name,
                    "routine_type": r.routine_type,
                    "return_type": r.return_type,
                    "definition": r.definition,
                    "external_language": r.external_language,
                    "creation_time": r.creation_time.isoformat() if r.creation_time else None,
                    "call_frequency": r.call_frequency,
                    "dependent_tables": r.dependent_tables or [],
                    "dependent_views": r.dependent_views or [],
                    "dependent_functions": r.dependent_functions or [],
                    "calls_procedures": r.calls_procedures or [],
                    "dependency_depth": r.dependency_depth
                }
                for r in routines
            ],
            "ml_models": [
                {
                    "model_name": m.model_name,
                    "model_type": m.model_type,
                    "dataset_name": m.dataset_name,
                    "creation_time": m.creation_time.isoformat() if m.creation_time else None,
                    "last_modified_time": m.last_modified_time.isoformat() if m.last_modified_time else None
                }
                for m in ml_models
            ],
            "query_stats": [
                {
                    "job_id": q.job_id,
                    "execution_time": q.execution_time.isoformat() if q.execution_time else None,
                    "query_text": q.query_text[:500] if q.query_text else None,  # Truncate for response
                    "bytes_scanned": q.bytes_scanned,
                    "slot_milliseconds": q.slot_milliseconds,
                    "cache_hit": q.cache_hit,
                    "referenced_tables": q.referenced_tables or [],
                    "user_email": q.user_email
                }
                for q in query_stats  # Return all query stats for complete user insights
            ],
            "security_policies": [
                {
                    "security_type": s.security_type,
                    "table_name": s.table_name,
                    "policy_name": s.policy_name,
                    "filter_predicate": s.filter_predicate,
                    "grantees": s.grantees or []
                }
                for s in security_policies
            ],
            "sharded_tables": [
                {
                    "shard_group": st.shard_group,
                    "table_prefix": st.table_prefix,
                    "shard_count": st.shard_count,
                    "total_size_mb": st.total_size_mb,
                    "date_range_start": st.date_range_start.isoformat() if st.date_range_start else None,
                    "date_range_end": st.date_range_end.isoformat() if st.date_range_end else None,
                    "shard_tables": st.shard_tables or []
                }
                for st in sharded_tables
            ]
        }
        
        return report
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting assessment report: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assessment_id}/recommendations")
async def get_assessment_recommendations(assessment_id: int, db: Session = Depends(get_db)):
    """
    Get Redshift configuration recommendations based on assessment data.
    """
    try:
        assessment_repo = AssessmentRepository(db)

        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        tables = assessment_repo.get_tables(assessment_id)
        columns = assessment_repo.get_columns(assessment_id)
        query_stats = assessment_repo.get_query_stats(assessment_id)
        datasets = assessment_repo.get_datasets(assessment_id)

        # Convert ORM objects to dicts
        assessment_dict = {
            'total_size_mb': assessment.total_size_mb or 0,
            'total_tables': assessment.total_tables or 0,
            'total_datasets': assessment.total_datasets or 0,
        }
        tables_list = [
            {
                'id': t.id,
                'table_name': t.table_name,
                'dataset_name': t.dataset_name,
                'table_type': t.table_type,
                'row_count': t.row_count or 0,
                'size_mb': t.size_mb or 0,
                'partitioning_columns': t.partitioning_columns or [],
                'clustering_columns': t.clustering_columns or [],
            }
            for t in tables
        ]
        columns_list = [
            {
                'table_id': c.table_id,
                'column_name': c.column_name,
                'data_type': c.data_type,
                'is_nullable': c.is_nullable,
                'ordinal_position': c.ordinal_position,
            }
            for c in columns
        ]
        query_stats_list = [
            {
                'job_id': q.job_id,
                'query_text': q.query_text,
                'bytes_scanned': q.bytes_scanned or 0,
                'slot_milliseconds': q.slot_milliseconds or 0,
                'user_email': q.user_email,
                'execution_time': q.execution_time.isoformat() if q.execution_time else None,
            }
            for q in query_stats
        ]
        datasets_list = [
            {
                'dataset_name': d.dataset_name,
                'location': d.location,
            }
            for d in datasets
        ]

        engine = RecommendationEngine()
        recommendations = engine.generate_recommendations(
            assessment_dict, tables_list, columns_list, query_stats_list, datasets_list
        )

        return recommendations

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating recommendations: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assessment_id}/tco")
async def get_assessment_tco(
    assessment_id: int,
    region: str = 'us-east-1',
    db: Session = Depends(get_db)
):
    """
    Get TCO analysis comparing BigQuery vs Redshift costs.
    """
    try:
        assessment_repo = AssessmentRepository(db)

        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        tables = assessment_repo.get_tables(assessment_id)
        query_stats = assessment_repo.get_query_stats(assessment_id)

        assessment_dict = {
            'total_size_mb': assessment.total_size_mb or 0,
        }
        tables_list = [
            {
                'table_name': t.table_name,
                'row_count': t.row_count or 0,
                'size_mb': t.size_mb or 0,
            }
            for t in tables
        ]
        query_stats_list = [
            {
                'bytes_scanned': q.bytes_scanned or 0,
                'slot_milliseconds': q.slot_milliseconds or 0,
                'execution_time': q.execution_time.isoformat() if q.execution_time else None,
                'query_text': q.query_text,
                'user_email': q.user_email,
            }
            for q in query_stats
        ]

        # First get config recommendations (includes workload analysis)
        columns = assessment_repo.get_columns(assessment_id)
        datasets = assessment_repo.get_datasets(assessment_id)
        columns_list = [
            {'table_id': c.table_id, 'column_name': c.column_name, 'data_type': c.data_type}
            for c in columns
        ]
        datasets_list = [{'dataset_name': d.dataset_name, 'location': d.location} for d in datasets]

        rec_engine = RecommendationEngine()
        recs = rec_engine.generate_recommendations(
            assessment_dict,
            [{'id': t.id, 'table_name': t.table_name, 'dataset_name': t.dataset_name,
              'table_type': t.table_type, 'row_count': t.row_count or 0,
              'partitioning_columns': t.partitioning_columns or [],
              'clustering_columns': t.clustering_columns or []}
             for t in tables],
            columns_list, query_stats_list, datasets_list
        )

        provisioned_config = recs['config_recommendation']['provisioned']
        serverless_config = recs['config_recommendation']['serverless']
        workload_metrics = recs.get('workload_metrics', {})

        tco_engine = TCOEngine()
        tco = tco_engine.calculate_tco(
            assessment_dict, tables_list, query_stats_list,
            provisioned_config, serverless_config,
            workload_metrics, region
        )

        return tco

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error calculating TCO: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
