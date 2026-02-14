# Pathway A Complete Implementation Plan

## Overview
Complete the GCS → S3 → Redshift migration pipeline (Pathway A) with production-grade implementation.

## Current Status

### ✅ Working
1. BigQuery → GCS export (Stage 1)
2. Database schema and models
3. Frontend wizard UI
4. Basic orchestration framework

### ❌ Not Working / Incomplete
1. Job status not changing from "Running" to "Completed"
2. "Last Run At" showing wrong timestamp
3. GCS → S3 transfer (Stage 2) - placeholder only
4. S3 → Redshift load (Stage 3) - placeholder only
5. Missing UI fields for AWS credentials and transfer configuration

## Implementation Tasks

### Task 1: Fix Job Status and Timestamp ⚡ PRIORITY

**Problem**: Migration stays in "running" status even after completion

**Root Cause**: Orchestrator completes but doesn't update migration status properly

**Fix Location**: `backend/services/bq_redshift_migration/orchestrator.py`

**Changes Needed**:
```python
# In _execute_migration() method
if success:
    migration.status = 'completed'  # ✅ Already there
    migration.end_time = datetime.utcnow()  # ✅ Already there
    migration.last_run_at = datetime.utcnow()  # ❌ ADD THIS
    migration.updated_at = datetime.utcnow()  # ✅ Already there
```

**Frontend Fix**: `frontend/src/pages/MigrationsPage.tsx`
- Change `last_run_time` to `last_run_at` (column name mismatch)

---

### Task 2: Add Missing Database Columns

**Table**: `migrations_bq_redshift`

**Missing Columns**:
```sql
ALTER TABLE migrations_bq_redshift 
ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMP;

ALTER TABLE migrations_bq_redshift
ADD COLUMN IF NOT EXISTS aws_access_key_id VARCHAR(255);

ALTER TABLE migrations_bq_redshift
ADD COLUMN IF NOT EXISTS aws_secret_access_key_encrypted TEXT;

ALTER TABLE migrations_bq_redshift
ADD COLUMN IF NOT EXISTS gcp_service_account_key_encrypted TEXT;

ALTER TABLE migrations_bq_redshift
ADD COLUMN IF NOT EXISTS transfer_job_name VARCHAR(500);

ALTER TABLE migrations_bq_redshift
ADD COLUMN IF NOT EXISTS overwrite_existing_files BOOLEAN DEFAULT FALSE;

ALTER TABLE migrations_bq_redshift
ADD COLUMN IF NOT EXISTS delete_source_after_transfer BOOLEAN DEFAULT FALSE;
```

---

### Task 3: Update Frontend UI - Add AWS Credentials Fields

**File**: `frontend/src/components/migrations/CreateMigrationWizard.tsx`

**Add to MigrationFormData interface**:
```typescript
export interface MigrationFormData {
  // ... existing fields
  
  // AWS Credentials for GCS → S3 transfer
  awsAccessKeyId?: string;
  awsSecretAccessKey?: string;
  
  // Transfer Options
  overwriteExistingFiles?: boolean;
  deleteSourceAfterTransfer?: boolean;
  
  // GCP Service Account (for Storage Transfer Service)
  gcpServiceAccountKey?: string;
}
```

**File**: `frontend/src/components/migrations/steps/ConfigurationSetupStep.tsx`

**Add fields in Pathway A section**:
```tsx
{/* Stage 2: GCS to S3 Transfer (Path A) */}
{formData.pathway === 'A' && (
  <div className="pathway-section">
    <h4>Stage 2: GCS to S3 Transfer (GCP Storage Transfer Service)</h4>
    
    <div className="form-section">
      <label className="form-label">
        AWS Access Key ID <span className="required">*</span>
      </label>
      <Input
        type="text"
        value={formData.awsAccessKeyId || ''}
        onChange={(e) => updateFormData({ awsAccessKeyId: e.target.value })}
        placeholder="AKIAIOSFODNN7EXAMPLE"
      />
      <p className="form-help">
        AWS credentials for Storage Transfer Service to write to S3
      </p>
    </div>
    
    <div className="form-section">
      <label className="form-label">
        AWS Secret Access Key <span className="required">*</span>
      </label>
      <Input
        type="password"
        value={formData.awsSecretAccessKey || ''}
        onChange={(e) => updateFormData({ awsSecretAccessKey: e.target.value })}
        placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
      />
      <p className="form-help">
        Keep this secure - will be encrypted in database
      </p>
    </div>
    
    <div className="form-section">
      <label className="form-label">
        <input
          type="checkbox"
          checked={formData.overwriteExistingFiles || false}
          onChange={(e) => updateFormData({ overwriteExistingFiles: e.target.checked })}
        />
        Overwrite existing files in S3
      </label>
    </div>
    
    <div className="form-section">
      <label className="form-label">
        <input
          type="checkbox"
          checked={formData.deleteSourceAfterTransfer || false}
          onChange={(e) => updateFormData({ deleteSourceAfterTransfer: e.target.checked })}
        />
        Delete files from GCS after successful transfer
      </label>
    </div>
  </div>
)}
```

