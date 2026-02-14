"""
Test BigQuery Assessment Service - Complete Implementation

This script tests the comprehensive BigQuery assessment with all metadata collection.
"""

import asyncio
import json
from database import get_db
from services.bigquery_assessment_service import BigQueryAssessmentService
from repositories.assessment_repository import AssessmentRepository
from repositories.connection_repository import ConnectionRepository


async def test_bigquery_assessment():
    """Test complete BigQuery assessment"""
    
    print("=" * 80)
    print("BigQuery Assessment - Complete Test")
    print("=" * 80)
    
    # Get database session
    db = next(get_db())
    
    try:
        # 1. Get BigQuery connection from database
        print("\n1. Fetching BigQuery connection...")
        conn_repo = ConnectionRepository(db)
        connections = conn_repo.list_connections()
        
        bigquery_conn = None
        for conn in connections:
            if conn.database.lower() == 'bigquery' and conn.type == 'source':
                bigquery_conn = conn
                break
        
        if not bigquery_conn:
            print("✗ No BigQuery connection found")
            print("Please create a BigQuery source connection first")
            return
        
        print(f"✓ Found BigQuery connection: {bigquery_conn.name} (ID: {bigquery_conn.id})")
        
        # 2. Get connection credentials
        print("\n2. Loading connection credentials...")
        connection_string = conn_repo.get_decrypted_connection_string(bigquery_conn.id)
        
        # Parse connection string to get credentials
        # Format: bigquery://project_id?credentials_json=...
        if '?' in connection_string:
            base, params = connection_string.split('?', 1)
            project_id = base.replace('bigquery://', '')
            
            # Parse parameters
            params_dict = {}
            for param in params.split('&'):
                if '=' in param:
                    key, value = param.split('=', 1)
                    params_dict[key] = value
            
            credentials_json = params_dict.get('credentials_json', '')
            
            connection_params = {
                'project_id': project_id,
                'credentials_json': credentials_json
            }
            
            print(f"✓ Project ID: {project_id}")
        else:
            print("✗ Invalid connection string format")
            return
        
        # 3. Create assessment record
        print("\n3. Creating assessment record...")
        assessment_repo = AssessmentRepository(db)
        
        # Find a Redshift target connection (optional)
        target_conn_id = None
        for conn in connections:
            if conn.database.lower() == 'redshift' and conn.type == 'target':
                target_conn_id = conn.id
                break
        
        assessment = assessment_repo.create_assessment(
            source_connection_id=bigquery_conn.id,
            target_connection_id=target_conn_id,
            project_id=project_id,
            status='pending',
            created_by='test_script'
        )
        
        print(f"✓ Created assessment ID: {assessment.id}")
        
        # 4. Initialize BigQuery service
        print("\n4. Initializing BigQuery service...")
        bq_service = BigQueryAssessmentService(connection_params)
        print("✓ BigQuery client initialized")
        
        # 5. Run full assessment
        print("\n5. Running full assessment...")
        print("-" * 80)
        
        result = await bq_service.run_full_assessment(assessment.id, db)
        
        print("-" * 80)
        print("\n6. Assessment Results:")
        print(json.dumps(result, indent=2, default=str))
        
        # 7. Verify data in database
        print("\n7. Verifying data in database...")
        assessment = assessment_repo.get_by_id(assessment.id)
        
        print(f"\nAssessment Status: {assessment.status}")
        print(f"Total Datasets: {assessment.total_datasets}")
        print(f"Total Tables: {assessment.total_tables}")
        print(f"Total Views: {assessment.total_views}")
        print(f"Total Routines: {assessment.total_routines}")
        print(f"Total ML Models: {assessment.total_ml_models}")
        print(f"Total Size: {assessment.total_size_mb / 1024:.2f} GB")
        
        # 8. Get dataset summary
        print("\n8. Dataset Summary:")
        dataset_summary = assessment_repo.get_dataset_summary(assessment.id)
        for ds in dataset_summary[:5]:  # Show first 5
            print(f"  - {ds['dataset_name']}: {ds['table_count']} tables, {ds['total_size_mb']:.2f} MB")
        
        if len(dataset_summary) > 5:
            print(f"  ... and {len(dataset_summary) - 5} more datasets")
        
        print("\n" + "=" * 80)
        print("✓ Assessment completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def main():
    """Main entry point"""
    asyncio.run(test_bigquery_assessment())


if __name__ == "__main__":
    main()
