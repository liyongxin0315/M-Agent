"""
AgentM 熔断器模块

实现多级熔断机制（节点级/工作流级/系统级）
支持降级策略、状态监控和告警
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常状态，允许请求通过
    OPEN = "open"          # 熔断状态，拒绝请求
    HALF_OPEN = "half_open"  # 半开状态，允许部分请求测试


class FallbackStrategy(Enum):
    """降级策略"""
    RETURN_DEFAULT = "return_default"      # 返回默认值
    RETURN_CACHE = "return_cache"          # 返回缓存值
    CALL_BACKUP = "call_backup"            # 调用备用服务
    FAIL_FAST = "fail_fast"                # 快速失败
    RETRY_ONCE = "retry_once"              # 重试一次
    GRACEFUL_DEGRADE = "graceful_degrade"  # 优雅降级


@dataclass
class CircuitStats:
    """熔断器统计信息"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rejected_requests: int = 0
    fallback_invocations: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_change_times: List[datetime] = field(default_factory=list)
    
    def success_rate(self) -> float:
        """计算成功率"""
        if self.total_requests == 0:
            return 100.0
        return (self.successful_requests / self.total_requests) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "rejected_requests": self.rejected_requests,
            "fallback_invocations": self.fallback_invocations,
            "success_rate_percent": round(self.success_rate(), 2),
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success": self.last_success_time.isoformat() if self.last_success_time else None
        }


@dataclass
class CircuitConfig:
    """熔断器配置"""
    failure_threshold: int = 5          # 失败阈值，达到后触发熔断
    success_threshold: int = 3          # 成功阈值，半开状态下需要多少次成功才能恢复
    recovery_timeout_seconds: float = 30.0  # 恢复超时时间（秒）
    half_open_max_requests: int = 3     # 半开状态允许的最大请求数
    timeout_seconds: Optional[float] = None  # 请求超时时间
    fallback_strategy: FallbackStrategy = FallbackStrategy.FAIL_FAST
    default_value: Any = None           # 默认返回值
    cache_key: Optional[str] = None     # 缓存键
    backup_function: Optional[Callable] = None  # 备用函数
    enabled: bool = True                # 是否启用熔断器
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_threshold": self.failure_threshold,
            "success_threshold": self.success_threshold,
            "recovery_timeout_seconds": self.recovery_timeout_seconds,
            "half_open_max_requests": self.half_open_max_requests,
            "timeout_seconds": self.timeout_seconds,
            "fallback_strategy": self.fallback_strategy.value,
            "default_value": self.default_value,
            "enabled": self.enabled
        }


class CircuitBreakerError(Exception):
    """熔断器异常"""
    def __init__(self, message: str, circuit_name: str, state: CircuitState):
        super().__init__(message)
        self.circuit_name = circuit_name
        self.state = state


class CircuitBreakerOpen(CircuitBreakerError):
    """熔断器打开异常"""
    pass