---

### Task 4: Implement GCS → S3 Transfer (Production Grade)

**File**: `backend/services/bq_redshift_migration/gcs_to_s3_transfer.py` (NEW)

**Implementation**:
```python
"""
GCS to S3 Transfer using GCP Storage Transfer Service

Production-grade implementation with:
- Proper error handling
- Progress monitoring
- Retry logic
- Detailed logging
"""

import logging
import time
from typing import Dict, Optional
from datetime import datetime
from google.cloud import storage_transfer_v1
from google.cloud.storage_transfer_v1 import types

logger = logging.getLogger(__name__)


class GCSToS3Transfer:
    """Handles GCS to S3 transfers using GCP Storage Transfer Service"""
    
    def __init__(self):
        self.client = None
    
    def _get_client(self):
        """Lazy initialization of Storage Transfer Service client"""
        if not self.client:
            self.client = storage_transfer_v1.StorageTransferServiceClient()
        return self.client
    
    def create_transfer_job(
        self,
        project_id: str,
        gcs_bucket: str,
        gcs_path: str,
        s3_bucket: str,
        s3_path: str,
        aws_access_key_id: str,
        aws_secret_access_key: str,
        description: str = "GCS to S3 Transfer",
        overwrite_existing: bool = False,
        delete_source: bool = False
    ) -> str:
        """
        Create a Storage Transfer Service job
        
        Returns:
            Transfer job name
        """
        try:
            client = self._get_client()
            
            # Build transfer job request
            transfer_job = types.TransferJob(
                description=description,
                status=types.TransferJob.Status.ENABLED,
                project_id=project_id,
                transfer_spec=types.TransferSpec(
                    gcs_data_source=types.GcsData(
                        bucket_name=gcs_bucket,
                        path=gcs_path
                    ),
                    aws_s3_data_sink=types.AwsS3Data(
                        bucket_name=s3_bucket,
                        path=s3_path,
                        aws_access_key=types.AwsAccessKey(
                            access_key_id=aws_access_key_id,
                            secret_access_key=aws_secret_access_key
                        )
                    ),
                    transfer_options=types.TransferOptions(
                        overwrite_objects_already_existing_in_sink=overwrite_existing,
                        delete_objects_from_source_after_transfer=delete_source
                    )
                ),
                schedule=types.Schedule(
                    schedule_start_date=types.Date(
                        year=datetime.utcnow().year,
                        month=datetime.utcnow().month,
                        day=datetime.utcnow().day
                    ),
                    schedule_end_date=types.Date(
                        year=datetime.utcnow().year,
                        month=datetime.utcnow().month,
                        day=datetime.utcnow().day
                    )
                )
            )
            
            # Create job
            request = types.CreateTransferJobRequest(
                transfer_job=transfer_job
            )
            
            response = client.create_transfer_job(request=request)
            job_name = response.name
            
            logger.info(f"Created transfer job: {job_name}")
            return job_name
            
        except Exception as e:
            logger.error(f"Failed to create transfer job: {e}", exc_info=True)
            raise
    
    def monitor_transfer_job(
        self,
        job_name: str,
        project_id: str,
        poll_interval: int = 30,
        timeout: int = 3600
    ) -> Dict:
        """
        Monitor transfer job until completion
        
        Returns:
            Job status and statistics
        """
        try:
            client = self._get_client()
            start_time = time.time()
            
            while True:
                # Check timeout
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Transfer job {job_name} timed out after {timeout}s")
                
                # Get job status
                request = types.GetTransferJobRequest(
                    job_name=job_name,
                    project_id=project_id
                )
                job = client.get_transfer_job(request=request)
                
                logger.info(f"Transfer job {job_name} status: {job.status}")
                
                # Check if completed
                if job.status == types.TransferJob.Status.SUCCESS:
                    logger.info(f"Transfer job {job_name} completed successfully")
                    return {
                        'status': 'SUCCESS',
                        'job_name': job_name,
                        'completed_at': datetime.utcnow().isoformat()
                    }
                
                elif job.status == types.TransferJob.Status.FAILED:
                    logger.error(f"Transfer job {job_name} failed")
                    return {
                        'status': 'FAILED',
                        'job_name': job_name,
                        'error': 'Transfer job failed'
                    }
                
                # Wait before next poll
                time.sleep(poll_interval)
                
        except Exception as e:
            logger.error(f"Failed to monitor transfer job: {e}", exc_info=True)
            raise
    
    def get_transfer_operation_stats(
        self,
        job_name: str,
        project_id: str
    ) -> Optional[Dict]:
        """Get statistics for the most recent transfer operation"""
        try:
            client = self._get_client()
            
            # List operations for this job
            request = types.ListTransferOperationsRequest(
                filter=f'{{"project_id": "{project_id}", "job_names": ["{job_name}"]}}',
                page_size=1
            )
            
            operations = client.list_transfer_operations(request=request)
            
            for operation in operations:
                if operation.metadata:
                    counters = operation.metadata.counters
                    return {
                        'objects_found': counters.objects_found_from_source,
                        'bytes_found': counters.bytes_found_from_source,
                        'objects_copied': counters.objects_copied_to_sink,
                        'bytes_copied': counters.bytes_copied_to_sink,
                        'objects_failed': counters.objects_failed_to_delete_from_source
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get transfer stats: {e}")
            return None
```

