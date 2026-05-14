"""
Middleware Chain System for AgentM.

This module implements a flexible middleware chain architecture that allows
cross-cutting concerns (logging, authentication, sandbox, memory, etc.) to be
applied in a strict order with pre/post processing hooks.

Design Philosophy:
- Separation of concerns: Each middleware handles one specific aspect
- Strict ordering: Middlewares execute in defined order
- Async-first: All I/O operations are asynchronous
- Error handling: Graceful degradation with proper exception propagation

Example Usage:
    >>> async def main():
    ...     chain = MiddlewareChain()
    ...     chain.add(ThreadIsolationMiddleware())
    ...     chain.add(SandboxMiddleware())
    ...     result = await chain.execute({"thread_id": "abc123", "query": "Hello"})
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class MiddlewarePhase(str, Enum):
    """Execution phase for middleware hooks.
    
    Attributes:
        PRE: Before core logic execution
        POST: After core logic execution
    """
    PRE = "pre_process"
    POST = "post_process"


@dataclass
class MiddlewareContext:
    """Context object passed through middleware chain.
    
    Attributes:
        thread_id: Unique identifier for the current thread/session
        query: User query or input
        metadata: Additional metadata (user info, timestamps, etc.)
        sandbox: Sandbox provider instance (injected by SandboxMiddleware)
        memory: Memory manager instance (injected by MemoryMiddleware)
        virtual_paths: Virtual to physical path mappings
        files: Uploaded files metadata
        state: Mutable state dictionary for middleware communication
        errors: Collected errors during processing
        start_time: Chain execution start timestamp
    """
    thread_id: str
    query: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    sandbox: Optional[Any] = None
    memory: Optional[Any] = None
    virtual_paths: Dict[str, str] = field(default_factory=dict)
    files: List[Dict[str, Any]] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    errors: List[Exception] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary representation."""
        return {
            "thread_id": self.thread_id,
            "query": self.query,
            "metadata": self.metadata,
            "virtual_paths": self.virtual_paths,
            "files": self.files,
            "state": self.state,
            "errors": [str(e) for e in self.errors],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MiddlewareContext:
        """Create context from dictionary."""
        return cls(
            thread_id=data.get("thread_id", str(uuid.uuid4())),
            query=data.get("query", ""),
            metadata=data.get("metadata", {}),
            virtual_paths=data.get("virtual_paths", {}),
            files=data.get("files", []),
            state=data.get("state", {}),
            errors=[],
        )


class MiddlewareError(Exception):
    """Base exception for middleware errors.
    
    Attributes:
        message: Error description
        context: Context at time of error
        recoverable: Whether execution can continue
    """
    
    def __init__(
        self,
        message: str,
        context: Optional[MiddlewareContext] = None,
        recoverable: bool = True,
    ):
        super().__init__(message)
        self.message = message
        self.context = context
        self.recoverable = recoverable
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {self.message}"


class Middleware(ABC):
    """Abstract base class for all middlewares.
    
    Middleware provides a way to intercept and modify requests/responses
    in a standardized way. Each middleware can:
    - Modify the context before core execution (pre_process)
    - Modify the result after core execution (post_process)
    - Skip further processing by raising MiddlewareError
    - Add state/data to context for other middlewares
    
    Implementation Requirements:
    - All methods must be async
    - Must preserve context immutability where possible
    - Should log significant actions
    - Must handle exceptions gracefully
    
    Example:
        class LoggingMiddleware(Middleware):
            async def pre_process(self, context: MiddlewareContext) -> MiddlewareContext:
                logger.info(f"Processing query: {context.query}")
                context.state["log_start"] = datetime.now()
                return context
            
            async def post_process(
                self,
                context: MiddlewareContext,
                result: Any,
            ) -> MiddlewareContext:
                duration = datetime.now() - context.state["log_start"]
                logger.info(f"Completed in {duration}")
                return context
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this middleware."""
        pass
    
    @property
    def priority(self) -> int:
        """Execution priority (lower = earlier execution).
        
        Default priority is 100. Override to change execution order.
        """
        return 100
    
    @abstractmethod
    async def pre_process(
        self,
        context: MiddlewareContext,
    ) -> MiddlewareContext:
        """Process context before core logic execution.
        
        This method is called in order (by priority) before the core
        business logic executes. Use this for:
        - Input validation
        - Resource setup
        - Data injection
        - Authentication/authorization
        
        Args:
            context: Current execution context
            
        Returns:
            Modified context (must return context, can be same instance)
            
        Raises:
            MiddlewareError: To halt execution with specific error
        """
        pass
    
    @abstractmethod
    async def post_process(
        self,
        context: MiddlewareContext,
        result: Any,
    ) -> MiddlewareContext:
        """Process result after core logic execution.
        
        This method is called in reverse order (by priority) after the
        core business logic completes. Use this for:
        - Response transformation
        - Resource cleanup
        - Logging/metrics
        - Side effects (notifications, caching)
        
        Args:
            context: Current execution context
            result: Result from core logic or previous middleware
            
        Returns:
            Modified context (must return context, can be same instance)
            
        Raises:
            MiddlewareError: To transform/handle errors
        """
        pass
    
    async def on_error(
        self,
        context: MiddlewareContext,
        error: Exception,
    ) -> None:
        """Handle errors that occur during middleware execution.
        
        Override this method to implement custom error handling logic.
        Default implementation logs the error.
        
        Args:
            context: Current execution context
            error: The exception that was raised
        """
        logger.error(f"Error in {self.name}: {error}")


class MiddlewareChain:
    """Middleware chain executor.
    
    The chain manages a collection of middlewares and executes them in
    a strict order. Execution flow:
    
    1. Sort middlewares by priority (ascending)
    2. Execute pre_process hooks in order
    3. Execute core logic
    4. Execute post_process hooks in reverse order
    
    The chain supports:
    - Dynamic middleware registration
    - Error handling with recovery options
    - Execution metrics and logging
    - Context passing between middlewares
    
    Attributes:
        middlewares: List of registered middlewares
        core_executor: Core business logic function
        execution_metrics: Statistics about chain execution
        
    Example:
        >>> chain = MiddlewareChain()
        >>> chain.add(AuthMiddleware())
        >>> chain.add(SandboxMiddleware())
        >>> chain.add(MemoryMiddleware())
        >>>
        >>> async def core_logic(ctx):
        ...     return {"answer": "Processed: " + ctx.query}
        >>>
        >>> chain.set_core_executor(core_logic)
        >>> result = await chain.execute(context)
    """
    
    def __init__(self, base_path: str = "/tmp/agentm"):
        """Initialize middleware chain.
        
        Args:
            base_path: Base directory for thread isolation
        """
        self._middlewares: List[Middleware] = []
        self._core_executor: Optional[Callable] = None
        self._base_path = base_path
        self._execution_metrics: Dict[str, Any] = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "avg_duration_ms": 0.0,
        }
        self._is_frozen = False
    
    @property
    def middlewares(self) -> List[Middleware]:
        """Get list of registered middlewares."""
        return self._middlewares.copy()
    
    @property
    def metrics(self) -> Dict[str, Any]:
        """Get execution metrics."""
        return self._execution_metrics.copy()
    
    def add(self, middleware: Middleware) -> MiddlewareChain:
        """Add middleware to chain.
        
        Middlewares are sorted by priority before execution.
        
        Args:
            middleware: Middleware instance to add
            
        Returns:
            Self for method chaining
            
        Raises:
            RuntimeError: If chain is frozen (already executing)
        """
        if self._is_frozen:
            raise RuntimeError("Cannot add middleware to frozen chain")
        
        self._middlewares.append(middleware)
        self._middlewares.sort(key=lambda m: m.priority)
        logger.debug(f"Added middleware: {middleware.name} (priority={middleware.priority})")
        return self
    
    def remove(self, name: str) -> bool:
        """Remove middleware by name.
        
        Args:
            name: Name of middleware to remove
            
        Returns:
            True if removed, False if not found
        """
        for i, mw in enumerate(self._middlewares):
            if mw.name == name:
                self._middlewares.pop(i)
                logger.debug(f"Removed middleware: {name}")
                return True
        return False
    
    def set_core_executor(self, executor: Callable) -> None:
        """Set the core business logic executor.
        
        Args:
            executor: Async function that takes MiddlewareContext and returns result
        """
        self._core_executor = executor
    
    async def execute(
        self,
        context: MiddlewareContext,
        executor: Optional[Callable] = None,
    ) -> Any:
        """Execute middleware chain with context.
        
        This method:
        1. Freezes the chain (prevents modifications)
        2. Executes all pre_process hooks
        3. Executes core logic
        4. Executes all post_process hooks (reverse order)
        5. Updates metrics
        6. Unfreezes the chain
        
        Args:
            context: Execution context
            executor: Optional core executor (overrides default)
            
        Returns:
            Result from core executor after post_process
            
        Raises:
            MiddlewareError: If any middleware fails
            ValueError: If no core executor is set
        """
        self._is_frozen = True
        start_time = datetime.now()
        
        try:
            self._execution_metrics["total_executions"] += 1
            
            # Pre-processing phase (forward order)
            logger.debug(f"Starting pre-processing with {len(self._middlewares)} middlewares")
            for mw in self._middlewares:
                try:
                    context = await mw.pre_process(context)
                    logger.debug(f"Completed pre_process: {mw.name}")
                except MiddlewareError:
                    raise
                except Exception as e:
                    logger.error(f"Error in {mw.name}.pre_process: {e}")
                    context.errors.append(e)
                    await mw.on_error(context, e)
                    if not isinstance(e, MiddlewareError) or not getattr(e, 'recoverable', True):
                        raise MiddlewareError(
                            f"Pre-processing failed in {mw.name}",
                            context=context,
                            recoverable=False,
                        ) from e
            
            # Core execution
            core_executor = executor or self._core_executor
            if not core_executor:
                raise ValueError("No core executor set")
            
            logger.debug("Executing core logic")
            result = await core_executor(context)
            
            # Post-processing phase (reverse order)
            logger.debug("Starting post-processing")
            for mw in reversed(self._middlewares):
                try:
                    context = await mw.post_process(context, result)
                    logger.debug(f"Completed post_process: {mw.name}")
                except MiddlewareError:
                    raise
                except Exception as e:
                    logger.error(f"Error in {mw.name}.post_process: {e}")
                    context.errors.append(e)
                    await mw.on_error(context, e)
            
            self._execution_metrics["successful_executions"] += 1
            return result
            
        except Exception as e:
            self._execution_metrics["failed_executions"] += 1
            logger.error(f"Chain execution failed: {e}")
            raise
        finally:
            # Update metrics
            duration = (datetime.now() - start_time).total_seconds() * 1000
            metrics = self._execution_metrics
            total = metrics["total_executions"]
            metrics["avg_duration_ms"] = (
                (metrics["avg_duration_ms"] * (total - 1) + duration) / total
            )
            
            self._is_frozen = False


