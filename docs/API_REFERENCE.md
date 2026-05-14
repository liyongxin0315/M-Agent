# AgentM API 参考

## 模块概览

```
agentm/
├── middleware.py      # 中间件链系统
├── sandbox.py         # 沙箱系统
├── memory.py          # 记忆系统
├── sse_server.py      # SSE 流式输出
└── subagent.py        # 子 Agent 并发执行
```

---

## Middleware Chain API

### Middleware (抽象基类)

所有中间件的基类。

```python
from agentm import Middleware, MiddlewareContext

class CustomMiddleware(Middleware):
    @property
    def name(self) -> str:
        """唯一标识符"""
        return "custom"
    
    @property
    def priority(self) -> int:
        """执行优先级（数字越小越先执行）"""
        return 100
    
    async def pre_process(
        self,
        context: MiddlewareContext,
    ) -> MiddlewareContext:
        """核心逻辑执行前的处理"""
        pass
    
    async def post_process(
        self,
        context: MiddlewareContext,
        result: Any,
    ) -> MiddlewareContext:
        """核心逻辑执行后的处理"""
        pass
```

### MiddlewareChain

中间件链执行器。

```python
from agentm import MiddlewareChain, MiddlewareContext

# 创建链
chain = MiddlewareChain(base_path="/tmp/agentm")

# 添加中间件
chain.add(ThreadIsolationMiddleware())
chain.add(SandboxMiddleware())
chain.add(MemoryMiddleware())

# 设置核心执行器
async def core_executor(ctx: MiddlewareContext) -> Any:
    # 业务逻辑
    return {"result": "success"}

chain.set_core_executor(core_executor)

# 执行
ctx = MiddlewareContext(
    thread_id="thread-123",
    query="Hello, world!",
)
result = await chain.execute(ctx)
```

**方法**:

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `add(middleware)` | middleware: Middleware | MiddlewareChain | 添加中间件 |
| `remove(name)` | name: str | bool | 移除中间件 |
| `set_core_executor(fn)` | fn: Callable | None | 设置核心执行器 |
| `execute(ctx)` | ctx: MiddlewareContext | Any | 执行链 |
| `middlewares` | - | List[Middleware] | 获取中间件列表 |
| `metrics` | - | Dict | 获取执行指标 |

### MiddlewareContext

执行上下文对象。

```python
@dataclass
class MiddlewareContext:
    thread_id: str           # 线程 ID
    query: str               # 用户查询
    metadata: Dict           # 元数据
    sandbox: SandboxProvider # 沙箱提供者（由 SandboxMiddleware 注入）
    memory: MemoryManager    # 记忆管理器（由 MemoryMiddleware 注入）
    virtual_paths: Dict      # 虚拟路径映射
    files: List              # 上传文件
    state: Dict              # 中间件共享状态
```

### 内置中间件

#### ThreadIsolationMiddleware

线程数据隔离。

```python
mw = ThreadIsolationMiddleware(
    base_path="/tmp/agentm",  # 基础目录
)
```

#### SandboxMiddleware

沙箱注入。

```python
mw = SandboxMiddleware(
    timeout_seconds=60,  # 命令超时时间
)
```

#### MemoryMiddleware

记忆注入。

```python
mw = MemoryMiddleware(
    storage_path="/tmp/memory.json",  # 存储路径
    confidence_threshold=0.7,         # 置信度阈值
    max_facts=10,                     # 最大注入事实数
)
```

#### FileUploadMiddleware

文件上传处理。

```python
mw = FileUploadMiddleware(
    max_file_size_mb=10,              # 最大文件大小
    allowed_types=["text/plain"],     # 允许的 MIME 类型
)
```

#### ClarificationMiddleware

澄清中断。

```python
mw = ClarificationMiddleware(
    clarification_patterns=None,  # 自定义模式列表
)
```

---

## Sandbox API

### SandboxProvider (抽象基类)

沙箱提供者接口。

