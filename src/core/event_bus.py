#!/usr/bin/env python3
"""
Event Bus Module - 事件总线模块

Provides publish/subscribe event handling with persistence support.
事件发布/订阅系统，支持事件持久化。

Author: AgentM Core Team
"""

import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import aiofiles


class EventType(str, Enum):
    """预定义事件类型"""
    GOAL_SET = "goal.set"
    GOAL_COMPLETED = "goal.completed"
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    MEMORY_ADDED = "memory.added"
    MEMORY_RETRIEVED = "memory.retrieved"
    REFLECTION_STARTED = "reflection.started"
    REFLECTION_COMPLETED = "reflection.completed"
    SYSTEM_STARTED = "system.started"
    SYSTEM_STOPPED = "system.stopped"
    CUSTOM = "custom"


@dataclass
class Event:
    """事件数据结构"""
    event_type: str
    data: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    event_id: str = field(default_factory=lambda: f"evt_{datetime.utcnow().timestamp()}")
    source: str = "unknown"
    priority: int = 0  # 高优先级事件优先处理
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """从字典创建"""
        return cls(**data)


class EventBus:
    """
    事件总线类
    
    提供异步事件发布/订阅功能，支持：
    - 多订阅者注册
    - 事件队列管理
    - 事件持久化
    - 优先级处理
    
    Attributes:
        persistence_path: 事件持久化文件路径
        queue_size: 事件队列最大大小
        retry_attempts: 失败重试次数
    """
    
    def __init__(
        self,
        persistence_path: Optional[str] = None,
        queue_size: int = 1000,
        retry_attempts: int = 3,
        retry_delay: float = 1.0
    ):
        """
        初始化事件总线
        
        Args:
            persistence_path: 事件持久化文件路径
            queue_size: 事件队列最大大小
            retry_attempts: 失败重试次数
            retry_delay: 重试延迟（秒）
        """
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._persistence_path = Path(persistence_path) if persistence_path else None
        self._queue_size = queue_size
        self._retry_attempts = retry_attempts
        self._retry_delay = retry_delay
        self._running = False
        self._logger = logging.getLogger(__name__)
        
        # 确保持久化目录存在
        if self._persistence_path:
            self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
    
    def subscribe(self, event_type: str, handler: Callable) -> None:
        """
        订阅事件
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数 (async def handler(event: Event))
        
        Raises:
            ValueError: 当 handler 不是可调用对象时
        """
        if not callable(handler):
            raise ValueError("Handler must be callable")
        
        self._subscribers[event_type].append(handler)
        self._logger.info(f"Subscribed handler to event type: {event_type}")
    
    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """
        取消订阅
        
        Args:
            event_type: 事件类型
            handler: 要移除的处理函数
        
        Returns:
            bool: 是否成功移除
        """
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            self._logger.info(f"Unsubscribed handler from event type: {event_type}")
            return True
        return False
    
    async def publish(self, event_type: str, data: Dict[str, Any], 
                     source: str = "unknown", priority: int = 0) -> bool:
        """
        发布事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
            source: 事件来源
            priority: 优先级（数字越大优先级越高）
        
        Returns:
            bool: 是否成功发布
        """
        event = Event(
            event_type=event_type,
            data=data,
            source=source,
            priority=priority
        )
        
        try:
            # 非阻塞放入队列
            self._event_queue.put_nowait(event)
            self._logger.debug(f"Event published: {event.event_id} ({event_type})")
            
            # 持久化事件
            if self._persistence_path:
                await self._persist_event(event)
            
            return True
            
        except asyncio.QueueFull:
            self._logger.warning(f"Event queue full, dropping event: {event_type}")
            return False
        except Exception as e:
            self._logger.error(f"Failed to publish event: {e}")
            return False
    
    async def _persist_event(self, event: Event) -> None:
        """
        持久化事件到文件
        
        Args:
            event: 要持久化的事件
        """
        if not self._persistence_path:
            return
        
        try:
            async with aiofiles.open(self._persistence_path, 'a') as f:
                await f.write(json.dumps(event.to_dict()) + '\n')
        except Exception as e:
            self._logger.error(f"Failed to persist event: {e}")
    
    async def process_events(self) -> None:
        """
        处理事件队列中的事件（后台循环）
        
        持续从队列中取出事件并分发给订阅者。
        应该在独立的任务/线程中运行。
        """
        self._running = True
        self._logger.info("Event bus processing started")
        
        while self._running:
            try:
                # 带超时获取事件，便于优雅退出
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                
                # 分发给订阅者
                await self._dispatch_event(event)
                self._event_queue.task_done()
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self._logger.error(f"Error processing event: {e}")
        
        self._logger.info("Event bus processing stopped")
    
    async def _dispatch_event(self, event: Event) -> None:
        """
        分发事件给所有订阅者
        
        Args:
            event: 要分发的事件
        """
        handlers = self._subscribers.get(event.event_type, [])
        
        # 也触发通配符订阅
        handlers.extend(self._subscribers.get("*", []))
        
        if not handlers:
            self._logger.debug(f"No handlers for event: {event.event_type}")
            return
        
        # 并发执行所有处理器
        tasks = []
        for handler in handlers:
            task = self._safe_execute_handler(handler, event)
            tasks.append(task)
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 记录失败的处理器
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self._logger.error(
                        f"Handler {i} failed for event {event.event_id}: {result}"
                    )
    
    async def _safe_execute_handler(
        self,
        handler: Callable,
        event: Event
    ) -> Any:
        """
        安全执行处理器，带重试机制
        
        Args:
            handler: 处理器函数
            event: 事件对象
        
        Returns:
            处理器返回值或异常
        """
        for attempt in range(self._retry_attempts):
            try:
                if asyncio.iscoroutinefunction(handler):
                    return await handler(event)
                else:
                    return handler(event)
            except Exception as e:
                if attempt == self._retry_attempts - 1:
                    raise
                await asyncio.sleep(self._retry_delay)
    
    def stop(self) -> None:
        """停止事件处理循环"""
        self._running = False
        self._logger.info("Event bus stop requested")
    
    @property
    def is_running(self) -> bool:
        """检查事件总线是否正在运行"""
        return self._running
    
    @property
    def queue_size(self) -> int:
        """当前队列中的事件数量"""
        return self._event_queue.qsize()
    
    async def load_events(self, limit: int = 100) -> List[Event]:
        """
        从持久化存储加载历史事件
        
        Args:
            limit: 最大加载数量
        
        Returns:
            事件列表
        """
        if not self._persistence_path or not self._persistence_path.exists():
            return []
        
        events = []
        try:
            async with aiofiles.open(self._persistence_path, 'r') as f:
                async for line in f:
                    if len(events) >= limit:
                        break
                    try:
                        event_data = json.loads(line.strip())
                        events.append(Event.from_dict(event_data))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            self._logger.error(f"Failed to load events: {e}")
        
        return events


