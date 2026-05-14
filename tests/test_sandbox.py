"""
Unit tests for sandbox module.

Tests cover:
- Path translation and security
- Command execution
- File operations
- Security violations
"""

import asyncio
import pytest
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sandbox import (
    SandboxProvider,
    LocalSandboxProvider,
    SandboxError,
    SecurityViolationError,
    TimeoutError,
    SandboxMode,
    create_sandbox,
)


class TestLocalSandboxProvider:
    """Tests for LocalSandboxProvider."""
    
    @pytest.fixture
    def sandbox(self):
        """Create test sandbox."""
        return LocalSandboxProvider(
            thread_id="test-sandbox",
            timeout_seconds=10,
        )
    
    def test_initialization(self, sandbox):
        """Test sandbox initialization."""
        assert sandbox.thread_id == "test-sandbox"
        assert sandbox.provider_name == "local"
        assert len(sandbox.virtual_paths) > 0
    
    def test_path_translation(self, sandbox):
        """Test virtual to physical path translation."""
        # Valid path
        physical = sandbox.translate_path("/workspace/test.txt")
        assert physical.startswith(sandbox.virtual_paths["/workspace"])
        
        # Root virtual path
        physical = sandbox.translate_path("/workspace")
        assert physical == sandbox.virtual_paths["/workspace"]
    
    def test_path_translation_security(self, sandbox):
        """Test path traversal prevention."""
        # Attempt path traversal
        with pytest.raises(SecurityViolationError, match="traversal"):
            sandbox.translate_path("/workspace/../../../etc/passwd")
        
        # Invalid virtual path
        with pytest.raises(SecurityViolationError, match="not in allowed"):
            sandbox.translate_path("/etc/passwd")
    
    @pytest.mark.asyncio
    async def test_command_execution(self, sandbox):
        """Test basic command execution."""
        # Write a test file first
        await sandbox.write_file("/workspace/test.txt", "Hello, World!")
        
        # Read with command
        output = await sandbox.execute_command("cat /workspace/test.txt")
        
        assert "Hello, World!" in output
    
    @pytest.mark.asyncio
    async def test_command_with_cwd(self, sandbox):
        """Test command with working directory."""
        await sandbox.write_file("/workspace/subdir/file.txt", "Test")
        
        output = await sandbox.execute_command(
            "cat subdir/file.txt",
            cwd="/workspace",
        )
        
        assert "Test" in output
    
    @pytest.mark.asyncio
    async def test_command_timeout(self):
        """Test command timeout."""
        sandbox = LocalSandboxProvider(
            thread_id="timeout-test",
            timeout_seconds=1,
        )
        
        with pytest.raises(TimeoutError, match="timed out"):
            await sandbox.execute_command("sleep 5")
    
    @pytest.mark.asyncio
    async def test_dangerous_command_blocked(self, sandbox):
        """Test that dangerous commands are blocked."""
        dangerous_commands = [
            "rm -rf /",
            "rm file.txt",
            "chmod 777 /etc",
            "wget http://evil.com",
            "curl http://evil.com",
        ]
        
        for cmd in dangerous_commands:
            with pytest.raises(SecurityViolationError):
                await sandbox.execute_command(cmd)
    
    @pytest.mark.asyncio
    async def test_file_operations(self, sandbox):
        """Test file read/write operations."""
        # Write file
        content = "Test content\nLine 2\nLine 3"
        await sandbox.write_file("/workspace/test.txt", content)
        
        # Read file
        read_content = await sandbox.read_file("/workspace/test.txt")
        assert read_content == content
        
        # Check file exists
        exists = await sandbox.file_exists("/workspace/test.txt")
        assert exists is True
        
        # Check non-existent file
        exists = await sandbox.file_exists("/workspace/nonexistent.txt")
        assert exists is False
    
    @pytest.mark.asyncio
    async def test_directory_listing(self, sandbox):
        """Test directory listing."""
        # Create files
        await sandbox.write_file("/workspace/file1.txt", "1")
        await sandbox.write_file("/workspace/file2.txt", "2")
        await sandbox.write_file("/workspace/subdir/file3.txt", "3")
        
        # List root
        files = await sandbox.list_dir("/workspace")
        assert "file1.txt" in files
        assert "file2.txt" in files
        assert "subdir" in files
        
        # List subdirectory
        files = await sandbox.list_dir("/workspace/subdir")
        assert "file3.txt" in files
    
    @pytest.mark.asyncio
    async def test_file_not_found(self, sandbox):
        """Test file not found error."""
        with pytest.raises(FileNotFoundError):
            await sandbox.read_file("/workspace/nonexistent.txt")
    
    @pytest.mark.asyncio
    async def test_not_a_directory(self, sandbox):
        """Test listing a file as directory."""
        await sandbox.write_file("/workspace/file.txt", "content")
        
        with pytest.raises(NotADirectoryError):
            await sandbox.list_dir("/workspace/file.txt")
    
    @pytest.mark.asyncio
    async def test_execution_log(self, sandbox):
        """Test command execution logging."""
        await sandbox.execute_command("echo test1")
        await sandbox.execute_command("echo test2")
        
        log = sandbox.get_execution_log()
        
        assert len(log) == 2
        assert log[0]["command"] == "echo test1"
        assert log[1]["command"] == "echo test2"
        assert "duration_ms" in log[0]
    
    @pytest.mark.asyncio
    async def test_cleanup(self, sandbox):
        """Test sandbox cleanup."""
        # Create some files
        await sandbox.write_file("/workspace/test.txt", "test")
        
        # Cleanup
        await sandbox.cleanup()
        
        # Verify cleanup (implementation dependent)
        # The cleanup should remove the thread directory
    
    @pytest.mark.asyncio
    async def test_nested_directory_creation(self, sandbox):
        """Test that writing to nested paths creates directories."""
        await sandbox.write_file("/workspace/a/b/c/deep.txt", "deep content")
        
        content = await sandbox.read_file("/workspace/a/b/c/deep.txt")
        assert content == "deep content"
    
    @pytest.mark.asyncio
    async def test_large_file_handling(self, sandbox):
        """Test handling of large files."""
        # Create content larger than default limit
        large_content = "x" * (2 * 1024 * 1024)  # 2MB
        
        await sandbox.write_file("/workspace/large.txt", large_content)
        
        # Reading should fail due to size limit
        with pytest.raises(SandboxError, match="too large"):
            await sandbox.read_file("/workspace/large.txt")


