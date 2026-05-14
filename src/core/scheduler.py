#!/usr/bin/env python3
"""
Task Scheduler Module - 任务调度器模块

Provides cron-based scheduling, delayed tasks, and task priority management.
定时任务调度、延迟任务和任务优先级管理。

Author: AgentM Core Team
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union
from enum import Enum
from pathlib import Path
import yaml


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """任务优先级枚举"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Task:
    """
    任务数据结构
    
    Attributes:
        task_id: 任务 ID
        name: 任务名称
        handler: 任务处理函数名（用于序列化）
        args: 位置参数
        kwargs: 关键字参数
        status: 任务状态
        priority: 优先级
        created_at: 创建时间
        scheduled_at: 计划执行时间
        started_at: 开始执行时间
        completed_at: 完成时间
        result: 执行结果
        error: 错误信息
        retry_count: 重试次数
        max_retries: 最大重试次数
        cron_expr: Cron 表达式（定时任务）
        delay_seconds: 延迟秒数（延迟任务）
    """
    task_id: str = field(default_factory=lambda: f"task_{datetime.utcnow().timestamp()}")
    name: str = "unnamed"
    handler: str = ""
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    scheduled_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    cron_expr: Optional[str] = None
    delay_seconds: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            **asdict(self),
            'status': self.status.value,
            'priority': self.priority.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """从字典创建"""
        data = data.copy()
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = TaskStatus(data['status'])
        if 'priority' in data and isinstance(data['priority'], (int, str)):
            data['priority'] = TaskPriority(int(data['priority']))
        return cls(**data)
    
    def is_due(self) -> bool:
        """检查任务是否到期"""
        try:
            scheduled = datetime.fromisoformat(self.scheduled_at.replace('Z', '+00:00'))
            return datetime.utcnow() >= scheduled
        except Exception:
            return True
    
    def should_retry(self) -> bool:
        """检查是否应该重试"""
        return self.retry_count < self.max_retries