class CircuitBreaker:
    """
    熔断器实现
    
    特性:
    - 三级状态：CLOSED -> OPEN -> HALF_OPEN -> CLOSED
    - 可配置的失败/成功阈值
    - 支持多种降级策略
    - 线程安全的状态管理
    - 详细的统计信息
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitConfig] = None
    ):
        self.name = name
        self.config = config or CircuitConfig()
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._failure_count = 0
        self._success_count = 0
        self._half_open_requests = 0
        self._opened_at: Optional[datetime] = None
        self._lock = asyncio.Lock()
        
        # 回调函数
        self._on_state_change: Optional[Callable[[CircuitState, CircuitState], None]] = None
        self._on_failure: Optional[Callable[[Exception], None]] = None
        self._on_fallback: Optional[Callable[[], None]] = None
    
    @property
    def state(self) -> CircuitState:
        """获取当前状态"""
        return self._state
    
    @property
    def stats(self) -> CircuitStats:
        """获取统计信息"""
        return self._stats
    
    def on_state_change(self, callback: Callable[[CircuitState, CircuitState], None]) -> None:
        """注册状态变化回调"""
        self._on_state_change = callback
    
    def on_failure(self, callback: Callable[[Exception], None]) -> None:
        """注册失败回调"""
        self._on_failure = callback
    
    def on_fallback(self, callback: Callable[[], None]) -> None:
        """注册降级回调"""
        self._on_fallback = callback
    
    async def _change_state(self, new_state: CircuitState) -> None:
        """改变状态"""
        old_state = self._state
        if old_state == new_state:
            return
        
        self._state = new_state
        self._stats.state_change_times.append(datetime.now())
        
        logger.info(f"[{self.name}] 状态变更：{old_state.value} -> {new_state.value}")
        
        if new_state == CircuitState.OPEN:
            self._opened_at = datetime.now()
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_requests = 0
            self._success_count = 0
        elif new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
        
        if self._on_state_change:
            try:
                self._on_state_change(old_state, new_state)
            except Exception as e:
                logger.error(f"[{self.name}] 状态变化回调失败：{e}")
    
    async def _should_allow_request(self) -> bool:
        """判断是否允许请求"""
        if not self.config.enabled:
            return True
        
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            if self._state == CircuitState.OPEN:
                # 检查是否超过恢复超时时间
                if self._opened_at:
                    elapsed = (datetime.now() - self._opened_at).total_seconds()
                    if elapsed >= self.config.recovery_timeout_seconds:
                        await self._change_state(CircuitState.HALF_OPEN)
                        return True
                return False
            
            if self._state == CircuitState.HALF_OPEN:
                # 半开状态只允许有限请求
                if self._half_open_requests < self.config.half_open_max_requests:
                    self._half_open_requests += 1
                    return True
                return False
        
        return False
    
    async def _record_success(self) -> None:
        """记录成功"""
        async with self._lock:
            self._stats.successful_requests += 1
            self._stats.last_success_time = datetime.now()
            
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    await self._change_state(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                # 在关闭状态下成功，减少失败计数
                self._failure_count = max(0, self._failure_count - 1)
    
    async def _record_failure(self, error: Exception) -> None:
        """记录失败"""
        async with self._lock:
            self._stats.failed_requests += 1
            self._stats.last_failure_time = datetime.now()
            
            if self._on_failure:
                try:
                    self._on_failure(error)
                except Exception as e:
                    logger.error(f"[{self.name}] 失败回调失败：{e}")
            
            if self._state == CircuitState.HALF_OPEN:
                # 半开状态下失败，立即打开
                await self._change_state(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.config.failure_threshold:
                    await self._change_state(CircuitState.OPEN)
    
    async def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        执行受保护的函数
        
        Args:
            func: 要执行的函数（可以是同步或异步）
            *args: 位置参数
            **kwargs: 关键字参数
        
        Returns:
            函数执行结果
        
        Raises:
            CircuitBreakerOpen: 熔断器打开时
            Exception: 函数执行异常
        """
        self._stats.total_requests += 1
        
        # 检查是否允许请求
        if not await self._should_allow_request():
            self._stats.rejected_requests += 1
            logger.warning(f"[{self.name}] 请求被拒绝，熔断器状态：{self._state.value}")
            return await self._execute_fallback()
        
        try:
            # 执行函数（支持超时）
            if self.config.timeout_seconds:
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=self.config.timeout_seconds
                    )
                else:
                    loop = asyncio.get_event_loop()
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, func, *args),
                        timeout=self.config.timeout_seconds
                    )
            else:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, func, *args)
            
            await self._record_success()
            return result
        
        except asyncio.TimeoutError as e:
            logger.error(f"[{self.name}] 请求超时")
            await self._record_failure(e)
            return await self._execute_fallback()
        
        except CircuitBreakerOpen:
            raise
        
        except Exception as e:
            logger.error(f"[{self.name}] 执行失败：{e}")
            await self._record_failure(e)
            return await self._execute_fallback()
    
    async def _execute_fallback(self) -> Any:
        """执行降级策略"""
        self._stats.fallback_invocations += 1
        
        if self._on_fallback:
            try:
                self._on_fallback()
            except Exception as e:
                logger.error(f"[{self.name}] 降级回调失败：{e}")
        
        strategy = self.config.fallback_strategy
        logger.info(f"[{self.name}] 执行降级策略：{strategy.value}")
        
        if strategy == FallbackStrategy.RETURN_DEFAULT:
            return self.config.default_value
        
        elif strategy == FallbackStrategy.FAIL_FAST:
            raise CircuitBreakerOpen(
                f"熔断器 {self.name} 已打开",
                self.name,
                self._state
            )
        
        elif strategy == FallbackStrategy.RETRY_ONCE:
            # 重试一次（不经过熔断器）
            try:
                if asyncio.iscoroutinefunction(self.config.backup_function):
                    return await self.config.backup_function()
                elif self.config.backup_function:
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(None, self.config.backup_function)
            except Exception as e:
                logger.error(f"[{self.name}] 重试失败：{e}")
            return self.config.default_value
        
        elif strategy == FallbackStrategy.CALL_BACKUP:
            if self.config.backup_function:
                try:
                    if asyncio.iscoroutinefunction(self.config.backup_function):
                        return await self.config.backup_function()
                    else:
                        loop = asyncio.get_event_loop()
                        return await loop.run_in_executor(None, self.config.backup_function)
                except Exception as e:
                    logger.error(f"[{self.name}] 备用函数失败：{e}")
            return self.config.default_value
        
        elif strategy == FallbackStrategy.GRACEFUL_DEGRADE:
            # 优雅降级：返回部分功能或简化结果
            return self.config.default_value
        
        return self.config.default_value
    
    def reset(self) -> None:
        """重置熔断器"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_requests = 0
        self._opened_at = None
        logger.info(f"[{self.name}] 熔断器已重置")
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态信息"""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "half_open_requests": self._half_open_requests,
            "opened_at": self._opened_at.isoformat() if self._opened_at else None,
            "config": self.config.to_dict(),
            "stats": self._stats.to_dict()
        }