class TestSandboxMode:
    """Tests for SandboxMode enum."""
    
    def test_sandbox_modes(self):
        """Test sandbox mode values."""
        assert SandboxMode.LOCAL.value == "local"
        assert SandboxMode.DOCKER.value == "docker"
        assert SandboxMode.RESTRICTED.value == "restricted"


class TestCreateSandbox:
    """Tests for sandbox factory function."""
    
    def test_create_local_sandbox(self):
        """Test creating local sandbox."""
        sandbox = create_sandbox(
            SandboxMode.LOCAL,
            thread_id="factory-test",
        )
        
        assert isinstance(sandbox, LocalSandboxProvider)
        assert sandbox.thread_id == "factory-test"
    
    def test_create_restricted_sandbox(self):
        """Test creating restricted sandbox."""
        sandbox = create_sandbox(
            SandboxMode.RESTRICTED,
            thread_id="restricted-test",
        )
        
        assert isinstance(sandbox, LocalSandboxProvider)
        # Restricted should have shorter timeout
        assert sandbox._timeout == 30
        assert sandbox._allow_network is False
    
    def test_create_unknown_mode(self):
        """Test creating sandbox with unknown mode."""
        with pytest.raises(ValueError, match="Unknown sandbox mode"):
            create_sandbox("unknown_mode", thread_id="test")
    
    def test_create_docker_not_implemented(self):
        """Test that Docker mode raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            create_sandbox(
                SandboxMode.DOCKER,
                thread_id="docker-test",
            )


class TestSecurityPatterns:
    """Tests for security pattern detection."""
    
    @pytest.mark.asyncio
    async def test_dangerous_patterns_blocked(self, sandbox):
        """Test dangerous pattern detection."""
        dangerous_patterns = [
            "echo test > /etc/passwd",
            "cat file > /proc/meminfo",
            "dd if=/dev/zero of=/dev/sda",
        ]
        
        for cmd in dangerous_patterns:
            with pytest.raises(SecurityViolationError, match="Dangerous pattern"):
                await sandbox.execute_command(cmd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