# 全局单例
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """
    获取全局事件总线单例
    
    Returns:
        EventBus 实例
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def main():
    """事件总线独立进程入口"""
    import yaml
    
    # 加载配置
    config_path = Path(__file__).parent.parent / "config.yaml"
    config = {}
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    
    event_config = config.get('event_bus', {})
    
    # 创建事件总线
    bus = EventBus(
        persistence_path=event_config.get('persistence_path'),
        queue_size=event_config.get('queue_size', 1000),
        retry_attempts=event_config.get('retry_attempts', 3),
        retry_delay=event_config.get('retry_delay', 1.0)
    )
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 注册示例处理器
    async def log_handler(event: Event):
        logging.info(f"Event received: {event.event_type} from {event.source}")
    
    bus.subscribe("*", log_handler)
    
    # 发布系统启动事件
    await bus.publish(
        EventType.SYSTEM_STARTED.value,
        {"message": "Event bus started"},
        source="event_bus"
    )
    
    # 启动事件处理循环
    try:
        await bus.process_events()
    except KeyboardInterrupt:
        logging.info("Shutting down event bus...")
        bus.stop()
        await bus.publish(
            EventType.SYSTEM_STOPPED.value,
            {"message": "Event bus stopped"},
            source="event_bus"
        )


if __name__ == "__main__":
    asyncio.run(main())
