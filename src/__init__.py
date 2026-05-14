"""
AgentM - Advanced Agent Management System

AgentM is a production-grade agent management platform inspired by DeerFlow,
featuring:
- Middleware chain for cross-cutting concerns
- Secure sandbox execution
- Structured memory with confidence scoring
- Real-time SSE streaming
- Concurrent subagent execution

Example:
    >>> from agentm import MiddlewareChain, MemoryManager, SubagentExecutor
    >>> 
    >>> # Initialize components
    >>> chain = MiddlewareChain()
    >>> memory = MemoryManager("/path/to/memory.json")
    >>> executor = SubagentExecutor(max_concurrent=5)
"""

__version__ = "0.1.0"
__author__ = "AgentM Team"

from .middleware import (
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

from .sandbox import (
    SandboxProvider,
    LocalSandboxProvider,
    SandboxError,
    SecurityViolationError,
    TimeoutError,
    SandboxResult,
    SandboxMode,
    create_sandbox,
)

from .memory import (
    MemoryManager,
    MemoryData,
    MemoryFact,
    UserContext,
    ContextSection,
    MemoryError,
    MemoryValidationError,
)

from .sse_server import (
    EventType,
    SSEEvent,
    SSEServer,
    ClientConnection,
    SSEConnectionError,
    create_sse_response,
)

from .subagent import (
    SubagentExecutor,
    SubagentTask,
    TaskStatus,
    SubagentError,
    SubagentTimeoutError,
    SubagentConcurrencyError,
)

__all__ = [
    # Middleware
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
    # Sandbox
    "SandboxProvider",
    "LocalSandboxProvider",
    "SandboxError",
    "SecurityViolationError",
    "TimeoutError",
    "SandboxResult",
    "SandboxMode",
    "create_sandbox",
    # Memory
    "MemoryManager",
    "MemoryData",
    "MemoryFact",
    "UserContext",
    "ContextSection",
    "MemoryError",
    "MemoryValidationError",
    # SSE
    "EventType",
    "SSEEvent",
    "SSEServer",
    "ClientConnection",
    "SSEConnectionError",
    "create_sse_response",
    # Subagent
    "SubagentExecutor",
    "SubagentTask",
    "TaskStatus",
    "SubagentError",
    "SubagentTimeoutError",
    "SubagentConcurrencyError",
]
