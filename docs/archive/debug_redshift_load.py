"""
Debug Script for S3 to Redshift Load Issue

This script investigates why data is not loading from S3 to Redshift
even though the migration shows as completed.

Usage:
    python debug_redshift_load.py <migration_id>
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import logging
from sqlalchemy.orm import Session
from database import get_db
from models.bq_redshift_migration import MigrationBQRedshift, MigrationLog
from models.connection import Connection
from services.encryption_service import get_encryption_service
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)


def print_subsection(title: str):
    """Print a formatted subsection header"""
    print("\n" + "-"*80)
    print(f"  {title}")
    print("-"*80)


def debug_migration(migration_id: int):
    """
    Debug a migration to find why S3 to Redshift load is not working.
    
    Args:
        migration_id: Migration ID to debug
    """
    db: Session = next(get_db())
    
    try:
        print_section(f"DEBUGGING MIGRATION {migration_id}")
        
        # Step 1: Get migration details
        print_subsection("Step 1: Fetching Migration Details")
        migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
        
        if not migration:
            print(f"❌ ERROR: Migration {migration_id} not found in database")
            return False
        
        print(f"✓ Migration found: {migration.migration_name}")
        print(f"  Status: {migration.status}")
        print(f"  Current Stage: {migration.current_stage}")
        print(f"  Pathway: {migration.pathway}")
        print(f"  Created: {migration.created_at}")
        print(f"  Updated: {migration.updated_at}")
        
        # Step 2: Check checkpoint data
        print_subsection("Step 2: Analyzing Checkpoint Data")
        checkpoint_data = migration.checkpoint_data or {}
        
        print(f"Checkpoint keys: {list(checkpoint_data.keys())}")
        
        export_completed = checkpoint_data.get('export_completed_at')
        transfer_completed = checkpoint_data.get('transfer_completed_at')
        load_completed = checkpoint_data.get('load_completed_at')
        
        print(f"\nStage Completion Status:")
        print(f"  Export:   {'✓ Completed' if export_completed else '✗ Not completed'}")
        if export_completed:
            print(f"            at {export_completed}")
        
        print(f"  Transfer: {'✓ Completed' if transfer_completed else '✗ Not completed'}")
        if transfer_completed:
            print(f"            at {transfer_completed}")
        
        print(f"  Load:     {'✓ Completed' if load_completed else '✗ Not completed'}")
        if load_completed:
            print(f"            at {load_completed}")
        
        # Step 3: Check export results
        print_subsection("Step 3: Checking Export Results")
        export_results = checkpoint_data.get('export_results', [])
        
        if not export_results:
            print("❌ ERROR: No export results found in checkpoint data")
            print("   The export stage may not have completed successfully")
            return False
        
        print(f"✓ Found {len(export_results)} export results")
        
        successful_exports = [r for r in export_results if r.get('success')]
        failed_exports = [r for r in export_results if not r.get('success')]
        
        print(f"  Successful: {len(successful_exports)}")
        print(f"  Failed: {len(failed_exports)}")
        
        if successful_exports:
            print("\nSuccessful Exports:")
            for result in successful_exports:
                table = result.get('table', result.get('table_id', 'unknown'))
                schema = result.get('schema', [])
                print(f"  - {table}: {len(schema)} columns")
        
        if failed_exports:
            print("\n❌ Failed Exports:")
            for result in failed_exports:
                table = result.get('table', result.get('table_id', 'unknown'))
                error = result.get('error', 'Unknown error')
                print(f"  - {table}: {error}")
        
        # Step 4: Check transfer results
        print_subsection("Step 4: Checking Transfer Results")
        transfer_stats = checkpoint_data.get('transfer_stats', {})
        
        if not transfer_stats:
            print("❌ ERROR: No transfer stats found in checkpoint data")
            print("   The transfer stage may not have completed successfully")
            return False
        
        print(f"✓ Transfer stats found")
        print(f"  Status: {transfer_stats.get('status', 'unknown')}")
        print(f"  Files found: {transfer_stats.get('files_found', 0)}")
        print(f"  Files transferred: {transfer_stats.get('files_transferred', 0)}")
        print(f"  Files failed: {transfer_stats.get('files_failed', 0)}")
        print(f"  Bytes transferred: {transfer_stats.get('bytes_transferred', 0):,}")
        print(f"  Duration: {transfer_stats.get('duration_seconds', 0):.2f}s")
        
        # Step 5: Check load results
        print_subsection("Step 5: Checking Load Results")
        load_results = checkpoint_data.get('load_results', [])
        load_summary = checkpoint_data.get('load_summary', {})
        
        if not load_results and not load_summary:
            print("❌ ISSUE FOUND: No load results in checkpoint data")
            print("   This indicates the load stage was never executed or failed silently")
            print("\n   Possible reasons:")
            print("   1. Load stage was skipped due to missing configuration")
            print("   2. Load stage failed before creating results")
            print("   3. Load stage was never called by the orchestrator")
            
            # Check if load stage should have run
            if export_completed and transfer_completed:
                print("\n   ⚠️  Export and transfer completed, but load did not run!")
                print("   This is the root cause of the issue.")
            
            return False
        
        if load_summary:
            print(f"✓ Load summary found")
            print(f"  Successful loads: {load_summary.get('successful_loads', 0)}")
            print(f"  Failed loads: {load_summary.get('failed_loads', 0)}")
            print(f"  Total rows loaded: {load_summary.get('total_rows_loaded', 0):,}")
        
        if load_results:
            print(f"\n✓ Found {len(load_results)} load results")
            
            successful_loads = [r for r in load_results if r.get('success')]
            failed_loads = [r for r in load_results if not r.get('success')]
            
            if successful_loads:
                print("\nSuccessful Loads:")
                for result in successful_loads:
                    table = result.get('table', 'unknown')
                    rows = result.get('rows_loaded', 0)
                    print(f"  - {table}: {rows:,} rows")
            
            if failed_loads:
                print("\n❌ Failed Loads:")
                for result in failed_loads:
                    table = result.get('table', 'unknown')
                    error = result.get('error', 'Unknown error')
                    print(f"  - {table}: {error}")
        
        # Step 6: Check target configuration
        print_subsection("Step 6: Validating Target Configuration")
        
        print(f"Target Cluster: {migration.target_cluster or '❌ NOT SET'}")
        print(f"Target Database: {migration.target_database or '❌ NOT SET'}")
        print(f"Target Schema: {migration.target_schema or '❌ NOT SET'}")
        print(f"IAM Role ARN: {migration.iam_role_arn or '❌ NOT SET'}")
        
        if not migration.target_cluster:
            print("\n❌ ERROR: Target cluster not configured")
            return False
        
        if not migration.target_database:
            print("\n❌ ERROR: Target database not configured")
            return False
        
        if not migration.iam_role_arn:
            print("\n❌ WARNING: IAM role ARN not configured")
            print("   This is required for Redshift to access S3")
        
        # Step 7: Check target connection
        print_subsection("Step 7: Checking Target Connection")
        
        if not migration.target_connection_id:
            print("❌ ERROR: Target connection ID not set")
            return False
        
        target_conn = db.query(Connection).filter_by(id=migration.target_connection_id).first()
        
        if not target_conn:
            print(f"❌ ERROR: Target connection {migration.target_connection_id} not found")
            return False
        
        print(f"✓ Target connection found: {target_conn.name}")
        print(f"  Type: {target_conn.connection_type}")
        print(f"  Status: {target_conn.status}")
        
        # Check connection params
        conn_params = target_conn.connection_params or {}
        print(f"\nConnection Parameters:")
        print(f"  Host: {conn_params.get('host', '❌ NOT SET')}")
        print(f"  Port: {conn_params.get('port', '❌ NOT SET')}")
        print(f"  Database: {conn_params.get('database', '❌ NOT SET')}")
        print(f"  Username: {conn_params.get('username', '❌ NOT SET')}")
        print(f"  Password: {'✓ SET' if conn_params.get('password_encrypted') else '❌ NOT SET'}")
        print(f"  IAM Role: {conn_params.get('iam_role_arn', '❌ NOT SET')}")
        
        # Step 8: Check S3 configuration
        print_subsection("Step 8: Validating S3 Configuration")
        
        print(f"S3 Bucket: {migration.s3_bucket or '❌ NOT SET'}")
        print(f"S3 Path: {migration.s3_path or '(root)'}")
        print(f"AWS Access Key: {migration.aws_access_key_id or '❌ NOT SET'}")
        print(f"AWS Secret Key: {'✓ ENCRYPTED' if migration.aws_secret_access_key_encrypted else '❌ NOT SET'}")
        
        if not migration.s3_bucket:
            print("\n❌ ERROR: S3 bucket not configured")
            return False
        
        # Step 9: Check migration logs
        print_subsection("Step 9: Analyzing Migration Logs")
        
        logs = db.query(MigrationLog).filter_by(
            migration_id=migration_id
        ).order_by(MigrationLog.created_at.desc()).limit(50).all()
        
        if not logs:
            print("⚠️  WARNING: No logs found for this migration")
            print("   This could indicate the migration never started")
        else:
            print(f"✓ Found {len(logs)} recent log entries")
            
            # Group by stage
            stages = {}
            for log in logs:
                stage = log.stage
                if stage not in stages:
                    stages[stage] = []
                stages[stage].append(log)
            
            print(f"\nLogs by stage:")
            for stage, stage_logs in stages.items():
                print(f"  {stage}: {len(stage_logs)} entries")
            
            # Show recent errors
            error_logs = [log for log in logs if log.log_level in ('ERROR', 'CRITICAL')]
            if error_logs:
                print(f"\n❌ Found {len(error_logs)} error logs:")
                for log in error_logs[:5]:  # Show first 5 errors
                    print(f"\n  [{log.log_level}] {log.stage} - {log.created_at}")
                    print(f"  {log.message}")
                    if log.error_code:
                        print(f"  Error Code: {log.error_code}")
            
            # Show load stage logs
            load_logs = [log for log in logs if log.stage == 'load']
            if load_logs:
                print(f"\n✓ Found {len(load_logs)} load stage logs:")
                for log in load_logs[:10]:  # Show first 10
                    print(f"  [{log.log_level}] {log.message[:100]}")
            else:
                print(f"\n❌ ISSUE FOUND: No load stage logs found")
                print("   This confirms the load stage was never executed")
        
        # Step 10: Diagnosis Summary
        print_section("DIAGNOSIS SUMMARY")
        
        issues_found = []
        
        # Check each stage
        if not export_completed:
            issues_found.append("Export stage not completed")
        
        if not transfer_completed:
            issues_found.append("Transfer stage not completed")
        
        if not load_completed:
            issues_found.append("Load stage not completed")
        
        if not load_results and not load_summary:
            issues_found.append("Load stage was never executed (no results in checkpoint)")
        
        if not migration.target_cluster:
            issues_found.append("Target cluster not configured")
        
        if not migration.iam_role_arn and not conn_params.get('iam_role_arn'):
            issues_found.append("IAM role ARN not configured")
        
        if not logs or not [log for log in logs if log.stage == 'load']:
            issues_found.append("No load stage logs found")
        
        if issues_found:
            print("\n❌ ISSUES FOUND:")
            for i, issue in enumerate(issues_found, 1):
                print(f"  {i}. {issue}")
            
            print("\n📋 RECOMMENDED ACTIONS:")
            
            if "Load stage was never executed" in str(issues_found):
                print("\n  1. Check orchestrator logic:")
                print("     - Verify pathway_c.py _execute_load_stage() is being called")
                print("     - Check if there are any conditions preventing load stage execution")
                print("     - Review orchestrator.py _execute_migration() flow")
                
                print("\n  2. Check target configuration:")
                print("     - Ensure target_cluster, target_database are set")
                print("     - Verify IAM role ARN is configured")
                print("     - Check target connection has valid credentials")
                
                print("\n  3. Review pathway C execute() method:")
                print("     - Check stage transition logic")
                print("     - Verify checkpoint data is being read correctly")
                print("     - Look for any exceptions being swallowed")
            
            if "IAM role ARN not configured" in str(issues_found):
                print("\n  4. Configure IAM role:")
                print("     - Add iam_role_arn to migration configuration")
                print("     - Or add it to target connection parameters")
                print("     - Ensure role has S3 read permissions")
            
            return False
        else:
            print("\n✓ No obvious issues found in configuration")
            print("  The load stage appears to have executed successfully")
            print("\n  Next steps:")
            print("  1. Check Redshift cluster directly for loaded data")
            print("  2. Review Redshift STL_LOAD_ERRORS table")
            print("  3. Verify IAM role permissions")
            
            return True
    
    except Exception as e:
        print_section("ERROR DURING DEBUGGING")
        print(f"❌ Exception occurred: {e}")
        import traceback
        print("\nFull traceback:")
        print(traceback.format_exc())
        return False
    
    finally:
        db.close()


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python debug_redshift_load.py <migration_id>")
        print("\nExample:")
        print("  python debug_redshift_load.py 123")
        sys.exit(1)
    
    try:
        migration_id = int(sys.argv[1])
    except ValueError:
        print(f"Error: Invalid migration ID '{sys.argv[1]}'. Must be an integer.")
        sys.exit(1)
    
    success = debug_migration(migration_id)
    
    if success:
        print("\n" + "="*80)
        print("✓ Debugging completed successfully")
        print("="*80)
        sys.exit(0)
    else:
        print("\n" + "="*80)
        print("❌ Issues found - see details above")
        print("="*80)
        sys.exit(1)


if __name__ == '__main__':
    main()
