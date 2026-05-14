# AgentM 架构设计文档

## 概述

AgentM 是一个生产级的智能体管理平台，灵感来源于 DeerFlow 项目，但采用了独特的设计理念和实现方式。

## 设计原则

### 1. 关注点分离
每个模块只负责单一职责，通过清晰的接口进行通信。

### 2. 异步优先
所有 I/O 操作都采用异步设计，最大化并发性能。

### 3. 安全隔离
通过沙箱系统和虚拟路径映射，确保每个执行环境的安全隔离。

### 4. 可观测性
完整的日志、指标和事件追踪系统。

### 5. 可扩展性
抽象接口设计允许轻松替换底层实现。

## 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      Client Layer                            │
│                    (Web/Mobile/API)                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP/SSE
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway                              │
│                  (FastAPI + SSE Server)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Request Context
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Middleware Chain                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Thread   │ │ File     │ │ Sandbox  │ │ Memory   │  ...  │
│  │Isolation │ │ Upload   │ │ Injection│ │ Injection│       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Enriched Context
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Core Executor                             │
│              (Business Logic Handler)                        │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌─────────────────┐ ┌───────────┐ ┌──────────────┐
    │  Sandbox        │ │  Memory   │ │  Subagent    │
    │  Provider       │ │  Manager  │ │  Executor    │
    │                 │ │           │ │              │
    │  - Local        │ │  - Facts  │ │  - Concurrent│
    │  - Docker (TBD) │ │  - Context│ │  - Timeout   │
    │  - Custom       │ │  - Config │ │  - Retry     │
    └─────────────────┘ └───────────┘ └──────────────┘
```

## 核心模块

### 1. Middleware Chain (中间件链)

**职责**: 处理横切关注点，如认证、日志、沙箱注入等。

**设计特点**:
- 严格顺序执行（按优先级排序）
- Pre/Post 双阶段处理
- 错误传播和恢复机制

**执行流程**:
```
Request → [MW1.pre] → [MW2.pre] → ... → Core → [MW2.post] → [MW1.post] → Response
```

### 2. Sandbox System (沙箱系统)

**职责**: 提供安全的代码执行和文件操作环境。

**设计特点**:
- 虚拟路径映射（逻辑路径 → 物理路径）
- 命令白名单/黑名单
- 路径遍历防护
- 超时控制

**安全机制**:
```python
# 虚拟路径隔离
/agentm/workspace  →  /tmp/agentm/{thread_id}/workspace
/agentm/uploads    →  /tmp/agentm/{thread_id}/uploads
/agentm/outputs    →  /tmp/agentm/{thread_id}/outputs

# 危险命令拦截
rm, chmod, wget, curl, ssh 等被禁止
```

### 3. Memory System (记忆系统)

**职责**: 结构化存储用户上下文和事实，支持置信度评分。

**设计特点**:
- JSON 持久化存储
- 置信度评分（0.0-1.0）
- 延迟批量更新（减少 I/O）
- 自动大小限制

**数据结构**:
```
MemoryData
├── version: str
├── last_updated: datetime
├── user: UserContext
│   ├── work_context: ContextSection
│   ├── personal_context: ContextSection
│   └── top_of_mind: ContextSection
└── facts: List[MemoryFact]
    ├── id: str
    ├── content: str
    ├── category: str
    ├── confidence: float
    └── metadata
```

### 4. SSE Server (流式输出)

**职责**: 实时推送执行进度和结果到客户端。

**设计特点**:
- 标准 SSE 协议
- 心跳保活
- 事件类型化
- 连接管理

**事件类型**:
- `run_start` - 执行开始
- `progress` - 进度更新
- `log` - 日志消息
- `error` - 错误通知
- `result` - 最终结果
- `run_end` - 执行结束

### 5. Subagent Executor (子 Agent 执行器)

**职责**: 并发执行多个子 Agent 任务，管理资源限制。

**设计特点**:
- 信号量控制并发数
- 超时保护
- 自动重试
- 结果追踪

**并发模型**:
```
Task Queue → [Semaphore] → Worker Pool → Results
                ↓
         Max Concurrent: N
