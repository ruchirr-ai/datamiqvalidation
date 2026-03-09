"""
Deploy Service

Executes converted DDL/code assets against a target database connection
in dependency order. Stops on first failure and reports partial results.
Uses the platform's existing encryption service to decrypt credentials.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from models.conversion_job import ConversionJob
from models.conversion_batch import ConversionBatch
from models.connection import Connection
from services.encryption_service import get_encryption_service

logger = logging.getLogger(__name__)

# Dependency order for asset deployment — lower index = deployed first
ASSET_DEPLOY_ORDER = [
    "TABLE_DDL",
    "VIEW",
    "STORED_PROCEDURE",
    "FUNCTION",
    "MATERIALIZED_VIEW",
    "SCHEDULED_QUERY",
]


@dataclass
class DeployResult:
    """Result of a batch deployment operation."""
    success: bool
    deployed_assets: list[str] = field(default_factory=list)
    failed_asset: Optional[str] = None
    error_message: Optional[str] = None


class DeployService:
    """Deploys converted SQL/DDL assets to a target database.

    Assets are executed in dependency order. Execution stops on the first failure.
    """

    def deploy_batch(
        self,
        batch: ConversionBatch,
        jobs: list[ConversionJob],
        target_connection: Connection,
    ) -> DeployResult:
        """Deploy all completed conversion jobs to the target database."""
        conn_params = self._get_connection_params(target_connection)

        sorted_jobs = self._sort_by_deploy_order(
            [j for j in jobs if j.target_code]
        )

        if not sorted_jobs:
            logger.warning(
                "No deployable assets found",
                extra={"batch_id": batch.id},
            )
            return DeployResult(success=True, deployed_assets=[])

        deployed: list[str] = []

        for job in sorted_jobs:
            asset_label = job.asset_name or f"job_{job.id}"
            try:
                self._execute_sql(
                    sql=job.target_code,
                    connection_type=target_connection.type,
                    conn_params=conn_params,
                )
                deployed.append(asset_label)
                logger.info(
                    "Asset deployed successfully",
                    extra={
                        "batch_id": batch.id,
                        "asset_name": asset_label,
                        "asset_type": job.asset_type,
                    },
                )
            except Exception as exc:
                error_msg = str(exc)
                logger.error(
                    "Asset deployment failed, stopping batch deploy",
                    extra={
                        "batch_id": batch.id,
                        "asset_name": asset_label,
                        "asset_type": job.asset_type,
                    },
                )
                return DeployResult(
                    success=False,
                    deployed_assets=deployed,
                    failed_asset=asset_label,
                    error_message=error_msg,
                )

        logger.info(
            "Batch deployment completed successfully",
            extra={"batch_id": batch.id, "deployed_count": len(deployed)},
        )
        return DeployResult(success=True, deployed_assets=deployed)

    @staticmethod
    def _sort_by_deploy_order(jobs: list[ConversionJob]) -> list[ConversionJob]:
        """Sort jobs by the predefined asset dependency order."""
        order_map = {t: i for i, t in enumerate(ASSET_DEPLOY_ORDER)}
        return sorted(
            jobs,
            key=lambda j: order_map.get(j.asset_type, len(ASSET_DEPLOY_ORDER)),
        )

    @staticmethod
    def _get_connection_params(connection: Connection) -> dict:
        """Return decrypted connection parameters."""
        if connection.connection_params_encrypted:
            encryption_service = get_encryption_service()
            decrypted = encryption_service.decrypt(
                connection.connection_params_encrypted
            )
            return json.loads(decrypted)
        return connection.connection_params or {}

    @staticmethod
    def _execute_sql(sql: str, connection_type: str, conn_params: dict) -> None:
        """Execute a SQL statement against the target database."""
        if connection_type in ("postgresql", "redshift"):
            import psycopg2

            conn = psycopg2.connect(
                host=conn_params.get("host", "localhost"),
                port=conn_params.get("port", 5432),
                database=conn_params.get("database", ""),
                user=conn_params.get("username", ""),
                password=conn_params.get("password", ""),
            )
            try:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(sql)
            finally:
                conn.close()
        else:
            raise NotImplementedError(
                f"Deployment to '{connection_type}' databases is not yet supported"
            )
