"""
推理路由：根据任务复杂度决定走哪条路径

路径决策：
  简单 → LLM 直接生成 → Z3 抽检
  复杂 → LLM 生成多个候选 → Z3 严格验证

渐进式自动升级：
  所有任务先走简单模式
  Z3 抽检失败 → 自动升级到复杂模式
  结果存入记忆，下次同类任务直接选最优模式
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable
from loguru import logger

from .llm_engine import get_llm_engine, get_coding_engine, LLMEngine
from .z3_engine import get_z3_engine, Z3Engine, Verdict


class TaskMode(Enum):
    """任务处理模式"""
    SIMPLE = "simple"      # LLM + Z3 抽检
    COMPLEX = "complex"    # LLM 多候选 + Z3 严格验证


@dataclass
class TaskContext:
    """任务上下文"""
    task_id: str
    prompt: str             # 原始任务描述
    code: str | None = None  # 生成的代码
    mode: TaskMode = TaskMode.SIMPLE
    llm_result: str | None = None
    verification_result = None  # Z3Engine.VerificationResult
    upgrade_triggered: bool = False  # 是否触发过自动升级
    history: list = field(default_factory=list)  # 思考过程记录


@dataclass
class RouterDecision:
    """路由决策结果"""
    mode: TaskMode
    reason: str
    confidence: float = 1.0


class ReasoningRouter:
    """
    推理路由：决定任务走简单还是复杂路径
    支持渐进式自动升级
    """

    def __init__(
        self,
        llm_engine: LLMEngine | None = None,
        z3_engine: Z3Engine | None = None,
    ):
        self.llm = llm_engine or get_coding_engine()  # 代码专项模型
        self.z3 = z3_engine or get_z3_engine()

        # 记忆：同类任务的最佳模式（task_pattern → mode）
        self._mode_cache: dict[str, TaskMode] = {}

    def decide(self, prompt: str, context: TaskContext) -> RouterDecision:
        """
        决策：走简单还是复杂
        """
        # 1. 先查记忆缓存
        cache_key = self._cache_key(prompt)
        if cache_key in self._mode_cache:
            cached_mode = self._mode_cache[cache_key]
            return RouterDecision(
                mode=cached_mode,
                reason="从历史记忆读取，同类任务上次用此模式",
                confidence=0.9,
            )

        # 2. 无历史，用简单模式起步
        return RouterDecision(
            mode=TaskMode.SIMPLE,
            reason="无历史记录，默认简单模式",
            confidence=0.5,
        )

    def execute(self, context: TaskContext) -> TaskContext:
        """
        执行完整推理流程

        流程：
          1. 决策模式
          2. 调用 LLM 生成
          3. 调用 Z3 验证
          4. 失败则自动升级
        """
        decision = self.decide(context.prompt, context)
        context.mode = decision.mode

        # 第一次尝试
        context = self._try_mode(context)

        # 渐进式升级：简单失败 → 换复杂
        if (
            context.verification_result is not None
            and context.verification_result.verdict == Verdict.FAIL
            and not context.upgrade_triggered
        ):
            logger.info("简单模式 Z3 抽检失败，触发自动升级到复杂模式")
            context.upgrade_triggered = True
            context.mode = TaskMode.COMPLEX
            context.history.append({
                "event": "auto_upgrade",
                "reason": "simple_mode_failed",
                "verdict": context.verification_result.verdict.value,
            })
            context = self._try_mode(context)

        # 记录缓存
        self._cache_mode(context)

        return context

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _try_mode(self, context: TaskContext) -> TaskContext:
        """按指定模式执行一次"""
        if context.mode == TaskMode.SIMPLE:
            return self._execute_simple(context)
        else:
            return self._execute_complex(context)

    def _execute_simple(self, context: TaskContext) -> TaskContext:
        """
        简单模式：LLM 直接出 → Z3 抽检
        """
        context.history.append({"event": "mode_start", "mode": "simple"})

        # LLM 生成
        code = self.llm.generate(
            prompt=f"请生成代码：\n{context.prompt}",
            system="你是一个代码生成助手。只输出代码，不输出解释。",
        )
        context.llm_result = code
        context.code = code

        context.history.append({
            "event": "llm_generated",
            "mode": "simple",
            "code_length": len(code),
        })

        # Z3 抽检
        spec = self._extract_spec(context.prompt)
        z3_result = self.z3.verify(code, spec, mode="quick")
        context.verification_result = z3_result

        context.history.append({
            "event": "z3_verified",
            "mode": "simple",
            "verdict": z3_result.verdict.value,
            "time_ms": z3_result.execution_time_ms,
        })

        return context

    def _execute_complex(self, context: TaskContext) -> TaskContext:
        """
        复杂模式：LLM 生成多个候选 → Z3 严格验证
        """
        context.history.append({"event": "mode_start", "mode": "complex"})

        # LLM 生成 5 个候选
        candidates = self.llm.generate_candidates(
            prompt=f"请生成5个不同的代码实现：\n{context.prompt}",
            system="你是一个代码生成助手。请生成5个不同的实现方案，编号为1-5。只输出代码。",
            n=5,
        )

        context.history.append({
            "event": "llm_candidates",
            "mode": "complex",
            "count": len(candidates),
        })

        # Z3 严格验证每个候选
        spec = self._extract_spec(context.prompt)
        best_candidate = None
        best_result = None

        for i, candidate in enumerate(candidates):
            result = self.z3.verify(candidate, spec, mode="strict")
            context.history.append({
                "event": "z3_strict_verified",
                "mode": "complex",
                "candidate_index": i,
                "verdict": result.verdict.value,
                "time_ms": result.execution_time_ms,
            })

            # 选最优：PASS > UNKNOWN > TIMEOUT > FAIL
            if best_result is None or self._better(result, best_result):
                best_candidate = candidate
                best_result = result

        context.code = best_candidate
        context.llm_result = best_candidate
        context.verification_result = best_result

        return context

    def _better(self, a, b) -> bool:
        """比较两个验证结果，a比b好返回True"""
        order = {Verdict.PASS: 0, Verdict.UNKNOWN: 1, Verdict.TIMEOUT: 2, Verdict.FAIL: 3, Verdict.ERROR: 4}
        return order[a.verdict] < order[b.verdict]

    def _extract_spec(self, prompt: str) -> str:
        """从 prompt 中提取规格说明（简化版）"""
        # 简化：直接用 prompt 作为 spec
        # 实际需要 LLM 抽取或用户明确指定
        return prompt

    def _cache_key(self, prompt: str) -> str:
        """生成缓存 key"""
        # 简化：用 prompt 前50字符
        return prompt[:50].strip().lower()

    def _cache_mode(self, context: TaskContext):
        """记录此任务的最佳模式到缓存"""
        key = self._cache_key(context.prompt)
        self._mode_cache[key] = context.mode


# 全局单例
_router: ReasoningRouter | None = None


def get_router() -> ReasoningRouter:
    global _router
    if _router is None:
        _router = ReasoningRouter()
    return _router
