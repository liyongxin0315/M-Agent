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
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator
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
    """协调器状态"""
    session_id: str
    tasks: dict[str, Task] = field(default_factory=dict)
    completed_task_ids: list[str] = field(default_factory=list)
    failed_task_ids: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)


class ResultAggregator:
    """聚合多次执行结果"""
    def __init__(self):
        self.parts: list[str] = []

    def add_chunk(self, chunk: str):
        self.parts.append(chunk)

    def get_result(self) -> str:
        return "".join(self.parts)


class IntentParser:
    """意图解析器"""

    KEYWORDS = {
        IntentType.CHAT: [
            "你好", "hi", "hello", "嗨", "hey", "早上好", "下午好", "晚上好",
            "你是谁", "叫什么", "干什么的", "有什么功能", "能做什么",
            "帮我干嘛", "都能干嘛", "用什么模型", "你是干嘛的", "你是ai吗",
            "你会什么", "说说话", "聊聊天", "随便聊聊", "介绍一下",
        ],
        IntentType.CODE_GENERATE: [
            "写", "生成", "帮我写", "实现", "创建", "function", "def ",
            "class ", "帮我写个", "写一个", "generate", "write", "create",
        ],
        IntentType.CODE_FIX: [
            "修复", "fix", "bug", "报错", "错误", "问题", "修复它",
        ],
        IntentType.CODE_REFACTOR: [
            "重构", "refactor", "优化代码", "改进",
        ],
        IntentType.CODE_REVIEW: [
            "审查", "review", "评审", "看看代码",
        ],
    }

    def parse(self, prompt: str) -> tuple[IntentType, str]:
        prompt_lower = prompt.lower().strip()
        for intent, keywords in self.KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in prompt_lower:
                    return intent, prompt
        return IntentType.CODE_GENERATE, prompt


class Coordinator:
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
        SSE只输出实际回复内容，内部日志写到文件
        """
        intent, task_desc = self.intent_parser.parse(prompt)
        task_id = str(uuid.uuid4())[:8]
        task = Task(
            task_id=task_id,
            description=task_desc,
            intent=intent,
        )
        self.state.tasks[task_id] = task

        logger.info(f"[Coordinator] 会话ID: {self.session_id} | 任务ID: {task_id} | 意图: {intent.value} | 任务: {task_desc}")

        task.status = TaskStatus.RUNNING
        task.started_at = time.time()

        try:
            if intent in (IntentType.CODE_GENERATE, IntentType.CODE_FIX,
                          IntentType.CODE_REFACTOR, IntentType.CODE_REVIEW):
                async for chunk in self._run_code_task(task):
                    yield chunk
            elif intent == IntentType.CHAT:
                for chunk in self._run_chat(task):
                    yield chunk
            else:
                task.status = TaskStatus.FAILED
                task.error = "unknown_intent"

        except Exception as e:
            logger.exception(f"任务执行失败: {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)

        finally:
            task.finished_at = time.time()
            task.status = task.status if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED) else (
                TaskStatus.COMPLETED if task.error is None else TaskStatus.FAILED)
            elapsed = (task.finished_at - (task.started_at or task.finished_at)) * 1000
            logger.info(f"[Coordinator] 任务完成，耗时: {elapsed:.0f}ms | 结果: {task.status.value}")

    async def _run_code_task(self, task: Task) -> AsyncGenerator[str, None]:
        """执行代码类任务（调用执行Agent），流式输出实际回复"""
        logger.info(f"[Coordinator] → 分发给执行Agent...")
        result_gen = self.executor.execute_stream(task.description)

        for chunk in result_gen:
            if isinstance(chunk, str):
                # SSE只输出实际内容，不过滤——让客户端看到完整流式输出
                yield chunk
                self._result_agg.add_chunk(chunk)
            else:
                result = chunk
                task.result = result
                task.error = result.error
                self.state.completed_task_ids.append(task.task_id)
                logger.info(f"[Executor] 执行完成 | 耗时: {result.duration_ms:.0f}ms | 结果: {result.success} | 实际输出: {result.actual_output[:200] if result.actual_output else '(无)'}")

    def _run_chat(self, task: Task):
        """闲聊类任务：直接调用 LLM 生成回复"""
        logger.info(f"[Coordinator] → 闲聊模式")
        from ..core.llm_engine import get_reasoning_engine
        llm = get_reasoning_engine()
        response = llm.generate(
            prompt=task.description,
            system="你是一个友好、有用的AI助手。用户跟你打招呼，简洁回复即可。",
        )
        yield response
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
