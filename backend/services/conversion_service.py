"""
Conversion Service

Core orchestration logic for standalone and batch code conversions.
Coordinates sqlglot parsing, Bedrock invocation, retry logic, persistence,
and cache management. All operations enforce workspace_id tenant isolation.
"""

import logging
import time
import random
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from models.conversion_job import ConversionJob
from models.conversion_batch import ConversionBatch
from models.conversion_log import ConversionLog, ConversionLogStepName
from models.conversion_schemas import (
    StandaloneConversionRequest,
    BatchConversionRequest,
    ALLOWED_SOURCE_DIALECTS,
    ALLOWED_TARGET_DIALECTS,
)
from repositories.conversion_repository import ConversionRepository
from services.audit_logger import AuditLogger
from services.bedrock_client import BedrockClient, BedrockModel
from services.sqlglot_parser import SqlGlotParser
from services.conversion_cache import ConversionCache
from utils.unescape import unescape_code_output

logger = logging.getLogger(__name__)


class ConversionService:
    """Orchestrates code conversion workflows."""

    def __init__(self, db: Session, cache: ConversionCache) -> None:
        self.repo = ConversionRepository(db)
        self.cache = cache
        self.bedrock_client = BedrockClient()
        self.sqlglot_parser = SqlGlotParser()
        self.audit_logger = AuditLogger(db)

    # ── Log helper ────────────────────────────────────────────────────

    def _create_log(
        self,
        job_id: int,
        workspace_id: int,
        step_name: str,
        message: str,
        log_level: str = "INFO",
        duration_ms: Optional[int] = None,
    ) -> None:
        """Persist a ConversionLog entry."""
        try:
            self.repo.create_log({
                "job_id": job_id,
                "workspace_id": workspace_id,
                "step_name": step_name,
                "message": message,
                "log_level": log_level,
                "duration_ms": duration_ms,
            })
        except Exception as exc:
            logger.warning(
                "Failed to persist conversion log: %s",
                exc,
                extra={"job_id": job_id, "step_name": step_name},
            )

    # ── Dialect validation ────────────────────────────────────────────

    @staticmethod
    def _validate_dialects(source_dialect: str, target_dialect: str) -> None:
        if source_dialect not in ALLOWED_SOURCE_DIALECTS:
            raise ValueError(
                f"Invalid source_dialect '{source_dialect}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_SOURCE_DIALECTS))}"
            )
        if target_dialect not in ALLOWED_TARGET_DIALECTS:
            raise ValueError(
                f"Invalid target_dialect '{target_dialect}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_TARGET_DIALECTS))}"
            )

    # ── Standalone conversion ─────────────────────────────────────────

    def create_standalone_conversion(
        self,
        request: StandaloneConversionRequest,
        workspace_id: int,
        user_id: str,
    ) -> ConversionJob:
        """Execute a standalone (single-snippet) conversion."""
        self._validate_dialects(request.source_dialect, request.target_dialect)

        if request.additional_context and len(request.additional_context) > 50_000:
            raise ValueError(
                "additional_context exceeds maximum length of 50,000 characters"
            )

        job = self.repo.create_job(
            workspace_id=workspace_id,
            source_code=request.source_code,
            source_dialect=request.source_dialect,
            target_dialect=request.target_dialect,
            asset_type=request.asset_type.value if hasattr(request.asset_type, 'value') else request.asset_type,
            asset_name=request.asset_name,
            bedrock_model=request.bedrock_model,
            aws_region=request.aws_region,
            prompt_template_path=request.prompt_template_path,
            use_sqlglot=request.use_sqlglot,
            status="pending",
            retry_count=0,
            created_by=user_id,
        )

        logger.info(
            "Standalone conversion started",
            extra={"job_id": job.id, "workspace_id": workspace_id},
        )

        # Optional sqlglot pre-processing
        sqlglot_output = None
        sqlglot_success = None

        if request.use_sqlglot:
            sg_start = time.time()
            self._create_log(
                job.id, workspace_id,
                ConversionLogStepName.SQLGLOT_PARSE_STARTED.value,
                "SqlGlot parsing started",
            )
            sg_result = self.sqlglot_parser.parse_and_transpile(
                request.source_code,
                request.source_dialect,
                request.target_dialect,
            )
            sg_duration = int((time.time() - sg_start) * 1000)
            sqlglot_success = sg_result.success
            if sg_result.success:
                sqlglot_output = sg_result.transpiled_code
                self._create_log(
                    job.id, workspace_id,
                    ConversionLogStepName.SQLGLOT_PARSE_COMPLETED.value,
                    "SqlGlot parsing completed successfully",
                    duration_ms=sg_duration,
                )
            else:
                logger.warning(
                    "sqlglot parse failed, proceeding with raw source",
                    extra={"job_id": job.id, "warning": sg_result.warning},
                )
                self._create_log(
                    job.id, workspace_id,
                    ConversionLogStepName.SQLGLOT_PARSE_FAILED.value,
                    f"SqlGlot parsing failed: {sg_result.warning}",
                    log_level="WARNING",
                    duration_ms=sg_duration,
                )
            self.repo.update_job(
                job.id, workspace_id,
                sqlglot_success=sqlglot_success,
            )

        # Bedrock invocation with retry logic
        max_retries = request.max_retries
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                self.repo.update_job(
                    job.id, workspace_id,
                    status="in_progress",
                    retry_count=attempt,
                )

                if attempt > 0:
                    self._create_log(
                        job.id, workspace_id,
                        ConversionLogStepName.RETRY_ATTEMPTED.value,
                        f"Retry attempt {attempt} of {max_retries}",
                        log_level="WARNING",
                    )

                tmpl_start = time.time()
                template = self.bedrock_client.fetch_prompt_template(
                    request.prompt_template_path,
                    request.aws_region,
                )
                tmpl_duration = int((time.time() - tmpl_start) * 1000)
                self._create_log(
                    job.id, workspace_id,
                    ConversionLogStepName.TEMPLATE_LOADED.value,
                    f"Prompt template loaded from {request.prompt_template_path}",
                    duration_ms=tmpl_duration,
                )

                prompt = BedrockClient.render_prompt(
                    template=template,
                    source_code=request.source_code,
                    source_dialect=request.source_dialect,
                    target_dialect=request.target_dialect,
                    asset_type=request.asset_type.value if hasattr(request.asset_type, 'value') else request.asset_type,
                    sqlglot_output=sqlglot_output,
                    additional_context=request.additional_context,
                )

                bedrock_start = time.time()
                self._create_log(
                    job.id, workspace_id,
                    ConversionLogStepName.BEDROCK_INVOCATION_STARTED.value,
                    f"Bedrock invocation started with model {request.bedrock_model}",
                )
                target_code = self.bedrock_client.invoke_model(
                    prompt=prompt,
                    model_id=request.bedrock_model,
                    region=request.aws_region,
                )
                bedrock_duration = int((time.time() - bedrock_start) * 1000)
                self._create_log(
                    job.id, workspace_id,
                    ConversionLogStepName.BEDROCK_INVOCATION_COMPLETED.value,
                    "Bedrock invocation completed successfully",
                    duration_ms=bedrock_duration,
                )

                target_code = unescape_code_output(target_code)
                job = self.repo.update_job(
                    job.id, workspace_id,
                    target_code=target_code,
                    status="completed",
                    retry_count=attempt,
                )

                self._create_log(
                    job.id, workspace_id,
                    ConversionLogStepName.CONVERSION_COMPLETED.value,
                    "Conversion completed successfully",
                )

                logger.info(
                    "Standalone conversion completed",
                    extra={"job_id": job.id, "workspace_id": workspace_id, "attempts": attempt + 1},
                )
                self.audit_logger.log_data_modification(
                    user_id=int(user_id) if user_id.isdigit() else 0,
                    username=user_id,
                    workspace_id=workspace_id,
                    resource_type="conversion_job",
                    resource_id=job.id,
                    action="create",
                )
                return job

            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Conversion attempt failed: %s",
                    last_error,
                    extra={
                        "job_id": job.id,
                        "workspace_id": workspace_id,
                        "attempt": attempt + 1,
                        "max_retries": max_retries,
                        "error": last_error,
                    },
                )
                self._create_log(
                    job.id, workspace_id,
                    ConversionLogStepName.BEDROCK_INVOCATION_FAILED.value,
                    f"Attempt {attempt + 1} failed: {last_error}",
                    log_level="ERROR",
                )

                if attempt < max_retries:
                    delay = self._backoff_delay(attempt)
                    time.sleep(delay)
                    continue

        # All retries exhausted
        job = self.repo.update_job(
            job.id, workspace_id,
            status="failed",
            error_message=last_error,
            retry_count=max_retries,
        )

        self._create_log(
            job.id, workspace_id,
            ConversionLogStepName.CONVERSION_FAILED.value,
            f"Conversion failed after {max_retries + 1} attempts: {last_error}",
            log_level="ERROR",
        )

        logger.error(
            "Standalone conversion failed after all retries",
            extra={"job_id": job.id, "workspace_id": workspace_id, "retries": max_retries},
        )
        return job

    # ── Batch conversion ──────────────────────────────────────────────

    def create_batch_conversion(
        self,
        request: BatchConversionRequest,
        workspace_id: int,
        user_id: str,
    ) -> ConversionBatch:
        """Create a batch conversion with individual jobs for each asset."""
        asset_type_val = lambda at: at.value if hasattr(at, 'value') else at

        batch = self.repo.create_batch(
            workspace_id=workspace_id,
            batch_name=request.batch_name,
            migration_project_id=request.migration_project_id,
            source_connection_id=request.source_connection_id,
            target_connection_id=request.target_connection_id,
            bedrock_model=request.bedrock_model,
            aws_region=request.aws_region,
            prompt_template_path=request.prompt_template_path,
            use_sqlglot=request.use_sqlglot,
            max_retries=request.max_retries,
            status="pending",
            total_assets=len(request.assets),
            completed_assets=0,
            failed_assets=0,
            created_by=user_id,
        )

        for asset in request.assets:
            self.repo.create_job(
                workspace_id=workspace_id,
                batch_id=batch.id,
                source_code=asset.source_code,
                source_dialect=request.source_dialect,
                target_dialect=request.target_dialect,
                asset_type=asset_type_val(asset.asset_type),
                asset_name=asset.asset_name,
                bedrock_model=request.bedrock_model,
                aws_region=request.aws_region,
                prompt_template_path=request.prompt_template_path,
                use_sqlglot=request.use_sqlglot,
                status="pending",
                retry_count=0,
                created_by=user_id,
            )

        logger.info(
            "Batch conversion created",
            extra={
                "batch_id": batch.id,
                "workspace_id": workspace_id,
                "total_assets": len(request.assets),
            },
        )
        self.audit_logger.log_data_modification(
            user_id=int(user_id) if user_id.isdigit() else 0,
            username=user_id,
            workspace_id=workspace_id,
            resource_type="conversion_batch",
            resource_id=batch.id,
            action="create",
        )
        return batch

    def run_batch_background(self, batch_id: int, workspace_id: int) -> None:
        """Process all jobs in a batch sequentially."""
        batch = self.repo.get_batch(batch_id, workspace_id)
        if not batch:
            logger.error(
                "Batch not found for background processing",
                extra={"batch_id": batch_id, "workspace_id": workspace_id},
            )
            return

        self.repo.update_batch(batch_id, workspace_id, status="in_progress")

        jobs = self.repo.list_batch_jobs(batch_id, workspace_id)
        completed_count = 0
        failed_count = 0

        for job in jobs:
            try:
                self._process_single_job(job, batch, workspace_id)
                completed_count += 1
            except Exception:
                failed_count += 1

            self.repo.update_batch(
                batch_id, workspace_id,
                completed_assets=completed_count,
                failed_assets=failed_count,
            )

            self.cache.set_batch_status(batch_id, {
                "status": "in_progress",
                "total_assets": batch.total_assets,
                "completed_assets": completed_count,
                "failed_assets": failed_count,
            })

        if failed_count == 0:
            final_status = "completed"
        elif completed_count > 0:
            final_status = "completed_with_errors"
        else:
            final_status = "failed"

        self.repo.update_batch(batch_id, workspace_id, status=final_status)
        self.cache.invalidate_batch_status(batch_id)

        logger.info(
            "Batch conversion finished",
            extra={
                "batch_id": batch_id,
                "workspace_id": workspace_id,
                "status": final_status,
                "completed": completed_count,
                "failed": failed_count,
            },
        )

    def _process_single_job(
        self,
        job: ConversionJob,
        batch: ConversionBatch,
        workspace_id: int,
    ) -> None:
        """Process a single job within a batch with retry logic."""
        self._validate_dialects(job.source_dialect, job.target_dialect)

        max_retries = batch.max_retries
        sqlglot_output = None
        sqlglot_success = None

        if batch.use_sqlglot:
            sg_start = time.time()
            self._create_log(
                job.id, workspace_id,
                ConversionLogStepName.SQLGLOT_PARSE_STARTED.value,
                "SqlGlot parsing started",
            )
            sg_result = self.sqlglot_parser.parse_and_transpile(
                job.source_code,
                job.source_dialect,
                job.target_dialect,
            )
            sg_duration = int((time.time() - sg_start) * 1000)
            sqlglot_success = sg_result.success
            if sg_result.success:
                sqlglot_output = sg_result.transpiled_code
                self._create_log(
                    job.id, workspace_id,
                    ConversionLogStepName.SQLGLOT_PARSE_COMPLETED.value,
                    "SqlGlot parsing completed successfully",
                    duration_ms=sg_duration,
                )
            else:
                self._create_log(
                    job.id, workspace_id,
                    ConversionLogStepName.SQLGLOT_PARSE_FAILED.value,
                    f"SqlGlot parsing failed: {sg_result.warning}",
                    log_level="WARNING",
                    duration_ms=sg_duration,
                )
            self.repo.update_job(
                job.id, workspace_id,
                sqlglot_success=sqlglot_success,
            )

        last_error = None

        for attempt in range(max_retries + 1):
            try:
                self.repo.update_job(
                    job.id, workspace_id,
                    status="in_progress",
                    retry_count=attempt,
                )

                if attempt > 0:
                    self._create_log(
                        job.id, workspace_id,
                        ConversionLogStepName.RETRY_ATTEMPTED.value,
                        f"Retry attempt {attempt} of {max_retries}",
                        log_level="WARNING",
                    )

                tmpl_start = time.time()
                template = self.bedrock_client.fetch_prompt_template(
                    job.prompt_template_path,
                    job.aws_region,
                )
                tmpl_duration = int((time.time() - tmpl_start) * 1000)
                self._create_log(
                    job.id, workspace_id,
                    ConversionLogStepName.TEMPLATE_LOADED.value,
                    f"Prompt template loaded from {job.prompt_template_path}",
                    duration_ms=tmpl_duration,
                )

                prompt = BedrockClient.render_prompt(
                    template=template,
                    source_code=job.source_code,
                    source_dialect=job.source_dialect,
                    target_dialect=job.target_dialect,
                    asset_type=job.asset_type,
                    sqlglot_output=sqlglot_output,
                    asset_name=job.asset_name,
                )

                bedrock_start = time.time()
                self._create_log(
                    job.id, workspace_id,
                    ConversionLogStepName.BEDROCK_INVOCATION_STARTED.value,
                    f"Bedrock invocation started with model {job.bedrock_model}",
                )
                target_code = self.bedrock_client.invoke_model(
                    prompt=prompt,
                    model_id=job.bedrock_model,
                    region=job.aws_region,
                )
                bedrock_duration = int((time.time() - bedrock_start) * 1000)
                self._create_log(
                    job.id, workspace_id,
                    ConversionLogStepName.BEDROCK_INVOCATION_COMPLETED.value,
                    "Bedrock invocation completed successfully",
                    duration_ms=bedrock_duration,
                )

                target_code = unescape_code_output(target_code)

                self.repo.update_job(
                    job.id, workspace_id,
                    target_code=target_code,
                    status="completed",
                    retry_count=attempt,
                )

                self._create_log(
                    job.id, workspace_id,
                    ConversionLogStepName.CONVERSION_COMPLETED.value,
                    "Conversion completed successfully",
                )
                return

            except Exception as exc:
                last_error = str(exc)
                self._create_log(
                    job.id, workspace_id,
                    ConversionLogStepName.BEDROCK_INVOCATION_FAILED.value,
                    f"Attempt {attempt + 1} failed: {last_error}",
                    log_level="ERROR",
                )
                if attempt < max_retries:
                    delay = self._backoff_delay(attempt)
                    time.sleep(delay)
                    continue

        # All retries exhausted
        self.repo.update_job(
            job.id, workspace_id,
            status="failed",
            error_message=last_error,
            retry_count=max_retries,
        )
        self._create_log(
            job.id, workspace_id,
            ConversionLogStepName.CONVERSION_FAILED.value,
            f"Conversion failed after {max_retries + 1} attempts: {last_error}",
            log_level="ERROR",
        )
        raise RuntimeError(f"Job {job.id} failed: {last_error}")

    # ── Query, delete, and listing methods ────────────────────────────

    def get_job(self, job_id: int, workspace_id: int) -> Optional[ConversionJob]:
        """Get a single conversion job by ID, scoped to workspace."""
        return self.repo.get_job(job_id, workspace_id)

    def list_jobs(
        self,
        workspace_id: int,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        asset_type: Optional[str] = None,
        source_dialect: Optional[str] = None,
        standalone_only: bool = False,
    ) -> dict:
        """List conversion jobs with pagination and filtering."""
        jobs, total = self.repo.list_jobs(
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
            status=status,
            asset_type=asset_type,
            source_dialect=source_dialect,
            standalone_only=standalone_only,
        )
        return {
            "jobs": jobs,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def delete_job(self, job_id: int, workspace_id: int, user_id: str = "") -> bool:
        """Delete a conversion job scoped to workspace."""
        result = self.repo.delete_job(job_id, workspace_id)
        if result:
            logger.info(
                "Conversion job deleted",
                extra={"job_id": job_id, "workspace_id": workspace_id},
            )
            self.audit_logger.log_data_modification(
                user_id=int(user_id) if user_id.isdigit() else 0,
                username=user_id,
                workspace_id=workspace_id,
                resource_type="conversion_job",
                resource_id=job_id,
                action="delete",
            )
        return result

    def get_batch(self, batch_id: int, workspace_id: int) -> Optional[ConversionBatch]:
        """Get a conversion batch by ID, scoped to workspace."""
        return self.repo.get_batch(batch_id, workspace_id)

    def list_batch_jobs(self, batch_id: int, workspace_id: int) -> list[ConversionJob]:
        """List all jobs belonging to a batch."""
        return self.repo.list_batch_jobs(batch_id, workspace_id)

    def list_bedrock_models(self, region: str) -> list[BedrockModel]:
        """List available Bedrock foundation models for a region."""
        return self.bedrock_client.list_models(region)

    def get_job_logs(
        self, job_id: int, workspace_id: int,
    ) -> List[ConversionLog]:
        """Retrieve conversion logs for a job, scoped to workspace."""
        return self.repo.list_logs_by_job(job_id, workspace_id)

    def list_batches(
        self, workspace_id: int, page: int = 1, page_size: int = 20,
    ) -> dict:
        """List conversion batches with pagination, scoped to workspace."""
        return self.repo.list_batches(workspace_id, page, page_size)

    def delete_batch(self, batch_id: int, workspace_id: int) -> bool:
        """Delete a batch and its associated jobs (CASCADE), scoped to workspace."""
        return self.repo.delete_batch(batch_id, workspace_id)

    def bulk_delete_jobs(self, job_ids: List[int], workspace_id: int) -> int:
        """Delete multiple conversion jobs by ID, scoped to workspace."""
        return self.repo.bulk_delete_jobs(job_ids, workspace_id)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _backoff_delay(attempt: int, base_delay: float = 1.0) -> float:
        """Calculate exponential backoff delay with jitter."""
        delay = base_delay * (2 ** attempt)
        jitter = random.uniform(0, delay * 0.5)
        return delay + jitter
