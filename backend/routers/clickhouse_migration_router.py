"""
ClickHouse Migration Router

API endpoints for BigQuery → GCS → ClickHouse migrations.
Handles migration creation, execution, status tracking, and logging.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from repositories.connection_repository import ConnectionRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/migrations/clickhouse", tags=["clickhouse-migrations"])


# ─── Request/Response Models ───────────────────────────────────────────────

class ClickHouseMigrationRequest(BaseModel):
    """Request to start a ClickHouse migration."""
    name: str
    source_connection_id: int
    target_connection_id: int
    selected_tables: List[Dict[str, Any]]  # [{table_name, dataset_name, columns, row_count, ...}]
    config: Dict[str, Any]  # GCS bucket, HMAC keys, engine, order_by, etc.


class MigrationStatusResponse(BaseModel):
    """Migration status with per-table progress."""
    migration_id: str
    name: str
    status: str  # pending, running, completed, failed
    total_tables: int
    completed_tables: int
    failed_tables: int
    current_table: Optional[str] = None
    current_stage: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    table_results: List[Dict[str, Any]] = []


class MigrationLogEntry(BaseModel):
    """Single log entry."""
    table_name: str
    stage: str
    status: str
    message: str
    rows_processed: int = 0
    duration_seconds: float = 0
    error_detail: Optional[str] = None
    timestamp: str


# ─── In-memory migration state (replace with DB in production) ─────────────

# No longer using in-memory dict — all state persisted to migrations_clickhouse table


# ─── DB Helper Functions ──────────────────────────────────────────────────

def _get_migration_from_db(migration_id: str, db: Session):
    """Get migration record from database."""
    from models.clickhouse_migration import ClickHouseMigration
    return db.query(ClickHouseMigration).filter(
        ClickHouseMigration.migration_id == migration_id
    ).first()


def _update_migration_db(migration_id: str, updates: Dict[str, Any]):
    """Update migration record in database."""
    from database import db_instance
    from models.clickhouse_migration import ClickHouseMigration
    db = db_instance.SessionLocal()
    try:
        migration = db.query(ClickHouseMigration).filter(
            ClickHouseMigration.migration_id == migration_id
        ).first()
        if migration:
            for key, value in updates.items():
                setattr(migration, key, value)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to update migration {migration_id}: {e}")
        db.rollback()
    finally:
        db.close()


# ─── Background Task ──────────────────────────────────────────────────────

def run_clickhouse_migration_background(
    migration_id: str,
    source_connection_id: int,
    target_connection_id: int,
    selected_tables: List[Dict],
    config: Dict[str, Any],
):
    """Background task to execute the ClickHouse migration."""
    from database import db_instance
    import time

    db = db_instance.SessionLocal()
    try:
        connection_repo = ConnectionRepository(db)

        # Get connections
        source_conn = connection_repo.get_by_id(source_connection_id)
        target_conn = connection_repo.get_by_id(target_connection_id)

        if not source_conn or not target_conn:
            _update_migration_db(migration_id, {
                'status': 'failed',
                'completed_at': datetime.utcnow(),
                'logs': [{'table_name': '_migration_', 'stage': 'init', 'status': 'failed', 'message': 'Source or target connection not found', 'timestamp': datetime.utcnow().isoformat()}],
            })
            return

        # Initialize BigQuery client using decrypted connection params
        from google.cloud import bigquery
        from google.oauth2 import service_account
        from routers.connections_router import get_decrypted_connection_params
        import json as json_lib

        source_params = get_decrypted_connection_params(source_conn)
        # Extract service account JSON - stored as 'credentials_json', 'service_account_json', or 'credentials'
        sa_info = source_params.get('credentials_json') or source_params.get('service_account_json') or source_params.get('credentials') or source_params
        project_id = source_params.get('project_id', '')

        if isinstance(sa_info, str):
            sa_info = json_lib.loads(sa_info)

        credentials = service_account.Credentials.from_service_account_info(sa_info)
        bq_client = bigquery.Client(credentials=credentials, project=project_id)

        # Initialize ClickHouse client using decrypted connection params
        import clickhouse_connect
        target_params = get_decrypted_connection_params(target_conn)
        ch_client = clickhouse_connect.get_client(
            host=target_params.get('host', ''),
            port=int(target_params.get('port', 8443)),
            database=target_params.get('database_name') or target_params.get('database', 'default'),
            username=target_params.get('username', 'default'),
            password=target_params.get('password', ''),
            secure=str(target_params.get('secure', 'false')).lower() in ('true', '1', 'yes'),
            connect_timeout=30,
        )

        # Initialize migration service
        from services.clickhouse_migration_service import ClickHouseMigrationService

        migration_config = {
            'gcs_bucket': config.get('gcsBucket', '').replace('gs://', '').strip('/'),
            'gcs_path_prefix': config.get('gcsPathPrefix', 'migrations'),
            'gcs_hmac_access_key': config.get('gcsHmacAccessKey', ''),
            'gcs_hmac_secret_key': config.get('gcsHmacSecretKey', ''),
            'clickhouse_database': config.get('clickhouseDatabase', 'default'),
            'clickhouse_engine': config.get('clickhouseEngine', 'MergeTree'),
            'clickhouse_order_by': config.get('clickhouseOrderBy', 'auto'),
            'custom_order_by_map': config.get('customOrderByMap', {}),
            'export_format': config.get('exportFormat', 'PARQUET'),
            'compression': config.get('compression', 'SNAPPY'),
        }

        service = ClickHouseMigrationService(bq_client, ch_client, migration_config)

        # Update migration state to running
        _update_migration_db(migration_id, {
            'status': 'running',
            'started_at': datetime.utcnow(),
        })

        # Determine dataset from first table (or from config)
        dataset_name = ''
        if selected_tables:
            dataset_name = selected_tables[0].get('dataset_name', '')

        # Fetch column metadata from the latest assessment for this source connection
        # This avoids redundant BigQuery API calls — assessment already has all metadata
        from repositories.assessment_repository import AssessmentRepository
        from models.assessment import Assessment, AssessmentTable, AssessmentColumn
        assessment_repo = AssessmentRepository(db)

        # Find the latest completed assessment for this source connection
        latest_assessment = db.query(Assessment).filter(
            Assessment.source_connection_id == source_connection_id,
            Assessment.status == 'completed'
        ).order_by(Assessment.started_at.desc()).first()

        if latest_assessment:
            logger.info(f"Using assessment {latest_assessment.id} ({latest_assessment.name}) for table metadata")
            # Get all tables and columns from the assessment
            assessment_tables = db.query(AssessmentTable).filter(
                AssessmentTable.assessment_id == latest_assessment.id,
                AssessmentTable.table_type == 'BASE TABLE',  # Exclude views
            ).all()
            assessment_columns = db.query(AssessmentColumn).filter(
                AssessmentColumn.assessment_id == latest_assessment.id
            ).all()

            # Build lookup: table_name -> columns
            table_columns_map = {}
            table_id_to_name = {}
            for t in assessment_tables:
                table_id_to_name[t.id] = t.table_name
                table_columns_map[t.table_name] = {
                    'row_count': t.row_count or 0,
                    'partitioning_columns': t.partitioning_columns or [],
                    'clustering_columns': t.clustering_columns or [],
                    'columns': [],
                }
            for col in assessment_columns:
                tname = table_id_to_name.get(col.table_id)
                if tname and tname in table_columns_map:
                    table_columns_map[tname]['columns'].append({
                        'column_name': col.column_name,
                        'data_type': col.data_type,
                        'is_nullable': col.is_nullable if col.is_nullable is not None else True,
                    })

            # Enrich selected_tables with assessment data
            for table in selected_tables:
                table_name = table.get('table_name', '')
                if table_name in table_columns_map and not table.get('columns'):
                    meta = table_columns_map[table_name]
                    table['columns'] = meta['columns']
                    table['row_count'] = meta['row_count']
                    table['partitioning_columns'] = meta['partitioning_columns']
                    table['clustering_columns'] = meta['clustering_columns']
                    logger.info(f"  {table_name}: {len(meta['columns'])} columns from assessment")
        else:
            logger.warning("No completed assessment found — falling back to BigQuery API")

        # Fallback: fetch from BigQuery for tables still missing columns
        project_id_for_query = project_id
        for table in selected_tables:
            if not table.get('columns'):
                table_name = table.get('table_name', '')
                table_dataset = table.get('dataset_name', dataset_name)
                try:
                    bq_table_ref = f'{project_id_for_query}.{table_dataset}.{table_name}'
                    bq_table = bq_client.get_table(bq_table_ref)
                    # Skip views — only migrate base tables
                    if bq_table.table_type == 'VIEW':
                        logger.info(f"  {table_name}: skipping (VIEW, not a table)")
                        table['_skip'] = True
                        continue
                    table['columns'] = [
                        {
                            'column_name': field.name,
                            'data_type': field.field_type,
                            'is_nullable': field.mode != 'REQUIRED',
                        }
                        for field in bq_table.schema
                    ]
                    table['row_count'] = bq_table.num_rows or 0
                    logger.info(f"  {table_name}: fetched from BigQuery (no assessment data)")
                except Exception as e:
                    logger.error(f"Failed to fetch schema for {table_name}: {e}")
                    table['columns'] = []

        # Filter out views from selected_tables
        selected_tables = [t for t in selected_tables if not t.get('_skip')]

        # Run migration
        total = len(selected_tables)
        completed_count = 0
        failed_count = 0
        for i, table in enumerate(selected_tables):
            table_name = table.get('table_name', '')
            table_dataset = table.get('dataset_name', dataset_name)

            _update_migration_db(migration_id, {'current_table': table_name, 'current_stage': 'ddl'})

            # Get columns for this table
            columns = table.get('columns', [])

            # Determine ORDER BY
            order_by = service._determine_order_by(table)

            # Stage 1: DDL
            if not service.create_table(table_name, columns, order_by):
                _update_table_result(migration_id, table_name, 'failed', 'ddl')
                failed_count += 1
                _update_migration_db(migration_id, {'failed_tables': failed_count})
                continue

            # Stage 2: Export
            _update_migration_db(migration_id, {'current_stage': 'export'})
            if not service.export_to_gcs(project_id, table_dataset, table_name):
                _update_table_result(migration_id, table_name, 'failed', 'export')
                failed_count += 1
                _update_migration_db(migration_id, {'failed_tables': failed_count})
                continue

            # Stage 3: Import
            _update_migration_db(migration_id, {'current_stage': 'import'})
            if not service.import_from_gcs(table_name, columns):
                _update_table_result(migration_id, table_name, 'failed', 'import')
                failed_count += 1
                _update_migration_db(migration_id, {'failed_tables': failed_count})
                continue

            # Stage 4: Verify
            _update_migration_db(migration_id, {'current_stage': 'verify'})
            service.verify_row_count(table_name, table.get('row_count', 0))

            _update_table_result(migration_id, table_name, 'completed', 'verify')
            completed_count += 1
            _update_migration_db(migration_id, {'completed_tables': completed_count})

        # Finalize
        final_status = 'completed' if failed_count == 0 else ('failed' if completed_count == 0 else 'completed')
        _update_migration_db(migration_id, {
            'status': final_status,
            'completed_at': datetime.utcnow(),
            'current_table': None,
            'current_stage': None,
            'logs': service.logs,
        })

        ch_client.close()

    except Exception as e:
        logger.error(f"Migration {migration_id} failed: {e}", exc_info=True)
        _update_migration_db(migration_id, {
            'status': 'failed',
            'completed_at': datetime.utcnow(),
            'logs': [{'table_name': '_migration_', 'stage': 'error', 'status': 'failed', 'message': f'Migration failed: {str(e)}', 'timestamp': datetime.utcnow().isoformat()}],
        })
    finally:
        db.close()


def _update_table_result(migration_id: str, table_name: str, status: str, last_stage: str):
    """Update the table result in migration state (DB)."""
    from database import db_instance
    from models.clickhouse_migration import ClickHouseMigration
    db = db_instance.SessionLocal()
    try:
        migration = db.query(ClickHouseMigration).filter(
            ClickHouseMigration.migration_id == migration_id
        ).first()
        if migration:
            results = migration.table_results or []
            results.append({
                'table_name': table_name,
                'status': status,
                'last_stage': last_stage,
                'timestamp': datetime.utcnow().isoformat(),
            })
            migration.table_results = results
            db.commit()
    except Exception as e:
        logger.error(f"Failed to update table result: {e}")
        db.rollback()
    finally:
        db.close()


# ─── API Endpoints ─────────────────────────────────────────────────────────

@router.post("/start")
async def start_migration(
    request: ClickHouseMigrationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start a new BigQuery → ClickHouse migration."""
    import uuid
    from models.clickhouse_migration import ClickHouseMigration

    migration_id = str(uuid.uuid4())[:8]

    # Create migration record in database
    migration = ClickHouseMigration(
        migration_id=migration_id,
        name=request.name,
        status='pending',
        source_connection_id=request.source_connection_id,
        target_connection_id=request.target_connection_id,
        total_tables=len(request.selected_tables),
        completed_tables=0,
        failed_tables=0,
        config=request.config,
        selected_tables=[t for t in request.selected_tables],
        table_results=[],
        logs=[],
    )
    db.add(migration)
    db.commit()

    # Start background task
    background_tasks.add_task(
        run_clickhouse_migration_background,
        migration_id,
        request.source_connection_id,
        request.target_connection_id,
        request.selected_tables,
        request.config,
    )

    return {
        'migration_id': migration_id,
        'status': 'pending',
        'message': f'Migration started for {len(request.selected_tables)} tables',
    }


