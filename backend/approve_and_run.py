"""
Approve the structure and kick off the load stage using an existing Glue database.
"""
import sys, asyncio, json, logging, os
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv("../.env")

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

# Use an existing Glue database (no CreateDatabase permission needed)
EXISTING_GLUE_DB = "datamiq_iceberg"

from database import db_instance
from sqlalchemy import text

with db_instance.get_session() as db:
    m = db.execute(text("SELECT id, status, structure_report, checkpoint_data FROM migrations_bq_iceberg WHERE id=1")).fetchone()
    print(f"Migration id={m[0]}, status={m[1]}")
    
    sr = m[2] if isinstance(m[2], dict) else json.loads(m[2]) if m[2] else {}
    existing_cp = m[3] if isinstance(m[3], dict) else json.loads(m[3]) if m[3] else {}
    
    # Update to use existing database
    checkpoint = {
        "assessment_tables": existing_cp.get("assessment_tables", []),
        "iceberg_structure_plan": sr,
    }
    checkpoint["iceberg_structure_plan"]["glue_database_name"] = EXISTING_GLUE_DB

    db.execute(text("""
        UPDATE migrations_bq_iceberg 
        SET status='approved',
            glue_database_name=:glue_db,
            structure_approved_at=NOW(),
            structure_approved_by=1,
            checkpoint_data=CAST(:cp AS jsonb),
            updated_at=NOW()
        WHERE id=1
    """), {"cp": json.dumps(checkpoint), "glue_db": EXISTING_GLUE_DB})
    db.commit()
    print(f"Approved with existing Glue DB: {EXISTING_GLUE_DB}")

# Run orchestration
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
print(f"Migration glue_database_name: {mig.glue_database_name}")

aws_region = mig.aws_region or "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = aws_region

athena_client = boto3.client("athena", region_name=aws_region)
sts_client = boto3.client("sts", region_name=aws_region)

try:
    from services.unified_kms_service import get_unified_kms_service
    kms_service = get_unified_kms_service()
except Exception as e:
    kms_service = None

credential_provider = AWSCredentialProvider(kms_service=kms_service, sts_client=sts_client)

from pyiceberg.catalog.glue import GlueCatalog
s3_bucket = getattr(mig, "s3_bucket", "datamiq-data") or "datamiq-data"
s3_prefix = getattr(mig, "s3_path_prefix", "iceberg/") or "iceberg/"
warehouse = f"s3://{s3_bucket}/{s3_prefix.rstrip('/')}"
glue_catalog = GlueCatalog(name="glue", warehouse=warehouse, region_name=aws_region)
print(f"GlueCatalog initialized OK, warehouse={warehouse}")

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
if mig.status == 'failed':
    print("Check logs above for the specific error")
bg_db.close()
