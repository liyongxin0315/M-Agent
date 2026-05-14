"""
Unit tests for subagent module.

Tests cover:
- Task submission and execution
- Concurrency control
- Timeout handling
- Retry mechanism
- Result tracking
"""

import asyncio
import pytest
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from subagent import (
    SubagentExecutor,
    SubagentTask,
    TaskStatus,
    SubagentError,
    SubagentTimeoutError,
)


class TestSubagentTask:
    """Tests for SubagentTask."""
    
    def test_create_task(self):
        """Test basic task creation."""
        task = SubagentTask(
            id="task-123",
            agent_type="research",
            task="Research topic",
        )
        
        assert task.id == "task-123"
        assert task.agent_type == "research"
        assert task.status == TaskStatus.PENDING
        assert task.result is None
    
    def test_task_to_dict(self):
        """Test task serialization."""
        task = SubagentTask(
            id="task-456",
            agent_type="analysis",
            task="Analyze data",
            timeout_seconds=600,
        )
        
        data = task.to_dict()
        
        assert data["id"] == "task-456"
        assert data["agent_type"] == "analysis"
        assert data["status"] == "pending"
        assert data["timeout_seconds"] == 600


class TestSubagentExecutor:
    """Tests for SubagentExecutor."""
    
    @pytest.fixture
    def executor(self):
        """Create test executor."""
        return SubagentExecutor(
            max_concurrent=3,
            default_timeout=10,
            max_retries=1,
        )
    
    @pytest.mark.asyncio
    async def test_executor_initialization(self, executor):
        """Test executor initialization."""
        assert executor.max_concurrent == 3
        assert executor._default_timeout == 10
        assert executor._max_retries == 1
        
        stats = executor.stats
        assert stats["total_submitted"] == 0
        assert stats["current_running"] == 0
    
    @pytest.mark.asyncio
    async def test_submit_task(self, executor):
        """Test task submission."""
        task_id = await executor.submit(
            agent_type="research",
            task="Test task",
        )
        
        assert task_id is not None
        
        task = executor.get_task(task_id)
        assert task is not None
        assert task.agent_type == "research"
        assert task.status == TaskStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_execute_task(self, executor):
        """Test task execution."""
        # Set mock handler
        async def mock_handler(agent_type, task):
            return {"result": f"Processed: {task}"}
        
        executor.set_agent_handler(mock_handler)
        
        result = await executor.execute(
            agent_type="test",
            task="Execute me",
        )
        
        assert result["result"] == "Processed: Execute me"
        assert executor.stats["total_completed"] == 1
    
    @pytest.mark.asyncio
    async def test_execute_with_timeout(self):
        """Test task timeout."""
        executor = SubagentExecutor(
            max_concurrent=2,
            default_timeout=1,
        )
        
        async def slow_handler(agent_type, task):
            await asyncio.sleep(5)
            return "should not reach"
        
        executor.set_agent_handler(slow_handler)
        
        with pytest.raises(SubagentTimeoutError):
            await executor.execute(
                agent_type="slow",
                task="Timeout test",
            )
        
        assert executor.stats["total_timeout"] >= 1
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test automatic retry on failure."""
        attempt_count = 0
        
        async def failing_handler(agent_type, task):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise ValueError("Intentional failure")
            return "success after retry"
        
        executor = SubagentExecutor(
            max_concurrent=2,
            max_retries=2,
        )
        executor.set_agent_handler(failing_handler)
        
        result = await executor.execute(
            agent_type="retry",
            task="Retry test",
        )
        
        assert result == "success after retry"
        assert attempt_count == 2
        assert executor.stats["total_retries"] >= 1
    
    @pytest.mark.asyncio
    async def test_concurrency_limit(self, executor):
        """Test concurrency limiting."""
        max_concurrent_observed = 0
        current_running = 0
        lock = asyncio.Lock()
        
        async def tracking_handler(agent_type, task):
            nonlocal max_concurrent_observed, current_running
            
            async with lock:
                current_running += 1
                if current_running > max_concurrent_observed:
                    max_concurrent_observed = current_running
            
            await asyncio.sleep(0.1)
            
            async with lock:
                current_running -= 1
            
            return "done"
        
        executor.set_agent_handler(tracking_handler)
        
        # Submit more tasks than max_concurrent
        tasks = [
            executor.execute("test", f"Task {i}")
            for i in range(5)
        ]
        
        await asyncio.gather(*tasks)
        
        # Should never exceed max_concurrent
        assert max_concurrent_observed <= executor.max_concurrent
    
    @pytest.mark.asyncio
    async def test_cancel_task(self, executor):
        """Test task cancellation."""
        # Submit task
        task_id = await executor.submit(
            agent_type="test",
            task="To cancel",
        )
        
        # Cancel before execution
        cancelled = await executor.cancel_task(task_id)
        
        assert cancelled is True
        
        task = executor.get_task(task_id)
        assert task.status == TaskStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_cancel_all_tasks(self, executor):
        """Test cancelling all tasks."""
        # Submit multiple tasks
        task_ids = []
        for i in range(5):
            tid = await executor.submit("test", f"Task {i}")
            task_ids.append(tid)
        
        # Cancel all
        cancelled_count = await executor.cancel_all()
        
        assert cancelled_count == 5
        
        # Verify all cancelled
        for tid in task_ids:
            task = executor.get_task(tid)
            assert task.status == TaskStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_wait_for_task(self, executor):
        """Test waiting for task completion."""
        async def handler(agent_type, task):
            await asyncio.sleep(0.1)
            return "completed"
        
        executor.set_agent_handler(handler)
        
        task_id = await executor.submit("test", "Wait test")
        
        # Wait for completion
        task = await executor.wait_for_task(task_id)
        
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "completed"
    
    @pytest.mark.asyncio
    async def test_wait_all_tasks(self, executor):
        """Test waiting for multiple tasks."""
        async def handler(agent_type, task):
            await asyncio.sleep(0.05)
            return f"done: {task}"
        
        executor.set_agent_handler(handler)
        
        # Submit multiple
        task_ids = []
        for i in range(3):
            tid = await executor.submit("test", f"Task {i}")
            task_ids.append(tid)
        
        # Wait for all
        tasks = await executor.wait_all(task_ids)
        
        assert len(tasks) == 3
        assert all(t.status == TaskStatus.COMPLETED for t in tasks)
    
    @pytest.mark.asyncio
    async def test_get_result(self, executor):
        """Test getting task result."""
        async def handler(agent_type, task):
            return {"key": "value"}
        
        executor.set_agent_handler(handler)
        
        result = await executor.execute("test", "Result test")
        
        assert result == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_task_not_found(self, executor):
        """Test handling non-existent task."""
        task = executor.get_task("nonexistent")
        assert task is None
        
        with pytest.raises(KeyError):
            await executor.wait_for_task("nonexistent")
    
    @pytest.mark.asyncio
    async def test_list_tasks(self, executor):
        """Test listing tasks."""
        # Submit tasks with different types
        await executor.submit("research", "Task 1")
        await executor.submit("analysis", "Task 2")
        await executor.submit("research", "Task 3")
        
        # List all
        all_tasks = executor.list_tasks()
        assert len(all_tasks) == 3
        
        # Filter by type
        research_tasks = executor.list_tasks(agent_type="research")
        assert len(research_tasks) == 2
        
        # Limit
        limited = executor.list_tasks(limit=2)
        assert len(limited) == 2
    
    @pytest.mark.asyncio
    async def test_executor_stats(self, executor):
        """Test statistics tracking."""
        async def handler(agent_type, task):
            return "done"
        
        executor.set_agent_handler(handler)
        
        # Execute multiple tasks
        for i in range(3):
            await executor.execute("test", f"Task {i}")
        
        stats = executor.stats
        
        assert stats["total_submitted"] == 3
        assert stats["total_completed"] == 3
        assert stats["total_failed"] == 0
    
    @pytest.mark.asyncio
    async def test_cleanup(self, executor):
        """Test executor cleanup."""
        await executor.submit("test", "Task to cancel")
        
        await executor.cleanup()
        
        # All tasks should be cancelled
        tasks = executor.list_tasks()
        assert all(t.status == TaskStatus.CANCELLED for t in tasks)
    
    @pytest.mark.asyncio
    async def test_active_count(self, executor):
        """Test getting active task count."""
        async def handler(agent_type, task):
            await asyncio.sleep(0.1)
            return "done"
        
        executor.set_agent_handler(handler)
        
        # Submit tasks
        for i in range(3):
            await executor.submit("test", f"Task {i}")
        
        # Start processing
        await executor.start_processor()
        
        # Give time to start
        await asyncio.sleep(0.05)
        
        active = executor.get_active_count()
        assert active <= executor.max_concurrent
        
        await executor.cleanup()


class TestTaskStatus:
    """Tests for TaskStatus enum."""
    
    def test_status_values(self):
        """Test status enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"
        assert TaskStatus.TIMEOUT.value == "timeout"
        assert TaskStatus.CANCELLED.value == "cancelled"


class TestSubagentError:
    """Tests for subagent exceptions."""
    
    def test_subagent_error(self):
        """Test SubagentError."""
        error = SubagentError("Test error")
        
        assert str(error) == "Test error"
    
    def test_timeout_error(self):
        """Test SubagentTimeoutError."""
        error = SubagentTimeoutError("Timed out after 300s")
        
        assert "Timed out" in str(error)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
