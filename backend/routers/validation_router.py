"""
Validation Router

Handles API endpoints for post-migration data validation operations.
"""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from models.validation_schemas import (
    CreateValidationRunRequest,
    MigrationInfoResponse,
    BedrockModelResponse,
    PaginatedValidationRunsResponse,
    ValidationReportResponse,
    ValidationRunResponse,
    ValidationTableDetailResponse,
    ValidationTableResultResponse,
    DirectValidationRequest,
    DirectValidationResponse,
)
from services.validation_cache import ValidationCache
from services.validation_service import ValidationService
from shared.middleware.auth_middleware import CurrentUser, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/validations", tags=["validations"])


def get_workspace_id(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
) -> int:
    """Extract workspace ID from X-Workspace-ID header or default to 1."""
    workspace_id = request.headers.get("X-Workspace-ID")
    if workspace_id:
        return int(workspace_id)
    return 1


def _build_service(db: Session) -> ValidationService:
    """Instantiate ValidationService with its dependencies."""
    cache = ValidationCache()
    return ValidationService(db=db, cache=cache)


# ---------------------------------------------------------------------------
# Create validation run
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=ValidationRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_validation_run(
    request: CreateValidationRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Create and start a validation run as a background task."""
    try:
        service = _build_service(db)

        # Auto-fill source/target connections from migration if not provided
        source_conn_id = request.source_connection_id
        target_conn_id = request.target_connection_id
        if not source_conn_id or not target_conn_id:
            migration_info = service.get_migration_info(
                migration_id=request.migration_id, workspace_id=workspace_id
            )
            if not source_conn_id:
                source_conn_id = migration_info.get("source_connection_id")
            if not target_conn_id:
                target_conn_id = migration_info.get("target_connection_id")
        if not source_conn_id or not target_conn_id:
            raise ValueError("Could not determine source/target connections from migration")

        run = service.create_validation_run(
            workspace_id=workspace_id,
            migration_id=request.migration_id,
            source_connection_id=source_conn_id,
            target_connection_id=target_conn_id,
            tables=request.tables,
            table_configs=[tc.model_dump() for tc in request.table_configs] if request.table_configs else None,
            bedrock_model=request.bedrock_model,
            batch_size=request.batch_size,
            sampling_mode=request.sampling_mode.value if request.sampling_mode else "all",
            sample_limit=request.sample_limit,
            type_mapping_overrides=request.type_mapping_overrides,
            created_by=str(current_user.user_id),
            run_name=request.run_name,
        )
        background_tasks.add_task(
            service.run_validation_background,
            run["id"],
            workspace_id,
        )
        return ValidationRunResponse(**run)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(
            "Failed to create validation run",
            extra={"workspace_id": workspace_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request",
        )


# ---------------------------------------------------------------------------
# List validation runs
# ---------------------------------------------------------------------------


@router.get("/", response_model=PaginatedValidationRunsResponse)
async def list_validation_runs(
    page: int = 1,
    page_size: int = 20,
    migration_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    include_table_results: bool = False,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """List validation runs with pagination and optional filters."""
    try:
        service = _build_service(db)
        result = service.list_runs(
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
            migration_id=migration_id,
            status=status_filter,
            include_table_results=include_table_results,
        )
        return PaginatedValidationRunsResponse(
            runs=[ValidationRunResponse(**r) for r in result["runs"]],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to list validation runs",
            extra={"workspace_id": workspace_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request",
        )


# ---------------------------------------------------------------------------
# List Bedrock models (MUST be before /{run_id} to avoid path conflict)
# ---------------------------------------------------------------------------


@router.get("/bedrock-models", response_model=list[BedrockModelResponse])
async def list_bedrock_models(
    region: str = "us-east-1",
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """List available Bedrock foundation models for AI analysis."""
    try:
        from services.bedrock_client import BedrockClient
        client = BedrockClient()
        models = client.list_models(region=region)
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


# ---------------------------------------------------------------------------
# Get migration info for validation form auto-fill
# ---------------------------------------------------------------------------


@router.get("/migration/{migration_id}/info", response_model=MigrationInfoResponse)
async def get_migration_info(
    migration_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Get migration details for auto-filling the validation form."""
    try:
        service = _build_service(db)
        info = service.get_migration_info(
            migration_id=migration_id, workspace_id=workspace_id
        )
        if info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Migration {migration_id} not found",
            )
        return MigrationInfoResponse(**info)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to get migration info",
            extra={"workspace_id": workspace_id, "migration_id": migration_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request",
        )

# ---------------------------------------------------------------------------
# Get columns for a migration table
# ---------------------------------------------------------------------------