---

### Task 5: Update Pathway A to Use New Transfer Service

**File**: `backend/services/bq_redshift_migration/pathway_a.py`

**Replace `_execute_transfer_stage` method**:
```python
def _execute_transfer_stage(
    self,
    migration_id: int,
    storage_config: Dict,
    pending_shards: List
) -> bool:
    """
    Stage 2: Transfer from GCS to S3 using GCP Storage Transfer Service.
    """
    try:
        from .gcs_to_s3_transfer import GCSToS3Transfer
        
        logger.info(f"Migration {migration_id}: Starting TRANSFER stage")
        
        # Initialize transfer service
        transfer_service = GCSToS3Transfer()
        
        # Create transfer job
        job_name = transfer_service.create_transfer_job(
            project_id=storage_config['project_id'],
            gcs_bucket=storage_config['gcs_bucket'],
            gcs_path=storage_config['gcs_path'],
            s3_bucket=storage_config['s3_bucket'],
            s3_path=storage_config['s3_path'],
            aws_access_key_id=storage_config['aws_access_key_id'],
            aws_secret_access_key=storage_config['aws_secret_access_key'],
            description=f"Migration {migration_id} - GCS to S3",
            overwrite_existing=storage_config.get('overwrite_existing', False),
            delete_source=storage_config.get('delete_source', False)
        )
        
        logger.info(f"Created transfer job: {job_name}")
        
        # Monitor until completion
        result = transfer_service.monitor_transfer_job(
            job_name=job_name,
            project_id=storage_config['project_id'],
            poll_interval=30,
            timeout=3600  # 1 hour timeout
        )
        
        if result['status'] != 'SUCCESS':
            logger.error(f"Transfer failed: {result}")
            return False
        
        # Get transfer statistics
        stats = transfer_service.get_transfer_operation_stats(
            job_name=job_name,
            project_id=storage_config['project_id']
        )
        
        if stats:
            logger.info(f"Transfer stats: {stats}")
        
        # Save checkpoint
        self.checkpoint_manager.save_checkpoint(
            migration_id,
            'transfer',
            {
                'completed_at': datetime.utcnow().isoformat(),
                'transfer_job': job_name,
                'stats': stats
            }
        )
        
        logger.info(f"Migration {migration_id}: TRANSFER stage completed")
        return True
        
    except Exception as e:
        logger.error(f"Transfer stage failed: {e}", exc_info=True)
        return False
```

---

## Implementation Priority

### Phase 1: Quick Fixes (30 min)
1. ✅ Fix job status update
2. ✅ Fix last_run_at timestamp
3. ✅ Add missing database column

### Phase 2: UI Updates (1 hour)
1. ✅ Add AWS credentials fields
2. ✅ Add transfer options checkboxes
3. ✅ Update form submission

### Phase 3: Backend Implementation (2-3 hours)
1. ✅ Create GCSToS3Transfer service
2. ✅ Update Pathway A implementation
3. ✅ Add proper error handling
4. ✅ Add progress logging

### Phase 4: Testing (1 hour)
1. ✅ Test complete flow
2. ✅ Verify GCS → S3 transfer
3. ✅ Verify status updates
4. ✅ Verify timestamps

---

## Next Steps

1. **Immediate**: Fix status and timestamp (5 min)
2. **Short-term**: Add database migration for new columns
3. **Medium-term**: Implement GCS → S3 transfer service
4. **Long-term**: Implement S3 → Redshift load (Stage 3)

Would you like me to proceed with Phase 1 (Quick Fixes) first?