# =============================================================================
# Concrete Middleware Implementations
# =============================================================================


class ThreadIsolationMiddleware(Middleware):
    """Middleware for thread data isolation.
    
    Creates isolated directory structures for each thread to prevent
    data leakage between concurrent executions.
    
    Features:
    - Virtual path mapping (logical to physical paths)
    - Automatic directory creation
    - Optional cleanup on completion
    
    Virtual Path Structure:
        /agentm/{thread_id}/workspace  - Working directory
        /agentm/{thread_id}/uploads    - Uploaded files
        /agentm/{thread_id}/outputs    - Generated outputs
    """
    
    def __init__(self, base_path: str = "/tmp/agentm"):
        """Initialize thread isolation middleware.
        
        Args:
            base_path: Base directory for thread data
        """
        self._base_path = Path(base_path)
    
    @property
    def name(self) -> str:
        return "thread_isolation"
    
    @property
    def priority(self) -> int:
        return 10  # Execute early
    
    async def pre_process(
        self,
        context: MiddlewareContext,
    ) -> MiddlewareContext:
        """Create thread isolation directories.
        
        Sets up virtual path mappings and creates physical directories.
        """
        thread_id = context.thread_id
        
        # Define virtual to physical path mappings
        context.virtual_paths = {
            "/agentm/workspace": str(self._base_path / thread_id / "workspace"),
            "/agentm/uploads": str(self._base_path / thread_id / "uploads"),
            "/agentm/outputs": str(self._base_path / thread_id / "outputs"),
        }
        
        # Create physical directories
        for physical_path in context.virtual_paths.values():
            path = Path(physical_path)
            path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {physical_path}")
        
        context.state["thread_dirs_created"] = list(context.virtual_paths.values())
        logger.info(f"Thread isolation setup complete for {thread_id}")
        
        return context
    
    async def post_process(
        self,
        context: MiddlewareContext,
        result: Any,
    ) -> MiddlewareContext:
        """Optional cleanup after execution.
        
        By default, directories are preserved. Set cleanup=True in
        context.metadata to enable automatic cleanup.
        """
        if context.metadata.get("cleanup", False):
            dirs_to_clean = context.state.get("thread_dirs_created", [])
            for dir_path in dirs_to_clean:
                try:
                    import shutil
                    shutil.rmtree(dir_path)
                    logger.debug(f"Cleaned up directory: {dir_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean {dir_path}: {e}")
        
        return context


