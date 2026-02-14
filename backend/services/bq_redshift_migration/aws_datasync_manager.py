"""
AWS DataSync Manager for GCS to S3 Migration (Path B)

Automates AWS DataSync deployment and management for large-scale GCS-to-S3 transfers
with resume capability and delta synchronization.
"""

import os
import time
import logging
import boto3
import requests
from typing import Dict, Optional, Tuple
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class DataSyncManager:
    """
    Manages AWS DataSync for GCS to S3 migrations.
    
    Features:
    - EC2 DataSync Agent deployment from SSM AMI
    - Agent activation via local network
    - GCS source location setup with HMAC keys
    - S3 destination location setup
    - Task creation with CHANGED transfer mode
    - Automatic failure recovery with delta sync
    """
    
    def __init__(
        self,
        aws_region: str = None,
        vpc_id: str = None,
        private_subnet_id: str = None,
        security_group_id: str = None
    ):
        """
        Initialize DataSync Manager.
        
        Args:
            aws_region: AWS region for DataSync resources
            vpc_id: VPC ID for EC2 agent
            private_subnet_id: Private subnet ID for EC2 agent
            security_group_id: Security group ID for EC2 agent
        """
        self.region = aws_region or os.getenv('AWS_REGION', 'us-east-1')
        self.vpc_id = vpc_id or os.getenv('AWS_VPC_ID')
        self.private_subnet_id = private_subnet_id or os.getenv('AWS_PRIVATE_SUBNET_ID')
        self.security_group_id = security_group_id or os.getenv('AWS_SECURITY_GROUP_ID')
        
        # Initialize AWS clients
        self.ec2_client = boto3.client('ec2', region_name=self.region)
        self.datasync_client = boto3.client('datasync', region_name=self.region)
        self.ssm_client = boto3.client('ssm', region_name=self.region)
        
        logger.info(f"DataSync Manager initialized for region: {self.region}")
    
    def get_latest_datasync_ami(self) -> str:
        """
        Get the latest AWS DataSync AMI ID from SSM Parameter Store.
        
        Returns:
            str: AMI ID for DataSync agent
        """
        try:
            # AWS publishes DataSync AMI IDs in SSM Parameter Store
            parameter_name = f'/aws/service/datasync/ami-amazon-linux-latest/x86_64'
            
            response = self.ssm_client.get_parameter(Name=parameter_name)
            ami_id = response['Parameter']['Value']
            
            logger.info(f"Latest DataSync AMI: {ami_id}")
            return ami_id
            
        except ClientError as e:
            logger.error(f"Failed to get DataSync AMI from SSM: {e}")
            raise Exception(f"Could not retrieve DataSync AMI: {e}")
    
    def deploy_datasync_agent(
        self,
        instance_type: str = 'm5.xlarge',
        key_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> Tuple[str, str]:
        """
        Deploy EC2 DataSync Agent in private subnet.
        
        Args:
            instance_type: EC2 instance type (default: m5.xlarge)
            key_name: SSH key pair name (optional)
            tags: Additional tags for the instance
            
        Returns:
            Tuple[str, str]: (instance_id, private_ip)
        """
        try:
            logger.info("Deploying DataSync agent EC2 instance...")
            
            # Get latest DataSync AMI
            ami_id = self.get_latest_datasync_ami()
            
            # Prepare instance tags
            instance_tags = {
                'Name': 'DataSync-Agent',
                'Purpose': 'GCS-to-S3-Migration',
                'ManagedBy': 'DataMIQ'
            }
            if tags:
                instance_tags.update(tags)
            
            tag_specifications = [{
                'ResourceType': 'instance',
                'Tags': [{'Key': k, 'Value': v} for k, v in instance_tags.items()]
            }]
            
            # Launch EC2 instance
            launch_params = {
                'ImageId': ami_id,
                'InstanceType': instance_type,
                'SubnetId': self.private_subnet_id,
                'SecurityGroupIds': [self.security_group_id],
                'MinCount': 1,
                'MaxCount': 1,
                'TagSpecifications': tag_specifications,
                'IamInstanceProfile': {
                    'Name': os.getenv('DATASYNC_INSTANCE_PROFILE', 'DataSyncAgentRole')
                }
            }
            
            if key_name:
                launch_params['KeyName'] = key_name
            
            response = self.ec2_client.run_instances(**launch_params)
            
            instance_id = response['Instances'][0]['InstanceId']
            logger.info(f"DataSync agent instance launched: {instance_id}")
            
            # Wait for instance to be running
            logger.info("Waiting for instance to be running...")
            waiter = self.ec2_client.get_waiter('instance_running')
            waiter.wait(InstanceIds=[instance_id])
            
            # Get private IP
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            private_ip = response['Reservations'][0]['Instances'][0]['PrivateIpAddress']
            
            logger.info(f"DataSync agent deployed: {instance_id} at {private_ip}")
            
            # Wait additional time for DataSync agent to initialize
            logger.info("Waiting for DataSync agent to initialize (60 seconds)...")
            time.sleep(60)
            
            return instance_id, private_ip
            
        except ClientError as e:
            logger.error(f"Failed to deploy DataSync agent: {e}")
            raise Exception(f"DataSync agent deployment failed: {e}")
    
    def activate_agent(self, agent_private_ip: str, activation_region: str = None) -> str:
        """
        Activate DataSync agent by retrieving activation key and registering.
        
        Args:
            agent_private_ip: Private IP address of the DataSync agent
            activation_region: AWS region for activation (defaults to self.region)
            
        Returns:
            str: Agent ARN
        """
        try:
            activation_region = activation_region or self.region
            
            logger.info(f"Activating DataSync agent at {agent_private_ip}...")
            
            # Step 1: Get activation key from agent via local network
            activation_key_url = f"http://{agent_private_ip}/?gatewayType=SYNC&activationRegion={activation_region}&no_redirect"
            
            logger.info(f"Retrieving activation key from: {activation_key_url}")
            
            # Retry logic for activation key retrieval
            max_retries = 5
            retry_delay = 30
            
            for attempt in range(max_retries):
                try:
                    response = requests.get(activation_key_url, timeout=30)
                    
                    if response.status_code == 200:
                        # Extract activation key from redirect URL
                        # Format: http://...?activationKey=XXXXX-XXXXX-XXXXX-XXXXX-XXXXX
                        if 'activationKey=' in response.text:
                            activation_key = response.text.split('activationKey=')[1].split('&')[0]
                            logger.info(f"Activation key retrieved: {activation_key[:20]}...")
                            break
                        else:
                            activation_key = response.text.strip()
                            logger.info(f"Activation key retrieved: {activation_key[:20]}...")
                            break
                    else:
                        logger.warning(f"Attempt {attempt + 1}/{max_retries}: HTTP {response.status_code}")
                        
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Attempt {attempt + 1}/{max_retries}: {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    raise Exception("Failed to retrieve activation key after all retries")
            
            # Step 2: Register agent with DataSync
            logger.info("Registering agent with AWS DataSync...")
            
            response = self.datasync_client.create_agent(
                ActivationKey=activation_key,
                AgentName=f'DataSync-Agent-{agent_private_ip}',
                Tags=[
                    {'Key': 'Purpose', 'Value': 'GCS-to-S3-Migration'},
                    {'Key': 'ManagedBy', 'Value': 'DataMIQ'}
                ]
            )
            
            agent_arn = response['AgentArn']
            logger.info(f"DataSync agent activated: {agent_arn}")
            
            return agent_arn
            
        except Exception as e:
            logger.error(f"Failed to activate DataSync agent: {e}")
            raise Exception(f"Agent activation failed: {e}")
    
    def create_gcs_location(
        self,
        gcs_bucket: str,
        gcs_hmac_access_key: str,
        gcs_hmac_secret_key: str,
        agent_arns: list,
        subdirectory: str = '/'
    ) -> str:
        """
        Create DataSync location for GCS source using HMAC keys.
        
        Args:
            gcs_bucket: GCS bucket name
            gcs_hmac_access_key: GCS HMAC access key
            gcs_hmac_secret_key: GCS HMAC secret key
            agent_arns: List of DataSync agent ARNs
            subdirectory: Subdirectory within bucket (default: /)
            
        Returns:
            str: Location ARN for GCS
        """
        try:
            logger.info(f"Creating DataSync location for GCS bucket: {gcs_bucket}")
            
            # GCS is accessed via S3-compatible API at storage.googleapis.com
            response = self.datasync_client.create_location_object_storage(
                ServerHostname='storage.googleapis.com',
                ServerPort=443,
                ServerProtocol='HTTPS',
                Subdirectory=subdirectory,
                BucketName=gcs_bucket,
                AccessKey=gcs_hmac_access_key,
                SecretKey=gcs_hmac_secret_key,
                AgentArns=agent_arns,
                Tags=[
                    {'Key': 'Source', 'Value': 'GCS'},
                    {'Key': 'Bucket', 'Value': gcs_bucket},
                    {'Key': 'ManagedBy', 'Value': 'DataMIQ'}
                ]
            )
            
            location_arn = response['LocationArn']
            logger.info(f"GCS location created: {location_arn}")
            
            return location_arn
            
        except ClientError as e:
            logger.error(f"Failed to create GCS location: {e}")
            raise Exception(f"GCS location creation failed: {e}")
    
    def create_s3_location(
        self,
        s3_bucket: str,
        s3_bucket_arn: str,
        iam_role_arn: str,
        subdirectory: str = '/'
    ) -> str:
        """
        Create DataSync location for S3 destination.
        
        Args:
            s3_bucket: S3 bucket name
            s3_bucket_arn: S3 bucket ARN
            iam_role_arn: IAM role ARN for S3 access
            subdirectory: Subdirectory within bucket (default: /)
            
        Returns:
            str: Location ARN for S3
        """
        try:
            logger.info(f"Creating DataSync location for S3 bucket: {s3_bucket}")
            
            response = self.datasync_client.create_location_s3(
                S3BucketArn=s3_bucket_arn,
                Subdirectory=subdirectory,
                S3Config={
                    'BucketAccessRoleArn': iam_role_arn
                },
                Tags=[
                    {'Key': 'Destination', 'Value': 'S3'},
                    {'Key': 'Bucket', 'Value': s3_bucket},
                    {'Key': 'ManagedBy', 'Value': 'DataMIQ'}
                ]
            )
            
            location_arn = response['LocationArn']
            logger.info(f"S3 location created: {location_arn}")
            
            return location_arn
            
        except ClientError as e:
            logger.error(f"Failed to create S3 location: {e}")
            raise Exception(f"S3 location creation failed: {e}")
    
    def create_sync_task(
        self,
        source_location_arn: str,
        destination_location_arn: str,
        task_name: str,
        cloudwatch_log_group_arn: Optional[str] = None
    ) -> str:
        """
        Create DataSync task with CHANGED transfer mode for delta sync.
        
        Args:
            source_location_arn: Source location ARN (GCS)
            destination_location_arn: Destination location ARN (S3)
            task_name: Name for the sync task
            cloudwatch_log_group_arn: CloudWatch log group ARN (optional)
            
        Returns:
            str: Task ARN
        """
        try:
            logger.info(f"Creating DataSync task: {task_name}")
            
            # Task options for delta sync and verification
            options = {
                'VerifyMode': 'ONLY_FILES_TRANSFERRED',  # Verify only transferred files
                'OverwriteMode': 'ALWAYS',  # Overwrite existing files
                'TransferMode': 'CHANGED',  # Only transfer changed/new files (delta sync)
                'Atime': 'BEST_EFFORT',  # Preserve access time
                'Mtime': 'PRESERVE',  # Preserve modification time
                'Uid': 'NONE',  # Don't preserve UID
                'Gid': 'NONE',  # Don't preserve GID
                'PreserveDeletedFiles': 'PRESERVE',  # Don't delete files from destination
                'PreserveDevices': 'NONE',  # Don't preserve device files
                'PosixPermissions': 'NONE',  # Don't preserve POSIX permissions
                'BytesPerSecond': -1,  # No bandwidth limit
                'TaskQueueing': 'ENABLED',  # Enable task queueing
                'LogLevel': 'TRANSFER'  # Log transferred files
            }
            
            create_params = {
                'SourceLocationArn': source_location_arn,
                'DestinationLocationArn': destination_location_arn,
                'Name': task_name,
                'Options': options,
                'Tags': [
                    {'Key': 'Purpose', 'Value': 'GCS-to-S3-Migration'},
                    {'Key': 'ManagedBy', 'Value': 'DataMIQ'}
                ]
            }
            
            # Add CloudWatch logging if provided
            if cloudwatch_log_group_arn:
                create_params['CloudWatchLogGroupArn'] = cloudwatch_log_group_arn
            
            response = self.datasync_client.create_task(**create_params)
            
            task_arn = response['TaskArn']
            logger.info(f"DataSync task created: {task_arn}")
            logger.info(f"Transfer mode: CHANGED (delta sync enabled)")
            logger.info(f"Verify mode: ONLY_FILES_TRANSFERRED")
            
            return task_arn
            
        except ClientError as e:
            logger.error(f"Failed to create DataSync task: {e}")
            raise Exception(f"Task creation failed: {e}")
    
    def start_task_execution(self, task_arn: str) -> str:
        """
        Start DataSync task execution.
        
        Args:
            task_arn: Task ARN to execute
            
        Returns:
            str: Task execution ARN
        """
        try:
            logger.info(f"Starting DataSync task execution: {task_arn}")
            
            response = self.datasync_client.start_task_execution(
                TaskArn=task_arn
            )
            
            execution_arn = response['TaskExecutionArn']
            logger.info(f"Task execution started: {execution_arn}")
            
            return execution_arn
            
        except ClientError as e:
            logger.error(f"Failed to start task execution: {e}")
            raise Exception(f"Task execution failed to start: {e}")
    
    def get_task_execution_status(self, execution_arn: str) -> Dict:
        """
        Get status of a task execution.
        
        Args:
            execution_arn: Task execution ARN
            
        Returns:
            Dict: Execution status details
        """
        try:
            response = self.datasync_client.describe_task_execution(
                TaskExecutionArn=execution_arn
            )
            
            status = {
                'status': response['Status'],
                'bytes_written': response.get('BytesWritten', 0),
                'bytes_transferred': response.get('BytesTransferred', 0),
                'files_transferred': response.get('FilesTransferred', 0),
                'start_time': response.get('StartTime'),
                'estimated_files_to_transfer': response.get('EstimatedFilesToTransfer', 0),
                'estimated_bytes_to_transfer': response.get('EstimatedBytesToTransfer', 0),
                'result': response.get('Result', {})
            }
            
            return status
            
        except ClientError as e:
            logger.error(f"Failed to get task execution status: {e}")
            raise Exception(f"Could not retrieve execution status: {e}")
    
    def retry_failed_task(self, task_arn: str) -> str:
        """
        Retry a failed task. DataSync will automatically transfer only the delta
        (remaining files) due to CHANGED transfer mode.
        
        Args:
            task_arn: Task ARN to retry
            
        Returns:
            str: New task execution ARN
        """
        try:
            logger.info(f"Retrying failed task: {task_arn}")
            logger.info("DataSync will transfer only remaining files (delta sync)")
            
            # Simply start a new execution - DataSync handles delta automatically
            execution_arn = self.start_task_execution(task_arn)
            
            logger.info(f"Task retry initiated: {execution_arn}")
            
            return execution_arn
            
        except Exception as e:
            logger.error(f"Failed to retry task: {e}")
            raise Exception(f"Task retry failed: {e}")
    
    def wait_for_task_completion(
        self,
        execution_arn: str,
        poll_interval: int = 30,
        max_wait_time: int = 86400  # 24 hours
    ) -> Dict:
        """
        Wait for task execution to complete.
        
        Args:
            execution_arn: Task execution ARN
            poll_interval: Seconds between status checks (default: 30)
            max_wait_time: Maximum wait time in seconds (default: 24 hours)
            
        Returns:
            Dict: Final execution status
        """
        try:
            logger.info(f"Waiting for task execution to complete: {execution_arn}")
            
            start_time = time.time()
            
            while True:
                # Check if max wait time exceeded
                if time.time() - start_time > max_wait_time:
                    raise Exception(f"Task execution exceeded maximum wait time of {max_wait_time} seconds")
                
                # Get current status
                status = self.get_task_execution_status(execution_arn)
                
                current_status = status['status']
                logger.info(f"Task status: {current_status} | "
                          f"Files: {status['files_transferred']}/{status['estimated_files_to_transfer']} | "
                          f"Bytes: {status['bytes_transferred']}/{status['estimated_bytes_to_transfer']}")
                
                # Check if completed
                if current_status == 'SUCCESS':
                    logger.info("Task execution completed successfully")
                    return status
                
                elif current_status in ['ERROR', 'FAILED']:
                    logger.error(f"Task execution failed: {status.get('result', {})}")
                    raise Exception(f"Task execution failed: {status.get('result', {})}")
                
                # Wait before next poll
                time.sleep(poll_interval)
                
        except Exception as e:
            logger.error(f"Error waiting for task completion: {e}")
            raise
    
    def cleanup_resources(
        self,
        instance_id: Optional[str] = None,
        agent_arn: Optional[str] = None,
        task_arn: Optional[str] = None,
        source_location_arn: Optional[str] = None,
        destination_location_arn: Optional[str] = None
    ):
        """
        Clean up DataSync resources.
        
        Args:
            instance_id: EC2 instance ID to terminate
            agent_arn: Agent ARN to delete
            task_arn: Task ARN to delete
            source_location_arn: Source location ARN to delete
            destination_location_arn: Destination location ARN to delete
        """
        try:
            logger.info("Cleaning up DataSync resources...")
            
            # Delete task
            if task_arn:
                try:
                    self.datasync_client.delete_task(TaskArn=task_arn)
                    logger.info(f"Deleted task: {task_arn}")
                except ClientError as e:
                    logger.warning(f"Could not delete task: {e}")
            
            # Delete locations
            if source_location_arn:
                try:
                    self.datasync_client.delete_location(LocationArn=source_location_arn)
                    logger.info(f"Deleted source location: {source_location_arn}")
                except ClientError as e:
                    logger.warning(f"Could not delete source location: {e}")
            
            if destination_location_arn:
                try:
                    self.datasync_client.delete_location(LocationArn=destination_location_arn)
                    logger.info(f"Deleted destination location: {destination_location_arn}")
                except ClientError as e:
                    logger.warning(f"Could not delete destination location: {e}")
            
            # Delete agent
            if agent_arn:
                try:
                    self.datasync_client.delete_agent(AgentArn=agent_arn)
                    logger.info(f"Deleted agent: {agent_arn}")
                except ClientError as e:
                    logger.warning(f"Could not delete agent: {e}")
            
            # Terminate EC2 instance
            if instance_id:
                try:
                    self.ec2_client.terminate_instances(InstanceIds=[instance_id])
                    logger.info(f"Terminated EC2 instance: {instance_id}")
                except ClientError as e:
                    logger.warning(f"Could not terminate instance: {e}")
            
            logger.info("Resource cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            raise