class TaskScheduler:
    """
    任务调度器类
    
    提供功能：
    - Cron 定时任务
    - 延迟任务
    - 任务优先级队列
    - 任务执行跟踪
    - 并发控制
    
    Attributes:
        max_concurrent: 最大并发任务数
        check_interval: 检查间隔（秒）
    """
    
    def __init__(
        self,
        max_concurrent: int = 3,
        check_interval: float = 1.0
    ):
        """
        初始化任务调度器
        
        Args:
            max_concurrent: 最大并发任务数
            check_interval: 检查间隔（秒）
        """
        self._max_concurrent = max_concurrent
        self._check_interval = check_interval
        
        # 任务存储
        self._pending_tasks: List[Task] = []  # 待执行任务
        self._running_tasks: Dict[str, Task] = {}  # 运行中任务
        self._completed_tasks: List[Task] = []  # 已完成任务
        self._failed_tasks: List[Task] = []  # 失败任务
        
        # 任务处理器注册表
        self._handlers: Dict[str, Callable] = {}
        
        # 并发控制
        self._semaphore: Optional[asyncio.Semaphore] = None
        
        # 运行状态
        self._running = False
        self._task = None
        
        # 日志
        self._logger = logging.getLogger(__name__)
    
    @property
    def semaphore(self) -> asyncio.Semaphore:
        """懒加载信号量"""
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)
        return self._semaphore
    
    def register_handler(self, name: str, handler: Callable) -> None:
        """
        注册任务处理器
        
        Args:
            name: 处理器名称
            handler: 处理函数（可以是 async 或普通函数）
        """
        if not callable(handler):
            raise ValueError("Handler must be callable")
        
        self._handlers[name] = handler
        self._logger.info(f"Registered handler: {name}")
    
    def schedule(
        self,
        handler: Union[str, Callable],
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        cron_expr: Optional[str] = None,
        delay_seconds: Optional[float] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        name: Optional[str] = None
    ) -> Task:
        """
        调度任务
        
        Args:
            handler: 处理函数或函数名
            args: 位置参数
            kwargs: 关键字参数
            cron_expr: Cron 表达式（定时任务）
            delay_seconds: 延迟秒数（延迟任务）
            priority: 优先级
            name: 任务名称
        
        Returns:
            创建的 Task 对象
        
        Raises:
            ValueError: 当 handler 未注册或参数无效时
        """
        # 解析 handler
        if callable(handler):
            handler_name = handler.__name__
            self.register_handler(handler_name, handler)
        else:
            handler_name = handler
            if handler_name not in self._handlers:
                raise ValueError(f"Handler not registered: {handler_name}")
        
        # 创建任务
        task = Task(
            name=name or handler_name,
            handler=handler_name,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
            cron_expr=cron_expr,
            delay_seconds=delay_seconds
        )
        
        # 计算计划执行时间
        if delay_seconds is not None:
            scheduled_time = datetime.utcnow() + timedelta(seconds=delay_seconds)
            task.scheduled_at = scheduled_time.isoformat()
        elif cron_expr:
            # 计算下一个 cron 时间
            next_run = self._next_cron_time(cron_expr)
            task.scheduled_at = next_run.isoformat()
        
        # 添加到待执行队列
        self._pending_tasks.append(task)
        self._pending_tasks.sort(key=lambda t: (-t.priority.value, t.scheduled_at))
        
        self._logger.info(
            f"Task scheduled: {task.task_id} ({task.name}) "
            f"at {task.scheduled_at} priority={priority.name}"
        )
        
        return task
    
    def _next_cron_time(self, cron_expr: str) -> datetime:
        """
        计算下一个 cron 执行时间
        
        Args:
            cron_expr: Cron 表达式 (分 时 日 月 周)
        
        Returns:
            下一个执行时间
        """
        try:
            from croniter import croniter
            base = datetime.utcnow()
            cron = croniter(cron_expr, base)
            return cron.get_next(datetime)
        except ImportError:
            self._logger.warning("croniter not installed, using fallback")
            # 简单 fallback: 1 分钟后
            return datetime.utcnow() + timedelta(minutes=1)
        except Exception as e:
            self._logger.error(f"Invalid cron expression: {e}")
            return datetime.utcnow() + timedelta(minutes=1)
    
    async def run_pending(self) -> None:
        """
        运行待处理任务（后台循环）
        
        持续检查待执行任务，执行到期的任务。
        应该在独立的任务/线程中运行。
        """
        self._running = True
        self._logger.info("Task scheduler started")
        
        while self._running:
            try:
                # 检查待执行任务
                await self._check_and_execute()
                
                # 等待下一次检查
                await asyncio.sleep(self._check_interval)
                
            except asyncio.CancelledError:
                self._logger.info("Task scheduler cancelled")
                break
            except Exception as e:
                self._logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(self._check_interval)
        
        self._logger.info("Task scheduler stopped")
    
    async def _check_and_execute(self) -> None:
        """检查并执行到期任务"""
        now = datetime.utcnow()
        
        # 找出到期的任务
        due_tasks = []
        remaining = []
        
        for task in self._pending_tasks:
            if task.is_due():
                due_tasks.append(task)
            else:
                remaining.append(task)
        
        self._pending_tasks = remaining
        
        # 执行到期任务（按优先级排序）
        due_tasks.sort(key=lambda t: -t.priority.value)
        
        for task in due_tasks:
            await self._execute_task(task)
    
    async def _execute_task(self, task: Task) -> None:
        """
        执行单个任务
        
        Args:
            task: 要执行的任务
        """
        # 获取处理器
        handler = self._handlers.get(task.handler)
        if not handler:
            self._logger.error(f"Handler not found: {task.handler}")
            task.status = TaskStatus.FAILED
            task.error = f"Handler not found: {task.handler}"
            self._failed_tasks.append(task)
            return
        
        # 更新状态
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow().isoformat()
        self._running_tasks[task.task_id] = task
        
        self._logger.info(f"Executing task: {task.task_id} ({task.name})")
        
        # 异步执行（带并发控制）
        async with self.semaphore:
            try:
                # 执行处理器
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(*task.args, **task.kwargs)
                else:
                    result = handler(*task.args, **task.kwargs)
                
                # 成功完成
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow().isoformat()
                task.result = result
                self._completed_tasks.append(task)
                
                self._logger.info(f"Task completed: {task.task_id}")
                
                # 如果是 cron 任务，重新调度
                if task.cron_expr:
                    self._reschedule_cron_task(task)
                
            except Exception as e:
                self._logger.error(f"Task failed: {task.task_id} - {e}")
                task.error = str(e)
                
                # 检查是否重试
                if task.should_retry():
                    task.retry_count += 1
                    task.status = TaskStatus.PENDING
                    task.started_at = None
                    # 指数退避
                    delay = min(2 ** task.retry_count, 60)
                    task.scheduled_at = (
                        datetime.utcnow() + timedelta(seconds=delay)
                    ).isoformat()
                    self._pending_tasks.append(task)
                    self._logger.info(
                        f"Task scheduled for retry: {task.task_id} "
                        f"(attempt {task.retry_count}/{task.max_retries})"
                    )
                else:
                    task.status = TaskStatus.FAILED
                    task.completed_at = datetime.utcnow().isoformat()
                    self._failed_tasks.append(task)
            
            finally:
                # 从运行中移除
                if task.task_id in self._running_tasks:
                    del self._running_tasks[task.task_id]
    
    def _reschedule_cron_task(self, task: Task) -> None:
        """重新调度 cron 任务"""
        if not task.cron_expr:
            return
        
        # 创建新任务实例
        new_task = Task(
            name=task.name,
            handler=task.handler,
            args=task.args,
            kwargs=task.kwargs,
            priority=task.priority,
            cron_expr=task.cron_expr,
            max_retries=task.max_retries
        )
        
        # 计算下一个执行时间
        next_run = self._next_cron_time(task.cron_expr)
        new_task.scheduled_at = next_run.isoformat()
        
        # 添加到待执行队列
        self._pending_tasks.append(new_task)
        self._pending_tasks.sort(key=lambda t: (-t.priority.value, t.scheduled_at))
        
        self._logger.info(
            f"Cron task rescheduled: {new_task.task_id} next run at {next_run}"
        )
    
    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务 ID
        
        Returns:
            bool: 是否成功取消
        """
        # 检查待执行任务
        for i, task in enumerate(self._pending_tasks):
            if task.task_id == task_id:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.utcnow().isoformat()
                self._pending_tasks.pop(i)
                self._logger.info(f"Task cancelled: {task_id}")
                return True
        
        # 检查运行中任务（标记为取消，实际停止需要处理器配合）
        if task_id in self._running_tasks:
            self._running_tasks[task_id].status = TaskStatus.CANCELLED
            self._logger.warning(
                f"Task cancellation requested for running task: {task_id}"
            )
            return True
        
        return False
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        获取任务
        
        Args:
            task_id: 任务 ID
        
        Returns:
            Task 对象或 None
        """
        # 检查所有队列
        all_tasks = (
            self._pending_tasks +
            list(self._running_tasks.values()) +
            self._completed_tasks +
            self._failed_tasks
        )
        
        for task in all_tasks:
            if task.task_id == task_id:
                return task
        
        return None
    
    def get_pending_count(self) -> int:
        """获取待执行任务数量"""
        return len(self._pending_tasks)
    
    def get_running_count(self) -> int:
        """获取运行中任务数量"""
        return len(self._running_tasks)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取调度器统计信息
        
        Returns:
            统计信息字典
        """
        return {
            "pending": len(self._pending_tasks),
            "running": len(self._running_tasks),
            "completed": len(self._completed_tasks),
            "failed": len(self._failed_tasks),
            "handlers": list(self._handlers.keys()),
            "max_concurrent": self._max_concurrent
        }
    
    def stop(self) -> None:
        """停止调度器"""
        self._running = False
        self._logger.info("Task scheduler stop requested")
    
    @property
    def is_running(self) -> bool:
        """检查调度器是否正在运行"""
        return self._running


# 全局单例
_scheduler: Optional[TaskScheduler] = None


def get_scheduler() -> TaskScheduler:
    """
    获取全局调度器单例
    
    Returns:
        TaskScheduler 实例
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler


