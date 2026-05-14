"""
执行 Agent（F 动作空间）

核心职责：
  - 接收代码生成任务
  - 调用推理路由（LLM + Z3）
  - 返回验证后的代码 + 思考过程
  - 记录执行轨迹供学习系统使用
"""

from __future__ import annotations

import uuid
import time
from dataclasses import dataclass, field
from typing import Generator
from loguru import logger

from ..core.reasoning_router import (
    ReasoningRouter,
    TaskContext,
    TaskMode,
    get_router,
)
from ..core.z3_engine import Verdict


@dataclass
class ExecutionResult:
    """执行结果"""
    task_id: str
    code: str
    mode: TaskMode
    verdict: str                    # pass / fail / unknown
    execution_time_ms: float
    counterexample: str | None     # Z3 找到的反例（如果有）
    upgrade_triggered: bool
    history: list                  # 完整思考链


class ExecutorAgent:
    """
    执行 Agent：代码生成 + 验证的核心执行单元

    使用方式：
      agent = ExecutorAgent()
      result = agent.execute("帮我写一个快排")

      # 流式输出（边想边说）
      for chunk in agent.execute_stream("帮我写一个快排"):
          print(chunk, end="", flush=True)
    """

    def __init__(self, router: ReasoningRouter | None = None):
        self.router = router or get_router()

    def execute(self, prompt: str) -> ExecutionResult:
        """
        同步执行：任务 → LLM → Z3 → 结果
        """
        task_id = str(uuid.uuid4())[:8]
        context = TaskContext(task_id=task_id, prompt=prompt)

        start = time.perf_counter()

        # 执行推理流程（可能自动升级）
        context = self.router.execute(context)

        elapsed_ms = (time.perf_counter() - start) * 1000

        return ExecutionResult(
            task_id=task_id,
            code=context.code or "",
            mode=context.mode,
            verdict=(
                context.verification_result.verdict.value
                if context.verification_result
                else "unknown"
            ),
            execution_time_ms=elapsed_ms,
            counterexample=(
                context.verification_result.counterexample
                if context.verification_result
                else None
            ),
            upgrade_triggered=context.upgrade_triggered,
            history=context.history,
        )

    def execute_stream(self, prompt: str) -> Generator[str, None, ExecutionResult]:
        """
        流式执行：边生成边输出，最终返回完整结果
        思考过程实时可见
        """
        task_id = str(uuid.uuid4())[:8]
        context = TaskContext(task_id=task_id, prompt=prompt)

        # 1. 开始决策
        decision = self.router.decide(prompt, context)
        context.mode = decision.mode
        yield f"[M-Agent] 任务ID: {task_id}\n"
        yield f"[M-Agent] 选择模式: {decision.mode.value} ({decision.reason})\n\n"

        start = time.perf_counter()

        # 2. LLM 生成阶段
        yield "[M-Agent] LLM 正在生成代码...\n"

        if context.mode == TaskMode.SIMPLE:
            code = self.router.llm.generate(
                prompt=f"请生成代码：\n{prompt}",
                system="你是一个代码生成助手。只输出代码，不输出解释。",
            )
        else:
            yield "[M-Agent] 复杂模式：生成 5 个候选方案...\n"
            code = self.router.llm.generate(
                prompt=f"请生成5个不同的代码实现：\n{prompt}",
                system="你是一个代码生成助手。请生成5个不同的实现方案，编号为1-5。只输出代码。",
            )

        context.llm_result = code
        context.code = code
        yield f"\n--- 生成的代码 ---\n{code}\n\n"

        # 3. Z3 验证阶段
        yield "[M-Agent] Z3 正在验证...\n"

        spec = self.router._extract_spec(prompt)
        z3_mode = "quick" if context.mode == TaskMode.SIMPLE else "strict"
        z3_result = self.router.z3.verify(code, spec, mode=z3_mode)
        context.verification_result = z3_result

        yield f"[M-Agent] 验证结果: {z3_result.verdict.value}\n"
        if z3_result.verdict == Verdict.PASS:
            yield "[M-Agent] ✅ Z3 验证通过\n"
        elif z3_result.verdict == Verdict.FAIL:
            yield f"[M-Agent] ❌ Z3 发现反例：\n{z3_result.counterexample or '未知'}\n"

        # 4. 渐进式升级
        if (
            z3_result.verdict == Verdict.FAIL
            and not context.upgrade_triggered
        ):
            yield "\n[M-Agent] 简单模式失败，触发自动升级...\n"
            context.upgrade_triggered = True
            context.mode = TaskMode.COMPLEX

            # 重新执行复杂模式
            code = self.router.llm.generate(
                prompt=f"请生成5个不同的代码实现：\n{prompt}",
                system="你是一个代码生成助手。请生成5个不同的实现方案，编号为1-5。只输出代码。",
            )
            context.llm_result = code
            context.code = code
            yield f"\n--- 重新生成的代码 ---\n{code}\n\n"

            z3_result = self.router.z3.verify(code, spec, mode="strict")
            context.verification_result = z3_result
            yield f"[M-Agent] 验证结果: {z3_result.verdict.value}\n"

        elapsed_ms = (time.perf_counter() - start) * 1000
        yield f"\n[M-Agent] 总耗时: {elapsed_ms:.0f}ms\n"

        yield f"\n{'='*60}\n"
        yield f"最终结果：{'通过' if z3_result.verdict == Verdict.PASS else '失败'}\n"
        yield f"使用模式：{context.mode.value}\n"
        yield f"{'='*60}\n"

        # 返回完整结果
        result = ExecutionResult(
            task_id=task_id,
            code=context.code or "",
            mode=context.mode,
            verdict=z3_result.verdict.value,
            execution_time_ms=elapsed_ms,
            counterexample=z3_result.counterexample,
            upgrade_triggered=context.upgrade_triggered,
            history=context.history,
        )
        yield result  # type: ignore

    # 便捷方法
    def verify(self, code: str, spec: str, mode: str = "quick") -> dict:
        """单独验证一段代码"""
        z3_result = self.router.z3.verify(code, spec, mode=mode)
        return {
            "verdict": z3_result.verdict.value,
            "message": z3_result.message,
            "counterexample": z3_result.counterexample,
            "time_ms": z3_result.execution_time_ms,
        }


# 全局单例
_executor: ExecutorAgent | None = None


def get_executor() -> ExecutorAgent:
    global _executor
    if _executor is None:
        _executor = ExecutorAgent()
    return _executor