class FileUploadMiddleware(Middleware):
    """Middleware for handling file uploads.
    
    Processes uploaded files and makes them available in the sandbox.
    
    Features:
    - File validation (size, type)
    - Secure filename handling
    - Metadata extraction
    """
    
    def __init__(
        self,
        max_file_size_mb: int = 10,
        allowed_types: Optional[List[str]] = None,
    ):
        """Initialize file upload middleware.
        
        Args:
            max_file_size_mb: Maximum file size in megabytes
            allowed_types: List of allowed MIME types (None = all)
        """
        self._max_size_bytes = max_file_size_mb * 1024 * 1024
        self._allowed_types = allowed_types
    
    @property
    def name(self) -> str:
        return "file_upload"
    
    @property
    def priority(self) -> int:
        return 20
    
    async def pre_process(
        self,
        context: MiddlewareContext,
    ) -> MiddlewareContext:
        """Process uploaded files from context.
        
        Validates files and prepares them for sandbox access.
        """
        files = context.metadata.get("files", [])
        valid_files = []
        
        for file_info in files:
            # Validate file size
            if file_info.get("size", 0) > self._max_size_bytes:
                logger.warning(f"File too large: {file_info.get('name')}")
                continue
            
            # Validate file type
            mime_type = file_info.get("mime_type", "")
            if self._allowed_types and mime_type not in self._allowed_types:
                logger.warning(f"File type not allowed: {mime_type}")
                continue
            
            # Secure filename
            original_name = file_info.get("name", "unnamed")
            safe_name = "".join(
                c for c in original_name
                if c.isalnum() or c in "._-"
            ).strip()
            file_info["safe_name"] = safe_name
            
            valid_files.append(file_info)
        
        context.files = valid_files
        context.state["files_processed"] = len(valid_files)
        logger.debug(f"Processed {len(valid_files)} files")
        
        return context
    
    async def post_process(
        self,
        context: MiddlewareContext,
        result: Any,
    ) -> MiddlewareContext:
        """Add file references to result if applicable."""
        if context.files and isinstance(result, dict):
            result["attached_files"] = [
                {"name": f["safe_name"], "path": f.get("path")}
                for f in context.files
            ]
        return context


