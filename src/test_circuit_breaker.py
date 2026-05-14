"""
AgentM 熔断器模块单元测试

测试熔断器状态转换、执行保护、降级策略、多级熔断等功能
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.circuit_breaker import (
    CircuitBreaker,
    CircuitConfig,
    CircuitState,
    CircuitStats,
    FallbackStrategy,
    CircuitBreakerError,
    CircuitBreakerOpen,
    MultiLevelCircuitBreaker,
    CircuitBreakerMonitor,
)


class TestCircuitState:
    """测试熔断器状态枚举"""
    
    def test_state_values(self):
        """测试状态值"""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestFallbackStrategy:
    """测试降级策略枚举"""
    
    def test_strategy_values(self):
        """测试策略值"""
        assert FallbackStrategy.RETURN_DEFAULT.value == "return_default"
        assert FallbackStrategy.RETURN_CACHE.value == "return_cache"
        assert FallbackStrategy.CALL_BACKUP.value == "call_backup"
        assert FallbackStrategy.FAIL_FAST.value == "fail_fast"
        assert FallbackStrategy.RETRY_ONCE.value == "retry_once"
        assert FallbackStrategy.GRACEFUL_DEGRADE.value == "graceful_degrade"


class TestCircuitConfig:
    """测试熔断器配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = CircuitConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.recovery_timeout_seconds == 30.0
        assert config.half_open_max_requests == 3
        assert config.timeout_seconds is None
        assert config.fallback_strategy == FallbackStrategy.FAIL_FAST
        assert config.enabled is True
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = CircuitConfig(
            failure_threshold=10,
            success_threshold=5,
            recovery_timeout_seconds=60.0,
            fallback_strategy=FallbackStrategy.RETURN_DEFAULT,
            default_value="fallback",
        )
        assert config.failure_threshold == 10
        assert config.success_threshold == 5
        assert config.recovery_timeout_seconds == 60.0
        assert config.fallback_strategy == FallbackStrategy.RETURN_DEFAULT
        assert config.default_value == "fallback"
    
    def test_to_dict(self):
        """测试转换为字典"""
        config = CircuitConfig(failure_threshold=10)
        data = config.to_dict()
        
        assert isinstance(data, dict)
        assert data["failure_threshold"] == 10
        assert data["enabled"] is True


class TestCircuitStats:
    """测试熔断器统计"""
    
    def test_default_stats(self):
        """测试默认统计"""
        stats = CircuitStats()
        assert stats.total_requests == 0
        assert stats.successful_requests == 0
        assert stats.failed_requests == 0
        assert stats.rejected_requests == 0
        assert stats.fallback_invocations == 0
    
    def test_success_rate(self):
        """测试成功率计算"""
        stats = CircuitStats()
        
        # 无请求时成功率 100%
        assert stats.success_rate() == 100.0
        
        # 10 个请求，8 个成功
        stats.total_requests = 10
        stats.successful_requests = 8
        assert stats.success_rate() == 80.0
        
        # 全部失败
        stats.successful_requests = 0
        assert stats.success_rate() == 0.0
    
    def test_to_dict(self):
        """测试转换为字典"""
        stats = CircuitStats(
            total_requests=100,
            successful_requests=90,
            failed_requests=10,
        )
        data = stats.to_dict()
        
        assert data["total_requests"] == 100
        assert data["successful_requests"] == 90
        assert data["failed_requests"] == 10
        assert data["success_rate_percent"] == 90.0


