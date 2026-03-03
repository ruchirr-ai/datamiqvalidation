"""
GCP DataSync Agent Deployer

Deploys AWS DataSync agent on Google Cloud Platform Compute Engine VM.
This enables secure, private network transfer from GCS to S3 without exposing data to public internet.

Architecture:
- DataSync agent runs on GCP Compute Engine VM
- VM is in same VPC/region as GCS bucket
- Agent connects to GCS via private network
- Agent transfers data to S3 via AWS DataSync service
"""

import logging
import time
import requests
from typing import Dict, Any, Optional, List
from google.cloud import compute_v1
from google.oauth2 import service_account
import json

logger = logging.getLogger(__name__)


class GCPDataSyncDeployer:
    """
    Deploys and manages AWS DataSync agent on GCP Compute Engine.
    
    Features:
    - Deploy DataSync agent from AWS-provided image
    - Use existing VM or create new VM
    - Automatic agent activation
    - Private network connectivity to GCS
    - Secure transfer to S3
    """
    
    def __init__(
        self,
        project_id: str,
        credentials_json: str,
        zone: str = "us-central1-a"
    ):
        """
        Initialize GCP DataSync Deployer.
        
        Args:
            project_id: GCP project ID
            credentials_json: Service account JSON credentials
            zone: GCP zone for VM deployment
        """
        self.project_id = project_id
        self.zone = zone
        
        # Parse credentials
        if isinstance(credentials_json, str):
            credentials_dict = json.loads(credentials_json)
        else:
            credentials_dict = credentials_json
        
        # Create credentials
        self.credentials = service_account.Credentials.from_service_account_info(
            credentials_dict
        )
        
        # Initialize GCP clients
        self.compute_client = compute_v1.InstancesClient(credentials=self.credentials)
        self.images_client = compute_v1.ImagesClient(credentials=self.credentials)
        
        self.instance_name: Optional[str] = None
        self.instance_internal_ip: Optional[str] = None
        self.instance_external_ip: Optional[str] = None
    
    def list_existing_vms(self) -> List[Dict[str, Any]]:
        """
        List existing VMs in the project that could be used for DataSync.
        
        Returns:
            List of VM instances with their details
        """
        try:
            logger.info(f"Listing VMs in project {self.project_id}, zone {self.zone}")
            
            request = compute_v1.ListInstancesRequest(
                project=self.project_id,
                zone=self.zone
            )
            
            instances = []
            for instance in self.compute_client.list(request=request):
                # Get network interface details
                internal_ip = None
                external_ip = None
                if instance.network_interfaces:
                    internal_ip = instance.network_interfaces[0].network_i_p
                    if instance.network_interfaces[0].access_configs:
                        external_ip = instance.network_interfaces[0].access_configs[0].nat_i_p
                
                instances.append({
                    'name': instance.name,
                    'status': instance.status,
                    'machine_type': instance.machine_type.split('/')[-1],
                    'internal_ip': internal_ip,
                    'external_ip': external_ip,
                    'zone': self.zone,
                    'tags': list(instance.tags.items) if instance.tags else []
                })
            
            logger.info(f"Found {len(instances)} VMs")
            return instances
            
        except Exception as e:
            logger.error(f"Failed to list VMs: {e}")
            raise
    
    def check_vm_exists(self, instance_name: str) -> bool:
        """
        Check if a VM with given name exists.
        
        Args:
            instance_name: Name of the VM instance
            
        Returns:
            True if VM exists, False otherwise
        """
        try:
            request = compute_v1.GetInstanceRequest(
                project=self.project_id,
                zone=self.zone,
                instance=instance_name
            )
            
            instance = self.compute_client.get(request=request)
            return instance is not None
            
        except Exception:
            return False
    
    def get_vm_details(self, instance_name: str) -> Dict[str, Any]:
        """
        Get details of an existing VM.
        
        Args:
            instance_name: Name of the VM instance
            
        Returns:
            VM details dictionary
        """
        try:
            logger.info(f"Getting details for VM: {instance_name}")
            
            request = compute_v1.GetInstanceRequest(
                project=self.project_id,
                zone=self.zone,
                instance=instance_name
            )
            
            instance = self.compute_client.get(request=request)
            
            # Extract network details
            internal_ip = None
            external_ip = None
            if instance.network_interfaces:
                internal_ip = instance.network_interfaces[0].network_i_p
                if instance.network_interfaces[0].access_configs:
                    external_ip = instance.network_interfaces[0].access_configs[0].nat_i_p
            
            return {
                'name': instance.name,
                'status': instance.status,
                '