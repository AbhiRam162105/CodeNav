"""
Task management for background agent execution.
"""
import logging
import threading
import uuid
from typing import Optional, Dict, List, Callable
from datetime import datetime
from queue import Queue
import time

logger = logging.getLogger(__name__)


class AgentTask:
    """Represents a background agent task."""

    def __init__(
        self,
        task_id: str,
        description: str,
        session_id: Optional[str] = None
    ):
        """
        Initialize agent task.

        Args:
            task_id: Unique task ID
            description: Task description
            session_id: Associated session ID (optional)
        """
        self.task_id = task_id
        self.description = description
        self.session_id = session_id
        self.status = "pending"  # pending, running, complete, error, cancelled
        self.created_at = datetime.utcnow().isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.result: Optional[Dict] = None
        self.error: Optional[str] = None
        self.progress = 0  # 0-100
        self.current_step: Optional[str] = None
        self._cancel_event = threading.Event()

    def start(self):
        """Mark task as started."""
        self.status = "running"
        self.started_at = datetime.utcnow().isoformat()

    def update_progress(self, progress: int, step: Optional[str] = None):
        """
        Update task progress.

        Args:
            progress: Progress percentage (0-100)
            step: Current step description
        """
        self.progress = max(0, min(100, progress))
        if step:
            self.current_step = step

    def complete(self, result: Dict):
        """
        Mark task as complete.

        Args:
            result: Task result
        """
        self.status = "complete"
        self.result = result
        self.completed_at = datetime.utcnow().isoformat()
        self.progress = 100

    def fail(self, error: str):
        """
        Mark task as failed.

        Args:
            error: Error message
        """
        self.status = "error"
        self.error = error
        self.completed_at = datetime.utcnow().isoformat()

    def cancel(self):
        """Cancel the task."""
        self.status = "cancelled"
        self.completed_at = datetime.utcnow().isoformat()
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        """Check if task is cancelled."""
        return self._cancel_event.is_set()

    def to_dict(self) -> Dict:
        """Convert task to dictionary."""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "session_id": self.session_id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress": self.progress,
            "current_step": self.current_step,
            "result": self.result,
            "error": self.error
        }


class TaskManager:
    """Manages background agent tasks."""

    def __init__(self, max_concurrent: int = 3):
        """
        Initialize task manager.

        Args:
            max_concurrent: Maximum concurrent tasks
        """
        self.max_concurrent = max_concurrent
        self.tasks: Dict[str, AgentTask] = {}
        self.task_queue: Queue = Queue()
        self._workers: List[threading.Thread] = []
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Start worker threads
        for i in range(max_concurrent):
            worker = threading.Thread(
                target=self._worker,
                name=f"TaskWorker-{i}",
                daemon=True
            )
            worker.start()
            self._workers.append(worker)

        logger.info(f"Task manager started with {max_concurrent} workers")

    def create_task(
        self,
        description: str,
        session_id: Optional[str] = None
    ) -> AgentTask:
        """
        Create a new task.

        Args:
            description: Task description
            session_id: Associated session ID

        Returns:
            AgentTask
        """
        task_id = str(uuid.uuid4())
        task = AgentTask(task_id, description, session_id)

        with self._lock:
            self.tasks[task_id] = task

        logger.info(f"Created task {task_id}: {description}")

        return task

    def submit_task(
        self,
        task_id: str,
        execute_fn: Callable[[AgentTask], Dict]
    ):
        """
        Submit a task for execution.

        Args:
            task_id: Task ID
            execute_fn: Function to execute (takes AgentTask, returns result dict)
        """
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        if task.status != "pending":
            raise ValueError(f"Task {task_id} already started")

        # Add to queue
        self.task_queue.put((task, execute_fn))

        logger.info(f"Submitted task {task_id} to queue")

    def get_task(self, task_id: str) -> Optional[AgentTask]:
        """
        Get a task by ID.

        Args:
            task_id: Task ID

        Returns:
            AgentTask or None
        """
        return self.tasks.get(task_id)

    def list_tasks(
        self,
        status: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> List[Dict]:
        """
        List tasks.

        Args:
            status: Filter by status (optional)
            session_id: Filter by session ID (optional)

        Returns:
            List of task summaries
        """
        tasks = []

        with self._lock:
            for task in self.tasks.values():
                # Apply filters
                if status and task.status != status:
                    continue

                if session_id and task.session_id != session_id:
                    continue

                tasks.append(task.to_dict())

        # Sort by created_at (most recent first)
        tasks.sort(key=lambda t: t["created_at"], reverse=True)

        return tasks

    def cancel_task(self, task_id: str):
        """
        Cancel a task.

        Args:
            task_id: Task ID
        """
        task = self.get_task(task_id)
        if task:
            task.cancel()
            logger.info(f"Cancelled task {task_id}")

    def cleanup_old_tasks(self, max_age_hours: int = 24):
        """
        Clean up old completed/failed tasks.

        Args:
            max_age_hours: Maximum age in hours
        """
        current_time = datetime.utcnow()
        cutoff_time = current_time.timestamp() - (max_age_hours * 3600)

        to_remove = []

        with self._lock:
            for task_id, task in self.tasks.items():
                # Only remove completed/error/cancelled tasks
                if task.status not in ["complete", "error", "cancelled"]:
                    continue

                # Check age
                if task.completed_at:
                    completed_time = datetime.fromisoformat(task.completed_at)
                    if completed_time.timestamp() < cutoff_time:
                        to_remove.append(task_id)

            # Remove old tasks
            for task_id in to_remove:
                del self.tasks[task_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")

    def _worker(self):
        """Worker thread that executes tasks."""
        logger.info(f"Task worker {threading.current_thread().name} started")

        while not self._stop_event.is_set():
            try:
                # Get task from queue (with timeout)
                task, execute_fn = self.task_queue.get(timeout=1)

                # Execute task
                logger.info(f"Executing task {task.task_id}")

                task.start()

                try:
                    result = execute_fn(task)
                    task.complete(result)

                    logger.info(f"Task {task.task_id} completed successfully")

                except Exception as e:
                    error_msg = str(e)
                    task.fail(error_msg)

                    logger.error(f"Task {task.task_id} failed: {error_msg}", exc_info=True)

            except:
                # Queue timeout or other error - just continue
                pass

        logger.info(f"Task worker {threading.current_thread().name} stopped")

    def shutdown(self):
        """Shutdown the task manager."""
        logger.info("Shutting down task manager")

        self._stop_event.set()

        # Wait for workers
        for worker in self._workers:
            worker.join(timeout=5)

        logger.info("Task manager shutdown complete")

    def __del__(self):
        """Cleanup on deletion."""
        self.shutdown()


# Global task manager instance
_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """Get the global task manager instance."""
    global _task_manager

    if _task_manager is None:
        _task_manager = TaskManager()

    return _task_manager
