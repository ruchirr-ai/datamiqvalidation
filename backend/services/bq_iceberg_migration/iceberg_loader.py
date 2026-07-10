"""
Parallel Iceberg Loader for BigQuery to Iceberg Migrations

Creates Iceberg tables and loads Parquet data files using a configurable
worker pool with asyncio semaphore-based concurrency control.

Key Features:
- Configurable parallelism (1-16 concurrent workers)
- Independent error handling per worker (failure isolation)
- Deduplication check before append (zero duplicate rows)
- Retry with exponential backoff (5s, 15s, 45s) for S3 access errors
- Progress tracking per table with callback support
- Glue database auto-creation if not exists

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.8, 12.1, 12.2, 12.4
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from services.bq_iceberg_migration.error_codes import (
    ErrorCode,
    MigrationLogger,
    is_retryable,
    get_retry_delays,
)

logger = logging.getLogger(__name__)


# --- Result Data Classes ---

@dataclass
class TableLoadResult:
    """Result of loading a single table.

    Attributes:
        table_name: Name of the table that was loaded.
        success: Whether the load completed successfully.
        error_code: Error code if the load failed.
        error_message: Human-readable error description if failed.
        files_appended: Number of data files registered.
        duration_seconds: Time taken to load the table.
        retries: Number of retry attempts made.
    """

    table_name: str
    success: bool
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    files_appended: int = 0
    duration_seconds: float = 0.0
    retries: int = 0


@dataclass
class LoadResult:
    """Aggregated result of loading all tables in a migration.

    Attributes:
        total_tables: Total number of tables attempted.
        successful_tables: Number of tables loaded successfully.
        failed_tables: Number of tables that failed.
        table_results: Individual results per table.
        duration_seconds: Total time for the load stage.
    """

    total_tables: int = 0
    successful_tables: int = 0
    failed_tables: int = 0
    table_results: List[TableLoadResult] = field(default_factory=list)
    duration_seconds: float = 0.0

    @property
    def all_succeeded(self) -> bool:
        """Check if all tables loaded successfully."""
        return self.failed_tables == 0 and self.total_tables > 0

    @property
    def progress_percentage(self) -> int:
        """Calculate current progress as a percentage."""
        if self.total_tables == 0:
            return 0
        completed = self.successful_tables + self.failed_tables
        return int((completed / self.total_tables) * 100)


# --- Iceberg Table Properties ---

# Required table properties per design document (Requirement 2.6)
DEFAULT_TABLE_PROPERTIES: Dict[str, str] = {
    "table_type": "ICEBERG",
    "write.format.default": "parquet",
    "write.parquet.compression-codec": "zstd",
    "format-version": "2",
    "write.metadata.delete-after-commit.enabled": "true",
    "write.metadata.previous-versions-max": "3",
}


# --- Parallel Iceberg Loader ---

class ParallelIcebergLoader:
    """Creates Iceberg tables and loads Parquet data files using parallel workers.

    Uses asyncio semaphore-based concurrency to limit the number of tables
    being loaded simultaneously. Each worker operates independently with its
    own error handling, ensuring that a failure in one table does not affect
    the loading of other tables.

    Args:
        catalog: PyIceberg GlueCatalog instance for table operations.
        credential_provider: AWSCredentialProvider for AWS access.
        type_mapper: BQToIcebergTypeMapper for schema conversion.
        partition_mapper: PartitionSpecMapper for partition spec creation.
        dedup_guard: DeduplicationGuard for preventing duplicate data.
        parallelism: Number of concurrent workers (1-16, default 4).
        migration_logger: Optional MigrationLogger for structured logging.
    """

    DEFAULT_PARALLELISM = 4
    MAX_PARALLELISM = 16
    MIN_PARALLELISM = 1

    # S3 Tables throttling retry configuration (Requirement 6.3, 6.4, 6.5, 6.6)
    S3_TABLES_THROTTLE_MAX_RETRIES = 5
    S3_TABLES_THROTTLE_BASE_DELAY = 1.0  # seconds
    S3_TABLES_THROTTLE_MAX_DELAY = 32.0  # seconds

    def __init__(
        self,
        catalog: Any,
        credential_provider: Any,
        type_mapper: Any,
        partition_mapper: Any,
        dedup_guard: Any,
        parallelism: int = 4,
        migration_logger: Optional[MigrationLogger] = None,
    ) -> None:
        self._catalog = catalog
        self._cred_provider = credential_provider
        self._type_mapper = type_mapper
        self._partition_mapper = partition_mapper
        self._dedup_guard = dedup_guard
        self._parallelism = min(
            max(parallelism, self.MIN_PARALLELISM), self.MAX_PARALLELISM
        )
        self._migration_logger = migration_logger

    @property
    def parallelism(self) -> int:
        """Get the configured parallelism level."""
        return self._parallelism

    async def load_tables(
        self,
        migration: Any,
        structure_plan: Dict[str, Any],
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
    ) -> LoadResult:
        """Load all tables in parallel using asyncio worker pool.

        Creates an asyncio semaphore to limit concurrency and dispatches
        one task per table. Results are gathered and aggregated.

        Args:
            migration: The MigrationBQIceberg model instance.
            structure_plan: Approved structure plan from checkpoint_data.
                Must contain a 'tables' key with list of table plans.
            progress_callback: Optional callback(completed, total, percentage)
                called after each table completes.

        Returns:
            LoadResult with aggregated outcomes for all tables.
        """
        start_time = time.time()
        tables = structure_plan.get("tables", [])
        total_tables = len(tables)

        if total_tables == 0:
            logger.warning("No tables found in structure plan, nothing to load")
            return LoadResult(total_tables=0)

        logger.info(
            "Starting parallel Iceberg load: %d tables with %d workers",
            total_tables,
            self._parallelism,
        )

        if self._migration_logger:
            self._migration_logger.log_stage_transition("transfer", "load")

        semaphore = asyncio.Semaphore(self._parallelism)
        completed_count = 0
        lock = asyncio.Lock()

        async def _wrapped_load(table_plan: Dict[str, Any]) -> TableLoadResult:
            nonlocal completed_count
            result = await self._load_single_table(
                semaphore, migration, table_plan
            )
            async with lock:
                completed_count += 1
                percentage = int((completed_count / total_tables) * 100)
                if progress_callback:
                    try:
                        progress_callback(completed_count, total_tables, percentage)
                    except Exception as cb_err:
                        logger.warning(
                            "Progress callback error: %s", cb_err
                        )
                if self._migration_logger:
                    self._migration_logger.log_progress(
                        completed_count, total_tables, percentage
                    )
            return result

        tasks = [
            asyncio.create_task(_wrapped_load(table_plan))
            for table_plan in tables
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results, handling any unexpected exceptions
        table_results: List[TableLoadResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                table_name = tables[i].get("proposed_name", f"table_{i}")
                table_results.append(
                    TableLoadResult(
                        table_name=table_name,
                        success=False,
                        error_code=ErrorCode.ICEBERG_TABLE_CREATE_FAILED.value,
                        error_message=str(result),
                    )
                )
            else:
                table_results.append(result)

        load_result = self._aggregate_results(table_results)
        load_result.duration_seconds = time.time() - start_time

        logger.info(
            "Parallel Iceberg load complete: %d/%d tables succeeded in %.2fs",
            load_result.successful_tables,
            load_result.total_tables,
            load_result.duration_seconds,
        )

        return load_result

    async def _load_single_table(
        self,
        semaphore: asyncio.Semaphore,
        migration: Any,
        table_plan: Dict[str, Any],
    ) -> TableLoadResult:
        """Load a single table with independent error handling.

        Acquires the semaphore before processing. Each step is wrapped in
        error handling so that failures are isolated to this table only.

        Steps:
        1. Check deduplication before append
        2. Create table (or verify existing)
        3. Append data files
        4. Update shard status

        Args:
            semaphore: Asyncio semaphore for concurrency control.
            migration: The migration model instance.
            table_plan: The approved structure plan for this table.

        Returns:
            TableLoadResult indicating success or failure.
        """
        table_name = table_plan.get("proposed_name", "unknown")
        start_time = time.time()
        retries = 0

        async with semaphore:
            try:
                logger.info("Loading table: %s", table_name)

                # Extract table configuration from the plan
                # Use migration's glue_database_name (user's selection) over plan's stored value
                migration_db = getattr(migration, "glue_database_name", None)
                database = migration_db or table_plan.get("database", "default")
                schema = table_plan.get("schema")
                partition_spec = table_plan.get("partition_spec")
                sort_order = table_plan.get("sort_order")
                properties = table_plan.get("table_properties", {})
                s3_file_uris = table_plan.get("data_files", [])

                # Log table creation start
                column_count = len(table_plan.get("columns", []))
                partition_desc = None
                if partition_spec:
                    partition_desc = (
                        f"{partition_spec.get('transform', 'none')}"
                        f"({partition_spec.get('column', '')})"
                    )

                if self._migration_logger:
                    self._migration_logger.log_table_creation_start(
                        table_name, column_count, partition_desc
                    )
                    self._migration_logger.log_schema_mapping(
                        table_name, column_count, partition_desc,
                        sort_order=str(table_plan.get("sort_order_columns")) if table_plan.get("sort_order_columns") else None
                    )

                # Step 1: Ensure database exists
                await asyncio.to_thread(self.ensure_database_exists, database)

                # Step 2: Create or verify table (with retry for S3 errors)
                table = await self._create_or_verify_table_with_retry(
                    database=database,
                    table_name=table_name,
                    table_plan=table_plan,
                    properties=properties,
                )
                retries = table.get("retries", 0) if isinstance(table, dict) else 0
                iceberg_table = table.get("table") if isinstance(table, dict) else table

                # Step 3: Deduplication check
                if s3_file_uris and iceberg_table is not None:
                    safe, new_files = await asyncio.to_thread(
                        self._dedup_guard.is_safe_to_append,
                        iceberg_table,
                        s3_file_uris,
                    )

                    if safe and new_files:
                        # Log data file registration
                        if self._migration_logger:
                            self._migration_logger.log_data_file_registration(
                                table_name, len(new_files)
                            )

                        # Step 4: Append data files (with retry for S3 errors)
                        await self._append_with_retry(
                            iceberg_table, new_files, table_name
                        )
                    elif not safe:
                        logger.info(
                            "Table '%s': all files already registered, skipping append",
                            table_name,
                        )

                duration = time.time() - start_time

                # Log completion
                if self._migration_logger:
                    self._migration_logger.log_table_creation_complete(
                        table_name, duration
                    )

                return TableLoadResult(
                    table_name=table_name,
                    success=True,
                    files_appended=len(s3_file_uris),
                    duration_seconds=duration,
                    retries=retries,
                )

            except _RetryExhaustedError as e:
                duration = time.time() - start_time
                error_code = e.error_code

                if self._migration_logger:
                    self._migration_logger.log_error(
                        error_code=error_code,
                        operation="load_single_table",
                        message=str(e),
                        table_name=table_name,
                        context={"retries": e.retries},
                    )

                return TableLoadResult(
                    table_name=table_name,
                    success=False,
                    error_code=error_code.value,
                    error_message=str(e),
                    duration_seconds=duration,
                    retries=e.retries,
                )

            except Exception as e:
                duration = time.time() - start_time
                error_code = self._classify_error(e)

                logger.error(
                    "Failed to load table '%s': %s (error_code=%s)",
                    table_name,
                    e,
                    error_code.value,
                )

                if self._migration_logger:
                    self._migration_logger.log_error(
                        error_code=error_code,
                        operation="load_single_table",
                        message=str(e),
                        table_name=table_name,
                    )

                return TableLoadResult(
                    table_name=table_name,
                    success=False,
                    error_code=error_code.value,
                    error_message=str(e),
                    duration_seconds=duration,
                )

    async def _create_or_verify_table_with_retry(
        self,
        database: str,
        table_name: str,
        table_plan: Dict[str, Any],
        properties: Dict[str, str],
    ) -> Dict[str, Any]:
        """Create or verify an Iceberg table with retry for S3 access errors.

        If the table already exists, verifies schema compatibility.
        Retries up to 3 times with exponential backoff for S3 errors.

        Args:
            database: Glue database name.
            table_name: Name of the table to create.
            table_plan: The approved structure plan for this table.
            properties: Table properties to set.

        Returns:
            Dict with 'table' (the Iceberg table object) and 'retries' count.

        Raises:
            _RetryExhaustedError: If all retries are exhausted.
        """
        delays = get_retry_delays(ErrorCode.ICEBERG_S3_ACCESS_ERROR)
        retries = 0

        for attempt in range(len(delays) + 1):
            try:
                # Check if table already exists (Requirement 5.4)
                existing_table = await asyncio.to_thread(
                    self._try_load_table, database, table_name
                )

                if existing_table is not None:
                    logger.info(
                        "Table '%s.%s' already exists, verifying compatibility",
                        database,
                        table_name,
                    )
                    return {"table": existing_table, "retries": retries}

                # Create new table
                schema = table_plan.get("schema")
                partition_spec = table_plan.get("partition_spec")
                sort_order = table_plan.get("sort_order")

                # If schema is None or not a PyIceberg Schema object,
                # build it from the columns list in the table_plan.
                # The columns may use different field names depending on source
                # (structure report uses bq_type; assessment uses data_type/type).
                if schema is None or not hasattr(schema, 'fields'):
                    columns = table_plan.get("columns", [])
                    if columns:
                        try:
                            # Normalize column dicts to the format map_schema expects
                            normalized = []
                            for col in columns:
                                normalized.append({
                                    "name": col.get("name", "unknown"),
                                    "type": col.get("type") or col.get("data_type") or col.get("bq_type", "STRING"),
                                    "mode": col.get("mode", "NULLABLE" if col.get("nullable", True) else "REQUIRED"),
                                    "fields": col.get("fields"),
                                })

                            # Build real PyIceberg Schema directly (not the custom dataclass)
                            from pyiceberg.schema import Schema as PySchema
                            from pyiceberg.types import (
                                NestedField as PyField, StringType as PyST,
                                LongType as PyLT, DoubleType as PyDT,
                                BooleanType as PyBT, DateType as PyDate,
                                TimestampType as PyTS, TimestamptzType as PyTSTZ,
                            )
                            BQ_TO_PY = {
                                "STRING": PyST(), "BYTES": PyST(),
                                "INT64": PyLT(), "INTEGER": PyLT(),
                                "FLOAT64": PyDT(), "FLOAT": PyDT(),
                                "BOOLEAN": PyBT(), "BOOL": PyBT(),
                                "DATE": PyDate(),
                                "DATETIME": PyTS(), "TIMESTAMP": PyTSTZ(),
                                "TIME": PyST(), "JSON": PyST(),
                                "GEOGRAPHY": PyST(), "NUMERIC": PyDT(),
                                "BIGNUMERIC": PyDT(),
                            }
                            py_fields = []
                            for i, col in enumerate(normalized, start=1):
                                bq_t = col["type"].upper()
                                py_type = BQ_TO_PY.get(bq_t, PyST())
                                required = col["mode"].upper() == "REQUIRED"
                                py_fields.append(PyField(i, col["name"], py_type, required=required))
                            schema = PySchema(*py_fields)
                            logger.info(
                                "Built PyIceberg schema for table '%s': %d fields",
                                table_name, len(py_fields),
                            )
                        except Exception as schema_err:
                            logger.warning(
                                "Could not build schema from columns for table '%s': %s. "
                                "Using minimal schema.",
                                table_name, schema_err,
                            )
                            from pyiceberg.schema import Schema as _Schema
                            from pyiceberg.types import NestedField as _NF, StringType as _ST
                            schema = _Schema(_NF(1, "id", _ST(), required=False))
                    else:
                        from pyiceberg.schema import Schema as _Schema
                        from pyiceberg.types import NestedField as _NF, StringType as _ST
                        schema = _Schema(_NF(1, "id", _ST(), required=False))

                # Ensure partition_spec and sort_order are None if not real PyIceberg objects
                if partition_spec is not None and not hasattr(partition_spec, 'fields'):
                    partition_spec = None  # unpartitioned
                if sort_order is not None and not hasattr(sort_order, 'fields'):
                    sort_order = None  # unsorted

                table = await asyncio.to_thread(
                    self.create_table,
                    database,
                    table_name,
                    schema,
                    partition_spec,
                    sort_order,
                    properties,
                )
                return {"table": table, "retries": retries}

            except Exception as e:
                if self._is_s3_access_error(e) and attempt < len(delays):
                    delay = delays[attempt]
                    retries += 1
                    logger.warning(
                        "S3 access error creating table '%s' (attempt %d/%d), "
                        "retrying in %ds: %s",
                        table_name,
                        attempt + 1,
                        len(delays) + 1,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)
                elif self._is_s3_access_error(e):
                    raise _RetryExhaustedError(
                        f"S3 access error creating table '{table_name}' "
                        f"after {retries} retries: {e}",
                        error_code=ErrorCode.ICEBERG_S3_ACCESS_ERROR,
                        retries=retries,
                    ) from e
                else:
                    raise

        # Should not reach here, but just in case
        raise _RetryExhaustedError(
            f"Failed to create table '{table_name}' after {retries} retries",
            error_code=ErrorCode.ICEBERG_TABLE_CREATE_FAILED,
            retries=retries,
        )

    async def _append_with_retry(
        self, table: Any, file_uris: List[str], table_name: str
    ) -> None:
        """Append data files with retry for S3 access errors.

        Args:
            table: The Iceberg table object.
            file_uris: List of S3 file URIs to append.
            table_name: Name of the table (for logging).

        Raises:
            _RetryExhaustedError: If all retries are exhausted.
        """
        delays = get_retry_delays(ErrorCode.ICEBERG_S3_ACCESS_ERROR)
        retries = 0

        for attempt in range(len(delays) + 1):
            try:
                await asyncio.to_thread(
                    self.append_data_files, table, file_uris
                )
                return
            except Exception as e:
                if self._is_s3_access_error(e) and attempt < len(delays):
                    delay = delays[attempt]
                    retries += 1
                    logger.warning(
                        "S3 access error appending to table '%s' (attempt %d/%d), "
                        "retrying in %ds: %s",
                        table_name,
                        attempt + 1,
                        len(delays) + 1,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)
                elif self._is_s3_access_error(e):
                    raise _RetryExhaustedError(
                        f"S3 access error appending to table '{table_name}' "
                        f"after {retries} retries: {e}",
                        error_code=ErrorCode.ICEBERG_S3_ACCESS_ERROR,
                        retries=retries,
                    ) from e
                else:
                    raise

    async def _retry_with_throttle_backoff(
        self,
        operation: Callable,
        table_name: str,
        operation_name: str,
    ) -> Any:
        """Execute an S3 Tables API operation with throttle-specific retry logic.

        Distinguishes HTTP 429 / SlowDown from other errors. Retries with
        exponential backoff (1s, 2s, 4s, 8s, 16s) up to 5 retries.
        Logs WARNING on each throttle retry with table_name, operation,
        retry count, and backoff delay.

        Args:
            operation: A callable (sync or async) that performs the S3 Tables API call.
            table_name: Name of the table being operated on (for logging).
            operation_name: Human-readable name of the operation (for logging).

        Returns:
            The result of the operation callable on success.

        Raises:
            _RetryExhaustedError: If all 5 retries are exhausted due to throttling.
                Uses error code S3_TABLES_THROTTLED.
            Exception: Re-raises non-throttle errors immediately with no retry.

        Requirements: 6.3, 6.4, 6.5, 6.6
        """
        last_exception: Optional[Exception] = None

        for attempt in range(self.S3_TABLES_THROTTLE_MAX_RETRIES + 1):
            try:
                if asyncio.iscoroutinefunction(operation):
                    return await operation()
                else:
                    return await asyncio.to_thread(operation)
            except Exception as e:
                if self._is_s3_tables_throttle_error(e):
                    last_exception = e

                    if attempt >= self.S3_TABLES_THROTTLE_MAX_RETRIES:
                        # All retries exhausted
                        break

                    # Calculate exponential backoff delay: 1s, 2s, 4s, 8s, 16s
                    delay = min(
                        self.S3_TABLES_THROTTLE_BASE_DELAY * (2 ** attempt),
                        self.S3_TABLES_THROTTLE_MAX_DELAY,
                    )

                    logger.warning(
                        "S3 Tables API throttled for table '%s' during '%s' "
                        "(retry %d/%d, backoff %.1fs): %s",
                        table_name,
                        operation_name,
                        attempt + 1,
                        self.S3_TABLES_THROTTLE_MAX_RETRIES,
                        delay,
                        e,
                    )

                    if self._migration_logger:
                        self._migration_logger.log_warning(
                            operation=operation_name,
                            message=(
                                f"S3 Tables API throttled for table '{table_name}' "
                                f"(retry {attempt + 1}/{self.S3_TABLES_THROTTLE_MAX_RETRIES}, "
                                f"backoff {delay:.1f}s)"
                            ),
                            table_name=table_name,
                            error_code=ErrorCode.S3_TABLES_THROTTLED,
                            context={
                                "retry_count": attempt + 1,
                                "max_retries": self.S3_TABLES_THROTTLE_MAX_RETRIES,
                                "backoff_delay": delay,
                            },
                        )

                    await asyncio.sleep(delay)
                else:
                    # Non-throttle error: classify as S3_TABLES_API_FAILED and re-raise
                    raise

        # All retries exhausted — raise with S3_TABLES_THROTTLED error code
        raise _RetryExhaustedError(
            f"S3 Tables API throttled for table '{table_name}' during '{operation_name}' "
            f"after {self.S3_TABLES_THROTTLE_MAX_RETRIES} retries: {last_exception}",
            error_code=ErrorCode.S3_TABLES_THROTTLED,
            retries=self.S3_TABLES_THROTTLE_MAX_RETRIES,
        )

    async def _load_single_table_s3_tables(
        self,
        table_config: Dict[str, Any],
        s3_tables_adapter: Any,
        maintenance_config: Any,
    ) -> TableLoadResult:
        """Load a single table to S3 Tables with maintenance config and throttle handling.

        After successful table creation via the S3TablesAdapter:
        1. Calls s3_tables_adapter.configure_maintenance() (non-fatal on failure)
        2. Appends data files with throttle-aware retry

        Throttle retry: exponential backoff starting at 1s, doubling each retry,
        max 5 retries, max delay 32s. Uses error code S3_TABLES_THROTTLED.

        Args:
            table_config: Dict with table configuration including:
                - proposed_name: Name of the table to create.
                - namespace: S3 Tables namespace.
                - schema: PyIceberg Schema object.
                - partition_spec: PyIceberg PartitionSpec object.
                - data_files: List of S3 URIs for data files to append.
                - database: Glue database name.
                - columns: List of column definitions.
            s3_tables_adapter: S3TablesAdapter instance for table operations.
            maintenance_config: MaintenanceConfig instance with compaction and
                snapshot management settings. Applied after table creation.

        Returns:
            TableLoadResult indicating success or failure.

        Requirements: 1.1, 1.6
        """
        table_name = table_config.get("proposed_name", "unknown")
        namespace = table_config.get("namespace", "default")
        start_time = time.time()

        try:
            logger.info(
                "Loading table to S3 Tables: %s.%s",
                namespace,
                table_name,
            )

            # Step 1: Ensure namespace exists
            await asyncio.to_thread(
                s3_tables_adapter.ensure_namespace, namespace
            )

            # Step 2: Create table via S3 Tables adapter (with throttle retry)
            schema = table_config.get("schema")
            partition_spec = table_config.get("partition_spec")

            create_result = await self._retry_with_throttle_backoff(
                operation=lambda: s3_tables_adapter.create_table(
                    namespace=namespace,
                    table_name=table_name,
                    schema=schema,
                    partition_spec=partition_spec,
                ),
                table_name=table_name,
                operation_name="create_table",
            )

            # Step 3: Configure maintenance immediately after table creation (non-fatal)
            if maintenance_config is not None:
                try:
                    maintenance_success = await asyncio.to_thread(
                        s3_tables_adapter.configure_maintenance,
                        namespace,
                        table_name,
                        maintenance_config,
                    )
                    if not maintenance_success:
                        logger.warning(
                            "Maintenance configuration failed for table '%s.%s', "
                            "continuing with default S3 Tables maintenance settings",
                            namespace,
                            table_name,
                        )
                except Exception as maint_err:
                    # Maintenance config failure is non-fatal — log and continue
                    logger.warning(
                        "Unexpected error configuring maintenance for table '%s.%s': %s. "
                        "Continuing with default S3 Tables maintenance settings",
                        namespace,
                        table_name,
                        maint_err,
                    )

            # Step 4: Register in Glue catalog (if needed)
            database = table_config.get(
                "database", "default"
            )
            await asyncio.to_thread(self.ensure_database_exists, database)

            # Step 5: Append data files with throttle-aware retry
            s3_file_uris = table_config.get("data_files", [])
            files_appended = 0

            if s3_file_uris:
                # Load table from Glue catalog for append operation
                iceberg_table = await asyncio.to_thread(
                    self._try_load_table, database, table_name
                )

                if iceberg_table is not None:
                    # Deduplication check
                    safe, new_files = await asyncio.to_thread(
                        self._dedup_guard.is_safe_to_append,
                        iceberg_table,
                        s3_file_uris,
                    )

                    if safe and new_files:
                        if self._migration_logger:
                            self._migration_logger.log_data_file_registration(
                                table_name, len(new_files)
                            )

                        await self._retry_with_throttle_backoff(
                            operation=lambda: self.append_data_files(
                                iceberg_table, new_files
                            ),
                            table_name=table_name,
                            operation_name="append_data_files",
                        )
                        files_appended = len(new_files)
                    elif not safe:
                        logger.info(
                            "Table '%s.%s': all files already registered, skipping append",
                            namespace,
                            table_name,
                        )

            duration = time.time() - start_time

            if self._migration_logger:
                self._migration_logger.log_table_creation_complete(
                    table_name, duration
                )

            return TableLoadResult(
                table_name=table_name,
                success=True,
                files_appended=files_appended,
                duration_seconds=duration,
            )

        except _RetryExhaustedError as e:
            duration = time.time() - start_time

            if self._migration_logger:
                self._migration_logger.log_error(
                    error_code=e.error_code,
                    operation="load_single_table_s3_tables",
                    message=str(e),
                    table_name=table_name,
                    context={"retries": e.retries},
                )

            return TableLoadResult(
                table_name=table_name,
                success=False,
                error_code=e.error_code.value,
                error_message=str(e),
                duration_seconds=duration,
                retries=e.retries,
            )

        except Exception as e:
            duration = time.time() - start_time
            error_code = self._classify_error(e)

            logger.error(
                "Failed to load table '%s.%s' to S3 Tables: %s (error_code=%s)",
                namespace,
                table_name,
                e,
                error_code.value,
            )

            if self._migration_logger:
                self._migration_logger.log_error(
                    error_code=error_code,
                    operation="load_single_table_s3_tables",
                    message=str(e),
                    table_name=table_name,
                )

            return TableLoadResult(
                table_name=table_name,
                success=False,
                error_code=error_code.value,
                error_message=str(e),
                duration_seconds=duration,
            )

    @staticmethod
    def _is_s3_tables_throttle_error(error: Exception) -> bool:
        """Determine if an exception is an S3 Tables throttling error.

        Checks for HTTP 429 status code or SlowDown error code, which indicate
        the S3 Tables API is rate-limiting the request.

        Args:
            error: The exception to classify.

        Returns:
            True if this is a throttle error (HTTP 429 or SlowDown), False otherwise.

        Requirements: 6.4
        """
        error_str = str(error)

        # Check for HTTP 429 status code
        if "429" in error_str:
            return True

        # Check for SlowDown error code (case-sensitive AWS error code)
        if "SlowDown" in error_str:
            return True

        # Check botocore ClientError response metadata
        if hasattr(error, "response"):
            response = getattr(error, "response", {})
            if isinstance(response, dict):
                # Check HTTP status code
                status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if status_code == 429:
                    return True
                # Check error code
                error_code = response.get("Error", {}).get("Code", "")
                if error_code == "SlowDown":
                    return True

        return False

    def _compute_file_time_watermark(
        self,
        processed_files: List[Dict[str, Any]],
    ) -> Optional[str]:
        """Compute the maximum file_modification_time across processed files.

        Scans all processed file metadata dicts for the 'file_modification_time'
        key and returns the maximum value formatted as an ISO 8601 UTC timestamp
        with second precision.

        Args:
            processed_files: List of file metadata dicts, each expected to have
                a 'file_modification_time' key with a datetime or ISO string value.

        Returns:
            ISO 8601 UTC timestamp string (e.g., "2024-01-15T10:30:00Z")
            or None if no files were processed or no valid timestamps found.
        """
        if not processed_files:
            return None

        max_time: Optional[datetime] = None

        for file_meta in processed_files:
            mod_time = file_meta.get("file_modification_time")
            if mod_time is None:
                continue

            # Handle both datetime objects and ISO string values
            if isinstance(mod_time, str):
                try:
                    parsed = datetime.fromisoformat(mod_time.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    continue
            elif isinstance(mod_time, datetime):
                parsed = mod_time
            else:
                continue

            # Ensure timezone-aware (assume UTC if naive)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)

            if max_time is None or parsed > max_time:
                max_time = parsed

        if max_time is None:
            return None

        # Format as ISO 8601 UTC with second precision
        return max_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _filter_files_by_watermark(
        self,
        files: List[Dict[str, Any]],
        watermark: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Filter source data files to include only those newer than watermark.

        Returns all files if watermark is None. Otherwise, returns only files
        whose 'file_modification_time' is strictly greater than the watermark.

        Args:
            files: List of file metadata dicts with 'file_modification_time' key.
            watermark: ISO 8601 UTC timestamp string, or None (include all files).

        Returns:
            Filtered list of files with modification_time > watermark.
        """
        if watermark is None:
            return list(files)

        # Parse the watermark timestamp
        try:
            watermark_dt = datetime.fromisoformat(watermark.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            # If watermark is invalid, return all files as a safe fallback
            logger.warning(
                "Invalid watermark format '%s', returning all files", watermark
            )
            return list(files)

        if watermark_dt.tzinfo is None:
            watermark_dt = watermark_dt.replace(tzinfo=timezone.utc)

        filtered: List[Dict[str, Any]] = []
        for file_meta in files:
            mod_time = file_meta.get("file_modification_time")
            if mod_time is None:
                # Include files without a modification time (safe default)
                filtered.append(file_meta)
                continue

            # Parse file modification time
            if isinstance(mod_time, str):
                try:
                    file_dt = datetime.fromisoformat(mod_time.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    # Include files with unparseable timestamps
                    filtered.append(file_meta)
                    continue
            elif isinstance(mod_time, datetime):
                file_dt = mod_time
            else:
                filtered.append(file_meta)
                continue

            if file_dt.tzinfo is None:
                file_dt = file_dt.replace(tzinfo=timezone.utc)

            # Strictly greater than watermark
            if file_dt > watermark_dt:
                filtered.append(file_meta)

        return filtered

    async def load_table_incremental(
        self,
        migration: Any,
        table_name: str,
        source_files: List[Dict[str, Any]],
        checkpoint_data: Dict[str, Any],
    ) -> TableLoadResult:
        """Perform an incremental load for a single table using file-time watermark.

        Reads the existing watermark from checkpoint_data, filters source files
        to only include those newer than the watermark, processes them, and
        updates the watermark only on full success.

        Args:
            migration: The MigrationBQIceberg model instance.
            table_name: Name of the table to load incrementally.
            source_files: List of file metadata dicts with 'file_modification_time'.
            checkpoint_data: The migration's checkpoint_data dict (mutable).

        Returns:
            TableLoadResult indicating success or failure.
        """
        start_time = time.time()

        # Read existing watermark from checkpoint_data
        file_time_watermarks = checkpoint_data.get("file_time_watermarks", {})
        existing_watermark = file_time_watermarks.get(table_name)

        logger.info(
            "Starting incremental load for table '%s' with watermark: %s",
            table_name,
            existing_watermark or "None (first load)",
        )

        # Filter files by watermark
        new_files = self._filter_files_by_watermark(source_files, existing_watermark)

        # No new files — log INFO and mark completed with zero files
        if not new_files:
            duration = time.time() - start_time
            logger.info(
                "No new files to process for table '%s' "
                "(all files at or before watermark %s)",
                table_name,
                existing_watermark,
            )
            return TableLoadResult(
                table_name=table_name,
                success=True,
                files_appended=0,
                duration_seconds=duration,
            )

        logger.info(
            "Found %d new file(s) for table '%s' (filtered from %d total)",
            len(new_files),
            table_name,
            len(source_files),
        )

        # Process files (actual loading logic delegated to existing methods)
        try:
            # Extract file URIs for append
            file_uris = [f.get("uri") or f.get("file_path", "") for f in new_files]
            file_uris = [uri for uri in file_uris if uri]  # Remove empty URIs

            database = getattr(migration, "glue_database_name", "default")

            # Load the table from catalog
            iceberg_table = await asyncio.to_thread(
                self._try_load_table, database, table_name
            )

            if iceberg_table is None:
                raise RuntimeError(
                    f"Table '{database}.{table_name}' not found in catalog "
                    f"for incremental load"
                )

            # Append new files
            if file_uris:
                await self._append_with_retry(iceberg_table, file_uris, table_name)

            # Full success — update watermark
            new_watermark = self._compute_file_time_watermark(new_files)
            if new_watermark is not None:
                # Monotonic update: only write if strictly greater
                if existing_watermark is None or new_watermark > existing_watermark:
                    if "file_time_watermarks" not in checkpoint_data:
                        checkpoint_data["file_time_watermarks"] = {}
                    checkpoint_data["file_time_watermarks"][table_name] = new_watermark
                    logger.info(
                        "Updated watermark for table '%s': %s → %s",
                        table_name,
                        existing_watermark or "None",
                        new_watermark,
                    )

            duration = time.time() - start_time
            return TableLoadResult(
                table_name=table_name,
                success=True,
                files_appended=len(file_uris),
                duration_seconds=duration,
            )

        except Exception as e:
            # Partial failure — do NOT update watermark
            duration = time.time() - start_time
            error_code = self._classify_error(e)

            logger.error(
                "Incremental load failed for table '%s': %s. "
                "Watermark NOT updated (preserving %s for retry).",
                table_name,
                e,
                existing_watermark or "None",
            )

            return TableLoadResult(
                table_name=table_name,
                success=False,
                error_code=error_code.value,
                error_message=str(e),
                duration_seconds=duration,
            )

    def reset_watermark_for_full_reload(
        self,
        table_name: str,
        checkpoint_data: Dict[str, Any],
    ) -> None:
        """Reset the watermark for a table to null, enabling full reload.

        When the user triggers a full reload for a table that has an existing
        watermark, this method resets the watermark to None so the next load
        processes all available files regardless of modification time.

        Args:
            table_name: Name of the table whose watermark should be reset.
            checkpoint_data: The migration's checkpoint_data dict (mutable).

        Validates: Requirement 8.7
        """
        file_time_watermarks = checkpoint_data.get("file_time_watermarks", {})
        previous_watermark = file_time_watermarks.get(table_name)

        if "file_time_watermarks" in checkpoint_data:
            checkpoint_data["file_time_watermarks"][table_name] = None

        logger.info(
            "Reset watermark for table '%s' for full reload: %s → None",
            table_name,
            previous_watermark or "None",
        )

    def create_table(
        self,
        database: str,
        table_name: str,
        schema: Any,
        partition_spec: Any,
        sort_order: Any,
        properties: Optional[Dict[str, str]] = None,
    ) -> Any:
        """Create an Iceberg table in Glue Data Catalog.

        Creates the table with the specified schema, partition spec, sort order,
        and required Iceberg table properties. Merges user-provided properties
        with the default required properties.

        Args:
            database: The Glue database name.
            table_name: The name for the new Iceberg table.
            schema: The Iceberg Schema object for the table.
            partition_spec: The Iceberg PartitionSpec for the table.
            sort_order: The Iceberg SortOrder for the table.
            properties: Additional table properties (merged with defaults).

        Returns:
            The created PyIceberg Table object.

        Raises:
            Exception: If table creation fails (S3 access, Glue permissions, etc.)
        """
        # Merge default properties with user-provided ones
        merged_properties = dict(DEFAULT_TABLE_PROPERTIES)
        if properties:
            merged_properties.update(properties)

        full_table_name = f"{database}.{table_name}"

        logger.info(
            "Creating Iceberg table '%s' with %d properties",
            full_table_name,
            len(merged_properties),
        )

        try:
            from pyiceberg.partitioning import UNPARTITIONED_PARTITION_SPEC
            from pyiceberg.table.sorting import UNSORTED_SORT_ORDER
            table = self._catalog.create_table(
                identifier=full_table_name,
                schema=schema,
                partition_spec=partition_spec if partition_spec is not None else UNPARTITIONED_PARTITION_SPEC,
                sort_order=sort_order if sort_order is not None else UNSORTED_SORT_ORDER,
                properties=merged_properties,
            )
            logger.info("Successfully created Iceberg table '%s'", full_table_name)
            return table
        except Exception as e:
            logger.error(
                "Failed to create Iceberg table '%s': %s",
                full_table_name,
                e,
            )
            raise

    def append_data_files(self, table: Any, s3_file_uris: List[str]) -> None:
        """Register existing Parquet files as data files in the Iceberg table.

        Uses PyIceberg's append operation to register pre-existing Parquet
        files in S3 as data files in the Iceberg table's metadata.

        Args:
            table: The PyIceberg Table object to append to.
            s3_file_uris: List of S3 URIs pointing to Parquet data files.

        Raises:
            Exception: If the append operation fails.
        """
        if not s3_file_uris:
            logger.debug("No files to append, skipping")
            return

        logger.info(
            "Appending %d data file(s) to table",
            len(s3_file_uris),
        )

        try:
            table.append(s3_file_uris)
            logger.info(
                "Successfully appended %d data file(s)",
                len(s3_file_uris),
            )
        except Exception as e:
            logger.error("Failed to append data files: %s", e)
            raise

    def ensure_database_exists(self, database: str) -> None:
        """Use existing Glue database or create it if it doesn't exist.

        First checks whether the database already exists — if so, uses it directly
        without requiring CreateDatabase permissions. Only attempts creation if
        the database is not found.

        Args:
            database: The Glue database name to ensure exists.

        Raises:
            Exception: If database creation fails and the DB doesn't already exist.
        """
        try:
            # Try to load — if it succeeds, DB already exists, we're done
            self._catalog.load_namespace_properties(database)
            logger.info("Using existing Glue database '%s'", database)
            return
        except Exception:
            pass  # DB doesn't exist yet, fall through to create

        # Database doesn't exist, try to create it
        logger.info("Creating Glue database '%s'", database)
        try:
            self._catalog.create_namespace(
                database,
                properties={"description": f"DataMIQ Iceberg migration database: {database}"},
            )
            logger.info("Successfully created Glue database '%s'", database)
        except Exception as e:
            error_str = str(e).lower()
            if "access denied" in error_str or "not authorized" in error_str:
                logger.error(
                    "Permission denied creating database '%s': %s. "
                    "Tip: Create the Glue database manually in AWS Console "
                    "and use 'Select Existing Database' in the structure review.",
                    database, e,
                )
                raise PermissionError(
                    f"Missing IAM permissions to create Glue database '{database}'. "
                    f"Please create it manually in AWS Glue Console first, "
                    f"then select it in the structure review step. Error: {e}"
                ) from e
            if "already exists" in error_str or "alreadyexists" in error_str:
                logger.debug("Database '%s' was created concurrently, continuing", database)
                return
            raise

    def _try_load_table(self, database: str, table_name: str) -> Optional[Any]:
        """Try to load an existing Iceberg table from the catalog.

        Args:
            database: The Glue database name.
            table_name: The table name to look up.

        Returns:
            The Table object if it exists, None otherwise.
        """
        full_name = f"{database}.{table_name}"
        try:
            return self._catalog.load_table(full_name)
        except Exception:
            return None

    def _aggregate_results(self, results: List[TableLoadResult]) -> LoadResult:
        """Aggregate individual table results into a LoadResult.

        Args:
            results: List of per-table load results.

        Returns:
            Aggregated LoadResult.
        """
        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)

        return LoadResult(
            total_tables=len(results),
            successful_tables=successful,
            failed_tables=failed,
            table_results=results,
        )

    @staticmethod
    def _is_s3_access_error(error: Exception) -> bool:
        """Determine if an exception is an S3 access error.

        Checks the error message for common S3 access-related patterns.

        Args:
            error: The exception to classify.

        Returns:
            True if this is an S3 access error, False otherwise.
        """
        error_str = str(error).lower()
        s3_patterns = [
            "s3",
            "access denied",
            "no such bucket",
            "nosuchbucket",
            "forbidden",
            "403",
            "nosuchkey",
            "connection reset",
            "connection timeout",
            "endpoint url",
        ]
        return any(pattern in error_str for pattern in s3_patterns)

    @staticmethod
    def _classify_error(error: Exception) -> ErrorCode:
        """Classify an exception into an appropriate error code.

        Distinguishes S3 Tables throttling errors (HTTP 429, SlowDown) from
        general S3 Tables API errors using distinct error codes.

        Args:
            error: The exception to classify.

        Returns:
            The most appropriate ErrorCode for this error.

        Requirements: 6.4
        """
        error_str = str(error)
        error_str_lower = error_str.lower()

        # Check for S3 Tables throttle errors first (Requirement 6.4)
        if ParallelIcebergLoader._is_s3_tables_throttle_error(error):
            return ErrorCode.S3_TABLES_THROTTLED

        if "permission" in error_str_lower or "access denied" in error_str_lower or "not authorized" in error_str_lower:
            if "glue" in error_str_lower:
                return ErrorCode.GLUE_PERMISSION_DENIED
            return ErrorCode.ICEBERG_S3_ACCESS_ERROR

        if "s3tables" in error_str_lower or "s3 tables" in error_str_lower:
            return ErrorCode.S3_TABLES_API_FAILED

        if "s3" in error_str_lower or "bucket" in error_str_lower:
            return ErrorCode.ICEBERG_S3_ACCESS_ERROR

        if "glue" in error_str_lower or "catalog" in error_str_lower:
            return ErrorCode.GLUE_REGISTRATION_FAILED

        if "schema" in error_str_lower or "evolution" in error_str_lower:
            return ErrorCode.ICEBERG_SCHEMA_EVOLUTION_FAILED

        if "append" in error_str_lower:
            return ErrorCode.ICEBERG_APPEND_FAILED

        return ErrorCode.ICEBERG_TABLE_CREATE_FAILED


# --- Internal Exception ---

class _RetryExhaustedError(Exception):
    """Internal exception raised when all retry attempts are exhausted.

    Attributes:
        error_code: The categorized error code for this failure.
        retries: Number of retry attempts made.
    """

    def __init__(self, message: str, error_code: ErrorCode, retries: int) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.retries = retries
