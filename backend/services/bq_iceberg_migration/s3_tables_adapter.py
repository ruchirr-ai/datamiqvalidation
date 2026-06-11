"""
S3 Tables Adapter for AWS S3 Tables (Managed Iceberg) Operations

Handles namespace and table management for the AWS S3 Tables variant of
Iceberg migrations. All resource names (namespaces, tables) must be
user-approved before creation — the system never auto-generates names.

Requirements:
- 5.7: Use user-provided namespace name, create via S3 Tables API if not existing
- 1.3: Table bucket ARN must match arn:aws:s3tables:<region>:<account-id>:bucket/<name>
- 1.1, 1.2, 1.3, 1.4: Maintenance configuration (compaction + snapshot management)
- 2.1, 2.3: glue.id derivation from table bucket ARN
"""

import re
import time
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MaintenanceConfig:
    """
    Configuration for S3 Tables maintenance settings.

    Controls compaction and snapshot management behavior applied via
    the Boto3 `put_table_maintenance_configuration()` API after table creation.

    Attributes:
        compaction_enabled: Whether automatic compaction is enabled.
        target_file_size_mb: Target file size for compaction output (64-512 MB).
        compaction_strategy: Strategy for compaction — binpack, sort, or z-order.
        sort_columns: Columns to sort by when strategy is sort or z-order.
        snapshot_management_enabled: Whether snapshot management is enabled.
        min_snapshots_to_keep: Minimum number of snapshots to retain.
        max_snapshot_age_hours: Maximum age of snapshots in hours before cleanup.
    """

    compaction_enabled: bool = True
    target_file_size_mb: int = 512
    compaction_strategy: str = "binpack"
    sort_columns: list[str] = field(default_factory=list)
    snapshot_management_enabled: bool = True
    min_snapshots_to_keep: int = 30
    max_snapshot_age_hours: int = 720