class SandboxMiddleware(Middleware):
    """Middleware for sandbox provider injection.
    
    Provides isolated execution environment for code and file operations.
    
    Features:
    - Virtual path translation
    - Command execution with timeout
    - File I/O with path restrictions
    """
    
    def __init__(self, timeout_seconds: int = 60):
        """Initialize sandbox middleware.
        
        Args:
            timeout_seconds: Default command execution timeout
        """
        self._timeout = timeout_seconds
    
    @property
    def name(self) -> str:
        return "sandbox"
    
    @property
    def priority(self) -> int:
        return 30
    
    async def pre_process(
        self,
        context: MiddlewareContext,
    ) -> MiddlewareContext:
        """Initialize sandbox provider for context.
        
        Creates a sandbox instance with thread-specific paths.
        """
        from .sandbox import LocalSandboxProvider
        
        context.sandbox = LocalSandboxProvider(
            thread_id=context.thread_id,
            virtual_paths=context.virtual_paths,
            timeout_seconds=self._timeout,
        )
        
        logger.debug(f"Sandbox initialized for thread {context.thread_id}")
        return context
    
    async def post_process(
        self,
        context: MiddlewareContext,
        result: Any,
    ) -> MiddlewareContext:
        """Cleanup sandbox resources if needed."""
        if context.sandbox and hasattr(context.sandbox, 'cleanup'):
            await context.sandbox.cleanup()
        return context


