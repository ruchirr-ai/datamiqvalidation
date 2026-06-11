"""
Unit tests for the Iceberg Migration Orchestrator.

Tests the orchestrator's state machine, cancel/back navigation,
checkpoint-based resume, and progress tracking.

Requirements: 7.1, 7.3, 7.4, 7.5, 7.6, 7.7
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from services.bq_iceberg_migration.orchestrator import (
    IcebergMigrationOrchestrator,
    VALID_TRANSITIONS,
    PRESERVED_CONFIG_FIELDS,
    NAVIGABLE_STEPS,
    STEP_REGENERATED_DATA,
    calculate_progress_percentage,
)
from services.bq_iceberg_migration.error_codes import MigrationLogger
from services.bq_iceberg_migration.iceberg_loader import LoadResult, TableLoadResult


# =============================================================================
# Fixtures
# =============================================================================


def _create_mock_migration(status="pending", **kwargs):
    """Create a mock migration with default values."""
    migration = MagicMock()
    migration.id = kwargs.get("id", 1)
    migration.workspace_id = kwargs.get("workspace_id", 100)
    migration.status = status
    migration.migration_name = kwargs.get("migration_name", "test_migration")
    migration.pathway = kwargs.get("pathway", "A")
    migration.source_connection_id = kwargs.get("source_connection_id", 10)
    migration.source_project_id = kwargs.get("source_project_id", "my-gcp-project")
    migration.source_dataset = kwargs.get("source_dataset", "analytics")
    migration.source_tables = kwargs.get("source_tables", ["events", "users"])
    migration.target_connection_id = kwargs.get("target_connection_id", 20)
    migration.destination_type = kwargs.get("destination_type", "iceberg_s3")
    migration.s3_bucket = kwargs.get("s3_bucket", "my-data-lake")
    migration.s3_path_prefix = kwargs.get("s3_path_prefix", "iceberg/")
    migration.table_bucket_arn = kwargs.get("table_bucket_arn", None)
    migration.s3_tables_namespace = kwargs.get("s3_tables_namespace", None)
    migration.aws_region = kwargs.get("aws_region", "us-east-1")
    migration.glue_database_name = kwargs.get("glue_database_name", "analytics_db")
    migration.dataset_to_db_mapping = kwargs.get("dataset_to_db_mapping", None)
    migration.aws_access_key_id = kwargs.get("aws_access_key_id", "AKIAEXAMPLE")
    migration.aws_secret_access_key_encrypted = kwargs.get(
        "aws_secret_access_key_encrypted", "encrypted_secret"
    )
    migration.aws_role_arn = kwargs.get("aws_role_arn", None)
    migration.load_type = kwargs.get("load_type", "full")
    migration.table_load_configs = kwargs.get("table_load_configs", None)
    migration.parallelism = kwargs.get("parallelism", 4)
    migration.enable_load_stage_verification = kwargs.get(
        "enable_load_stage_verification", False
    )
    migration.checkpoint_data = kwargs.get("checkpoint_data", {})
    migration.structure_report = kwargs.get("structure_report", None)
    migration.cost_analysis_report = kwargs.get("cost_analysis_report", None)
    migration.structure_approved_at = kwargs.get("structure_approved_at", None)
    migration.structure_approved_by = kwargs.get("structure_approved_by", None)
    migration.current_stage = kwargs.get("current_stage", None)
    migration.progress_percentage = kwargs.get("progress_percentage", 0)
    migration.start_time = kwargs.get("start_time", None)
    migration.end_time = kwargs.get("end_time", None)
    migration.duration_seconds = kwargs.get("duration_seconds", None)
    migration.last_run_at = kwargs.get("last_run_at", None)
    migration.total_rows_source = kwargs.get("total_rows_source", None)
    migration.total_rows_target = kwargs.get("total_rows_target", None)
    migration.total_bytes_transferred = kwargs.get("total_bytes_transferred", None)
    return migration


def _create_orchestrator(**kwargs):
    """Create an orchestrator with mock dependencies."""
    loader = kwargs.get("loader", MagicMock())
    structure_report_generator = kwargs.get("structure_report_generator", MagicMock())
    cost_engine = kwargs.get("cost_engine", MagicMock())
    schema_evolution_service = kwargs.get("schema_evolution_service", MagicMock())
    validation_service = kwargs.get("validation_service", MagicMock())
    athena_verifier = kwargs.get("athena_verifier", MagicMock())
    migration_logger = kwargs.get("migration_logger", None)

    return IcebergMigrationOrchestrator(
        loader=loader,
        structure_report_generator=structure_report_generator,
        cost_engine=cost_engine,
        schema_evolution_service=schema_evolution_service,
        validation_service=validation_service,
        athena_verifier=athena_verifier,
        migration_logger=migration_logger,
    )


# =============================================================================
# Status Transition Tests
# =============================================================================


class TestStatusTransitions:
    """Tests for the state machine transition logic."""

    def test_valid_transition_pending_to_running(self):
        """Test valid transition from pending to running."""
        orchestrator = _create_orchestrator()
        assert orchestrator.is_valid_transition("pending", "running") is True

    def test_valid_transition_running_to_pending_review(self):
        """Test valid transition from running to pending_review."""
        orchestrator = _create_orchestrator()
        assert orchestrator.is_valid_transition("running", "pending_review") is True

    def test_valid_transition_pending_review_to_approved(self):
        """Test valid transition from pending_review to approved."""
        orchestrator = _create_orchestrator()
        assert orchestrator.is_valid_transition("pending_review", "approved") is True

    def test_valid_transition_approved_to_running(self):
        """Test valid transition from approved to running (load stage)."""
        orchestrator = _create_orchestrator()
        assert orchestrator.is_valid_transition("approved", "running") is True

    def test_valid_transition_running_to_completed(self):
        """Test valid transition from running to completed."""
        orchestrator = _create_orchestrator()
        assert orchestrator.is_valid_transition("running", "completed") is True

    def test_valid_transition_running_to_failed(self):
        """Test valid transition from running to failed."""
        orchestrator = _create_orchestrator()
        assert orchestrator.is_valid_transition("running", "failed") is True

    def test_valid_transition_any_to_cancelled(self):
        """Test that most states can transition to cancelled."""
        orchestrator = _create_orchestrator()
        for status in ["pending", "running", "pending_review", "approved", "paused"]:
            assert orchestrator.is_valid_transition(status, "cancelled") is True

    def test_invalid_transition_pending_to_completed(self):
        """Test invalid transition from pending directly to completed."""
        orchestrator = _create_orchestrator()
        assert orchestrator.is_valid_transition("pending", "completed") is False

    def test_invalid_transition_completed_to_pending_review(self):
        """Test invalid transition from completed to pending_review."""
        orchestrator = _create_orchestrator()
        assert orchestrator.is_valid_transition("completed", "pending_review") is False

    def test_invalid_transition_unknown_status(self):
        """Test transition from unknown status returns False."""
        orchestrator = _create_orchestrator()
        assert orchestrator.is_valid_transition("unknown", "running") is False

    def test_transition_status_applies_valid(self):
        """Test that transition_status applies valid transitions."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration(status="pending")

        result = orchestrator.transition_status(migration, "running")

        assert result is True
        assert migration.status == "running"

    def test_transition_status_rejects_invalid(self):
        """Test that transition_status rejects invalid transitions."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration(status="pending")

        result = orchestrator.transition_status(migration, "completed")

        assert result is False
        assert migration.status == "pending"

    def test_restart_from_failed(self):
        """Test restart from failed state."""
        orchestrator = _create_orchestrator()
        assert orchestrator.is_valid_transition("failed", "running") is True

    def test_restart_from_cancelled(self):
        """Test restart from cancelled state."""
        orchestrator = _create_orchestrator()
        assert orchestrator.is_valid_transition("cancelled", "running") is True

    def test_pause_from_running(self):
        """Test pause from running state."""
        orchestrator = _create_orchestrator()
        assert orchestrator.is_valid_transition("running", "paused") is True

    def test_resume_from_paused(self):
        """Test resume from paused state."""
        orchestrator = _create_orchestrator()
        assert orchestrator.is_valid_transition("paused", "running") is True


# =============================================================================
# Cancel from Review Tests
# =============================================================================


class TestCancelFromReview:
    """Tests for cancel from pending_review behavior."""

    def test_cancel_sets_status_to_cancelled(self):
        """Test that cancel sets status to cancelled."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration(status="pending_review")

        orchestrator.handle_cancel_from_review(migration)

        assert migration.status == "cancelled"

    def test_cancel_preserves_source_connection(self):
        """Test that cancel preserves source connection ID."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration(
            status="pending_review",
            source_connection_id=42,
        )

        orchestrator.handle_cancel_from_review(migration)

        assert migration.source_connection_id == 42

    def test_cancel_preserves_target_settings(self):
        """Test that cancel preserves all target settings."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration(
            status="pending_review",
            destination_type="iceberg_s3_tables",
            table_bucket_arn="arn:aws:s3tables:us-east-1:123456:bucket/my-bucket",
            aws_region="eu-west-1",
            glue_database_name="custom_db",
        )

        orchestrator.handle_cancel_from_review(migration)

        assert migration.destination_type == "iceberg_s3_tables"
        assert migration.table_bucket_arn == "arn:aws:s3tables:us-east-1:123456:bucket/my-bucket"
        assert migration.aws_region == "eu-west-1"
        assert migration.glue_database_name == "custom_db"

    def test_cancel_preserves_checkpoint_data(self):
        """Test that cancel preserves checkpoint data."""
        orchestrator = _create_orchestrator()
        checkpoint = {"assessment_tables": [{"table_name": "events"}]}
        migration = _create_mock_migration(
            status="pending_review",
            checkpoint_data=checkpoint,
        )

        orchestrator.handle_cancel_from_review(migration)

        assert migration.checkpoint_data == checkpoint

    def test_cancel_preserves_structure_report(self):
        """Test that cancel preserves the structure report for reference."""
        orchestrator = _create_orchestrator()
        report = {"tables": [{"source_table": "events"}]}
        migration = _create_mock_migration(
            status="pending_review",
            structure_report=report,
        )

        orchestrator.handle_cancel_from_review(migration)

        assert migration.structure_report == report

    def test_cancel_preserves_credentials(self):
        """Test that cancel preserves AWS credentials."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration(
            status="pending_review",
            aws_access_key_id="AKIATEST123",
            aws_secret_access_key_encrypted="enc_secret",
        )

        orchestrator.handle_cancel_from_review(migration)

        assert migration.aws_access_key_id == "AKIATEST123"
        assert migration.aws_secret_access_key_encrypted == "enc_secret"


# =============================================================================
# Back Navigation Tests
# =============================================================================


class TestBackNavigation:
    """Tests for back navigation behavior."""

    def test_back_to_source_config_clears_report(self):
        """Test that navigating back to source_config clears structure report."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration(
            status="pending_review",
            structure_report={"tables": []},
            cost_analysis_report={"setup_costs": {}},
            structure_approved_at=datetime.now(timezone.utc),
        )

        result = orchestrator.handle_back_navigation(migration, "source_config")

        assert result is True
        assert migration.structure_report is None
        assert migration.cost_analysis_report is None
        assert migration.structure_approved_at is None

    def test_back_to_review_only_clears_approval(self):
        """Test that navigating back to review only clears approval data."""
        orchestrator = _create_orchestrator()
        report = {"tables": [{"source_table": "events"}]}
        migration = _create_mock_migration(
            status="pending_review",
            structure_report=report,
            structure_approved_at=datetime.now(timezone.utc),
            structure_approved_by=5,
        )

        result = orchestrator.handle_back_navigation(migration, "review")

        assert result is True
        # Structure report should be preserved
        assert migration.structure_report == report
        # Approval data should be cleared
        assert migration.structure_approved_at is None
        assert migration.structure_approved_by is None

    def test_back_preserves_source_settings(self):
        """Test that back navigation preserves source settings."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration(
            status="pending_review",
            source_project_id="my-project",
            source_dataset="analytics",
            source_tables=["events", "users"],
        )

        orchestrator.handle_back_navigation(migration, "target_config")

        assert migration.source_project_id == "my-project"
        assert migration.source_dataset == "analytics"
        assert migration.source_tables == ["events", "users"]

    def test_back_invalid_step_returns_false(self):
        """Test that invalid step name returns False."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration(status="pending_review")

        result = orchestrator.handle_back_navigation(migration, "invalid_step")

        assert result is False

    def test_back_from_pending_review_transitions_to_running(self):
        """Test that back from pending_review transitions status to running."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration(status="pending_review")

        orchestrator.handle_back_navigation(migration, "table_selection")

        assert migration.status == "running"

    def test_all_navigable_steps_are_valid(self):
        """Test that all defined navigable steps are accepted."""
        orchestrator = _create_orchestrator()

        for step in NAVIGABLE_STEPS:
            migration = _create_mock_migration(status="pending_review")
            result = orchestrator.handle_back_navigation(migration, step)
            assert result is True, f"Step '{step}' should be valid"


# =============================================================================
# Checkpoint Resume Tests
# =============================================================================


class TestCheckpointResume:
    """Tests for checkpoint-based resume logic."""

    def test_resume_skips_completed_tables(self):
        """Test that resume skips tables with completed status."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration()
        migration.checkpoint_data = {
            "table_load_statuses": {
                "events": "completed",
                "users": "failed",
                "sessions": "pending",
            }
        }

        structure_plan = {
            "tables": [
                {"proposed_name": "events", "source_table": "events"},
                {"proposed_name": "users", "source_table": "users"},
                {"proposed_name": "sessions", "source_table": "sessions"},
            ]
        }

        result = orchestrator._filter_tables_for_resume(migration, structure_plan)

        table_names = [t["proposed_name"] for t in result]
        assert "events" not in table_names
        assert "users" in table_names
        assert "sessions" in table_names
        assert len(result) == 2

    def test_resume_with_no_checkpoint_loads_all(self):
        """Test that resume without checkpoint data loads all tables."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration()
        migration.checkpoint_data = {}

        structure_plan = {
            "tables": [
                {"proposed_name": "events"},
                {"proposed_name": "users"},
            ]
        }

        result = orchestrator._filter_tables_for_resume(migration, structure_plan)
        assert len(result) == 2

    def test_resume_with_all_completed_loads_none(self):
        """Test that resume with all tables completed loads nothing."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration()
        migration.checkpoint_data = {
            "table_load_statuses": {
                "events": "completed",
                "users": "completed",
            }
        }

        structure_plan = {
            "tables": [
                {"proposed_name": "events"},
                {"proposed_name": "users"},
            ]
        }

        result = orchestrator._filter_tables_for_resume(migration, structure_plan)
        assert len(result) == 0

    def test_resume_includes_failed_tables(self):
        """Test that resume includes tables with failed status."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration()
        migration.checkpoint_data = {
            "table_load_statuses": {
                "events": "failed",
            }
        }

        structure_plan = {
            "tables": [
                {"proposed_name": "events"},
            ]
        }

        result = orchestrator._filter_tables_for_resume(migration, structure_plan)
        assert len(result) == 1
        assert result[0]["proposed_name"] == "events"


# =============================================================================
# Progress Percentage Tests
# =============================================================================


class TestProgressPercentage:
    """Tests for progress percentage calculation."""

    def test_zero_total_returns_zero(self):
        """Test that zero total tables returns 0%."""
        assert calculate_progress_percentage(0, 0) == 0

    def test_zero_completed_returns_zero(self):
        """Test that zero completed returns 0%."""
        assert calculate_progress_percentage(0, 10) == 0

    def test_all_completed_returns_100(self):
        """Test that all completed returns 100%."""
        assert calculate_progress_percentage(10, 10) == 100

    def test_half_completed(self):
        """Test that half completed returns 50%."""
        assert calculate_progress_percentage(5, 10) == 50

    def test_one_third_completed_floors(self):
        """Test that 1/3 completed floors to 33%."""
        assert calculate_progress_percentage(1, 3) == 33

    def test_two_thirds_completed_floors(self):
        """Test that 2/3 completed floors to 66%."""
        assert calculate_progress_percentage(2, 3) == 66

    def test_negative_total_returns_zero(self):
        """Test that negative total returns 0%."""
        assert calculate_progress_percentage(5, -1) == 0

    def test_single_table_completed(self):
        """Test single table completed returns 100%."""
        assert calculate_progress_percentage(1, 1) == 100


# =============================================================================
# Approve Structure Tests
# =============================================================================


class TestApproveStructure:
    """Tests for structure approval logic."""

    def test_approve_from_pending_review(self):
        """Test successful approval from pending_review status."""
        mock_report_gen = MagicMock()
        orchestrator = _create_orchestrator(structure_report_generator=mock_report_gen)
        migration = _create_mock_migration(
            status="pending_review",
            structure_report={"tables": [{"source_table": "events"}]},
        )

        result = orchestrator.approve_structure(migration)

        assert result is True
        assert migration.status == "approved"
        assert migration.structure_approved_at is not None
        assert migration.checkpoint_data["iceberg_structure_plan"] is not None

    def test_approve_with_overrides(self):
        """Test approval with user overrides applied."""
        mock_report_gen = MagicMock()
        modified_report = {"tables": [{"source_table": "events", "partition_spec": {"column": "date", "transform": "month"}}]}
        mock_report_gen.apply_overrides.return_value = modified_report

        orchestrator = _create_orchestrator(structure_report_generator=mock_report_gen)
        migration = _create_mock_migration(
            status="pending_review",
            structure_report={"tables": [{"source_table": "events"}]},
        )

        overrides = {"events": {"partition_spec": {"column": "date", "transform": "month"}}}
        result = orchestrator.approve_structure(migration, overrides=overrides)

        assert result is True
        mock_report_gen.apply_overrides.assert_called_once()
        assert migration.checkpoint_data["iceberg_structure_plan"] == modified_report

    def test_approve_from_wrong_status_fails(self):
        """Test that approval from non-pending_review status fails."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration(status="running")

        result = orchestrator.approve_structure(migration)

        assert result is False
        assert migration.status == "running"

    def test_approve_without_report_fails(self):
        """Test that approval without a structure report fails."""
        orchestrator = _create_orchestrator()
        migration = _create_mock_migration(
            status="pending_review",
            structure_report=None,
        )

        result = orchestrator.approve_structure(migration)

        assert result is False