class TestCircuitBreakerBasic:
    """测试熔断器基本功能"""
    
    def test_initial_state(self):
        """测试初始状态"""
        breaker = CircuitBreaker("test")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.name == "test"
    
    def test_get_status(self):
        """测试获取状态"""
        breaker = CircuitBreaker("test")
        status = breaker.get_status()
        
        assert status["name"] == "test"
        assert status["state"] == "closed"
        assert "config" in status
        assert "stats" in status
    
    def test_reset(self):
        """测试重置"""
        breaker = CircuitBreaker("test")
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerExecution:
    """测试熔断器执行保护"""
    
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """测试成功执行"""
        breaker = CircuitBreaker("test")
        
        async def success_func():
            return "success"
        
        result = await breaker.execute(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.successful_requests == 1
    
    @pytest.mark.asyncio
    async def test_failed_execution(self):
        """测试失败执行"""
        config = CircuitConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)
        
        async def fail_func():
            raise Exception("模拟失败")
        
        # 失败 3 次，触发熔断
        for i in range(3):
            try:
                await breaker.execute(fail_func)
            except:
                pass
        
        assert breaker.state == CircuitState.OPEN
        assert breaker.stats.failed_requests == 3
    
    @pytest.mark.asyncio
    async def test_timeout_execution(self):
        """测试超时执行"""
        config = CircuitConfig(
            timeout_seconds=0.1,
            fallback_strategy=FallbackStrategy.RETURN_DEFAULT,
            default_value="timeout_fallback"
        )
        breaker = CircuitBreaker("test", config)
        
        async def slow_func():
            await asyncio.sleep(1.0)
            return "done"
        
        # 超时后应该返回默认值
        result = await breaker.execute(slow_func)
        assert breaker.stats.failed_requests >= 1
        # 超时触发降级
        assert result == "timeout_fallback" or breaker.stats.fallback_invocations >= 1
    
    @pytest.mark.asyncio
    async def test_state_transition_closed_to_open(self):
        """测试状态转换：CLOSED -> OPEN"""
        config = CircuitConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)
        
        async def fail_func():
            raise Exception("失败")
        
        # 初始状态
        assert breaker.state == CircuitState.CLOSED
        
        # 失败 2 次
        for _ in range(2):
            try:
                await breaker.execute(fail_func)
            except:
                pass
        
        # 应该触发熔断
        assert breaker.state == CircuitState.OPEN
    
    @pytest.mark.asyncio
    async def test_state_transition_open_to_half_open(self):
        """测试状态转换：OPEN -> HALF_OPEN"""
        config = CircuitConfig(
            failure_threshold=2,
            recovery_timeout_seconds=0.5
        )
        breaker = CircuitBreaker("test", config)
        
        async def fail_func():
            raise Exception("失败")
        
        # 触发熔断
        for _ in range(2):
            try:
                await breaker.execute(fail_func)
            except:
                pass
        
        assert breaker.state == CircuitState.OPEN
        
        # 等待恢复超时
        await asyncio.sleep(0.6)
        
        # 下次请求应该触发半开
        async def success_func():
            return "success"
        
        result = await breaker.execute(success_func)
        assert breaker.state == CircuitState.HALF_OPEN
    
    @pytest.mark.asyncio
    async def test_state_transition_half_open_to_closed(self):
        """测试状态转换：HALF_OPEN -> CLOSED"""
        config = CircuitConfig(
            failure_threshold=2,
            success_threshold=2,
            recovery_timeout_seconds=0.1
        )
        breaker = CircuitBreaker("test", config)
        
        async def fail_func():
            raise Exception("失败")
        
        async def success_func():
            return "success"
        
        # 触发熔断
        for _ in range(2):
            try:
                await breaker.execute(fail_func)
            except:
                pass
        
        # 等待恢复超时
        await asyncio.sleep(0.2)
        
        # 成功 2 次，恢复关闭状态
        for _ in range(2):
            await breaker.execute(success_func)
        
        assert breaker.state == CircuitState.CLOSED


class TestCircuitBreakerFallback:
    """测试熔断器降级策略"""
    
    @pytest.mark.asyncio
    async def test_fallback_return_default(self):
        """测试降级策略：返回默认值"""
        config = CircuitConfig(
            failure_threshold=1,
            fallback_strategy=FallbackStrategy.RETURN_DEFAULT,
            default_value="default_value"
        )
        breaker = CircuitBreaker("test", config)
        
        async def fail_func():
            raise Exception("失败")
        
        # 第一次失败，触发熔断
        try:
            await breaker.execute(fail_func)
        except:
            pass
        
        # 第二次应该返回默认值
        result = await breaker.execute(fail_func)
        assert result == "default_value"
    
    @pytest.mark.asyncio
    async def test_fallback_fail_fast(self):
        """测试降级策略：快速失败"""
        config = CircuitConfig(
            failure_threshold=1,
            fallback_strategy=FallbackStrategy.FAIL_FAST
        )
        breaker = CircuitBreaker("test", config)
        
        async def fail_func():
            raise Exception("失败")
        
        # 触发熔断
        try:
            await breaker.execute(fail_func)
        except:
            pass
        
        # 应该抛出 CircuitBreakerOpen
        with pytest.raises(CircuitBreakerOpen):
            await breaker.execute(fail_func)
    
    @pytest.mark.asyncio
    async def test_fallback_retry_once(self):
        """测试降级策略：重试一次"""
        call_count = 0
        
        def backup_func():
            nonlocal call_count
            call_count += 1
            return "backup_result"
        
        config = CircuitConfig(
            failure_threshold=1,
            fallback_strategy=FallbackStrategy.RETRY_ONCE,
            backup_function=backup_func,
            default_value="default"
        )
        breaker = CircuitBreaker("test", config)
        
        async def fail_func():
            raise Exception("失败")
        
        # 触发熔断
        try:
            await breaker.execute(fail_func)
        except:
            pass
        
        # 重试应该调用备用函数（熔断器打开后请求被拒绝，直接执行降级）
        result = await breaker.execute(fail_func)
        # 重试策略会调用备用函数
        assert call_count >= 1
        assert result == "backup_result"