```python
from agentm import SandboxProvider

class CustomSandbox(SandboxProvider):
    @property
    def provider_name(self) -> str:
        return "custom"
    
    async def execute_command(
        self,
        cmd: str,
        cwd: str = None,
        timeout: Optional[float] = None,
    ) -> str:
        pass
    
    async def read_file(self, path: str) -> str:
        pass
    
    async def write_file(self, path: str, content: str) -> None:
        pass
    
    async def list_dir(self, path: str) -> List[str]:
        pass
    
    async def file_exists(self, path: str) -> bool:
        pass
    
    async def cleanup(self) -> None:
        pass
```

### LocalSandboxProvider

本地沙箱实现。

```python
from agentm import LocalSandboxProvider

sandbox = LocalSandboxProvider(
    thread_id="thread-123",
    virtual_paths={
        "/workspace": "/tmp/agentm/thread-123/workspace",
    },
    timeout_seconds=60,
    max_output_size=1024 * 1024,  # 1MB
    allow_network=False,
)

# 执行命令
output = await sandbox.execute_command("ls -la", cwd="/workspace")

# 文件操作
await sandbox.write_file("/workspace/test.txt", "Hello")
content = await sandbox.read_file("/workspace/test.txt")
files = await sandbox.list_dir("/workspace")
exists = await sandbox.file_exists("/workspace/test.txt")

# 清理
await sandbox.cleanup()
```

### 异常

```python
from agentm import (
    SandboxError,
    SecurityViolationError,
    TimeoutError,
)

try:
    await sandbox.execute_command("rm -rf /")
except SecurityViolationError as e:
    print(f"Security violation: {e}")
except TimeoutError as e:
    print(f"Timeout: {e}")
except SandboxError as e:
    print(f"Sandbox error: {e}")
```

---

## Memory API

### MemoryManager

记忆管理器。

```python
from agentm import MemoryManager, MemoryFact

# 创建管理器
manager = MemoryManager(
    storage_path="/tmp/memory.json",
    debounce_seconds=60,
    max_facts=100,
    confidence_threshold=0.5,
)

# 加载
manager.load()

# 添加事实
fact = MemoryFact(
    content="User prefers TypeScript",
    category="preference",
    confidence=0.9,
    source="thread-123",
)
manager.add_fact(fact)

# 更新事实
manager.update_fact(
    fact_id="fact-id",
    content="Updated content",
    confidence=0.95,
)

# 删除事实
manager.delete_fact("fact-id")

# 查询
top_facts = manager.get_top_facts(limit=10, min_confidence=0.7)
by_category = manager.get_facts_by_category("work")
search_results = manager.search_facts("TypeScript")

# 获取单个事实
fact = manager.get_fact_by_id("fact-id")

# 强制保存
manager.flush()

# 统计
stats = manager.get_statistics()
```

### MemoryFact

记忆事实数据类。

```python
@dataclass
class MemoryFact:
    id: str                    # 唯一 ID（自动生成）
    content: str               # 事实内容
    category: str              # 分类
    confidence: float          # 置信度 0.0-1.0
    created_at: str            # 创建时间
    updated_at: Optional[str]  # 更新时间
    source: str                # 来源
    access_count: int          # 访问次数
    last_accessed: Optional[str]  # 最后访问时间
```

**有效分类**:
- `context` - 通用上下文
- `work` - 工作相关
- `personal` - 个人相关
- `preference` - 偏好设置
- `skill` - 技能/能力
- `project` - 项目信息
- `contact` - 联系人
- `note` - 笔记
- `other` - 其他

---

## SSE Server API

### SSEServer

SSE 服务器。

```python
from agentm import SSEServer, EventType, SSEEvent

# 创建服务器
server = SSEServer(
    heartbeat_interval=30,    # 心跳间隔（秒）
    max_queue_size=1000,      # 每客户端最大队列大小
    client_timeout=300,       # 客户端超时（秒）
)

# 发送事件
await server.emit_run_start("run-123", {"query": "Hello"})
await server.emit_progress("run-123", 50, "Processing...")
await server.emit_log("run-123", "Step 1 complete", level="info")
await server.emit_result("run-123", {"answer": "World"})
await server.emit_run_end("run-123")

# 发送错误
await server.emit_error(
    "run-123",
    error="Something failed",
    code="ERR_PROCESSING",
)

# 结束流
await server.end_stream("run-123")

# 获取连接客户端
clients = server.get_connected_clients("run-123")

# 统计
stats = server.stats
```