```

## 数据流

### 请求处理流程

```
1. Client Request
       ↓
2. API Gateway (创建 SSE 连接)
       ↓
3. Middleware Chain
   - ThreadIsolation: 创建隔离目录
   - FileUpload: 处理上传文件
   - Sandbox: 注入沙箱提供者
   - Memory: 注入相关记忆
       ↓
4. Core Executor (业务逻辑)
   - 可能调用 Subagent Executor
   - 使用 Sandbox 进行文件操作
       ↓
5. SSE Events (实时推送)
   - run_start
   - progress (多次)
   - result
   - run_end
       ↓
6. Response
```

### 记忆注入流程

```
1. MemoryMiddleware.pre_process()
       ↓
2. 加载 MemoryManager
       ↓
3. 筛选高置信度事实 (confidence >= threshold)
       ↓
4. 注入到 context.state["injected_facts"]
       ↓
5. Core Executor 可使用这些事实增强 LLM 上下文
```

## 模块依赖关系

```
middleware.py
├── 依赖 sandbox.py (SandboxMiddleware)
└── 依赖 memory.py (MemoryMiddleware)

sandbox.py
└── 无外部依赖 (核心模块)

memory.py
└── 无外部依赖 (核心模块)

sse_server.py
└── 可选依赖 FastAPI (仅用于 create_sse_response)

subagent.py
└── 无外部依赖 (核心模块)
```

## 扩展点

### 自定义中间件

```python
class CustomMiddleware(Middleware):
    @property
    def name(self) -> str:
        return "custom"
    
    @property
    def priority(self) -> int:
        return 25  # 控制执行顺序
    
    async def pre_process(self, context):
        # 前置处理
        return context
    
    async def post_process(self, context, result):
        # 后置处理
        return context
```

### 自定义沙箱提供者

```python
class DockerSandboxProvider(SandboxProvider):
    @property
    def provider_name(self) -> str:
        return "docker"
    
    async def execute_command(self, cmd, **kwargs):
        # Docker 容器内执行
        pass
```

## 性能考虑

### 并发控制
- Middleware Chain: 顺序执行（保证顺序）
- Subagent Executor: 限制并发数（防止资源耗尽）
- SSE Server: 每客户端独立队列

### I/O 优化
- Memory: 延迟批量写入（debounce）
- Sandbox: 异步 subprocess
- SSE: 流式传输（无缓冲）

### 内存管理
- 限制记忆事实数量（默认 100 条）
- 限制输出大小（默认 1MB）
- 限制任务队列大小（默认 1000）

## 安全考虑

### 沙箱隔离
- 虚拟路径映射防止访问未授权目录
- 危险命令拦截
- 路径遍历防护

### 数据保护
- 线程隔离（每个 thread_id 独立目录）
- 输入验证（所有外部输入）
- 异常处理（不泄露敏感信息）

## 监控和日志

### 指标收集
- Middleware 执行时间
- Sandbox 命令执行次数
- Memory 事实数量
- Subagent 任务状态分布
- SSE 连接数和事件数

### 日志级别
- DEBUG: 详细调试信息
- INFO: 正常操作日志
- WARNING: 可恢复问题
- ERROR: 需要关注的错误

## 未来扩展

### 计划功能
1. Docker 沙箱提供者
2. 向量搜索记忆
3. 分布式子 Agent 执行
4. 工作流编排引擎
5. MCP (Model Context Protocol) 集成

### 可扩展接口
所有核心模块都使用抽象基类设计，便于替换实现：
- `SandboxProvider` - 支持新的执行环境
- `Middleware` - 支持新的横切关注点
- `SubagentExecutor` - 支持新的调度策略