class MultiLevelCircuitBreaker:
    """
    多级熔断器管理器
    
    支持节点级、工作流级、系统级三级熔断
    """
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
        
        # 层级关系
        self._node_breakers: Dict[str, CircuitBreaker] = {}      # 节点级
        self._workflow_breakers: Dict[str, CircuitBreaker] = {}  # 工作流级
        self._system_breakers: Dict[str, CircuitBreaker] = {}    # 系统级
        
        # 全局配置
        self._default_config = CircuitConfig()
    
    def get_or_create(
        self,
        name: str,
        level: str = "node",
        config: Optional[CircuitConfig] = None
    ) -> CircuitBreaker:
        """获取或创建熔断器"""
        if name in self._breakers:
            return self._breakers[name]
        
        breaker = CircuitBreaker(name, config or self._default_config)
        self._breakers[name] = breaker
        
        if level == "node":
            self._node_breakers[name] = breaker
        elif level == "workflow":
            self._workflow_breakers[name] = breaker
        elif level == "system":
            self._system_breakers[name] = breaker
        
        logger.info(f"创建 {level} 级熔断器：{name}")
        return breaker
    
    def get_node_breaker(self, node_name: str) -> Optional[CircuitBreaker]:
        """获取节点级熔断器"""
        return self._node_breakers.get(node_name)
    
    def get_workflow_breaker(self, workflow_name: str) -> Optional[CircuitBreaker]:
        """获取工作流级熔断器"""
        return self._workflow_breakers.get(workflow_name)
    
    def get_system_breaker(self, service_name: str) -> Optional[CircuitBreaker]:
        """获取系统级熔断器"""
        return self._system_breakers.get(service_name)
    
    def set_default_config(self, config: CircuitConfig) -> None:
        """设置默认配置"""
        self._default_config = config
    
    async def execute_with_circuit_breaker(
        self,
        node_name: str,
        workflow_name: str,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        使用多级熔断器执行函数
        
        执行顺序：节点级 -> 工作流级 -> 系统级
        """
        # 获取各级熔断器
        node_breaker = self.get_node_breaker(node_name)
        workflow_breaker = self.get_workflow_breaker(workflow_name)
        
        # 如果没有节点级熔断器，创建一个
        if not node_breaker:
            node_breaker = self.get_or_create(node_name, "node")
        
        # 执行（经过节点级熔断器）
        return await node_breaker.execute(func, *args, **kwargs)
    
    def get_all_status(self) -> Dict[str, Any]:
        """获取所有熔断器状态"""
        return {
            "node_level": {
                name: breaker.get_status()
                for name, breaker in self._node_breakers.items()
            },
            "workflow_level": {
                name: breaker.get_status()
                for name, breaker in self._workflow_breakers.items()
            },
            "system_level": {
                name: breaker.get_status()
                for name, breaker in self._system_breakers.items()
            },
            "summary": {
                "total_breakers": len(self._breakers),
                "open_count": sum(1 for b in self._breakers.values() if b.state == CircuitState.OPEN),
                "half_open_count": sum(1 for b in self._breakers.values() if b.state == CircuitState.HALF_OPEN)
            }
        }
    
    def reset_all(self) -> None:
        """重置所有熔断器"""
        for breaker in self._breakers.values():
            breaker.reset()
        logger.info("所有熔断器已重置")


class CircuitBreakerMonitor:
    """
    熔断器监控器
    
    提供状态监控、告警、自动恢复等功能
    """
    
    def __init__(self, manager: MultiLevelCircuitBreaker):
        self.manager = manager
        self._alert_callbacks: List[Callable[[str, Dict], None]] = []
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
    
    def add_alert_callback(self, callback: Callable[[str, Dict], None]) -> None:
        """添加告警回调"""
        self._alert_callbacks.append(callback)
    
    async def start_monitoring(self, interval_seconds: float = 5.0) -> None:
        """开始监控"""
        self._running = True
        
        async def monitor_loop():
            while self._running:
                await self._check_and_alert()
                await asyncio.sleep(interval_seconds)
        
        self._monitor_task = asyncio.create_task(monitor_loop())
        logger.info("熔断器监控已启动")
    
    async def stop_monitoring(self) -> None:
        """停止监控"""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("熔断器监控已停止")
    
    async def _check_and_alert(self) -> None:
        """检查状态并发送告警"""
        status = self.manager.get_all_status()
        
        # 检查是否有熔断器打开
        open_breakers = []
        for level_name, level_data in status.items():
            if level_name == "summary":
                continue
            for name, breaker_status in level_data.items():
                if breaker_status["state"] == "open":
                    open_breakers.append({
                        "name": name,
                        "level": level_name,
                        "status": breaker_status
                    })
        
        if open_breakers:
            alert_data = {
                "timestamp": datetime.now().isoformat(),
                "open_breakers": open_breakers,
                "summary": status["summary"]
            }
            
            logger.warning(f"检测到 {len(open_breakers)} 个熔断器打开：{[b['name'] for b in open_breakers]}")
            
            for callback in self._alert_callbacks:
                try:
                    callback("circuit_breaker_open", alert_data)
                except Exception as e:
                    logger.error(f"告警回调失败：{e}")
    
    def get_health_report(self) -> Dict[str, Any]:
        """获取健康报告"""
        status = self.manager.get_all_status()
        
        # 计算健康分数
        total = status["summary"]["total_breakers"]
        open_count = status["summary"]["open_count"]
        half_open_count = status["summary"]["half_open_count"]
        
        if total == 0:
            health_score = 100
        else:
            health_score = max(0, 100 - (open_count * 20) - (half_open_count * 10))
        
        return {
            "health_score": health_score,
            "status": "healthy" if health_score >= 80 else ("warning" if health_score >= 50 else "critical"),
            "total_breakers": total,
            "open_breakers": open_count,
            "half_open_breakers": half_open_count,
            "details": status
        }


# ============ 装饰器 ============

def with_circuit_breaker(
    name: Optional[str] = None,
    config: Optional[CircuitConfig] = None,
    manager: Optional[MultiLevelCircuitBreaker] = None
):
    """
    熔断器装饰器
    
    用法:
        @with_circuit_breaker(name="my_function")
        async def my_function():
            ...
    """
    _manager = manager or MultiLevelCircuitBreaker()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        breaker_name = name or func.__name__
        breaker = _manager.get_or_create(breaker_name, "node", config)
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await breaker.execute(func, *args, **kwargs)
        
        return wrapper
    return decorator


# ============ 全局实例 ============

# 全局熔断器管理器
_global_manager: Optional[MultiLevelCircuitBreaker] = None
_global_monitor: Optional[CircuitBreakerMonitor] = None


def get_circuit_breaker_manager() -> MultiLevelCircuitBreaker:
    """获取全局熔断器管理器"""
    global _global_manager
    if _global_manager is None:
        _global_manager = MultiLevelCircuitBreaker()
    return _global_manager


def get_circuit_breaker_monitor() -> Optional[CircuitBreakerMonitor]:
    """获取全局熔断器监控器"""
    global _global_monitor
    return _global_monitor


async def init_circuit_breaker_monitor() -> CircuitBreakerMonitor:
    """初始化并启动监控器"""
    global _global_monitor
    manager = get_circuit_breaker_manager()
    _global_monitor = CircuitBreakerMonitor(manager)
    await _global_monitor.start_monitoring(interval_seconds=5.0)
    return _global_monitor


# ============ 主程序 ============

async def main():
    """测试熔断器模块"""
    logging.basicConfig(level=logging.INFO)
    
    # 创建熔断器
    config = CircuitConfig(
        failure_threshold=3,
        success_threshold=2,
        recovery_timeout_seconds=5.0,
        fallback_strategy=FallbackStrategy.RETURN_DEFAULT,
        default_value="fallback_value"
    )
    
    breaker = CircuitBreaker("test_breaker", config)
    
    # 注册回调
    def on_state_change(old_state, new_state):
        logger.info(f"状态变化：{old_state} -> {new_state}")
    
    breaker.on_state_change(on_state_change)
    
    # 测试正常执行
    async def success_func():
        return "success"
    
    result = await breaker.execute(success_func)
    logger.info(f"正常执行结果：{result}")
    
    # 测试失败执行
    async def fail_func():
        raise Exception("模拟失败")
    
    for i in range(5):
        try:
            result = await breaker.execute(fail_func)
            logger.info(f"失败执行结果：{result}")
        except CircuitBreakerOpen as e:
            logger.warning(f"熔断器打开：{e}")
    
    # 获取状态
    status = breaker.get_status()
    logger.info(f"熔断器状态：{status}")
    
    # 测试多级熔断器
    manager = MultiLevelCircuitBreaker()
    
    node_breaker = manager.get_or_create("api_call", "node")
    workflow_breaker = manager.get_or_create("data_sync", "workflow")
    system_breaker = manager.get_or_create("external_api", "system")
    
    all_status = manager.get_all_status()
    logger.info(f"多级熔断器状态：{all_status}")
    
    # 测试监控器
    monitor = CircuitBreakerMonitor(manager)
    
    def alert_callback(event_type, data):
        logger.warning(f"告警：{event_type}, 数据：{data}")
    
    monitor.add_alert_callback(alert_callback)
    
    health_report = monitor.get_health_report()
    logger.info(f"健康报告：{health_report}")
    
    logger.info("熔断器模块测试完成")


if __name__ == "__main__":
    asyncio.run(main())
