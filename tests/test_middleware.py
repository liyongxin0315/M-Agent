"""
Unit tests for middleware module.

Tests cover:
- MiddlewareContext creation and serialization
- MiddlewareChain execution flow
- Individual middleware implementations
- Error handling
"""

import asyncio
import pytest
import tempfile
from pathlib import Path
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from middleware import (
    Middleware,
    MiddlewareChain,
    MiddlewareContext,
    MiddlewareError,
    MiddlewarePhase,
    ThreadIsolationMiddleware,
    FileUploadMiddleware,
    SandboxMiddleware,
    MemoryMiddleware,
    ClarificationMiddleware,
)


class TestMiddlewareContext:
    """Tests for MiddlewareContext."""
    
    def test_create_context(self):
        """Test basic context creation."""
        ctx = MiddlewareContext(
            thread_id="test-123",
            query="Hello, world!",
        )
        
        assert ctx.thread_id == "test-123"
        assert ctx.query == "Hello, world!"
        assert ctx.metadata == {}
        assert ctx.virtual_paths == {}
        assert ctx.files == []
        assert ctx.errors == []
    
    def test_context_with_metadata(self):
        """Test context with metadata."""
        ctx = MiddlewareContext(
            thread_id="test-123",
            query="Test query",
            metadata={"user_id": "user-456", "priority": "high"},
        )
        
        assert ctx.metadata["user_id"] == "user-456"
        assert ctx.metadata["priority"] == "high"
    
    def test_context_to_dict(self):
        """Test context serialization."""
        ctx = MiddlewareContext(
            thread_id="test-123",
            query="Test",
            metadata={"key": "value"},
            virtual_paths={"/workspace": "/tmp/ws"},
        )
        
        data = ctx.to_dict()
        
        assert data["thread_id"] == "test-123"
        assert data["query"] == "Test"
        assert data["metadata"] == {"key": "value"}
        assert data["virtual_paths"] == {"/workspace": "/tmp/ws"}
    
    def test_context_from_dict(self):
        """Test context deserialization."""
        data = {
            "thread_id": "test-456",
            "query": "From dict",
            "metadata": {"restored": True},
            "virtual_paths": {"/data": "/tmp/data"},
        }
        
        ctx = MiddlewareContext.from_dict(data)
        
        assert ctx.thread_id == "test-456"
        assert ctx.query == "From dict"
        assert ctx.metadata["restored"] is True


