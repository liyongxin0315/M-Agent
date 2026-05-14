"""
AgentM Core - 自主 Agent 核心系统

一个独立的自主 Agent 系统，能够：
- 自主决策和执行任务
- 持久化记忆和共享
- 事件驱动和定时任务
- 自我进化和学习

Author: AgentM Core Team
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "AgentM Core Team"

from .event_bus import EventBus, EventType, Event, get_event_bus
from .memory_store import MemoryStore, MemoryType, Memory, get_memory_store
from .scheduler import TaskScheduler, TaskPriority, TaskStatus, get_scheduler
from .autonomous_loop import AutonomousAgent, GoalStatus, get_autonomous_agent

__all__ = [
    # Event Bus
    "EventBus",
    "EventType",
    "Event",
    "get_event_bus",
    
    # Memory Store
    "MemoryStore",
    "MemoryType",
    "Memory",
    "get_memory_store",
    
    # Scheduler
    "TaskScheduler",
    "TaskPriority",
    "TaskStatus",
    "get_scheduler",
    
    # Autonomous Agent
    "AutonomousAgent",
    "GoalStatus",
    "get_autonomous_agent",
]
