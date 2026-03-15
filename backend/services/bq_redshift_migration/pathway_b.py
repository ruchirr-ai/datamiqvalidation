"""
Pathway B: GCS to S3 Migration using AWS DataSync Agent on GCP VM

Architecture:
  DataSync Agent runs as a GCP Compute Engine VM inside the user's VPC.
  This gives the agent private network access to GCS (no public internet for reads).
  The agent then transfers data to S3 over an encrypted channel.

Flow:
  1. Deploy DataSync agent VM in GCP (or use existing VM)
  2. Activate the agent with AWS DataSync service
  3. Create GCS source location (object-storage via HMAC)
  4. Create S3 destination location
  5. Create and execute DataSync transfer task
  6. Monitor until completion
  7. Optionally clean up GCP VM

User options:
  - create_vm: App creates a new GCP Compute Engine VM with the DataSync agent image
  - existing_vm: User provides IP of an existing VM running the DataSync agent
"""

import boto3
import time
import logging
import requests
from typing import Dict, Any, Optional, List, Tuple
from botocore.exceptions import ClientError
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

# AWS DataSync agent OVA is deployed as a VM in GCP.
# Google publishes a community image for this, or user imports the OVA.
# The official approach: download OVA from AWS console, import to GCP as custom image.
DATASYNC_AGENT_GCP_IMAGE_FAMILY = "datasync-agent"
DATASYNC_AGENT_GCP_IMAGE_PROJECT = None  # User's project (custom image)


