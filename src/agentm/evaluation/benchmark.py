"""
评估系统（U 效用函数）

量化评估代码质量：
  - 正确性：编译/测试通过率
  - 性能：执行时间
  - 代码质量：LLM 评分
  - 奥运选手式对比：这次 vs 历史

反馈：全自动 Benchmark + 用户可反馈修正
"""

from __future__ import annotations

import time
import statistics
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

from ..agents.executor_agent import ExecutionResult
from ..core.z3_engine import Verdict


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class ScoreComponent(Enum):
    CORRECTNESS = "correctness"
    PERFORMANCE = "performance"
    CODE_QUALITY = "code_quality"
    OVERALL = "overall"


@dataclass
class BenchmarkResult:
    """单次任务的评估结果"""
    task_id: str

    # 正确性（0-1）
    correctness_score: float = 0.0
    z3_verdict: str = "unknown"
    test_pass_rate: float = 0.0
    boundary_cases_passed: int = 0
    boundary_cases_total: int = 0

    # 性能（0-1，毫秒转化的相对分）
    performance_score: float = 0.0
    execution_time_ms: float = 0.0

    # 代码质量（0-1）
    code_quality_score: float = 0.0
    readability: float = 0.0      # 可读性 0-10
    maintainability: float = 0.0  # 可维护性 0-10
    complexity: float = 0.0        # 圈复杂度

    # 综合分（加权平均）
    overall_score: float = 0.0

    # 对比数据
    vs_history_best: float | None = None  # vs 历史最佳，负数=更差
    vs_last_run: float | None = None    # vs 上次同类任务

    # 元数据
    mode_used: str = "unknown"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BenchmarkHistory:
    """同类任务的基准历史数据"""
    task_pattern: str              # 任务模式（前50字符）
    sample_count: int = 0
    avg_score: float = 0.0
    best_score: float = 0.0
    worst_score: float = 0.0
    avg_time_ms: float = 0.0
    scores: list[float] = field(default_factory=list)
    times_ms: list[float] = field(default_factory=list)

    def update(self, score: float, time_ms: float):
        self.scores.append(score)
        self.times_ms.append(time_ms)
        self.sample_count = len(self.scores)
        self.avg_score = statistics.mean(self.scores)
        self.best_score = max(self.scores)
        self.worst_score = min(self.scores)
        self.avg_time_ms = statistics.mean(self.times_ms)

    def vs_best(self, score: float) -> float:
        """相对历史最佳的差距（正数=更好）"""
        if self.best_score == 0:
            return 0.0
        return (score - self.best_score) / self.best_score

    def vs_last(self, score: float) -> float | None:
        """相对上次运行的差距"""
        if len(self.scores) < 2:
            return None
        return score - self.scores[-2]


# ---------------------------------------------------------------------------
# Evaluation Engine
# ---------------------------------------------------------------------------

class EvaluationEngine:
    """
    评估引擎：量化代码质量

    评分权重（可配置）：
      正确性 50% + 性能 20% + 代码质量 30% = 100%
    """

    def __init__(
        self,
        correctness_weight: float = 0.5,
        performance_weight: float = 0.2,
        quality_weight: float = 0.3,
        baseline_time_ms: float = 1000.0,  # 基准时间，用于性能评分
    ):
        self.correctness_weight = correctness_weight
        self.performance_weight = performance_weight
        self.quality_weight = quality_weight
        self.baseline_time_ms = baseline_time_ms

        # 任务历史（内存存储，可持久化到文件）
        self._history: dict[str, BenchmarkHistory] = {}

    def evaluate(self, result: ExecutionResult) -> BenchmarkResult:
        """评估一次执行结果"""
        # 1. 正确性评分
        correctness = self._evaluate_correctness(result)

        # 2. 性能评分
        performance = self._evaluate_performance(result)

        # 3. 代码质量评分（简化版）
        quality = self._evaluate_code_quality(result)

        # 4. 综合分
        overall = (
            correctness * self.correctness_weight
            + performance * self.performance_weight
            + quality * self.quality_weight
        )

        # 5. 对比历史
        pattern = result.mode.value
        history = self._get_history(pattern)
        history.update(overall, result.execution_time_ms)

        benchmark = BenchmarkResult(
            task_id=result.task_id,
            correctness_score=correctness,
            z3_verdict=result.verdict,
            performance_score=performance,
            execution_time_ms=result.execution_time_ms,
            code_quality_score=quality,
            overall_score=overall,
            vs_history_best=history.vs_best(overall),
            vs_last_run=history.vs_last(overall),
            mode_used=result.mode.value,
        )

        return benchmark

    def _evaluate_correctness(self, result: ExecutionResult) -> float:
        """评估正确性"""
        if result.verdict == "pass":
            return 1.0
        elif result.verdict == "fail":
            # 有反例说明部分正确
            if result.counterexample:
                return 0.3  # 有明显 bug
            return 0.5
        elif result.verdict == "unknown":
            return 0.5
        else:
            return 0.0

    def _evaluate_performance(self, result: ExecutionResult) -> float:
        """评估性能（相对评分，基于基准时间）"""
        if result.execution_time_ms == 0:
            return 0.0
        # 性能评分：基准时间内得满分，超时衰减
        ratio = self.baseline_time_ms / result.execution_time_ms
        # 上限为 1.0
        return min(1.0, ratio)

    def _evaluate_code_quality(self, result: ExecutionResult) -> float:
        """评估代码质量（简化版）"""
        if not result.code:
            return 0.0

        score = 0.5  # 默认基础分

        # 行数评分：50-200行算健康
        lines = len(result.code.splitlines())
        if 10 <= lines <= 100:
            score += 0.2
        elif 100 < lines <= 200:
            score += 0.1
        elif lines > 300:
            score -= 0.2  # 过长代码扣分

        # 有注释加一点
        comment_ratio = result.code.count('\n#') / max(lines, 1)
        if comment_ratio > 0.1:
            score += 0.1

        # 有 docstring 加一点
        if '"""' in result.code or "'''" in result.code:
            score += 0.1

        return max(0.0, min(1.0, score))

    def _get_history(self, pattern: str) -> BenchmarkHistory:
        if pattern not in self._history:
            self._history[pattern] = BenchmarkHistory(task_pattern=pattern)
        return self._history[pattern]

    def get_history(self, pattern: str) -> BenchmarkHistory | None:
        return self._history.get(pattern)

    def get_all_history(self) -> dict[str, BenchmarkHistory]:
        return self._history

    def summary(self) -> dict:
        """生成评估摘要"""
        if not self._history:
            return {"total_patterns": 0, "total_runs": 0}

        total_runs = sum(h.sample_count for h in self._history.values())
        overall_avg = statistics.mean(
            [h.avg_score for h in self._history.values() if h.sample_count > 0]
        ) if self._history else 0.0

        return {
            "total_patterns": len(self._history),
            "total_runs": total_runs,
            "overall_avg_score": overall_avg,
            "best_ever": max(
                (h.best_score for h in self._history.values()),
                default=0.0
            ),
        }


# ---------------------------------------------------------------------------
# Global Instance
# ---------------------------------------------------------------------------

_evaluator: EvaluationEngine | None = None


def get_evaluator() -> EvaluationEngine:
    global _evaluator
    if _evaluator is None:
        _evaluator = EvaluationEngine()
    return _evaluator
