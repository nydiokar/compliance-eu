"""Test scheduler functionality."""

import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from src.core.scheduler import JobScheduler, ScheduledJob
from src.core.scheduler.cron import CronExpression


class TestCronExpression:
    """Test cron expression parsing."""
    
    def test_basic_cron_expressions(self):
        """Test basic cron expression parsing."""
        # Every minute
        cron = CronExpression("* * * * *")
        assert cron.expression == "* * * * *"
        
        # Daily at 9 AM
        cron = CronExpression("0 9 * * *")
        assert cron.minute == "0"
        assert cron.hour == "9"
        
        # Every Monday at 2:30 PM
        cron = CronExpression("30 14 * * 1")
        assert cron.minute == "30"
        assert cron.hour == "14"
        assert cron.weekday == "1"
    
    def test_invalid_cron_expressions(self):
        """Test invalid cron expression handling."""
        with pytest.raises(ValueError):
            CronExpression("* * *")  # Too few fields
        
        with pytest.raises(ValueError):
            CronExpression("60 * * * *")  # Invalid minute
        
        with pytest.raises(ValueError):
            CronExpression("* 25 * * *")  # Invalid hour
    
    def test_next_execution_calculation(self):
        """Test next execution time calculation."""
        # Every minute
        cron = CronExpression("* * * * *")
        now = datetime(2025, 1, 1, 12, 30, 0)
        next_run = cron.get_next_execution(now)
        assert next_run == datetime(2025, 1, 1, 12, 31, 0)
        
        # Daily at 9 AM
        cron = CronExpression("0 9 * * *")
        now = datetime(2025, 1, 1, 8, 0, 0)  # Before 9 AM
        next_run = cron.get_next_execution(now)
        assert next_run == datetime(2025, 1, 1, 9, 0, 0)
        
        now = datetime(2025, 1, 1, 10, 0, 0)  # After 9 AM
        next_run = cron.get_next_execution(now)
        assert next_run == datetime(2025, 1, 2, 9, 0, 0)  # Next day
    
    def test_should_run_at(self):
        """Test should_run_at functionality."""
        cron = CronExpression("0 9 * * *")  # Daily at 9 AM
        
        # Should run at 9:00
        assert cron.should_run_at(datetime(2025, 1, 1, 9, 0, 0))
        
        # Should not run at other times
        assert not cron.should_run_at(datetime(2025, 1, 1, 8, 0, 0))
        assert not cron.should_run_at(datetime(2025, 1, 1, 9, 1, 0))


class TestJobScheduler:
    """Test job scheduler."""
    
    def test_scheduler_initialization(self):
        """Test scheduler initialization."""
        scheduler = JobScheduler()
        assert not scheduler._running
        assert len(scheduler._jobs) == 0
    
    def test_add_job(self):
        """Test adding jobs."""
        scheduler = JobScheduler()
        
        def test_func():
            return "test result"
        
        job_id = scheduler.add_job(
            name="Test Job",
            cron_expression="0 9 * * *",
            function=test_func
        )
        
        assert job_id is not None
        assert len(scheduler._jobs) == 1
        
        job = scheduler.get_job(job_id)
        assert job is not None
        assert job.name == "Test Job"
        assert job.enabled is True
        assert job.next_run is not None
    
    def test_remove_job(self):
        """Test removing jobs."""
        scheduler = JobScheduler()
        
        def test_func():
            return "test result"
        
        job_id = scheduler.add_job("Test Job", "0 9 * * *", test_func)
        assert len(scheduler._jobs) == 1
        
        removed = scheduler.remove_job(job_id)
        assert removed is True
        assert len(scheduler._jobs) == 0
        
        # Try to remove non-existent job
        removed = scheduler.remove_job("nonexistent")
        assert removed is False
    
    def test_enable_disable_job(self):
        """Test enabling and disabling jobs."""
        scheduler = JobScheduler()
        
        def test_func():
            return "test result"
        
        job_id = scheduler.add_job("Test Job", "0 9 * * *", test_func)
        job = scheduler.get_job(job_id)
        assert job.enabled is True
        
        # Disable job
        result = scheduler.disable_job(job_id)
        assert result is True
        assert job.enabled is False
        assert job.next_run is None
        
        # Enable job
        result = scheduler.enable_job(job_id)
        assert result is True
        assert job.enabled is True
        assert job.next_run is not None
    
    def test_list_jobs(self):
        """Test listing jobs."""
        scheduler = JobScheduler()
        
        def test_func():
            return "test result"
        
        assert len(scheduler.list_jobs()) == 0
        
        job1_id = scheduler.add_job("Job 1", "0 9 * * *", test_func)
        job2_id = scheduler.add_job("Job 2", "0 10 * * *", test_func)
        
        jobs = scheduler.list_jobs()
        assert len(jobs) == 2
        assert any(job.name == "Job 1" for job in jobs)
        assert any(job.name == "Job 2" for job in jobs)
    
    def test_job_execution_mock(self):
        """Test job execution with mocked function."""
        scheduler = JobScheduler()
        
        mock_function = Mock(return_value="success")
        
        job_id = scheduler.add_job(
            name="Test Job",
            cron_expression="* * * * *",  # Every minute
            function=mock_function,
            kwargs={"param": "value"}
        )
        
        job = scheduler.get_job(job_id)
        execution = Mock()
        execution.id = "exec_123"
        execution.job_id = job_id
        execution.started_at = datetime.now()
        
        # Test job execution
        scheduler._execute_job(job, execution)
        
        # Verify mock was called with correct parameters
        mock_function.assert_called_once_with(param="value")
        assert execution.status.value == "completed"
        assert execution.result == "success"
    
    def test_get_status(self):
        """Test scheduler status."""
        scheduler = JobScheduler()
        
        def test_func():
            return "test"
        
        # Initially no jobs
        status = scheduler.get_status()
        assert status["total_jobs"] == 0
        assert status["enabled_jobs"] == 0
        assert not status["running"]
        
        # Add jobs
        scheduler.add_job("Job 1", "0 9 * * *", test_func, enabled=True)
        scheduler.add_job("Job 2", "0 10 * * *", test_func, enabled=False)
        
        status = scheduler.get_status()
        assert status["total_jobs"] == 2
        assert status["enabled_jobs"] == 1


@pytest.fixture
def mock_dataset():
    """Create a mock dataset for testing."""
    dataset = Mock()
    dataset.id = "test-dataset"
    dataset.name = "Test Dataset"
    dataset.org_id = "test-org"
    dataset.profile = "budget_execution_v1"
    dataset.schedule_cron = "0 9 * * *"
    dataset.publish_target = "ckan"
    dataset.active = True
    dataset.description = "Test dataset"
    return dataset


def test_scheduler_integration_mock():
    """Test basic scheduler integration."""
    from src.core.scheduler import get_scheduler
    
    scheduler = get_scheduler()
    assert scheduler is not None
    
    # Test adding a mock job
    def mock_job():
        return {"status": "completed", "message": "Mock job executed"}
    
    job_id = scheduler.add_job(
        name="Mock Integration Test",
        cron_expression="0 */6 * * *",  # Every 6 hours
        function=mock_job
    )
    
    assert job_id is not None
    job = scheduler.get_job(job_id)
    assert job is not None
    assert job.enabled is True
    
    # Clean up
    scheduler.remove_job(job_id)