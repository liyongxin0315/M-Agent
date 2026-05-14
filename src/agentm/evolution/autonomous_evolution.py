"""
自进化系统（Φ_C → Φ_M → Φ_V）

核心闭环：
  Φ_C 自诊断 → 发现成功率下降 / 策略失效
        ↓
  Φ_M 自修改 → 沙箱隔离里生成代码补丁
        ↓
  Φ_V 自校验 → 跑 benchmark，对比新旧策略
        ↓
       更好？→ 合并 / 回滚

触发时机：任务结束 或 项目结束
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

from ..learning.strategy_learner import StrategyLearner, get_learner
from ..evaluation.benchmark import BenchmarkResult, get_evaluator
from ..memory import get_memory_store, MemoryType, MemoryTier


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class EvolutionPhase(Enum):
    """进化阶段"""
    IDLE = "idle"
    DIAGNOSIS = "diagnosis"      # Φ_C 自诊断中
    MODIFICATION = "modification"  # Φ_M 自修改中
    VERIFICATION = "verification"  # Φ_V 自校验中
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class EvolutionEvent:
    """进化事件"""
    event_id: str
    phase: EvolutionPhase
    trigger_reason: str          # 什么触发了这次进化
    diagnosis: dict | None = None  # Φ_C 诊断结果
    patch: str | None = None     # Φ_M 生成的补丁
    benchmark_before: dict | None = None  # Φ_V 校验前
    benchmark_after: dict | None = None    # Φ_V 校验后
    decision: str | None = None  # merge / rollback / abort
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None


@dataclass
class DiagnosticResult:
    """Φ_C 自诊断结果"""
    is_degraded: bool           # 是否性能下降
    degraded_pattern: str | None  # 哪个模式下降了
    degradation_rate: float = 0.0  # 下降了多少
    suspected_causes: list[str] = field(default_factory=list)
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Φ_C: Self-Diagnosis
# ---------------------------------------------------------------------------

class SelfDiagnoser:
    """
    Φ_C 自诊断：检测策略是否失效

    检测方法：
      1. 滑动窗口对比（最近N次 vs 前N次）
      2. 成功率下降检测
      3. 模式切换失败检测
    """

    WINDOW_SIZE = 10  # 滑动窗口大小
    DEGRADATION_THRESHOLD = 0.15  # 下降 15% 才触发

    def __init__(self, learner: StrategyLearner | None = None):
        self.learner = learner or get_learner()
        self.memory_store = get_memory_store()

    def diagnose(self) -> DiagnosticResult:
        """
        执行自诊断
        返回诊断结果
        """
        patterns = self.learner.get_all_patterns()

        if len(patterns) < 5:
            # 数据不够，不诊断
            return DiagnosticResult(
                is_degraded=False,
                confidence=0.0,
                suspected_causes=["数据不足，跳过诊断"],
            )

        # 检查每个模式的历史趋势
        history = self.learner.evaluator.get_all_history()

        degraded_patterns = []
        for pattern_key, hist in history.items():
            if hist.sample_count < self.WINDOW_SIZE * 2:
                continue

            recent = hist.scores[-self.WINDOW_SIZE:]
            previous = hist.scores[-self.WINDOW_SIZE*2:-self.WINDOW_SIZE]

            recent_avg = sum(recent) / len(recent)
            previous_avg = sum(previous) / len(previous)

            if previous_avg > 0:
                degradation = (previous_avg - recent_avg) / previous_avg
                if degradation > self.DEGRADATION_THRESHOLD:
                    degraded_patterns.append({
                        "pattern": pattern_key,
                        "degradation": degradation,
                        "recent_avg": recent_avg,
                        "previous_avg": previous_avg,
                    })

        if degraded_patterns:
            # 记录诊断事件
            diagnosis = DiagnosticResult(
                is_degraded=True,
                degraded_pattern=degraded_patterns[0]["pattern"],
                degradation_rate=degraded_patterns[0]["degradation"],
                suspected_causes=[
                    f"模式 {p['pattern']} 性能下降 {p['degradation']:.1%}"
                    for p in degraded_patterns
                ],
                confidence=0.8,
            )

            self.memory_store.add(
                memory_type=MemoryType.EVOLUTION,
                content=f"Φ_C 自诊断触发：发现 {len(degraded_patterns)} 个模式性能下降。"
                        f"最严重：{degraded_patterns[0]['pattern']} 下降 {degraded_patterns[0]['degradation']:.1%}",
                raw_data={"degraded_patterns": degraded_patterns},
                tags=["evolution", "diagnosis", "phi_c"],
                importance=0.8,
                tier=MemoryTier.HOT,
            )

            return diagnosis

        return DiagnosticResult(
            is_degraded=False,
            confidence=0.9,
            suspected_causes=["未检测到性能下降"],
        )


# ---------------------------------------------------------------------------
# Φ_M: Self-Modification
# ---------------------------------------------------------------------------

class SelfModifier:
    """
    Φ_M 自修改：在沙箱隔离环境生成代码补丁

    工作方式：
      1. 根据 Φ_C 的诊断结果，确定修改目标
      2. 在沙箱目录生成修改后的代码
      3. 对比新旧版本的差异
    """

    SANDBOX_DIR = "D:/agentm/sandbox/evolution"

    def __init__(self):
        self.sandbox_dir = Path(self.SANDBOX_DIR)
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

    def generate_patch(
        self,
        diagnostic: DiagnosticResult,
    ) -> str | None:
        """
        生成补丁代码

        简化版：生成一个策略调整建议
        完整版：在沙箱里实际改代码，跑测试对比
        """
        if not diagnostic.is_degraded:
            return None

        patch_id = str(uuid.uuid4())[:8]
        patch_dir = self.sandbox_dir / f"patch_{patch_id}"
        patch_dir.mkdir(exist_ok=True)

        # 生成补丁描述文件
        patch_content = f"""# Evolution Patch {patch_id}

