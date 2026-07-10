"""
Directly test the full orchestration to see what happens step by step.
"""
import sys, asyncio, logging
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv("../.env")

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

from database import db_instance
from sqlalchemy import text
import boto3, json

# Reset migration
with db_instance.get_session() as db:
    db.execute(text(
        "UPDATE migrations_bq_iceberg SET status='pending', current_stage=NULL, "
        "progress_percentage=0, start_time=NULL, structure_report=NULL, "
        "cost_analysis_report=NULL, structure_approved_at=NULL, "
        "checkpoint_data='{}', updated_at=NOW() WHERE id=1"
    ))
    db.commit()
    print("Reset migration to pending")

# Run orchestration directly (not in a thread) to see output
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

bg_db = db_instance.SessionLocal()
mig = bg_db.query(MigrationBQIceberg).filter_by(id=1).first()
print(f"Migration: id={mig.id}, status={mig.status}, project={mig.source_project_id}, dataset={mig.source_dataset}, tables={mig.source_tables}")
print(f"Source connection id: {mig.source_connection_id}")

aws_region = mig.aws_region or "us-east-1"
athena_client = boto3.client("athena", region_name=aws_region)
sts_client = boto3.client("sts", region_name=aws_region)

try:
    from services.unified_kms_service import get_unified_kms_service
    kms_service = get_unified_kms_service()
    print("KMS loaded OK")
except Exception as e:
    print(f"KMS not available: {e}")
    kms_service = None

credential_provider = AWSCredentialProvider(kms_service=kms_service, sts_client=sts_client)

try:
    from pyiceberg.catalog.glue import GlueCatalog
    glue_catalog = GlueCatalog(name="glue", **{"region_name": aws_region, "s3.region": aws_region})
    print("GlueCatalog OK")
except Exception as e:
    print(f"GlueCatalog failed: {e}")
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

print("\n--- Running orchestration ---")
loop = asyncio.new_event_loop()
result = loop.run_until_complete(orchestrator.execute_iceberg_migration(mig))
bg_db.commit()
loop.close()

print(f"\n--- Result: {result} ---")
print(f"Status: {mig.status}, Stage: {mig.current_stage}")
sr = mig.structure_report or {}
print(f"Structure report tables: {len(sr.get('tables', []))}")
bg_db.close()
