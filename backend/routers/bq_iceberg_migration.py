"""
BigQuery to Iceberg Migration API Router

REST API endpoints for managing BQ to Iceberg migrations.
Supports CRUD operations, lifecycle management, structure review/approval,
cost analysis, and validation endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
import logging
import re
import io

from database import get_db
from shared.middleware.auth_middleware import get_current_user, get_workspace_id
from models.migration_bq_iceberg import MigrationBQIceberg
from models.iceberg_table_validation import IcebergTableValidation
from models.bq_redshift_migration import MigrationLog
from services.bq_iceberg_migration.validators import (
    validate_compaction_strategy,
    validate_maintenance_config,
    validate_s3_tables_parallelism,
)

logger = logging.getLogger(__name__)


def _setup_thread_aws_env():
    """Ensure AWS_PROFILE and region are propagated into background thread environment."""
    import os as _os
    from dotenv import load_dotenv as _ld
    _ld(override=False)
    _profile = _os.getenv("AWS_PROFILE")
    if _profile:
        _os.environ["AWS_PROFILE"] = _profile
    _os.environ.setdefault("AWS_DEFAULT_REGION", _os.getenv("AWS_REGION", "us-east-1"))


router = APIRouter(prefix="/api/migrations/bq-iceberg", tags=["BQ-Iceberg Migrations"])


# Connection test router (separate prefix)
connection_test_router = APIRouter(prefix="/api/connections", tags=["Connection Tests"])


# ============================================================================
# Pydantic Request/Response Schemas
# ============================================================================

class MaintenanceConfigRequest(BaseModel):
    """Request schema for S3 Tables maintenance configuration."""
    target_file_size_mb: int = Field(512, ge=64, le=512)
    min_snapshots_to_keep: int = Field(30, gt=0)
    max_snapshot_age_hours: int = Field(720, gt=0)


class CompactionConfigRequest(BaseModel):
    """Per-table compaction strategy configuration."""
    strategy: str = Field("binpack", pattern="^(binpack|sort|z-order)$")
    sort_columns: list[str] = Field(default_factory=list)


class CreateIcebergMigrationRequest(BaseModel):
    """Request schema for creating a new BQ-to-Iceberg migration."""
    migration_name: str = Field(..., min_length=1, max_length=255)
    pathway: str = Field(..., pattern="^[ABC]$")

    # Source Configuration
    source_connection_id: Optional[int] = None
    source_project_id: Optional[str] = None
    source_dataset: Optional[str] = None
    source_tables: Optional[List[str]] = None

    # Target Configuration
    destination_type: str = Field(..., pattern="^(iceberg_s3|iceberg_s3_tables)$")
    target_connection_id: Optional[int] = None
    s3_bucket: Optional[str] = Field(None, max_length=63)
    s3_path_prefix: Optional[str] = Field(None, max_length=512)
    table_bucket_arn: Optional[str] = Field(None, max_length=500)
    s3_tables_namespace: Optional[str] = Field(None, max_length=255)
    aws_region: str = Field(..., min_length=1, max_length=50)
    glue_database_name: str = Field(..., min_length=1, max_length=255)
    dataset_to_db_mapping: Optional[Dict[str, str]] = None

    # AWS Credentials
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_role_arn: Optional[str] = Field(None, max_length=500)

    # Intermediate Storage
    gcs_bucket: Optional[str] = None
    gcs_path: Optional[str] = None
    gcs_region: Optional[str] = None
    export_format: Optional[str] = "PARQUET"
    compression: Optional[str] = "ZSTD"
    service_account_json: Optional[str] = None

    # Load Configuration
    load_type: Optional[str] = Field("full", pattern="^(full|incremental)$")
    table_load_configs: Optional[Dict[str, Any]] = None
    parallelism: Optional[int] = Field(4, ge=1, le=16)
    enable_load_stage_verification: Optional[bool] = False

    # S3 Tables Maintenance Configuration (only for iceberg_s3_tables)
    maintenance_config: Optional[MaintenanceConfigRequest] = None

    # Scheduling
    schedule_type: Optional[str] = None
    cron_expression: Optional[str] = None

    @field_validator('glue_database_name')
    @classmethod
    def validate_glue_db_name(cls, v: str) -> str:
        if not re.match(r'^[a-z0-9_]+$', v):
            raise ValueError('Glue database name must match pattern [a-z0-9_]+')
        return v

    @field_validator('s3_bucket')
    @classmethod
    def validate_s3_bucket(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 0:
            if not re.match(r'^[a-z0-9][a-z0-9.\-]{1,61}[a-z0-9]$', v):
                raise ValueError('Invalid S3 bucket name format')
        return v


class UpdateIcebergMigrationRequest(BaseModel):
    """Request schema for updating an existing BQ-to-Iceberg migration."""
    migration_name: Optional[str] = Field(None, min_length=1, max_length=255)
    pathway: Optional[str] = Field(None, pattern="^[ABC]$")

    # Source Configuration
    source_connection_id: Optional[int] = None
    source_project_id: Optional[str] = None
    source_dataset: Optional[str] = None
    source_tables: Optional[List[str]] = None

    # Target Configuration
    destination_type: Optional[str] = Field(None, pattern="^(iceberg_s3|iceberg_s3_tables)$")
    target_connection_id: Optional[int] = None
    s3_bucket: Optional[str] = Field(None, max_length=63)
    s3_path_prefix: Optional[str] = Field(None, max_length=512)
    table_bucket_arn: Optional[str] = Field(None, max_length=500)
    s3_tables_namespace: Optional[str] = Field(None, max_length=255)
    aws_region: Optional[str] = Field(None, max_length=50)
    glue_database_name: Optional[str] = Field(None, max_length=255)
    dataset_to_db_mapping: Optional[Dict[str, str]] = None

    # AWS Credentials
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_role_arn: Optional[str] = Field(None, max_length=500)

    # Intermediate Storage
    gcs_bucket: Optional[str] = None
    gcs_path: Optional[str] = None
    gcs_region: Optional[str] = None
    export_format: Optional[str] = None
    compression: Optional[str] = None
    service_account_json: Optional[str] = None

    # Load Configuration
    load_type: Optional[str] = Field(None, pattern="^(full|incremental)$")
    table_load_configs: Optional[Dict[str, Any]] = None
    parallelism: Optional[int] = Field(None, ge=1, le=16)
    enable_load_stage_verification: Optional[bool] = None

    # Scheduling
    schedule_type: Optional[str] = None
    cron_expression: Optional[str] = None

    @field_validator('glue_database_name')
    @classmethod
    def validate_glue_db_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r'^[a-z0-9_]+$', v):
            raise ValueError('Glue database name must match pattern [a-z0-9_]+')
        return v


class IcebergMigrationListResponse(BaseModel):
    """Response schema for migration list items."""
    id: int
    workspace_id: int
    migration_name: str
    pathway: str
    destination_type: str
    status: str
    current_stage: Optional[str] = None
    progress_percentage: int = 0
    aws_region: str
    glue_database_name: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class IcebergMigrationDetailResponse(BaseModel):
    """Response schema for migration detail."""
    id: int
    workspace_id: int
    migration_name: str
    pathway: str
    source: Dict[str, Any]
    target: Dict[str, Any]
    credentials: Dict[str, Any]
    storage: Dict[str, Any]
    load_config: Dict[str, Any]
    state: Dict[str, Any]
    structure_review: Dict[str, Any]
    schedule: Dict[str, Any]
    metrics: Dict[str, Any]
    created_by: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class MigrationStatusResponse(BaseModel):
    """Response schema for migration status."""
    migration_id: int
    status: str
    current_stage: Optional[str] = None
    progress_percentage: int = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: Optional[int] = None
    total_rows_source: Optional[int] = None
    total_rows_target: Optional[int] = None
    total_bytes_transferred: Optional[int] = None


class ApproveStructureRequest(BaseModel):
    """Request schema for approving structure with optional overrides."""
    overrides: Optional[Dict[str, Any]] = None
    dataset_to_db_mapping: Optional[Dict[str, str]] = None
    excluded_tables: Optional[List[str]] = None
    custom_properties: Optional[Dict[str, Dict[str, str]]] = None
    table_compaction_configs: Optional[Dict[str, CompactionConfigRequest]] = None


class RequestChangesRequest(BaseModel):
    """Request schema for submitting structure overrides."""
    table_overrides: Dict[str, Any] = Field(
        ..., description="Per-table overrides: partition spec, sort order, exclusions"
    )
    dataset_to_db_mapping: Optional[Dict[str, str]] = None


class CustomStructureRequest(BaseModel):
    """Request schema for defining custom table structure."""
    table_name: str = Field(..., min_length=1, max_length=255)
    columns: List[Dict[str, Any]] = Field(
        ..., description="Column definitions: name, iceberg_type, nullable"
    )
    partition_spec: Optional[Dict[str, Any]] = None
    sort_order: Optional[List[Dict[str, Any]]] = None
    table_properties: Optional[Dict[str, str]] = None


class CostRecalculateRequest(BaseModel):
    """Request schema for recalculating cost analysis with new growth rate."""
    growth_rate_monthly: float = Field(..., ge=0.0, le=1.0)


class TestIcebergConnectionRequest(BaseModel):
    """Request schema for testing an Iceberg connection."""
    destination_type: str = Field(..., pattern="^(iceberg_s3|iceberg_s3_tables)$")
    s3_bucket: Optional[str] = None
    s3_path_prefix: Optional[str] = None
    table_bucket_arn: Optional[str] = None
    aws_region: str = Field(..., min_length=1)
    glue_database_name: str = Field(..., min_length=1)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_role_arn: Optional[str] = None


class ValidationResultsResponse(BaseModel):
    """Response schema for validation results."""
    migration_id: int
    total_tables: int
    passed: int
    failed: int
    skipped: int
    tables: List[Dict[str, Any]]


# ============================================================================
# Helper Functions
# ============================================================================

def _get_migration_or_404(
    db: Session, migration_id: int, workspace_id: int
) -> MigrationBQIceberg:
    """Fetch migration by ID with workspace isolation check."""
    migration = db.query(MigrationBQIceberg).filter(
        MigrationBQIceberg.id == migration_id,
        MigrationBQIceberg.workspace_id == workspace_id
    ).first()

    if not migration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Migration {migration_id} not found"
        )
    return migration


def _encrypt_secret(value: str) -> str:
    """Encrypt a secret value using KMS. Falls back to plaintext in dev."""
    try:
        from services.unified_kms_service import get_unified_kms_service
        kms = get_unified_kms_service()
        return kms.encrypt_credential(
            plaintext=value,
            credential_type='aws_secret_key',
            resource_type='migration'
        )
    except Exception as e:
        logger.warning(f"KMS encryption failed, storing unencrypted (DEV ONLY): {e}")
        return value


def _format_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Format datetime to ISO string with Z suffix."""
    return dt.isoformat() + 'Z' if dt else None