class GCPDataSyncAgent:
    """
    Manages the AWS DataSync agent running on a GCP Compute Engine VM.
    
    The agent VM sits inside the GCP VPC, giving it private access to GCS.
    It communicates with the AWS DataSync service to transfer data to S3.
    """
    
    def __init__(
        self,
        gcp_project_id: str,
        gcp_zone: str,
        aws_region: str,
        service_account_info: Optional[Dict] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        datasync_role_arn: Optional[str] = None,
    ):
        self.gcp_project_id = gcp_project_id
        self.gcp_zone = gcp_zone
        self.aws_region = aws_region
        self.service_account_info = service_account_info
        
        # Store AWS credentials for use in _ensure_datasync_image_exists and boto3 calls
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        
        # S3 bucket for AMI export and GCS bucket for image import
        # These are set by the caller (PathwayB._execute_transfer_stage) before create_agent_vm
        self._export_s3_bucket: Optional[str] = None
        self._gcs_bucket: Optional[str] = None
        
        # Initialize GCP Compute client
        try:
            from google.cloud import compute_v1
            from google.oauth2 import service_account as sa_module
            
            if service_account_info:
                credentials = sa_module.Credentials.from_service_account_info(service_account_info)
                self.compute_client = compute_v1.InstancesClient(credentials=credentials)
            else:
                self.compute_client = compute_v1.InstancesClient()
            
            logger.info("GCP Compute client initialized")
        except ImportError:
            logger.warning("google-cloud-compute not installed, GCP VM creation will not work")
            self.compute_client = None
        
        # Initialize AWS DataSync client (assumes IAM role if DATASYNC_ROLE_ARN is set)
        from shared.datasync_client import create_datasync_client
        self.datasync_client = create_datasync_client(
            region=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            role_arn=datasync_role_arn,
        )
        
        self.vm_instance_name: Optional[str] = None
        self.agent_ip: Optional[str] = None
        self.agent_arn: Optional[str] = None
    
    def _ensure_datasync_image_exists(self) -> str:
        """
        This method is no longer used - we expect users to manually create the DataSync agent VM.
        Kept for backward compatibility but will raise an error if called.
        """
        raise Exception(
            "Automatic DataSync agent VM creation is not supported. "
            "Please manually create the VM following the setup guide and use 'Use Existing VM' mode."
        )
    
    def create_agent_vm(
        self,
        machine_type: str = "n1-standard-4",
        network: str = "default",
        subnet: str = "",
        datasync_image: str = "",
    ) -> str:
        """
        This method is no longer used - we expect users to manually create the DataSync agent VM.
        
        Automatic VM creation has been removed in favor of a manual setup process for reliability.
        Users should follow the setup guide to create the VM and then provide its IP address.
        
        Raises:
            Exception with instructions
        """
        raise Exception(
            "Automatic DataSync agent VM creation is not supported. "
            "Please manually create the VM following the AWS_DATASYNC_SETUP_GUIDE.md and use 'Use Existing VM' mode."
        )
    
    def _wait_for_gcp_operation(self, operation, zone: str, timeout: int = 300):
        """Wait for a GCP zone operation to complete."""
        from google.cloud import compute_v1
        from google.oauth2 import service_account as sa_module
        
        if self.service_account_info:
            credentials = sa_module.Credentials.from_service_account_info(self.service_account_info)
            op_client = compute_v1.ZoneOperationsClient(credentials=credentials)
        else:
            op_client = compute_v1.ZoneOperationsClient()
        
        start = time.time()
        
        while time.time() - start < timeout:
            result = op_client.get(
                project=self.gcp_project_id,
                zone=zone,
                operation=operation.name,
            )
            if result.status == compute_v1.Operation.Status.DONE:
                if result.error:
                    raise Exception(f"GCP operation failed: {result.error}")
                return result
            time.sleep(5)
        
        raise Exception(f"GCP operation timed out after {timeout}s")
    
    def get_activation_key(self, agent_ip: str) -> str:
        """
        Get activation key from the DataSync agent running on the GCP VM.
        
        The agent exposes an HTTP endpoint on port 80 for activation.
        This must be called from a machine that can reach the agent's IP.
        
        For GCP VMs, this means the backend must be able to reach the VM's
        internal IP (e.g., via VPN, Cloud Interconnect, or running in same VPC).
        """
        logger.info(f"Retrieving activation key from agent at {agent_ip}")
        
        activation_url = (
            f"http://{agent_ip}/?gatewayType=SYNC"
            f"&activationRegion={self.aws_region}"
            f"&no_redirect"
        )
        
        # Retry a few times as agent may still be booting
        for attempt in range(5):
            try:
                response = requests.get(activation_url, timeout=30)
                response.raise_for_status()
                activation_key = response.text.strip()
                logger.info("Activation key retrieved successfully")
                return activation_key
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt + 1}/5 failed: {e}")
                if attempt < 4:
                    time.sleep(30)
        
        raise Exception(f"Failed to get activation key from {agent_ip} after 5 attempts")
    
    def activate_agent(self, activation_key: str) -> str:
        """Activate the DataSync agent with AWS."""
        logger.info("Activating DataSync agent with AWS")
        
        response = self.datasync_client.create_agent(
            ActivationKey=activation_key,
            AgentName=f"gcp-datasync-agent-{int(time.time())}",
            Tags=[
                {"Key": "Source", "Value": "GCP"},
                {"Key": "ManagedBy", "Value": "DataMIQ-PathB"},
            ],
        )
        
        self.agent_arn = response["AgentArn"]
        logger.info(f"Agent activated: {self.agent_arn}")
        return self.agent_arn
    
    def create_gcs_source_location(
        self,
        bucket_name: str,
        gcs_access_key: str,
        gcs_secret_key: str,
        subdirectory: str = "/",
    ) -> str:
        """Create DataSync source location for GCS using HMAC keys."""
        logger.info(f"Creating GCS source location: {bucket_name}{subdirectory}")
        
        response = self.datasync_client.create_location_object_storage(
            ServerHostname="storage.googleapis.com",
            ServerPort=443,
            ServerProtocol="HTTPS",
            Subdirectory=subdirectory,
            BucketName=bucket_name,
            AccessKey=gcs_access_key,
            SecretKey=gcs_secret_key,
            AgentArns=[self.agent_arn],
            Tags=[
                {"Key": "Source", "Value": "GCS"},
                {"Key": "Bucket", "Value": bucket_name},
            ],
        )
        
        location_arn = response["LocationArn"]
        logger.info(f"GCS source location created: {location_arn}")
        return location_arn
    
    def create_s3_destination_location(
        self,
        s3_bucket_name: str,
        subdirectory: str = "/",
        s3_config_role_arn: Optional[str] = None,
    ) -> str:
        """
        Create DataSync destination location for S3.
        
        Requires an IAM role ARN that DataSync can assume to access S3.
        The role must have a trust policy for datasync.amazonaws.com and S3 permissions.
        """
        logger.info(f"Creating S3 destination location: {s3_bucket_name}{subdirectory}")
        
        if not s3_config_role_arn:
            raise Exception(
                "DataSync S3 IAM Role ARN is required. "
                "Please provide an IAM role ARN in the migration configuration (Stage 2). "
                "The role must trust datasync.amazonaws.com and have S3 access permissions."
            )
        
        s3_bucket_arn = f"arn:aws:s3:::{s3_bucket_name}"
        
        response = self.datasync_client.create_location_s3(
            S3BucketArn=s3_bucket_arn,
            Subdirectory=subdirectory,
            S3StorageClass="STANDARD",
            S3Config={"BucketAccessRoleArn": s3_config_role_arn},
            Tags=[
                {"Key": "Destination", "Value": "S3"},
            ],
        )
        
        location_arn = response["LocationArn"]
        logger.info(f"S3 destination location created: {location_arn}")
        return location_arn
    
    def create_and_run_task(
        self,
        source_location_arn: str,
        dest_location_arn: str,
        task_name: str = "GCS-to-S3-DataMIQ",
    ) -> Dict[str, Any]:
        """Create a DataSync task and execute it. Returns final result."""
        logger.info(f"Creating DataSync task: {task_name}")
        
        try:
            task_response = self.datasync_client.create_task(
                SourceLocationArn=source_location_arn,
                DestinationLocationArn=dest_location_arn,
                Name=task_name,
                Options={
                    "VerifyMode": "ONLY_FILES_TRANSFERRED",
                    "OverwriteMode": "ALWAYS",
                    "TransferMode": "CHANGED",
                    "Atime": "BEST_EFFORT",
                    "Mtime": "PRESERVE",
                    "PreserveDeletedFiles": "PRESERVE",
                    "BytesPerSecond": -1,
                    "TaskQueueing": "ENABLED",
                },
                Tags=[{"Key": "ManagedBy", "Value": "DataMIQ-PathB"}],
            )
        except ClientError as e:
            error_msg = str(e)
            # Detect "agent is offline" error
            if "agent is offline" in error_msg.lower() or "agent" in error_msg.lower() and "offline" in error_msg.lower():
                logger.error(f"Agent is offline: {error_msg}")
                return {
                    "status": "agent_offline",
                    "task_arn": None,
                    "execution_arn": None,
                    "files_transferred": 0,
                    "bytes_transferred": 0,
                    "error": error_msg,
                    "result": {},
                }
            raise
        
        task_arn = task_response["TaskArn"]
        logger.info(f"Task created: {task_arn}")
        
        # Start execution
        try:
            exec_response = self.datasync_client.start_task_execution(TaskArn=task_arn)
        except ClientError as e:
            error_msg = str(e)
            if "agent is offline" in error_msg.lower() or ("agent" in error_msg.lower() and "offline" in error_msg.lower()):
                logger.error(f"Agent is offline during StartTaskExecution: {error_msg}")
                return {
                    "status": "agent_offline",
                    "task_arn": task_arn,
                    "execution_arn": None,
                    "files_transferred": 0,
                    "bytes_transferred": 0,
                    "error": error_msg,
                    "result": {},
                }
            raise
        
        execution_arn = exec_response["TaskExecutionArn"]
        logger.info(f"Task execution started: {execution_arn}")
        
        # Monitor
        result = self._monitor_execution(execution_arn)
        
        # Check for permission errors — no point retrying these
        error_detail = result.get("Result", {}).get("ErrorDetail", "") if isinstance(result.get("Result"), dict) else ""
        error_code = result.get("Result", {}).get("ErrorCode", "") if isinstance(result.get("Result"), dict) else ""
        
        if result["Status"] == "ERROR":
            logger.error(f"Task execution FAILED: {error_detail or error_code or 'Unknown error'}")
            
            # Don't retry permission errors — they won't fix themselves
            if "Permission denied" in error_detail or "Access denied" in error_detail:
                logger.error("Permission error detected — skipping retries (fix credentials/permissions first)")
                return {
                    "status": "failed",
                    "task_arn": task_arn,
                    "execution_arn": execution_arn,
                    "files_transferred": 0,
                    "bytes_transferred": 0,
                    "error": error_detail or error_code,
                    "result": result,
                }
            
            # Retry transient errors (up to 2 retries, shorter waits)
            logger.warning("Transient error, retrying...")
            for attempt in range(1, 3):
                wait_secs = 30 * attempt
                logger.info(f"Retry {attempt}/2 — waiting {wait_secs}s...")
                time.sleep(wait_secs)
                try:
                    exec_response = self.datasync_client.start_task_execution(TaskArn=task_arn)
                except ClientError as retry_err:
                    error_msg = str(retry_err)
                    if "agent is offline" in error_msg.lower() or ("agent" in error_msg.lower() and "offline" in error_msg.lower()):
                        logger.error(f"Agent went offline during retry: {error_msg}")
                        return {
                            "status": "agent_offline",
                            "task_arn": task_arn,
                            "execution_arn": None,
                            "files_transferred": 0,
                            "bytes_transferred": 0,
                            "error": error_msg,
                            "result": {},
                        }
                    raise
                result = self._monitor_execution(exec_response["TaskExecutionArn"])
                if result["Status"] == "SUCCESS":
                    break
                # Extract error from retry
                retry_error = result.get("Result", {}).get("ErrorDetail", "") if isinstance(result.get("Result"), dict) else ""
                logger.error(f"Retry {attempt} failed: {retry_error}")
        
        return {
            "status": "success" if result["Status"] == "SUCCESS" else "failed",
            "task_arn": task_arn,
            "execution_arn": execution_arn,
            "files_transferred": result.get("FilesTransferred", 0),
            "bytes_transferred": result.get("BytesTransferred", 0),
            "error": error_detail or error_code if result["Status"] == "ERROR" else None,
            "result": result,
        }
    
    def _monitor_execution(self, execution_arn: str, poll_interval: int = 15) -> Dict:
        """Poll DataSync task execution until done."""
        logger.info(f"Monitoring execution: {execution_arn}")
        
        while True:
            response = self.datasync_client.describe_task_execution(
                TaskExecutionArn=execution_arn
            )
            status = response["Status"]
            
            bytes_xfer = response.get("BytesTransferred", 0)
            files_xfer = response.get("FilesTransferred", 0)
            logger.info(f"  Status: {status} | Files: {files_xfer} | Bytes: {bytes_xfer}")
            
            if status in ("SUCCESS", "ERROR"):
                # Log error details if available
                result_info = response.get("Result", {})
                if status == "ERROR" and result_info:
                    error_detail = result_info.get("ErrorDetail", "No details")
                    error_code = result_info.get("ErrorCode", "Unknown")
                    logger.error(f"  ERROR: {error_code} — {error_detail}")
                return response
            
            time.sleep(poll_interval)
    
    def cleanup_vm(self):
        """Delete the GCP VM created for the DataSync agent."""
        if not self.vm_instance_name or not self.compute_client:
            return
        
        try:
            from google.cloud import compute_v1
            
            logger.info(f"Deleting DataSync agent VM: {self.vm_instance_name}")
            request = compute_v1.DeleteInstanceRequest(
                project=self.gcp_project_id,
                zone=self.gcp_zone,
                instance=self.vm_instance_name,
            )
            self.compute_client.delete(request=request)
            logger.info("VM deletion initiated")
        except Exception as e:
            logger.error(f"Failed to delete VM: {e}")


