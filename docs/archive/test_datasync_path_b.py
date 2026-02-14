#!/usr/bin/env python3
"""
Test script for AWS DataSync Manager (Path B)

Demonstrates end-to-end GCS to S3 migration using DataSync with:
- EC2 agent deployment
- Agent activation
- Location setup
- Task creation
- Execution and monitoring
- Failure recovery
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.bq_redshift_migration.aws_datasync_manager import DataSyncManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_datasync_deployment():
    """Test DataSync agent deployment and activation"""
    
    logger.info("=" * 80)
    logger.info("AWS DataSync Manager - Path B Test")
    logger.info("=" * 80)
    
    # Initialize DataSync Manager
    manager = DataSyncManager(
        aws_region=os.getenv('AWS_REGION', 'us-east-1'),
        vpc_id=os.getenv('AWS_VPC_ID'),
        private_subnet_id=os.getenv('AWS_PRIVATE_SUBNET_ID'),
        security_group_id=os.getenv('AWS_SECURITY_GROUP_ID')
    )
    
    instance_id = None
    agent_arn = None
    source_location_arn = None
    destination_location_arn = None
    task_arn = None
    
    try:
        # Step 1: Deploy DataSync Agent
        logger.info("\n" + "=" * 80)
        logger.info("Step 1: Deploying DataSync Agent EC2 Instance")
        logger.info("=" * 80)
        
        instance_id, private_ip = manager.deploy_datasync_agent(
            instance_type='m5.xlarge',
            key_name=os.getenv('AWS_KEY_PAIR_NAME'),
            tags={'Migration': 'BQ-to-Redshift', 'Path': 'B'}
        )
        
        logger.info(f"✓ Agent deployed: {instance_id} at {private_ip}")
        
        # Step 2: Activate Agent
        logger.info("\n" + "=" * 80)
        logger.info("Step 2: Activating DataSync Agent")
        logger.info("=" * 80)
        
        agent_arn = manager.activate_agent(
            agent_private_ip=private_ip,
            activation_region=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        logger.info(f"✓ Agent activated: {agent_arn}")
        
        # Step 3: Create GCS Source Location
        logger.info("\n" + "=" * 80)
        logger.info("Step 3: Creating GCS Source Location")
        logger.info("=" * 80)
        
        source_location_arn = manager.create_gcs_location(
            gcs_bucket=os.getenv('GCS_BUCKET', 'my-gcs-bucket'),
            gcs_hmac_access_key=os.getenv('GCS_HMAC_ACCESS_KEY'),
            gcs_hmac_secret_key=os.getenv('GCS_HMAC_SECRET_KEY'),
            agent_arns=[agent_arn],
            subdirectory='/bigquery-export/'
        )
        
        logger.info(f"✓ GCS location created: {source_location_arn}")
        
        # Step 4: Create S3 Destination Location
        logger.info("\n" + "=" * 80)
        logger.info("Step 4: Creating S3 Destination Location")
        logger.info("=" * 80)
        
        s3_bucket = os.getenv('S3_BUCKET', 'my-s3-bucket')
        s3_bucket_arn = f"arn:aws:s3:::{s3_bucket}"
        
        destination_location_arn = manager.create_s3_location(
            s3_bucket=s3_bucket,
            s3_bucket_arn=s3_bucket_arn,
            iam_role_arn=os.getenv('DATASYNC_S3_ROLE_ARN'),
            subdirectory='/bigquery-data/'
        )
        
        logger.info(f"✓ S3 location created: {destination_location_arn}")
        
        # Step 5: Create Sync Task
        logger.info("\n" + "=" * 80)
        logger.info("Step 5: Creating DataSync Task")
        logger.info("=" * 80)
        
        task_arn = manager.create_sync_task(
            source_location_arn=source_location_arn,
            destination_location_arn=destination_location_arn,
            task_name='GCS-to-S3-BQ-Migration',
            cloudwatch_log_group_arn=os.getenv('CLOUDWATCH_LOG_GROUP_ARN')
        )
        
        logger.info(f"✓ Task created: {task_arn}")
        logger.info("  Transfer Mode: CHANGED (delta sync)")
        logger.info("  Verify Mode: ONLY_FILES_TRANSFERRED")
        
        # Step 6: Start Task Execution
        logger.info("\n" + "=" * 80)
        logger.info("Step 6: Starting Task Execution")
        logger.info("=" * 80)
        
        execution_arn = manager.start_task_execution(task_arn)
        
        logger.info(f"✓ Execution started: {execution_arn}")
        
        # Step 7: Monitor Execution
        logger.info("\n" + "=" * 80)
        logger.info("Step 7: Monitoring Task Execution")
        logger.info("=" * 80)
        logger.info("Note: This will poll every 30 seconds until completion")
        logger.info("Press Ctrl+C to stop monitoring (task will continue)")
        
        try:
            final_status = manager.wait_for_task_completion(
                execution_arn=execution_arn,
                poll_interval=30,
                max_wait_time=86400  # 24 hours
            )
            
            logger.info("\n" + "=" * 80)
            logger.info("Task Execution Completed Successfully!")
            logger.info("=" * 80)
            logger.info(f"Files transferred: {final_status['files_transferred']}")
            logger.info(f"Bytes transferred: {final_status['bytes_transferred']}")
            logger.info(f"Duration: {final_status.get('result', {}).get('TotalDuration', 'N/A')}")
            
        except KeyboardInterrupt:
            logger.info("\nMonitoring stopped by user. Task continues in background.")
            logger.info(f"Check status with execution ARN: {execution_arn}")
        
        # Step 8: Demonstrate Failure Recovery
        logger.info("\n" + "=" * 80)
        logger.info("Step 8: Failure Recovery (Delta Sync)")
        logger.info("=" * 80)
        logger.info("If task fails, re-trigger with same task_arn:")
        logger.info(f"  retry_execution_arn = manager.retry_failed_task('{task_arn}')")
        logger.info("DataSync will automatically transfer only remaining files (delta)")
        
        logger.info("\n" + "=" * 80)
        logger.info("Test Completed Successfully!")
        logger.info("=" * 80)
        
        # Ask user if they want to clean up
        cleanup = input("\nClean up resources? (y/n): ").lower().strip()
        
        if cleanup == 'y':
            logger.info("\nCleaning up resources...")
            manager.cleanup_resources(
                instance_id=instance_id,
                agent_arn=agent_arn,
                task_arn=task_arn,
                source_location_arn=source_location_arn,
                destination_location_arn=destination_location_arn
            )
            logger.info("✓ Cleanup completed")
        else:
            logger.info("\nResources preserved. Clean up manually when done:")
            logger.info(f"  Instance ID: {instance_id}")
            logger.info(f"  Agent ARN: {agent_arn}")
            logger.info(f"  Task ARN: {task_arn}")
        
    except Exception as e:
        logger.error(f"\n✗ Test failed: {e}")
        logger.error("Attempting cleanup...")
        
        try:
            manager.cleanup_resources(
                instance_id=instance_id,
                agent_arn=agent_arn,
                task_arn=task_arn,
                source_location_arn=source_location_arn,
                destination_location_arn=destination_location_arn
            )
        except Exception as cleanup_error:
            logger.error(f"Cleanup failed: {cleanup_error}")
        
        sys.exit(1)


def test_failure_recovery():
    """Test failure recovery with delta sync"""
    
    logger.info("=" * 80)
    logger.info("Testing Failure Recovery with Delta Sync")
    logger.info("=" * 80)
    
    # This assumes you have an existing task ARN from a previous run
    task_arn = input("Enter existing task ARN to retry: ").strip()
    
    if not task_arn:
        logger.error("No task ARN provided")
        return
    
    manager = DataSyncManager()
    
    try:
        logger.info(f"Retrying task: {task_arn}")
        logger.info("DataSync will transfer only remaining files (delta sync)")
        
        execution_arn = manager.retry_failed_task(task_arn)
        
        logger.info(f"✓ Retry execution started: {execution_arn}")
        
        # Monitor the retry
        final_status = manager.wait_for_task_completion(
            execution_arn=execution_arn,
            poll_interval=30
        )
        
        logger.info("\n" + "=" * 80)
        logger.info("Retry Completed Successfully!")
        logger.info("=" * 80)
        logger.info(f"Files transferred (delta): {final_status['files_transferred']}")
        logger.info(f"Bytes transferred (delta): {final_status['bytes_transferred']}")
        
    except Exception as e:
        logger.error(f"Retry failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test AWS DataSync Manager')
    parser.add_argument(
        '--mode',
        choices=['deploy', 'retry'],
        default='deploy',
        help='Test mode: deploy (full test) or retry (test failure recovery)'
    )
    
    args = parser.parse_args()
    
    if args.mode == 'deploy':
        test_datasync_deployment()
    elif args.mode == 'retry':
        test_failure_recovery()

