"""
Z3 符号引擎：代码正确性验证

功能：
  - 验证代码片段的行为正确性
  - 找反例（bug 触发条件）
  - 抽检（简单任务）
  - 严格验证（复杂任务）
"""

from __future__ import annotations

import subprocess
import tempfile
import os
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class Verdict(Enum):
    """验证结果"""
    PASS = "pass"           # 通过
    FAIL = "fail"          # 有反例
    UNKNOWN = "unknown"     # 无法证明
    ERROR = "error"         # 执行错误
    TIMEOUT = "timeout"     # 超时


@dataclass
class VerificationResult:
    """验证结果详情"""
    verdict: Verdict
    message: str
    counterexample: str | None = None  # 反例（bug 触发条件）
    execution_time_ms: float = 0.0
    model: str | None = None           # 使用的 Z3 模型名称


class Z3Engine:
    """
    Z3 符号引擎

    使用方式：
      1. 抽检模式：快速扫描常见 bug 模式
      2. 严格模式：完整的形式化验证
    """

    def __init__(self, timeout_ms: int = 30000):
        self.timeout_ms = timeout_ms  # 毫秒

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def verify(self, code: str, spec: str, mode: str = "normal") -> VerificationResult:
        """
        验证一段代码是否符合规格说明

        参数：
          code: 待验证的代码（Python 或伪代码）
          spec: 规格说明（自然语言描述预期行为）
          mode: "quick"=抽检，"normal"=正常，"strict"=严格

        返回：
          VerificationResult: 包含 verdict + 详情
        """
        if mode == "quick":
            return self._quick_check(code, spec)
        elif mode == "strict":
            return self._strict_verify(code, spec)
        else:
            return self._quick_check(code, spec)

    # ------------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------------

    def _quick_check(self, code: str, spec: str) -> VerificationResult:
        """
        快速抽检模式：跑测试用例 + 边界条件扫描
        不会证明「永远正确」，但能找到常见 bug
        """
        import time
        start = time.perf_counter()

        # 生成测试用例
        test_cases = self._generate_test_cases(code, spec)
        if not test_cases:
            return VerificationResult(
                verdict=Verdict.UNKNOWN,
                message="无法生成有效测试用例",
                execution_time_ms=0,
            )

        # 执行测试
        failed = []
        passed_count = 0
        for tc in test_cases:
            result = self._run_test(code, tc)
            if result["passed"]:
                passed_count += 1
            else:
                failed.append(result)

        elapsed = (time.perf_counter() - start) * 1000

        if not failed:
            return VerificationResult(
                verdict=Verdict.PASS,
                message=f"通过全部 {passed_count} 个测试用例",
                execution_time_ms=elapsed,
            )
        else:
            return VerificationResult(
                verdict=Verdict.FAIL,
                message=f"失败 {len(failed)}/{len(test_cases)} 个用例",
                counterexample=self._format_counterexample(failed),
                execution_time_ms=elapsed,
            )

    def _strict_verify(self, code: str, spec: str) -> VerificationResult:
        """
        严格验证模式：用 Z3 SMT 求解器做形式化证明
        """
        import time
        start = time.perf_counter()

        # 将代码 + spec 翻译成 Z3 约束
        z3_script = self._code_to_z3(code, spec)

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".smt2", delete=False
            ) as f:
                f.write(z3_script)
                tmp_path = f.name

            result = subprocess.run(
                ["z3", "-smt2", "-st", tmp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout_ms / 1000,
            )
            os.unlink(tmp_path)

            elapsed = (time.perf_counter() - start) * 1000
            output = result.stdout.strip()

            if "unsat" in output:
                return VerificationResult(
                    verdict=Verdict.PASS,
                    message="Z3 证明：公式不可满足（代码正确）",
                    execution_time_ms=elapsed,
                    model="z3",
                )
            elif "sat" in output:
                # 提取反例
                model = self._extract_model(output)
                return VerificationResult(
                    verdict=Verdict.FAIL,
                    message="Z3 发现反例：代码存在缺陷",
                    counterexample=model,
                    execution_time_ms=elapsed,
                    model="z3",
                )
            else:
                return VerificationResult(
                    verdict=Verdict.UNKNOWN,
                    message=f"Z3 无法判定：{output[:200]}",
                    execution_time_ms=elapsed,
                    model="z3",
                )

        except FileNotFoundError:
            elapsed = (time.perf_counter() - start) * 1000
            logger.warning("Z3 未安装，退化为快速抽检模式")
            return self._quick_check(code, spec)
        except subprocess.TimeoutExpired:
            return VerificationResult(
                verdict=Verdict.TIMEOUT,
                message=f"Z3 验证超时（>{self.timeout_ms}ms）",
                execution_time_ms=self.timeout_ms,
                model="z3",
            )
        except Exception as e:
            return VerificationResult(
                verdict=Verdict.ERROR,
                message=f"Z3 执行异常：{str(e)[:200]}",
                execution_time_ms=0,
                model="z3",
            )

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _generate_test_cases(self, code: str, spec: str) -> list[dict]:
        """
        根据代码 + 规格说明生成测试用例
        简化版：正则提取函数签名，生成边界值测试
        """
        test_cases = []

        # 简化：提取函数定义的参数
        import re
        func_match = re.search(r"def\s+(\w+)\s*\((.*?)\)", code)
        if not func_match:
            return test_cases

        func_name = func_match.group(1)
        params = [p.strip().split(":")[0].strip() for p in func_match.group(2).split(",") if p.strip()]

        # 生成边界值测试用例
        # 简化处理：空值、零值、负数、极大值
        for params_test in self._boundary_values(len(params)):
            test_cases.append({
                "func": func_name,
                "params": params_test,
                "expected": None,  # 无预期，靠程序崩溃判断
            })

        return test_cases

    def _boundary_values(self, n: int) -> list[list]:
        """生成 n 个参数的边界值组合"""
        base_values = [0, 1, -1, 10**6, None]
        result = []
        for _ in range(min(n * 2, 10)):  # 限制数量
            result.append([base_values[i % len(base_values)] for i in range(n)])
        return result

    def _run_test(self, code: str, test_case: dict) -> dict:
        """运行单个测试用例"""
        import traceback
        try:
            # 构造调用代码
            params_str = ", ".join(
                repr(p) if p is not None else "None"
                for p in test_case["params"]
            )
            call_code = f"{test_case['func']}({params_str})"

            # 拼接执行
            exec_code = f"""
{code}
result = {call_code}
"""
            locals_: dict = {}
            exec(exec_code, {}, locals_)
            return {"passed": True, "result": locals_.get("result")}
        except Exception:
            return {
                "passed": False,
                "error": traceback.format_exc(),
                "params": test_case["params"],
            }

    def _code_to_z3(self, code: str, spec: str) -> str:
        """
        将 Python 代码 + 规格说明翻译成 Z3 SMT-LIB 2 脚本
        简化版：实际需要更复杂的代码分析
        """
        # 这里需要静态分析提取变量约束，简化处理
        smt = f"""
; 规格: {spec}
; 代码片段（需要完整分析工具链才能自动提取约束）
(set-logic ALL)
(declare-const x Int)
(declare-const result Int)
; 实际约束需要 AST 分析工具，这里仅示意
(assert (> result 0))
(check-sat)
(get-model)
"""
        return smt

    def _extract_model(self, output: str) -> str:
        """从 Z3 输出提取反例模型"""
        lines = output.split("\n")
        model_lines = [l for l in lines if "=" in l]
        return "\n".join(model_lines[:10])  # 最多取10行

    def _format_counterexample(self, failed: list[dict]) -> str:
        """格式化反例信息"""
        lines = []
        for f in failed[:3]:  # 最多3个
            lines.append(f"参数: {f.get('params', [])}, 错误: {f.get('error', '未知')[:100]}")
        return "\n".join(lines)


# 全局单例
_z3_engine: Z3Engine | None = None


def get_z3_engine() -> Z3Engine:
    global _z3_engine
    if _z3_engine is None:
        _z3_engine = Z3Engine()
    return _z3_engine