class PathwayB:
    """
    Path B: GCS → S3 via AWS DataSync Agent on GCP VM
    
    The DataSync agent runs inside GCP for private GCS access.
    
    Stages:
    1. Export BigQuery tables to GCS (handled by orchestrator)
    2. Transfer from GCS to S3 using DataSync agent on GCP VM
    3. Load from S3 to Redshift using RedshiftLoader
    """
    
    # Size thresholds for parallel task count (in bytes)
    PARALLEL_THRESHOLDS = [
        (1_000_000_000_000, 16),  # 1 TB+ → up to 16 tasks
        (100_000_000_000, 8),     # 100 GB+ → up to 8 tasks
        (10_000_000_000, 4),      # 10 GB+ → up to 4 tasks
    ]
    PARALLEL_MIN_BYTES = 10_000_000_000  # 10 GB minimum to trigger parallelism
    
    def __init__(self, checkpoint_manager, manifest_handler, log_callback=None):
        self.checkpoint_manager = checkpoint_manager
        self.manifest_handler = manifest_handler
        self.log_callback = log_callback
    
    def _plan_parallel_tasks(self, migration_id: int) -> List[Dict]:
        """
        Plan parallel DataSync tasks based on export results stored in checkpoint_data.
        
        Returns a list of task groups. Each group is a dict:
          {
            "tables": ["table_a", "table_b"],
            "subdirectory": "/path/dataset"  (for single-task, whole directory)
                        or "/path/dataset/table_a" (for per-table tasks),
            "total_bytes": 123456,
            "task_index": 0
          }
        
        For small datasets or single tables, returns one group (current behavior).
        For large datasets, splits into multiple groups by table.
        """
        from database import get_db
        from models.bq_redshift_migration import MigrationBQRedshift
        
        db = next(get_db())
        try:
            migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
            if not migration:
                return []
            
            checkpoint_data = migration.checkpoint_data or {}
            export_results = checkpoint_data.get('export_results', [])
            
            if not export_results:
                logger.warning("No export_results in checkpoint_data, falling back to single task")
                return [{"tables": [], "subdirectory": None, "total_bytes": 0, "task_index": 0, "single_task": True}]
            
            # Build table size map from export results
            table_sizes = []
            for result in export_results:
                if not result.get('success'):
                    continue
                table_ref = result.get('table', '')
                # table_ref is like "project.dataset.table_name"
                table_name = table_ref.split('.')[-1] if '.' in table_ref else table_ref
                num_bytes = result.get('num_bytes', 0)
                table_sizes.append({"table": table_name, "bytes": num_bytes})
            
            if not table_sizes:
                logger.warning("No successful exports found, falling back to single task")
                return [{"tables": [], "subdirectory": None, "total_bytes": 0, "task_index": 0, "single_task": True}]
            
            total_bytes = sum(t["bytes"] for t in table_sizes)
            num_tables = len(table_sizes)
            
            logger.info(f"Parallel planning: {num_tables} tables, {total_bytes:,} bytes ({total_bytes / (1024**3):.2f} GB)")
            
            # Determine max parallel tasks based on total size
            if total_bytes < self.PARALLEL_MIN_BYTES or num_tables <= 1:
                logger.info("Below parallel threshold or single table — using single DataSync task")
                return [{"tables": [t["table"] for t in table_sizes], "subdirectory": None, "total_bytes": total_bytes, "task_index": 0, "single_task": True}]
            
            max_tasks = 2  # default
            for threshold_bytes, max_t in self.PARALLEL_THRESHOLDS:
                if total_bytes >= threshold_bytes:
                    max_tasks = max_t
                    break
            
            num_tasks = min(max_tasks, num_tables)
            logger.info(f"Planning {num_tasks} parallel DataSync tasks for {total_bytes / (1024**3):.2f} GB across {num_tables} tables")
            
            # Greedy bin-packing: sort tables by size descending, assign each to the lightest batch
            table_sizes.sort(key=lambda t: t["bytes"], reverse=True)
            
            batches: List[Dict] = [{"tables": [], "total_bytes": 0, "task_index": i} for i in range(num_tasks)]
            
            for table_info in table_sizes:
                # Find the batch with the least total bytes
                lightest = min(batches, key=lambda b: b["total_bytes"])
                lightest["tables"].append(table_info["table"])
                lightest["total_bytes"] += table_info["bytes"]
            
            # Remove empty batches (shouldn't happen but safety)
            batches = [b for b in batches if b["tables"]]
            
            for batch in batches:
                logger.info(f"  Task {batch['task_index']}: {len(batch['tables'])} tables, {batch['total_bytes'] / (1024**3):.2f} GB — {batch['tables']}")
            
            if self.log_callback:
                self.log_callback(
                    migration_id, "INFO", "transfer",
                    f"Parallel transfer plan: {len(batches)} DataSync tasks for {total_bytes / (1024**3):.2f} GB across {num_tables} tables",
                    log_metadata={"batches": [{"task_index": b["task_index"], "tables": b["tables"], "bytes": b["total_bytes"]} for b in batches]}
                )
            
            return batches
        finally:
            db.close()
    
    def _execute_parallel_tasks(
        self,
        migration_id: int,
        agent: 'GCPDataSyncAgent',
        batches: List[Dict],
        gcs_bucket: str,
        gcs_path: str,
        s3_bucket: str,
        s3_path: str,
        dataset: str,
        gcs_access_key: str,
        gcs_secret_key: str,
        datasync_s3_role_arn: str,
        aws_access_key: str,
        aws_secret_key: str,
        aws_region: str,
    ) -> bool:
        """
        Execute multiple DataSync tasks in parallel, one per batch of tables.
        
        Each batch gets its own GCS source location (pointing to a per-table subdirectory
        or a combined filter). The S3 destination is shared.
        
        For batches with a single table, the source location points directly to that table's
        subdirectory. For batches with multiple tables, we create one task per table within
        the batch (since DataSync source locations can only point to one subdirectory).
        """
        # Load existing parallel task checkpoint
        from database import get_db
        from models.bq_redshift_migration import MigrationBQRedshift
        
        db = next(get_db())
        try:
            mig = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
            checkpoint_data = mig.checkpoint_data or {} if mig else {}
            parallel_status = checkpoint_data.get("parallel_tasks", {})
        finally:
            db.close()
        
        # Flatten batches into individual table-level tasks
        # DataSync source locations are per-subdirectory, so each table needs its own task
        table_tasks = []
        for batch in batches:
            for table_name in batch["tables"]:
                task_key = f"table_{table_name}"
                if parallel_status.get(task_key, {}).get("status") == "success":
                    logger.info(f"Skipping already-completed task for table: {table_name}")
                    if self.log_callback:
                        self.log_callback(migration_id, "INFO", "transfer", f"Table '{table_name}' transfer already completed, skipping")
                    continue
                table_tasks.append({
                    "table": table_name,
                    "task_key": task_key,
                    "batch_index": batch["task_index"],
                })
        
        if not table_tasks:
            logger.info("All parallel tasks already completed")
            return True
        
        total_tasks = len(table_tasks)
        logger.info(f"Executing {total_tasks} parallel DataSync tasks")
        if self.log_callback:
            self.log_callback(migration_id, "INFO", "transfer", f"Starting {total_tasks} parallel DataSync tasks")
        
        # Create shared S3 destination location (reuse if already saved)
        db = next(get_db())
        try:
            mig = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
            cp = mig.checkpoint_data or {} if mig else {}
            saved_dest_arn = cp.get("datasync_dest_location_arn")
            _par_migration_name = mig.migration_name if mig else 'Unknown'
        finally:
            db.close()
        
        if saved_dest_arn:
            dest_arn = saved_dest_arn
            logger.info(f"Reusing saved S3 destination location: {dest_arn}")
        else:
            s3_subdir = f"/{s3_path}" if s3_path else "/"
            dest_arn = agent.create_s3_destination_location(
                s3_bucket_name=s3_bucket,
                subdirectory=s3_subdir,
                s3_config_role_arn=datasync_s3_role_arn,
            )
            self._save_checkpoint(migration_id, {"datasync_dest_location_arn": dest_arn})
        
        # Worker function for each table task
        def run_table_task(task_info: Dict) -> Dict:
            table_name = task_info["table"]
            task_key = task_info["task_key"]
            try:
                # Build per-table GCS subdirectory: /gcs_path/dataset/table_name/
                if gcs_path:
                    table_subdir = f"/{gcs_path}/{dataset}/{table_name}/"
                else:
                    table_subdir = f"/{dataset}/{table_name}/"
                
                logger.info(f"[{table_name}] Creating GCS source location: gs://{gcs_bucket}{table_subdir}")
                
                source_arn = agent.create_gcs_source_location(
                    bucket_name=gcs_bucket,
                    gcs_access_key=gcs_access_key,
                    gcs_secret_key=gcs_secret_key,
                    subdirectory=table_subdir,
                )
                
                # Build per-table S3 destination: /s3_path/dataset/table_name/
                if s3_path:
                    s3_table_subdir = f"/{s3_path}/{dataset}/{table_name}/"
                else:
                    s3_table_subdir = f"/{dataset}/{table_name}/"
                
                table_dest_arn = agent.create_s3_destination_location(
                    s3_bucket_name=s3_bucket,
                    subdirectory=s3_table_subdir,
                    s3_config_role_arn=datasync_s3_role_arn,
                )
                
                _par_task_name = f"DataMIQ-Mig{migration_id}-{table_name}"
                _par_task_start = datetime.utcnow()
                result = agent.create_and_run_task(
                    source_location_arn=source_arn,
                    dest_location_arn=table_dest_arn,
                    task_name=_par_task_name,
                )
                
                # Log parallel task to history
                _par_task_status = 'completed' if result.get('status') == 'success' else 'failed'
                self._log_task_history(
                    migration_id=migration_id, migration_name=_par_migration_name,
                    task_name=_par_task_name, task_arn=result.get('task_arn'),
                    execution_arn=result.get('execution_arn'), agent_arn=agent.agent_arn,
                    agent_ip=agent.agent_ip, source_arn=source_arn,
                    source_uri=f"gs://{gcs_bucket}{table_subdir}",
                    dest_arn=table_dest_arn,
                    dest_uri=f"s3://{s3_bucket}{s3_table_subdir}",
                    status=_par_task_status, started_at=_par_task_start,
                    table_name=table_name,
                    files_transferred=result.get('files_transferred', 0),
                    bytes_transferred=result.get('bytes_transferred', 0),
                    error_message=result.get('error'),
                )
                
                return {
                    "task_key": task_key,
                    "table": table_name,
                    "status": result.get("status", "failed"),
                    "files_transferred": result.get("files_transferred", 0),
                    "bytes_transferred": result.get("bytes_transferred", 0),
                    "error": result.get("error"),
                    "task_arn": result.get("task_arn"),
                }
            except Exception as e:
                logger.error(f"[{table_name}] DataSync task failed: {e}")
                return {
                    "task_key": task_key,
                    "table": table_name,
                    "status": "failed",
                    "error": str(e),
                    "files_transferred": 0,
                    "bytes_transferred": 0,
                }
        
        # Execute tasks in parallel with ThreadPoolExecutor
        max_workers = min(total_tasks, 16)
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {executor.submit(run_table_task, task): task for task in table_tasks}
            
            for future in as_completed(future_to_task):
                task_info = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Save per-task checkpoint immediately
                    self._save_checkpoint(migration_id, {
                        f"parallel_tasks": {
                            **parallel_status,
                            result["task_key"]: {
                                "status": result["status"],
                                "files": result["files_transferred"],
                                "bytes": result["bytes_transferred"],
                                "error": result.get("error"),
                            }
                        }
                    })
                    # Update local tracking
                    parallel_status[result["task_key"]] = {"status": result["status"]}
                    
                    status_icon = "OK" if result["status"] == "success" else "FAILED"
                    log_msg = f"[{result['table']}] {status_icon} — {result['files_transferred']} files, {result['bytes_transferred']} bytes"
                    if result.get("error"):
                        log_msg += f" — Error: {result['error']}"
                    
                    logger.info(log_msg)
                    if self.log_callback:
                        level = "INFO" if result["status"] == "success" else "ERROR"
                        self.log_callback(migration_id, level, "transfer", log_msg)
                    
                except Exception as e:
                    logger.error(f"[{task_info['table']}] Future raised exception: {e}")
                    results.append({
                        "task_key": task_info["task_key"],
                        "table": task_info["table"],
                        "status": "failed",
                        "error": str(e),
                    })
        
        # Summarize
        succeeded = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] != "success"]
        total_files = sum(r.get("files_transferred", 0) for r in results)
        total_bytes = sum(r.get("bytes_transferred", 0) for r in results)
        
        summary = f"Parallel transfer complete: {len(succeeded)}/{len(results)} tasks succeeded, {total_files} files, {total_bytes:,} bytes"
        logger.info(summary)
        if self.log_callback:
            self.log_callback(migration_id, "INFO", "transfer", summary,
                log_metadata={"succeeded": len(succeeded), "failed": len(failed), "total_files": total_files, "total_bytes": total_bytes})
        
        if failed:
            for r in failed:
                logger.error(f"Failed task: table={r['table']}, error={r.get('error')}")
            if self.log_callback:
                self.log_callback(migration_id, "ERROR", "transfer",
                    f"{len(failed)} table transfers failed: {[r['table'] for r in failed]}")
            return False
        
        return True
    
    def execute(
        self,
        migration_id: int,
        source_config: Dict,
        target_config: Dict,
        storage_config: Dict,
    ) -> bool:
        try:
            logger.info("=" * 80)
            logger.info(f"STARTING PATH B MIGRATION {migration_id} - DataSync Agent on GCP")
            logger.info("=" * 80)
            
            # Get checkpoint data from migration object (like PathwayC does)
            from database import get_db
            from models.bq_redshift_migration import MigrationBQRedshift
            
            db = next(get_db())
            try:
                migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
                if not migration:
                    logger.error(f"Migration {migration_id} not found")
                    return False
                
                checkpoint_data = migration.checkpoint_data or {}
                
                # Determine which stages are completed
                export_completed = checkpoint_data.get('export_completed_at') is not None
                transfer_completed = checkpoint_data.get('transfer_completed_at') is not None
                load_completed = checkpoint_data.get('load_completed_at') is not None
                
                logger.info("Checkpoint Status:")
                logger.info(f"  Export: {'✓ Completed' if export_completed else '✗ Pending'}")
                logger.info(f"  Transfer: {'✓ Completed' if transfer_completed else '✗ Pending'}")
                logger.info(f"  Load: {'✓ Completed' if load_completed else '✗ Pending'}")
                
                # Stage 1: Export (handled by orchestrator)
                if not export_completed:
                    logger.error("Export stage not completed. Cannot proceed.")
                    return False
                
                # Stage 2: Transfer via DataSync
                if not transfer_completed:
                    logger.info("=" * 80)
                    logger.info("STAGE 2: TRANSFER (GCS → S3 via DataSync on GCP VM)")
                    logger.info("=" * 80)
                    
                    success = self._execute_transfer_stage(migration_id, storage_config, source_config)
                    if not success:
                        logger.error("Transfer stage failed")
                        return False
                    
                    # Refresh from DB to pick up checkpoint changes made by _save_checkpoint
                    # (_save_checkpoint uses separate DB sessions)
                    db.expire_all()
                    db.refresh(migration)
                    checkpoint_data = migration.checkpoint_data or {}
                    
                    # Mark transfer completed in checkpoint
                    checkpoint_data['transfer_completed_at'] = datetime.utcnow().isoformat()
                    migration.checkpoint_data = checkpoint_data
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(migration, 'checkpoint_data')
                    migration.current_stage = 'load'
                    migration.updated_at = datetime.utcnow()
                    db.commit()
                    
                    logger.info("✓ Transfer stage completed")
                else:
                    logger.info("Transfer stage already completed, skipping...")
                
                # Stage 3: Load to Redshift (reuse PathwayC's load logic)
                if not load_completed:
                    logger.info("=" * 80)
                    logger.info("STAGE 3: LOAD (S3 → Redshift)")
                    logger.info("=" * 80)
                    
                    # Refresh session to pick up checkpoint changes made by transfer stage
                    # (transfer stage uses separate DB sessions via _save_checkpoint)
                    db.expire_all()
                    
                    from .pathway_c import PathwayC
                    pathway_c = PathwayC(self.checkpoint_manager, self.manifest_handler, self.log_callback)
                    
                    success = pathway_c._execute_load_stage(
                        migration_id, target_config, storage_config, [], db
                    )
                    if not success:
                        logger.error("Load stage failed")
                        if self.log_callback:
                            self.log_callback(migration_id, "ERROR", "load", "Load stage (S3 → Redshift) failed — check backend console logs for details")
                        return False
                    
                    # Refresh from DB to pick up checkpoint changes made by load stage
                    db.expire_all()
                    db.refresh(migration)
                    checkpoint_data = migration.checkpoint_data or {}
                    
                    # Mark load completed in checkpoint (if not already set by load stage)
                    if not checkpoint_data.get('load_completed_at'):
                        checkpoint_data['load_completed_at'] = datetime.utcnow().isoformat()
                    migration.checkpoint_data = checkpoint_data
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(migration, 'checkpoint_data')
                    migration.current_stage = 'completed'
                    migration.updated_at = datetime.utcnow()
                    db.commit()
                    
                    logger.info("✓ Load stage completed")
                else:
                    logger.info("Load stage already completed, skipping...")
                
                logger.info("=" * 80)
                logger.info(f"✓ PATH B MIGRATION {migration_id} COMPLETED SUCCESSFULLY")
                logger.info("=" * 80)
                return True
                
            finally:
                db.close()
            
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"PATH B MIGRATION {migration_id} FAILED: {e}")
            logger.error(tb)
            # Write error to migration logs so it shows in the UI
            if self.log_callback:
                self.log_callback(migration_id, "CRITICAL", "transfer", f"Path B failed: {str(e)}", log_metadata={"stack_trace": tb})
            return False
    
    def _execute_transfer_stage(
        self,
        migration_id: int,
        storage_config: Dict,
        source_config: Dict,
    ) -> bool:
        """Execute GCS → S3 transfer using DataSync agent on GCP VM."""
        try:
            # Extract config
            gcs_bucket = storage_config.get("gcs_bucket", "").replace("gs://", "").strip("/")
            gcs_path = storage_config.get("gcs_path", "").strip("/")
            s3_bucket = storage_config.get("s3_bucket", "").replace("s3://", "").strip("/")
            s3_path = storage_config.get("s3_path", "").strip("/")
            aws_region = storage_config.get("aws_region", "us-east-1")
            
            agent_mode = storage_config.get("datasync_agent_mode", "existing_vm")
            gcp_zone = storage_config.get("datasync_gcp_zone", "")
            gcp_machine_type = storage_config.get("datasync_gcp_machine_type", "n1-standard-4")
            gcp_network = storage_config.get("datasync_gcp_network", "default")
            gcp_subnet = storage_config.get("datasync_gcp_subnet", "")
            existing_vm_ip = storage_config.get("datasync_existing_vm_ip", "")
            datasync_s3_role_arn = storage_config.get("datasync_s3_role_arn", "")
            
            # GCS HMAC credentials
            gcs_access_key = storage_config.get("gcs_access_key", "")
            gcs_secret_key = self._decrypt_gcs_secret(storage_config, migration_id)
            
            # AWS credentials
            aws_access_key = storage_config.get("aws_access_key_id", "")
            aws_secret_key = self._decrypt_aws_secret(storage_config, migration_id)
            
            # GCP project from source config
            gcp_project_id = source_config.get("project_id", "")
            
            # Parse service account JSON for GCP API calls
            sa_info = self._get_service_account_info(storage_config, migration_id)
            if sa_info:
                gcp_project_id = gcp_project_id or sa_info.get("project_id", "")
            
            # Validate
            if not gcs_access_key or not gcs_secret_key:
                msg = "GCS HMAC credentials not provided"
                logger.error(msg)
                if self.log_callback:
                    self.log_callback(migration_id, "ERROR", "transfer", msg)
                return False
            if not aws_access_key or not aws_secret_key:
                msg = "AWS credentials not provided"
                logger.error(msg)
                if self.log_callback:
                    self.log_callback(migration_id, "ERROR", "transfer", msg)
                return False
            if agent_mode == "create_vm" and not gcp_zone:
                msg = "GCP zone required for create_vm mode"
                logger.error(msg)
                if self.log_callback:
                    self.log_callback(migration_id, "ERROR", "transfer", msg)
                return False
            if agent_mode == "existing_vm" and not existing_vm_ip:
                msg = "Existing VM IP required for existing_vm mode"
                logger.error(msg)
                if self.log_callback:
                    self.log_callback(migration_id, "ERROR", "transfer", msg)
                return False
            if not gcp_project_id:
                msg = "GCP project ID not found. Ensure service account JSON is provided in Stage 1."
                logger.error(msg)
                if self.log_callback:
                    self.log_callback(migration_id, "ERROR", "transfer", msg)
                return False
            
            logger.info(f"GCS Source: gs://{gcs_bucket}/{gcs_path}")
            logger.info(f"S3 Destination: s3://{s3_bucket}/{s3_path}")
            logger.info(f"Agent mode: {agent_mode}")
            logger.info(f"AWS Region: {aws_region}")
            logger.info(f"VM IP: {existing_vm_ip}")
            
            # Validate VM IP doesn't look like an HMAC key (common misconfiguration)
            if existing_vm_ip and (existing_vm_ip.startswith("GOOG") or len(existing_vm_ip) > 50):
                msg = (
                    f"VM IP '{existing_vm_ip[:20]}...' looks like a GCS HMAC key, not an IP address. "
                    f"Please check the 'DataSync Agent VM IP' field in Stage 2."
                )
                logger.error(msg)
                if self.log_callback:
                    self.log_callback(migration_id, "ERROR", "transfer", msg)
                return False
            
            if self.log_callback:
                self.log_callback(migration_id, "INFO", "transfer",
                    f"DataSync config: mode={agent_mode}, GCS=gs://{gcs_bucket}/{gcs_path}, S3=s3://{s3_bucket}/{s3_path}, region={aws_region}",
                    log_metadata={"agent_mode": agent_mode, "gcp_zone": gcp_zone, "aws_region": aws_region})
            
            # Debug: Log credential info (not the actual values for security)
            logger.info(f"AWS Access Key ID length: {len(aws_access_key) if aws_access_key else 0}")
            logger.info(f"AWS Secret Key length: {len(aws_secret_key) if aws_secret_key else 0}")
            logger.info(f"AWS Access Key ID starts with: {aws_access_key[:8] if aws_access_key and len(aws_access_key) >= 8 else 'N/A'}")
            logger.info(f"DataSync S3 Role ARN: {datasync_s3_role_arn or 'NOT SET'}")
            
            # Initialize agent manager
            agent = GCPDataSyncAgent(
                gcp_project_id=gcp_project_id,
                gcp_zone=gcp_zone or "us-central1-a",
                aws_region=aws_region,
                service_account_info=sa_info,
                aws_access_key_id=aws_access_key.strip() if aws_access_key else None,
                aws_secret_access_key=aws_secret_key.strip() if aws_secret_key else None,
                datasync_role_arn=datasync_s3_role_arn or None,
            )
            
            # Set S3/GCS buckets for AMI export/import flow in _ensure_datasync_image_exists
            agent._export_s3_bucket = s3_bucket
            agent._gcs_bucket = gcs_bucket
            
            # Step 1: Get agent IP (only existing VM mode is supported)
            if agent_mode == "create_vm":
                msg = "Automatic VM creation is no longer supported. Please manually create the DataSync agent VM and use 'Use Existing VM' mode."
                logger.error(msg)
                if self.log_callback:
                    self.log_callback(migration_id, "ERROR", "transfer", msg)
                return False
            
            if not existing_vm_ip:
                msg = "VM IP address is required. Please provide the IP of your DataSync agent VM."
                logger.error(msg)
                if self.log_callback:
                    self.log_callback(migration_id, "ERROR", "transfer", msg)
                return False
            
            agent_ip = existing_vm_ip
            agent.agent_ip = agent_ip
            if self.log_callback:
                self.log_callback(migration_id, "INFO", "transfer",
                    f"Using DataSync agent VM at: {agent_ip}")
            
            # Load checkpoint data to check for saved location ARNs
            from database import get_db
            from models.bq_redshift_migration import MigrationBQRedshift
            from models.datasync_agent import DataSyncAgent
            _db = next(get_db())
            try:
                _mig = _db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
                _cp = _mig.checkpoint_data or {} if _mig else {}
                _migration_name = _mig.migration_name if _mig else 'Unknown'
            finally:
                _db.close()
            
            saved_source_arn = _cp.get("datasync_source_location_arn")
            saved_dest_arn = _cp.get("datasync_dest_location_arn")
            
            # Step 2: Get or create agent using shared registry (one agent per VM IP)
            agent_arn = self._get_or_create_agent(
                migration_id, agent, agent_ip, aws_region
            )
            agent.agent_arn = agent_arn
            
            # Step 3: Create source location (GCS) (or reuse saved)
            if saved_source_arn:
                source_arn = saved_source_arn
                logger.info(f"Reusing saved source location: {source_arn}")
            else:
                gcs_subdir = f"/{gcs_path}" if gcs_path else "/"
                source_arn = agent.create_gcs_source_location(
                    bucket_name=gcs_bucket,
                    gcs_access_key=gcs_access_key,
                    gcs_secret_key=gcs_secret_key,
                    subdirectory=gcs_subdir,
                )
                self._save_checkpoint(migration_id, {"datasync_source_location_arn": source_arn})
            
            # Step 4: Create destination location (S3) (or reuse saved)
            if saved_dest_arn:
                dest_arn = saved_dest_arn
                logger.info(f"Reusing saved dest location: {dest_arn}")
            else:
                s3_subdir = f"/{s3_path}" if s3_path else "/"
                dest_arn = agent.create_s3_destination_location(
                    s3_bucket_name=s3_bucket,
                    subdirectory=s3_subdir,
                    s3_config_role_arn=datasync_s3_role_arn,
                )
                self._save_checkpoint(migration_id, {"datasync_dest_location_arn": dest_arn})
            
            # Step 5: Create and run task
            _task_start = datetime.utcnow()
            _task_name = f"DataMIQ-Migration-{migration_id}"
            result = agent.create_and_run_task(
                source_location_arn=source_arn,
                dest_location_arn=dest_arn,
                task_name=_task_name,
            )
            
            # Log task to history
            _task_status = 'completed' if result.get('status') == 'success' else ('agent_offline' if result.get('status') == 'agent_offline' else 'failed')
            self._log_task_history(
                migration_id=migration_id, migration_name=_migration_name,
                task_name=_task_name, task_arn=result.get('task_arn'),
                execution_arn=result.get('execution_arn'), agent_arn=agent.agent_arn,
                agent_ip=agent_ip, source_arn=source_arn,
                source_uri=f"gs://{gcs_bucket}/{gcs_path}" if gcs_path else f"gs://{gcs_bucket}",
                dest_arn=dest_arn,
                dest_uri=f"s3://{s3_bucket}/{s3_path}" if s3_path else f"s3://{s3_bucket}",
                status=_task_status, started_at=_task_start,
                files_transferred=result.get('files_transferred', 0),
                bytes_transferred=result.get('bytes_transferred', 0),
                error_message=result.get('error'),
            )
            
            # Handle agent offline — clear saved ARNs, re-activate, and retry once
            if result.get("status") == "agent_offline":
                logger.warning("Agent is offline — re-activating via registry")
                if self.log_callback:
                    self.log_callback(migration_id, "WARNING", "transfer",
                        "DataSync agent is offline. Re-activating...")
                
                # Clear location ARNs from checkpoint (they're tied to the old agent)
                self._save_checkpoint(migration_id, {
                    "datasync_source_location_arn": None,
                    "datasync_dest_location_arn": None,
                })
                
                # Force re-activate via registry
                agent_arn = self._get_or_create_agent(
                    migration_id, agent, agent_ip, aws_region, force_reactivate=True
                )
                agent.agent_arn = agent_arn
                
                # Re-create locations with new agent
                gcs_subdir = f"/{gcs_path}" if gcs_path else "/"
                source_arn = agent.create_gcs_source_location(
                    bucket_name=gcs_bucket,
                    gcs_access_key=gcs_access_key,
                    gcs_secret_key=gcs_secret_key,
                    subdirectory=gcs_subdir,
                )
                self._save_checkpoint(migration_id, {"datasync_source_location_arn": source_arn})
                
                s3_subdir = f"/{s3_path}" if s3_path else "/"
                dest_arn = agent.create_s3_destination_location(
                    s3_bucket_name=s3_bucket,
                    subdirectory=s3_subdir,
                    s3_config_role_arn=datasync_s3_role_arn,
                )
                self._save_checkpoint(migration_id, {"datasync_dest_location_arn": dest_arn})
                
                # Retry the task
                if self.log_callback:
                    self.log_callback(migration_id, "INFO", "transfer", "Retrying DataSync task with re-activated agent...")
                _retry_start = datetime.utcnow()
                _retry_task_name = f"DataMIQ-Migration-{migration_id}-retry"
                result = agent.create_and_run_task(
                    source_location_arn=source_arn,
                    dest_location_arn=dest_arn,
                    task_name=_retry_task_name,
                )
                
                # Log retry task
                _retry_status = 'completed' if result.get('status') == 'success' else ('agent_offline' if result.get('status') == 'agent_offline' else 'failed')
                self._log_task_history(
                    migration_id=migration_id, migration_name=_migration_name,
                    task_name=_retry_task_name, task_arn=result.get('task_arn'),
                    execution_arn=result.get('execution_arn'), agent_arn=agent.agent_arn,
                    agent_ip=agent_ip, source_arn=source_arn,
                    source_uri=f"gs://{gcs_bucket}/{gcs_path}" if gcs_path else f"gs://{gcs_bucket}",
                    dest_arn=dest_arn,
                    dest_uri=f"s3://{s3_bucket}/{s3_path}" if s3_path else f"s3://{s3_bucket}",
                    status=_retry_status, started_at=_retry_start,
                    files_transferred=result.get('files_transferred', 0),
                    bytes_transferred=result.get('bytes_transferred', 0),
                    error_message=result.get('error'),
                )
                
                # If still offline after retry, fail
                if result.get("status") == "agent_offline":
                    error_msg = "Agent is still offline after re-activation. Please reboot the DataSync VM and try again."
                    logger.error(error_msg)
                    if self.log_callback:
                        self.log_callback(migration_id, "ERROR", "transfer", error_msg)
                    return False
            
            if result["status"] == "success":
                logger.info("=" * 80)
                logger.info("DataSync Transfer Completed Successfully")
                logger.info(f"  Files: {result.get('files_transferred', 0)}")
                logger.info(f"  Bytes: {result.get('bytes_transferred', 0)}")
                logger.info("=" * 80)
                
                if self.log_callback:
                    self.log_callback(migration_id, "INFO", "transfer",
                        f"DataSync transfer complete: {result.get('files_transferred', 0)} files, {result.get('bytes_transferred', 0)} bytes")
                
                # Generate manifest files for Redshift COPY
                logger.info("=" * 80)
                logger.info("GENERATING MANIFEST FILES FOR REDSHIFT COPY")
                logger.info("=" * 80)
                
                try:
                    self._generate_manifests_for_redshift(
                        migration_id, s3_bucket, s3_path, aws_access_key, aws_secret_key, aws_region
                    )
                except Exception as manifest_err:
                    logger.warning(f"Manifest generation failed (non-fatal): {manifest_err}")
                    if self.log_callback:
                        self.log_callback(migration_id, "WARNING", "transfer",
                            f"Manifest generation failed (will use prefix-based COPY): {str(manifest_err)}")
                
                return True
            else:
                error_msg = result.get("error", "Unknown error")
                logger.error(f"DataSync transfer failed: {error_msg}")
                logger.error(f"Result: {result}")
                
                # If the error is related to locations (permission denied, location access),
                # clear saved location ARNs so they get re-created on next retry
                error_lower = error_msg.lower()
                if any(kw in error_lower for kw in [
                    "permission denied", "location", "access denied", "x50006",
                    "creating location", "source location", "dest location"
                ]):
                    logger.warning("Location-related error detected — clearing saved location ARNs for retry")
                    self._save_checkpoint(migration_id, {
                        "datasync_source_location_arn": None,
                        "datasync_dest_location_arn": None,
                    })
                    if self.log_callback:
                        self.log_callback(migration_id, "WARNING", "transfer",
                            "Cleared cached DataSync locations — they will be re-created on next retry")
                
                if self.log_callback:
                    self.log_callback(migration_id, "ERROR", "transfer",
                        f"DataSync transfer failed: {error_msg}",
                        log_metadata={"task_arn": result.get("task_arn"), "error": error_msg})
                return False
                
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            error_str = str(e)
            logger.error(f"DataSync transfer failed: {e}")
            logger.error(tb)
            
            # Provide actionable guidance for common errors
            user_msg = f"DataSync transfer error: {error_str}"
            if "AssumeRole" in error_str and "AccessDenied" in error_str:
                user_msg = (
                    f"DataSync transfer error: {error_str}\n\n"
                    f"FIX: The IAM user making this call needs permission to assume the DataSync role.\n"
                    f"1. Go to AWS IAM → Users → find the user shown in the error → Permissions → Add inline policy:\n"
                    f'   {{"Effect": "Allow", "Action": "sts:AssumeRole", "Resource": "{datasync_s3_role_arn}"}}\n'
                    f"2. Go to IAM → Roles → {datasync_s3_role_arn.split('/')[-1] if datasync_s3_role_arn else 'DataSyncS3AccessRole'} → Trust relationships → Edit:\n"
                    f"   Add the IAM user ARN from the error as a trusted principal."
                )
            
            if self.log_callback:
                self.log_callback(migration_id, "ERROR", "transfer", user_msg, log_metadata={"stack_trace": tb})
            return False
    
    def _generate_manifests_for_redshift(
        self,
        migration_id: int,
        s3_bucket: str,
        s3_path: str,
        aws_access_key: str,
        aws_secret_key: str,
        aws_region: str,
    ):
        """
        After DataSync transfer, list files in S3 and generate per-table manifest files.
        
        Manifest files are used by Redshift COPY command for reliable loading.
        Each table gets its own manifest file listing all its data files.
        
        Structure in S3:
          s3://bucket/path/dataset/table_name/file1.parquet
          s3://bucket/path/dataset/table_name/file2.parquet
          s3://bucket/path/manifests/table_name.manifest
        """
        import json
        
        s3 = boto3.client(
            "s3",
            region_name=aws_region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
        )
        
        prefix = s3_path.strip("/") + "/" if s3_path else ""
        
        # List all data files in S3
        logger.info(f"Listing files in s3://{s3_bucket}/{prefix}")
        
        all_files = []
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=s3_bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                size = obj.get("Size", 0)
                # Skip manifest files and directories
                if not key.endswith("/") and "/manifests/" not in key:
                    all_files.append({"key": key, "size": size})
        
        logger.info(f"Found {len(all_files)} data files in S3")
        
        if not all_files:
            logger.warning("No data files found in S3 after transfer")
            return
        
        # Group files by table
        # Expected structure: prefix/dataset/table_name/file.parquet
        tables = {}
        for file_info in all_files:
            key = file_info["key"]
            # Remove the base prefix to get relative path
            relative = key[len(prefix):] if key.startswith(prefix) else key
            parts = relative.split("/")
            
            if len(parts) >= 2:
                # parts[0] = dataset, parts[1] = table_name, parts[2+] = file
                table_name = parts[1] if len(parts) >= 3 else parts[0]
                if table_name not in tables:
                    tables[table_name] = []
                tables[table_name].append({
                    "url": f"s3://{s3_bucket}/{key}",
                    "size": file_info["size"],
                })
            else:
                # File at root level
                table_name = "_root"
                if table_name not in tables:
                    tables[table_name] = []
                tables[table_name].append({
                    "url": f"s3://{s3_bucket}/{key}",
                    "size": file_info["size"],
                })
        
        logger.info(f"Found {len(tables)} tables: {list(tables.keys())}")
        
        # Generate manifest for each table
        manifest_prefix = f"{prefix}manifests" if prefix else "manifests"
        manifests_created = []
        
        for table_name, file_entries in tables.items():
            manifest = {
                "entries": [
                    {
                        "url": entry["url"],
                        "mandatory": True,
                        "meta": {"content_length": entry["size"]},
                    }
                    for entry in sorted(file_entries, key=lambda e: e["url"])
                ]
            }
            
            manifest_key = f"{manifest_prefix}/{table_name}.manifest"
            manifest_json = json.dumps(manifest, indent=2)
            
            s3.put_object(
                Bucket=s3_bucket,
                Key=manifest_key,
                Body=manifest_json.encode("utf-8"),
                ContentType="application/json",
            )
            
            manifest_uri = f"s3://{s3_bucket}/{manifest_key}"
            manifests_created.append({
                "table": table_name,
                "manifest_uri": manifest_uri,
                "file_count": len(file_entries),
            })
            
            logger.info(f"  ✓ Manifest for '{table_name}': {manifest_uri} ({len(file_entries)} files)")
        
        logger.info(f"✓ Generated {len(manifests_created)} manifest files")
        
        if self.log_callback:
            self.log_callback(
                migration_id, "INFO", "transfer",
                f"Generated {len(manifests_created)} manifest files for Redshift COPY",
                log_metadata={"manifests": manifests_created},
            )
        
        # Store manifest info in migration checkpoint for the load stage
        from database import get_db
        from models.bq_redshift_migration import MigrationBQRedshift
        from sqlalchemy.orm.attributes import flag_modified
        
        db = next(get_db())
        try:
            migration = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
            if migration:
                checkpoint_data = migration.checkpoint_data or {}
                checkpoint_data["manifests"] = manifests_created
                migration.checkpoint_data = checkpoint_data
                flag_modified(migration, "checkpoint_data")  # CRITICAL: Tell SQLAlchemy JSONB changed
                db.commit()
                logger.info("✓ Manifest info saved to migration checkpoint")
        finally:
            db.close()
    
    def _log_task_history(self, migration_id, migration_name, task_name, task_arn, execution_arn,
                          agent_arn, agent_ip, source_arn, source_uri, dest_arn, dest_uri,
                          status, started_at, table_name=None, files_transferred=0,
                          bytes_transferred=0, error_message=None, error_code=None,
                          error_details=None, raw_result=None):
        """Log a DataSync task to the task_history table."""
        try:
            from database import db_instance
            from models.task_history import TaskHistory
            from datetime import datetime

            end_time = datetime.utcnow()
            duration = (end_time - started_at).total_seconds() if started_at else None

            with db_instance.get_session() as db:
                record = TaskHistory(
                    migration_id=migration_id,
                    migration_name=migration_name or 'Unknown',
                    task_arn=task_arn,
                    execution_arn=execution_arn,
                    task_name=task_name,
                    task_type='datasync',
                    agent_arn=agent_arn,
                    agent_ip=agent_ip,
                    source_location_arn=source_arn,
                    source_uri=source_uri,
                    dest_location_arn=dest_arn,
                    dest_uri=dest_uri,
                    table_name=table_name,
                    status=status,
                    started_at=started_at,
                    completed_at=end_time,
                    duration_seconds=duration,
                    files_transferred=files_transferred or 0,
                    bytes_transferred=bytes_transferred or 0,
                    error_message=error_message,
                    error_code=error_code,
                    error_details=error_details,
                    raw_result=raw_result,
                )
                db.add(record)
        except Exception as log_err:
            logger.warning(f"Failed to log task history: {log_err}")

    def _save_checkpoint(self, migration_id: int, data: Dict):
        """Save key-value pairs into migration checkpoint_data."""
        from database import get_db
        from models.bq_redshift_migration import MigrationBQRedshift
        
        db = next(get_db())
        try:
            mig = db.query(MigrationBQRedshift).filter_by(id=migration_id).first()
            if mig:
                cp = mig.checkpoint_data or {}
                cp.update(data)
                mig.checkpoint_data = cp
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(mig, "checkpoint_data")
                db.commit()
                logger.info(f"Checkpoint saved: {list(data.keys())}")
        finally:
            db.close()
    
    def _get_or_create_agent(
        self,
        migration_id: int,
        agent: 'GCPDataSyncAgent',
        vm_ip: str,
        aws_region: str,
        force_reactivate: bool = False,
    ) -> str:
        """
        Look up the VM IP in the datasync_agents registry.
        If an agent ARN exists and is usable, return it.
        Otherwise activate a new agent and save to registry.
        
        Args:
            migration_id: For logging
            agent: GCPDataSyncAgent instance (used to activate)
            vm_ip: IP address of the DataSync agent VM
            aws_region: AWS region
            force_reactivate: If True, skip registry lookup and re-activate
            
        Returns:
            Agent ARN string
        """
        from database import get_db
        from models.datasync_agent import DataSyncAgent
        
        # Step 1: Check registry (unless forced)
        if not force_reactivate:
            db = next(get_db())
            try:
                existing = db.query(DataSyncAgent).filter_by(vm_ip=vm_ip).first()
                if existing:
                    logger.info(f"Found agent in registry: {existing.agent_arn} (status={existing.status})")
                    
                    # Verify agent is still reachable by describing it
                    try:
                        resp = agent.datasync_client.describe_agent(AgentArn=existing.agent_arn)
                        status = resp.get("Status", "UNKNOWN")
                        
                        if status == "ONLINE":
                            logger.info(f"Agent {existing.agent_arn} is ONLINE — reusing")
                            existing.status = "online"
                            existing.last_used_at = datetime.utcnow()
                            db.commit()
                            
                            if self.log_callback:
                                self.log_callback(migration_id, "INFO", "transfer",
                                    f"Reusing registered agent for VM {vm_ip}: {existing.agent_arn}")
                            return existing.agent_arn
                        else:
                            logger.warning(f"Agent {existing.agent_arn} status is {status} — will re-activate")
                            existing.status = "offline"
                            db.commit()
                    except Exception as e:
                        logger.warning(f"Could not verify agent {existing.agent_arn}: {e} — will re-activate")
            finally:
                db.close()
        
        # Step 2: Activate new agent
        if self.log_callback:
            self.log_callback(migration_id, "INFO", "transfer",
                f"Activating DataSync agent on VM {vm_ip}...")
        
        logger.info(f"Getting activation key from {vm_ip}")
        activation_key = agent.get_activation_key(vm_ip)
        
        if self.log_callback:
            self.log_callback(migration_id, "INFO", "transfer",
                "Registering agent with AWS DataSync service...")
        
        agent_arn = agent.activate_agent(activation_key)
        logger.info(f"Agent activated: {agent_arn}")
        
        if self.log_callback:
            self.log_callback(migration_id, "INFO", "transfer",
                f"Agent activated: {agent_arn}")
        
        # Wait for agent to fully initialize after activation.
        # Freshly activated agents need time to become fully operational.
        # Without this delay, the first DataSync task often fails because
        # the agent hasn't finished its internal initialization.
        logger.info("Waiting 60s for agent to fully initialize after activation...")
        if self.log_callback:
            self.log_callback(migration_id, "INFO", "transfer",
                "Waiting 60 seconds for agent to fully initialize...")
        time.sleep(60)
        
        # Verify agent is ONLINE before proceeding
        for verify_attempt in range(3):
            try:
                resp = agent.datasync_client.describe_agent(AgentArn=agent_arn)
                status = resp.get("Status", "UNKNOWN")
                logger.info(f"Agent status after wait: {status}")
                if status == "ONLINE":
                    logger.info("Agent is ONLINE and ready for tasks")
                    if self.log_callback:
                        self.log_callback(migration_id, "INFO", "transfer",
                            "Agent is ONLINE and ready for tasks")
                    break
                else:
                    logger.warning(f"Agent status is {status}, waiting 30s more...")
                    if self.log_callback:
                        self.log_callback(migration_id, "INFO", "transfer",
                            f"Agent status: {status}, waiting for ONLINE...")
                    time.sleep(30)
            except Exception as e:
                logger.warning(f"Could not verify agent status: {e}, waiting 30s...")
                time.sleep(30)
        
        # Step 3: Save to registry (upsert)
        db = next(get_db())
        try:
            existing = db.query(DataSyncAgent).filter_by(vm_ip=vm_ip).first()
            if existing:
                existing.agent_arn = agent_arn
                existing.aws_region = aws_region
                existing.status = "online"
                existing.last_used_at = datetime.utcnow()
                logger.info(f"Updated agent registry: {vm_ip} -> {agent_arn}")
            else:
                new_agent = DataSyncAgent(
                    vm_ip=vm_ip,
                    agent_arn=agent_arn,
                    aws_region=aws_region,
                    status="online",
                )
                db.add(new_agent)
                logger.info(f"Added to agent registry: {vm_ip} -> {agent_arn}")
            db.commit()
        finally:
            db.close()
        
        # Also save to migration checkpoint for backward compatibility
        self._save_checkpoint(migration_id, {"datasync_agent_arn": agent_arn})
        
        return agent_arn
    
    def _decrypt_gcs_secret(self, storage_config: Dict, migration_id: int) -> Optional[str]:
        """Decrypt GCS HMAC secret key."""
        encrypted = storage_config.get("gcs_secret_key_encrypted", "")
        if not encrypted:
            return None
        try:
            from services.unified_kms_service import get_unified_kms_service
            kms = get_unified_kms_service()
            return kms.decrypt_credential(
                ciphertext=encrypted,
                credential_type='gcp_hmac_secret',
                resource_type='migration',
                allow_plaintext_fallback=True
            )
        except Exception:
            logger.warning("KMS decryption failed, using value as-is (dev mode)")
            return encrypted
    
    def _decrypt_aws_secret(self, storage_config: Dict, migration_id: int) -> Optional[str]:
        """Decrypt AWS secret access key."""
        encrypted = storage_config.get("aws_secret_access_key_encrypted", "")
        if not encrypted:
            return None
        try:
            from services.unified_kms_service import get_unified_kms_service
            kms = get_unified_kms_service()
            # Note: resource_id is NOT passed because it was not included
            # in the encryption context when the credential was encrypted.
            # Encryption context must match exactly for KMS decryption.
            return kms.decrypt_credential(
                ciphertext=encrypted,
                credential_type='aws_secret_key',
                resource_type='migration',
                allow_plaintext_fallback=True
            )
        except Exception:
            logger.warning("KMS decryption failed, using value as-is (dev mode)")
            return encrypted
    
    def _get_service_account_info(self, storage_config: Dict, migration_id: int) -> Optional[Dict]:
        """Get decrypted service account JSON as dict."""
        encrypted = storage_config.get("service_account_json_encrypted", "")
        if not encrypted:
            return None
        try:
            from services.unified_kms_service import get_unified_kms_service
            kms = get_unified_kms_service()
            sa_json = kms.decrypt_credential(
                ciphertext=encrypted,
                credential_type='gcp_service_account',
                resource_type='migration',
                allow_plaintext_fallback=True
            )
        except Exception:
            sa_json = encrypted
        
        import json
        try:
            return json.loads(sa_json) if sa_json else None
        except json.JSONDecodeError:
            return None
    
    def validate_migration(self, migration_id: int, source_config: Dict, target_config: Dict) -> Dict:
        return {
            "migration_id": migration_id,
            "valid": True,
            "validated_at": datetime.utcnow().isoformat(),
            "tables": {},
        }