@router.get("/{migration_id}/status")
async def get_migration_status(migration_id: str, db: Session = Depends(get_db)):
    """Get real-time migration status."""
    from models.clickhouse_migration import ClickHouseMigration
    migration = db.query(ClickHouseMigration).filter(
        ClickHouseMigration.migration_id == migration_id
    ).first()
    if not migration:
        raise HTTPException(status_code=404, detail="Migration not found")

    return {
        'migration_id': migration.migration_id,
        'name': migration.name,
        'status': migration.status,
        'total_tables': migration.total_tables,
        'completed_tables': migration.completed_tables,
        'failed_tables': migration.failed_tables,
        'current_table': migration.current_table,
        'current_stage': migration.current_stage,
        'started_at': migration.started_at.isoformat() if migration.started_at else None,
        'completed_at': migration.completed_at.isoformat() if migration.completed_at else None,
        'table_results': migration.table_results or [],
    }


@router.get("/{migration_id}/logs")
async def get_migration_logs(migration_id: str, db: Session = Depends(get_db)):
    """Get detailed migration logs."""
    from models.clickhouse_migration import ClickHouseMigration
    migration = db.query(ClickHouseMigration).filter(
        ClickHouseMigration.migration_id == migration_id
    ).first()
    if not migration:
        raise HTTPException(status_code=404, detail="Migration not found")

    return {
        'migration_id': migration_id,
        'logs': migration.logs or [],
    }


