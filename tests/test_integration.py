"""
Integration tests for AgentM core modules.

Tests cover end-to-end workflows:
- Middleware chain with sandbox and memory
- Subagent execution with result tracking
- Complete request lifecycle
"""

import asyncio
import pytest
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from middleware import (
    MiddlewareChain,
    MiddlewareContext,
    ThreadIsolationMiddleware,
    SandboxMiddleware,
    MemoryMiddleware,
)

from memory import MemoryManager, MemoryFact
from sandbox import LocalSandboxProvider
from subagent import SubagentExecutor, TaskStatus


class TestMiddlewareIntegration:
    """Integration tests for middleware chain."""
    
    @pytest.mark.asyncio
    async def test_full_middleware_chain(self):
        """Test complete middleware chain execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create chain with multiple middlewares
            chain = MiddlewareChain(base_path=tmpdir)
            chain.add(ThreadIsolationMiddleware(base_path=tmpdir))
            chain.add(SandboxMiddleware())
            
            # Core executor that uses sandbox
            async def core_executor(ctx):
                # Write file using sandbox
                await ctx.sandbox.write_file(
                    "/workspace/output.txt",
                    f"Processed: {ctx.query}",
                )
                
                # Read it back
                content = await ctx.sandbox.read_file("/workspace/output.txt")
                
                return {"output": content, "thread_id": ctx.thread_id}
            
            chain.set_core_executor(core_executor)
            
            # Execute
            ctx = MiddlewareContext(
                thread_id="integration-test",
                query="Hello, World!",
            )
            
            result = await chain.execute(ctx)
            
            # Verify result
            assert "Processed: Hello, World!" in result["output"]
            assert result["thread_id"] == "integration-test"
            
            # Verify file was created
            sandbox_path = ctx.virtual_paths["/workspace"]
            output_file = Path(sandbox_path) / "output.txt"
            assert output_file.exists()
    
    @pytest.mark.asyncio
    async def test_memory_injection_in_chain(self):
        """Test memory injection during chain execution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup memory
            memory_path = Path(tmpdir) / "memory.json"
            memory_mgr = MemoryManager(str(memory_path))
            memory_mgr.load()
            memory_mgr.add_fact(MemoryFact(
                content="User prefers Python",
                category="preference",
                confidence=0.9,
            ))
            memory_mgr.flush()
            
            # Create chain with memory middleware
            chain = MiddlewareChain(base_path=tmpdir)
            chain.add(MemoryMiddleware(
                storage_path=str(memory_path),
                confidence_threshold=0.7,
            ))
            
            # Core executor that uses injected memory
            async def core_executor(ctx):
                facts = ctx.state.get("injected_facts", [])
                return {"injected_facts": facts}
            
            chain.set_core_executor(core_executor)
            
            # Execute
            ctx = MiddlewareContext(
                thread_id="memory-test",
                query="What's my preference?",
            )
            
            result = await chain.execute(ctx)
            
            # Verify memory was injected
            assert len(result["injected_facts"]) == 1
            assert "User prefers Python" in result["injected_facts"]


class TestSubagentIntegration:
    """Integration tests for subagent executor."""
    
    @pytest.mark.asyncio
    async def test_batch_execution(self):
        """Test batch subagent execution."""
        executor = SubagentExecutor(
            max_concurrent=2,
            default_timeout=30,
        )
        
        # Mock handler that simulates different agent types
        async def mock_handler(agent_type, task):
            await asyncio.sleep(0.05)
            return {
                "agent_type": agent_type,
                "task": task,
                "status": "completed",
            }
        
        executor.set_agent_handler(mock_handler)
        
        # Submit batch
        tasks = [
            executor.execute("research", f"Research task {i}")
            for i in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify all completed
        assert len(results) == 5
        assert all(r["status"] == "completed" for r in results)
        
        # Verify stats
        stats = executor.stats
        assert stats["total_completed"] == 5
        
        await executor.cleanup()
    
    @pytest.mark.asyncio
    async def test_mixed_task_outcomes(self):
        """Test handling mixed success/failure/timeout."""
        executor = SubagentExecutor(
            max_concurrent=3,
            default_timeout=1,
            max_retries=0,
        )
        
        call_count = 0
        
        async def mixed_handler(agent_type, task):
            nonlocal call_count
            call_count += 1
            
            if "fail" in task:
                raise ValueError("Intentional failure")
            elif "slow" in task:
                await asyncio.sleep(5)  # Will timeout
                return "should not reach"
            else:
                return "success"
        
        executor.set_agent_handler(mixed_handler)
        
        # Submit mixed tasks
        success_id = await executor.submit("test", "success task")
        fail_id = await executor.submit("test", "fail task")
        timeout_id = await executor.submit("test", "slow task")
        
        # Wait for all
        success_task = await executor.wait_for_task(success_id)
        fail_task = await executor.wait_for_task(fail_id)
        timeout_task = await executor.wait_for_task(timeout_id)
        
        # Verify outcomes
        assert success_task.status == TaskStatus.COMPLETED
        assert fail_task.status == TaskStatus.FAILED
        assert timeout_task.status == TaskStatus.TIMEOUT
        
        await executor.cleanup()


class TestEndToEndWorkflow:
    """End-to-end workflow tests."""
    
    @pytest.mark.asyncio
    async def test_complete_request_lifecycle(self):
        """Test complete request from submission to result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup components
            memory_path = Path(tmpdir) / "memory.json"
            
            # Initialize memory with context
            memory_mgr = MemoryManager(str(memory_path))
            memory_mgr.load()
            memory_mgr.add_fact(MemoryFact(
                content="Working on AgentM project",
                category="work",
                confidence=0.95,
            ))
            memory_mgr.flush()
            
            # Create middleware chain
            chain = MiddlewareChain(base_path=tmpdir)
            chain.add(ThreadIsolationMiddleware(base_path=tmpdir))
            chain.add(SandboxMiddleware())
            chain.add(MemoryMiddleware(
                storage_path=str(memory_path),
                confidence_threshold=0.7,
            ))
            
            # Subagent executor
            subagent_executor = SubagentExecutor(max_concurrent=2)
            
            async def mock_subagent(agent_type, task):
                await asyncio.sleep(0.05)
                return {
                    "type": agent_type,
                    "result": f"Processed: {task}",
                }
            
            subagent_executor.set_agent_handler(mock_subagent)
            
            # Core executor that orchestrates everything
            async def core_executor(ctx):
                # Use sandbox to create work file
                await ctx.sandbox.write_file(
                    "/workspace/input.txt",
                    ctx.query,
                )
                
                # Submit subagent task
                result = await subagent_executor.execute(
                    agent_type="processor",
                    task=ctx.query,
                )
                
                # Write output
                await ctx.sandbox.write_file(
                    "/workspace/output.txt",
                    str(result),
                )
                
                return {
                    "subagent_result": result,
                    "memory_facts": ctx.state.get("injected_facts", []),
                    "thread_id": ctx.thread_id,
                }
            
            chain.set_core_executor(core_executor)
            
            # Execute request
            ctx = MiddlewareContext(
                thread_id="e2e-test",
                query="Process this request",
            )
            
            result = await chain.execute(ctx)
            
            # Verify complete workflow
            assert "subagent_result" in result
            assert result["subagent_result"]["type"] == "processor"
            assert len(result["memory_facts"]) > 0
            assert result["thread_id"] == "e2e-test"
            
            # Verify files created
            workspace = ctx.virtual_paths["/workspace"]
            assert (Path(workspace) / "input.txt").exists()
            assert (Path(workspace) / "output.txt").exists()
            
            # Cleanup
            await subagent_executor.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
