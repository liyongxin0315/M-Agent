"""
AgentM 性能优化模块

提供性能分析、缓存机制、异步并行执行等优化功能
"""

import asyncio
import cProfile
import functools
import hashlib
import logging
import os
import pstats
import sys
import time
from collections import OrderedDict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

logger = logging.getLogger(__name__)

# 类型变量
T = TypeVar('T')


@dataclass
class CacheEntry:
    """缓存条目"""
    value: Any
    created_at: datetime
    expires_at: Optional[datetime]
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    size_bytes: int = 0


class LRUCache:
    """
    LRU 缓存实现
    
    特性:
    - 基于访问频率自动淘汰
    - 支持过期时间
    - 线程安全
    - 内存限制
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        max_memory_mb: float = 100.0,
        default_ttl_seconds: Optional[float] = None
    ):
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self.max_size = max_size
        self.max_memory_bytes = int(max_memory_mb * 1024 * 1024)
        self.default_ttl = timedelta(seconds=default_ttl_seconds) if default_ttl_seconds else None
        self._current_memory = 0
        
        # 统计信息
        self.hits = 0
        self.misses = 0
        self.evictions = 0
    
    def _estimate_size(self, value: Any) -> int:
        """估算对象大小（字节）"""
        try:
            import sys
            size = sys.getsizeof(value)
            if isinstance(value, (dict, list, tuple, set)):
                if isinstance(value, dict):
                    size += sum(self._estimate_size(k) + self._estimate_size(v) for k, v in value.items())
                elif isinstance(value, (list, tuple, set)):
                    size += sum(self._estimate_size(item) for item in value)
            return size
        except Exception:
            return 1024  # 默认估算 1KB
    
    def _evict_if_needed(self) -> None:
        """如果需要则淘汰条目"""
        # 检查数量限制
        while len(self._cache) > self.max_size:
            self._evict_oldest()
        
        # 检查内存限制
        while self._current_memory > self.max_memory_bytes and self._cache:
            self._evict_oldest()
    
    def _evict_oldest(self) -> None:
        """淘汰最久未使用的条目"""
        if self._cache:
            key, entry = self._cache.popitem(last=False)
            self._current_memory -= entry.size_bytes
            self.evictions += 1
            logger.debug(f"LRU 淘汰：{key}, 释放 {entry.size_bytes} 字节")
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """检查是否过期"""
        if entry.expires_at is None:
            return False
        return datetime.now() > entry.expires_at
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        async with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None
            
            entry = self._cache[key]
            
            # 检查过期
            if self._is_expired(entry):
                del self._cache[key]
                self._current_memory -= entry.size_bytes
                self.misses += 1
                return None
            
            # 更新访问统计
            entry.access_count += 1
            entry.last_accessed = datetime.now()
            
            # 移到末尾（最近使用）
            self._cache.move_to_end(key)
            
            self.hits += 1
            return entry.value
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[float] = None
    ) -> None:
        """设置缓存值"""
        async with self._lock:
            # 计算过期时间
            if ttl_seconds is not None:
                expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
            elif self.default_ttl:
                expires_at = datetime.now() + self.default_ttl
            else:
                expires_at = None
            
            # 估算大小
            size = self._estimate_size(value)
            
            # 如果已存在，先移除旧值
            if key in self._cache:
                old_entry = self._cache[key]
                self._current_memory -= old_entry.size_bytes
                del self._cache[key]
            
            # 创建新条目
            entry = CacheEntry(
                value=value,
                created_at=datetime.now(),
                expires_at=expires_at,
                size_bytes=size
            )
            
            self._cache[key] = entry
            self._current_memory += size
            
            # 淘汰
            self._evict_if_needed()
            
            logger.debug(f"缓存设置：{key}, 大小 {size} 字节")
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        async with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                self._current_memory -= entry.size_bytes
                del self._cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """清空缓存"""
        async with self._lock:
            self._cache.clear()
            self._current_memory = 0
            logger.info("缓存已清空")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        hit_rate = (self.hits / (self.hits + self.misses) * 100) if (self.hits + self.misses) > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "memory_bytes": self._current_memory,
            "memory_mb": self._current_memory / 1024 / 1024,
            "max_memory_mb": self.max_memory_bytes / 1024 / 1024,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate_percent": round(hit_rate, 2)
        }
    
    async def cleanup_expired(self) -> int:
        """清理过期条目"""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if self._is_expired(entry)
            ]
            
            for key in expired_keys:
                entry = self._cache[key]
                self._current_memory -= entry.size_bytes
                del self._cache[key]
            
            if expired_keys:
                logger.info(f"清理了 {len(expired_keys)} 个过期缓存条目")
            
            return len(expired_keys)


def cached(
    cache: LRUCache,
    key_fn: Optional[Callable[..., str]] = None,
    ttl_seconds: Optional[float] = None
):
    """
    异步缓存装饰器
    
    用法:
        @cached(my_cache, ttl_seconds=300)
        async def expensive_function(arg1, arg2):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # 生成缓存键
            if key_fn:
                key = key_fn(*args, **kwargs)
            else:
                # 默认：函数名 + 参数哈希
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                key_string = ":".join(key_parts)
                key = hashlib.md5(key_string.encode()).hexdigest()
            
            # 尝试从缓存获取
            cached_value = await cache.get(key)
            if cached_value is not None:
                logger.debug(f"缓存命中：{func.__name__}({key})")
                return cached_value
            
            # 执行函数
            logger.debug(f"缓存未命中，执行：{func.__name__}({key})")
            result = await func(*args, **kwargs)
            
            # 存入缓存
            await cache.set(key, result, ttl_seconds=ttl_seconds)
            
            return result
        
        return wrapper
    return decorator


