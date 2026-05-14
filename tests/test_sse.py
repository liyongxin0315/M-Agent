"""
Unit tests for SSE server module.

Tests cover:
- Event formatting
- Server operations
- Client connections
- Event broadcasting
"""

import asyncio
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sse_server import (
    EventType,
    SSEEvent,
    SSEServer,
    ClientConnection,
)


class TestSSEEvent:
    """Tests for SSEEvent."""
    
    def test_create_event(self):
        """Test basic event creation."""
        event = SSEEvent(
            type=EventType.MESSAGE,
            data={"message": "Hello"},
        )
        
        assert event.type == EventType.MESSAGE
        assert event.data == {"message": "Hello"}
        assert event.id is not None
    
    def test_event_to_sse_format(self):
        """Test SSE wire format."""
        event = SSEEvent(
            type=EventType.PROGRESS,
            data={"progress": 50},
            id="event-123",
        )
        
        formatted = event.to_sse_format()
        
        assert "event: progress" in formatted
        assert 'data: {"progress": 50}' in formatted
        assert "id: event-123" in formatted
        assert formatted.endswith("\n\n")
    
    def test_event_to_dict(self):
        """Test event serialization."""
        event = SSEEvent(
            type=EventType.ERROR,
            data={"error": "Test error"},
            retry=5000,
        )
        
        data = event.to_dict()
        
        assert data["type"] == "error"
        assert data["data"]["error"] == "Test error"
        assert data["retry"] == 5000


class TestSSEServer:
    """Tests for SSEServer."""
    
    @pytest.fixture
    def server(self):
        """Create test server."""
        return SSEServer(
            heartbeat_interval=1,
            max_queue_size=100,
        )
    
    @pytest.mark.asyncio
    async def test_server_initialization(self, server):
        """Test server initialization."""
        stats = server.stats
        
        assert stats["total_connections"] == 0
        assert stats["active_connections"] == 0
        assert stats["total_events_sent"] == 0
    
    @pytest.mark.asyncio
    async def test_emit_event(self, server):
        """Test emitting events."""
        run_id = "test-run"
        
        # Emit without clients (should not fail)
        count = await server.emit(run_id, SSEEvent(
            type=EventType.MESSAGE,
            data={"test": True},
        ))
        
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_emit_run_start(self, server):
        """Test run start event."""
        count = await server.emit_run_start(
            "run-123",
            {"query": "Hello"},
        )
        
        # No clients yet
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_emit_progress(self, server):
        """Test progress event."""
        count = await server.emit_progress(
            "run-123",
            progress=50,
            message="Processing",
        )
        
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_emit_error(self, server):
        """Test error event."""
        count = await server.emit_error(
            "run-123",
            error="Something failed",
            code="ERR_TEST",
        )
        
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_emit_result(self, server):
        """Test result event."""
        count = await server.emit_result(
            "run-123",
            {"answer": "42"},
        )
        
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_end_stream(self, server):
        """Test ending stream."""
        count = await server.end_stream("run-123")
        
        assert count == 0
    
    @pytest.mark.asyncio
    async def test_get_connected_clients(self, server):
        """Test getting connected clients."""
        clients = server.get_connected_clients("run-123")
        
        assert clients == []
    
    @pytest.mark.asyncio
    async def test_cleanup_inactive(self, server):
        """Test cleaning up inactive clients."""
        removed = server.cleanup_inactive_clients()
        
        assert removed == 0
    
    @pytest.mark.asyncio
    async def test_stats_tracking(self, server):
        """Test statistics tracking."""
        # Emit multiple events
        for i in range(5):
            await server.emit(
                f"run-{i}",
                SSEEvent(type=EventType.MESSAGE, data={"i": i}),
            )
        
        stats = server.stats
        
        assert stats["total_events_sent"] == 0  # No clients
        assert stats["runs_tracked"] == set()  # No connections


class TestClientConnection:
    """Tests for ClientConnection."""
    
    @pytest.mark.asyncio
    async def test_create_connection(self):
        """Test connection creation."""
        conn = ClientConnection(
            client_id="client-123",
            run_id="run-456",
        )
        
        assert conn.client_id == "client-123"
        assert conn.run_id == "run-456"
        assert conn.connected is True
        assert conn.events_sent == 0
    
    @pytest.mark.asyncio
    async def test_send_event(self):
        """Test sending event to client."""
        conn = ClientConnection(
            client_id="client-123",
            run_id="run-456",
        )
        
        event = SSEEvent(
            type=EventType.MESSAGE,
            data={"test": True},
        )
        
        sent = await conn.send(event)
        
        assert sent is True
        assert conn.events_sent == 1
        
        # Get from queue
        queued = await conn.queue.get()
        assert queued == event
    
    @pytest.mark.asyncio
    async def test_send_to_disconnected(self):
        """Test sending to disconnected client."""
        conn = ClientConnection(
            client_id="client-123",
            run_id="run-456",
        )
        
        conn.disconnect()
        
        event = SSEEvent(
            type=EventType.MESSAGE,
            data={},
        )
        
        sent = await conn.send(event)
        
        assert sent is False
    
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnecting client."""
        conn = ClientConnection(
            client_id="client-123",
            run_id="run-456",
        )
        
        assert conn.connected is True
        
        conn.disconnect()
        
        assert conn.connected is False


class TestEventType:
    """Tests for EventType enum."""
    
    def test_event_types(self):
        """Test all event types."""
        assert EventType.RUN_START.value == "run_start"
        assert EventType.RUN_END.value == "run_end"
        assert EventType.PROGRESS.value == "progress"
        assert EventType.LOG.value == "log"
        assert EventType.ERROR.value == "error"
        assert EventType.RESULT.value == "result"
        assert EventType.MESSAGE.value == "message"
        assert EventType.HEARTBEAT.value == "heartbeat"
        assert EventType.CUSTOM.value == "custom"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
