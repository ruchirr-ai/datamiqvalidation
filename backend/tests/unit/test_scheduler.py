"""
Unit Tests for Migration Scheduler

Tests CRON parsing, scheduling logic, and migration execution.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from services.bq_redshift_migration.scheduler import MigrationScheduler
from models.bq_redshift_migration import MigrationBQRedshift


class TestMigrationScheduler:
    """Test suite for MigrationScheduler"""
    
    @pytest.fixture
    def db_session(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def scheduler(self, db_session):
        """Create scheduler instance"""
        return MigrationScheduler(db_session)
    
    def test_calculate_next_run_daily(self, scheduler):
        """Test CRON calculation for daily schedule"""
        # Sample CRON: Daily at 2 AM
        cron_expression = "0 2 * * *"
        base_time = datetime(2026, 2, 8, 10, 0, 0)
        
        next_run = scheduler.calculate_next_run(cron_expression, base_time)
        
        # Should be next day at 2 AM
        expected = datetime(2026, 2, 9, 2, 0, 0)
        assert next_run == expected
    
    def test_calculate_next_run_hourly(self, scheduler):
        """Test CRON calculation for hourly schedule"""
        # Sample CRON: Every hour at minute 0
        cron_expression = "0 * * * *"
        base_time = datetime(2026, 2, 8, 10, 30, 0)
        
        next_run = scheduler.calculate_next_run(cron_expression, base_time)
        
        # Should be 11:00 AM same day
        expected = datetime(2026, 2, 8, 11, 0, 0)
        assert next_run == expected
    
    def test_calculate_next_run_weekly(self, scheduler):
        """Test CRON calculation for weekly schedule"""
        # Sample CRON: Every Monday at 3 AM
        cron_expression = "0 3 * * 1"
        base_time = datetime(2026, 2, 8, 10, 0, 0)  # Sunday
        
        next_run = scheduler.calculate_next_run(cron_expression, base_time)
        
        # Should be next Monday at 3 AM
        assert next_run.weekday() == 0  # Monday
        assert next_run.hour == 3
        assert next_run.minute == 0
    
    def test_calculate_next_run_invalid_cron(self, scheduler):
        """Test invalid CRON expression"""
        invalid_cron = "invalid cron"
        
        with pytest.raises(ValueError):
            scheduler.calculate_next_run(invalid_cron)
    
    def test_get_scheduled_migrations(self, scheduler, db_session):
        """Test retrieving scheduled migrations"""
        # Sample migrations
        migration1 = Mock(spec=MigrationBQRedshift)
        migration1.id = 1
        migration1.schedule_type = 'recurring'
        migration1.cron_expression = "0 2 * * *"
        migration1.schedule_enabled = True
        
        migration2 = Mock(spec=MigrationBQRedshift)
        migration2.id = 2
        migration2.schedule_type = 'recurring'
        migration2.cron_expression = "0 3 * * *"
        migration2.schedule_enabled = True
        
        # Mock query
        query_mock = Mock()
        query_mock.filter.return_value.all.return_value = [migration1, migration2]
        db_session.query.return_value = query_mock
        
        migrations = scheduler.get_scheduled_migrations()
        
        assert len(migrations) == 2
        assert migrations[0].id == 1
        assert migrations[1].id == 2
    
    def test_get_due_migrations(self, scheduler, db_session):
        """Test retrieving migrations due for execution"""
        now = datetime.utcnow()
        past_time = now - timedelta(hours=1)
        
        # Sample migration due for execution
        migration = Mock(spec=MigrationBQRedshift)
        migration.id = 1
        migration.schedule_type = 'recurring'
        migration.schedule_enabled = True
        migration.next_run_time = past_time
        migration.status = 'pending'
        
        # Mock query
        query_mock = Mock()
        query_mock.filter.return_value.all.return_value = [migration]
        db_session.query.return_value = query_mock
        
        migrations = scheduler.get_due_migrations()
        
        assert len(migrations) == 1
        assert migrations[0].id == 1
    
    @patch('services.bq_redshift_migration.scheduler.MigrationOrchestrator')
    def test_execute_scheduled_migration_success(self, mock_orchestrator, scheduler, db_session):
        """Test successful scheduled migration execution"""
        # Sample migration
        migration = Mock(spec=MigrationBQRedshift)
        migration.id = 1
        migration.cron_expression = "0 2 * * *"
        
        # Mock database query
        db_session.query.return_value.filter_by.return_value.first.return_value = migration
        
        # Mock orchestrator
        mock_orch_instance = Mock()
        mock_orch_instance.start_migration.return_value = True
        mock_orchestrator.return_value = mock_orch_instance
        
        success = scheduler.execute_scheduled_migration(1)
        
        assert success is True
        mock_orch_instance.start_migration.assert_called_once_with(1)
        db_session.commit.assert_called()
    
    @patch('services.bq_redshift_migration.scheduler.MigrationOrchestrator')
    def test_execute_scheduled_migration_failure(self, mock_orchestrator, scheduler, db_session):
        """Test failed scheduled migration execution"""
        # Sample migration
        migration = Mock(spec=MigrationBQRedshift)
        migration.id = 1
        
        # Mock database query
        db_session.query.return_value.filter_by.return_value.first.return_value = migration
        
        # Mock orchestrator failure
        mock_orch_instance = Mock()
        mock_orch_instance.start_migration.return_value = False
        mock_orchestrator.return_value = mock_orch_instance
        
        success = scheduler.execute_scheduled_migration(1)
        
        assert success is False
    
    def test_enable_schedule(self, scheduler, db_session):
        """Test enabling schedule for a migration"""
        # Sample migration
        migration = Mock(spec=MigrationBQRedshift)
        migration.id = 1
        migration.cron_expression = "0 2 * * *"
        
        # Mock database query
        db_session.query.return_value.filter_by.return_value.first.return_value = migration
        
        success = scheduler.enable_schedule(1)
        
        assert success is True
        assert migration.schedule_enabled is True
        assert migration.next_run_time is not None
        db_session.commit.assert_called()
    
    def test_enable_schedule_no_cron(self, scheduler, db_session):
        """Test enabling schedule without CRON expression"""
        # Sample migration without CRON
        migration = Mock(spec=MigrationBQRedshift)
        migration.id = 1
        migration.cron_expression = None
        
        # Mock database query
        db_session.query.return_value.filter_by.return_value.first.return_value = migration
        
        success = scheduler.enable_schedule(1)
        
        assert success is False
    
    def test_disable_schedule(self, scheduler, db_session):
        """Test disabling schedule for a migration"""
        # Sample migration
        migration = Mock(spec=MigrationBQRedshift)
        migration.id = 1
        migration.schedule_enabled = True
        
        # Mock database query
        db_session.query.return_value.filter_by.return_value.first.return_value = migration
        
        success = scheduler.disable_schedule(1)
        
        assert success is True
        assert migration.schedule_enabled is False
        db_session.commit.assert_called()
    
    def test_update_schedule(self, scheduler, db_session):
        """Test updating CRON schedule"""
        # Sample migration
        migration = Mock(spec=MigrationBQRedshift)
        migration.id = 1
        migration.cron_expression = "0 2 * * *"
        
        # Mock database query
        db_session.query.return_value.filter_by.return_value.first.return_value = migration
        
        new_cron = "0 3 * * *"
        success = scheduler.update_schedule(1, new_cron)
        
        assert success is True
        assert migration.cron_expression == new_cron
        assert migration.next_run_time is not None
        db_session.commit.assert_called()
    
    def test_process_scheduled_migrations(self, scheduler, db_session):
        """Test processing all due migrations"""
        now = datetime.utcnow()
        past_time = now - timedelta(hours=1)
        
        # Sample migrations
        migration1 = Mock(spec=MigrationBQRedshift)
        migration1.id = 1
        migration1.schedule_type = 'recurring'
        migration1.schedule_enabled = True
        migration1.next_run_time = past_time
        migration1.status = 'pending'
        migration1.cron_expression = "0 2 * * *"
        
        migration2 = Mock(spec=MigrationBQRedshift)
        migration2.id = 2
        migration2.schedule_type = 'recurring'
        migration2.schedule_enabled = True
        migration2.next_run_time = past_time
        migration2.status = 'pending'
        migration2.cron_expression = "0 3 * * *"
        
        # Mock get_due_migrations
        with patch.object(scheduler, 'get_due_migrations', return_value=[migration1, migration2]):
            with patch.object(scheduler, 'execute_scheduled_migration') as mock_execute:
                mock_execute.side_effect = [True, False]  # First succeeds, second fails
                
                stats = scheduler.process_scheduled_migrations()
        
        assert stats['total_due'] == 2
        assert stats['started'] == 1
        assert stats['failed'] == 1


# Sample payloads for integration tests
SAMPLE_CRON_EXPRESSIONS = {
    'daily_2am': "0 2 * * *",
    'hourly': "0 * * * *",
    'every_15_min': "*/15 * * * *",
    'weekly_monday': "0 3 * * 1",
    'monthly_first': "0 0 1 * *",
}

SAMPLE_MIGRATION_SCHEDULE = {
    "migration_name": "Scheduled Daily Migration",
    "pathway": "A",
    "schedule_type": "recurring",
    "cron_expression": "0 2 * * *",
    "schedule_enabled": True,
    "source_project_id": "my-gcp-project",
    "source_dataset": "production",
    "source_tables": ["users", "orders"],
    "target_cluster": "my-cluster.redshift.amazonaws.com",
    "target_database": "analytics",
    "target_schema": "public",
    "gcs_bucket": "migration-bucket",
    "gcs_path": "migrations/daily",
    "s3_bucket": "migration-s3",
    "s3_path": "migrations/daily"
}