class TestMiddlewareChain:
    """Tests for MiddlewareChain."""
    
    @pytest.fixture
    def chain(self):
        """Create test chain."""
        return MiddlewareChain(base_path=tempfile.gettempdir())
    
    @pytest.mark.asyncio
    async def test_chain_creation(self, chain):
        """Test chain initialization."""
        assert chain.middlewares == []
        assert chain.metrics["total_executions"] == 0
    
    @pytest.mark.asyncio
    async def test_add_middleware(self, chain):
        """Test adding middleware."""
        mw = ThreadIsolationMiddleware()
        chain.add(mw)
        
        assert len(chain.middlewares) == 1
        assert chain.middlewares[0].name == "thread_isolation"
    
    @pytest.mark.asyncio
    async def test_middleware_priority_ordering(self, chain):
        """Test that middlewares are sorted by priority."""
        # Add in random order
        chain.add(MemoryMiddleware())  # priority 40
        chain.add(ThreadIsolationMiddleware())  # priority 10
        chain.add(FileUploadMiddleware())  # priority 20
        
        # Should be sorted by priority
        names = [mw.name for mw in chain.middlewares]
        assert names == ["thread_isolation", "file_upload", "memory"]
    
    @pytest.mark.asyncio
    async def test_execute_chain(self, chain):
        """Test full chain execution."""
        # Add middleware
        chain.add(ThreadIsolationMiddleware())
        
        # Set core executor
        async def core_executor(ctx):
            return {"result": "success", "thread_id": ctx.thread_id}
        
        chain.set_core_executor(core_executor)
        
        # Execute
        ctx = MiddlewareContext(
            thread_id="test-exec",
            query="Test execution",
        )
        
        result = await chain.execute(ctx)
        
        assert result["result"] == "success"
        assert result["thread_id"] == "test-exec"
        assert chain.metrics["successful_executions"] == 1
    
    @pytest.mark.asyncio
    async def test_execute_without_executor(self, chain):
        """Test execution without core executor raises error."""
        ctx = MiddlewareContext(
            thread_id="test",
            query="Test",
        )
        
        with pytest.raises(ValueError, match="No core executor set"):
            await chain.execute(ctx)
    
    @pytest.mark.asyncio
    async def test_execute_with_inline_executor(self, chain):
        """Test execution with inline executor."""
        ctx = MiddlewareContext(
            thread_id="test",
            query="Test",
        )
        
        async def executor(ctx):
            return {"inline": True}
        
        result = await chain.execute(ctx, executor=executor)
        
        assert result["inline"] is True
    
    @pytest.mark.asyncio
    async def test_middleware_error_handling(self, chain):
        """Test error handling in middleware."""
        class ErrorMiddleware(Middleware):
            @property
            def name(self):
                return "error_mw"
            
            @property
            def priority(self):
                return 10
            
            async def pre_process(self, context):
                raise ValueError("Test error")
            
            async def post_process(self, context, result):
                return context
        
        chain.add(ErrorMiddleware())
        chain.set_core_executor(lambda ctx: {"result": "should not reach"})
        
        ctx = MiddlewareContext(
            thread_id="test",
            query="Test",
        )
        
        with pytest.raises(MiddlewareError):
            await chain.execute(ctx)
        
        assert chain.metrics["failed_executions"] == 1
    
    @pytest.mark.asyncio
    async def test_metrics_tracking(self, chain):
        """Test execution metrics."""
        chain.set_core_executor(lambda ctx: {"ok": True})
        
        # Execute multiple times
        for i in range(3):
            ctx = MiddlewareContext(
                thread_id=f"test-{i}",
                query="Test",
            )
            await chain.execute(ctx)
        
        metrics = chain.metrics
        assert metrics["total_executions"] == 3
        assert metrics["successful_executions"] == 3
        assert metrics["failed_executions"] == 0
        assert metrics["avg_duration_ms"] >= 0
    
    @pytest.mark.asyncio
    async def test_remove_middleware(self, chain):
        """Test removing middleware."""
        mw1 = ThreadIsolationMiddleware()
        mw2 = FileUploadMiddleware()
        
        chain.add(mw1)
        chain.add(mw2)
        
        assert len(chain.middlewares) == 2
        
        removed = chain.remove("thread_isolation")
        assert removed is True
        assert len(chain.middlewares) == 1
        assert chain.middlewares[0].name == "file_upload"
        
        # Remove non-existent
        removed = chain.remove("nonexistent")
        assert removed is False


class TestThreadIsolationMiddleware:
    """Tests for ThreadIsolationMiddleware."""
    
    @pytest.mark.asyncio
    async def test_pre_process_creates_directories(self):
        """Test that pre_process creates thread directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mw = ThreadIsolationMiddleware(base_path=tmpdir)
            
            ctx = MiddlewareContext(
                thread_id="test-thread",
                query="Test",
            )
            
            ctx = await mw.pre_process(ctx)
            
            # Check virtual paths are set
            assert "/agentm/workspace" in ctx.virtual_paths
            assert "/agentm/uploads" in ctx.virtual_paths
            assert "/agentm/outputs" in ctx.virtual_paths
            
            # Check directories exist
            for path in ctx.virtual_paths.values():
                assert Path(path).exists()
                assert Path(path).is_dir()
    
    @pytest.mark.asyncio
    async def test_post_process_cleanup(self):
        """Test cleanup on post_process."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mw = ThreadIsolationMiddleware(base_path=tmpdir)
            
            ctx = MiddlewareContext(
                thread_id="cleanup-test",
                query="Test",
                metadata={"cleanup": True},
            )
            
            # Pre-process to create dirs
            ctx = await mw.pre_process(ctx)
            dirs_created = ctx.state.get("thread_dirs_created", [])
            
            # Verify dirs exist
            for d in dirs_created:
                assert Path(d).exists()
            
            # Post-process with cleanup
            ctx = await mw.post_process(ctx, {"result": "test"})
            
            # Verify dirs are cleaned up
            for d in dirs_created:
                assert not Path(d).exists()