class TestCircuitBreakerCallbacks:
    """测试熔断器回调"""
    
    @pytest.mark.asyncio
    async def test_state_change_callback(self):
        """测试状态变化回调"""
        state_changes = []
        
        def on_state_change(old_state, new_state):
            state_changes.append((old_state, new_state))
        
        config = CircuitConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)
        breaker.on_state_change(on_state_change)
        
        async def fail_func():
            raise Exception("失败")
        
        # 触发熔断
        for _ in range(2):
            try:
                await breaker.execute(fail_func)
            except:
                pass
        
        # 应该有一次状态变化：CLOSED -> OPEN
        assert len(state_changes) >= 1
        assert state_changes[0] == (CircuitState.CLOSED, CircuitState.OPEN)
    
    @pytest.mark.asyncio
    async def test_failure_callback(self):
        """测试失败回调"""
        failures = []
        
        def on_failure(error):
            failures.append(error)
        
        breaker = CircuitBreaker("test")
        breaker.on_failure(on_failure)
        
        async def fail_func():
            raise Exception("测试失败")
        
        try:
            await breaker.execute(fail_func)
        except:
            pass
        
        assert len(failures) == 1
        assert str(failures[0]) == "测试失败"


class TestMultiLevelCircuitBreaker:
    """测试多级熔断器"""
    
    def test_create_breakers(self):
        """测试创建熔断器"""
        manager = MultiLevelCircuitBreaker()
        
        node_breaker = manager.get_or_create("node1", "node")
        workflow_breaker = manager.get_or_create("workflow1", "workflow")
        system_breaker = manager.get_or_create("system1", "system")
        
        assert node_breaker is not None
        assert workflow_breaker is not None
        assert system_breaker is not None
    
    def test_get_breakers(self):
        """测试获取熔断器"""
        manager = MultiLevelCircuitBreaker()
        
        breaker = manager.get_or_create("test_node", "node")
        
        # 获取节点级
        node_breaker = manager.get_node_breaker("test_node")
        assert node_breaker is breaker
        
        # 获取不存在的
        assert manager.get_workflow_breaker("nonexistent") is None
    
    def test_get_all_status(self):
        """测试获取所有状态"""
        manager = MultiLevelCircuitBreaker()
        
        manager.get_or_create("node1", "node")
        manager.get_or_create("workflow1", "workflow")
        
        status = manager.get_all_status()
        
        assert "node_level" in status
        assert "workflow_level" in status
        assert "system_level" in status
        assert "summary" in status
        assert status["summary"]["total_breakers"] == 2
    
    def test_reset_all(self):
        """测试重置所有"""
        manager = MultiLevelCircuitBreaker()
        
        manager.get_or_create("node1", "node")
        manager.get_or_create("node2", "node")
        
        manager.reset_all()
        
        status = manager.get_all_status()
        assert status["summary"]["open_count"] == 0


class TestCircuitBreakerMonitor:
    """测试熔断器监控器"""
    
    def test_create_monitor(self):
        """测试创建监控器"""
        manager = MultiLevelCircuitBreaker()
        monitor = CircuitBreakerMonitor(manager)
        
        assert monitor.manager is manager
    
    def test_alert_callback(self):
        """测试告警回调"""
        manager = MultiLevelCircuitBreaker()
        monitor = CircuitBreakerMonitor(manager)
        
        alerts = []
        
        def alert_callback(event_type, data):
            alerts.append((event_type, data))
        
        monitor.add_alert_callback(alert_callback)
        assert len(monitor._alert_callbacks) == 1
    
    def test_health_report(self):
        """测试健康报告"""
        manager = MultiLevelCircuitBreaker()
        monitor = CircuitBreakerMonitor(manager)
        
        # 无熔断器时健康分数 100
        report = monitor.get_health_report()
        assert report["health_score"] == 100
        assert report["status"] == "healthy"
        
        # 添加熔断器
        manager.get_or_create("test1", "node")
        manager.get_or_create("test2", "node")
        
        report = monitor.get_health_report()
        assert report["total_breakers"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
