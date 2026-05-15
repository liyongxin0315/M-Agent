"""
主Agent 协调器（G 目标空间 + S 状态空间）

职责：
  - 接收用户指令
  - 意图分析（LLM 语义分类 + 缓存）
  - 任务拆解（拆成子任务，分发给对应Agent）
  - 结果汇总（流式输出）
  - 状态管理（记录当前状态）
"""

from __future__ import annotations

import uuid
import time
import asyncio
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
    mode: str = "auto"
    parent_id: str | None = None
    sub_tasks: list[str] = field(default_factory=list)
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


# —————————————————————————————————————————————
# LLM 意图分类器（带缓存）
# —————————————————————————————————————————————

# 少样本示例：告诉 LLM 哪些输入属于哪类
_INTENT_EXAMPLES = """
用户输入 → 意图分类

"你好" → chat
"hi，你好" → chat
"你是谁" → chat
"你能干嘛" → chat
"现在几点了" → chat
"给我讲个笑话" → chat
"推荐一首诗" → chat
"解释一下什么是递归" → chat

"帮我写一个快速排序" → code_generate
"用 Python 实现一个队列" → code_generate
"写个函数判断素数" → code_generate
"生成一个 REST API 的例子" → code_generate
"帮我写个爬虫" → code_generate

"这段代码报错了" → code_fix
"修复一下这个 bug" → code_fix
"为什么程序崩溃了" → code_fix

"这段代码太乱了，帮我重构" → code_refactor
"优化一下性能" → code_refactor

"帮我看看这段代码有没有问题" → code_review
"代码审查一下" → code_review
"""

_INTENT_CLASSIFY_PROMPT = """你是一个意图分类器。根据用户输入，判断它属于哪个意图类型。

意图类型：
- chat：闲聊、打招呼、问问题（与编程无关的问题）、通用问答
- code_generate：要求写代码、生成代码片段、实现某个功能
- code_fix：修复 bug、报错修复
- code_refactor：重构代码、优化代码结构
- code_review：审查代码、评审代码

{examples}

现在分类：
"{user_input}" → """

# —————————————————————————————————————————————

class IntentCache:
    """意图分类缓存，LRU 策略"""

    def __init__(self, max_size: int = 200):
        self._cache: dict[str, IntentType] = {}
        self._max_size = max_size

    def get(self, prompt: str) -> IntentType | None:
        key = prompt.strip().lower()
        return self._cache.get(key)

    def set(self, prompt: str, intent: IntentType):
        key = prompt.strip().lower()
        if len(self._cache) >= self._max_size:
            # 简单策略：清掉最老的 20%
            keys_to_remove = list(self._cache.keys())[: self._max_size // 5]
            for k in keys_to_remove:
                del self._cache[k]
        self._cache[key] = intent


class IntentParser:
    """
    LLM 意图分类器。

    - 优先走缓存（命中率高的请求直接返回）
    - 缓存未命中则调用本地 Ollama LLM 做少样本分类
    - 分类结果缓存供下次使用
    """

    def __init__(self, cache_size: int = 200):
        self._cache = IntentCache(max_size=cache_size)

    async def parse(self, prompt: str) -> tuple[IntentType, str]:
        """
        异步分类。缓存命中则直接返回，否则调 LLM。
        """
        # 1. 缓存查询（同步，快）
        cached = self._cache.get(prompt)
        if cached is not None:
            logger.debug(f"[IntentParser] cache hit: '{prompt[:40]}' → {cached.value}")
            return cached, prompt

        # 2. LLM 分类（异步，调 Ollama）
        intent = await self._classify_with_llm(prompt)
        self._cache.set(prompt, intent)
        logger.debug(f"[IntentParser] LLM classified: '{prompt[:40]}' → {intent.value}")
        return intent, prompt

    async def _classify_with_llm(self, prompt: str) -> IntentType:
        """
        调用 Ollama 做少样本意图分类。
        失败时默认回退到 code_generate（偏保守，避免漏掉代码任务）。
        """
        try:
            from ..core.llm_engine import get_reasoning_engine
            llm = get_reasoning_engine()

            full_prompt = _INTENT_CLASSIFY_PROMPT.format(
                examples=_INTENT_EXAMPLES,
                user_input=prompt,
            )

            response = llm.generate(
                prompt=full_prompt,
                system="你是一个意图分类器，只输出分类结果（如 chat / code_generate / code_fix 等），不要输出其他内容。",
            )

            # 解析 LLM 返回的分类
            intent = self._parse_response(response.strip())
            return intent

        except Exception as e:
            logger.warning(f"[IntentParser] LLM 分类失败，回退到 code_generate: {e}")
            return IntentType.CODE_GENERATE

    def _parse_response(self, raw: str) -> IntentType:
        """从 LLM 返回中解析出 IntentType"""
        raw = raw.strip().lower()

        # 尝试直接匹配
        for intent in IntentType:
            if intent.value in raw:
                return intent

        # 模糊匹配
        if "chat" in raw or "闲聊" in raw or "打招呼" in raw:
            return IntentType.CHAT
        if "fix" in raw or "bug" in raw or "修复" in raw or "报错" in raw:
            return IntentType.CODE_FIX
        if "review" in raw or "审查" in raw or "评审" in raw:
            return IntentType.CODE_REVIEW
        if "refactor" in raw or "重构" in raw or "优化" in raw:
            return IntentType.CODE_REFACTOR
        if "generate" in raw or "生成" in raw or "写代码" in raw or "实现" in raw:
            return IntentType.CODE_GENERATE

        # 默认
        return IntentType.CODE_GENERATE


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
        异步流式执行：意图分类 → 分发 → 流式输出
        SSE 只输出实际回复内容，内部日志写到文件
        """
        # 1. LLM 意图分类（带缓存）
        intent, task_desc = await self.intent_parser.parse(prompt)
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
            elapsed = (task.finished_at - (task.started_at or task.finished_at)) * 1000
            logger.info(f"[Coordinator] 任务完成，耗时: {elapsed:.0f}ms | 结果: {task.status.value}")

    async def _run_code_task(self, task: Task) -> AsyncGenerator[str, None]:
        """执行代码类任务（调用执行Agent），流式输出实际回复"""
        logger.info(f"[Coordinator] → 分发给执行Agent...")
        result_gen = self.executor.execute_stream(task.description)

        for chunk in result_gen:
            if isinstance(chunk, str):
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
