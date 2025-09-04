"""Simple job scheduler implementation."""

import asyncio
import threading
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

from src.logging_conf import get_logger
from src.settings import settings
from .cron import CronExpression

logger = get_logger("scheduler")


class JobStatus(str, Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobExecution:
    """Record of a job execution."""
    id: str
    job_id: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    status: JobStatus = JobStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class ScheduledJob:
    """A scheduled job configuration."""
    id: str
    name: str
    cron_expression: str
    function: Callable
    kwargs: Dict[str, Any]
    enabled: bool = True
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class JobScheduler:
    """Simple cron-based job scheduler."""
    
    def __init__(self):
        """Initialize the scheduler."""
        self._jobs: Dict[str, ScheduledJob] = {}
        self._executions: List[JobExecution] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.check_interval = 60  # Check every minute
        
    def add_job(
        self,
        name: str,
        cron_expression: str,
        function: Callable,
        kwargs: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
        enabled: bool = True
    ) -> str:
        """Add a new scheduled job.
        
        Args:
            name: Human-readable job name
            cron_expression: Cron expression for scheduling
            function: Function to execute
            kwargs: Keyword arguments for function
            job_id: Optional job ID (auto-generated if not provided)
            enabled: Whether job is enabled
            
        Returns:
            Job ID
        """
        if job_id is None:
            job_id = str(uuid.uuid4())
        
        if kwargs is None:
            kwargs = {}
        
        # Validate cron expression
        try:
            cron = CronExpression(cron_expression)
        except Exception as e:
            raise ValueError(f"Invalid cron expression '{cron_expression}': {e}")
        
        # Calculate next run time
        next_run = cron.get_next_execution() if enabled else None
        
        job = ScheduledJob(
            id=job_id,
            name=name,
            cron_expression=cron_expression,
            function=function,
            kwargs=kwargs,
            enabled=enabled,
            next_run=next_run
        )
        
        self._jobs[job_id] = job
        logger.info("Job added", job_id=job_id, name=name, cron=cron_expression, next_run=next_run)
        
        return job_id
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job.
        
        Args:
            job_id: Job ID to remove
            
        Returns:
            True if job was removed, False if not found
        """
        if job_id in self._jobs:
            job = self._jobs.pop(job_id)
            logger.info("Job removed", job_id=job_id, name=job.name)
            return True
        return False
    
    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    def list_jobs(self) -> List[ScheduledJob]:
        """List all jobs."""
        return list(self._jobs.values())
    
    def enable_job(self, job_id: str) -> bool:
        """Enable a job."""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job.enabled = True
            # Calculate next run time
            cron = CronExpression(job.cron_expression)
            job.next_run = cron.get_next_execution()
            logger.info("Job enabled", job_id=job_id, next_run=job.next_run)
            return True
        return False
    
    def disable_job(self, job_id: str) -> bool:
        """Disable a job."""
        if job_id in self._jobs:
            job = self._jobs[job_id]
            job.enabled = False
            job.next_run = None
            logger.info("Job disabled", job_id=job_id)
            return True
        return False
    
    def update_job_schedule(self, job_id: str, cron_expression: str) -> bool:
        """Update job's cron schedule."""
        if job_id not in self._jobs:
            return False
        
        try:
            cron = CronExpression(cron_expression)
        except Exception as e:
            logger.error("Invalid cron expression", job_id=job_id, expression=cron_expression, error=str(e))
            return False
        
        job = self._jobs[job_id]
        job.cron_expression = cron_expression
        
        if job.enabled:
            job.next_run = cron.get_next_execution()
        
        logger.info("Job schedule updated", job_id=job_id, cron=cron_expression, next_run=job.next_run)
        return True
    
    def start(self):
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler is already running")
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._thread.start()
        
        logger.info("Scheduler started", check_interval=self.check_interval)
    
    def stop(self):
        """Stop the scheduler."""
        if not self._running:
            return
        
        logger.info("Stopping scheduler")
        self._running = False
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        
        logger.info("Scheduler stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop running in background thread."""
        logger.info("Scheduler loop started")
        
        while not self._stop_event.wait(self.check_interval):
            try:
                self._check_and_run_jobs()
            except Exception as e:
                logger.error("Error in scheduler loop", error=str(e))
        
        logger.info("Scheduler loop ended")
    
    def _check_and_run_jobs(self):
        """Check for jobs that should run and execute them."""
        now = datetime.now().replace(second=0, microsecond=0)  # Round to minute
        
        for job_id, job in self._jobs.items():
            if not job.enabled or not job.next_run:
                continue
            
            if now >= job.next_run:
                logger.info("Executing scheduled job", job_id=job_id, name=job.name)
                
                # Execute job asynchronously
                execution_id = str(uuid.uuid4())
                execution = JobExecution(
                    id=execution_id,
                    job_id=job_id,
                    started_at=now,
                    status=JobStatus.RUNNING
                )
                self._executions.append(execution)
                
                # Run job in thread pool
                thread = threading.Thread(
                    target=self._execute_job,
                    args=(job, execution),
                    daemon=True
                )
                thread.start()
                
                # Update job's next run time
                job.last_run = now
                try:
                    cron = CronExpression(job.cron_expression)
                    job.next_run = cron.get_next_execution(now)
                    logger.debug("Job next run scheduled", job_id=job_id, next_run=job.next_run)
                except Exception as e:
                    logger.error("Failed to calculate next run", job_id=job_id, error=str(e))
                    job.enabled = False  # Disable job if cron is invalid
    
    def _execute_job(self, job: ScheduledJob, execution: JobExecution):
        """Execute a single job."""
        try:
            logger.info("Starting job execution", job_id=job.id, execution_id=execution.id)
            
            # Execute the job function
            result = job.function(**job.kwargs)
            
            # Record successful completion
            execution.status = JobStatus.COMPLETED
            execution.result = result
            execution.finished_at = datetime.now()
            
            logger.info("Job completed successfully", 
                       job_id=job.id, 
                       execution_id=execution.id,
                       duration=(execution.finished_at - execution.started_at).total_seconds())
            
        except Exception as e:
            # Record failure
            execution.status = JobStatus.FAILED
            execution.error = str(e)
            execution.finished_at = datetime.now()
            
            logger.error("Job execution failed", 
                        job_id=job.id,
                        execution_id=execution.id,
                        error=str(e))
    
    def get_job_executions(self, job_id: Optional[str] = None, limit: int = 50) -> List[JobExecution]:
        """Get job execution history.
        
        Args:
            job_id: Optional job ID to filter by
            limit: Maximum number of executions to return
            
        Returns:
            List of job executions, most recent first
        """
        executions = self._executions
        
        if job_id:
            executions = [e for e in executions if e.job_id == job_id]
        
        # Sort by start time, most recent first
        executions = sorted(executions, key=lambda e: e.started_at, reverse=True)
        
        return executions[:limit]
    
    def cleanup_old_executions(self, keep_days: int = 7):
        """Clean up old job execution records.
        
        Args:
            keep_days: Number of days of executions to keep
        """
        cutoff = datetime.now() - timedelta(days=keep_days)
        
        old_count = len(self._executions)
        self._executions = [e for e in self._executions if e.started_at >= cutoff]
        removed_count = old_count - len(self._executions)
        
        if removed_count > 0:
            logger.info("Cleaned up old executions", removed=removed_count, kept=len(self._executions))
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status."""
        total_jobs = len(self._jobs)
        enabled_jobs = sum(1 for j in self._jobs.values() if j.enabled)
        recent_executions = len([e for e in self._executions 
                               if e.started_at >= datetime.now() - timedelta(hours=24)])
        
        return {
            "running": self._running,
            "total_jobs": total_jobs,
            "enabled_jobs": enabled_jobs,
            "recent_executions_24h": recent_executions,
            "check_interval": self.check_interval
        }


# Global scheduler instance
_scheduler_instance: Optional[JobScheduler] = None


def get_scheduler() -> JobScheduler:
    """Get the global scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = JobScheduler()
    return _scheduler_instance