class S3TablesAdapter:
    """
    Adapter for AWS S3 Tables (managed Iceberg) operations.

    All resource names must be user-approved before creation.
    Namespace names are collected during the structure review step and
    must pass S3 Tables naming validation before use.
    """

    # S3 Tables namespace naming constraints
    # - 1 to 255 characters
    # - Lowercase letters, numbers, and underscores only
    # - Must start with a letter or underscore
    # - Cannot start with a number
    NAMESPACE_NAME_PATTERN = re.compile(r'^[a-z_][a-z0-9_]{0,254}$')
    NAMESPACE_MIN_LENGTH = 1
    NAMESPACE_MAX_LENGTH = 255

    # S3 Tables table naming constraints
    # - 1 to 255 characters
    # - Lowercase letters, numbers, and underscores only
    # - Must start with a letter or underscore
    TABLE_NAME_PATTERN = re.compile(r'^[a-z_][a-z0-9_]{0,254}$')

    def __init__(self, s3tables_client: Any, table_bucket_arn: str, aws_region: str):
        """
        Initialize S3 Tables Adapter.

        Args:
            s3tables_client: Boto3 S3Tables client for API operations.
            table_bucket_arn: ARN of the S3 table bucket
                (format: arn:aws:s3tables:<region>:<account-id>:bucket/<name>).
            aws_region: AWS region where the table bucket resides.
        """
        self._client = s3tables_client
        self._table_bucket_arn = table_bucket_arn
        self._aws_region = aws_region

        logger.info(
            "S3TablesAdapter initialized",
            extra={
                "table_bucket_arn": table_bucket_arn,
                "aws_region": aws_region,
            }
        )

    # Pattern for validating S3 Tables bucket ARN format
    _TABLE_BUCKET_ARN_PATTERN = re.compile(
        r'^arn:aws:s3tables:([a-z0-9-]+):(\d{12}):bucket/([a-z0-9][a-z0-9.\-]{1,61}[a-z0-9])$'
    )

    @staticmethod
    def derive_glue_id(table_bucket_arn: str) -> str:
        """
        Derive the glue.id catalog identifier from a table bucket ARN.

        Extracts account_id and bucket_name from the ARN format:
            arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>

        Returns:
            String in format: {account_id}:s3tablescatalog/{bucket-name}

        Raises:
            ValueError: If ARN format is invalid.

        Example:
            >>> S3TablesAdapter.derive_glue_id(
            ...     "arn:aws:s3tables:us-east-1:123456789012:bucket/my-bucket"
            ... )
            '123456789012:s3tablescatalog/my-bucket'
        """
        match = S3TablesAdapter._TABLE_BUCKET_ARN_PATTERN.match(table_bucket_arn)
        if not match:
            raise ValueError(
                f"Invalid table bucket ARN format: '{table_bucket_arn}'. "
                f"Expected format: arn:aws:s3tables:<region>:<account-id>:bucket/<bucket-name>"
            )

        account_id = match.group(2)
        bucket_name = match.group(3)

        glue_id = f"{account_id}:s3tablescatalog/{bucket_name}"

        logger.debug(
            "Derived glue.id from table bucket ARN",
            extra={
                "table_bucket_arn": table_bucket_arn,
                "glue_id": glue_id,
            }
        )

        return glue_id

    def validate_namespace_name(self, namespace: str) -> bool:
        """
        Validate namespace name follows S3 Tables naming conventions.

        S3 Tables namespace naming rules:
        - 1 to 255 characters in length
        - Lowercase letters, numbers, and underscores only
        - Must start with a letter or underscore (not a number)

        Args:
            namespace: The namespace name to validate.

        Returns:
            True if the name is valid, False otherwise.
        """
        if not namespace:
            logger.warning("Namespace name is empty")
            return False

        if len(namespace) > self.NAMESPACE_MAX_LENGTH:
            logger.warning(
                "Namespace name exceeds maximum length",
                extra={
                    "namespace": namespace,
                    "length": len(namespace),
                    "max_length": self.NAMESPACE_MAX_LENGTH,
                }
            )
            return False

        if not self.NAMESPACE_NAME_PATTERN.match(namespace):
            logger.warning(
                "Namespace name does not match S3 Tables naming conventions",
                extra={"namespace": namespace}
            )
            return False

        return True

    def ensure_namespace(self, namespace: str) -> None:
        """
        Create namespace in S3 table bucket if it does not already exist.

        Namespace name MUST be user-provided and approved during the structure
        review step. This method will NOT auto-generate or modify the name.

        Args:
            namespace: User-approved namespace name.

        Raises:
            ValueError: If the namespace name fails validation.
            RuntimeError: If the S3 Tables API call fails for a reason other
                than the namespace already existing.
        """
        if not self.validate_namespace_name(namespace):
            raise ValueError(
                f"Invalid namespace name '{namespace}'. "
                f"Must be 1-255 characters, lowercase letters/numbers/underscores, "
                f"and start with a letter or underscore."
            )

        logger.info(
            "Ensuring namespace exists in S3 Tables",
            extra={
                "namespace": namespace,
                "table_bucket_arn": self._table_bucket_arn,
            }
        )

        try:
            self._client.create_namespace(
                tableBucketARN=self._table_bucket_arn,
                namespace=[namespace],
            )
            logger.info(
                "Namespace created successfully in S3 Tables",
                extra={"namespace": namespace}
            )
        except self._client.exceptions.ConflictException:
            # Namespace already exists — this is expected on retry/resume
            logger.info(
                "Namespace already exists in S3 Tables, skipping creation",
                extra={"namespace": namespace}
            )
        except Exception as e:
            error_type = type(e).__name__
            logger.error(
                "Failed to create namespace in S3 Tables",
                extra={
                    "namespace": namespace,
                    "table_bucket_arn": self._table_bucket_arn,
                    "error_type": error_type,
                    "error_message": str(e),
                    "error_code": "S3_TABLES_API_FAILED",
                }
            )
            raise RuntimeError(
                f"Failed to create namespace '{namespace}' in S3 Tables: {e}"
            ) from e

    def create_table(
        self,
        namespace: str,
        table_name: str,
        schema: Any,
        partition_spec: Any,
    ) -> dict:
        """
        Create a table in S3 Tables and return metadata location.

        Table name MUST be user-approved during the structure review step.
        The table is created within the specified namespace in the S3 table
        bucket, and the returned metadata location is used for Glue catalog
        registration.

        Args:
            namespace: User-approved namespace name.
            table_name: User-approved table name.
            schema: PyIceberg Schema object for the table.
            partition_spec: PyIceberg PartitionSpec object for the table.

        Returns:
            dict with keys:
                - metadata_location (str): S3 URI of the Iceberg metadata file.
                - table_arn (str): ARN of the created S3 Tables table.
                - namespace (str): The namespace the table was created in.
                - table_name (str): The table name.

        Raises:
            ValueError: If namespace or table name fails validation.
            RuntimeError: If the S3 Tables API call fails.
        """
        if not self.validate_namespace_name(namespace):
            raise ValueError(
                f"Invalid namespace name '{namespace}'. "
                f"Must be 1-255 characters, lowercase letters/numbers/underscores, "
                f"and start with a letter or underscore."
            )

        if not self._validate_table_name(table_name):
            raise ValueError(
                f"Invalid table name '{table_name}'. "
                f"Must be 1-255 characters, lowercase letters/numbers/underscores, "
                f"and start with a letter or underscore."
            )

        logger.info(
            "Creating table in S3 Tables",
            extra={
                "namespace": namespace,
                "table_name": table_name,
                "table_bucket_arn": self._table_bucket_arn,
            }
        )

        try:
            # Build the Iceberg table format configuration
            format_config = {
                "icebergInput": {
                    "metadataLocation": "",  # S3 Tables generates this
                    "schema": self._serialize_schema(schema),
                    "partitionSpec": self._serialize_partition_spec(partition_spec),
                }
            }

            response = self._client.create_table(
                tableBucketARN=self._table_bucket_arn,
                namespace=namespace,
                name=table_name,
                format="ICEBERG",
            )

            table_arn = response.get("tableARN", "")
            # Retrieve the metadata location from the table details
            metadata_location = self._get_table_metadata_location(
                namespace, table_name
            )

            logger.info(
                "Table created successfully in S3 Tables",
                extra={
                    "namespace": namespace,
                    "table_name": table_name,
                    "table_arn": table_arn,
                    "metadata_location": metadata_location,
                }
            )

            return {
                "metadata_location": metadata_location,
                "table_arn": table_arn,
                "namespace": namespace,
                "table_name": table_name,
            }

        except self._client.exceptions.ConflictException:
            # Table already exists — retrieve its metadata location
            logger.info(
                "Table already exists in S3 Tables, retrieving metadata location",
                extra={
                    "namespace": namespace,
                    "table_name": table_name,
                }
            )
            metadata_location = self._get_table_metadata_location(
                namespace, table_name
            )
            return {
                "metadata_location": metadata_location,
                "table_arn": "",
                "namespace": namespace,
                "table_name": table_name,
            }

        except Exception as e:
            error_type = type(e).__name__
            logger.error(
                "Failed to create table in S3 Tables",
                extra={
                    "namespace": namespace,
                    "table_name": table_name,
                    "table_bucket_arn": self._table_bucket_arn,
                    "error_type": error_type,
                    "error_message": str(e),
                    "error_code": "S3_TABLES_API_FAILED",
                }
            )
            raise RuntimeError(
                f"Failed to create table '{namespace}.{table_name}' "
                f"in S3 Tables: {e}"
            ) from e

    # Retry configuration for maintenance configuration calls
    _MAINTENANCE_MAX_RETRIES = 3  # 3 retries after initial attempt (4 total attempts)
    _MAINTENANCE_BACKOFF_BASE = 2  # seconds
    _MAINTENANCE_BACKOFF_MULTIPLIER = 3  # exponential factor: 2s, 6s, 18s

    def configure_maintenance(
        self,
        namespace: str,
        table_name: str,
        config: MaintenanceConfig,
    ) -> bool:
        """
        Configure S3 Tables maintenance (compaction + snapshot management)
        via put_table_maintenance_configuration() Boto3 API.

        Called immediately after successful table creation.
        Retries up to 3 times with exponential backoff (2s, 6s, 18s).
        Logs error but does NOT fail the table creation on failure.

        Args:
            namespace: Table namespace.
            table_name: Table name.
            config: MaintenanceConfig with user settings.

        Returns:
            True if configuration succeeded, False if all retries failed.
        """
        payload = self._build_maintenance_payload(config)
        full_table_name = f"{namespace}.{table_name}"

        last_error = None
        for attempt in range(self._MAINTENANCE_MAX_RETRIES + 1):
            try:
                self._client.put_table_maintenance_configuration(
                    tableBucketARN=self._table_bucket_arn,
                    namespace=namespace,
                    tableName=table_name,
                    **payload,
                )

                logger.info(
                    "S3 Tables Maintenance configuration applied successfully",
                    extra={
                        "table_name": full_table_name,
                        "namespace": namespace,
                        "compaction_strategy": config.compaction_strategy,
                        "target_file_size_mb": config.target_file_size_mb,
                        "snapshot_management_enabled": config.snapshot_management_enabled,
                        "min_snapshots_to_keep": config.min_snapshots_to_keep,
                        "max_snapshot_age_hours": config.max_snapshot_age_hours,
                    }
                )
                return True

            except Exception as e:
                last_error = e
                delay = (
                    self._MAINTENANCE_BACKOFF_BASE
                    * (self._MAINTENANCE_BACKOFF_MULTIPLIER ** attempt)
                )
                logger.warning(
                    "S3 Tables maintenance configuration attempt failed, retrying",
                    extra={
                        "table_name": full_table_name,
                        "namespace": namespace,
                        "attempt": attempt + 1,
                        "max_retries": self._MAINTENANCE_MAX_RETRIES,
                        "backoff_seconds": delay,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                    }
                )
                if attempt < self._MAINTENANCE_MAX_RETRIES:
                    time.sleep(delay)

        # All retries exhausted
        logger.error(
            "S3 Tables maintenance configuration failed after all retries",
            extra={
                "table_name": full_table_name,
                "namespace": namespace,
                "error_code": "S3_TABLES_MAINTENANCE_CONFIG_FAILED",
                "error_type": type(last_error).__name__,
                "error_message": str(last_error),
                "max_retries": self._MAINTENANCE_MAX_RETRIES,
            }
        )
        return False

    def _build_maintenance_payload(self, config: MaintenanceConfig) -> dict:
        """
        Build the put_table_maintenance_configuration API payload.

        Constructs the payload dict matching the Boto3 API shape for
        both icebergCompaction and icebergSnapshotManagement settings.

        Args:
            config: MaintenanceConfig with user settings.

        Returns:
            Dict with keys 'icebergCompaction' and 'icebergSnapshotManagement'
            matching the Boto3 API shape for maintenance configuration.
        """
        # Build strategy value based on compaction type
        if config.compaction_strategy in ("sort", "z-order") and config.sort_columns:
            strategy_value: dict | str = {
                config.compaction_strategy: {
                    "sortColumns": config.sort_columns,
                }
            }
        else:
            strategy_value = config.compaction_strategy

        # Build compaction settings
        compaction_settings: dict = {
            "isEnabled": config.compaction_enabled,
            "settings": {
                "targetFileSizeMB": config.target_file_size_mb,
                "strategy": strategy_value,
            },
        }

        # Build snapshot management settings
        snapshot_settings: dict = {
            "isEnabled": config.snapshot_management_enabled,
            "settings": {
                "minSnapshotsToKeep": config.min_snapshots_to_keep,
                "maxSnapshotAgeHours": config.max_snapshot_age_hours,
            },
        }

        return {
            "icebergCompaction": compaction_settings,
            "icebergSnapshotManagement": snapshot_settings,
        }

    def _validate_table_name(self, table_name: str) -> bool:
        """
        Validate table name follows S3 Tables naming conventions.

        Args:
            table_name: The table name to validate.

        Returns:
            True if the name is valid, False otherwise.
        """
        if not table_name:
            return False

        if not self.TABLE_NAME_PATTERN.match(table_name):
            return False

        return True

    def _get_table_metadata_location(self, namespace: str, table_name: str) -> str:
        """
        Retrieve the metadata location for an existing table in S3 Tables.

        Args:
            namespace: Namespace containing the table.
            table_name: Name of the table.

        Returns:
            S3 URI of the Iceberg metadata file.
        """
        try:
            response = self._client.get_table(
                tableBucketARN=self._table_bucket_arn,
                namespace=namespace,
                name=table_name,
            )
            metadata_location = response.get("metadataLocation", "")
            return metadata_location
        except Exception as e:
            logger.error(
                "Failed to retrieve table metadata location",
                extra={
                    "namespace": namespace,
                    "table_name": table_name,
                    "error_message": str(e),
                }
            )
            raise RuntimeError(
                f"Failed to get metadata location for "
                f"'{namespace}.{table_name}': {e}"
            ) from e

    def _serialize_schema(self, schema: Any) -> dict:
        """
        Serialize a PyIceberg Schema object to a dict for the S3 Tables API.

        Args:
            schema: PyIceberg Schema object.

        Returns:
            Dict representation of the schema.
        """
        if hasattr(schema, "model_dump"):
            return schema.model_dump()
        if hasattr(schema, "as_dict"):
            return schema.as_dict()
        # Fallback: convert to string representation
        return {"raw": str(schema)}

    def _serialize_partition_spec(self, partition_spec: Any) -> dict:
        """
        Serialize a PyIceberg PartitionSpec object to a dict for the S3 Tables API.

        Args:
            partition_spec: PyIceberg PartitionSpec object.

        Returns:
            Dict representation of the partition spec.
        """
        if hasattr(partition_spec, "model_dump"):
            return partition_spec.model_dump()
        if hasattr(partition_spec, "as_dict"):
            return partition_spec.as_dict()
        # Fallback: convert to string representation
        return {"raw": str(partition_spec)}