# ============================================================================
# Task 11.1: CRUD API Endpoints
# ============================================================================

@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_migration(
    request: Request,
    req: CreateIcebergMigrationRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """
    Create a new BigQuery to Iceberg migration.

    Supports two destination types:
    - iceberg_s3: Standard Apache Iceberg on S3
    - iceberg_s3_tables: AWS S3 Tables (managed Iceberg)
    """
    try:
        # Check for duplicate name within workspace
        existing = db.query(MigrationBQIceberg).filter(
            MigrationBQIceberg.workspace_id == workspace_id,
            MigrationBQIceberg.migration_name == req.migration_name
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Migration with name '{req.migration_name}' already exists in this workspace"
            )

        # Validate parallelism for S3 Tables destinations (max 8)
        parallelism_warning = None
        if req.destination_type == "iceberg_s3_tables" and req.parallelism is not None:
            is_valid, error_msg = validate_s3_tables_parallelism(req.parallelism)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "S3 Tables API has lower concurrency limits than standard S3. "
                        "Parallelism above 8 may cause throttling errors and slower "
                        "overall throughput."
                    )
                )
            # Warn if parallelism is at the upper boundary (5-8 range)
            if req.parallelism > 4:
                parallelism_warning = (
                    "S3 Tables API has lower concurrency limits than standard S3. "
                    "Parallelism above 8 may cause throttling errors and slower "
                    "overall throughput."
                )

        # Validate maintenance config for S3 Tables destinations
        if req.maintenance_config is not None:
            if req.destination_type != "iceberg_s3_tables":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Maintenance configuration is only supported for iceberg_s3_tables destinations."
                )
            is_valid, error_msg = validate_maintenance_config(
                req.maintenance_config.target_file_size_mb,
                req.maintenance_config.min_snapshots_to_keep,
                req.maintenance_config.max_snapshot_age_hours,
            )
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid maintenance configuration: {error_msg}"
                )

        # Encrypt secrets if provided
        aws_secret_encrypted = None
        if req.aws_secret_access_key:
            aws_secret_encrypted = _encrypt_secret(req.aws_secret_access_key)

        sa_json_encrypted = None
        if req.service_account_json:
            sa_json_encrypted = _encrypt_secret(req.service_account_json)

        # Create migration record
        migration = MigrationBQIceberg(
            workspace_id=workspace_id,
            migration_name=req.migration_name,
            pathway=req.pathway,
            source_connection_id=req.source_connection_id,
            source_project_id=req.source_project_id,
            source_dataset=req.source_dataset,
            source_tables=req.source_tables,
            target_connection_id=req.target_connection_id,
            destination_type=req.destination_type,
            s3_bucket=req.s3_bucket,
            s3_path_prefix=req.s3_path_prefix,
            table_bucket_arn=req.table_bucket_arn,
            s3_tables_namespace=req.s3_tables_namespace,
            aws_region=req.aws_region,
            glue_database_name=req.glue_database_name,
            dataset_to_db_mapping=req.dataset_to_db_mapping,
            aws_access_key_id=req.aws_access_key_id,
            aws_secret_access_key_encrypted=aws_secret_encrypted,
            aws_role_arn=req.aws_role_arn,
            gcs_bucket=req.gcs_bucket,
            gcs_path=req.gcs_path,
            gcs_region=req.gcs_region,
            export_format=req.export_format or 'PARQUET',
            compression=req.compression or 'ZSTD',
            service_account_json_encrypted=sa_json_encrypted,
            load_type=req.load_type or 'full',
            table_load_configs=req.table_load_configs,
            parallelism=req.parallelism or 4,
            enable_load_stage_verification=req.enable_load_stage_verification or False,
            status='pending',
            schedule_type=req.schedule_type,
            cron_expression=req.cron_expression,
            created_by=current_user.user_id,
        )

        # Persist maintenance config in checkpoint_data for the loader service
        if req.maintenance_config is not None:
            checkpoint = migration.checkpoint_data or {}
            checkpoint['maintenance_config'] = {
                "target_file_size_mb": req.maintenance_config.target_file_size_mb,
                "min_snapshots_to_keep": req.maintenance_config.min_snapshots_to_keep,
                "max_snapshot_age_hours": req.maintenance_config.max_snapshot_age_hours,
            }
            migration.checkpoint_data = checkpoint

        db.add(migration)
        db.commit()
        db.refresh(migration)

        logger.info(
            f"Created Iceberg migration {migration.id} "
            f"(workspace={workspace_id}, name='{req.migration_name}')"
        )

        response = migration.to_dict()
        if parallelism_warning:
            response["warnings"] = [parallelism_warning]
        return response

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create Iceberg migration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create migration: {str(e)}"
        )