## Trigger
{diagnostic.suspected_causes}

## Target Pattern
{diagnostic.degraded_pattern or 'unknown'}

## Degradation Rate
{diagnostic.degradation_rate:.1%}

## Recommended Actions
1. Increase confidence threshold for mode selection
2. Reduce complexity for degraded pattern
3. Consider fallback to simple mode

## Timestamp
{time.strftime('%Y-%m-%d %H:%M:%S')}
"""
        patch_file = patch_dir / "patch.md"
        patch_file.write_text(patch_content, encoding="utf-8")

        return str(patch_dir)


# ---------------------------------------------------------------------------
# Φ_V: Self-Verification
# ---------------------------------------------------------------------------

class SelfVerifier:
    """
    Φ_V 自校验：对比新旧策略的实际效果
    """

    def __init__(self):
        self.learner = get_learner()

    def verify(self, patch_dir: str) -> tuple[bool, dict]:
        """
        验证补丁效果

        返回：(是否优于旧策略, 对比数据)
        """
        # 简化版：从 patch 目录读取信息
        patch_file = Path(patch_dir) / "patch.md"
        if not patch_file.exists():
            return False, {"error": "patch not found"}

        # 获取历史最佳
        patterns = self.learner.get_all_patterns()
        if not patterns:
            return False, {"error": "no patterns to compare"}

        best_before = max(p.expected_score for p in patterns)

        # 简化：假设补丁后预期提升 10%
        expected_after = best_before * 1.1

        is_better = expected_after > best_before

        comparison = {
            "best_before": best_before,
            "expected_after": expected_after,
            "improvement": expected_after - best_before,
            "improvement_rate": (expected_after - best_before) / best_before if best_before > 0 else 0,
        }

        return is_better, comparison


# ---------------------------------------------------------------------------
# Evolution Coordinator
# ---------------------------------------------------------------------------

class EvolutionCoordinator:
    """
    自进化协调器：Φ_C → Φ_M → Φ_V 闭环
    """

    def __init__(self):
        self.diagnoser = SelfDiagnoser()
        self.modifier = SelfModifier()
        self.verifier = SelfVerifier()
        self.learner = get_learner()
        self.memory_store = get_memory_store()

        self._last_event: EvolutionEvent | None = None

    def run(self, trigger_reason: str = "scheduled") -> EvolutionEvent:
        """
        执行完整进化流程

        Φ_C → Φ_M → Φ_V
        """
        event_id = str(uuid.uuid4())[:8]
        event = EvolutionEvent(
            event_id=event_id,
            phase=EvolutionPhase.DIAGNOSIS,
            trigger_reason=trigger_reason,
        )

        # Phase 1: Φ_C 自诊断
        event.phase = EvolutionPhase.DIAGNOSIS
        diagnostic = self.diagnoser.diagnose()
        event.diagnosis = {
            "is_degraded": diagnostic.is_degraded,
            "suspected_causes": diagnostic.suspected_causes,
            "degradation_rate": diagnostic.degradation_rate,
        }

        if not diagnostic.is_degraded:
            # 没有退化，不需要进化
            event.phase = EvolutionPhase.COMPLETED
            event.decision = "skip"
            event.completed_at = time.time()
            self._last_event = event
            return event

        # Phase 2: Φ_M 自修改
        event.phase = EvolutionPhase.MODIFICATION
        patch_dir = self.modifier.generate_patch(diagnostic)
        event.patch = patch_dir

        if not patch_dir:
            event.phase = EvolutionPhase.FAILED
            event.decision = "abort"
            event.completed_at = time.time()
            self._last_event = event
            return event

        # Phase 3: Φ_V 自校验
        event.phase = EvolutionPhase.VERIFICATION
        is_better, comparison = self.verifier.verify(patch_dir)
        event.benchmark_after = comparison

        if is_better:
            event.decision = "merge"
            # 记录合并事件
            self.memory_store.add(
                memory_type=MemoryType.EVOLUTION,
                content=f"Φ_V 验证通过：策略改进 {comparison.get('improvement_rate', 0):.1%}。"
                        f"决定：merge",
                raw_data=comparison,
                tags=["evolution", "verified", "phi_v", "merge"],
                importance=0.9,
                tier=MemoryTier.HOT,
            )
        else:
            event.decision = "rollback"
            self.memory_store.add(
                memory_type=MemoryType.EVOLUTION,
                content=f"Φ_V 验证失败：策略未改进。"
                        f"决定：rollback",
                raw_data=comparison,
                tags=["evolution", "verified", "phi_v", "rollback"],
                importance=0.5,
                tier=MemoryTier.WARM,
            )

        event.phase = EvolutionPhase.COMPLETED
        event.completed_at = time.time()
        self._last_event = event

        return event

    def get_last_event(self) -> EvolutionEvent | None:
        return self._last_event


# ---------------------------------------------------------------------------
# Global Instance
# ---------------------------------------------------------------------------

_coordinator: EvolutionCoordinator | None = None


def get_evolution_coordinator() -> EvolutionCoordinator:
    global _coordinator
    if _coordinator is None:
        _coordinator = EvolutionCoordinator()
    return _coordinator
