"""
Unit tests for DeduplicationGuard service.

Tests snapshot-based file detection, filtering of new files,
and safe append verification for retry/resume operations.
"""

import pytest
from unittest.mock import MagicMock, patch

from services.bq_iceberg_migration.dedup_guard import DeduplicationGuard


# --- Sample payloads ---

SAMPLE_REGISTERED_FILES = [
    "s3://bucket/data/table1/part-00000.parquet",
    "s3://bucket/data/table1/part-00001.parquet",
    "s3://bucket/data/table1/part-00002.parquet",
]

SAMPLE_NEW_FILES = [
    "s3://bucket/data/table1/part-00003.parquet",
    "s3://bucket/data/table1/part-00004.parquet",
]

SAMPLE_MIXED_FILES = SAMPLE_REGISTERED_FILES[:2] + SAMPLE_NEW_FILES


def _make_manifest_entry(file_path: str) -> MagicMock:
    """Create a mock manifest entry with a data_file containing the given path."""
    entry = MagicMock()
    entry.data_file = MagicMock()
    entry.data_file.file_path = file_path
    return entry


def _make_manifest(file_paths: list[str]) -> MagicMock:
    """Create a mock manifest that returns entries for the given file paths."""
    manifest = MagicMock()
    entries = [_make_manifest_entry(fp) for fp in file_paths]
    manifest.fetch_manifest_entry = MagicMock(return_value=entries)
    return manifest


def _make_table_with_files(file_paths: list[str]) -> MagicMock:
    """Create a mock Iceberg table with a snapshot containing the given files."""
    table = MagicMock()
    snapshot = MagicMock()
    manifest = _make_manifest(file_paths)
    snapshot.manifests = MagicMock(return_value=[manifest])
    table.current_snapshot = MagicMock(return_value=snapshot)
    table.io = MagicMock()
    return table


def _make_table_no_snapshot() -> MagicMock:
    """Create a mock Iceberg table with no current snapshot (new table)."""
    table = MagicMock()
    table.current_snapshot = MagicMock(return_value=None)
    table.io = MagicMock()
    return table


class TestGetRegisteredFiles:
    """Test get_registered_files retrieves file paths from snapshot metadata."""

    def test_returns_empty_set_when_no_snapshot(self):
        """A table with no snapshot should return an empty set."""
        guard = DeduplicationGuard()
        table = _make_table_no_snapshot()

        result = guard.get_registered_files(table)

        assert result == set()

    def test_returns_registered_file_paths(self):
        """Should return all file paths from the table's latest snapshot."""
        guard = DeduplicationGuard()
        table = _make_table_with_files(SAMPLE_REGISTERED_FILES)

        result = guard.get_registered_files(table)

        assert result == set(SAMPLE_REGISTERED_FILES)

    def test_returns_set_type(self):
        """Return value should be a set for O(1) membership checks."""
        guard = DeduplicationGuard()
        table = _make_table_with_files(SAMPLE_REGISTERED_FILES)

        result = guard.get_registered_files(table)

        assert isinstance(result, set)

    def test_handles_multiple_manifests(self):
        """Should collect files from multiple manifests in a snapshot."""
        guard = DeduplicationGuard()
        table = MagicMock()
        snapshot = MagicMock()

        manifest1 = _make_manifest(SAMPLE_REGISTERED_FILES[:2])
        manifest2 = _make_manifest(SAMPLE_REGISTERED_FILES[2:])
        snapshot.manifests = MagicMock(return_value=[manifest1, manifest2])
        table.current_snapshot = MagicMock(return_value=snapshot)
        table.io = MagicMock()

        result = guard.get_registered_files(table)

        assert result == set(SAMPLE_REGISTERED_FILES)

    def test_handles_empty_manifest(self):
        """A snapshot with an empty manifest should return an empty set."""
        guard = DeduplicationGuard()
        table = MagicMock()
        snapshot = MagicMock()

        manifest = MagicMock()
        manifest.fetch_manifest_entry = MagicMock(return_value=[])
        snapshot.manifests = MagicMock(return_value=[manifest])
        table.current_snapshot = MagicMock(return_value=snapshot)
        table.io = MagicMock()

        result = guard.get_registered_files(table)

        assert result == set()

    def test_deduplicates_file_paths(self):
        """Duplicate file paths across manifests should be deduplicated."""
        guard = DeduplicationGuard()
        table = MagicMock()
        snapshot = MagicMock()

        # Same file in two manifests
        duplicate_path = "s3://bucket/data/part-00000.parquet"
        manifest1 = _make_manifest([duplicate_path])
        manifest2 = _make_manifest([duplicate_path])
        snapshot.manifests = MagicMock(return_value=[manifest1, manifest2])
        table.current_snapshot = MagicMock(return_value=snapshot)
        table.io = MagicMock()

        result = guard.get_registered_files(table)

        assert result == {duplicate_path}
        assert len(result) == 1


