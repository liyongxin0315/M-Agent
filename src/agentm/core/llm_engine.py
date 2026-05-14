"""
LLM 引擎：接入 Ollama（本地 qwen3）

功能：
  - 生成代码候选
  - 简单任务直接出结果
  - 复杂任务生成多个候选供 Z3 验证
"""

from __future__ import annotations

import ollama
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential


DEFAULT_MODEL = "qwen3"
DEFAULT_HOST = "http://127.0.0.1:11434"


class LLMEngine:
    """Ollama 本地推理引擎"""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        host: str = DEFAULT_HOST,
        temperature: float = 0.7,
        num_predict: int = 2048,
    ):
        self.model = model
        self.host = host
        self.temperature = temperature
        self.num_predict = num_predict

    def generate(self, prompt: str, system: str | None = None) -> str:
        """
        生成单一答案（简单任务用）
        """
        return self._call(prompt, system, n=1)[0]

    def generate_candidates(self, prompt: str, system: str | None = None, n: int = 5) -> list[str]:
        """
        生成多个候选（复杂任务用）
        n: 候选数量
        """
        return self._call(prompt, system, n=n)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def _call(self, prompt: str, system: str | None, n: int) -> list[str]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = ollama.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": self.temperature,
                    "num_predict": self.num_predict,
                },
            )
            content = response["message"]["content"]
            # 支持 n > 1 时 ollama 返回多个的情况
            if isinstance(content, list):
                return content
            # 否则按 n 分割（简单处理，实际可用 completion API）
            return [content]
        except Exception as e:
            logger.error(f"Ollama 调用失败: {e}")
            raise

    def health_check(self) -> bool:
        """检查 Ollama 是否可用"""
        try:
            ollama.ps(model=self.model, host=self.host)
            return True
        except Exception:
            return False


# 全局单例
_llm_engine: LLMEngine | None = None


def get_llm_engine() -> LLMEngine:
    global _llm_engine
    if _llm_engine is None:
        _llm_engine = LLMEngine()
    return _llm_engine


def init_llm_engine(model: str = DEFAULT_MODEL, host: str = DEFAULT_HOST, **kwargs) -> LLMEngine:
    global _llm_engine
    _llm_engine = LLMEngine(model=model, host=host, **kwargs)
    return _llm_engine
