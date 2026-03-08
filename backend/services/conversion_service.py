"""
Conversion Service

Service for managing SQL code conversions using AWS Bedrock and SQLGlot.
Handles standalone and batch conversion workflows with retry logic.
"""

import logging
import os
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models.conversion_job_db import ConversionJob, ConversionBatch, ConversionLog
from models.conversion_job import ConversionJobCreate
from models.conversion_batch import ConversionBatchCreate
from models.conversion_log import ConversionLogCreate
from services.sqlglot_parser import SQLGlotParser, TranspileResult
from services.bedrock_client import BedrockClient, BedrockResponse, BedrockThrottlingError
from utils.unescape import extract_code_from_markdown

logger = logging.getLogger(__name__)


class ConversionService:
    """
    Service for managing SQL code conversions using AWS Bedrock and SQLGlot.
    Handles standalone and batch conversion workflows with retry logic.
    """
    
    def __init__(
        self,
        db: Session,
        redis_client: Optional[Any] = None
    ):
        """
        Initialize conversion service.
        
        Args:
            db: Database session
            redis_client: Redis client for caching
        """
        self.db = db
        self.redis_client = redis_client
        self.sqlglot_parser = SQLGlotParser()
        self.bedrock_client = BedrockClient()
        self.logger = logger
        
        # Configuration from environment
        self.default_model = os.getenv(
            'AWS_BEDROCK_DEFAULT_MODEL',
            'anthropic.claude-v2'
        )
        self.max_retries = int(os.getenv('CONVERSION_MAX_RETRIES', '3'))
        self.batch_parallelism = int(os.getenv('CONVERSION_BATCH_PARALLELISM', '5'))
    
    async def convert_standalone(
        self,
        workspace_id: int,
        user_id: int,
        source_code: str,
        source_dialect: str,
        target_dialect: str,
        asset_type: str,
        bedrock_model: Optional[str] = None,
        use_sqlglot: bool = True,
        prompt_template_path: Optional[str] = None,
        asset_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Convert a single SQL code snippet.
        
        Args:
            workspace_id: Workspace identifier for isolation
            user_id: User performing conversion
            source_code: SQL code to convert
            source_dialect: Source database dialect
            target_dialect: Target database dialect
            asset_type: Type of asset (view, stored_procedure, function, etc.)
            bedrock_model: AWS Bedrock model ID (optional)
            use_sqlglot: Whether to attempt SQLGlot first
            prompt_template_path: Custom prompt template path
            asset_name: Name of the asset
            
        Returns:
            Dictionary with job details
        """
        # Create conversion job record
        job = ConversionJob(
            workspace_id=workspace_id,
            source_code=source_code,
            source_dialect=source_dialect.lower(),
            target_dialect=target_dialect.lower(),
            asset_type=asset_type,
            asset_name=asset_name,
            bedrock_model=bedrock_model or self.default_model,
            aws_region=self.bedrock_client.aws_region,
            use_sqlglot=use_sqlglot,
            prompt_template_path=prompt_template_path,
            status='pending',
            created_by=user_id
        )
        
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        job_id = job.id
        
        try:
            # Log start
            self._create_log(
                job_id, workspace_id, 'conversion_started',
                f'Starting conversion from {source_dialect} to {target_dialect}'
            )
            
            # Update status to processing
            job.status = 'processing'
            self.db.commit()
            
            target_code = None
            sqlglot_success = False
            
            # Try SQLGlot first if enabled
            if use_sqlglot:
                self._create_log(
                    job_id, workspace_id, 'sqlglot_parse_started',
                    'Attempting SQLGlot transpilation'
                )
                
                transpile_result = self.sqlglot_parser.parse_and_transpile(
                    source_code, source_dialect, target_dialect
                )
                
                if transpile_result.success:
                    target_code = transpile_result.transpiled_code
                    sqlglot_success = True
                    
                    self._create_log(
                        job_id, workspace_id, 'sqlglot_parse_completed',
                        'SQLGlot transpilation successful'
                    )
                else:
                    self._create_log(
                        job_id, workspace_id, 'sqlglot_parse_failed',
                        f'SQLGlot failed: {transpile_result.error_message}',
                        log_level='WARNING'
                    )
            
            # Fallback to Bedrock if SQLGlot failed or disabled
            if not target_code:
                self._create_log(
                    job_id, workspace_id, 'bedrock_invocation_started',
                    f'Invoking Bedrock model {bedrock_model or self.default_model}'
                )
                
                # Load prompt template
                prompt = self._build_prompt(
                    source_code, source_dialect, target_dialect,
                    asset_type, prompt_template_path
                )
                
                # Invoke Bedrock
                bedrock_response = await self.bedrock_client.invoke_model(
                    model_id=bedrock_model or self.default_model,
                    prompt=prompt,
                    workspace_id=workspace_id
                )
                
                # Extract code from markdown
                target_code = extract_code_from_markdown(bedrock_response.generated_text)
                
                self._create_log(
                    job_id, workspace_id, 'bedrock_invocation_completed',
                    f'Bedrock invocation successful',
                    duration_ms=bedrock_response.duration_ms
                )
            
            # Update job with results
            job.target_code = target_code
            job.sqlglot_success = sqlglot_success
            job.status = 'completed'
            self.db.commit()
            
            self._create_log(
                job_id, workspace_id, 'conversion_completed',
                'Conversion completed successfully'
            )
            
            # Cache result
            self._cache_job(job)
            
            return {
                'job_id': job.id,
                'status': job.status,
                'target_code': job.target_code,
                'sqlglot_success': job.sqlglot_success,
                'created_at': job.created_at
            }
            
        except Exception as e:
            # Update job with error
            job.status = 'failed'
            job.error_message = str(e)
            self.db.commit()
            
            self._create_log(
                job_id, workspace_id, 'conversion_failed',
                f'Conversion failed: {str(e)}',
                log_level='ERROR'
            )
            
            raise
    
    async def convert_batch(
        self,
        workspace_id: int,
        user_id: int,
        source_connection_id: int,
        target_connection_id: int,
        asset_list: List[Dict[str, Any]],
        bedrock_model: Optional[str] = None,
        use_sqlglot: bool = True,
        max_retries: int = 3,
        migration_project_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Convert multiple SQL assets in batch.
        
        Args:
            workspace_id: Workspace identifier
            user_id: User performing conversion
            source_connection_id: Source database connection
            target_connection_id: Target database connection
            asset_list: List of assets to convert
            bedrock_model: AWS Bedrock model ID
            use_sqlglot: Whether to attempt SQLGlot first
            max_retries: Maximum retry attempts per job
            migration_project_id: Optional migration project ID
            
        Returns:
            Dictionary with batch details
        """
        from models.connection import Connection
        
        # Validate connections belong to workspace
        source_conn = self.db.query(Connection).filter(
            and_(
                Connection.id == source_connection_id,
                Connection.workspace_id == workspace_id
            )
        ).first()
        
        target_conn = self.db.query(Connection).filter(
            and_(
                Connection.id == target_connection_id,
                Connection.workspace_id == workspace_id
            )
        ).first()
        
        if not source_conn or not target_conn:
            raise ValueError("Invalid connection IDs or access denied")
        
        # Create batch record
        batch = ConversionBatch(
            workspace_id=workspace_id,
            migration_project_id=migration_project_id,
            source_connection_id=source_connection_id,
            target_connection_id=target_connection_id,
            bedrock_model=bedrock_model or self.default_model,
            aws_region=self.bedrock_client.aws_region,
            use_sqlglot=use_sqlglot,
            max_retries=max_retries,
            status='pending',
            total_assets=len(asset_list),
            created_by=user_id
        )
        
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        
        batch_id = batch.id
        
        # Create individual jobs for each asset
        jobs = []
        for asset in asset_list:
            job = ConversionJob(
                workspace_id=workspace_id,
                batch_id=batch_id,
                source_code=asset.get('source_code', ''),
                source_dialect=source_conn.db_type.lower(),
                target_dialect=target_conn.db_type.lower(),
                asset_type=asset.get('asset_type', 'other'),
                asset_name=asset.get('asset_name'),
                bedrock_model=bedrock_model or self.default_model,
                aws_region=self.bedrock_client.aws_region,
                use_sqlglot=use_sqlglot,
                status='pending',
                created_by=user_id
            )
            self.db.add(job)
            jobs.append(job)
        
        self.db.commit()
        
        # Update batch status to processing
        batch.status = 'processing'
        self.db.commit()
        
        # Process jobs asynchronously with parallelism limit
        asyncio.create_task(
            self._process_batch_jobs(batch_id, workspace_id, user_id)
        )
        
        return {
            'batch_id': batch.id,
            'status': batch.status,
            'total_assets': batch.total_assets,
            'completed_assets': batch.completed_assets,
            'failed_assets': batch.failed_assets,
            'created_at': batch.created_at
        }
    
    async def _process_batch_jobs(
        self,
        batch_id: int,
        workspace_id: int,
        user_id: int
    ):
        """Process batch jobs with parallelism limit"""
        # Get all pending jobs for batch
        jobs = self.db.query(ConversionJob).filter(
            and_(
                ConversionJob.batch_id == batch_id,
                ConversionJob.workspace_id == workspace_id,
                ConversionJob.status == 'pending'
            )
        ).all()
        
        # Process jobs with parallelism limit
        semaphore = asyncio.Semaphore(self.batch_parallelism)
        
        async def process_job(job):
            async with semaphore:
                try:
                    await self.convert_standalone(
                        workspace_id=workspace_id,
                        user_id=user_id,
                        source_code=job.source_code,
                        source_dialect=job.source_dialect,
                        target_dialect=job.target_dialect,
                        asset_type=job.asset_type,
                        bedrock_model=job.bedrock_model,
                        use_sqlglot=job.use_sqlglot,
                        asset_name=job.asset_name
                    )
                    
                    # Increment completed counter
                    batch = self.db.query(ConversionBatch).filter(
                        ConversionBatch.id == batch_id
                    ).first()
                    if batch:
                        batch.completed_assets += 1
                        self.db.commit()
                        
                except Exception as e:
                    self.logger.error(f"Job {job.id} failed: {str(e)}")
                    
                    # Increment failed counter
                    batch = self.db.query(ConversionBatch).filter(
                        ConversionBatch.id == batch_id
                    ).first()
                    if batch:
                        batch.failed_assets += 1
                        self.db.commit()
        
        # Process all jobs
        await asyncio.gather(*[process_job(job) for job in jobs])
        
        # Update batch status to completed
        batch = self.db.query(ConversionBatch).filter(
            ConversionBatch.id == batch_id
        ).first()
        if batch:
            batch.status = 'completed'
            self.db.commit()
    
    def get_job(
        self,
        job_id: int,
        workspace_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get conversion job by ID.
        
        Args:
            job_id: Job identifier
            workspace_id: Workspace identifier
            
        Returns:
            Job details or None
        """
        # Try cache first
        cached = self._get_cached_job(job_id)
        if cached:
            return cached
        
        # Query database
        job = self.db.query(ConversionJob).filter(
            and_(
                ConversionJob.id == job_id,
                ConversionJob.workspace_id == workspace_id
            )
        ).first()
        
        if not job:
            return None
        
        result = {
            'job_id': job.id,
            'workspace_id': job.workspace_id,
            'batch_id': job.batch_id,
            'source_code': job.source_code,
            'target_code': job.target_code,
            'source_dialect': job.source_dialect,
            'target_dialect': job.target_dialect,
            'asset_type': job.asset_type,
            'asset_name': job.asset_name,
            'bedrock_model': job.bedrock_model,
            'use_sqlglot': job.use_sqlglot,
            'sqlglot_success': job.sqlglot_success,
            'status': job.status,
            'error_message': job.error_message,
            'retry_count': job.retry_count,
            'created_at': job.created_at,
            'updated_at': job.updated_at
        }
        
        # Cache result
        if job.status in ['completed', 'failed']:
            self._cache_job_dict(job_id, result)
        
        return result
    
    def get_batch(
        self,
        batch_id: int,
        workspace_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get conversion batch by ID.
        
        Args:
            batch_id: Batch identifier
            workspace_id: Workspace identifier
            
        Returns:
            Batch details or None
        """
        batch = self.db.query(ConversionBatch).filter(
            and_(
                ConversionBatch.id == batch_id,
                ConversionBatch.workspace_id == workspace_id
            )
        ).first()
        
        if not batch:
            return None
        
        return {
            'batch_id': batch.id,
            'workspace_id': batch.workspace_id,
            'source_connection_id': batch.source_connection_id,
            'target_connection_id': batch.target_connection_id,
            'status': batch.status,
            'total_assets': batch.total_assets,
            'completed_assets': batch.completed_assets,
            'failed_assets': batch.failed_assets,
            'created_at': batch.created_at,
            'updated_at': batch.updated_at
        }
    
    def _build_prompt(
        self,
        source_code: str,
        source_dialect: str,
        target_dialect: str,
        asset_type: str,
        template_path: Optional[str] = None
    ) -> str:
        """Build prompt for Bedrock model"""
        
        if template_path:
            # Load custom template
            try:
                return self.bedrock_client.load_prompt_template(
                    template_path,
                    {
                        'source_code': source_code,
                        'source_dialect': source_dialect,
                        'target_dialect': target_dialect,
                        'asset_type': asset_type
                    }
                )
            except Exception as e:
                self.logger.warning(f"Failed to load template: {str(e)}, using default")
        
        # Default prompt
        return f"""Convert the following {source_dialect} {asset_type} to {target_dialect}.

Source SQL ({source_dialect}):
```sql
{source_code}
```

Please provide the converted {target_dialect} SQL code. Return only the SQL code in a markdown code block."""
    
    def _create_log(
        self,
        job_id: int,
        workspace_id: int,
        step_name: str,
        message: str,
        log_level: str = 'INFO',
        duration_ms: Optional[int] = None
    ):
        """Create conversion log entry"""
        log = ConversionLog(
            job_id=job_id,
            workspace_id=workspace_id,
            step_name=step_name,
            message=message,
            log_level=log_level,
            duration_ms=duration_ms
        )
        
        self.db.add(log)
        self.db.commit()
    
    def _cache_job(self, job):
        """Cache job in Redis"""
        if not self.redis_client:
            return
        
        try:
            import json
            cache_key = f"conversion:job:{job.id}"
            cache_data = {
                'job_id': job.id,
                'status': job.status,
                'target_code': job.target_code,
                'sqlglot_success': job.sqlglot_success
            }
            
            # Cache for 1 hour
            self.redis_client.setex(
                cache_key,
                3600,
                json.dumps(cache_data, default=str)
            )
        except Exception as e:
            self.logger.warning(f"Failed to cache job: {str(e)}")
    
    def _cache_job_dict(self, job_id: int, data: Dict[str, Any]):
        """Cache job dictionary in Redis"""
        if not self.redis_client:
            return
        
        try:
            import json
            cache_key = f"conversion:job:{job_id}"
            
            # Cache for 1 hour
            self.redis_client.setex(
                cache_key,
                3600,
                json.dumps(data, default=str)
            )
        except Exception as e:
            self.logger.warning(f"Failed to cache job: {str(e)}")
    
    def _get_cached_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get cached job from Redis"""
        if not self.redis_client:
            return None
        
        try:
            import json
            cache_key = f"conversion:job:{job_id}"
            cached = self.redis_client.get(cache_key)
            
            if cached:
                return json.loads(cached)
        except Exception as e:
            self.logger.warning(f"Failed to get cached job: {str(e)}")
        
        return None