class TestFilterNewFiles:
    """Test filter_new_files returns only unregistered files."""

    def test_all_files_are_new(self):
        """When no files are registered, all candidates should be returned."""
        guard = DeduplicationGuard()
        table = _make_table_no_snapshot()

        result = guard.filter_new_files(table, SAMPLE_NEW_FILES)

        assert result == SAMPLE_NEW_FILES

    def test_all_files_already_registered(self):
        """When all candidates are registered, should return empty list."""
        guard = DeduplicationGuard()
        table = _make_table_with_files(SAMPLE_REGISTERED_FILES)

        result = guard.filter_new_files(table, SAMPLE_REGISTERED_FILES)

        assert result == []

    def test_mixed_new_and_registered(self):
        """Should return only the files not already registered."""
        guard = DeduplicationGuard()
        table = _make_table_with_files(SAMPLE_REGISTERED_FILES)

        result = guard.filter_new_files(table, SAMPLE_MIXED_FILES)

        assert result == SAMPLE_NEW_FILES

    def test_empty_candidate_list(self):
        """Empty candidate list should return empty list."""
        guard = DeduplicationGuard()
        table = _make_table_with_files(SAMPLE_REGISTERED_FILES)

        result = guard.filter_new_files(table, [])

        assert result == []

    def test_preserves_order(self):
        """Returned files should preserve the order of the candidate list."""
        guard = DeduplicationGuard()
        table = _make_table_with_files([SAMPLE_NEW_FILES[1]])

        candidates = [SAMPLE_NEW_FILES[0], SAMPLE_NEW_FILES[1]]
        result = guard.filter_new_files(table, candidates)

        assert result == [SAMPLE_NEW_FILES[0]]

    def test_returns_list_type(self):
        """Return value should be a list."""
        guard = DeduplicationGuard()
        table = _make_table_no_snapshot()

        result = guard.filter_new_files(table, SAMPLE_NEW_FILES)

        assert isinstance(result, list)


class TestIsSafeToAppend:
    """Test is_safe_to_append returns correct (safe, new_files) tuple."""

    def test_safe_when_new_files_exist(self):
        """Should return (True, new_files) when there are files to append."""
        guard = DeduplicationGuard()
        table = _make_table_no_snapshot()

        safe, new_files = guard.is_safe_to_append(table, SAMPLE_NEW_FILES)

        assert safe is True
        assert new_files == SAMPLE_NEW_FILES

    def test_not_safe_when_all_registered(self):
        """Should return (False, []) when all files are already registered."""
        guard = DeduplicationGuard()
        table = _make_table_with_files(SAMPLE_REGISTERED_FILES)

        safe, new_files = guard.is_safe_to_append(table, SAMPLE_REGISTERED_FILES)

        assert safe is False
        assert new_files == []

    def test_safe_with_partial_overlap(self):
        """Should return (True, new_only) when some files are new."""
        guard = DeduplicationGuard()
        table = _make_table_with_files(SAMPLE_REGISTERED_FILES)

        safe, new_files = guard.is_safe_to_append(table, SAMPLE_MIXED_FILES)

        assert safe is True
        assert new_files == SAMPLE_NEW_FILES

    def test_not_safe_with_empty_candidates(self):
        """Empty candidate list should return (False, [])."""
        guard = DeduplicationGuard()
        table = _make_table_with_files(SAMPLE_REGISTERED_FILES)

        safe, new_files = guard.is_safe_to_append(table, [])

        assert safe is False
        assert new_files == []

    def test_returns_tuple(self):
        """Return value should be a tuple of (bool, list)."""
        guard = DeduplicationGuard()
        table = _make_table_no_snapshot()

        result = guard.is_safe_to_append(table, SAMPLE_NEW_FILES)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert isinstance(result[1], list)

    def test_safe_with_new_table(self):
        """A new table (no snapshot) with candidates should be safe to append."""
        guard = DeduplicationGuard()
        table = _make_table_no_snapshot()

        safe, new_files = guard.is_safe_to_append(table, SAMPLE_REGISTERED_FILES)

        assert safe is True
        assert new_files == SAMPLE_REGISTERED_FILES