@router.get("/glue-databases")
async def list_glue_databases(
    region: str = Query("us-east-1"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """List existing Glue Data Catalog databases available in the given region."""
    try:
        import os as _os
        import boto3 as _boto3
        _os.environ["AWS_DEFAULT_REGION"] = region
        glue = _boto3.client("glue", region_name=region)
        databases = []
        paginator = glue.get_paginator("get_databases")
        for page in paginator.paginate():
            for db_item in page.get("DatabaseList", []):
                databases.append({
                    "name": db_item["Name"],
                    "description": db_item.get("Description", ""),
                    "location": db_item.get("LocationUri", ""),
                })
        return {"databases": databases, "region": region}
    except Exception as e:
        logger.warning(f"Could not list Glue databases: {e}")
        return {"databases": [], "region": region, "error": str(e)}


@router.get("/list")
async def list_migrations(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    destination_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """List all Iceberg migrations for the current workspace."""
    try:
        query = db.query(MigrationBQIceberg).filter(
            MigrationBQIceberg.workspace_id == workspace_id
        )

        if status_filter:
            query = query.filter(MigrationBQIceberg.status == status_filter)
        if destination_type:
            query = query.filter(MigrationBQIceberg.destination_type == destination_type)

        total = query.count()
        migrations = query.order_by(
            MigrationBQIceberg.created_at.desc()
        ).limit(limit).offset(offset).all()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "migrations": [
                {
                    "id": m.id,
                    "workspace_id": m.workspace_id,
                    "migration_name": m.migration_name,
                    "pathway": m.pathway,
                    "destination_type": m.destination_type,
                    "status": m.status,
                    "current_stage": m.current_stage,
                    "progress_percentage": m.progress_percentage or 0,
                    "aws_region": m.aws_region,
                    "glue_database_name": m.glue_database_name,
                    "created_at": _format_datetime(m.created_at),
                    "updated_at": _format_datetime(m.updated_at),
                }
                for m in migrations
            ]
        }

    except Exception as e:
        logger.error(f"Failed to list Iceberg migrations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list migrations: {str(e)}"
        )


@router.get("/{migration_id}")
async def get_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Get detailed information about a specific Iceberg migration."""
    migration = _get_migration_or_404(db, migration_id, workspace_id)
    return migration.to_dict()


@router.put("/{migration_id}/update")
async def update_migration(
    request: Request,
    migration_id: int,
    req: UpdateIcebergMigrationRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Update an existing Iceberg migration configuration."""
    migration = _get_migration_or_404(db, migration_id, workspace_id)

    if migration.status == 'running':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a running migration. Pause or cancel it first."
        )

    try:
        update_data = req.model_dump(exclude_unset=True)

        # Validate parallelism for S3 Tables destinations (max 8)
        parallelism_warning = None
        # Determine effective destination type (from request or existing migration)
        effective_destination_type = update_data.get(
            'destination_type', migration.destination_type
        )
        if 'parallelism' in update_data and update_data['parallelism'] is not None:
            if effective_destination_type == "iceberg_s3_tables":
                is_valid, error_msg = validate_s3_tables_parallelism(
                    update_data['parallelism']
                )
                if not is_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            "S3 Tables API has lower concurrency limits than standard S3. "
                            "Parallelism above 8 may cause throttling errors and slower "
                            "overall throughput."
                        )
                    )
                if update_data['parallelism'] > 4:
                    parallelism_warning = (
                        "S3 Tables API has lower concurrency limits than standard S3. "
                        "Parallelism above 8 may cause throttling errors and slower "
                        "overall throughput."
                    )

        # Handle secret encryption
        if 'aws_secret_access_key' in update_data:
            secret = update_data.pop('aws_secret_access_key')
            if secret:
                migration.aws_secret_access_key_encrypted = _encrypt_secret(secret)

        if 'service_account_json' in update_data:
            sa_json = update_data.pop('service_account_json')
            if sa_json:
                migration.service_account_json_encrypted = _encrypt_secret(sa_json)

        # Apply remaining updates
        for field, value in update_data.items():
            if hasattr(migration, field) and value is not None:
                setattr(migration, field, value)

        migration.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(migration)

        logger.info(f"Updated Iceberg migration {migration_id}")
        response = migration.to_dict()
        if parallelism_warning:
            response["warnings"] = [parallelism_warning]
        return response

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update Iceberg migration {migration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update migration: {str(e)}"
        )


