"""
SSE (Server-Sent Events) Server for AgentM.

This module provides real-time event streaming to clients using the SSE
protocol. SSE allows the server to push events to clients over a single
HTTP connection, ideal for streaming execution progress, logs, and results.

Design Philosophy:
- Simple protocol: SSE is lighter than WebSockets for one-way streaming
- Event typing: Structured event types for client handling
- Connection management: Track and handle client disconnections
- Backpressure: Handle slow clients gracefully

Protocol Format:
    event: {event_type}
    data: {json_payload}
    id: {event_id}
    
    (blank line)

Event Types:
    - run_start: Execution started
    - run_end: Execution completed
    - progress: Progress update
    - log: Log message
    - error: Error occurred
    - result: Final result

Example Usage (Server):
    >>> from fastapi import FastAPI
    >>> from .sse_server import SSEServer, EventType, SSEEvent
    >>> 
    >>> app = FastAPI()
    >>> sse_server = SSEServer()
    >>> 
    >>> @app.post("/runs/{run_id}/stream")
    >>> async def stream_run(run_id: str, request: Request):
    ...     return await sse_server.create_stream(run_id, request)
    >>> 
    >>> # Emit events
    >>> await sse_server.emit(
    ...     run_id,
    ...     SSEEvent(
    ...         type=EventType.PROGRESS,
    ...         data={"progress": 50, "message": "Processing..."},
    ...     )
    ... )

Example Usage (Client):
    >>> const eventSource = new EventSource('/runs/abc123/stream');
    >>> eventSource.addEventListener('progress', (event) => {
    ...     const data = JSON.parse(event.data);
    ...     console.log(`Progress: ${data.progress}%`);
    ... });
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """SSE event types.
    
    Attributes:
        RUN_START: Execution started
        RUN_END: Execution completed
        PROGRESS: Progress update
        LOG: Log message
        ERROR: Error occurred
        RESULT: Final result
        MESSAGE: General message
        HEARTBEAT: Connection keepalive
        CUSTOM: Custom event type
    """
    RUN_START = "run_start"
    RUN_END = "run_end"
    PROGRESS = "progress"
    LOG = "log"
    ERROR = "error"
    RESULT = "result"
    MESSAGE = "message"
    HEARTBEAT = "heartbeat"
    CUSTOM = "custom"


@dataclass
class SSEEvent:
    """Server-Sent Event.
    
    Attributes:
        type: Event type
        data: Event payload (will be JSON serialized)
        id: Event ID (optional, auto-generated)
        timestamp: Event timestamp
        retry: Retry interval in ms (for client reconnection)
    """
    type: EventType
    data: Any
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    retry: Optional[int] = None
    
    def to_sse_format(self) -> str:
        """Convert to SSE wire format.
        
        Returns:
            SSE formatted string
        """
        lines = [
            f"event: {self.type.value}",
            f"data: {json.dumps(self.data, default=str, ensure_ascii=False)}",
        ]
        
        if self.id:
            lines.append(f"id: {self.id}")
        
        if self.retry is not None:
            lines.append(f"retry: {self.retry}")
        
        # SSE format requires blank line at end
        lines.append("")
        lines.append("")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "data": self.data,
            "id": self.id,
            "timestamp": self.timestamp,
            "retry": self.retry,
        }


@dataclass
class ClientConnection:
    """Represents a connected SSE client.
    
    Attributes:
        client_id: Unique client identifier
        run_id: Associated run ID
        queue: Event queue for this client
        connected: Connection status
        connected_at: Connection timestamp
        last_activity: Last activity timestamp
        events_sent: Number of events sent
    """
    client_id: str
    run_id: str
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    connected: bool = True
    connected_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_activity: str = field(default_factory=lambda: datetime.now().isoformat())
    events_sent: int = 0
    
    async def send(self, event: SSEEvent) -> bool:
        """Send event to client.
        
        Args:
            event: Event to send
            
        Returns:
            True if sent, False if client disconnected
        """
        if not self.connected:
            return False
        
        await self.queue.put(event)
        self.last_activity = datetime.now().isoformat()
        self.events_sent += 1
        return True
    
    def disconnect(self) -> None:
        """Mark client as disconnected."""
        self.connected = False


class SSEConnectionError(Exception):
    """Raised when SSE connection fails."""
    pass


class SSEServer:
    """SSE server for real-time event streaming.
    
    The SSE server manages client connections and event distribution.
    It supports:
    - Multiple clients per run
    - Event broadcasting
    - Connection lifecycle management
    - Heartbeat for keepalive
    
    Attributes:
        heartbeat_interval: Seconds between heartbeats
        max_queue_size: Maximum events per client queue
        client_timeout: Seconds before inactive client is removed
    
    Example:
        >>> server = SSEServer(heartbeat_interval=30)
        >>> 
        >>> @app.get("/stream/{run_id}")
        >>> async def stream(run_id: str, request: Request):
        ...     return await server.create_stream(run_id, request)
        >>> 
        >>> # Emit events
        >>> await server.emit_run_start("run123", {"query": "Hello"})
        >>> await server.emit_progress("run123", 50, "Processing...")
        >>> await server.emit_result("run123", {"answer": "World"})
    """
    
    # Sentinel value for end of stream
    END_SENTINEL = object()
    HEARTBEAT_SENTINEL = object()
    
    def __init__(
        self,
        heartbeat_interval: float = 30.0,
        max_queue_size: int = 1000,
        client_timeout: float = 300.0,
    ):
        """Initialize SSE server.
        
        Args:
            heartbeat_interval: Seconds between heartbeat events
            max_queue_size: Maximum events in client queue
            client_timeout: Seconds before removing inactive clients
        """
        self._heartbeat_interval = heartbeat_interval
        self._max_queue_size = max_queue_size
        self._client_timeout = client_timeout
        
        # Connection tracking: run_id -> {client_id -> ClientConnection}
        self._connections: Dict[str, Dict[str, ClientConnection]] = {}
        self._lock = asyncio.Lock()
        
        # Statistics
        self._stats = {
            "total_connections": 0,
            "active_connections": 0,
            "total_events_sent": 0,
            "runs_tracked": set(),
        }
        
        logger.info("SSEServer initialized")
    
    @property
    def stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        return {
            **self._stats,
            "active_connections": sum(
                len(conns) for conns in self._connections.values()
            ),
        }
    
    async def create_stream(
        self,
        run_id: str,
        request: Any,
    ) -> AsyncGenerator[str, None]:
        """Create SSE stream for client.
        
        This is an async generator that yields SSE-formatted events.
        Use with FastAPI's StreamingResponse.
        
        Args:
            run_id: Run identifier
            request: HTTP request object (for disconnect detection)
            
        Yields:
            SSE-formatted event strings
        """
        client_id = str(uuid.uuid4())
        connection = ClientConnection(client_id=client_id, run_id=run_id)
        
        async with self._lock:
            if run_id not in self._connections:
                self._connections[run_id] = {}
            self._connections[run_id][client_id] = connection
            self._stats["total_connections"] += 1
            self._stats["runs_tracked"].add(run_id)
        
        logger.info(f"Client {client_id} connected to run {run_id}")
        
        try:
            # Send connection event
            await connection.send(SSEEvent(
                type=EventType.MESSAGE,
                data={"message": "Connected", "client_id": client_id},
            ))
            
            # Event generator
            async def event_generator():
                while connection.connected:
                    try:
                        # Wait for event with timeout
                        event = await asyncio.wait_for(
                            connection.queue.get(),
                            timeout=self._heartbeat_interval,
                        )
                        
                        if event is self.END_SENTINEL:
                            # End of stream
                            yield SSEEvent(
                                type=EventType.RUN_END,
                                data={"message": "Stream ended"},
                            ).to_sse_format()
                            break
                        
                        if event is self.HEARTBEAT_SENTINEL:
                            # Heartbeat
                            yield SSEEvent(
                                type=EventType.HEARTBEAT,
                                data={"timestamp": datetime.now().isoformat()},
                            ).to_sse_format()
                            continue
                        
                        # Regular event
                        yield event.to_sse_format()
                        
                    except asyncio.TimeoutError:
                        # Send heartbeat on timeout
                        yield SSEEvent(
                            type=EventType.HEARTBEAT,
                            data={"timestamp": datetime.now().isoformat()},
                        ).to_sse_format()
                    
                    # Check for client disconnect
                    if hasattr(request, 'is_disconnected'):
                        if await request.is_disconnected():
                            logger.debug(f"Client {client_id} disconnected")
                            break
            
            async for event_data in event_generator():
                yield event_data
                
        except Exception as e:
            logger.error(f"Stream error for client {client_id}: {e}")
            raise
        finally:
            # Cleanup
            connection.disconnect()
            async with self._lock:
                if run_id in self._connections:
                    self._connections[run_id].pop(client_id, None)
                    if not self._connections[run_id]:
                        del self._connections[run_id]
            
            logger.info(f"Client {client_id} disconnected from run {run_id}")
    
    async def emit(self, run_id: str, event: SSEEvent) -> int:
        """Emit event to all clients subscribed to run.
        
        Args:
            run_id: Run identifier
            event: Event to emit
            
        Returns:
            Number of clients that received the event
        """
        async with self._lock:
            if run_id not in self._connections:
                return 0
            
            clients = self._connections[run_id]
            sent_count = 0
            
            for client in clients.values():
                if client.connected:
                    try:
                        # Non-blocking send with queue size check
                        if client.queue.qsize() < self._max_queue_size:
                            await client.send(event)
                            sent_count += 1
                        else:
                            logger.warning(
                                f"Client {client.client_id} queue full, dropping event"
                            )
                    except Exception as e:
                        logger.error(f"Failed to send to client: {e}")
                        client.disconnect()
            
            self._stats["total_events_sent"] += sent_count
            return sent_count
    
    async def emit_to_client(
        self,
        run_id: str,
        client_id: str,
        event: SSEEvent,
    ) -> bool:
        """Emit event to specific client.
        
        Args:
            run_id: Run identifier
            client_id: Target client
            event: Event to emit
            
        Returns:
            True if sent successfully
        """
        async with self._lock:
            if run_id not in self._connections:
                return False
            
            client = self._connections[run_id].get(client_id)
            if not client or not client.connected:
                return False
            
            await client.send(event)
            self._stats["total_events_sent"] += 1
            return True
    
    async def emit_run_start(
        self,
        run_id: str,
        data: Dict[str, Any],
    ) -> int:
        """Emit run start event.
        
        Args:
            run_id: Run identifier
            data: Event data
            
        Returns:
            Number of clients reached
        """
        return await self.emit(run_id, SSEEvent(
            type=EventType.RUN_START,
            data=data,
        ))
    
    async def emit_run_end(
        self,
        run_id: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Emit run end event.
        
        Args:
            run_id: Run identifier
            data: Event data
            
        Returns:
            Number of clients reached
        """
        return await self.emit(run_id, SSEEvent(
            type=EventType.RUN_END,
            data=data or {},
        ))
    
    async def emit_progress(
        self,
        run_id: str,
        progress: float,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Emit progress event.
        
        Args:
            run_id: Run identifier
            progress: Progress percentage (0-100)
            message: Progress message
            metadata: Additional metadata
            
        Returns:
            Number of clients reached
        """
        data = {
            "progress": progress,
            "message": message or "",
            "timestamp": datetime.now().isoformat(),
        }
        if metadata:
            data["metadata"] = metadata
        
        return await self.emit(run_id, SSEEvent(
            type=EventType.PROGRESS,
            data=data,
        ))
    
    async def emit_log(
        self,
        run_id: str,
        message: str,
        level: str = "info",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Emit log event.
        
        Args:
            run_id: Run identifier
            message: Log message
            level: Log level (debug/info/warning/error)
            metadata: Additional metadata
            
        Returns:
            Number of clients reached
        """
        data = {
            "message": message,
            "level": level,
            "timestamp": datetime.now().isoformat(),
        }
        if metadata:
            data["metadata"] = metadata
        
        return await self.emit(run_id, SSEEvent(
            type=EventType.LOG,
            data=data,
        ))
    
    async def emit_error(
        self,
        run_id: str,
        error: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Emit error event.
        
        Args:
            run_id: Run identifier
            error: Error message
            code: Error code
            details: Additional details
            
        Returns:
            Number of clients reached
        """
        data = {
            "error": error,
            "code": code,
            "timestamp": datetime.now().isoformat(),
        }
        if details:
            data["details"] = details
        
        return await self.emit(run_id, SSEEvent(
            type=EventType.ERROR,
            data=data,
        ))
    
    async def emit_result(
        self,
        run_id: str,
        result: Any,
    ) -> int:
        """Emit result event.
        
        Args:
            run_id: Run identifier
            result: Result data
            
        Returns:
            Number of clients reached
        """
        return await self.emit(run_id, SSEEvent(
            type=EventType.RESULT,
            data=result,
        ))
    
    async def end_stream(self, run_id: str) -> int:
        """End stream for all clients subscribed to run.
        
        Args:
            run_id: Run identifier
            
        Returns:
            Number of clients notified
        """
        async with self._lock:
            if run_id not in self._connections:
                return 0
            
            clients = self._connections[run_id]
            for client in clients.values():
                await client.queue.put(self.END_SENTINEL)
            
            count = len(clients)
            logger.info(f"Ended stream for run {run_id} ({count} clients)")
            return count
    
    def get_connected_clients(self, run_id: str) -> List[str]:
        """Get list of connected client IDs for run.
        
        Args:
            run_id: Run identifier
            
        Returns:
            List of client IDs
        """
        if run_id not in self._connections:
            return []
        
        return [
            client.client_id
            for client in self._connections[run_id].values()
            if client.connected
        ]
    
    def cleanup_inactive_clients(self) -> int:
        """Remove clients that have been inactive too long.
        
        Returns:
            Number of clients removed
        """
        removed = 0
        now = datetime.now()
        
        for run_id, clients in list(self._connections.items()):
            for client_id, client in list(clients.items()):
                last_activity = datetime.fromisoformat(client.last_activity)
                inactive_seconds = (now - last_activity).total_seconds()
                
                if inactive_seconds > self._client_timeout:
                    client.disconnect()
                    del clients[client_id]
                    removed += 1
            
            if not clients:
                del self._connections[run_id]
        
        if removed > 0:
            logger.info(f"Cleaned up {removed} inactive clients")
        
        return removed


# FastAPI integration helpers
def create_sse_response(
    event_generator: AsyncGenerator[str, None],
    headers: Optional[Dict[str, str]] = None,
) -> Any:
    """Create FastAPI StreamingResponse for SSE.
    
    Args:
        event_generator: Async generator yielding SSE events
        headers: Additional headers
        
    Returns:
        StreamingResponse instance
    """
    from fastapi.responses import StreamingResponse
    
    default_headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # Disable nginx buffering
        "Content-Type": "text/event-stream",
    }
    
    if headers:
        default_headers.update(headers)
    
    return StreamingResponse(
        event_generator,
        media_type="text/event-stream",
        headers=default_headers,
    )


__all__ = [
    "EventType",
    "SSEEvent",
    "SSEServer",
    "ClientConnection",
    "SSEConnectionError",
    "create_sse_response",
]
