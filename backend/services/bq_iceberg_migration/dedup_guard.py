"""
Deduplication Guard for BigQuery to Iceberg Migrations

Prevents duplicate data file registration during retry/resume operations
by checking Iceberg snapshot metadata before appending files.

This ensures zero duplicate rows when a migration is resumed after a partial
failure in the load stage.
"""

import logging
from typing import List, Set, Tuple

logger = logging.getLogger(__name__)


class DeduplicationGuard:
    """
    Prevents duplicate data file registration during retry/resume operations.

    When a migration fails mid-load and is resumed, some tables may already
    have data files registered from the previous attempt. This guard inspects
    the Iceberg table's latest snapshot metadata to identify which files are
    already registered, and filters candidate files accordingly.

    Key Features:
    - Snapshot-based file detection using Iceberg metadata
    - Safe append verification before data registration
    - Zero duplicate rows guarantee on retry/resume
    """

    def get_registered_files(self, table) -> Set[str]:
        """
        Get all data file paths currently registered in the Iceberg table's latest snapshot.

        Inspects the table's current snapshot and iterates through all manifest
        entries to collect registered file paths.

        Args:
            table: PyIceberg Table object to inspect.

        Returns:
            Set of file path strings registered in the table's latest snapshot.
            Returns an empty set if the table has no snapshots (new table).
        """
        try:
            snapshot = table.current_snapshot()
            if not snapshot:
                logger.debug(
                    "Table has no current snapshot, returning empty registered files set"
                )
                return set()

            registered = set()
            for manifest in snapshot.manifests(table.io):
                for entry in manifest.fetch_manifest_entry(table.io):
                    registered.add(entry.data_file.file_path)

            logger.debug(
                f"Found {len(registered)} registered files in table snapshot",
                extra={"registered_file_count": len(registered)}
            )
            return registered

        except Exception as e:
            logger.error(
                f"Failed to retrieve registered files from snapshot: {e}",
                extra={"error": str(e)}
            )
            raise

    def filter_new_files(self, table, candidate_files: List[str]) -> List[str]:
        """
        Return only files not already registered in the table.

        Compares candidate S3 URIs against the set of file paths in the
        table's latest snapshot metadata.

        Args:
            table: PyIceberg Table object to check against.
            candidate_files: List of S3 file URIs to evaluate.

        Returns:
            List of file URIs that are not yet registered in the table.
        """
        registered = self.get_registered_files(table)
        new_files = [f for f in candidate_files if f not in registered]

        if len(new_files) < len(candidate_files):
            skipped_count = len(candidate_files) - len(new_files)
            logger.info(
                f"Deduplication: {skipped_count} files already registered, "
                f"{len(new_files)} new files to append",
                extra={
                    "candidate_count": len(candidate_files),
                    "new_count": len(new_files),
                    "skipped_count": skipped_count,
                }
            )
        else:
            logger.debug(
                f"All {len(candidate_files)} candidate files are new",
                extra={"candidate_count": len(candidate_files)}
            )

        return new_files

    def is_safe_to_append(self, table, candidate_files: List[str]) -> Tuple[bool, List[str]]:
        """
        Check if append is safe (no duplicates). Returns (safe, new_files_only).

        An append is considered safe when there are new files to add. If all
        candidate files are already registered, the append is not safe (nothing
        to do, would be a no-op).

        Args:
            table: PyIceberg Table object to check against.
            candidate_files: List of S3 file URIs to evaluate.

        Returns:
            Tuple of (safe_to_append, new_files_only):
            - safe_to_append: True if there are new files to append, False otherwise.
            - new_files_only: List of file URIs not yet registered.
        """
        new_files = self.filter_new_files(table, candidate_files)
        safe = len(new_files) > 0

        if not safe:
            logger.warning(
                "Append not safe: all candidate files already registered in table. "
                "This may indicate a duplicate resume attempt.",
                extra={"candidate_count": len(candidate_files)}
            )
        else:
            logger.info(
                f"Append is safe: {len(new_files)} new files ready for registration",
                extra={
                    "new_file_count": len(new_files),
                    "total_candidates": len(candidate_files),
                }
            )

        return (safe, new_files)