class PerformanceProfiler:
    """
    性能分析器
    
    使用 cProfile 分析代码性能瓶颈
    """
    
    def __init__(self, output_file: Optional[str] = None):
        self.output_file = output_file
        self.profiler: Optional[cProfile.Profile] = None
        self.stats: Optional[pstats.Stats] = None
    
    def __enter__(self) -> "PerformanceProfiler":
        """开始分析"""
        self.profiler = cProfile.Profile()
        self.profiler.enable()
        logger.info("性能分析开始")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """停止分析"""
        if self.profiler:
            self.profiler.disable()
            logger.info("性能分析结束")
            
            if self.output_file:
                self.stats = pstats.Stats(self.profiler)
                self.stats.dump_stats(self.output_file)
                logger.info(f"分析结果已保存到：{self.output_file}")
    
    def get_top_functions(self, limit: int = 10, sort_by: str = 'cumulative') -> List[Dict[str, Any]]:
        """获取最耗时的函数"""
        if not self.stats:
            return []
        
        # 重定向输出到字符串
        import io
        stream = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = stream
        
        try:
            self.stats.sort_stats(sort_by).print_stats(limit)
        finally:
            sys.stdout = old_stdout
        
        # 解析输出（简化版本）
        results = []
        lines = stream.getvalue().strip().split('\n')
        
        for line in lines[5:]:  # 跳过表头
            if line.strip():
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        results.append({
                            "ncalls": parts[0],
                            "tottime": float(parts[1]),
                            "percall": float(parts[2]),
                            "cumtime": float(parts[3]),
                            "function": " ".join(parts[4:])
                        })
                    except (ValueError, IndexError):
                        continue
        
        return results
    
    def print_stats(self, limit: int = 20) -> None:
        """打印统计信息"""
        if self.stats:
            self.stats.sort_stats('cumulative').print_stats(limit)


