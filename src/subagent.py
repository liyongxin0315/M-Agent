"""
Subagent Concurrent Execution System for AgentM.

This module provides a controlled environment for executing multiple
subagents concurrently. It manages resource limits, timeouts, and
result aggregation for parallel task execution.

Design Philosophy:
- Controlled concurrency: Limit parallel execution to prevent resource exhaustion
- Timeout protection: Every subagent execution has a timeout
- Isolation: Each subagent runs independently
- Result tracking: Track status and results for each execution

Architecture:
    SubagentExecutor
    ├── Semaphore (concurrency control)
    ├── ThreadPoolExecutor (CPU-bound tasks)
    ├── Task Registry (tracking)
    └── Result Aggregator (collecting results)

Execution Flow:
    1. Submit task → Get task ID
    2. Task waits in queue if at concurrency limit
    3. Task executes with timeout
    4. Result stored in registry
    5. Client can poll or await result

Example Usage:
    >>> executor = SubagentExecutor(
    ...     max_concurrent=3,
    ...     timeout_seconds=300,
    ... )
    >>> 
    >>> # Submit tasks
    >>> task_id = await executor.submit(
    ...     agent_type="research",
    ...     task="Find latest AI news",
    ... )
    >>> 
    >>> # Wait for result
    >>> result = await executor.get_result(task_id)
    >>> 
    >>> # Or submit multiple and wait for all
    >>> task_ids = await executor.submit_batch([
    ...     {"agent_type": "research", "task": "Task 1"},
    ...     {"agent_type": "analysis", "task": "Task 2"},
    ... ])
    >>> results = await executor.wait_all(task_ids)
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TaskStatus(str, Enum):
    """Task execution status.
    
    Attributes:
        PENDING: Task submitted, waiting to execute
        RUNNING: Task currently executing
        COMPLETED: Task completed successfully
        FAILED: Task failed with error
        TIMEOUT: Task exceeded timeout
        CANCELLED: Task was cancelled
    """
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class SubagentTask:
    """Represents a subagent task.
    
    Attributes:
        id: Unique task identifier
        agent_type: Type of agent to execute
        task: Task description/prompt
        status: Current execution status
        created_at: Task creation timestamp
        started_at: Execution start timestamp
        completed_at: Execution end timestamp
        result: Execution result (if completed)
        error: Error message (if failed)
        timeout_seconds: Task timeout
        metadata: Additional metadata
        retry_count: Number of retry attempts
        max_retries: Maximum retry attempts
    """
    id: str
    agent_type: str
    task: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    timeout_seconds: float = 300.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 0
    _future: Optional[asyncio.Future] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "agent_type": self.agent_type,
            "task": self.task,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "timeout_seconds": self.timeout_seconds,
            "metadata": self.metadata,
            "retry_count": self.retry_count,
        }


class SubagentError(Exception):
    """Base exception for subagent errors."""
    pass


class SubagentTimeoutError(SubagentError):
    """Raised when subagent execution times out."""
    pass


class SubagentConcurrencyError(SubagentError):
    """Raised when concurrency limit is exceeded."""
    pass


class SubagentExecutor:
    """Subagent concurrent execution manager.
    
    The executor manages a pool of subagent executions with:
    - Concurrency limiting via semaphore
    - Timeout protection for each task
    - Automatic retry on failure
    - Result tracking and retrieval
    - Resource monitoring
    
    Attributes:
        max_concurrent: Maximum parallel executions
        default_timeout: Default timeout in seconds
        max_retries: Default max retry attempts
        thread_pool_size: Size of thread pool for CPU-bound tasks
    
    Example:
        >>> executor = SubagentExecutor(
        ...     max_concurrent=5,
        ...     default_timeout=300,
        ...     agent_handler=my_agent_handler,
        ... )
        >>> 
        >>> # Execute single task
        >>> result = await executor.execute(
        ...     agent_type="research",
        ...     task="Research quantum computing",
        ... )
        >>> 
        >>> # Execute with custom timeout
        >>> result = await executor.execute(
        ...     agent_type="analysis",
        ...     task="Analyze data",
        ...     timeout_seconds=600,
        ... )
        >>> 
        >>> # Batch execute
        >>> results = await executor.execute_batch([
        ...     {"agent_type": "research", "task": "Task 1"},
        ...     {"agent_type": "research", "task": "Task 2"},
        ... ])
    """
    
    def __init__(
        self,
        max_concurrent: int = 5,
        default_timeout: float = 300.0,
        max_retries: int = 0,
        thread_pool_size: Optional[int] = None,
        agent_handler: Optional[Callable] = None,
    ):
        """Initialize subagent executor.
        
        Args:
            max_concurrent: Maximum parallel task executions
            default_timeout: Default timeout in seconds
            max_retries: Default maximum retry attempts
            thread_pool_size: Thread pool size (default: max_concurrent * 2)
            agent_handler: Function to handle agent execution
        """
        self._max_concurrent = max_concurrent
        self._default_timeout = default_timeout
        self._max_retries = max_retries
        self._thread_pool_size = thread_pool_size or max_concurrent * 2
        self._agent_handler = agent_handler
        
        # Concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._thread_pool = ThreadPoolExecutor(
            max_workers=self._thread_pool_size,
            thread_name_prefix="agentm_subagent",
        )
        
        # Task registry
        self._tasks: Dict[str, SubagentTask] = {}
        self._pending_tasks: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        
        # Statistics
        self._stats = {
            "total_submitted": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_timeout": 0,
            "total_cancelled": 0,
            "total_retries": 0,
            "current_running": 0,
        }
        
        # Background task for processing queue
        self._processor_task: Optional[asyncio.Task] = None
        
        logger.info(
            f"SubagentExecutor initialized: max_concurrent={max_concurrent}, "
            f"default_timeout={default_timeout}s"
        )
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        return {
            **self._stats,
            "max_concurrent": self._max_concurrent,
            "pending_tasks": self._pending_tasks.qsize(),
            "registered_tasks": len(self._tasks),
        }
    
    @property
    def max_concurrent(self) -> int:
        """Get maximum concurrent executions."""
        return self._max_concurrent
    
    def set_agent_handler(self, handler: Callable) -> None:
        """Set the agent handler function.
        
        Args:
            handler: Async function that takes (agent_type, task) and returns result
        """
        self._agent_handler = handler
    
    async def start_processor(self) -> None:
        """Start background task processor."""
        if self._processor_task is None:
            self._processor_task = asyncio.create_task(self._process_queue())
            logger.debug("Started background task processor")
    
    async def stop_processor(self) -> None:
        """Stop background task processor."""
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None
            logger.debug("Stopped background task processor")
    
    async def _process_queue(self) -> None:
        """Background task to process pending tasks."""
        while True:
            try:
                task = await self._pending_tasks.get()
                asyncio.create_task(self._execute_task(task))
                self._pending_tasks.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing task queue: {e}")
    
    async def submit(
        self,
        agent_type: str,
        task: str,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Submit a subagent task for execution.
        
        Args:
            agent_type: Type of agent to execute
            task: Task description/prompt
            timeout_seconds: Execution timeout (uses default if not specified)
            max_retries: Maximum retry attempts (uses default if not specified)
            metadata: Additional metadata
            
        Returns:
            Task ID for tracking
            
        Raises:
            SubagentError: If submission fails
        """
        task_id = str(uuid.uuid4())
        
        subagent_task = SubagentTask(
            id=task_id,
            agent_type=agent_type,
            task=task,
            timeout_seconds=timeout_seconds or self._default_timeout,
            max_retries=max_retries or self._max_retries,
            metadata=metadata or {},
        )
        
        async with self._lock:
            self._tasks[task_id] = subagent_task
            self._stats["total_submitted"] += 1
        
        # Add to queue for processing
        await self._pending_tasks.put(subagent_task)
        
        logger.debug(f"Submitted task {task_id}: {agent_type}")
        return task_id
    
    async def execute(
        self,
        agent_type: str,
        task: str,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute a subagent task and wait for result.
        
        Convenience method that submits and waits for completion.
        
        Args:
            agent_type: Type of agent to execute
            task: Task description/prompt
            timeout_seconds: Execution timeout
            max_retries: Maximum retry attempts
            metadata: Additional metadata
            
        Returns:
            Task result
            
        Raises:
            SubagentTimeoutError: If execution times out
            SubagentError: If execution fails
        """
        task_id = await self.submit(
            agent_type=agent_type,
            task=task,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            metadata=metadata,
        )
        
        result = await self.wait_for_task(task_id)
        
        if result.status == TaskStatus.FAILED:
            raise SubagentError(f"Task failed: {result.error}")
        elif result.status == TaskStatus.TIMEOUT:
            raise SubagentTimeoutError(f"Task timed out after {timeout_seconds}s")
        elif result.status == TaskStatus.CANCELLED:
            raise SubagentError("Task was cancelled")
        
        return result.result
    
    async def _execute_task(self, task: SubagentTask) -> None:
        """Execute a single task with concurrency control.
        
        Args:
            task: Task to execute
        """
        async with self._semaphore:
            self._stats["current_running"] += 1
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now().isoformat()
            
            logger.debug(f"Executing task {task.id}: {task.agent_type}")
            
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    self._run_agent(task.agent_type, task.task),
                    timeout=task.timeout_seconds,
                )
                
                task.status = TaskStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.now().isoformat()
                self._stats["total_completed"] += 1
                
                logger.debug(f"Task {task.id} completed successfully")
                
            except asyncio.TimeoutError:
                task.status = TaskStatus.TIMEOUT
                task.error = f"Timeout after {task.timeout_seconds}s"
                task.completed_at = datetime.now().isoformat()
                self._stats["total_timeout"] += 1
                
                logger.warning(f"Task {task.id} timed out")
                
                # Retry if attempts remaining
                if task.retry_count < task.max_retries:
                    await self._retry_task(task)
                
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.completed_at = datetime.now().isoformat()
                self._stats["total_failed"] += 1
                
                logger.error(f"Task {task.id} failed: {e}")
                
                # Retry if attempts remaining
                if task.retry_count < task.max_retries:
                    await self._retry_task(task)
            
            finally:
                self._stats["current_running"] -= 1
                
                # Resolve future if set
                if task._future and not task._future.done():
                    task._future.set_result(task)
    
    async def _run_agent(self, agent_type: str, task: str) -> Any:
        """Run the actual agent.
        
        Args:
            agent_type: Type of agent
            task: Task description
            
        Returns:
            Agent result
            
        Raises:
            SubagentError: If no handler is configured
        """
        if not self._agent_handler:
            # Default mock implementation
            await asyncio.sleep(0.1)  # Simulate work
            return {"agent_type": agent_type, "task": task, "mock": True}
        
        # Call handler (can be sync or async)
        if asyncio.iscoroutinefunction(self._agent_handler):
            return await self._agent_handler(agent_type, task)
        else:
            # Run in thread pool for sync handlers
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self._thread_pool,
                self._agent_handler,
                agent_type,
                task,
            )
    
    async def _retry_task(self, task: SubagentTask) -> None:
        """Retry a failed/timed out task.
        
        Args:
            task: Task to retry
        """
        task.retry_count += 1
        task.status = TaskStatus.PENDING
        task.started_at = None
        task.completed_at = None
        task.error = None
        task.result = None
        
        self._stats["total_retries"] += 1
        logger.info(f"Retrying task {task.id} (attempt {task.retry_count})")
        
        await self._pending_tasks.put(task)
    
    async def wait_for_task(
        self,
        task_id: str,
        timeout: Optional[float] = None,
    ) -> SubagentTask:
        """Wait for a task to complete.
        
        Args:
            task_id: Task ID to wait for
            timeout: Maximum wait time (None = use task timeout)
            
        Returns:
            Completed task with result/error
            
        Raises:
            KeyError: If task ID not found
        """
        async with self._lock:
            if task_id not in self._tasks:
                raise KeyError(f"Task not found: {task_id}")
            
            task = self._tasks[task_id]
            
            # Create future if not exists
            if task._future is None:
                task._future = asyncio.get_event_loop().create_future()
        
        # Wait for completion
        if task._future:
            try:
                await asyncio.wait_for(task._future, timeout=timeout)
            except asyncio.TimeoutError:
                pass  # Return current status
        
        return task
    
    async def wait_all(
        self,
        task_ids: List[str],
        timeout: Optional[float] = None,
    ) -> List[SubagentTask]:
        """Wait for multiple tasks to complete.
        
        Args:
            task_ids: List of task IDs
            timeout: Maximum wait time for all tasks
            
        Returns:
            List of completed tasks
        """
        tasks = [asyncio.create_task(self.wait_for_task(tid)) for tid in task_ids]
        
        if timeout:
            done, pending = await asyncio.wait(
                tasks,
                timeout=timeout,
                return_when=asyncio.ALL_COMPLETED,
            )
            # Cancel pending
            for p in pending:
                p.cancel()
        else:
            done = await asyncio.gather(*tasks, return_exceptions=True)
        
        return [t for t in done if isinstance(t, SubagentTask)]
    
    async def get_result(self, task_id: str) -> Optional[Any]:
        """Get result of completed task.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task result, or None if not completed
        """
        async with self._lock:
            task = self._tasks.get(task_id)
        
        if task and task.status == TaskStatus.COMPLETED:
            return task.result
        return None
    
    async def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get status of task.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task status, or None if not found
        """
        async with self._lock:
            task = self._tasks.get(task_id)
        
        return task.status if task else None
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending/running task.
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if cancelled, False if not found or already completed
        """
        async with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMEOUT):
                return False
            
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now().isoformat()
            self._stats["total_cancelled"] += 1
            
            # Resolve future
            if task._future and not task._future.done():
                task._future.set_result(task)
        
        logger.debug(f"Cancelled task {task_id}")
        return True
    
    async def cancel_all(self) -> int:
        """Cancel all pending/running tasks.
        
        Returns:
            Number of tasks cancelled
        """
        async with self._lock:
            count = 0
            for task in self._tasks.values():
                if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = datetime.now().isoformat()
                    count += 1
            
            self._stats["total_cancelled"] += count
        
        logger.info(f"Cancelled {count} tasks")
        return count
    
    def get_task(self, task_id: str) -> Optional[SubagentTask]:
        """Get task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task if found, None otherwise
        """
        return self._tasks.get(task_id)
    
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        agent_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[SubagentTask]:
        """List tasks with optional filtering.
        
        Args:
            status: Filter by status
            agent_type: Filter by agent type
            limit: Maximum results
            
        Returns:
            List of matching tasks
        """
        tasks = list(self._tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        if agent_type:
            tasks = [t for t in tasks if t.agent_type == agent_type]
        
        # Sort by creation time (newest first)
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        return tasks[:limit]
    
    async def cleanup(self) -> None:
        """Cleanup executor resources.
        
        Cancels all pending tasks and shuts down thread pool.
        """
        logger.info("Cleaning up SubagentExecutor")
        
        # Cancel all tasks
        await self.cancel_all()
        
        # Stop processor
        await self.stop_processor()
        
        # Shutdown thread pool
        self._thread_pool.shutdown(wait=False)
        
        logger.debug("SubagentExecutor cleanup complete")
    
    def get_active_count(self) -> int:
        """Get number of currently running tasks.
        
        Returns:
            Number of running tasks
        """
        return self._stats["current_running"]
    
    def get_queue_size(self) -> int:
        """Get number of pending tasks in queue.
        
        Returns:
            Queue size
        """
        return self._pending_tasks.qsize()


__all__ = [
    "SubagentExecutor",
    "SubagentTask",
    "TaskStatus",
    "SubagentError",
    "SubagentTimeoutError",
    "SubagentConcurrencyError",
]
