"""
Athena Verifier for BigQuery to Iceberg Migrations

Verifies that Iceberg tables are queryable via Amazon Athena. Supports two
verification modes:

1. Table queryability check (SELECT 1 LIMIT 1) — used during load stage
   when enable_load_stage_verification is True, with a 120-second timeout.
2. Row count query (SELECT COUNT(*)) — used for post-migration validation,
   with a 300-second timeout.

Requirements: 2.3, 2.5, 10.3
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default timeouts for Athena operations
DEFAULT_QUERYABLE_TIMEOUT_SECONDS = 120
DEFAULT_COUNT_TIMEOUT_SECONDS = 300

# Athena query execution states
TERMINAL_STATES = {"SUCCEEDED", "FAILED", "CANCELLED"}
SUCCESS_STATE = "SUCCEEDED"


@dataclass
class VerificationResult:
    """Result of an Athena verification operation.

    Attributes:
        status: Verification status — 'success', 'failed', 'timeout', or 'error'.
        row_count: Row count result (only for count_rows operations).
        error_message: Human-readable error description (if status is not 'success').
        error_code: Categorized error code for logging/tracking.
        query_execution_id: Athena query execution ID for debugging.
        duration_seconds: Time taken for the verification in seconds.
    """

    status: str
    row_count: Optional[int] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    query_execution_id: Optional[str] = None
    duration_seconds: Optional[float] = None


class AthenaVerifier:
    """Verifies Iceberg tables are queryable via Amazon Athena.

    Executes verification queries against Athena to confirm that Iceberg tables
    registered in the Glue Data Catalog are accessible and return valid results.

    Used in two contexts:
    - During load stage (optional): verify_table_queryable() with 120s timeout
    - Post-migration validation: count_rows() with 300s timeout

    Args:
        athena_client: A boto3 Athena client for executing queries.
        workgroup: Athena workgroup to use for query execution. Defaults to "primary".
        output_location: S3 location for Athena query results. If not provided,
                         uses the workgroup's default output location.
    """

    def __init__(
        self,
        athena_client: Any,
        workgroup: str = "primary",
        output_location: Optional[str] = None,
    ) -> None:
        self._athena_client = athena_client
        self._workgroup = workgroup
        self._output_location = output_location

    def verify_table_queryable(
        self,
        database: str,
        table_name: str,
        timeout_seconds: int = DEFAULT_QUERYABLE_TIMEOUT_SECONDS,
    ) -> VerificationResult:
        """Verify that an Iceberg table is queryable via Athena.

        Executes a lightweight query (SELECT 1 FROM <database>.<table> LIMIT 1)
        and confirms successful execution within the specified timeout.

        Args:
            database: The Glue Data Catalog database name.
            table_name: The Iceberg table name to verify.
            timeout_seconds: Maximum time to wait for query completion.
                             Defaults to 120 seconds.

        Returns:
            A VerificationResult with status 'success' if the table is queryable,
            or an appropriate error status with details.
        """
        query = f'SELECT 1 FROM "{database}"."{table_name}" LIMIT 1'

        logger.info(
            "Verifying table queryability: %s.%s (timeout=%ds)",
            database,
            table_name,
            timeout_seconds,
        )

        return self._execute_and_wait(
            query=query,
            database=database,
            timeout_seconds=timeout_seconds,
            operation="verify_table_queryable",
            table_name=table_name,
        )

    def count_rows(
        self,
        database: str,
        table_name: str,
        timeout_seconds: int = DEFAULT_COUNT_TIMEOUT_SECONDS,
    ) -> Optional[int]:
        """Execute a row count query for post-migration validation.

        Runs SELECT COUNT(*) FROM <database>.<table> and returns the result.
        Used during manual validation to compare against source row counts.

        Args:
            database: The Glue Data Catalog database name.
            table_name: The Iceberg table name to count.
            timeout_seconds: Maximum time to wait for query completion.
                             Defaults to 300 seconds.

        Returns:
            The row count as an integer if successful, or None if the query
            fails or times out.
        """
        query = f'SELECT COUNT(*) FROM "{database}"."{table_name}"'

        logger.info(
            "Counting rows for validation: %s.%s (timeout=%ds)",
            database,
            table_name,
            timeout_seconds,
        )

        result = self._execute_and_wait(
            query=query,
            database=database,
            timeout_seconds=timeout_seconds,
            operation="count_rows",
            table_name=table_name,
        )

        if result.status == "success" and result.row_count is not None:
            logger.info(
                "Row count for %s.%s: %d",
                database,
                table_name,
                result.row_count,
            )
            return result.row_count

        logger.warning(
            "Failed to count rows for %s.%s: %s",
            database,
            table_name,
            result.error_message,
        )
        return None

    def _execute_and_wait(
        self,
        query: str,
        database: str,
        timeout_seconds: int,
        operation: str,
        table_name: str,
    ) -> VerificationResult:
        """Execute an Athena query and wait for completion.

        Starts a query execution, then polls for completion until the query
        reaches a terminal state or the timeout is exceeded.

        Args:
            query: The SQL query to execute.
            database: The Glue database context for the query.
            timeout_seconds: Maximum wait time in seconds.
            operation: Name of the operation (for logging).
            table_name: Table name (for logging context).

        Returns:
            A VerificationResult with the outcome of the query execution.
        """
        start_time = time.time()

        # Start query execution
        try:
            start_params: dict[str, Any] = {
                "QueryString": query,
                "QueryExecutionContext": {"Database": database},
                "WorkGroup": self._workgroup,
            }

            if self._output_location:
                start_params["ResultConfiguration"] = {
                    "OutputLocation": self._output_location,
                }

            response = self._athena_client.start_query_execution(**start_params)
            query_execution_id = response["QueryExecutionId"]

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "Failed to start Athena query for %s.%s (%s): %s",
                database,
                table_name,
                operation,
                e,
            )
            return VerificationResult(
                status="error",
                error_message=f"Failed to start Athena query: {e}",
                error_code="ATHENA_START_FAILED",
                duration_seconds=elapsed,
            )

        # Poll for query completion
        try:
            while True:
                elapsed = time.time() - start_time
                if elapsed >= timeout_seconds:
                    # Attempt to cancel the timed-out query
                    self._cancel_query(query_execution_id)
                    logger.warning(
                        "Athena query timed out for %s.%s (%s) after %.1fs "
                        "(execution_id=%s)",
                        database,
                        table_name,
                        operation,
                        elapsed,
                        query_execution_id,
                    )
                    return VerificationResult(
                        status="timeout",
                        error_message=(
                            f"Query timed out after {timeout_seconds}s"
                        ),
                        error_code="ATHENA_VERIFICATION_TIMEOUT",
                        query_execution_id=query_execution_id,
                        duration_seconds=elapsed,
                    )

                # Get query execution status
                status_response = self._athena_client.get_query_execution(
                    QueryExecutionId=query_execution_id
                )
                state = status_response["QueryExecution"]["Status"]["State"]

                if state in TERMINAL_STATES:
                    break

                # Wait before polling again (adaptive backoff)
                time.sleep(min(2.0, timeout_seconds - elapsed))

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                "Error polling Athena query status for %s.%s (%s): %s",
                database,
                table_name,
                operation,
                e,
            )
            return VerificationResult(
                status="error",
                error_message=f"Error polling query status: {e}",
                error_code="ATHENA_POLL_FAILED",
                query_execution_id=query_execution_id,
                duration_seconds=elapsed,
            )

        elapsed = time.time() - start_time

        # Handle terminal states
        if state == SUCCESS_STATE:
            row_count = self._extract_row_count(
                query_execution_id, operation
            )
            logger.info(
                "Athena %s succeeded for %s.%s in %.1fs (execution_id=%s)",
                operation,
                database,
                table_name,
                elapsed,
                query_execution_id,
            )
            return VerificationResult(
                status="success",
                row_count=row_count,
                query_execution_id=query_execution_id,
                duration_seconds=elapsed,
            )

        # Query failed or was cancelled
        error_reason = (
            status_response["QueryExecution"]["Status"]
            .get("StateChangeReason", "Unknown error")
        )
        logger.warning(
            "Athena %s failed for %s.%s: state=%s, reason=%s (execution_id=%s)",
            operation,
            database,
            table_name,
            state,
            error_reason,
            query_execution_id,
        )
        return VerificationResult(
            status="failed",
            error_message=f"Query {state.lower()}: {error_reason}",
            error_code="ATHENA_QUERY_FAILED",
            query_execution_id=query_execution_id,
            duration_seconds=elapsed,
        )

    def _extract_row_count(
        self,
        query_execution_id: str,
        operation: str,
    ) -> Optional[int]:
        """Extract the row count from a COUNT(*) query result.

        Only attempts extraction for count_rows operations. For
        verify_table_queryable, returns None (we only care about success).

        Args:
            query_execution_id: The Athena query execution ID.
            operation: The operation type ('count_rows' or 'verify_table_queryable').

        Returns:
            The integer row count if this is a count operation and extraction
            succeeds, otherwise None.
        """
        if operation != "count_rows":
            return None

        try:
            results_response = self._athena_client.get_query_results(
                QueryExecutionId=query_execution_id
            )
            rows = results_response.get("ResultSet", {}).get("Rows", [])

            # First row is the header, second row is the data
            if len(rows) >= 2:
                data_row = rows[1]
                value = data_row.get("Data", [{}])[0].get("VarCharValue", "0")
                return int(value)

        except (ValueError, IndexError, KeyError) as e:
            logger.warning(
                "Failed to extract row count from query results "
                "(execution_id=%s): %s",
                query_execution_id,
                e,
            )

        return None

    def _cancel_query(self, query_execution_id: str) -> None:
        """Attempt to cancel a running Athena query.

        Best-effort cancellation — failures are logged but not raised.

        Args:
            query_execution_id: The Athena query execution ID to cancel.
        """
        try:
            self._athena_client.stop_query_execution(
                QueryExecutionId=query_execution_id
            )
            logger.debug(
                "Cancelled Athena query execution: %s", query_execution_id
            )
        except Exception as e:
            logger.debug(
                "Failed to cancel Athena query %s (may have already completed): %s",
                query_execution_id,
                e,
            )