@router.post("/{migration_id}/retry")
async def retry_failed_tables(
    migration_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Retry failed tables in a migration."""
    from models.clickhouse_migration import ClickHouseMigration
    migration = db.query(ClickHouseMigration).filter(
        ClickHouseMigration.migration_id == migration_id
    ).first()
    if not migration:
        raise HTTPException(status_code=404, detail="Migration not found")
    if migration.status == 'running':
        raise HTTPException(status_code=400, detail="Migration is still running")

    failed = [r for r in (migration.table_results or []) if r.get('status') == 'failed']
    if not failed:
        return {'message': 'No failed tables to retry'}

    return {'message': f'{len(failed)} failed tables identified for retry (not yet implemented)'}


@router.get("/list")
async def list_migrations(db: Session = Depends(get_db)):
    """List all ClickHouse migrations."""
    from models.clickhouse_migration import ClickHouseMigration
    migrations = db.query(ClickHouseMigration).order_by(
        ClickHouseMigration.created_at.desc()
    ).all()

    return {
        'migrations': [
            {
                'migration_id': m.migration_id,
                'name': m.name,
                'status': m.status,
                'total_tables': m.total_tables,
                'completed_tables': m.completed_tables,
                'failed_tables': m.failed_tables,
                'started_at': m.started_at.isoformat() if m.started_at else None,
                'completed_at': m.completed_at.isoformat() if m.completed_at else None,
            }
            for m in migrations
        ]
    }
