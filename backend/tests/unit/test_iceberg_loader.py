"""
Unit tests for ParallelIcebergLoader service.

Tests parallel table loading, retry with exponential backoff,
deduplication checks, error isolation, and progress tracking.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.8, 12.1, 12.2, 12.4
"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, call

from services.bq_iceberg_migration.iceberg_loader import (
    ParallelIcebergLoader,
    TableLoadResult,
    LoadResult,
    DEFAULT_TABLE_PROPERTIES,
    _RetryExhaustedError,
)
from services.bq_iceberg_migration.error_codes import ErrorCode, MigrationLogger


# --- Fixtures ---

@pytest.fixture
def mock_catalog():
    """Mock PyIceberg GlueCatalog."""
    catalog = MagicMock()
    catalog.create_table = MagicMock(return_value=MagicMock())
    catalog.load_table = MagicMock(return_value=MagicMock())
    catalog.load_namespace_properties = MagicMock(return_value={})
    catalog.create_namespace = MagicMock()
    return catalog


@pytest.fixture
def mock_credential_provider():
    """Mock AWSCredentialProvider."""
    return MagicMock()


@pytest.fixture
def mock_type_mapper():
    """Mock BQToIcebergTypeMapper."""
    return MagicMock()


@pytest.fixture
def mock_partition_mapper():
    """Mock PartitionSpecMapper."""
    return MagicMock()


@pytest.fixture
def mock_dedup_guard():
    """Mock DeduplicationGuard that allows all appends."""
    guard = MagicMock()
    guard.is_safe_to_append = MagicMock(
        return_value=(True, ["s3://bucket/data/part-00000.parquet"])
    )
    return guard


@pytest.fixture
def loader(
    mock_catalog, mock_credential_provider, mock_type_mapper,
    mock_partition_mapper, mock_dedup_guard
):
    """ParallelIcebergLoader with mocked dependencies."""
    return ParallelIcebergLoader(
        catalog=mock_catalog,
        credential_provider=mock_credential_provider,
        type_mapper=mock_type_mapper,
        partition_mapper=mock_partition_mapper,
        dedup_guard=mock_dedup_guard,
        parallelism=4,
    )


# --- Sample Payloads ---

SAMPLE_STRUCTURE_PLAN = {
    "tables": [
        {
            "proposed_name": "events",
            "database": "analytics_db",
            "columns": [
                {"name": "event_id", "type": "string"},
                {"name": "event_date", "type": "date"},
            ],
            "schema": MagicMock(),
            "partition_spec": {"column": "event_date", "transform": "day"},
            "sort_order": MagicMock(),
            "sort_order_columns": ["event_date"],
            "table_properties": {"format-version": "2"},
            "data_files": [
                "s3://bucket/data/events/part-00000.parquet",
                "s3://bucket/data/events/part-00001.parquet",
            ],
        },
        {
            "proposed_name": "users",
            "database": "analytics_db",
            "columns": [
                {"name": "user_id", "type": "long"},
                {"name": "name", "type": "string"},
            ],
            "schema": MagicMock(),
            "partition_spec": None,
            "sort_order": MagicMock(),
            "sort_order_columns": None,
            "table_properties": {},
            "data_files": [
                "s3://bucket/data/users/part-00000.parquet",
            ],
        },
    ]
}

SAMPLE_MIGRATION = MagicMock()
SAMPLE_MIGRATION.glue_database_name = "analytics_db"
SAMPLE_MIGRATION.id = 1


# --- Tests: Parallelism Configuration ---

class TestParallelismConfiguration:
    """Test worker pool configuration bounds."""

    def test_default_parallelism(self, mock_catalog, mock_credential_provider,
                                  mock_type_mapper, mock_partition_mapper, mock_dedup_guard):
        """Default parallelism should be 4."""
        loader = ParallelIcebergLoader(
            catalog=mock_catalog,
            credential_provider=mock_credential_provider,
            type_mapper=mock_type_mapper,
            partition_mapper=mock_partition_mapper,
            dedup_guard=mock_dedup_guard,
        )
        assert loader.parallelism == 4

    def test_parallelism_clamped_to_max_16(self, mock_catalog, mock_credential_provider,
                                            mock_type_mapper, mock_partition_mapper, mock_dedup_guard):
        """Parallelism above 16 should be clamped to 16."""
        loader = ParallelIcebergLoader(
            catalog=mock_catalog,
            credential_provider=mock_credential_provider,
            type_mapper=mock_type_mapper,
            partition_mapper=mock_partition_mapper,
            dedup_guard=mock_dedup_guard,
            parallelism=20,
        )
        assert loader.parallelism == 16

    def test_parallelism_clamped_to_min_1(self, mock_catalog, mock_credential_provider,
                                           mock_type_mapper, mock_partition_mapper, mock_dedup_guard):
        """Parallelism below 1 should be clamped to 1."""
        loader = ParallelIcebergLoader(
            catalog=mock_catalog,
            credential_provider=mock_credential_provider,
            type_mapper=mock_type_mapper,
            partition_mapper=mock_partition_mapper,
            dedup_guard=mock_dedup_guard,
            parallelism=0,
        )
        assert loader.parallelism == 1

    def test_parallelism_negative_clamped_to_1(self, mock_catalog, mock_credential_provider,
                                                mock_type_mapper, mock_partition_mapper, mock_dedup_guard):
        """Negative parallelism should be clamped to 1."""
        loader = ParallelIcebergLoader(
            catalog=mock_catalog,
            credential_provider=mock_credential_provider,
            type_mapper=mock_type_mapper,
            partition_mapper=mock_partition_mapper,
            dedup_guard=mock_dedup_guard,
            parallelism=-5,
        )
        assert loader.parallelism == 1

    def test_parallelism_exact_boundaries(self, mock_catalog, mock_credential_provider,
                                           mock_type_mapper, mock_partition_mapper, mock_dedup_guard):
        """Parallelism at exact boundaries (1 and 16) should be accepted."""
        loader_min = ParallelIcebergLoader(
            catalog=mock_catalog,
            credential_provider=mock_credential_provider,
            type_mapper=mock_type_mapper,
            partition_mapper=mock_partition_mapper,
            dedup_guard=mock_dedup_guard,
            parallelism=1,
        )
        assert loader_min.parallelism == 1

        loader_max = ParallelIcebergLoader(
            catalog=mock_catalog,
            credential_provider=mock_credential_provider,
            type_mapper=mock_type_mapper,
            partition_mapper=mock_partition_mapper,
            dedup_guard=mock_dedup_guard,
            parallelism=16,
        )
        assert loader_max.parallelism == 16


# --- Tests: load_tables ---

class TestLoadTables:
    """Test the load_tables async method."""

    @pytest.mark.asyncio
    async def test_load_tables_empty_plan(self, loader):
        """Empty structure plan should return LoadResult with 0 tables."""
        result = await loader.load_tables(
            SAMPLE_MIGRATION, {"tables": []}, None
        )
        assert result.total_tables == 0
        assert result.successful_tables == 0
        assert result.failed_tables == 0

    @pytest.mark.asyncio
    async def test_load_tables_success(self, loader, mock_catalog, mock_dedup_guard):
        """Successful load should return all tables as successful."""
        mock_catalog.load_table.side_effect = Exception("not found")
        mock_dedup_guard.is_safe_to_append.return_value = (
            True,
            ["s3://bucket/data/events/part-00000.parquet"],
        )

        mock_table = MagicMock()
        mock_table.append = MagicMock()
        mock_catalog.create_table.return_value = mock_table

        result = await loader.load_tables(
            SAMPLE_MIGRATION, SAMPLE_STRUCTURE_PLAN, None
        )

        assert result.total_tables == 2
        assert result.successful_tables == 2
        assert result.failed_tables == 0
        assert result.all_succeeded is True

    @pytest.mark.asyncio
    async def test_load_tables_progress_callback(self, loader, mock_catalog, mock_dedup_guard):
        """Progress callback should be called after each table completes."""
        mock_catalog.load_table.side_effect = Exception("not found")
        mock_dedup_guard.is_safe_to_append.return_value = (True, ["file.parquet"])
        mock_table = MagicMock()
        mock_table.append = MagicMock()
        mock_catalog.create_table.return_value = mock_table

        progress_calls = []

        def track_progress(completed, total, percentage):
            progress_calls.append((completed, total, percentage))

        await loader.load_tables(
            SAMPLE_MIGRATION, SAMPLE_STRUCTURE_PLAN, track_progress
        )

        assert len(progress_calls) == 2
        # Final call should show 100%
        assert any(p[2] == 100 for p in progress_calls)

    @pytest.mark.asyncio
    async def test_load_tables_partial_failure(self, loader, mock_catalog, mock_dedup_guard):
        """One table failing should not affect other tables."""
        call_count = [0]

        def create_table_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("S3 access denied for first table")
            return MagicMock()

        mock_catalog.load_table.side_effect = Exception("not found")
        mock_catalog.create_table.side_effect = create_table_side_effect
        mock_dedup_guard.is_safe_to_append.return_value = (True, ["file.parquet"])

        result = await loader.load_tables(
            SAMPLE_MIGRATION, SAMPLE_STRUCTURE_PLAN, None
        )

        assert result.total_tables == 2
        # At least one should succeed (failure isolation)
        assert result.successful_tables >= 1
        assert result.failed_tables >= 1


# --- Tests: create_table ---

class TestCreateTable:
    """Test the create_table method."""

    def test_create_table_calls_catalog(self, loader, mock_catalog):
        """create_table should call catalog.create_table with correct args."""
        schema = MagicMock()
        partition_spec = MagicMock()
        sort_order = MagicMock()
        properties = {"custom_prop": "value"}

        loader.create_table(
            "my_db", "my_table", schema, partition_spec, sort_order, properties
        )

        mock_catalog.create_table.assert_called_once()
        call_kwargs = mock_catalog.create_table.call_args
        assert call_kwargs.kwargs["identifier"] == "my_db.my_table"
        assert call_kwargs.kwargs["schema"] == schema
        assert call_kwargs.kwargs["partition_spec"] == partition_spec
        assert call_kwargs.kwargs["sort_order"] == sort_order

    def test_create_table_merges_default_properties(self, loader, mock_catalog):
        """create_table should merge user properties with defaults."""
        loader.create_table(
            "db", "tbl", MagicMock(), MagicMock(), MagicMock(),
            {"custom": "value"}
        )

        call_kwargs = mock_catalog.create_table.call_args.kwargs
        props = call_kwargs["properties"]

        # Should have default properties
        assert props["table_type"] == "ICEBERG"
        assert props["write.format.default"] == "parquet"
        assert props["write.parquet.compression-codec"] == "zstd"
        assert props["format-version"] == "2"
        # Should have custom property
        assert props["custom"] == "value"

    def test_create_table_user_properties_override_defaults(self, loader, mock_catalog):
        """User properties should override defaults when keys conflict."""
        loader.create_table(
            "db", "tbl", MagicMock(), MagicMock(), MagicMock(),
            {"format-version": "1"}
        )

        call_kwargs = mock_catalog.create_table.call_args.kwargs
        props = call_kwargs["properties"]
        assert props["format-version"] == "1"

    def test_create_table_no_user_properties(self, loader, mock_catalog):
        """create_table with no user properties should use only defaults."""
        loader.create_table(
            "db", "tbl", MagicMock(), MagicMock(), MagicMock(), None
        )

        call_kwargs = mock_catalog.create_table.call_args.kwargs
        props = call_kwargs["properties"]
        assert props == DEFAULT_TABLE_PROPERTIES

    def test_create_table_raises_on_failure(self, loader, mock_catalog):
        """create_table should propagate catalog exceptions."""
        mock_catalog.create_table.side_effect = Exception("Glue API error")

        with pytest.raises(Exception, match="Glue API error"):
            loader.create_table(
                "db", "tbl", MagicMock(), MagicMock(), MagicMock(), {}
            )


# --- Tests: append_data_files ---

class TestAppendDataFiles:
    """Test the append_data_files method."""

    def test_append_calls_table_append(self, loader):
        """append_data_files should call table.append with file URIs."""
        table = MagicMock()
        files = ["s3://bucket/part-00000.parquet", "s3://bucket/part-00001.parquet"]

        loader.append_data_files(table, files)

        table.append.assert_called_once_with(files)

    def test_append_empty_list_skips(self, loader):
        """append_data_files with empty list should not call table.append."""
        table = MagicMock()

        loader.append_data_files(table, [])

        table.append.assert_not_called()

    def test_append_raises_on_failure(self, loader):
        """append_data_files should propagate exceptions."""
        table = MagicMock()
        table.append.side_effect = Exception("S3 access denied")

        with pytest.raises(Exception, match="S3 access denied"):
            loader.append_data_files(
                table, ["s3://bucket/part-00000.parquet"]
            )


# --- Tests: ensure_database_exists ---

class TestEnsureDatabaseExists:
    """Test the ensure_database_exists method."""

    def test_database_already_exists(self, loader, mock_catalog):
        """Should not create database if it already exists."""
        mock_catalog.load_namespace_properties.return_value = {"key": "val"}

        loader.ensure_database_exists("existing_db")

        mock_catalog.create_namespace.assert_not_called()

    def test_creates_database_when_not_exists(self, loader, mock_catalog):
        """Should create database when load_namespace_properties raises."""
        mock_catalog.load_namespace_properties.side_effect = Exception("not found")

        loader.ensure_database_exists("new_db")

        mock_catalog.create_namespace.assert_called_once_with(
            "new_db",
            properties={"description": "DataMIQ Iceberg migration database: new_db"},
        )

    def test_raises_permission_error_on_access_denied(self, loader, mock_catalog):
        """Should raise PermissionError when Glue access is denied."""
        mock_catalog.load_namespace_properties.side_effect = Exception("not found")
        mock_catalog.create_namespace.side_effect = Exception(
            "Access Denied: not authorized to perform glue:CreateDatabase"
        )

        with pytest.raises(PermissionError, match="Missing IAM permissions"):
            loader.ensure_database_exists("restricted_db")

    def test_handles_concurrent_creation(self, loader, mock_catalog):
        """Should handle race condition where DB is created concurrently."""
        mock_catalog.load_namespace_properties.side_effect = Exception("not found")
        mock_catalog.create_namespace.side_effect = Exception(
            "Database already exists"
        )

        # Should not raise
        loader.ensure_database_exists("concurrent_db")


# --- Tests: Retry Behavior ---

class TestRetryBehavior:
    """Test exponential backoff retry for S3 access errors."""

    @pytest.mark.asyncio
    async def test_retry_on_s3_error_during_create(self, loader, mock_catalog, mock_dedup_guard):
        """S3 access errors during table creation should trigger retry."""
        call_count = [0]

        def create_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise Exception("S3 access denied: NoSuchBucket")
            return MagicMock()

        mock_catalog.load_table.side_effect = Exception("not found")
        mock_catalog.create_table.side_effect = create_side_effect
        mock_dedup_guard.is_safe_to_append.return_value = (True, ["file.parquet"])

        plan = {
            "tables": [{
                "proposed_name": "retry_table",
                "database": "db",
                "columns": [],
                "schema": MagicMock(),
                "partition_spec": None,
                "sort_order": MagicMock(),
                "table_properties": {},
                "data_files": ["s3://bucket/file.parquet"],
            }]
        }

        with patch("services.bq_iceberg_migration.iceberg_loader.asyncio.sleep",
                   new_callable=AsyncMock):
            result = await loader.load_tables(SAMPLE_MIGRATION, plan, None)

        assert result.successful_tables == 1
        assert call_count[0] == 3  # 2 failures + 1 success

    @pytest.mark.asyncio
    async def test_retry_exhausted_marks_table_failed(self, loader, mock_catalog, mock_dedup_guard):
        """Exhausting all retries should mark the table as failed."""
        mock_catalog.load_table.side_effect = Exception("not found")
        mock_catalog.create_table.side_effect = Exception("S3 forbidden 403")
        mock_dedup_guard.is_safe_to_append.return_value = (True, ["file.parquet"])

        plan = {
            "tables": [{
                "proposed_name": "fail_table",
                "database": "db",
                "columns": [],
                "schema": MagicMock(),
                "partition_spec": None,
                "sort_order": MagicMock(),
                "table_properties": {},
                "data_files": ["s3://bucket/file.parquet"],
            }]
        }

        with patch("services.bq_iceberg_migration.iceberg_loader.asyncio.sleep",
                   new_callable=AsyncMock):
            result = await loader.load_tables(SAMPLE_MIGRATION, plan, None)

        assert result.failed_tables == 1
        assert result.table_results[0].success is False
        assert result.table_results[0].error_code == ErrorCode.ICEBERG_S3_ACCESS_ERROR.value


# --- Tests: Deduplication Integration ---

class TestDeduplicationIntegration:
    """Test deduplication guard integration in load flow."""

    @pytest.mark.asyncio
    async def test_skips_append_when_all_files_registered(
        self, loader, mock_catalog, mock_dedup_guard
    ):
        """Should skip append when dedup guard says all files registered."""
        mock_catalog.load_table.side_effect = Exception("not found")
        mock_table = MagicMock()
        mock_catalog.create_table.return_value = mock_table
        mock_dedup_guard.is_safe_to_append.return_value = (False, [])

        plan = {
            "tables": [{
                "proposed_name": "dedup_table",
                "database": "db",
                "columns": [],
                "schema": MagicMock(),
                "partition_spec": None,
                "sort_order": MagicMock(),
                "table_properties": {},
                "data_files": ["s3://bucket/already-registered.parquet"],
            }]
        }

        result = await loader.load_tables(SAMPLE_MIGRATION, plan, None)

        assert result.successful_tables == 1
        mock_table.append.assert_not_called()

    @pytest.mark.asyncio
    async def test_appends_only_new_files(
        self, loader, mock_catalog, mock_dedup_guard
    ):
        """Should only append files not already registered."""
        mock_catalog.load_table.side_effect = Exception("not found")
        mock_table = MagicMock()
        mock_catalog.create_table.return_value = mock_table
        new_files = ["s3://bucket/new-file.parquet"]
        mock_dedup_guard.is_safe_to_append.return_value = (True, new_files)

        plan = {
            "tables": [{
                "proposed_name": "partial_dedup",
                "database": "db",
                "columns": [],
                "schema": MagicMock(),
                "partition_spec": None,
                "sort_order": MagicMock(),
                "table_properties": {},
                "data_files": [
                    "s3://bucket/old-file.parquet",
                    "s3://bucket/new-file.parquet",
                ],
            }]
        }

        result = await loader.load_tables(SAMPLE_MIGRATION, plan, None)

        assert result.successful_tables == 1
        mock_table.append.assert_called_once_with(new_files)


# --- Tests: Error Classification ---

class TestErrorClassification:
    """Test error classification into error codes."""

    def test_classify_s3_access_error(self):
        """S3-related errors should be classified as ICEBERG_S3_ACCESS_ERROR."""
        error = Exception("S3 access denied: NoSuchBucket")
        result = ParallelIcebergLoader._classify_error(error)
        assert result == ErrorCode.ICEBERG_S3_ACCESS_ERROR

    def test_classify_glue_permission_error(self):
        """Glue permission errors should be classified as GLUE_PERMISSION_DENIED."""
        error = Exception("Glue: not authorized to perform this action")
        result = ParallelIcebergLoader._classify_error(error)
        assert result == ErrorCode.GLUE_PERMISSION_DENIED

    def test_classify_glue_registration_error(self):
        """Glue catalog errors should be classified as GLUE_REGISTRATION_FAILED."""
        error = Exception("Glue catalog API returned 500")
        result = ParallelIcebergLoader._classify_error(error)
        assert result == ErrorCode.GLUE_REGISTRATION_FAILED

    def test_classify_schema_error(self):
        """Schema evolution errors should be classified correctly."""
        error = Exception("Schema evolution failed: incompatible types")
        result = ParallelIcebergLoader._classify_error(error)
        assert result == ErrorCode.ICEBERG_SCHEMA_EVOLUTION_FAILED

    def test_classify_s3_tables_error(self):
        """S3 Tables API errors should be classified correctly."""
        error = Exception("S3Tables API returned error")
        result = ParallelIcebergLoader._classify_error(error)
        assert result == ErrorCode.S3_TABLES_API_FAILED

    def test_classify_append_error(self):
        """Append errors should be classified as ICEBERG_APPEND_FAILED."""
        error = Exception("Failed to append data files")
        result = ParallelIcebergLoader._classify_error(error)
        assert result == ErrorCode.ICEBERG_APPEND_FAILED

    def test_classify_unknown_error(self):
        """Unknown errors should default to ICEBERG_TABLE_CREATE_FAILED."""
        error = Exception("Something completely unexpected happened")
        result = ParallelIcebergLoader._classify_error(error)
        assert result == ErrorCode.ICEBERG_TABLE_CREATE_FAILED


# --- Tests: S3 Access Error Detection ---

class TestIsS3AccessError:
    """Test S3 access error detection."""

    def test_detects_access_denied(self):
        """Should detect 'access denied' as S3 error."""
        assert ParallelIcebergLoader._is_s3_access_error(
            Exception("Access Denied")
        ) is True

    def test_detects_no_such_bucket(self):
        """Should detect 'NoSuchBucket' as S3 error."""
        assert ParallelIcebergLoader._is_s3_access_error(
            Exception("NoSuchBucket: The specified bucket does not exist")
        ) is True

    def test_detects_forbidden_403(self):
        """Should detect '403' as S3 error."""
        assert ParallelIcebergLoader._is_s3_access_error(
            Exception("HTTP 403 Forbidden")
        ) is True

    def test_detects_s3_keyword(self):
        """Should detect 's3' keyword as S3 error."""
        assert ParallelIcebergLoader._is_s3_access_error(
            Exception("S3 service unavailable")
        ) is True

    def test_non_s3_error(self):
        """Non-S3 errors should return False."""
        assert ParallelIcebergLoader._is_s3_access_error(
            Exception("Invalid schema definition")
        ) is False


# --- Tests: LoadResult ---

class TestLoadResult:
    """Test LoadResult aggregation."""

    def test_all_succeeded_true(self):
        """all_succeeded should be True when no failures."""
        result = LoadResult(
            total_tables=3,
            successful_tables=3,
            failed_tables=0,
        )
        assert result.all_succeeded is True

    def test_all_succeeded_false_with_failures(self):
        """all_succeeded should be False when there are failures."""
        result = LoadResult(
            total_tables=3,
            successful_tables=2,
            failed_tables=1,
        )
        assert result.all_succeeded is False

    def test_all_succeeded_false_when_empty(self):
        """all_succeeded should be False when no tables."""
        result = LoadResult(total_tables=0)
        assert result.all_succeeded is False

    def test_progress_percentage_calculation(self):
        """progress_percentage should be (completed/total)*100."""
        result = LoadResult(
            total_tables=10,
            successful_tables=3,
            failed_tables=2,
        )
        assert result.progress_percentage == 50

    def test_progress_percentage_zero_tables(self):
        """progress_percentage should be 0 when no tables."""
        result = LoadResult(total_tables=0)
        assert result.progress_percentage == 0

    def test_progress_percentage_all_complete(self):
        """progress_percentage should be 100 when all done."""
        result = LoadResult(
            total_tables=5,
            successful_tables=5,
            failed_tables=0,
        )
        assert result.progress_percentage == 100


# --- Tests: Default Table Properties ---

class TestDefaultTableProperties:
    """Test that default table properties match the design."""

    def test_table_type_is_iceberg(self):
        """table_type should be ICEBERG."""
        assert DEFAULT_TABLE_PROPERTIES["table_type"] == "ICEBERG"

    def test_write_format_is_parquet(self):
        """write.format.default should be parquet."""
        assert DEFAULT_TABLE_PROPERTIES["write.format.default"] == "parquet"

    def test_compression_is_zstd(self):
        """write.parquet.compression-codec should be zstd."""
        assert DEFAULT_TABLE_PROPERTIES["write.parquet.compression-codec"] == "zstd"

    def test_format_version_is_2(self):
        """format-version should be 2."""
        assert DEFAULT_TABLE_PROPERTIES["format-version"] == "2"

    def test_metadata_delete_enabled(self):
        """write.metadata.delete-after-commit.enabled should be true."""
        assert DEFAULT_TABLE_PROPERTIES["write.metadata.delete-after-commit.enabled"] == "true"

    def test_previous_versions_max_is_3(self):
        """write.metadata.previous-versions-max should be 3."""
        assert DEFAULT_TABLE_PROPERTIES["write.metadata.previous-versions-max"] == "3"


# --- Tests: Existing Table Handling (Requirement 5.4) ---

class TestExistingTableHandling:
    """Test behavior when table already exists in Glue catalog."""

    @pytest.mark.asyncio
    async def test_uses_existing_table_without_recreating(
        self, loader, mock_catalog, mock_dedup_guard
    ):
        """Should use existing table without calling create_table."""
        existing_table = MagicMock()
        mock_catalog.load_table.return_value = existing_table
        mock_dedup_guard.is_safe_to_append.return_value = (True, ["file.parquet"])

        plan = {
            "tables": [{
                "proposed_name": "existing_table",
                "database": "db",
                "columns": [],
                "schema": MagicMock(),
                "partition_spec": None,
                "sort_order": MagicMock(),
                "table_properties": {},
                "data_files": ["s3://bucket/file.parquet"],
            }]
        }

        result = await loader.load_tables(SAMPLE_MIGRATION, plan, None)

        assert result.successful_tables == 1
        mock_catalog.create_table.assert_not_called()
