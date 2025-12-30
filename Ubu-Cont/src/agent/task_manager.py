"""
Task Manager

Manages task queue and priorities for the AI agent.
"""

import uuid
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority levels."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class Task:
    """A task for the agent to perform."""
    description: str
    goal: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created: datetime = field(default_factory=datetime.now)
    started: Optional[datetime] = None
    completed: Optional[datetime] = None
    parent_id: Optional[str] = None
    subtasks: List['Task'] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    error: Optional[str] = None
    max_retries: int = 3
    retry_count: int = 0

    @property
    def duration(self) -> Optional[float]:
        """Task duration in seconds."""
        if self.started and self.completed:
            return (self.completed - self.started).total_seconds()
        return None

    @property
    def is_complete(self) -> bool:
        """Check if task is in a final state."""
        return self.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED)


class TaskManager:
    """
    Manages the task queue for the AI agent.

    Supports:
    - Priority-based task ordering
    - Subtask hierarchies
    - Task retry logic
    - Task history
    """

    def __init__(self, max_history: int = 100):
        """
        Initialize task manager.

        Args:
            max_history: Maximum completed tasks to keep in history
        """
        self.max_history = max_history
        self._queue: List[Task] = []
        self._current: Optional[Task] = None
        self._history: deque = deque(maxlen=max_history)

    def add_task(self, task: Task) -> str:
        """
        Add a task to the queue.

        Args:
            task: Task to add

        Returns:
            Task ID
        """
        # Insert based on priority
        insert_idx = 0
        for i, existing in enumerate(self._queue):
            if task.priority.value > existing.priority.value:
                insert_idx = i
                break
            insert_idx = i + 1

        self._queue.insert(insert_idx, task)
        logger.info(f"Added task {task.id}: {task.description[:50]}")
        return task.id

    def add_subtask(self, parent_id: str, subtask: Task) -> Optional[str]:
        """
        Add a subtask to an existing task.

        Args:
            parent_id: Parent task ID
            subtask: Subtask to add

        Returns:
            Subtask ID or None if parent not found
        """
        parent = self.get_task(parent_id)
        if parent:
            subtask.parent_id = parent_id
            parent.subtasks.append(subtask)
            return subtask.id
        return None

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID (searches queue, current, and history)."""
        # Check current
        if self._current and self._current.id == task_id:
            return self._current

        # Check queue
        for task in self._queue:
            if task.id == task_id:
                return task
            # Check subtasks
            for subtask in task.subtasks:
                if subtask.id == task_id:
                    return subtask

        # Check history
        for task in self._history:
            if task.id == task_id:
                return task

        return None

    def get_current_task(self) -> Optional[Task]:
        """Get the current task being worked on."""
        if self._current and not self._current.is_complete:
            return self._current

        # Get next from queue
        if self._queue:
            self._current = self._queue.pop(0)
            self._current.status = TaskStatus.IN_PROGRESS
            self._current.started = datetime.now()
            logger.info(f"Started task {self._current.id}")
            return self._current

        return None

    def complete_current(self, result: str = None) -> None:
        """Mark current task as completed."""
        if self._current:
            self._current.status = TaskStatus.COMPLETED
            self._current.completed = datetime.now()
            self._current.result = result
            logger.info(f"Completed task {self._current.id}")
            self._history.append(self._current)
            self._current = None

    def fail_current(self, error: str = None) -> None:
        """Mark current task as failed."""
        if self._current:
            self._current.retry_count += 1

            if self._current.retry_count < self._current.max_retries:
                # Retry - put back in queue
                self._current.status = TaskStatus.PENDING
                self._current.started = None
                self._queue.insert(0, self._current)
                logger.warning(f"Retrying task {self._current.id} "
                             f"({self._current.retry_count}/{self._current.max_retries})")
            else:
                # Max retries exceeded
                self._current.status = TaskStatus.FAILED
                self._current.completed = datetime.now()
                self._current.error = error
                logger.error(f"Failed task {self._current.id}: {error}")
                self._history.append(self._current)

            self._current = None

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if cancelled successfully
        """
        # Check current
        if self._current and self._current.id == task_id:
            self._current.status = TaskStatus.CANCELLED
            self._current.completed = datetime.now()
            self._history.append(self._current)
            self._current = None
            logger.info(f"Cancelled current task {task_id}")
            return True

        # Check queue
        for i, task in enumerate(self._queue):
            if task.id == task_id:
                task.status = TaskStatus.CANCELLED
                task.completed = datetime.now()
                self._history.append(task)
                del self._queue[i]
                logger.info(f"Cancelled queued task {task_id}")
                return True

        return False

    def clear_queue(self) -> int:
        """
        Clear all pending tasks.

        Returns:
            Number of tasks cleared
        """
        count = len(self._queue)
        for task in self._queue:
            task.status = TaskStatus.CANCELLED
            self._history.append(task)
        self._queue.clear()
        logger.info(f"Cleared {count} tasks from queue")
        return count

    def get_queue_status(self) -> Dict[str, Any]:
        """Get queue status summary."""
        return {
            'queue_length': len(self._queue),
            'current_task': self._current.id if self._current else None,
            'current_description': self._current.description[:50] if self._current else None,
            'pending_by_priority': {
                p.name: sum(1 for t in self._queue if t.priority == p)
                for p in TaskPriority
            },
            'history_count': len(self._history),
            'completed_count': sum(1 for t in self._history if t.status == TaskStatus.COMPLETED),
            'failed_count': sum(1 for t in self._history if t.status == TaskStatus.FAILED),
        }

    def get_queue(self) -> List[Task]:
        """Get all queued tasks."""
        return list(self._queue)

    def get_history(self, limit: int = 10) -> List[Task]:
        """Get recent task history."""
        return list(self._history)[-limit:]

    def reprioritize(self, task_id: str, new_priority: TaskPriority) -> bool:
        """
        Change task priority.

        Args:
            task_id: Task to reprioritize
            new_priority: New priority level

        Returns:
            True if reprioritized successfully
        """
        for i, task in enumerate(self._queue):
            if task.id == task_id:
                task.priority = new_priority
                # Remove and re-add to maintain ordering
                del self._queue[i]
                self.add_task(task)
                return True
        return False