# =============================================================================
# Execute Migration Tests
# =============================================================================


class TestExecuteMigration:
    """Tests for the full migration execution flow."""

    def test_execute_generates_reports_and_pauses(self):
        """Test that execution generates reports and pauses at pending_review."""
        mock_report_gen = MagicMock()
        mock_report_gen.generate.return_value = {
            "tables": [{"source_table": "events", "proposed_name": "events"}],
            "table_count": 1,
        }

        mock_cost_engine = MagicMock()
        mock_cost_report = MagicMock()
        mock_cost_report.to_dict.return_value = {"setup_costs": {"total_setup": 10.0}}
        mock_cost_engine.calculate.return_value = mock_cost_report

        orchestrator = _create_orchestrator(
            structure_report_generator=mock_report_gen,
            cost_engine=mock_cost_engine,
        )

        migration = _create_mock_migration(status="pending")
        assessment_tables = [
            {"table_name": "events", "estimated_size_bytes": 1024, "columns": []}
        ]

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                orchestrator.execute_iceberg_migration(migration, assessment_tables)
            )
        finally:
            loop.close()

        # Should return True (paused, not failed)
        assert result is True
        assert migration.status == "pending_review"
        assert migration.structure_report is not None
        assert migration.cost_analysis_report is not None

    def test_execute_with_approved_plan_loads_tables(self):
        """Test that execution with approved plan proceeds to load."""
        mock_loader = MagicMock()
        load_result = LoadResult(
            total_tables=2,
            successful_tables=2,
            failed_tables=0,
            table_results=[
                TableLoadResult(table_name="events", success=True),
                TableLoadResult(table_name="users", success=True),
            ],
        )
        mock_loader.load_tables = AsyncMock(return_value=load_result)

        mock_validation = MagicMock()

        orchestrator = _create_orchestrator(
            loader=mock_loader,
            validation_service=mock_validation,
        )

        migration = _create_mock_migration(
            status="approved",
            structure_approved_at=datetime.now(timezone.utc),
            checkpoint_data={
                "iceberg_structure_plan": {
                    "tables": [
                        {"proposed_name": "events", "estimated_rows": 1000},
                        {"proposed_name": "users", "estimated_rows": 500},
                    ]
                }
            },
        )

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                orchestrator.execute_iceberg_migration(migration)
            )
        finally:
            loop.close()

        assert result is True
        assert migration.status == "completed"
        assert migration.progress_percentage == 100
        mock_loader.load_tables.assert_called_once()

    def test_execute_all_tables_fail_marks_failed(self):
        """Test that migration fails when all tables fail."""
        mock_loader = MagicMock()
        load_result = LoadResult(
            total_tables=2,
            successful_tables=0,
            failed_tables=2,
            table_results=[
                TableLoadResult(table_name="events", success=False, error_code="ICEBERG_S3_ACCESS_ERROR"),
                TableLoadResult(table_name="users", success=False, error_code="ICEBERG_S3_ACCESS_ERROR"),
            ],
        )
        mock_loader.load_tables = AsyncMock(return_value=load_result)

        orchestrator = _create_orchestrator(loader=mock_loader)

        migration = _create_mock_migration(
            status="approved",
            structure_approved_at=datetime.now(timezone.utc),
            checkpoint_data={
                "iceberg_structure_plan": {
                    "tables": [
                        {"proposed_name": "events", "estimated_rows": 1000},
                        {"proposed_name": "users", "estimated_rows": 500},
                    ]
                }
            },
        )

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                orchestrator.execute_iceberg_migration(migration)
            )
        finally:
            loop.close()

        assert result is False
        assert migration.status == "failed"