@router.delete("/{migration_id}")
async def delete_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Delete an Iceberg migration."""
    migration = _get_migration_or_404(db, migration_id, workspace_id)

    if migration.status == 'running':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a running migration. Cancel it first."
        )

    try:
        # Delete associated validation results (table may not exist on all environments)
        try:
            db.query(IcebergTableValidation).filter(
                IcebergTableValidation.migration_id == migration_id
            ).delete()
        except Exception:
            db.rollback()
            # Re-fetch migration since rollback cleared it
            migration = _get_migration_or_404(db, migration_id, workspace_id)

        # Delete associated logs (ignore if table missing)
        try:
            db.query(MigrationLog).filter(
                MigrationLog.migration_id == migration_id
            ).delete()
        except Exception:
            db.rollback()
            migration = _get_migration_or_404(db, migration_id, workspace_id)

        db.delete(migration)
        db.commit()

        logger.info(f"Deleted Iceberg migration {migration_id}")
        return {"message": "Migration deleted successfully", "migration_id": migration_id}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete Iceberg migration {migration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete migration: {str(e)}"
        )


# ============================================================================
# Task 11.2: Lifecycle API Endpoints
# ============================================================================

@router.post("/{migration_id}/start")
async def start_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Start an Iceberg migration (runs in background)."""
    migration = _get_migration_or_404(db, migration_id, workspace_id)

    if migration.status == 'running':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Migration is already running"
        )

    if migration.status not in ('pending', 'approved', 'ready', 'failed'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Migration cannot be started from status '{migration.status}'"
        )

    try:
        # If retrying from failed state, clear only the failed stage checkpoint so
        # completed stages (e.g. export) are not repeated.
        if migration.status == 'failed':
            checkpoint = dict(getattr(migration, 'checkpoint_data', None) or {})
            # Remove transfer/report completion markers so those stages re-run
            for key in ('transfer_completed_at', 's3_files_by_table',
                        'structure_report', 'cost_report', 'assessment_tables_report'):
                checkpoint.pop(key, None)
            migration.checkpoint_data = checkpoint
            from sqlalchemy.orm.attributes import flag_modified as _fm_retry
            _fm_retry(migration, 'checkpoint_data')
            migration.end_time = None
            migration.duration_seconds = None
            migration.progress_percentage = 0
            logger.info(
                f"Retrying failed migration {migration_id} — export checkpoint preserved, "
                "transfer stage will re-run"
            )

        migration.status = 'running'
        migration.start_time = datetime.utcnow()
        migration.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Started Iceberg migration {migration_id}")

        # Capture values for background thread before db session closes
        migration_id_val = migration_id
        workspace_id_val = workspace_id

        # Spawn background thread to run the orchestration
        import threading
        from database import db_instance

        def run_migration_background(mid: int, wid: int):
            bg_db = db_instance.SessionLocal()
            try:
                _setup_thread_aws_env()
                from models.migration_bq_iceberg import MigrationBQIceberg
                from services.bq_iceberg_migration.orchestrator import IcebergMigrationOrchestrator
                from services.bq_iceberg_migration.structure_report import StructureReportGenerator
                from services.bq_iceberg_migration.cost_engine import CostAnalysisEngine
                from services.bq_iceberg_migration.schema_evolution import SchemaEvolutionService
                from services.bq_iceberg_migration.validation_service import IcebergValidationService
                from services.bq_iceberg_migration.athena_verifier import AthenaVerifier
                from services.bq_iceberg_migration.iceberg_loader import ParallelIcebergLoader
                from services.bq_iceberg_migration.credential_provider import AWSCredentialProvider
                from services.bq_iceberg_migration.type_mapper import BQToIcebergTypeMapper
                from services.bq_iceberg_migration.partition_mapper import PartitionSpecMapper
                from services.bq_iceberg_migration.dedup_guard import DeduplicationGuard
                import asyncio
                import boto3

                mig = bg_db.query(MigrationBQIceberg).filter_by(id=mid).first()
                if not mig:
                    logger.error(f"Migration {mid} not found in background thread")
                    return

                # Expire cached state so we read the latest from DB
                bg_db.expire(mig)
                bg_db.refresh(mig)
                logger.info(f"[BG] Starting Iceberg migration {mid} orchestration, status={mig.status}")

                aws_region = mig.aws_region or "us-east-1"

                # Build a boto3 Athena client from the migration's AWS region.
                # AthenaVerifier.__init__ requires (athena_client, workgroup, output_location).
                athena_client = boto3.client("athena", region_name=aws_region)
                athena_workgroup = getattr(mig, "athena_workgroup", "primary") or "primary"
                athena_output = getattr(mig, "athena_output_location", None)
                athena_verifier = AthenaVerifier(
                    athena_client=athena_client,
                    workgroup=athena_workgroup,
                    output_location=athena_output,
                )

                # Build the credential provider for catalog/loader access.
                # AWSCredentialProvider.__init__ requires (kms_service, sts_client).
                try:
                    from services.unified_kms_service import get_unified_kms_service
                    kms_service = get_unified_kms_service()
                except Exception as _kms_err:
                    logger.warning(f"[BG] KMS service unavailable, using None: {_kms_err}")
                    kms_service = None

                sts_client = boto3.client("sts", region_name=aws_region)
                credential_provider = AWSCredentialProvider(
                    kms_service=kms_service,
                    sts_client=sts_client,
                )

                # Build a PyIceberg Glue catalog for the loader.
                # The catalog is built from the migration's Glue database and S3 settings.
                try:
                    import os as _os
                    _os.environ["AWS_DEFAULT_REGION"] = aws_region
                    # Only set static key/secret if explicitly provided — never overwrite
                    # with empty strings, as that breaks SSO / AWS_PROFILE credential chain.
                    _key = _os.getenv("AWS_ACCESS_KEY_ID", "")
                    _secret = _os.getenv("AWS_SECRET_ACCESS_KEY", "")
                    if _key:
                        _os.environ["AWS_ACCESS_KEY_ID"] = _key
                    if _secret:
                        _os.environ["AWS_SECRET_ACCESS_KEY"] = _secret
                    from pyiceberg.catalog.glue import GlueCatalog
                    # Pass warehouse (S3 location) and region so PyIceberg knows where to write metadata
                    _s3_bucket = getattr(mig, "s3_bucket", None) or ""
                    _s3_prefix = getattr(mig, "s3_path_prefix", "iceberg/") or "iceberg/"
                    _warehouse = f"s3://{_s3_bucket}/{_s3_prefix.rstrip('/')}" if _s3_bucket else None
                    _catalog_props = {"region_name": aws_region}
                    if _warehouse:
                        _catalog_props["warehouse"] = _warehouse
                    glue_catalog = GlueCatalog(name="glue", **_catalog_props)
                    logger.info(f"[BG] GlueCatalog initialized, warehouse={_warehouse}")
                except Exception as _catalog_err:
                    logger.warning(
                        f"[BG] Could not build GlueCatalog, using None: {_catalog_err}"
                    )
                    glue_catalog = None
                type_mapper = BQToIcebergTypeMapper()
                partition_mapper = PartitionSpecMapper()
                dedup_guard = DeduplicationGuard()
                loader = ParallelIcebergLoader(
                    catalog=glue_catalog,
                    credential_provider=credential_provider,
                    type_mapper=type_mapper,
                    partition_mapper=partition_mapper,
                    dedup_guard=dedup_guard,
                    parallelism=getattr(mig, 'parallelism', 4),
                )

                # No-arg constructors — these are correct as-is.
                structure_gen = StructureReportGenerator()
                cost_engine = CostAnalysisEngine()
                # SchemaEvolutionService.__init__ accepts optional type_mapper.
                schema_evolution = SchemaEvolutionService(type_mapper=type_mapper)
                validation_svc = IcebergValidationService()

                orchestrator = IcebergMigrationOrchestrator(
                    loader=loader,
                    structure_report_generator=structure_gen,
                    cost_engine=cost_engine,
                    schema_evolution_service=schema_evolution,
                    validation_service=validation_svc,
                    athena_verifier=athena_verifier,
                )

                # Run async execute in a new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    success = loop.run_until_complete(
                        orchestrator.execute_iceberg_migration(mig)
                    )
                    bg_db.commit()
                    logger.info(f"[BG] Migration {mid} orchestration finished, success={success}")
                finally:
                    loop.close()

            except Exception as e:
                logger.error(f"[BG] Migration {mid} background thread failed: {e}", exc_info=True)
                try:
                    from models.migration_bq_iceberg import MigrationBQIceberg
                    mig = bg_db.query(MigrationBQIceberg).filter_by(id=mid).first()
                    if mig and mig.status == 'running':
                        mig.status = 'failed'
                        mig.updated_at = datetime.utcnow()
                        bg_db.commit()
                except Exception:
                    pass
            finally:
                bg_db.close()

        thread = threading.Thread(
            target=run_migration_background,
            args=(migration_id_val, workspace_id_val),
            daemon=True,
            name=f"iceberg-migration-{migration_id_val}"
        )
        thread.start()
        logger.info(f"Background thread started for Iceberg migration {migration_id_val}")

        return {
            "message": "Migration started successfully",
            "migration_id": migration_id,
            "status": "running"
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to start Iceberg migration {migration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start migration: {str(e)}"
        )


@router.post("/{migration_id}/pause")
async def pause_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Pause a running Iceberg migration."""
    migration = _get_migration_or_404(db, migration_id, workspace_id)

    if migration.status != 'running':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Migration cannot be paused (current status: {migration.status})"
        )

    try:
        migration.status = 'paused'
        migration.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Paused Iceberg migration {migration_id}")
        return {"message": "Migration paused successfully", "migration_id": migration_id}

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to pause Iceberg migration {migration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause migration: {str(e)}"
        )


@router.post("/{migration_id}/resume")
async def resume_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Resume a paused or failed Iceberg migration with checkpoint."""
    migration = _get_migration_or_404(db, migration_id, workspace_id)

    if migration.status not in ('paused', 'failed'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Migration cannot be resumed (current status: {migration.status})"
        )

    try:
        migration.status = 'running'
        migration.updated_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"Resumed Iceberg migration {migration_id} "
            f"(checkpoint: {migration.resume_point})"
        )
        return {
            "message": "Migration resumed successfully",
            "migration_id": migration_id,
            "status": "running",
            "resume_point": migration.resume_point
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to resume Iceberg migration {migration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume migration: {str(e)}"
        )


@router.post("/{migration_id}/cancel")
async def cancel_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Cancel an Iceberg migration, preserving all configuration."""
    migration = _get_migration_or_404(db, migration_id, workspace_id)

    if migration.status in ('completed', 'cancelled'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Migration cannot be cancelled (current status: {migration.status})"
        )

    try:
        migration.status = 'cancelled'
        migration.end_time = datetime.utcnow()
        migration.updated_at = datetime.utcnow()
        # Preserve all config — connections, source/target settings, assessment data
        db.commit()

        logger.info(f"Cancelled Iceberg migration {migration_id} (config preserved)")
        return {"message": "Migration cancelled successfully", "migration_id": migration_id}

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to cancel Iceberg migration {migration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel migration: {str(e)}"
        )


@router.post("/{migration_id}/retry")
async def retry_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Retry a failed Iceberg migration from the last failed stage.
    
    Unlike /restart (which resets everything), /retry preserves completed stage
    checkpoints so that e.g. a completed BigQuery export is not repeated.
    The transfer stage and all subsequent stages are reset so they re-run cleanly.
    """
    migration = _get_migration_or_404(db, migration_id, workspace_id)

    if migration.status == 'running':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Migration is already running"
        )

    if migration.status != 'failed':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only failed migrations can be retried (current status: '{migration.status}'). "
                   "Use /start for pending/approved, or /restart to reset from scratch."
        )

    try:
        checkpoint = dict(getattr(migration, 'checkpoint_data', None) or {})

        # Preserve export checkpoint, clear everything from transfer onwards
        for key in (
            'transfer_completed_at',
            's3_files_by_table',
            'structure_report',
            'cost_report',
            'assessment_tables_report',
        ):
            checkpoint.pop(key, None)

        migration.checkpoint_data = checkpoint
        from sqlalchemy.orm.attributes import flag_modified as _fm_r
        _fm_r(migration, 'checkpoint_data')

        migration.status = 'pending'
        migration.current_stage = None
        migration.end_time = None
        migration.duration_seconds = None
        migration.progress_percentage = 0
        migration.structure_approved_at = None
        migration.structure_approved_by = None
        migration.updated_at = datetime.utcnow()
        db.commit()

        export_done = bool(checkpoint.get('export_completed_at'))
        logger.info(
            f"Migration {migration_id} set to pending for retry "
            f"(export preserved={export_done})"
        )
        return {
            "message": "Migration ready to retry — export checkpoint preserved. "
                       "Use /start to begin the transfer stage.",
            "migration_id": migration_id,
            "status": "pending",
            "export_preserved": export_done,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to set up retry for migration {migration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to prepare migration retry: {str(e)}"
        )


@router.post("/{migration_id}/restart")
async def restart_migration(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Restart an Iceberg migration from the beginning."""
    migration = _get_migration_or_404(db, migration_id, workspace_id)

    if migration.status == 'running':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot restart a running migration. Cancel it first."
        )

    try:
        # Reset state but preserve configuration
        migration.status = 'running'
        migration.current_stage = None
        migration.start_time = datetime.utcnow()
        migration.end_time = None
        migration.duration_seconds = None
        migration.progress_percentage = 0
        migration.checkpoint_data = {}
        migration.resume_point = None
        migration.total_rows_source = None
        migration.total_rows_target = None
        migration.total_bytes_transferred = None
        migration.structure_approved_at = None
        migration.structure_approved_by = None
        migration.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Restarted Iceberg migration {migration_id}")
        return {
            "message": "Migration restarted successfully",
            "migration_id": migration_id,
            "status": "running"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to restart Iceberg migration {migration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart migration: {str(e)}"
        )


@router.get("/{migration_id}/status")
async def get_migration_status(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Get current migration status with progress percentage."""
    migration = _get_migration_or_404(db, migration_id, workspace_id)

    return {
        "migration_id": migration.id,
        "status": migration.status,
        "current_stage": migration.current_stage,
        "progress_percentage": migration.progress_percentage or 0,
        "start_time": _format_datetime(migration.start_time),
        "end_time": _format_datetime(migration.end_time),
        "duration_seconds": migration.duration_seconds,
        "total_rows_source": migration.total_rows_source,
        "total_rows_target": migration.total_rows_target,
        "total_bytes_transferred": migration.total_bytes_transferred,
    }


@router.get("/{migration_id}/logs")
async def get_migration_logs(
    request: Request,
    migration_id: int,
    level: Optional[str] = None,
    stage: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Get migration logs with optional filtering by level and stage."""
    _get_migration_or_404(db, migration_id, workspace_id)

    try:
        query = db.query(MigrationLog).filter(
            MigrationLog.migration_id == migration_id
        )

        if level:
            query = query.filter(MigrationLog.log_level == level.upper())
        if stage:
            query = query.filter(MigrationLog.stage == stage)

        logs = query.order_by(MigrationLog.created_at.desc()).limit(limit).all()

        return {
            "migration_id": migration_id,
            "total_logs": len(logs),
            "logs": [log.to_dict() for log in logs]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get logs for migration {migration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get migration logs: {str(e)}"
        )


# ============================================================================
# Task 11.3: Structure Report and Approval API Endpoints
# ============================================================================

@router.get("/{migration_id}/structure-report")
async def get_structure_report(
    request: Request,
    migration_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Get the full Iceberg Structure Design Report as JSON."""
    migration = _get_migration_or_404(db, migration_id, workspace_id)

    if not migration.structure_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Structure report not yet generated. Migration must reach the review stage first."
        )

    return {
        "migration_id": migration_id,
        "status": migration.status,
        "structure_report": migration.structure_report,
        "cost_analysis_report": migration.cost_analysis_report,
        "approved_at": _format_datetime(migration.structure_approved_at),
        "approved_by": migration.structure_approved_by,
    }


@router.post("/{migration_id}/approve-structure")
async def approve_structure(
    request: Request,
    migration_id: int,
    req: ApproveStructureRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """
    Approve the structure report and allow the load stage to begin.

    Optionally accepts overrides and dataset-to-database mapping.
    Transitions migration from pending_review to approved.
    """
    migration = _get_migration_or_404(db, migration_id, workspace_id)

    if migration.status != 'pending_review':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Migration must be in 'pending_review' status to approve (current: {migration.status})"
        )

    try:
        # Build the approved structure plan
        structure_plan = migration.structure_report.copy() if migration.structure_report else {}

        # Apply overrides if provided
        if req.overrides:
            structure_plan['user_overrides'] = req.overrides
        if req.excluded_tables:
            structure_plan['excluded_tables'] = req.excluded_tables
        if req.custom_properties:
            structure_plan['custom_properties'] = req.custom_properties

        # Apply dataset-to-database mapping
        if req.dataset_to_db_mapping:
            migration.dataset_to_db_mapping = req.dataset_to_db_mapping
            structure_plan['dataset_to_db_mapping'] = req.dataset_to_db_mapping

        # Validate and apply per-table compaction configs
        if req.table_compaction_configs:
            # Get table schemas from the structure report for validation
            tables_in_report = structure_plan.get('tables', [])
            table_schema_map = {}
            for table_entry in tables_in_report:
                table_name = table_entry.get('proposed_name') or table_entry.get('source_table', '')
                columns = table_entry.get('columns', [])
                # Extract column names from the table schema
                schema_columns = [
                    col.get('name', '') for col in columns if isinstance(col, dict)
                ]
                if not schema_columns:
                    # Fallback: try column_name key
                    schema_columns = [
                        col.get('column_name', '') for col in columns if isinstance(col, dict)
                    ]
                table_schema_map[table_name] = schema_columns

            for table_name, compaction_config in req.table_compaction_configs.items():
                table_schema_columns = table_schema_map.get(table_name, [])
                is_valid, error_msg = validate_compaction_strategy(
                    compaction_config.strategy,
                    compaction_config.sort_columns,
                    table_schema_columns,
                )
                if not is_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid compaction config for table '{table_name}': {error_msg}"
                    )

            # Persist compaction configs in the structure plan under each table's entry
            for table_entry in tables_in_report:
                table_name = table_entry.get('proposed_name') or table_entry.get('source_table', '')
                if table_name in req.table_compaction_configs:
                    config = req.table_compaction_configs[table_name]
                    table_entry['compaction_config'] = {
                        "strategy": config.strategy,
                        "sort_columns": config.sort_columns,
                    }

            structure_plan['tables'] = tables_in_report

        # Store approved plan in checkpoint_data
        checkpoint = dict(migration.checkpoint_data or {})
        checkpoint['iceberg_structure_plan'] = structure_plan
        migration.checkpoint_data = checkpoint
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(migration, 'checkpoint_data')

        # Transition status to running and start load automatically
        migration.status = 'running'
        migration.structure_approved_at = datetime.utcnow()
        migration.structure_approved_by = current_user.user_id
        migration.start_time = datetime.utcnow()
        migration.updated_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"Structure approved for migration {migration_id} by user {current_user.user_id} — starting load"
        )

        # Capture values for background thread before db session closes
        migration_id_val = migration_id
        workspace_id_val = workspace_id

        # Spawn background thread to run the load stage (same pattern as start_migration)
        import threading
        from database import db_instance

        def run_migration_background(mid: int, wid: int):
            bg_db = db_instance.SessionLocal()
            try:
                _setup_thread_aws_env()
                from models.migration_bq_iceberg import MigrationBQIceberg
                from services.bq_iceberg_migration.orchestrator import IcebergMigrationOrchestrator
                from services.bq_iceberg_migration.structure_report import StructureReportGenerator
                from services.bq_iceberg_migration.cost_engine import CostAnalysisEngine
                from services.bq_iceberg_migration.schema_evolution import SchemaEvolutionService
                from services.bq_iceberg_migration.validation_service import IcebergValidationService
                from services.bq_iceberg_migration.athena_verifier import AthenaVerifier
                from services.bq_iceberg_migration.iceberg_loader import ParallelIcebergLoader
                from services.bq_iceberg_migration.credential_provider import AWSCredentialProvider
                from services.bq_iceberg_migration.type_mapper import BQToIcebergTypeMapper
                from services.bq_iceberg_migration.partition_mapper import PartitionSpecMapper
                from services.bq_iceberg_migration.dedup_guard import DeduplicationGuard
                import asyncio
                import boto3

                mig = bg_db.query(MigrationBQIceberg).filter_by(id=mid).first()
                if not mig:
                    logger.error(f"Migration {mid} not found in background thread")
                    return

                logger.info(f"[BG] Starting load stage for approved migration {mid}")

                aws_region = mig.aws_region or "us-east-1"

                athena_client = boto3.client("athena", region_name=aws_region)
                athena_workgroup = getattr(mig, "athena_workgroup", "primary") or "primary"
                athena_output = getattr(mig, "athena_output_location", None)
                athena_verifier = AthenaVerifier(
                    athena_client=athena_client,
                    workgroup=athena_workgroup,
                    output_location=athena_output,
                )

                try:
                    from services.unified_kms_service import get_unified_kms_service
                    kms_service = get_unified_kms_service()
                except Exception as _kms_err:
                    logger.warning(f"[BG] KMS service unavailable, using None: {_kms_err}")
                    kms_service = None

                sts_client = boto3.client("sts", region_name=aws_region)
                credential_provider = AWSCredentialProvider(
                    kms_service=kms_service,
                    sts_client=sts_client,
                )

                try:
                    import os as _os
                    _os.environ["AWS_DEFAULT_REGION"] = aws_region
                    from pyiceberg.catalog.glue import GlueCatalog
                    glue_catalog = GlueCatalog(name="glue")
                except Exception as _catalog_err:
                    logger.warning(
                        f"[BG] Could not build GlueCatalog, using None: {_catalog_err}"
                    )
                    glue_catalog = None

                type_mapper = BQToIcebergTypeMapper()
                partition_mapper = PartitionSpecMapper()
                dedup_guard = DeduplicationGuard()
                loader = ParallelIcebergLoader(
                    catalog=glue_catalog,
                    credential_provider=credential_provider,
                    type_mapper=type_mapper,
                    partition_mapper=partition_mapper,
                    dedup_guard=dedup_guard,
                    parallelism=getattr(mig, 'parallelism', 4),
                )

                structure_gen = StructureReportGenerator()
                cost_engine = CostAnalysisEngine()
                schema_evolution = SchemaEvolutionService(type_mapper=type_mapper)
                validation_svc = IcebergValidationService()

                orchestrator = IcebergMigrationOrchestrator(
                    loader=loader,
                    structure_report_generator=structure_gen,
                    cost_engine=cost_engine,
                    schema_evolution_service=schema_evolution,
                    validation_service=validation_svc,
                    athena_verifier=athena_verifier,
                )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    success = loop.run_until_complete(
                        orchestrator.execute_iceberg_migration(mig)
                    )
                    bg_db.commit()
                    logger.info(f"[BG] Approved migration {mid} load finished, success={success}")
                finally:
                    loop.close()

            except Exception as e:
                logger.error(f"[BG] Approved migration {mid} load thread failed: {e}", exc_info=True)
                try:
                    from models.migration_bq_iceberg import MigrationBQIceberg
                    mig = bg_db.query(MigrationBQIceberg).filter_by(id=mid).first()
                    if mig and mig.status == 'running':
                        mig.status = 'failed'
                        mig.updated_at = datetime.utcnow()
                        bg_db.commit()
                except Exception:
                    pass
            finally:
                bg_db.close()

        thread = threading.Thread(
            target=run_migration_background,
            args=(migration_id_val, workspace_id_val),
            daemon=True,
            name=f"iceberg-approved-load-{migration_id_val}"
        )
        thread.start()
        logger.info(f"Background load thread started for approved migration {migration_id_val}")

        return {
            "message": "Structure approved. Load stage started automatically.",
            "migration_id": migration_id,
            "status": "running",
            "approved_at": _format_datetime(migration.structure_approved_at)
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to approve structure for migration {migration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve structure: {str(e)}"
        )


@router.post("/{migration_id}/request-changes")
async def request_changes(
    request: Request,
    migration_id: int,
    req: RequestChangesRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """
    Submit structure overrides (partition changes, exclusions, custom properties).

    The report will be regenerated with the applied overrides.
    """
    migration = _get_migration_or_404(db, migration_id, workspace_id)

    if migration.status != 'pending_review':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Changes can only be requested in 'pending_review' status (current: {migration.status})"
        )

    try:
        # Store overrides in structure report for regeneration
        report = migration.structure_report or {}
        report['pending_overrides'] = req.table_overrides
        if req.dataset_to_db_mapping:
            report['pending_dataset_mapping'] = req.dataset_to_db_mapping

        migration.structure_report = report
        migration.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Structure changes requested for migration {migration_id}")
        return {
            "message": "Changes submitted. Report will be regenerated.",
            "migration_id": migration_id,
            "overrides_applied": list(req.table_overrides.keys())
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to request changes for migration {migration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit changes: {str(e)}"
        )


@router.post("/{migration_id}/custom-structure")
async def define_custom_structure(
    request: Request,
    migration_id: int,
    req: CustomStructureRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """
    Define a custom Iceberg table structure from scratch for a specific table.

    Validates that the custom structure is compatible with the source data.
    """
    migration = _get_migration_or_404(db, migration_id, workspace_id)

    if migration.status != 'pending_review':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Custom structures can only be defined in 'pending_review' status (current: {migration.status})"
        )

    try:
        # Validate column definitions
        warnings = []
        for col in req.columns:
            if 'name' not in col or 'iceberg_type' not in col:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Each column must have 'name' and 'iceberg_type' fields"
                )

        # Store custom structure in the report
        report = migration.structure_report or {}
        custom_structures = report.get('custom_structures', {})
        custom_structures[req.table_name] = {
            "table_name": req.table_name,
            "columns": req.columns,
            "partition_spec": req.partition_spec,
            "sort_order": req.sort_order,
            "table_properties": req.table_properties,
            "defined_by": current_user.user_id,
            "defined_at": datetime.utcnow().isoformat() + 'Z'
        }
        report['custom_structures'] = custom_structures
        migration.structure_report = report
        migration.updated_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"Custom structure defined for table '{req.table_name}' "
            f"in migration {migration_id}"
        )
        return {
            "message": f"Custom structure defined for table '{req.table_name}'",
            "migration_id": migration_id,
            "table_name": req.table_name,
            "warnings": warnings
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to define custom structure for migration {migration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to define custom structure: {str(e)}"
        )


@router.get("/{migration_id}/download-report")
async def download_report(
    request: Request,
    migration_id: int,
    format: str = Query("markdown", pattern="^(markdown|pdf)$"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    workspace_id: int = Depends(get_workspace_id)
):
    """Download the structure design report as Markdown or PDF."""
    migration = _get_migration_or_404(db, migration_id, workspace_id)

    if not migration.structure_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Structure report not yet generated."
        )

    try:
        report = migration.structure_report

        if format == "markdown":
            md_content = _generate_markdown_report(migration, report)
            return StreamingResponse(
                io.BytesIO(md_content.encode('utf-8')),
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f"attachment; filename=structure_report_{migration_id}.md"
                }
            )
        else:
            # PDF generation - return markdown as fallback if PDF library not available
            md_content = _generate_markdown_report(migration, report)
            return StreamingResponse(
                io.BytesIO(md_content.encode('utf-8')),
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f"attachment; filename=structure_report_{migration_id}.md"
                }
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download report for migration {migration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download report: {str(e)}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download report for migration {migration_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download report: {str(e)}"
        )


# ============================================================================
# Helper: Markdown Report Generation
# ============================================================================

def _generate_markdown_report(migration, report: dict) -> str:
    """Generate a markdown-formatted structure design report."""
    lines = [
        f"# Iceberg Structure Design Report",
        f"## Migration: {migration.migration_name}",
        f"",
        f"**Destination Type:** {migration.destination_type}",
        f"**AWS Region:** {migration.aws_region}",
        f"**Glue Database:** {migration.glue_database_name}",
        f"",
    ]

    # Tables section
    tables = report.get("tables", [])
    if tables:
        lines.append("## Tables")
        lines.append("")
        for table in tables:
            table_name = table.get("proposed_name", table.get("source_table", "unknown"))
            lines.append(f"### {table_name}")
            lines.append("")
            if "columns" in table:
                lines.append("| Column | Type | Nullable |")
                lines.append("|--------|------|----------|")
                for col in table.get("columns", []):
                    lines.append(
                        f"| {col.get('name', '')} | {col.get('iceberg_type', '')} "
                        f"| {col.get('nullable', True)} |"
                    )
                lines.append("")

    return "\n".join(lines)