async def main():
    """调度器独立进程入口（用于测试）"""
    import yaml
    
    # 加载配置
    config_path = Path(__file__).parent.parent / "config.yaml"
    config = {}
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    
    scheduler_config = config.get('scheduler', {})
    
    # 创建调度器
    scheduler = TaskScheduler(
        max_concurrent=scheduler_config.get('max_concurrent', 3),
        check_interval=scheduler_config.get('check_interval', 1.0)
    )
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 注册测试处理器
    async def test_handler(message: str):
        logging.info(f"Test handler executing: {message}")
        await asyncio.sleep(1)
        return f"Completed: {message}"
    
    scheduler.register_handler("test_handler", test_handler)
    
    # 调度测试任务
    scheduler.schedule(
        handler="test_handler",
        args=("Hello from scheduler!",),
        delay_seconds=2,
        priority=TaskPriority.NORMAL,
        name="Test Delayed Task"
    )
    
    logging.info("Task Scheduler initialized and test task scheduled")
    
    # 启动调度器（运行 10 秒后停止）
    try:
        scheduler._running = True
        for _ in range(10):
            await scheduler._check_and_execute()
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logging.info("Shutting down scheduler...")
    finally:
        scheduler.stop()
    
    # 输出统计
    stats = scheduler.get_statistics()
    logging.info(f"Statistics: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