class TestFileUploadMiddleware:
    """Tests for FileUploadMiddleware."""
    
    @pytest.mark.asyncio
    async def test_file_validation(self):
        """Test file validation."""
        mw = FileUploadMiddleware(
            max_file_size_mb=1,
            allowed_types=["text/plain", "application/json"],
        )
        
        ctx = MiddlewareContext(
            thread_id="test",
            query="Test",
            metadata={
                "files": [
                    {"name": "small.txt", "size": 100, "mime_type": "text/plain"},
                    {"name": "large.txt", "size": 2 * 1024 * 1024, "mime_type": "text/plain"},
                    {"name": "wrong.json", "size": 100, "mime_type": "application/octet-stream"},
                ]
            },
        )
        
        ctx = await mw.pre_process(ctx)
        
        # Only small.txt should pass
        assert len(ctx.files) == 1
        assert ctx.files[0]["safe_name"] == "small.txt"
    
    @pytest.mark.asyncio
    async def test_filename_sanitization(self):
        """Test filename sanitization."""
        mw = FileUploadMiddleware()
        
        ctx = MiddlewareContext(
            thread_id="test",
            query="Test",
            metadata={
                "files": [
                    {"name": "../../../etc/passwd", "size": 100},
                    {"name": "file with spaces & special!.txt", "size": 100},
                ]
            },
        )
        
        ctx = await mw.pre_process(ctx)
        
        # Check sanitized names
        assert ctx.files[0]["safe_name"] == "etcpasswd"
        assert ctx.files[1]["safe_name"] == "filewithspacesspecial.txt"


class TestSandboxMiddleware:
    """Tests for SandboxMiddleware."""
    
    @pytest.mark.asyncio
    async def test_sandbox_injection(self):
        """Test that sandbox is injected into context."""
        mw = SandboxMiddleware()
        
        ctx = MiddlewareContext(
            thread_id="test",
            query="Test",
            virtual_paths={"/workspace": "/tmp/ws"},
        )
        
        ctx = await mw.pre_process(ctx)
        
        assert ctx.sandbox is not None
        assert ctx.sandbox.thread_id == "test"


class TestMemoryMiddleware:
    """Tests for MemoryMiddleware."""
    
    @pytest.mark.asyncio
    async def test_memory_injection(self):
        """Test memory facts injection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "memory.json"
            
            # Create test memory
            from memory import MemoryManager, MemoryFact
            
            manager = MemoryManager(str(storage_path))
            manager.load()
            manager.add_fact(MemoryFact(
                content="Test fact 1",
                category="test",
                confidence=0.9,
            ))
            manager.add_fact(MemoryFact(
                content="Test fact 2",
                category="test",
                confidence=0.5,  # Below threshold
            ))
            manager.flush()
            
            # Test middleware
            mw = MemoryMiddleware(
                storage_path=str(storage_path),
                confidence_threshold=0.7,
                max_facts=5,
            )
            
            ctx = MiddlewareContext(
                thread_id="test",
                query="Test",
            )
            
            ctx = await mw.pre_process(ctx)
            
            # Should inject high-confidence facts only
            assert ctx.memory is not None
            assert len(ctx.state.get("injected_facts", [])) == 1


class TestClarificationMiddleware:
    """Tests for ClarificationMiddleware."""
    
    @pytest.mark.asyncio
    async def test_clarification_detection(self):
        """Test clarification detection."""
        mw = ClarificationMiddleware()
        
        # Test with clarification flag
        ctx = MiddlewareContext(
            thread_id="test",
            query="Test",
            metadata={"needs_clarification": True},
        )
        
        with pytest.raises(MiddlewareError, match="requires clarification"):
            await mw.pre_process(ctx)
    
    @pytest.mark.asyncio
    async def test_no_clarification_needed(self):
        """Test normal query passes through."""
        mw = ClarificationMiddleware()
        
        ctx = MiddlewareContext(
            thread_id="test",
            query="What is Python?",
        )
        
        result = await mw.pre_process(ctx)
        
        assert result is ctx  # Should pass through unchanged


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
