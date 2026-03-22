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
try:
    from services.sqlserver_assessment_service import SQLServerAssessmentService
except ImportError:
    SQLServerAssessmentService = None
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
    Background task to run the assessment.

    Detects the source database type (BigQuery or SQL Server) and runs
    the appropriate assessment service. BigQuery path is unchanged;
    SQL Server path uses SQLServerAssessmentService.
    """
    from database import db_instance
    import traceback
    import asyncio

    db = db_instance.SessionLocal()
    try:
        print(f"[BACKGROUND TASK] Starting assessment {assessment_id}", flush=True)
        print(f"[BACKGROUND TASK] Source connection: {source_connection_id}, Target connection: {target_connection_id}", flush=True)

        assessment_repo = AssessmentRepository(db)
        connection_repo = ConnectionRepository(db)

        # Log: Assessment started
        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message='Assessment execution started',
            stage='initialization'
        )
        db.commit()

        # Update status to 'running'
        assessment_repo.update_status(assessment_id, 'running')
        db.commit()

        # Log: Status updated
        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message='Assessment status updated to running',
            stage='initialization'
        )
        db.commit()

        # Get source and target connections
        source_conn = connection_repo.get_by_id(source_connection_id)
        target_conn = connection_repo.get_by_id(target_connection_id)

        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message=f'Retrieved source connection: {source_conn.name}',
            stage='initialization',
            log_metadata={'connection_id': source_connection_id, 'connection_name': source_conn.name}
        )
        db.commit()

        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message=f'Retrieved target connection: {target_conn.name}',
            stage='initialization',
            log_metadata={'connection_id': target_connection_id, 'connection_name': target_conn.name}
        )
        db.commit()

        # Determine source database type (the 'database' field holds the engine name,
        # e.g. 'bigquery', 'sqlserver'; the 'type' field is 'source'/'target')
        source_db_type = getattr(source_conn, 'database', 'bigquery').lower()
        print(f"[BACKGROUND TASK] Source DB Type: '{source_db_type}'", flush=True)

        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message=f'Initializing {source_db_type} assessment service',
            stage='initialization'
        )
        db.commit()

        # Initialize the appropriate assessment service based on database type
        if source_db_type == 'sqlserver':
            assessment_service = SQLServerAssessmentService(source_conn.connection_params)
        else:
            # Default to BigQuery (preserves existing behavior)
            assessment_service = BigQueryAssessmentService(source_conn.connection_params)

        # Log: Starting metadata collection
        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message=f'Starting metadata collection from {source_db_type}',
            stage='metadata_collection'
        )
        db.commit()

        print(f"[BACKGROUND TASK] Starting full assessment execution", flush=True)

        # Run the assessment (this collects all metadata)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(assessment_service.run_full_assessment(assessment_id, db))
        finally:
            loop.close()

        # Log: Metadata collection completed
        assessment = assessment_repo.get_by_id(assessment_id)
        assessment_repo.create_log(
            assessment_id=assessment_id,
            log_level='INFO',
            message='Metadata collection completed successfully',
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


@router.get("/{assessment_id}/assets")
async def get_assessment_assets(assessment_id: int, db: Session = Depends(get_db)):
    """
    Get convertible assets (tables, views, routines) from a completed assessment.
    Returns assets in the format expected by the batch converter's AssetSelector.
    """
    try:
        assessment_repo = AssessmentRepository(db)

        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        assets = []

        # Tables — source_code is a CREATE TABLE stub from column metadata
        tables = assessment_repo.get_tables(assessment_id)
        for t in tables:
            source_code = ""
            if hasattr(t, 'columns') and t.columns:
                cols = ", ".join(
                    f"{c.column_name} {c.data_type}"
                    for c in sorted(t.columns, key=lambda c: c.ordinal_position or 0)
                )
                source_code = f"CREATE TABLE {t.dataset_name}.{t.table_name} ({cols});"
            else:
                source_code = f"-- Table: {t.dataset_name}.{t.table_name} (schema not available)"

            assets.append({
                "asset_type": "TABLE_DDL",
                "asset_name": f"{t.dataset_name}.{t.table_name}" if t.dataset_name else t.table_name,
                "source_code": source_code,
            })

        # Views — source_code is the view definition
        views = assessment_repo.get_views(assessment_id)
        for v in views:
            source_code = v.view_definition or f"-- View: {v.view_name} (definition not available)"
            assets.append({
                "asset_type": "VIEW" if v.view_type != "MATERIALIZED_VIEW" else "MATERIALIZED_VIEW",
                "asset_name": v.view_name,
                "source_code": source_code,
            })

        # Routines → STORED_PROCEDURE / FUNCTION
        routines = assessment_repo.get_routines(assessment_id)
        for r in routines:
            rtype = "STORED_PROCEDURE" if r.routine_type == "PROCEDURE" else "FUNCTION"
            source_code = r.definition or f"-- {rtype}: {r.routine_name} (definition not available)"
            assets.append({
                "asset_type": rtype,
                "asset_name": r.routine_name,
                "source_code": source_code,
            })

        return {
            "assessment_id": assessment.id,
            "assessment_name": assessment.name,
            "total": len(assets),
            "assets": assets,
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting assessment assets: {e}")
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
        indexes = assessment_repo.get_indexes(assessment_id)
        
        # Determine source database type from connection
        source_db_type = 'bigquery'  # default
        try:
            from models.connection import Connection
            source_conn = db.query(Connection).filter(
                Connection.id == assessment.source_connection_id
            ).first()
            if source_conn:
                source_db_type = getattr(source_conn, 'database', 'bigquery').lower()
        except Exception:
            pass
        
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
                "total_size_mb": assessment.total_size_mb,
                "source_db_type": source_db_type
            },
            "datasets": [
                {
                    "dataset_name": d.dataset_name,
                    "location": d.location,
                    "creation_time": d.creation_time.isoformat() if d.creation_time else None,
                    "table_count": d.table_count,
                    "total_size_mb": d.total_size_mb,
                    "dataset_metadata": d.dataset_metadata or {}
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
                    "update_frequency": t.update_frequency,
                    "table_metadata": t.table_metadata or {}
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
                    "dependency_depth": r.dependency_depth,
                    "routine_metadata": r.routine_metadata or {}
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
                    "bytes_scanned": q.bytes_scanned,
                    "slot_milliseconds": q.slot_milliseconds,
                    "cache_hit": q.cache_hit,
                    "user_email": q.user_email
                }
                for q in query_stats
            ],
            "security_policies": [
                {
                    "security_type": s.security_type,
                    "table_name": s.table_name,
                    "policy_name": s.policy_name,
                    "filter_predicate": s.filter_predicate,
                    "grantees": s.grantees or [],
                    "security_metadata": s.security_metadata or {}
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
            ],
            "indexes": [
                {
                    "id": idx.id,
                    "table_id": idx.table_id,
                    "schema_name": idx.schema_name,
                    "table_name": idx.table_name,
                    "object_type": idx.object_type if hasattr(idx, 'object_type') else 'TABLE',
                    "index_name": idx.index_name,
                    "index_type": idx.index_type,
                    "is_unique": idx.is_unique,
                    "is_primary_key": idx.is_primary_key,
                    "is_clustered": idx.is_clustered,
                    "key_columns": idx.key_columns,
                    "included_columns": idx.included_columns,
                    "filter_definition": idx.filter_definition,
                    "size_mb": idx.size_mb,
                    "row_count": idx.row_count,
                    "index_metadata": idx.index_metadata or {}
                }
                for idx in indexes
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


@router.get("/{assessment_id}/report/summary")
async def get_assessment_report_summary(assessment_id: int, db: Session = Depends(get_db)):
    """Get lightweight assessment summary (metadata + datasets only) for fast initial load."""
    try:
        assessment_repo = AssessmentRepository(db)
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        datasets = assessment_repo.get_datasets(assessment_id)

        source_db_type = 'bigquery'
        try:
            from models.connection import Connection
            source_conn = db.query(Connection).filter(Connection.id == assessment.source_connection_id).first()
            if source_conn:
                source_db_type = getattr(source_conn, 'database', 'bigquery').lower()
        except Exception:
            pass

        # For SQL Server, compute extra summary counts
        trigger_count = 0
        schemas_count = 0
        security_items_count = 0
        security_policies_preview = []
        if source_db_type == 'sqlserver':
            try:
                routines = assessment_repo.get_routines(assessment_id)
                trigger_count = len([r for r in routines if r.routine_type == 'TRIGGER'])
            except Exception:
                pass
            try:
                security_policies = assessment_repo.get_security_policies(assessment_id)
                security_items_count = len(security_policies)
                schemas_count = len([s for s in security_policies if s.security_type == 'SCHEMA'])
                # Include security policies preview for schemas tab
                security_policies_preview = [
                    {
                        "security_type": s.security_type,
                        "table_name": s.table_name,
                        "policy_name": s.policy_name,
                        "filter_predicate": s.filter_predicate,
                        "grantees": s.grantees or [],
                        "security_metadata": s.security_metadata or {}
                    }
                    for s in security_policies
                ]
            except Exception:
                pass

        return {
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
                "total_size_mb": assessment.total_size_mb,
                "source_db_type": source_db_type,
                "trigger_count": trigger_count,
                "schemas_count": schemas_count,
                "security_items_count": security_items_count
            },
            "datasets": [
                {
                    "dataset_name": d.dataset_name,
                    "location": d.location,
                    "creation_time": d.creation_time.isoformat() if d.creation_time else None,
                    "table_count": d.table_count,
                    "total_size_mb": d.total_size_mb,
                    "dataset_metadata": d.dataset_metadata or {}
                }
                for d in datasets
            ],
            "security_policies_preview": security_policies_preview
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting report summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assessment_id}/report/tables")
async def get_assessment_report_tables(assessment_id: int, page: int = 1, page_size: int = 50, db: Session = Depends(get_db)):
    """Get paginated tables with their columns for an assessment."""
    try:
        assessment_repo = AssessmentRepository(db)
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        all_tables = assessment_repo.get_tables(assessment_id)
        all_columns = assessment_repo.get_columns(assessment_id)
        all_indexes = assessment_repo.get_indexes(assessment_id)

        total = len(all_tables)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_tables = all_tables[start:end]
        table_ids = {t.id for t in paginated_tables}

        return {
            "tables": [
                {
                    "id": t.id, "project_id": t.project_id, "dataset_name": t.dataset_name,
                    "table_name": t.table_name, "table_type": t.table_type,
                    "creation_time": t.creation_time.isoformat() if t.creation_time else None,
                    "row_count": t.row_count, "size_mb": t.size_mb,
                    "partitioning_columns": t.partitioning_columns or [],
                    "clustering_columns": t.clustering_columns or [],
                    "has_column_security": t.has_column_security, "has_row_security": t.has_row_security,
                    "is_sharded": t.is_sharded, "update_frequency": t.update_frequency,
                    "table_metadata": t.table_metadata or {}
                }
                for t in paginated_tables
            ],
            "columns": [
                {
                    "table_id": c.table_id, "column_name": c.column_name, "data_type": c.data_type,
                    "is_nullable": c.is_nullable, "ordinal_position": c.ordinal_position,
                    "is_partitioning_column": c.is_partitioning_column,
                    "clustering_ordinal_position": c.clustering_ordinal_position,
                    "policy_tags": c.policy_tags or [], "max_length": c.max_length
                }
                for c in all_columns if c.table_id in table_ids
            ],
            "indexes": [
                {
                    "id": idx.id, "table_id": idx.table_id, "schema_name": idx.schema_name,
                    "table_name": idx.table_name,
                    "object_type": idx.object_type if hasattr(idx, 'object_type') else 'TABLE',
                    "index_name": idx.index_name, "index_type": idx.index_type,
                    "is_unique": idx.is_unique, "is_primary_key": idx.is_primary_key,
                    "is_clustered": idx.is_clustered, "key_columns": idx.key_columns,
                    "included_columns": idx.included_columns, "filter_definition": idx.filter_definition,
                    "size_mb": idx.size_mb, "row_count": idx.row_count,
                    "index_metadata": idx.index_metadata or {}
                }
                for idx in all_indexes if idx.table_id in table_ids
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting report tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assessment_id}/report/views")
async def get_assessment_report_views(assessment_id: int, page: int = 1, page_size: int = 50, db: Session = Depends(get_db)):
    """Get paginated views for an assessment."""
    try:
        assessment_repo = AssessmentRepository(db)
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        all_views = assessment_repo.get_views(assessment_id)
        total = len(all_views)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_views = all_views[start:end]

        return {
            "views": [
                {
                    "view_name": v.view_name, "view_type": v.view_type,
                    "view_definition": v.view_definition,
                    "creation_time": v.creation_time.isoformat() if v.creation_time else None,
                    "dependencies": v.dependencies or [],
                    "dependent_tables": v.dependent_tables or [],
                    "dependent_views": v.dependent_views or [],
                    "dependent_functions": v.dependent_functions or [],
                    "dependency_depth": v.dependency_depth
                }
                for v in paginated_views
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting report views: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assessment_id}/report/routines")
async def get_assessment_report_routines(assessment_id: int, db: Session = Depends(get_db)):
    """Get all routines (stored procedures, functions, triggers) for an assessment."""
    try:
        assessment_repo = AssessmentRepository(db)
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        routines = assessment_repo.get_routines(assessment_id)
        return {
            "routines": [
                {
                    "routine_name": r.routine_name, "routine_type": r.routine_type,
                    "return_type": r.return_type, "definition": r.definition,
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
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting report routines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assessment_id}/report/security")
async def get_assessment_report_security(assessment_id: int, db: Session = Depends(get_db)):
    """Get security policies and column-level security data for an assessment."""
    try:
        assessment_repo = AssessmentRepository(db)
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        security_policies = assessment_repo.get_security_policies(assessment_id)
        columns = assessment_repo.get_columns(assessment_id)
        tables = assessment_repo.get_tables(assessment_id)

        return {
            "security_policies": [
                {
                    "security_type": s.security_type, "table_name": s.table_name,
                    "policy_name": s.policy_name, "filter_predicate": s.filter_predicate,
                    "grantees": s.grantees or [], "security_metadata": s.security_metadata or {}
                }
                for s in security_policies
            ],
            "columns": [
                {
                    "table_id": c.table_id, "column_name": c.column_name, "data_type": c.data_type,
                    "is_nullable": c.is_nullable, "ordinal_position": c.ordinal_position,
                    "is_partitioning_column": c.is_partitioning_column,
                    "clustering_ordinal_position": c.clustering_ordinal_position,
                    "policy_tags": c.policy_tags or [], "max_length": c.max_length
                }
                for c in columns
            ],
            "tables": [
                {
                    "id": t.id, "dataset_name": t.dataset_name, "table_name": t.table_name
                }
                for t in tables
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting report security: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assessment_id}/report/ml-models")
async def get_assessment_report_ml_models(assessment_id: int, db: Session = Depends(get_db)):
    """Get ML models and Spark models for an assessment."""
    try:
        assessment_repo = AssessmentRepository(db)
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        ml_models = assessment_repo.get_ml_models(assessment_id)
        routines = assessment_repo.get_routines(assessment_id)

        spark_models = [
            {
                "routine_name": r.routine_name, "routine_type": r.routine_type,
                "return_type": r.return_type, "definition": r.definition,
                "external_language": r.external_language,
                "creation_time": r.creation_time.isoformat() if r.creation_time else None,
                "call_frequency": r.call_frequency
            }
            for r in routines
            if r.external_language == 'PYTHON' and r.definition and ('pyspark' in r.definition or 'spark.' in r.definition)
        ]

        return {
            "ml_models": [
                {
                    "model_name": m.model_name, "model_type": m.model_type,
                    "dataset_name": m.dataset_name,
                    "creation_time": m.creation_time.isoformat() if m.creation_time else None,
                    "last_modified_time": m.last_modified_time.isoformat() if m.last_modified_time else None
                }
                for m in ml_models
            ],
            "spark_models": spark_models
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting report ML models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{assessment_id}/report/user-insights")
async def get_assessment_report_user_insights(assessment_id: int, db: Session = Depends(get_db)):
    """Get query stats for user insights tab."""
    try:
        assessment_repo = AssessmentRepository(db)
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        query_stats = assessment_repo.get_query_stats(assessment_id)
        return {
            "query_stats": [
                {
                    "job_id": q.job_id,
                    "execution_time": q.execution_time.isoformat() if q.execution_time else None,
                    "bytes_scanned": q.bytes_scanned,
                    "slot_milliseconds": q.slot_milliseconds,
                    "cache_hit": q.cache_hit,
                    "user_email": q.user_email
                }
                for q in query_stats
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting report user insights: {e}")
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
            'assessment_data': assessment.assessment_data or {},
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
                'query_metadata': q.query_metadata or {},
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
            'assessment_data': assessment.assessment_data or {},
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
                'cache_hit': q.cache_hit,
                'query_metadata': q.query_metadata if isinstance(q.query_metadata, dict) else {},
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


@router.get("/{assessment_id}/query-insights")
async def get_query_insights(
    assessment_id: int,
    timeframe: str = "all",  # all, 24h, 7d, 30d
    search: str = "",
    sort_by: str = "bytes_scanned",  # bytes_scanned, slot_milliseconds, execution_time
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get query insights with aggregated statistics and filtering
    
    Timeframe options:
    - all: All time
    - 24h: Last 24 hours
    - 7d: Last 7 days
    - 30d: Last 30 days
    """
    try:
        assessment_repo = AssessmentRepository(db)
        
        # Get assessment
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        # Get all query stats
        all_query_stats = assessment_repo.get_query_stats(assessment_id)
        
        # Filter by timeframe
        from datetime import datetime, timedelta
        import re
        now = datetime.utcnow()
        
        if timeframe == "24h":
            cutoff = now - timedelta(hours=24)
            query_stats = [q for q in all_query_stats if q.execution_time and q.execution_time >= cutoff]
        elif timeframe == "7d":
            cutoff = now - timedelta(days=7)
            query_stats = [q for q in all_query_stats if q.execution_time and q.execution_time >= cutoff]
        elif timeframe == "30d":
            cutoff = now - timedelta(days=30)
            query_stats = [q for q in all_query_stats if q.execution_time and q.execution_time >= cutoff]
        else:  # all
            query_stats = all_query_stats
        
        # Calculate aggregated metrics
        total_queries = len(query_stats)
        total_bytes_scanned = sum(q.bytes_scanned or 0 for q in query_stats)
        total_bytes_billed = 0
        total_slot_ms = sum(q.slot_milliseconds or 0 for q in query_stats)

        # Cache hit ratio: only count SELECT queries (cache_hit is meaningless for DML/DDL)
        # Also handle None cache_hit properly (don't count as miss)
        WRITE_STATEMENT_TYPES = {'INSERT', 'UPDATE', 'DELETE', 'MERGE', 'CREATE_TABLE_AS_SELECT',
                                  'CREATE_TABLE', 'DROP_TABLE', 'ALTER_TABLE', 'TRUNCATE_TABLE',
                                  'CREATE_VIEW', 'DROP_VIEW', 'CREATE_FUNCTION', 'DROP_FUNCTION',
                                  'CREATE_PROCEDURE', 'DROP_PROCEDURE', 'CREATE_MODEL', 'EXPORT_DATA'}
        
        select_queries = 0
        cache_hits = 0
        read_count = 0
        write_count = 0
        for q in query_stats:
            meta = q.query_metadata if isinstance(q.query_metadata, dict) else {}
            stmt_type = (meta.get('statement_type') or '').upper()
            bytes_billed_q = meta.get('bytes_billed', 0) or 0
            total_bytes_billed += bytes_billed_q
            
            # Read vs write classification using BQ statement_type (accurate)
            if stmt_type and stmt_type != 'UNKNOWN':
                if stmt_type in WRITE_STATEMENT_TYPES:
                    write_count += 1
                else:
                    read_count += 1
                # Cache hit only meaningful for SELECT
                if stmt_type == 'SELECT':
                    select_queries += 1
                    if q.cache_hit is True:
                        cache_hits += 1
            else:
                # Fallback to regex if statement_type not available (old data)
                if q.query_text:
                    query_upper = q.query_text.strip().upper()
                    if re.match(r'^\s*(INSERT|UPDATE|DELETE|MERGE|CREATE|DROP|ALTER|TRUNCATE)', query_upper):
                        write_count += 1
                    else:
                        read_count += 1
                        select_queries += 1
                        if q.cache_hit is True:
                            cache_hits += 1
                else:
                    read_count += 1
        
        cache_hit_rate = (cache_hits / select_queries * 100) if select_queries > 0 else 0
        
        avg_execution_time_ms = (total_slot_ms / total_queries) if total_queries > 0 else 0
        avg_slot_ms_raw = avg_execution_time_ms  # Save for later use
        
        unique_users = set(q.user_email for q in query_stats if q.user_email)
        active_users_count = len(unique_users)
        
        concurrent_queries_hourly = {}
        concurrent_queries_daily = {}
        concurrent_queries_weekly = {}
        
        for q in query_stats:
            if q.execution_time:
                hour_key = q.execution_time.strftime('%Y-%m-%d %H:00')
                concurrent_queries_hourly[hour_key] = concurrent_queries_hourly.get(hour_key, 0) + 1
                day_key = q.execution_time.strftime('%Y-%m-%d')
                concurrent_queries_daily[day_key] = concurrent_queries_daily.get(day_key, 0) + 1
                week_key = q.execution_time.strftime('%Y-W%W')
                concurrent_queries_weekly[week_key] = concurrent_queries_weekly.get(week_key, 0) + 1
        
        hourly_data = [{"time": k, "count": v} for k, v in sorted(concurrent_queries_hourly.items())]
        daily_data = [{"time": k, "count": v} for k, v in sorted(concurrent_queries_daily.items())]
        weekly_data = [{"time": k, "count": v} for k, v in sorted(concurrent_queries_weekly.items())]
        
        # Build query list with search filter
        filtered_stats = query_stats
        if search:
            search_lower = search.lower()
            filtered_stats = [q for q in query_stats if (
                (q.query_text and search_lower in q.query_text.lower()) or
                (q.user_email and search_lower in q.user_email.lower()) or
                (q.job_id and search_lower in q.job_id.lower())
            )]
        
        # Sort
        if sort_by == "slot_milliseconds":
            filtered_stats.sort(key=lambda q: q.slot_milliseconds or 0, reverse=True)
        elif sort_by == "execution_time":
            filtered_stats.sort(key=lambda q: q.execution_time or datetime.min, reverse=True)
        elif sort_by == "est_runtime":
            # Sort by estimated wall-clock runtime (slot_ms / concurrent_slots)
            # Higher slot_ms with lower concurrency = longer runtime
            filtered_stats.sort(key=lambda q: q.slot_milliseconds or 0, reverse=True)
        else:  # bytes_scanned (default)
            filtered_stats.sort(key=lambda q: q.bytes_scanned or 0, reverse=True)
        
        total_filtered = len(filtered_stats)
        
        # Paginate
        start = (page - 1) * page_size
        end = start + page_size
        page_stats = filtered_stats[start:end]
        
        # --- New metrics: concurrent queries, slot utilization, query runtime ---
        # Estimate max concurrent queries using 1-minute windows
        minute_buckets = {}
        for q in query_stats:
            if q.execution_time:
                minute_key = q.execution_time.strftime('%Y-%m-%d %H:%M')
                minute_buckets[minute_key] = minute_buckets.get(minute_key, 0) + 1
        max_concurrent_queries = max(minute_buckets.values()) if minute_buckets else 0
        avg_concurrent_queries = round(sum(minute_buckets.values()) / len(minute_buckets), 1) if minute_buckets else 0

        # Slot utilization per query (slot_ms as proxy for slot usage)
        slot_values = [q.slot_milliseconds or 0 for q in query_stats]
        non_zero_slots = [s for s in slot_values if s > 0]
        max_slot_ms = max(slot_values) if slot_values else 0
        min_slot_ms = min(non_zero_slots) if non_zero_slots else 0
        avg_slot_ms_per_query = round(total_slot_ms / total_queries, 0) if total_queries > 0 else 0

        # Compute per-query concurrent slots using actual runtime when available
        per_query_concurrent_slots = []
        for q in query_stats:
            q_slot_ms = q.slot_milliseconds or 0
            if q_slot_ms <= 0:
                continue
            # Try to get actual runtime from query_metadata
            q_runtime_ms = 0
            if q.query_metadata and isinstance(q.query_metadata, dict):
                q_runtime_ms = q.query_metadata.get('total_elapsed_time_ms', 0)
            if q_runtime_ms and q_runtime_ms > 0:
                per_query_concurrent_slots.append(max(1, q_slot_ms / q_runtime_ms))
            else:
                per_query_concurrent_slots.append(max(1, q_slot_ms / 30000))

        est_concurrent_slots = (sum(per_query_concurrent_slots) / len(per_query_concurrent_slots)) if per_query_concurrent_slots else 1

        # Estimate query runtime
        avg_wall_clock_s = (avg_slot_ms_per_query / max(est_concurrent_slots, 1)) / 1000 if avg_slot_ms_per_query > 0 else 0
        max_query_runtime_seconds = round((max_slot_ms / max(est_concurrent_slots, 1)) / 1000, 2) if max_slot_ms > 0 else 0
        min_query_runtime_seconds = round((min_slot_ms / max(est_concurrent_slots, 1)) / 1000, 4) if min_slot_ms > 0 else 0
        avg_query_runtime_seconds = round(avg_wall_clock_s, 2)

        # Peak slot utilization using sweep-line algorithm for true overlap.
        # For each query, compute [start, end) interval and its concurrent slots.
        # At every start/end event, track the running total of slots.
        # The maximum running total = true peak slots at any point in time.
        from datetime import timedelta as _td
        events = []  # list of (timestamp, +slots or -slots)
        total_query_slots_sum = 0.0
        query_interval_count = 0
        for q in query_stats:
            if not q.execution_time:
                continue
            q_slot_ms = q.slot_milliseconds or 0
            if q_slot_ms <= 0:
                continue
            # Compute this query's concurrent slot usage
            q_runtime_ms = 0
            if q.query_metadata and isinstance(q.query_metadata, dict):
                q_runtime_ms = q.query_metadata.get('total_elapsed_time_ms', 0)
            if q_runtime_ms and q_runtime_ms > 0:
                q_slots = max(1, q_slot_ms / q_runtime_ms)
                q_duration_ms = q_runtime_ms
            else:
                q_slots = max(1, q_slot_ms / 30000)
                q_duration_ms = 30000  # assume 30s
            start_t = q.execution_time
            end_t = start_t + _td(milliseconds=q_duration_ms)
            events.append((start_t, q_slots))
            events.append((end_t, -q_slots))
            total_query_slots_sum += q_slots
            query_interval_count += 1

        if events:
            # Sort by time; ties broken by ends (-) before starts (+)
            events.sort(key=lambda e: (e[0], e[1]))
            running_slots = 0.0
            peak_slot_utilization = 0.0
            for _, delta in events:
                running_slots += delta
                if running_slots > peak_slot_utilization:
                    peak_slot_utilization = running_slots
            peak_slot_utilization = round(peak_slot_utilization, 1)
            avg_slot_utilization = round(total_query_slots_sum / query_interval_count, 1) if query_interval_count else 0
        else:
            peak_slot_utilization = 0
            avg_slot_utilization = round(est_concurrent_slots, 1)

        # Override with JOBS_TIMELINE data if available (most accurate source)
        assessment_data = assessment.assessment_data or {}
        slot_timeline = assessment_data.get('slot_timeline') or {}
        p50_slot_utilization = 0
        p90_slot_utilization = 0
        p95_slot_utilization = 0
        p99_slot_utilization = 0
        if slot_timeline.get('peak_concurrent_slots', 0) > 0:
            peak_slot_utilization = round(slot_timeline['peak_concurrent_slots'], 1)
            avg_slot_utilization = round(slot_timeline.get('avg_concurrent_slots', avg_slot_utilization), 1)
            p50_slot_utilization = round(slot_timeline.get('p50_concurrent_slots', 0), 1)
            p90_slot_utilization = round(slot_timeline.get('p90_concurrent_slots', 0), 1)
            p95_slot_utilization = round(slot_timeline.get('p95_concurrent_slots', 0), 1)
            p99_slot_utilization = round(slot_timeline.get('p99_concurrent_slots', 0), 1)

        # Avg execution time = average slot-time per query (total CPU time / queries)
        # This differs from avg_query_runtime_seconds which is estimated wall-clock time.
        # slot-time = concurrent_slots × wall_clock, so slot-time > wall-clock for parallel queries.
        avg_execution_time_seconds = (avg_slot_ms_per_query / 1000) if avg_slot_ms_per_query > 0 else 0

        # ── Q3: Duration distribution histogram (bucket by minutes) ──
        duration_buckets = {}
        for q in query_stats:
            q_runtime_ms = 0
            if q.query_metadata and isinstance(q.query_metadata, dict):
                q_runtime_ms = q.query_metadata.get('total_elapsed_time_ms', 0)
            if not q_runtime_ms and q.slot_milliseconds:
                q_runtime_ms = (q.slot_milliseconds or 0) / max(est_concurrent_slots, 1)
            bucket_mins = round((q_runtime_ms or 0) / 60000)
            duration_buckets[bucket_mins] = duration_buckets.get(bucket_mins, 0) + 1
        duration_distribution = sorted(
            [{"duration_mins": k, "query_count": v} for k, v in duration_buckets.items()],
            key=lambda x: x["duration_mins"]
        )

        # ── Q4: Concurrent query percentiles (per-minute windows) ──
        minute_counts = sorted(minute_buckets.values()) if minute_buckets else []
        n_min = len(minute_counts)
        concurrent_query_percentiles = {}
        if n_min > 0:
            concurrent_query_percentiles = {
                "p50": minute_counts[min(int(n_min * 0.50), n_min - 1)],
                "p90": minute_counts[min(int(n_min * 0.90), n_min - 1)],
                "p95": minute_counts[min(int(n_min * 0.95), n_min - 1)],
                "p99": minute_counts[min(int(n_min * 0.99), n_min - 1)],
                "max": max(minute_counts),
                "avg": round(sum(minute_counts) / n_min, 1),
            }

        # ── Q5: Hourly slot usage by hour-of-day (0-23) ──
        hourly_slots = {}
        hourly_query_counts = {}
        for q in query_stats:
            if q.execution_time:
                hod = q.execution_time.hour
                hourly_slots[hod] = hourly_slots.get(hod, 0) + (q.slot_milliseconds or 0)
                hourly_query_counts[hod] = hourly_query_counts.get(hod, 0) + 1
        hourly_slot_usage = sorted(
            [{
                "hour": h,
                "query_count": hourly_query_counts.get(h, 0),
                "total_slot_seconds": round(hourly_slots.get(h, 0) / 1000, 1),
                "avg_slot_seconds_per_query": round(
                    (hourly_slots.get(h, 0) / 1000) / hourly_query_counts[h], 1
                ) if hourly_query_counts.get(h, 0) > 0 else 0,
                "avg_slots_used": round(hourly_slots.get(h, 0) / (3600 * 1000), 1),
            } for h in range(24)],
            key=lambda x: x["hour"]
        )

        # ── Q7: Write pattern breakdown by statement_type ──
        stmt_type_breakdown = {}
        for q in query_stats:
            meta = q.query_metadata if isinstance(q.query_metadata, dict) else {}
            st = (meta.get('statement_type') or 'UNKNOWN').upper()
            if st not in stmt_type_breakdown:
                stmt_type_breakdown[st] = {
                    "count": 0, "total_bytes_processed": 0,
                    "total_duration_ms": 0, "max_duration_ms": 0,
                }
            entry = stmt_type_breakdown[st]
            entry["count"] += 1
            entry["total_bytes_processed"] += (q.bytes_scanned or 0)
            q_dur = meta.get('total_elapsed_time_ms', 0) or 0
            entry["total_duration_ms"] += q_dur
            if q_dur > entry["max_duration_ms"]:
                entry["max_duration_ms"] = q_dur
        write_pattern_breakdown = sorted(
            [{
                "statement_type": st,
                "job_count": v["count"],
                "tib_processed": round(v["total_bytes_processed"] / (1024**4), 6),
                "avg_duration_sec": round((v["total_duration_ms"] / v["count"]) / 1000, 2) if v["count"] > 0 else 0,
                "max_duration_sec": round(v["max_duration_ms"] / 1000, 2),
            } for st, v in stmt_type_breakdown.items()],
            key=lambda x: x["job_count"], reverse=True
        )

        # ── Q8: User & connection patterns by hour-of-day ──
        hourly_users = {}
        for q in query_stats:
            if q.execution_time and q.user_email:
                hod = q.execution_time.hour
                if hod not in hourly_users:
                    hourly_users[hod] = {"users": set(), "queries": 0, "peak_concurrent": 0}
                hourly_users[hod]["users"].add(q.user_email)
                hourly_users[hod]["queries"] += 1
        # Compute peak concurrent per hour from minute buckets
        hourly_peak_concurrent = {}
        for q in query_stats:
            if q.execution_time:
                hod = q.execution_time.hour
                min_key = q.execution_time.strftime('%Y-%m-%d %H:%M')
                if hod not in hourly_peak_concurrent:
                    hourly_peak_concurrent[hod] = {}
                hourly_peak_concurrent[hod][min_key] = hourly_peak_concurrent[hod].get(min_key, 0) + 1
        user_patterns_by_hour = sorted(
            [{
                "hour": h,
                "distinct_users": len(hourly_users.get(h, {}).get("users", set())),
                "total_queries": hourly_users.get(h, {}).get("queries", 0),
                "peak_concurrent_in_hour": max(hourly_peak_concurrent.get(h, {}).values()) if hourly_peak_concurrent.get(h) else 0,
            } for h in range(24)],
            key=lambda x: x["hour"]
        )

        queries = []
        for q in page_stats:
            q_slot_ms = q.slot_milliseconds or 0
            # Compute per-query slot utilization using actual runtime when available
            q_runtime_ms = 0
            if q.query_metadata and isinstance(q.query_metadata, dict):
                q_runtime_ms = q.query_metadata.get('total_elapsed_time_ms', 0)
            if q_slot_ms > 0 and q_runtime_ms and q_runtime_ms > 0:
                q_slot_util = round(max(1, q_slot_ms / q_runtime_ms), 1)
                q_est_runtime = round((q_slot_ms / max(q_slot_ms / q_runtime_ms, 1)) / 1000, 2)
            elif q_slot_ms > 0:
                q_slot_util = round(q_slot_ms / 30000, 1)
                q_est_runtime = round((q_slot_ms / max(est_concurrent_slots, 1)) / 1000, 2)
            else:
                q_slot_util = 0
                q_est_runtime = 0

            queries.append({
                "job_id": q.job_id,
                "execution_time": q.execution_time.isoformat() if q.execution_time else None,
                "query_text": (q.query_text or '')[:500],
                "bytes_scanned": q.bytes_scanned or 0,
                "bytes_billed": (q.query_metadata or {}).get('bytes_billed', q.bytes_scanned or 0) if isinstance(q.query_metadata, dict) else (q.bytes_scanned or 0),
                "slot_milliseconds": q_slot_ms,
                "slot_utilization": q_slot_util,
                "est_runtime_seconds": q_est_runtime,
                "cache_hit": q.cache_hit if q.cache_hit is not None else False,
                "cache_hit_status": "Hit" if q.cache_hit is True else ("Miss" if q.cache_hit is False else "N/A"),
                "statement_type": (q.query_metadata or {}).get('statement_type', 'UNKNOWN') if isinstance(q.query_metadata, dict) else 'UNKNOWN',
                "referenced_tables": q.referenced_tables or [],
                "user_email": q.user_email or "Unknown"
            })
        
        return {
            "assessment_id": assessment_id,
            "timeframe": timeframe,
            "summary": {
                "total_query_count": total_queries,
                "active_users_count": active_users_count,
                "avg_execution_time_seconds": round(avg_execution_time_seconds, 3),
                "total_bytes_scanned": total_bytes_scanned,
                "total_bytes_billed": total_bytes_billed if total_bytes_billed > 0 else total_bytes_scanned,
                "total_slot_milliseconds": total_slot_ms,
                "cache_hit_rate": round(cache_hit_rate, 2),
                "cache_hits": cache_hits,
                "cache_misses": select_queries - cache_hits,
                "select_queries": select_queries,
                "read_queries": read_count,
                "write_queries": write_count,
                "max_concurrent_queries": max_concurrent_queries,
                "avg_concurrent_queries": avg_concurrent_queries,
                "max_slot_milliseconds": max_slot_ms,
                "min_slot_milliseconds": min_slot_ms,
                "avg_slot_ms_per_query": avg_slot_ms_per_query,
                "max_query_runtime_seconds": max_query_runtime_seconds,
                "min_query_runtime_seconds": min_query_runtime_seconds,
                "avg_query_runtime_seconds": avg_query_runtime_seconds,
                "peak_slot_utilization": peak_slot_utilization,
                "avg_slot_utilization": avg_slot_utilization,
                "p50_slot_utilization": p50_slot_utilization,
                "p90_slot_utilization": p90_slot_utilization,
                "p95_slot_utilization": p95_slot_utilization,
                "p99_slot_utilization": p99_slot_utilization
            },
            "charts": {
                "read_write_distribution": {
                    "read": read_count,
                    "write": write_count
                },
                "concurrent_queries": {
                    "hourly": hourly_data,
                    "daily": daily_data,
                    "weekly": weekly_data
                },
                "duration_distribution": duration_distribution,
                "concurrent_query_percentiles": concurrent_query_percentiles,
                "hourly_slot_usage": hourly_slot_usage,
                "write_pattern_breakdown": write_pattern_breakdown,
                "user_patterns_by_hour": user_patterns_by_hour
            },
            "queries": queries,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_filtered": total_filtered,
                "total_pages": (total_filtered + page_size - 1) // page_size
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting query insights: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