def profile_async(func: Callable[..., T]) -> Callable[..., T]:
    """
    异步函数性能分析装饰器
    
    用法:
        @profile_async
        async def my_function():
            ...
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        start_time = time.perf_counter()
        try:
            result = await func(*args, **kwargs)
            elapsed = time.perf_counter() - start_time
            logger.info(f"{func.__name__} 执行耗时：{elapsed:.4f}s")
            return result
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            logger.error(f"{func.__name__} 执行失败，耗时：{elapsed:.4f}s, 错误：{e}")
            raise
    
    return wrapper


class AsyncExecutor:
    """
    异步执行器
    
    提供并行执行、批处理、超时控制等功能
    """
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        executor_type: str = 'thread'  # 'thread' or 'process'
    ):
        self.max_workers = max_workers or os.cpu_count() or 4
        self.executor_type = executor_type
        self._executor: Optional[Any] = None
    
    def _get_executor(self):
        """获取执行器"""
        if self._executor is None:
            if self.executor_type == 'process':
                self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
            else:
                self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        return self._executor
    
    async def execute_parallel(
        self,
        func: Callable,
        args_list: List[Tuple],
        timeout_seconds: Optional[float] = None
    ) -> List[Any]:
        """
        并行执行多个任务
        
        Args:
            func: 要执行的函数
            args_list: 参数列表，每个元素是一个元组
            timeout_seconds: 超时时间
        
        Returns:
            结果列表
        """
        executor = self._get_executor()
        loop = asyncio.get_event_loop()
        
        async def run_with_timeout(args: Tuple) -> Any:
            if asyncio.iscoroutinefunction(func):
                if timeout_seconds:
                    return await asyncio.wait_for(func(*args), timeout=timeout_seconds)
                return await func(*args)
            else:
                # 同步函数在线程池中执行
                if timeout_seconds:
                    return await asyncio.wait_for(
                        loop.run_in_executor(executor, func, *args),
                        timeout=timeout_seconds
                    )
                return await loop.run_in_executor(executor, func, *args)
        
        tasks = [run_with_timeout(args) for args in args_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"任务 {i} 执行失败：{result}")
        
        return results
    
    async def execute_batch(
        self,
        func: Callable,
        items: List[Any],
        batch_size: int = 10,
        timeout_per_batch: Optional[float] = None
    ) -> List[Any]:
        """
        批处理执行
        
        Args:
            func: 处理函数
            items: 待处理项列表
            batch_size: 每批数量
            timeout_per_batch: 每批超时时间
        
        Returns:
            处理结果列表
        """
        results = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            logger.debug(f"执行批次 {i // batch_size + 1}, 大小 {len(batch)}")
            
            batch_results = await self.execute_parallel(
                func,
                [(item,) for item in batch],
                timeout_seconds=timeout_per_batch
            )
            results.extend(batch_results)
        
        return results
    
    def shutdown(self, wait: bool = True) -> None:
        """关闭执行器"""
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None


@dataclass
class OptimizationResult:
    """优化结果"""
    original_time: float
    optimized_time: float
    speedup: float
    memory_before_mb: float
    memory_after_mb: float
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_time_seconds": self.original_time,
            "optimized_time_seconds": self.optimized_time,
            "speedup_factor": round(self.speedup, 2),
            "speedup_percent": round((self.speedup - 1) * 100, 2),
            "memory_before_mb": round(self.memory_before_mb, 2),
            "memory_after_mb": round(self.memory_after_mb, 2),
            "memory_saved_mb": round(self.memory_before_mb - self.memory_after_mb, 2),
            "recommendations": self.recommendations
        }


class WorkflowOptimizer:
    """
    工作流优化器
    
    分析工作流性能并提供优化建议
    """
    
    def __init__(self):
        self.cache = LRUCache(max_size=500, max_memory_mb=50.0, default_ttl_seconds=300)
        self.executor = AsyncExecutor(max_workers=8, executor_type='thread')
        self.profiler = PerformanceProfiler()
    
    async def analyze_workflow(
        self,
        workflow_func: Callable,
        *args,
        **kwargs
    ) -> OptimizationResult:
        """
        分析工作流性能
        
        Args:
            workflow_func: 工作流函数
            *args: 位置参数
            **kwargs: 关键字参数
        
        Returns:
            优化结果
        """
        import tracemalloc
        
        # 第一次运行：原始性能
        tracemalloc.start()
        start_time = time.perf_counter()
        
        try:
            if asyncio.iscoroutinefunction(workflow_func):
                await workflow_func(*args, **kwargs)
            else:
                workflow_func(*args, **kwargs)
        finally:
            original_time = time.perf_counter() - start_time
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            memory_before_mb = peak / 1024 / 1024
        
        logger.info(f"原始执行时间：{original_time:.4f}s, 峰值内存：{memory_before_mb:.2f}MB")
        
        # 生成优化建议
        recommendations = self._generate_recommendations(
            original_time,
            memory_before_mb
        )
        
        # 估算优化后性能（假设有缓存和并行化）
        estimated_speedup = 1.0
        if "使用缓存" in str(recommendations):
            estimated_speedup *= 2.0
        if "并行执行" in str(recommendations):
            estimated_speedup *= 1.5
        
        optimized_time = original_time / estimated_speedup
        memory_after_mb = memory_before_mb * 0.8  # 估算优化后内存
        
        return OptimizationResult(
            original_time=original_time,
            optimized_time=optimized_time,
            speedup=estimated_speedup,
            memory_before_mb=memory_before_mb,
            memory_after_mb=memory_after_mb,
            recommendations=recommendations
        )
    
    def _generate_recommendations(
        self,
        execution_time: float,
        memory_mb: float
    ) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        if execution_time > 5.0:
            recommendations.append("⚠️ 执行时间较长，建议添加缓存机制")
        
        if execution_time > 10.0:
            recommendations.append("⚠️ 考虑使用并行执行优化性能")
        
        if memory_mb > 100:
            recommendations.append("⚠️ 内存使用较高，建议优化数据结构")
        
        if memory_mb > 500:
            recommendations.append("🔴 内存使用过高，考虑使用生成器或流式处理")
        
        if not recommendations:
            recommendations.append("✅ 性能良好，无需优化")
        
        return recommendations
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return self.cache.get_stats()
    
    async def cleanup(self) -> None:
        """清理资源"""
        await self.cache.cleanup_expired()
        self.executor.shutdown(wait=False)


# ============ 便捷函数 ============

# 全局缓存实例
global_cache: Optional[LRUCache] = None

def get_global_cache() -> LRUCache:
    """获取全局缓存实例"""
    global global_cache
    if global_cache is None:
        global_cache = LRUCache(
            max_size=1000,
            max_memory_mb=100.0,
            default_ttl_seconds=300
        )
    return global_cache


async def cache_get(key: str) -> Optional[Any]:
    """从全局缓存获取"""
    return await get_global_cache().get(key)


async def cache_set(key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
    """设置全局缓存"""
    await get_global_cache().set(key, value, ttl_seconds=ttl_seconds)


async def cache_delete(key: str) -> bool:
    """删除全局缓存"""
    return await get_global_cache().delete(key)


def clear_global_cache() -> None:
    """清空全局缓存"""
    global global_cache
    if global_cache:
        asyncio.create_task(global_cache.clear())
        global_cache = None


# ============ 主程序 ============

async def main():
    """测试优化模块"""
    logging.basicConfig(level=logging.INFO)
    
    # 测试缓存
    cache = LRUCache(max_size=100, max_memory_mb=10.0, default_ttl_seconds=60)
    
    await cache.set("test_key", {"data": "test_value"})
    result = await cache.get("test_key")
    logger.info(f"缓存测试结果：{result}")
    
    # 测试性能分析
    async def sample_function():
        total = 0
        for i in range(1000000):
            total += i
        await asyncio.sleep(0.1)
        return total
    
    with PerformanceProfiler(output_file="/tmp/profile_stats.prof") as profiler:
        result = await sample_function()
    
    logger.info(f"样本函数结果：{result}")
    
    # 测试并行执行
    executor = AsyncExecutor(max_workers=4)
    
    def slow_function(x):
        time.sleep(0.1)
        return x * 2
    
    results = await executor.execute_parallel(
        slow_function,
        [(i,) for i in range(10)],
        timeout_seconds=5.0
    )
    logger.info(f"并行执行结果：{results}")
    
    executor.shutdown()
    
    # 测试工作流优化器
    optimizer = WorkflowOptimizer()
    
    async def sample_workflow():
        await asyncio.sleep(0.5)
        return {"status": "completed"}
    
    opt_result = await optimizer.analyze_workflow(sample_workflow)
    logger.info(f"优化分析结果：{opt_result.to_dict()}")
    
    await optimizer.cleanup()
    
    logger.info("优化模块测试完成")


if __name__ == "__main__":
    asyncio.run(main())
