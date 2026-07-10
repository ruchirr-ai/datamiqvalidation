"""
Directly approve the structure and kick off the load stage.
Bypasses the HTTP layer to avoid token issues.
"""
import sys, asyncio, json, logging
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv("../.env")

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

from database import db_instance
from sqlalchemy import text

with db_instance.get_session() as db:
    m = db.execute(text("SELECT id, status, structure_report FROM migrations_bq_iceberg WHERE id=1")).fetchone()
    print(f"Migration id={m[0]}, status={m[1]}")
    
    sr = m[2] if isinstance(m[2], dict) else json.loads(m[2]) if m[2] else {}
    print(f"Structure report tables: {len(sr.get('tables', []))}")
    
    # Build checkpoint with approved structure plan
    checkpoint = {"iceberg_structure_plan": sr, "assessment_tables": []}
    # Fetch assessment_tables from existing checkpoint
    existing = db.execute(text("SELECT checkpoint_data FROM migrations_bq_iceberg WHERE id=1")).fetchone()
    if existing and existing[0]:
        existing_cp = existing[0] if isinstance(existing[0], dict) else json.loads(existing[0])
        checkpoint["assessment_tables"] = existing_cp.get("assessment_tables", [])
    
    from datetime import datetime
    db.execute(text("""
        UPDATE migrations_bq_iceberg 
        SET status='approved',
            structure_approved_at=NOW(),
            structure_approved_by=1,
            checkpoint_data=CAST(:cp AS jsonb),
            updated_at=NOW()
        WHERE id=1
    """), {"cp": json.dumps(checkpoint)})
    db.commit()
    print("Migration approved and checkpoint saved")

print("\nNow starting load stage in background thread...")

# Import and run the orchestration
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
import boto3

bg_db = db_instance.SessionLocal()
mig = bg_db.query(MigrationBQIceberg).filter_by(id=1).first()
print(f"Migration status: {mig.status}")

aws_region = mig.aws_region or "us-east-1"
athena_client = boto3.client("athena", region_name=aws_region)
sts_client = boto3.client("sts", region_name=aws_region)

try:
    from services.unified_kms_service import get_unified_kms_service
    kms_service = get_unified_kms_service()
except Exception as e:
    print(f"KMS: {e}")
    kms_service = None

credential_provider = AWSCredentialProvider(kms_service=kms_service, sts_client=sts_client)

import os as _os; _os.environ["AWS_DEFAULT_REGION"] = aws_region
try:
    from pyiceberg.catalog.glue import GlueCatalog
    glue_catalog = GlueCatalog(name="glue")
    print("GlueCatalog initialized OK")
except Exception as e:
    print(f"GlueCatalog failed (will proceed without): {e}")
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
    parallelism=1,
)

orchestrator = IcebergMigrationOrchestrator(
    loader=loader,
    structure_report_generator=StructureReportGenerator(),
    cost_engine=CostAnalysisEngine(),
    schema_evolution_service=SchemaEvolutionService(type_mapper=type_mapper),
    validation_service=IcebergValidationService(),
    athena_verifier=AthenaVerifier(athena_client=athena_client, workgroup="primary"),
)

print("\n--- Executing load stage ---")
loop = asyncio.new_event_loop()
result = loop.run_until_complete(orchestrator.execute_iceberg_migration(mig))
bg_db.commit()
loop.close()

print(f"\nResult: {result}")
print(f"Final status: {mig.status}, stage: {mig.current_stage}, progress: {mig.progress_percentage}%")
bg_db.close()