### SSEEvent

SSE 事件。

```python
from agentm import EventType, SSEEvent

event = SSEEvent(
    type=EventType.CUSTOM,
    data={"custom": "data"},
    id="event-123",  # 可选，自动生成
    retry=5000,      # 可选，重连间隔（毫秒）
)

# 转换为 SSE 格式
sse_format = event.to_sse_format()
# 输出:
# event: custom
# data: {"custom": "data"}
# id: event-123
#
#
```

### EventType

事件类型枚举。

```python
class EventType(str, Enum):
    RUN_START = "run_start"
    RUN_END = "run_end"
    PROGRESS = "progress"
    LOG = "log"
    ERROR = "error"
    RESULT = "result"
    MESSAGE = "message"
    HEARTBEAT = "heartbeat"
    CUSTOM = "custom"
```

---

## Subagent API

### SubagentExecutor

子 Agent 执行器。

```python
from agentm import SubagentExecutor

# 创建执行器
executor = SubagentExecutor(
    max_concurrent=5,       # 最大并发数
    default_timeout=300,    # 默认超时（秒）
    max_retries=2,          # 默认最大重试次数
    thread_pool_size=10,    # 线程池大小
)

# 设置 Agent 处理器
async def agent_handler(agent_type: str, task: str) -> Any:
    # 实际调用 Agent 的逻辑
    return {"result": "processed"}

executor.set_agent_handler(agent_handler)

# 执行单个任务
result = await executor.execute(
    agent_type="research",
    task="Find latest AI news",
    timeout_seconds=600,
    max_retries=3,
)

# 提交任务（不等待）
task_id = await executor.submit(
    agent_type="analysis",
    task="Analyze data",
)

# 等待任务
task = await executor.wait_for_task(task_id)
result = task.result

# 批量执行
task_ids = [
    await executor.submit("research", f"Task {i}")
    for i in range(5)
]
results = await executor.wait_all(task_ids)

# 获取状态
status = await executor.get_status(task_id)
# TaskStatus.PENDING | RUNNING | COMPLETED | FAILED | TIMEOUT | CANCELLED

# 取消任务
await executor.cancel_task(task_id)
await executor.cancel_all()

# 列出任务
tasks = executor.list_tasks(
    status=TaskStatus.COMPLETED,
    agent_type="research",
    limit=10,
)

# 统计
stats = executor.stats

# 清理
await executor.cleanup()
```

### SubagentTask

任务对象。

```python
@dataclass
class SubagentTask:
    id: str
    agent_type: str
    task: str
    status: TaskStatus
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    result: Optional[Any]
    error: Optional[str]
    timeout_seconds: float
    retry_count: int
    max_retries: int
```

### TaskStatus

任务状态枚举。

```python
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
```

---

## 工厂函数

### create_sandbox

创建沙箱提供者。

```python
from agentm import create_sandbox, SandboxMode

# 本地沙箱
sandbox = create_sandbox(
    SandboxMode.LOCAL,
    thread_id="thread-123",
    virtual_paths={...},
)

# 限制沙箱（更严格）
sandbox = create_sandbox(
    SandboxMode.RESTRICTED,
    thread_id="thread-123",
)

# Docker 沙箱（未实现）
sandbox = create_sandbox(
    SandboxMode.DOCKER,
    thread_id="thread-123",
)  # 抛出 NotImplementedError
```

### create_sse_response

创建 FastAPI SSE 响应。

```python
from fastapi import FastAPI
from agentm import SSEServer, create_sse_response

app = FastAPI()
server = SSEServer()

@app.get("/stream/{run_id}")
async def stream(run_id: str, request: Request):
    async def event_generator():
        async for event in server.create_stream(run_id, request):
            yield event
    
    return create_sse_response(
        event_generator,
        headers={"X-Custom": "header"},
    )
```
