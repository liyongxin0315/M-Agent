"""
主Agent 协调器（G 目标空间 + S 状态空间）

职责：
  - 接收用户指令
  - 意图分析（解析要做什么、复杂度如何）
  - 任务拆解（拆成子任务，分发给对应Agent）
  - 结果汇总（流式输出）
  - 状态管理（记录当前状态）
"""

from __future__ import annotations

import uuid
import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Callable
from loguru import logger

from ..agents import get_executor, ExecutorAgent


class IntentType(Enum):
    """意图类型"""
    CHAT = "chat"                    # 闲聊/打招呼
    CODE_GENERATE = "code_generate"   # 生成代码
    CODE_FIX = "code_fix"            # 修复bug
    CODE_REFACTOR = "code_refactor"   # 重构
    CODE_REVIEW = "code_review"       # 审查
    QUERY = "query"                  # 知识问答
    TASK = "task"                    # 通用任务


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """任务"""
    task_id: str
    description: str
    intent: IntentType = IntentType.TASK
    mode: str = "auto"               # auto/simple/complex
    parent_id: str | None = None      # 父任务ID
    sub_tasks: list[str] = field(default_factory=list)  # 子任务ID列表
    result: Any = None
    error: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None


@dataclass
class CoordinatorState:
    """协调器全局状态"""
    session_id: str
    tasks: dict[str, Task] = field(default_factory=dict)
    completed_task_ids: list[str] = field(default_factory=list)
    failed_task_ids: list[str] = field(default_factory=list)
    context: dict = field(default_factory=dict)  # 跨任务上下文


class IntentParser:
    """意图解析器：分析用户指令，决定意图类型和复杂度"""

    KEYWORDS = {
        IntentType.CHAT: [
            "你好", "hi", "hello", "嗨", "hey", "早上好", "下午好", "晚上好",
            "你是谁", "叫什么", "干什么的", "有什么功能", "能做什么",
        ],
        IntentType.CODE_GENERATE: [
            "写", "生成", "帮我写", "实现", "创建", "代码", "function", "def ",
            "class ", "帮我写个", "写一个", "generate", "write", "create",
        ],
        IntentType.CODE_FIX: [
            "修复", "bug", "报错", "崩了", "fix", "repair", "debug", "错误",
        ],
        IntentType.CODE_REFACTOR: [
            "重构", "优化", "重写", "改写", "refactor", "optimize",
        ],
        IntentType.CODE_REVIEW: [
            "审查", "review", "检查代码", "看看这段代码", "分析代码",
        ],
    }

    def parse(self, prompt: str) -> tuple[IntentType, str]:
        """
        解析用户指令
        返回：(意图类型, 任务描述)
        """
        prompt_lower = prompt.lower().strip()

        for intent, keywords in self.KEYWORDS.items():
            for kw in keywords:
                if kw in prompt_lower:
                    return intent, prompt

        # 默认按代码生成处理（因为这是第一个专项）
        return IntentType.CODE_GENERATE, prompt

    def extract_task_description(self, prompt: str) -> str:
        """提取核心任务描述（去掉语气词和废话）"""
        # 简化版：去掉「帮我」「请」等
        desc = prompt.strip()
        for prefix in ["帮我", "请", "能不能", "可以不可以"]:
            if desc.startswith(prefix):
                desc = desc[len(prefix):]
        return desc


class ResultAggregator:
    """结果汇总器：将各子Agent的结果汇总成统一输出"""

    def __init__(self):
        self._chunks: list[str] = []

    def add_chunk(self, chunk: str):
        self._chunks.append(chunk)

    def add_result(self, result: Any):
        self._chunks.append(str(result))

    def aggregate(self, format: str = "text") -> str:
        """汇总所有结果片段"""
        if format == "text":
            return "\n".join(self._chunks)
        elif format == "json":
            import json
            return json.dumps({"chunks": self._chunks}, ensure_ascii=False)
        return "\n".join(self._chunks)

    def reset(self):
        self._chunks.clear()


