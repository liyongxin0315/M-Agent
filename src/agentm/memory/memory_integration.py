"""
记忆系统集成：自动记录执行轨迹

在每次执行 Agent 任务后自动记录：
  - 任务记忆（task）
  - 推理链（reasoning_chain）
  - 反馈记忆（feedback）
"""

from __future__ import annotations

from ..agents.executor_agent import ExecutionResult
from .vector_store import (
    get_memory_store,
    MemoryStore,
    MemoryType,
    MemoryTier,
)


class MemoryIntegrator:
    """
    将执行结果自动写入记忆系统

    使用方式：
      integrator = MemoryIntegrator()
      integrator.record_execution(result)
    """

    def __init__(self, store: MemoryStore | None = None):
        self.store = store or get_memory_store()

    def record_execution(self, result: ExecutionResult) -> list[str]:
        """
        记录一次完整执行
        返回所有创建的 memory id
        """
        memory_ids = []

        # 1. 记录任务记忆
        task_mem = self.store.add(
            memory_type=MemoryType.TASK,
            content=f"任务执行：{result.mode.value} 模式，"
                    f"Z3 验证结果：{result.verdict}，"
                    f"耗时：{result.execution_time_ms:.0f}ms，"
                    f"自动升级：{result.upgrade_triggered}",
            raw_data={
                "task_id": result.task_id,
                "mode": result.mode.value,
                "verdict": result.verdict,
                "execution_time_ms": result.execution_time_ms,
                "upgrade_triggered": result.upgrade_triggered,
            },
            tags=["task", result.mode.value, result.verdict],
            importance=0.7,
            tier=MemoryTier.WARM,
        )
        memory_ids.append(task_mem.id)

        # 2. 记录推理链（从 history）
        parent_id = task_mem.id
        for i, step in enumerate(result.history):
            chain_mem = self.store.add(
                memory_type=MemoryType.REASONING_CHAIN,
                content=f"推理步骤 {i+1}：{step.get('event', 'unknown')}",
                raw_data=step,
                tags=["reasoning", f"step-{i+1}"],
                parent_id=parent_id if i > 0 else None,
                importance=0.5,
                tier=MemoryTier.COLD,
            )
            if i == 0:
                # 更新第一个的 parent_id
                parent_id = chain_mem.id
            memory_ids.append(chain_mem.id)

        # 3. 记录反馈（成功/失败）
        if result.verdict == "pass":
            feedback_content = f"任务通过：{result.task_id}，代码已生成并通过 Z3 验证"
            feedback_importance = 0.8
        elif result.verdict == "fail":
            feedback_content = f"任务失败：{result.task_id}，"
            if result.counterexample:
                feedback_content += f"Z3 反例：{result.counterexample[:200]}"
            feedback_importance = 0.9  # 失败的记忆更重要
        else:
            feedback_content = f"任务无法判定：{result.task_id}，Z3 结果：{result.verdict}"
            feedback_importance = 0.6

        feedback_mem = self.store.add(
            memory_type=MemoryType.FEEDBACK,
            content=feedback_content,
            raw_data={
                "task_id": result.task_id,
                "verdict": result.verdict,
                "counterexample": result.counterexample,
            },
            tags=["feedback", result.verdict],
            parent_id=task_mem.id,
            importance=feedback_importance,
            tier=MemoryTier.HOT if result.verdict == "fail" else MemoryTier.WARM,
        )
        memory_ids.append(feedback_mem.id)

        return memory_ids

    def search_related(self, query: str, top_k: int = 5) -> list:
        """搜索相关记忆"""
        return self.store.search(query, top_k=top_k)

    def get_task_history(self, limit: int = 10) -> list:
        """获取最近任务历史"""
        return self.store.query_by_type(MemoryType.TASK, limit=limit)


# 全局实例
_integrator: MemoryIntegrator | None = None


def get_memory_integrator() -> MemoryIntegrator:
    global _integrator
    if _integrator is None:
        _integrator = MemoryIntegrator()
    return _integrator
