"""
学习系统（L 学习算子）

从评估数据提取模式，改进策略：
  - 任务学习：同类任务用什么策略最好
  - 元学习：学习「如何学习」本身
  - 策略固化：3x 重复成功 → 升级为规则
"""

from __future__ import annotations

import time
import statistics
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

from ..evaluation.benchmark import BenchmarkResult, EvaluationEngine, get_evaluator
from ..memory import get_memory_store, MemoryType, MemoryTier


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class LearningSignal(Enum):
    """学习信号来源"""
    BENCHMARK = "benchmark"     # Benchmark 数据
    USER_FEEDBACK = "user_feedback"  # 用户纠正/反馈
    SELF_REFLECTION = "self_reflection"  # 自我反思
    EXECUTION_FAILURE = "execution_failure"  # 执行失败


@dataclass
class LearnedPattern:
    """学到的模式"""
    id: str
    pattern_key: str         # 模式标识（如 "sort_large_array"）
    description: str          # 模式描述

    # 策略信息
    recommended_mode: str    # 推荐模式（simple/complex）
    expected_score: float     # 期望分数

    # 证据
    supporting_runs: int = 0  # 支撑这个模式的成功次数
    evidence: list[dict] = field(default_factory=list)  # 具体证据

    # 学习元数据
    confidence: float = 0.5   # 置信度 0-1
    source: str = "auto"      # auto | manual

    # 时间戳
    learned_at: float = field(default_factory=time.time)
    last_verified_at: float = field(default_factory=time.time)
    verified_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Strategy Learner
# ---------------------------------------------------------------------------

class StrategyLearner:
    """
    策略学习器

    从 Benchmark 数据中提取模式，改进决策策略

    核心逻辑：
      1. 记录每次 Benchmark 结果
      2. 同类任务聚类分析
      3. 发现规律 → LearnedPattern
      4. 3x 验证成功 → 置信度提升
      5. 置信度 > 阈值 → 固化到知识库
    """

    PROMOTION_THRESHOLD = 3  # 3次成功才提升
    CONFIDENCE_THRESHOLD = 0.7  # 置信度阈值

    def __init__(self, evaluator: EvaluationEngine | None = None):
        self.evaluator = evaluator or get_evaluator()
        self.memory_store = get_memory_store()

        # 学到的模式库
        self._patterns: dict[str, LearnedPattern] = {}

        # 模式键→置信度统计
        self._pattern_runs: dict[str, list[bool]] = {}

    def record(self, result: BenchmarkResult) -> LearnedPattern | None:
        """
        记录一次 Benchmark 结果，从中学习
        返回：如果生成了新模式或更新了模式，返回它
        """
        pattern_key = self._extract_pattern_key(result)
        is_success = result.overall_score >= 0.7

        # 记录运行
        if pattern_key not in self._pattern_runs:
            self._pattern_runs[pattern_key] = []
        self._pattern_runs[pattern_key].append(is_success)

        # 更新或创建模式
        pattern = self._patterns.get(pattern_key)
        if pattern:
            pattern = self._update_pattern(pattern, result, is_success)
        else:
            pattern = self._create_pattern(pattern_key, result)
            self._patterns[pattern_key] = pattern

        # 检查是否要固化到记忆
        if self._should_promote(pattern):
            self._promote_to_memory(pattern)

        return pattern

    def _extract_pattern_key(self, result: BenchmarkResult) -> str:
        """从结果提取模式键（简化：基于模式名称）"""
        # 简化版：用 mode + verdict 作为 key
        return f"{result.mode_used}:{result.z3_verdict}"

    def _create_pattern(
        self,
        pattern_key: str,
        result: BenchmarkResult,
    ) -> LearnedPattern:
        """创建新模式"""
        pattern = LearnedPattern(
            id=f"pattern_{pattern_key}_{int(time.time())}",
            pattern_key=pattern_key,
            description=f"任务模式 {pattern_key}",
            recommended_mode=result.mode_used,
            expected_score=result.overall_score,
            supporting_runs=1,
            evidence=[{
                "task_id": result.task_id,
                "score": result.overall_score,
                "time_ms": result.execution_time_ms,
            }],
            confidence=0.3,  # 新模式低置信度
            source="auto",
        )
        return pattern

    def _update_pattern(
        self,
        pattern: LearnedPattern,
        result: BenchmarkResult,
        is_success: bool,
    ) -> LearnedPattern:
        """更新已有模式"""
        pattern.supporting_runs += 1
        pattern.evidence.append({
            "task_id": result.task_id,
            "score": result.overall_score,
            "time_ms": result.execution_time_ms,
        })

        # 更新期望分数（移动平均）
        old_score = pattern.expected_score
        pattern.expected_score = 0.7 * old_score + 0.3 * result.overall_score

        # 更新置信度
        runs = self._pattern_runs[pattern.pattern_key]
        success_rate = sum(runs) / len(runs)
        pattern.confidence = min(1.0, pattern.confidence + 0.1 * success_rate)

        pattern.last_verified_at = time.time()

        return pattern

    def _should_promote(self, pattern: LearnedPattern) -> bool:
        """判断是否应该固化到知识库"""
        # 条件：3次以上成功 且 置信度高于阈值
        if pattern.supporting_runs >= self.PROMOTION_THRESHOLD:
            if pattern.confidence >= self.CONFIDENCE_THRESHOLD:
                return True
        return False

    def _promote_to_memory(self, pattern: LearnedPattern):
        """将模式固化到记忆系统"""
        memory = self.memory_store.add(
            memory_type=MemoryType.EVOLUTION,
            content=f"策略进化：{pattern.description}。"
                    f"推荐模式：{pattern.recommended_mode}，"
                    f"期望分数：{pattern.expected_score:.2f}，"
                    f"置信度：{pattern.confidence:.2f}，"
                    f"验证次数：{pattern.verified_count}",
            raw_data=pattern.to_dict(),
            tags=["strategy", "learned", pattern.pattern_key],
            importance=pattern.confidence,
            tier=MemoryTier.HOT,
        )

        # 更新模式记录
        pattern.verified_count += 1
        pattern.last_verified_at = time.time()

        return memory

    def suggest_mode(self, task_description: str) -> str:
        """
        根据历史模式建议任务走哪个模式
        这是策略学习的核心输出
        """
        # 简化：查找最接近的模式
        best_pattern = None
        best_confidence = 0.0

        for pattern in self._patterns.values():
            if pattern.confidence > best_confidence:
                best_confidence = pattern.confidence
                best_pattern = pattern

        if best_pattern and best_pattern.confidence >= 0.5:
            return best_pattern.recommended_mode

        return "auto"  # 默认自动

    def get_all_patterns(self) -> list[LearnedPattern]:
        """获取所有学到的模式"""
        return list(self._patterns.values())

    def summary(self) -> dict:
        """生成学习摘要"""
        patterns = self._patterns.values()
        return {
            "total_patterns": len(patterns),
            "high_confidence": sum(1 for p in patterns if p.confidence >= 0.7),
            "verified": sum(1 for p in patterns if p.verified_count > 0),
            "most_confident": max(
                [(p.pattern_key, p.confidence) for p in patterns],
                default=("none", 0.0),
                key=lambda x: x[1]
            ),
        }


# ---------------------------------------------------------------------------
# Global Instance
# ---------------------------------------------------------------------------

_learner: StrategyLearner | None = None


def get_learner() -> StrategyLearner:
    global _learner
    if _learner is None:
        _learner = StrategyLearner()
    return _learner