class Coordinator:
    """
    主Agent 协调器

    使用方式：
      coord = Coordinator()
      async for chunk in coord.run("帮我写一个快排"):
          print(chunk, end="", flush=True)
    """

    def __init__(
        self,
        executor: ExecutorAgent | None = None,
        intent_parser: IntentParser | None = None,
        session_id: str | None = None,
    ):
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.executor = executor or get_executor()
        self.intent_parser = intent_parser or IntentParser()
        self.state = CoordinatorState(session_id=self.session_id)
        self._result_agg = ResultAggregator()

    async def run(self, prompt: str) -> AsyncGenerator[str, None]:
        """
        异步流式执行：接收任务 → 分析 → 分发 → 流式输出结果
        """
        # 1. 意图解析
        intent, task_desc = self.intent_parser.parse(prompt)
        task_id = str(uuid.uuid4())[:8]
        task = Task(
            task_id=task_id,
            description=task_desc,
            intent=intent,
        )
        self.state.tasks[task_id] = task

        yield f"[Coordinator] 会话ID: {self.session_id}\n"
        yield f"[Coordinator] 任务ID: {task_id}\n"
        yield f"[Coordinator] 意图: {intent.value}\n"
        yield f"[Coordinator] 任务: {task_desc}\n\n"

        task.status = TaskStatus.RUNNING
        task.started_at = time.time()

        try:
            # 2. 根据意图类型分发
            if intent in (IntentType.CODE_GENERATE, IntentType.CODE_FIX,
                          IntentType.CODE_REFACTOR, IntentType.CODE_REVIEW):
                async for chunk in self._run_code_task(task):
                    yield chunk
            elif intent == IntentType.CHAT:
                async for chunk in self._run_chat(task):
                    yield chunk
            else:
                yield f"[Coordinator] 未知意图类型，跳过执行\n"
                task.status = TaskStatus.FAILED
                task.error = "unknown_intent"

        except Exception as e:
            logger.exception(f"任务执行失败: {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
            yield f"\n[Coordinator] ❌ 执行失败: {e}\n"

        finally:
            task.finished_at = time.time()
            task.status = TaskStatus.COMPLETED if task.error is None else TaskStatus.FAILED
            elapsed = (task.finished_at - task.started_at) * 1000
            yield f"\n[Coordinator] 任务完成，耗时: {elapsed:.0f}ms\n"

    async def _run_code_task(self, task: Task) -> AsyncGenerator[str, None]:
        """执行代码类任务（调用执行Agent）"""
        yield f"[Coordinator] → 分发给执行Agent...\n"

        # 调用执行Agent，流式输出
        result_gen = self.executor.execute_stream(task.description)

        for chunk in result_gen:
            if isinstance(chunk, str):
                # 过滤掉执行Agent的[M-Agent]前缀，避免混淆
                clean_chunk = chunk.replace("[M-Agent]", "[Executor]")
                yield clean_chunk
                self._result_agg.add_chunk(chunk)
            else:
                # 最后一个是ExecutionResult
                result = chunk
                task.result = result
                self.state.completed_task_ids.append(task.task_id)

        yield f"\n[Coordinator] 执行Agent返回结果，已记录\n"

    async def _run_chat(self, task: Task) -> AsyncGenerator[str, None]:
        """闲聊类任务：直接调用 LLM 生成回复"""
        yield f"[Coordinator] → 闲聊模式\n"
        from ..core.llm_engine import get_reasoning_engine
        llm = get_reasoning_engine()
        response = llm.generate(
            prompt=task.description,
            system="你是一个友好、有用的AI助手。用户跟你打招呼，简洁回复即可。",
        )
        yield f"\n{response}\n"
        task.result = response
        task.status = TaskStatus.COMPLETED
        self.state.completed_task_ids.append(task.task_id)

    def get_state(self) -> dict:
        """获取当前状态快照"""
        return {
            "session_id": self.session_id,
            "total_tasks": len(self.state.tasks),
            "completed": len(self.state.completed_task_ids),
            "failed": len(self.state.failed_task_ids),
            "context": self.state.context,
        }


# 全局单例（线程安全）
import threading
_coord_lock = threading.Lock()
_coord_instance: Coordinator | None = None


def get_coordinator() -> Coordinator:
    global _coord_instance
    if _coord_instance is None:
        with _coord_lock:
            if _coord_instance is None:
                _coord_instance = Coordinator()
    return _coord_instance