class MemoryMiddleware(Middleware):
    """Middleware for memory system integration.
    
    Loads user memory and injects relevant facts into context.
    
    Features:
    - Memory loading with caching
    - Fact filtering by confidence
    - Memory injection for LLM context
    """
    
    def __init__(
        self,
        storage_path: str = "/tmp/agentm/memory.json",
        confidence_threshold: float = 0.7,
        max_facts: int = 10,
    ):
        """Initialize memory middleware.
        
        Args:
            storage_path: Path to memory storage file
            confidence_threshold: Minimum confidence for fact injection
            max_facts: Maximum facts to inject
        """
        self._storage_path = storage_path
        self._confidence_threshold = confidence_threshold
        self._max_facts = max_facts
    
    @property
    def name(self) -> str:
        return "memory"
    
    @property
    def priority(self) -> int:
        return 40
    
    async def pre_process(
        self,
        context: MiddlewareContext,
    ) -> MiddlewareContext:
        """Load and inject memory facts.
        
        Loads memory from storage and filters high-confidence facts
        for injection into the query context.
        """
        from .memory import MemoryManager
        
        manager = MemoryManager(self._storage_path)
        manager.load()
        context.memory = manager
        
        # Get relevant facts
        facts = manager.get_top_facts(
            limit=self._max_facts,
            min_confidence=self._confidence_threshold,
        )
        
        context.state["injected_facts"] = [f.content for f in facts]
        logger.debug(f"Injected {len(facts)} memory facts")
        
        return context
    
    async def post_process(
        self,
        context: MiddlewareContext,
        result: Any,
    ) -> MiddlewareContext:
        """Extract and save new facts from result if applicable."""
        if context.memory and context.metadata.get("extract_memory", False):
            # Extract facts from result (implementation depends on LLM)
            pass
        return context


class ClarificationMiddleware(Middleware):
    """Middleware for handling clarification requests.
    
    Detects when the agent needs more information and triggers
    a clarification flow instead of executing the query.
    
    Features:
    - Pattern detection for clarification needs
    - Structured clarification requests
    - Interrupt execution flow
    """
    
    def __init__(self, clarification_patterns: Optional[List[str]] = None):
        """Initialize clarification middleware.
        
        Args:
            clarification_patterns: Regex patterns indicating need for clarification
        """
        import re
        self._patterns = [
            re.compile(p, re.IGNORECASE)
            for p in clarification_patterns or [
                r"need more information",
                r"could you clarify",
                r"which.*do you mean",
                r"please specify",
            ]
        ]
    
    @property
    def name(self) -> str:
        return "clarification"
    
    @property
    def priority(self) -> int:
        return 50  # Execute last in pre_process
    
    async def pre_process(
        self,
        context: MiddlewareContext,
    ) -> MiddlewareContext:
        """Check if query needs clarification.
        
        Analyzes query for patterns that indicate ambiguity or
        missing information.
        """
        # Check for clarification flags from previous turns
        if context.metadata.get("needs_clarification"):
            raise MiddlewareError(
                "Query requires clarification",
                context=context,
                recoverable=True,
            )
        
        return context
    
    async def post_process(
        self,
        context: MiddlewareContext,
        result: Any,
    ) -> MiddlewareContext:
        """Check result for clarification requests."""
        if isinstance(result, dict):
            if result.get("action") == "clarify":
                context.state["clarification_needed"] = True
                context.state["clarification_question"] = result.get("question")
        
        return context


__all__ = [
    "Middleware",
    "MiddlewareChain",
    "MiddlewareContext",
    "MiddlewareError",
    "MiddlewarePhase",
    "ThreadIsolationMiddleware",
    "FileUploadMiddleware",
    "SandboxMiddleware",
    "MemoryMiddleware",
    "ClarificationMiddleware",
]
