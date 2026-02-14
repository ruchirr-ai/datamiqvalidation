"""
Test Assessment Run
Manually trigger assessment execution to debug status updates
"""

import asyncio
from database import db_instance
from models.assessment import Assessment
from models.assessment_log import AssessmentLog
from repositories.assessment_repository import AssessmentRepository
from repositories.connection_repository import ConnectionRepository
from services.bigquery_assessment_service import BigQueryAssessmentService

async def test_assessment_run():
    """Test running an assessment"""
    db = db_instance.SessionLocal()
    
    try:
        # Get the pending assessment
        assessment = db.query(Assessment).filter(Assessment.status == 'pending').first()
        
        if not assessment:
            print("No pending assessments found")
            return
        
        print(f"Found assessment: ID={assessment.id}, Name={assessment.name}, Status={assessment.status}")
        
        # Initialize repositories
        assessment_repo = AssessmentRepository(db)
        connection_repo = ConnectionRepository(db)
        
        # Get connections
        source_conn = connection_repo.get_by_id(assessment.source_connection_id)
        target_conn = connection_repo.get_by_id(assessment.target_connection_id)
        
        print(f"Source connection: {source_conn.name if source_conn else 'NOT FOUND'}")
        print(f"Target connection: {target_conn.name if target_conn else 'NOT FOUND'}")
        
        if not source_conn or not target_conn:
            print("ERROR: Connections not found!")
            return
        
        # Update status to running
        print("\n1. Updating status to 'running'...")
        assessment_repo.update_status(assessment.id, 'running')
        db.commit()
        
        # Verify status update
        assessment = assessment_repo.get_by_id(assessment.id)
        print(f"   Status after update: {assessment.status}")
        
        # Create log
        print("\n2. Creating log entry...")
        assessment_repo.create_log(
            assessment_id=assessment.id,
            log_level='INFO',
            message='Test: Assessment execution started',
            stage='test'
        )
        
        # Check logs
        logs = assessment_repo.get_logs(assessment.id)
        print(f"   Total logs: {len(logs)}")
        
        # Initialize BigQuery service
        print("\n3. Initializing BigQuery service...")
        try:
            bq_service = BigQueryAssessmentService(source_conn.connection_params)
            print("   BigQuery service initialized successfully")
            
            # Try to run assessment
            print("\n4. Running full assessment...")
            await bq_service.run_full_assessment(assessment.id, db)
            
            # Check final status
            assessment = assessment_repo.get_by_id(assessment.id)
            print(f"\n5. Final status: {assessment.status}")
            print(f"   Datasets: {assessment.total_datasets}")
            print(f"   Tables: {assessment.total_tables}")
            print(f"   Views: {assessment.total_views}")
            
        except Exception as e:
            print(f"   ERROR during assessment: {e}")
            import traceback
            traceback.print_exc()
            
            # Update to failed
            assessment_repo.update_status(assessment.id, 'failed', error_message=str(e))
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_assessment_run())
