"""
Backfill security metadata for existing assessments

This script re-collects security policies for existing assessments
to ensure the security_metadata field (containing DDL) is populated.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import db_instance
from repositories.assessment_repository import AssessmentRepository
from repositories.connection_repository import ConnectionRepository
from services.bigquery_assessment_service import BigQueryAssessmentService
import asyncio


async def backfill_security_for_assessment(assessment_id: int):
    """Backfill security policies for a single assessment"""
    db = db_instance.SessionLocal()
    
    try:
        print(f"\n{'='*60}")
        print(f"Processing Assessment ID: {assessment_id}")
        print(f"{'='*60}")
        
        assessment_repo = AssessmentRepository(db)
        connection_repo = ConnectionRepository(db)
        
        # Get assessment
        assessment = assessment_repo.get_by_id(assessment_id)
        if not assessment:
            print(f"❌ Assessment {assessment_id} not found")
            return False
        
        print(f"Assessment: {assessment.name}")
        print(f"Status: {assessment.status}")
        
        # Get source connection
        source_conn = connection_repo.get_by_id(assessment.source_connection_id)
        if not source_conn:
            print(f"❌ Source connection not found")
            return False
        
        print(f"Source Connection: {source_conn.name}")
        
        # Initialize BigQuery service
        print("\nInitializing BigQuery service...")
        bq_service = BigQueryAssessmentService(source_conn.connection_params)
        
        # Collect security policies
        print("Collecting security policies from BigQuery...")
        security_data = await bq_service.collect_security_policies_detailed()
        
        if not security_data:
            print("⚠️  No security policies found in BigQuery")
            return True
        
        print(f"✓ Found {len(security_data)} security policies")
        
        # Display what was found
        for policy in security_data:
            print(f"\n  Policy: {policy['policy_name']}")
            print(f"  Table: {policy['table_name']}")
            print(f"  Type: {policy['security_type']}")
            print(f"  Has DDL: {'Yes' if policy.get('security_metadata', {}).get('ddl') else 'No'}")
        
        # Save to database (this will replace existing policies)
        print("\nSaving security policies to database...")
        assessment_repo.bulk_create_security_policies(assessment_id, security_data)
        
        print(f"✓ Successfully backfilled {len(security_data)} security policies")
        
        db.commit()
        return True
        
    except Exception as e:
        print(f"❌ Error processing assessment {assessment_id}: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()


async def main():
    """Main function to backfill security metadata for all assessments"""
    db = db_instance.SessionLocal()
    
    try:
        assessment_repo = AssessmentRepository(db)
        
        # Get all completed assessments
        assessments = assessment_repo.list_assessments()
        completed_assessments = [a for a in assessments if a.status == 'completed']
        
        print(f"Found {len(completed_assessments)} completed assessments")
        
        if not completed_assessments:
            print("No completed assessments to process")
            return
        
        # Process each assessment
        success_count = 0
        for assessment in completed_assessments:
            success = await backfill_security_for_assessment(assessment.id)
            if success:
                success_count += 1
        
        print(f"\n{'='*60}")
        print(f"SUMMARY")
        print(f"{'='*60}")
        print(f"Total assessments processed: {len(completed_assessments)}")
        print(f"Successful: {success_count}")
        print(f"Failed: {len(completed_assessments) - success_count}")
        
    finally:
        db.close()


if __name__ == "__main__":
    print("Security Metadata Backfill Script")
    print("=" * 60)
    
    # Run the async main function
    asyncio.run(main())