@router.get("/migration/{migration_id}/tables/{table_name}/columns")
async def get_migration_table_columns(
    migration_id: int,
    table_name: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Get source and target columns for a selected migration table."""
    try:
        service = _build_service(db)

        result = service.get_migration_table_columns(
            migration_id=migration_id,
            table_name=table_name,
            workspace_id=workspace_id,
        )

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table '{table_name}' not found for migration {migration_id}",
            )

        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to get migration table columns",
            extra={
                "workspace_id": workspace_id,
                "migration_id": migration_id,
                "table_name": table_name,
                "error": str(exc),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving table columns",
        )
# ---------------------------------------------------------------------------
# Get validation run details
# ---------------------------------------------------------------------------


@router.get("/{run_id}", response_model=ValidationRunResponse)
async def get_validation_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Retrieve a single validation run by ID."""
    try:
        service = _build_service(db)
        run = service.get_run(run_id=run_id, workspace_id=workspace_id)
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Validation run {run_id} not found",
            )
        return ValidationRunResponse(**run)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to get validation run",
            extra={"workspace_id": workspace_id, "run_id": run_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request",
        )


# ---------------------------------------------------------------------------
# Get table results for a run
# ---------------------------------------------------------------------------


@router.get("/{run_id}/tables", response_model=list[ValidationTableResultResponse])
async def get_validation_table_results(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """List all table results for a validation run."""
    try:
        service = _build_service(db)
        results = service.get_table_results(run_id=run_id, workspace_id=workspace_id)
        if results is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Validation run {run_id} not found",
            )
        return [ValidationTableResultResponse(**r) for r in results]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to get table results",
            extra={"workspace_id": workspace_id, "run_id": run_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request",
        )


# ---------------------------------------------------------------------------
# Get table detail (with JSONB fields)
# ---------------------------------------------------------------------------


@router.get("/{run_id}/tables/{table_name}", response_model=ValidationTableDetailResponse)
async def get_validation_table_detail(
    run_id: int,
    table_name: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Retrieve detailed table result including JSONB fields."""
    try:
        service = _build_service(db)
        detail = service.get_table_detail(
            run_id=run_id, table_name=table_name, workspace_id=workspace_id,
        )
        if detail is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table '{table_name}' not found for validation run {run_id}",
            )
        return ValidationTableDetailResponse(**detail)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to get table detail",
            extra={
                "workspace_id": workspace_id,
                "run_id": run_id,
                "table_name": table_name,
                "error": str(exc),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request",
        )


# ---------------------------------------------------------------------------
# Get validation report
# ---------------------------------------------------------------------------


@router.get("/{run_id}/report", response_model=ValidationReportResponse)
async def get_validation_report(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Retrieve the full validation report for a run."""
    try:
        service = _build_service(db)
        report = service.get_report(run_id=run_id, workspace_id=workspace_id)
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Validation run {run_id} not found",
            )
        return report
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to get validation report",
            extra={"workspace_id": workspace_id, "run_id": run_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request",
        )


# ---------------------------------------------------------------------------
# Delete validation run
# ---------------------------------------------------------------------------


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_validation_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Delete a validation run and all associated table results."""
    try:
        service = _build_service(db)
        deleted = service.delete_run(run_id=run_id, workspace_id=workspace_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Validation run {run_id} not found",
            )
        return None
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to delete validation run",
            extra={"workspace_id": workspace_id, "run_id": run_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request",
        )


# ---------------------------------------------------------------------------
# Direct validation test (connection-to-connection, no migration required)
# ---------------------------------------------------------------------------


@router.get("/connections/{connection_id}/tables")
async def list_connection_tables(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """List user tables (schema + table) for a connection, for the Quick Test picker."""
    try:
        service = _build_service(db)
        return service.list_connection_tables(connection_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(
            "Failed to list connection tables",
            extra={"connection_id": connection_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tables: {exc}",
        )


@router.get("/connections/{connection_id}/columns")
async def list_connection_columns(
    connection_id: int,
    schema: str,
    table: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """List columns for a table on a connection, for the Quick Test column pickers."""
    try:
        service = _build_service(db)
        return service.list_connection_columns(connection_id, schema, table)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(
            "Failed to list connection columns",
            extra={"connection_id": connection_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list columns: {exc}",
        )


@router.post("/direct-test", response_model=DirectValidationResponse)
async def run_direct_validation_test(
    request: DirectValidationRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id),
):
    """Run validation checks directly between two connections (no migration).

    Works across any supported engine pair (e.g. SQL Server -> Redshift).
    Runs synchronously and returns results inline.
    """
    try:
        service = _build_service(db)
        result = service.run_direct_validation(
            source_connection_id=request.source_connection_id,
            target_connection_id=request.target_connection_id,
            source_schema=request.source_schema,
            target_schema=request.target_schema,
            table_name=request.table_name,
            checks={
                "row_count": request.row_count,
                "ddl_check": request.ddl_check,
                "null_check": request.null_check,
                "null_column": request.null_column,
                "duplicate_check": request.duplicate_check,
                "duplicate_match_key": request.duplicate_match_key,
                "sum_check": request.sum_check,
                "sum_column": request.sum_column,
                "average_check": request.average_check,
                "average_column": request.average_column,
                "specific_row_check": request.specific_row_check,
                "specific_row_match_key": request.specific_row_match_key,
                "specific_row_start": request.specific_row_start,
                "specific_row_end": request.specific_row_end,
            },
        )
        return DirectValidationResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error(
            "Direct validation test failed",
            extra={"workspace_id": workspace_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Direct validation failed: {exc}",
        )
