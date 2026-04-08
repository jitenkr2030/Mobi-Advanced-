"""
Background Jobs Module
Provides Celery-like async task processing for the Mobi Invoice application
"""

import os
import json
import time
import threading
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Callable, Optional, List
from enum import Enum
from dataclasses import dataclass, asdict
from queue import Queue, PriorityQueue
from concurrent.futures import ThreadPoolExecutor
from flask import current_app
from app import db, BackgroundJob

logger = logging.getLogger(__name__)

class JobStatus(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class JobPriority(Enum):
    LOW = 3
    MEDIUM = 2
    HIGH = 1
    CRITICAL = 0

class JobType(Enum):
    BACKUP_DATABASE = "BACKUP_DATABASE"
    SEND_EMAIL = "SEND_EMAIL"
    PROCESS_REPORT = "PROCESS_REPORT"
    CLEANUP_SESSIONS = "CLEANUP_SESSIONS"
    UPDATE_CACHE = "UPDATE_CACHE"
    SEND_NOTIFICATION = "SEND_NOTIFICATION"
    GENERATE_INVOICE = "GENERATE_INVOICE"
    PROCESS_RECURRING = "PROCESS_RECURRING"
    SEND_REMINDERS = "SEND_REMINDERS"
    CLEANUP_CACHE = "CLEANUP_CACHE"

@dataclass
class JobResult:
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0

class JobTask:
    """Represents a background job task"""
    
    def __init__(self, job_id: int, job_type: JobType, payload: Dict[str, Any], 
                 priority: JobPriority = JobPriority.MEDIUM, max_retries: int = 3):
        self.job_id = job_id
        self.job_type = job_type
        self.payload = payload
        self.priority = priority
        self.max_retries = max_retries
        self.retry_count = 0
        self.created_at = datetime.utcnow()
    
    def __lt__(self, other):
        """For priority queue ordering (lower priority value = higher priority)"""
        return self.priority.value < other.priority.value

class JobProcessor:
    """Base class for job processors"""
    
    def process(self, job: JobTask) -> JobResult:
        """Process the job - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement process method")

class DatabaseBackupProcessor(JobProcessor):
    """Processor for database backup jobs"""
    
    def process(self, job: JobTask) -> JobResult:
        try:
            start_time = time.time()
            
            backup_type = job.payload.get('type', 'FULL')
            backup_path = job.payload.get('path', f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
            
            # Perform backup
            import shutil
            shutil.copy2('mobi_invoice.db', backup_path)
            
            # Calculate checksum
            import hashlib
            with open(backup_path, 'rb') as f:
                checksum = hashlib.sha256(f.read()).hexdigest()
            
            # Get file size
            file_size = os.path.getsize(backup_path)
            
            execution_time = time.time() - start_time
            
            return JobResult(
                success=True,
                result={
                    'backup_path': backup_path,
                    'backup_type': backup_type,
                    'file_size': file_size,
                    'checksum': checksum
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            return JobResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time if 'start_time' in locals() else 0.0
            )

class EmailProcessor(JobProcessor):
    """Processor for email sending jobs"""
    
    def process(self, job: JobTask) -> JobResult:
        try:
            start_time = time.time()
            
            to = job.payload.get('to')
            subject = job.payload.get('subject')
            body = job.payload.get('body')
            template = job.payload.get('template')
            
            # Simulate email sending (in production, integrate with actual email service)
            logger.info(f"Sending email to {to}: {subject}")
            time.sleep(0.1)  # Simulate email sending time
            
            execution_time = time.time() - start_time
            
            return JobResult(
                success=True,
                result={
                    'to': to,
                    'subject': subject,
                    'sent_at': datetime.utcnow().isoformat(),
                    'message_id': f"msg_{int(time.time())}"
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            return JobResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time if 'start_time' in locals() else 0.0
            )

class ReportProcessor(JobProcessor):
    """Processor for report generation jobs"""
    
    def process(self, job: JobTask) -> JobResult:
        try:
            start_time = time.time()
            
            report_type = job.payload.get('report_type')
            filters = job.payload.get('filters', {})
            format_type = job.payload.get('format', 'pdf')
            
            # Simulate report generation
            logger.info(f"Generating {report_type} report in {format_type} format")
            time.sleep(2.0)  # Simulate report generation time
            
            report_url = f"/reports/{report_type}_{int(time.time())}.{format_type}"
            
            execution_time = time.time() - start_time
            
            return JobResult(
                success=True,
                result={
                    'report_type': report_type,
                    'report_url': report_url,
                    'format': format_type,
                    'generated_at': datetime.utcnow().isoformat(),
                    'filters': filters
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            return JobResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time if 'start_time' in locals() else 0.0
            )

class SessionCleanupProcessor(JobProcessor):
    """Processor for session cleanup jobs"""
    
    def process(self, job: JobTask) -> JobResult:
        try:
            start_time = time.time()
            
            from app import UserSession
            
            # Delete expired sessions
            expired_sessions = UserSession.query.filter(
                UserSession.expires_at < datetime.utcnow()
            ).all()
            
            count = 0
            for session in expired_sessions:
                db.session.delete(session)
                count += 1
            
            db.session.commit()
            
            execution_time = time.time() - start_time
            
            return JobResult(
                success=True,
                result={
                    'cleaned_sessions': count,
                    'cleaned_at': datetime.utcnow().isoformat()
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            db.session.rollback()
            return JobResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time if 'start_time' in locals() else 0.0
            )

class NotificationProcessor(JobProcessor):
    """Processor for notification jobs"""
    
    def process(self, job: JobTask) -> JobResult:
        try:
            start_time = time.time()
            
            from app import Notification
            
            user_id = job.payload.get('user_id')
            title = job.payload.get('title')
            message = job.payload.get('message')
            notification_type = job.payload.get('type', 'INFO')
            
            # Create notification
            notification = Notification(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type
            )
            
            db.session.add(notification)
            db.session.commit()
            
            execution_time = time.time() - start_time
            
            return JobResult(
                success=True,
                result={
                    'notification_id': notification.id,
                    'user_id': user_id,
                    'created_at': notification.created_at.isoformat()
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            db.session.rollback()
            return JobResult(
                success=False,
                error=str(e),
                execution_time=time.time() - start_time if 'start_time' in locals() else 0.0
            )

class BackgroundJobManager:
    """Manages background job processing"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.job_queue = PriorityQueue()
        self.running_jobs: Dict[int, JobTask] = {}
        self.processors: Dict[JobType, JobProcessor] = {}
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.is_running = False
        self.worker_thread: Optional[threading.Thread] = None
        
        # Register default processors
        self._register_default_processors()
    
    def _register_default_processors(self):
        """Register default job processors"""
        self.processors[JobType.BACKUP_DATABASE] = DatabaseBackupProcessor()
        self.processors[JobType.SEND_EMAIL] = EmailProcessor()
        self.processors[JobType.PROCESS_REPORT] = ReportProcessor()
        self.processors[JobType.CLEANUP_SESSIONS] = SessionCleanupProcessor()
        self.processors[JobType.SEND_NOTIFICATION] = NotificationProcessor()
    
    def register_processor(self, job_type: JobType, processor: JobProcessor):
        """Register a custom job processor"""
        self.processors[job_type] = processor
    
    def enqueue_job(self, job_type: JobType, payload: Dict[str, Any], 
                   priority: JobPriority = JobPriority.MEDIUM, 
                   scheduled_at: Optional[datetime] = None,
                   max_retries: int = 3) -> int:
        """Enqueue a new background job"""
        
        # Create job record in database
        job = BackgroundJob(
            job_type=job_type.value,
            status=JobStatus.PENDING.value,
            priority=priority.value,
            payload=json.dumps(payload),
            max_attempts=max_retries,
            scheduled_at=scheduled_at or datetime.utcnow()
        )
        
        db.session.add(job)
        db.session.commit()
        
        # Create job task
        job_task = JobTask(
            job_id=job.id,
            job_type=job_type,
            payload=payload,
            priority=priority,
            max_retries=max_retries
        )
        
        # Add to queue
        self.job_queue.put(job_task)
        
        logger.info(f"Enqueued job {job.id} of type {job_type.value}")
        return job.id
    
    def start(self):
        """Start the job processor"""
        if self.is_running:
            return
        
        self.is_running = True
        self.worker_thread = threading.Thread(target=self._process_jobs, daemon=True)
        self.worker_thread.start()
        logger.info("Background job manager started")
    
    def stop(self):
        """Stop the job processor"""
        self.is_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        self.executor.shutdown(wait=True)
        logger.info("Background job manager stopped")
    
    def _process_jobs(self):
        """Main job processing loop"""
        while self.is_running:
            try:
                # Get job from queue (with timeout to allow checking is_running)
                try:
                    job_task = self.job_queue.get(timeout=1.0)
                except:
                    continue
                
                # Check if job is scheduled for future
                if job_task.created_at > datetime.utcnow():
                    # Re-queue for later
                    self.job_queue.put(job_task)
                    time.sleep(1)
                    continue
                
                # Process job
                self.executor.submit(self._execute_job, job_task)
                
            except Exception as e:
                logger.error(f"Error in job processing loop: {e}")
                time.sleep(1)
    
    def _execute_job(self, job_task: JobTask):
        """Execute a single job"""
        job_id = job_task.job_id
        
        try:
            # Get job from database
            job = BackgroundJob.query.get(job_id)
            if not job:
                logger.error(f"Job {job_id} not found in database")
                return
            
            # Update job status to running
            job.status = JobStatus.RUNNING.value
            job.started_at = datetime.utcnow()
            db.session.commit()
            
            # Get processor
            processor = self.processors.get(job_task.job_type)
            if not processor:
                raise ValueError(f"No processor found for job type {job_task.job_type.value}")
            
            # Execute job
            result = processor.process(job_task)
            
            # Update job with result
            if result.success:
                job.status = JobStatus.COMPLETED.value
                job.result = json.dumps(result.result) if result.result else None
                logger.info(f"Job {job_id} completed successfully")
            else:
                job_task.retry_count += 1
                job.attempts = job_task.retry_count
                
                if job_task.retry_count < job_task.max_retries:
                    # Retry job
                    job.status = JobStatus.PENDING.value
                    job.error = result.error
                    job.scheduled_at = datetime.utcnow() + timedelta(minutes=2 ** job_task.retry_count)
                    
                    # Re-queue for retry
                    self.job_queue.put(job_task)
                    logger.warning(f"Job {job_id} failed, retrying ({job_task.retry_count}/{job_task.max_retries}): {result.error}")
                else:
                    # Mark as failed
                    job.status = JobStatus.FAILED.value
                    job.error = result.error
                    logger.error(f"Job {job_id} failed permanently: {result.error}")
            
            job.completed_at = datetime.utcnow()
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Unexpected error executing job {job_id}: {e}")
            logger.error(traceback.format_exc())
            
            try:
                job = BackgroundJob.query.get(job_id)
                if job:
                    job.status = JobStatus.FAILED.value
                    job.error = str(e)
                    job.completed_at = datetime.utcnow()
                    db.session.commit()
            except Exception as db_error:
                logger.error(f"Failed to update job status: {db_error}")
                db.session.rollback()
        
        finally:
            # Remove from running jobs
            self.running_jobs.pop(job_id, None)
    
    def get_job_status(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get job status"""
        job = BackgroundJob.query.get(job_id)
        if not job:
            return None
        
        return {
            'id': job.id,
            'job_type': job.job_type,
            'status': job.status,
            'priority': job.priority,
            'payload': json.loads(job.payload) if job.payload else None,
            'result': json.loads(job.result) if job.result else None,
            'error': job.error,
            'attempts': job.attempts,
            'max_attempts': job.max_attempts,
            'created_at': job.created_at.isoformat(),
            'scheduled_at': job.scheduled_at.isoformat(),
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None
        }
    
    def get_jobs(self, status: Optional[JobStatus] = None, 
                job_type: Optional[JobType] = None,
                limit: int = 50) -> List[Dict[str, Any]]:
        """Get list of jobs"""
        query = BackgroundJob.query
        
        if status:
            query = query.filter_by(status=status.value)
        if job_type:
            query = query.filter_by(job_type=job_type.value)
        
        jobs = query.order_by(BackgroundJob.created_at.desc()).limit(limit).all()
        
        return [self.get_job_status(job.id) for job in jobs]
    
    def cancel_job(self, job_id: int) -> bool:
        """Cancel a job"""
        job = BackgroundJob.query.get(job_id)
        if not job or job.status not in [JobStatus.PENDING.value, JobStatus.RUNNING.value]:
            return False
        
        job.status = JobStatus.CANCELLED.value
        job.completed_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Cancelled job {job_id}")
        return True
    
    def retry_job(self, job_id: int) -> bool:
        """Retry a failed job"""
        job = BackgroundJob.query.get(job_id)
        if not job or job.status != JobStatus.FAILED.value:
            return False
        
        job.status = JobStatus.PENDING.value
        job.error = None
        job.attempts = 0
        job.scheduled_at = datetime.utcnow()
        job.started_at = None
        job.completed_at = None
        db.session.commit()
        
        # Re-queue the job
        payload = json.loads(job.payload) if job.payload else {}
        priority = JobPriority(job.priority)
        job_type = JobType(job.job_type)
        
        job_task = JobTask(
            job_id=job.id,
            job_type=job_type,
            payload=payload,
            priority=priority,
            max_retries=job.max_attempts
        )
        
        self.job_queue.put(job_task)
        
        logger.info(f"Retrying job {job_id}")
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get job processing statistics"""
        stats = {
            'pending': BackgroundJob.query.filter_by(status=JobStatus.PENDING.value).count(),
            'running': BackgroundJob.query.filter_by(status=JobStatus.RUNNING.value).count(),
            'completed': BackgroundJob.query.filter_by(status=JobStatus.COMPLETED.value).count(),
            'failed': BackgroundJob.query.filter_by(status=JobStatus.FAILED.value).count(),
            'cancelled': BackgroundJob.query.filter_by(status=JobStatus.CANCELLED.value).count(),
            'queue_size': self.job_queue.qsize(),
            'running_jobs': len(self.running_jobs),
            'max_workers': self.max_workers
        }
        
        return stats

# Global job manager instance
job_manager = BackgroundJobManager()

# Convenience functions
def enqueue_job(job_type: JobType, payload: Dict[str, Any], 
               priority: JobPriority = JobPriority.MEDIUM) -> int:
    """Enqueue a background job"""
    return job_manager.enqueue_job(job_type, payload, priority)

def get_job_status(job_id: int) -> Optional[Dict[str, Any]]:
    """Get job status"""
    return job_manager.get_job_status(job_id)

# Scheduled tasks
class TaskScheduler:
    """Schedules recurring tasks"""
    
    def __init__(self, job_manager: BackgroundJobManager):
        self.job_manager = job_manager
        self.is_running = False
        self.scheduler_thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the task scheduler"""
        if self.is_running:
            return
        
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._schedule_loop, daemon=True)
        self.scheduler_thread.start()
        logger.info("Task scheduler started")
    
    def stop(self):
        """Stop the task scheduler"""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        logger.info("Task scheduler stopped")
    
    def _schedule_loop(self):
        """Main scheduling loop"""
        while self.is_running:
            try:
                current_time = datetime.utcnow()
                
                # Schedule session cleanup (every hour)
                if current_time.minute == 0:
                    self.job_manager.enqueue_job(
                        JobType.CLEANUP_SESSIONS,
                        {},
                        JobPriority.LOW
                    )
                
                # Schedule cache cleanup (every 6 hours)
                if current_time.hour % 6 == 0 and current_time.minute == 0:
                    self.job_manager.enqueue_job(
                        JobType.CLEANUP_CACHE,
                        {},
                        JobPriority.LOW
                    )
                
                # Sleep for a minute
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)

# Initialize background job system
def initialize_background_jobs():
    """Initialize background job system"""
    logger.info("Initializing background job system...")
    
    # Start job manager
    job_manager.start()
    
    # Start task scheduler
    scheduler = TaskScheduler(job_manager)
    scheduler.start()
    
    logger.info("Background job system initialized")

if __name__ == "__main__":
    # Test background job system
    initialize_background_jobs()
    
    # Test enqueueing a job
    job_id = enqueue_job(
        JobType.SEND_EMAIL,
        {
            'to': 'test@example.com',
            'subject': 'Test Email',
            'body': 'This is a test email from the background job system.'
        }
    )
    
    print(f"Enqueued job with ID: {job_id}")
    
    # Wait a bit and check status
    time.sleep(3)
    status = get_job_status(job_id)
    print(f"Job status: {status}")
    
    # Get stats
    stats = job_manager.get_stats()
    print(f"Job manager stats: {stats}")