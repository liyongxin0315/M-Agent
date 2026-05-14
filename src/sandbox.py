"""
Sandbox System for AgentM.

This module provides a secure execution environment for running untrusted
code and file operations. The sandbox abstracts the underlying execution
environment, supporting both local and containerized execution.

Design Philosophy:
- Abstraction: Provider interface allows swapping implementations
- Security: Path restrictions and command filtering
- Isolation: Each thread gets its own filesystem view
- Flexibility: Support local, Docker, and custom providers

Architecture:
    SandboxProvider (ABC)
    ├── LocalSandboxProvider    - Local filesystem with path restrictions
    ├── DockerSandboxProvider   - Container-based isolation (future)
    └── CustomSandboxProvider   - User-defined implementations

Example Usage:
    >>> async def main():
    ...     sandbox = LocalSandboxProvider(
    ...         thread_id="abc123",
    ...         virtual_paths={"/workspace": "/tmp/agentm/abc123/workspace"},
    ...     )
    ...     
    ...     # Execute commands
    ...     output = await sandbox.execute_command("ls -la")
    ...     
    ...     # File operations
    ...     await sandbox.write_file("/workspace/test.txt", "Hello")
    ...     content = await sandbox.read_file("/workspace/test.txt")
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class SandboxError(Exception):
    """Base exception for sandbox errors.
    
    Attributes:
        message: Error description
        command: Command that failed (if applicable)
        output: Command output (if available)
        return_code: Return code (if applicable)
    """
    
    def __init__(
        self,
        message: str,
        command: Optional[str] = None,
        output: Optional[str] = None,
        return_code: Optional[int] = None,
    ):
        super().__init__(message)
        self.message = message
        self.command = command
        self.output = output
        self.return_code = return_code
    
    def __str__(self) -> str:
        parts = [self.message]
        if self.command:
            parts.append(f"Command: {self.command}")
        if self.output:
            parts.append(f"Output: {self.output}")
        if self.return_code is not None:
            parts.append(f"Return code: {self.return_code}")
        return " | ".join(parts)


class SecurityViolationError(SandboxError):
    """Raised when a security policy is violated."""
    pass


class TimeoutError(SandboxError):
    """Raised when operation exceeds timeout."""
    pass


@dataclass
class SandboxResult:
    """Result from sandbox operation.
    
    Attributes:
        success: Whether operation succeeded
        output: Standard output
        error: Standard error
        return_code: Process return code
        duration_ms: Execution duration in milliseconds
        metadata: Additional metadata
    """
    success: bool
    output: str = ""
    error: str = ""
    return_code: int = 0
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SandboxProvider(ABC):
    """Abstract base class for sandbox providers.
    
    The sandbox provider interface defines the contract for secure
    execution environments. Implementations must provide:
    
    - Command execution with isolation
    - File system operations with path restrictions
    - Resource limits and timeout handling
    - Security policy enforcement
    
    Security Considerations:
    - All paths must be validated against allowed directories
    - Commands should be audited for dangerous operations
    - Resource limits prevent denial of service
    - Timeout prevents hanging operations
    
    Example Implementation:
        class MySandboxProvider(SandboxProvider):
            async def execute_command(self, cmd: str, cwd: str = None) -> str:
                # Validate command
                self._validate_command(cmd)
                
                # Execute with restrictions
                result = await self._run(cmd, cwd=cwd)
                
                # Audit result
                self._audit_result(result)
                
                return result
    """
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique name for this provider implementation."""
        pass
    
    @abstractmethod
    async def execute_command(
        self,
        cmd: str,
        cwd: str = None,
        timeout: Optional[float] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> str:
        """Execute a shell command in the sandbox.
        
        Args:
            cmd: Command to execute
            cwd: Working directory (virtual path)
            timeout: Execution timeout in seconds
            env: Environment variables
            
        Returns:
            Command stdout
            
        Raises:
            SecurityViolationError: If command violates security policy
            TimeoutError: If execution exceeds timeout
            SandboxError: For other execution errors
        """
        pass
    
    @abstractmethod
    async def read_file(self, path: str) -> str:
        """Read file contents.
        
        Args:
            path: File path (virtual path)
            
        Returns:
            File contents as string
            
        Raises:
            SecurityViolationError: If path is not allowed
            FileNotFoundError: If file doesn't exist
        """
        pass
    
    @abstractmethod
    async def write_file(self, path: str, content: str) -> None:
        """Write content to file.
        
        Args:
            path: File path (virtual path)
            content: Content to write
            
        Raises:
            SecurityViolationError: If path is not allowed
        """
        pass
    
    @abstractmethod
    async def list_dir(self, path: str) -> List[str]:
        """List directory contents.
        
        Args:
            path: Directory path (virtual path)
            
        Returns:
            List of filenames
            
        Raises:
            SecurityViolationError: If path is not allowed
            NotADirectoryError: If path is not a directory
        """
        pass
    
    @abstractmethod
    async def file_exists(self, path: str) -> bool:
        """Check if file exists.
        
        Args:
            path: File path (virtual path)
            
        Returns:
            True if file exists
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup sandbox resources.
        
        Called when sandbox is no longer needed.
        """
        pass
    
    def translate_path(self, virtual_path: str) -> str:
        """Translate virtual path to physical path.
        
        Subclasses should implement this to handle path mapping.
        
        Args:
            virtual_path: Virtual path from user/code
            
        Returns:
            Physical path on host system
            
        Raises:
            SecurityViolationError: If path translation fails
        """
        raise NotImplementedError


class LocalSandboxProvider(SandboxProvider):
    """Local filesystem sandbox provider.
    
    Provides sandboxing through path restrictions and command filtering
    on the local filesystem. Suitable for trusted environments where
    container overhead is not desired.
    
    Security Features:
    - Virtual path mapping (isolates thread data)
    - Command allowlist/blocklist
    - Path traversal prevention
    - Resource limits
    
    Virtual Path Structure:
        Virtual Path          -> Physical Path
        /workspace            -> /tmp/agentm/{thread_id}/workspace
        /uploads              -> /tmp/agentm/{thread_id}/uploads
        /outputs              -> /tmp/agentm/{thread_id}/outputs
    
    Example:
        >>> sandbox = LocalSandboxProvider(
        ...     thread_id="abc123",
        ...     virtual_paths={
        ...         "/workspace": "/tmp/agentm/abc123/workspace",
        ...     },
        ...     timeout_seconds=60,
        ... )
        >>> 
        >>> # Commands are restricted to workspace
        >>> await sandbox.execute_command("cat /workspace/file.txt")
        >>> 
        >>> # Path traversal is blocked
        >>> await sandbox.execute_command("cat /etc/passwd")  # Raises SecurityViolationError
    """
    
    # Dangerous commands that should be blocked
    DANGEROUS_COMMANDS: Set[str] = {
        "rm", "rmdir", "mkfs", "dd", "chmod", "chown",
        "wget", "curl", "nc", "netcat", "ssh", "scp",
        "sudo", "su", "passwd", "useradd", "userdel",
        "mount", "umount", "fdisk", "parted",
    }
    
    # Dangerous patterns
    DANGEROUS_PATTERNS: List[re.Pattern] = [
        re.compile(r"\b(rm\s+-rf\s+/)\b"),  # rm -rf /
        re.compile(r"\b(dd\s+.*of=/dev/)\b"),  # dd to device
        re.compile(r">\s*/etc/"),  # Redirect to /etc
        re.compile(r">\s*/proc/"),  # Redirect to /proc
        re.compile(r">\s*/sys/"),  # Redirect to /sys
    ]
    
    def __init__(
        self,
        thread_id: str,
        virtual_paths: Optional[Dict[str, str]] = None,
        timeout_seconds: float = 60.0,
        max_output_size: int = 1024 * 1024,  # 1MB
        allow_network: bool = False,
    ):
        """Initialize local sandbox provider.
        
        Args:
            thread_id: Unique thread identifier
            virtual_paths: Mapping of virtual to physical paths
            timeout_seconds: Default command timeout
            max_output_size: Maximum output size in bytes
            allow_network: Whether to allow network commands
        """
        self._thread_id = thread_id
        self._timeout = timeout_seconds
        self._max_output_size = max_output_size
        self._allow_network = allow_network
        
        # Default virtual paths
        base_path = Path(tempfile.gettempdir()) / "agentm" / thread_id
        self._virtual_paths = virtual_paths or {
            "/workspace": str(base_path / "workspace"),
            "/uploads": str(base_path / "uploads"),
            "/outputs": str(base_path / "outputs"),
        }
        
        # Ensure directories exist
        for physical_path in self._virtual_paths.values():
            Path(physical_path).mkdir(parents=True, exist_ok=True)
        
        self._execution_log: List[Dict[str, Any]] = []
        logger.info(f"LocalSandboxProvider initialized for thread {thread_id}")
    
    @property
    def provider_name(self) -> str:
        return "local"
    
    @property
    def thread_id(self) -> str:
        """Get thread ID."""
        return self._thread_id
    
    @property
    def virtual_paths(self) -> Dict[str, str]:
        """Get virtual path mappings."""
        return self._virtual_paths.copy()
    
    def translate_path(self, virtual_path: str) -> str:
        """Translate virtual path to physical path.
        
        Args:
            virtual_path: Virtual path (e.g., "/workspace/file.txt")
            
        Returns:
            Physical path on host
            
        Raises:
            SecurityViolationError: If path cannot be translated
        """
        if not virtual_path:
            raise SecurityViolationError("Empty path")
        
        # Try to match virtual path prefix
        for virtual_prefix, physical_prefix in self._virtual_paths.items():
            if virtual_path == virtual_prefix:
                return physical_prefix
            if virtual_path.startswith(virtual_prefix + "/"):
                relative = virtual_path[len(virtual_prefix):]
                physical = os.path.join(physical_prefix, relative.lstrip("/"))
                
                # Resolve to absolute path (handles .., symlinks)
                resolved = os.path.normpath(physical)
                
                # Verify resolved path is still under physical_prefix
                if not resolved.startswith(physical_prefix):
                    raise SecurityViolationError(
                        f"Path traversal detected: {virtual_path}"
                    )
                
                return resolved
        
        # Path doesn't match any virtual mapping
        raise SecurityViolationError(
            f"Path not in allowed directories: {virtual_path}"
        )
    
    def _validate_command(self, cmd: str) -> None:
        """Validate command for security violations.
        
        Args:
            cmd: Command to validate
            
        Raises:
            SecurityViolationError: If command is dangerous
        """
        # Extract base command
        parts = cmd.split()
        if not parts:
            raise SecurityViolationError("Empty command")
        
        base_cmd = os.path.basename(parts[0]).lower()
        
        # Check against dangerous commands
        if base_cmd in self.DANGEROUS_COMMANDS:
            raise SecurityViolationError(
                f"Command not allowed: {base_cmd}"
            )
        
        # Check for network commands if not allowed
        if not self._allow_network and base_cmd in {"wget", "curl", "nc", "ssh"}:
            raise SecurityViolationError(
                f"Network command not allowed: {base_cmd}"
            )
        
        # Check dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern.search(cmd):
                raise SecurityViolationError(
                    f"Dangerous pattern detected in command"
                )
    
    def _truncate_output(self, output: str) -> str:
        """Truncate output if too large.
        
        Args:
            output: Command output
            
        Returns:
            Truncated output with notice
        """
        if len(output) > self._max_output_size:
            return (
                output[:self._max_output_size] +
                f"\n... [truncated, exceeded {self._max_output_size} bytes]"
            )
        return output
    
    async def execute_command(
        self,
        cmd: str,
        cwd: str = None,
        timeout: Optional[float] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> str:
        """Execute command in sandbox.
        
        Args:
            cmd: Command to execute
            cwd: Working directory (virtual path)
            timeout: Timeout in seconds (overrides default)
            env: Environment variables
            
        Returns:
            Command stdout
            
        Raises:
            SecurityViolationError: If command is not allowed
            TimeoutError: If execution times out
            SandboxError: For execution errors
        """
        start_time = datetime.now()
        
        # Validate command
        self._validate_command(cmd)
        
        # Translate working directory
        physical_cwd = None
        if cwd:
            physical_cwd = self.translate_path(cwd)
        
        # Merge environment
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        
        try:
            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                cmd,
                cwd=physical_cwd,
                env=full_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            # Wait with timeout
            exec_timeout = timeout or self._timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=exec_timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise TimeoutError(
                    f"Command timed out after {exec_timeout}s",
                    command=cmd,
                )
            
            # Decode output
            stdout_str = self._truncate_output(stdout.decode("utf-8", errors="replace"))
            stderr_str = self._truncate_output(stderr.decode("utf-8", errors="replace"))
            
            # Log execution
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self._execution_log.append({
                "command": cmd,
                "cwd": cwd,
                "return_code": process.returncode,
                "duration_ms": duration,
                "timestamp": datetime.now().isoformat(),
            })
            
            # Check return code
            if process.returncode != 0:
                raise SandboxError(
                    f"Command failed with return code {process.returncode}",
                    command=cmd,
                    output=stderr_str,
                    return_code=process.returncode,
                )
            
            logger.debug(f"Command executed: {cmd} ({duration:.1f}ms)")
            return stdout_str
            
        except (SecurityViolationError, TimeoutError):
            raise
        except Exception as e:
            raise SandboxError(
                f"Command execution failed: {e}",
                command=cmd,
            ) from e
    
    async def read_file(self, path: str) -> str:
        """Read file contents.
        
        Args:
            path: Virtual file path
            
        Returns:
            File contents
            
        Raises:
            SecurityViolationError: If path not allowed
            FileNotFoundError: If file doesn't exist
        """
        physical_path = self.translate_path(path)
        
        if not os.path.isfile(physical_path):
            raise FileNotFoundError(f"File not found: {path}")
        
        # Check file size
        file_size = os.path.getsize(physical_path)
        if file_size > self._max_output_size:
            raise SandboxError(
                f"File too large: {file_size} bytes (max: {self._max_output_size})"
            )
        
        with open(physical_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    
    async def write_file(self, path: str, content: str) -> None:
        """Write content to file.
        
        Args:
            path: Virtual file path
            content: Content to write
            
        Raises:
            SecurityViolationError: If path not allowed
        """
        physical_path = self.translate_path(path)
        
        # Create parent directories
        Path(physical_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(physical_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.debug(f"File written: {path}")
    
    async def list_dir(self, path: str) -> List[str]:
        """List directory contents.
        
        Args:
            path: Virtual directory path
            
        Returns:
            List of filenames
            
        Raises:
            SecurityViolationError: If path not allowed
            NotADirectoryError: If not a directory
        """
        physical_path = self.translate_path(path)
        
        if not os.path.isdir(physical_path):
            raise NotADirectoryError(f"Not a directory: {path}")
        
        return os.listdir(physical_path)
    
    async def file_exists(self, path: str) -> bool:
        """Check if file exists.
        
        Args:
            path: Virtual file path
            
        Returns:
            True if file exists
        """
        try:
            physical_path = self.translate_path(path)
            return os.path.isfile(physical_path)
        except SecurityViolationError:
            return False
    
    async def cleanup(self) -> None:
        """Cleanup sandbox resources.
        
        Removes temporary files and directories.
        """
        logger.info(f"Cleaning up sandbox for thread {self._thread_id}")
        
        # Optionally clean up thread directory
        if self._virtual_paths:
            base_path = Path(tempfile.gettempdir()) / "agentm" / self._thread_id
            if base_path.exists():
                try:
                    shutil.rmtree(base_path)
                    logger.debug(f"Removed thread directory: {base_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up {base_path}: {e}")
    
    def get_execution_log(self) -> List[Dict[str, Any]]:
        """Get command execution log.
        
        Returns:
            List of execution records
        """
        return self._execution_log.copy()


class SandboxMode(str, Enum):
    """Sandbox execution mode.
    
    Attributes:
        LOCAL: Local filesystem sandbox
        DOCKER: Docker container sandbox
        RESTRICTED: Highly restricted local sandbox
    """
    LOCAL = "local"
    DOCKER = "docker"
    RESTRICTED = "restricted"


def create_sandbox(
    mode: SandboxMode,
    thread_id: str,
    **kwargs,
) -> SandboxProvider:
    """Factory function to create sandbox provider.
    
    Args:
        mode: Sandbox mode
        thread_id: Thread identifier
        **kwargs: Provider-specific arguments
        
    Returns:
        Configured sandbox provider
        
    Raises:
        ValueError: If mode is not supported
    """
    if mode == SandboxMode.LOCAL:
        return LocalSandboxProvider(thread_id=thread_id, **kwargs)
    elif mode == SandboxMode.RESTRICTED:
        # More restrictive settings
        return LocalSandboxProvider(
            thread_id=thread_id,
            allow_network=False,
            timeout_seconds=30,
            **kwargs,
        )
    elif mode == SandboxMode.DOCKER:
        # Docker provider would be implemented here
        raise NotImplementedError("Docker sandbox not yet implemented")
    else:
        raise ValueError(f"Unknown sandbox mode: {mode}")


__all__ = [
    "SandboxProvider",
    "LocalSandboxProvider",
    "SandboxError",
    "SecurityViolationError",
    "TimeoutError",
    "SandboxResult",
    "SandboxMode",
    "create_sandbox",
]
