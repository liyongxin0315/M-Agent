# AgentM 设计决策文档

本文档记录 AgentM 核心设计决策及其理由。

---

## 1. 中间件链设计

### 决策：采用 Pre/Post 双阶段模式

**选项对比**:

| 方案 | 优点 | 缺点 |
|------|------|------|
| Pre/Post 双阶段 | 清晰分离关注点，支持后置处理 | 实现稍复杂 |
| 单一处理函数 | 简单直接 | 无法优雅处理后置逻辑 |
| 装饰器模式 | Pythonic | 调试困难，堆栈深 |

**选择理由**:
1. **后置处理必要性**: 资源清理、响应转换、日志记录等需要在核心逻辑之后执行
2. **错误处理**: Post 阶段可以处理/转换错误
3. **与 DeerFlow 对齐**: 参考了成熟的中间件设计模式

**实现细节**:
```python
# 执行顺序
for mw in middlewares:  # 正向
    await mw.pre_process(context)

result = await core_execute(context)

for mw in reversed(middlewares):  # 反向
    await mw.post_process(context, result)
```

---

## 2. 沙箱系统设计

### 决策：虚拟路径映射而非真实路径

**选项对比**:

| 方案 | 优点 | 缺点 |
|------|------|------|
| 虚拟路径映射 | 安全、灵活、易测试 | 需要转换逻辑 |
| 直接使用真实路径 | 简单 | 安全风险高 |
| chroot 隔离 | 系统级安全 | 需要 root 权限，复杂 |

**选择理由**:
1. **安全性**: 防止路径遍历攻击 (`../../../etc/passwd`)
2. **灵活性**: 可以轻松切换底层存储（本地/Docker/S3）
3. **可测试性**: 测试时可以映射到临时目录

**实现细节**:
```python
# 虚拟路径配置
virtual_paths = {
    "/workspace": f"/tmp/agentm/{thread_id}/workspace",
    "/uploads": f"/tmp/agentm/{thread_id}/uploads",
}

# 路径转换时验证
def translate_path(virtual_path):
    for virt, phys in virtual_paths.items():
        if virtual_path.startswith(virt):
            resolved = os.path.normpath(physical_path)
            if not resolved.startswith(phys):
                raise SecurityViolationError("Path traversal detected")
```

### 决策：命令白名单而非黑名单

**理由**:
- 黑名单容易遗漏危险命令
- 白名单更安全，但可能限制功能
- **折中方案**: 黑名单 + 模式匹配（检测危险模式如 `> /etc/`）

---

## 3. 记忆系统设计

### 决策：JSON 文件存储而非数据库

**选项对比**:

| 方案 | 优点 | 缺点 |
|------|------|------|
| JSON 文件 | 简单、易备份、无依赖 | 并发写入需锁、查询能力弱 |
| SQLite | 支持查询、并发好 | 需要依赖、迁移复杂 |
| Redis | 快速、支持过期 | 需要服务、持久化配置 |

**选择理由**:
1. **简单性**: AgentM 初期不需要复杂查询
2. **可移植性**: JSON 文件易于备份和迁移
3. **无依赖**: 不需要额外服务
4. **可扩展**: 未来可切换到数据库（接口不变）

### 决策：置信度评分系统

**理由**:
1. **质量区分**: 不是所有事实都同样可靠
2. **自动过滤**: 可以设置阈值过滤低质量记忆
3. **LLM 友好**: 可以告诉 LLM"以下是高置信度事实"

**评分标准**:
- 0.9-1.0: 用户明确陈述的事实
- 0.7-0.9: 从多次对话推断的事实
- 0.5-0.7: 单次对话推断的事实
- <0.5: 不确定/推测的事实

### 决策：延迟批量更新（Debounce）

**理由**:
1. **减少 I/O**: 避免每次添加事实都写盘
2. **性能**: 批量写入比频繁写入高效
3. **容错**: 多次更新只保留最终状态

**实现**:
```python
def add_fact(self, fact):
    self._pending_updates.append(fact)
    self._schedule_flush()  # 60 秒后写入

def _schedule_flush(self):
    # 取消之前的定时器，重新计时
    if self._debounce_timer:
        self._debounce_timer.cancel()
    self._debounce_timer = asyncio.create_task(self._delayed_flush())
```

---

## 4. SSE 流式设计

### 决策：SSE 而非 WebSocket

**选项对比**:

| 方案 | 优点 | 缺点 |
|------|------|------|
| SSE | 简单、HTTP 兼容、自动重连 | 仅单向（服务器→客户端） |
| WebSocket | 双向、低延迟 | 需要额外协议处理、代理配置复杂 |
| 轮询 | 简单 | 延迟高、资源浪费 |

**选择理由**:
1. **单向足够**: AgentM 只需要服务器推送事件到客户端
2. **HTTP 兼容**: 通过标准 HTTP 端口，无需特殊配置
3. **自动重连**: 浏览器原生支持断线重连
4. **简单**: 实现和维护成本低

### 决策：心跳机制

**理由**:
1. **连接保活**: 防止代理/负载均衡器关闭空闲连接
2. **客户端检测**: 客户端可以检测连接是否断开
3. **调试友好**: 可以看到连接是否活跃

**实现**:
```python
async def event_generator():
    while connected:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=30)
            yield event
        except asyncio.TimeoutError:
            yield HEARTBEAT_EVENT  # 发送心跳
```

---

## 5. 子 Agent 并发设计

### 决策：Semaphore 控制并发而非进程池

**选项对比**:

| 方案 | 优点 | 缺点 |
|------|------|------|
| Semaphore | 简单、灵活、易监控 | 需要自己管理任务队列 |
| ProcessPoolExecutor | 真正并行 | 进程间通信开销大 |
| ThreadPoolExecutor | 轻量 | GIL 限制 CPU 密集型 |

**选择理由**:
1. **IO 密集型**: Agent 调用主要是等待 LLM 响应，不是 CPU 密集
2. **资源控制**: Semaphore 可以精确控制并发数
3. **灵活性**: 可以轻松实现优先级、取消等功能

### 决策：每个任务独立超时

**理由**:
1. **公平性**: 慢任务不会阻塞其他任务
2. **可预测**: 用户可以设置每个任务的超时
3. **资源保护**: 防止单个任务占用过多资源

**实现**:
```python
async def _execute_task(self, task):
    async with self._semaphore:  # 获取许可
        try:
            result = await asyncio.wait_for(
                self._run_agent(task.agent_type, task.task),
                timeout=task.timeout_seconds,
            )
        except asyncio.TimeoutError:
            task.status = TaskStatus.TIMEOUT
```

### 决策：自动重试机制

**理由**:
1. **容错**: 网络抖动、临时错误可以自动恢复
2. **可配置**: 不同任务可以设置不同重试次数
3. **透明**: 对用户无感

**限制**:
- 仅重试失败/超时任务
- 不重试业务逻辑错误（如无效输入）
- 重试次数有限制（防止无限循环）

---

## 6. 类型注解和文档

### 决策：完整类型注解

**理由**:
1. **IDE 支持**: 自动补全、类型检查
2. **文档**: 类型本身就是文档
3. **错误预防**: mypy 可以在运行前发现类型错误
4. **重构友好**: 修改接口时容易发现调用点

### 决策：Google 风格 Docstring

**理由**:
1. **可读性**: 清晰的结构
2. **工具支持**: Sphinx 等工具可以直接生成文档
3. **一致性**: 团队统一风格

**示例**:
```python
def execute_command(
    self,
    cmd: str,
    cwd: str = None,
    timeout: Optional[float] = None,
) -> str:
    """Execute a shell command in the sandbox.
    
    Args:
        cmd: Command to execute
        cwd: Working directory (virtual path)
        timeout: Execution timeout in seconds
        
    Returns:
        Command stdout
        
    Raises:
        SecurityViolationError: If command violates security policy
        TimeoutError: If execution exceeds timeout
    """
```

---

## 7. 异常处理设计

### 决策：自定义异常层次

**理由**:
1. **精确捕获**: 可以针对特定异常处理
2. **上下文信息**: 自定义异常可以携带更多信息
3. **API 清晰**: 调用者知道可能抛出什么异常

**层次结构**:
```
Exception
├── MemoryError
│   └── MemoryValidationError
├── SandboxError
│   ├── SecurityViolationError
│   └── TimeoutError
└── SubagentError
    ├── SubagentTimeoutError
    └── SubagentConcurrencyError
```

### 决策：不捕获所有异常

**理由**:
1. **透明**: 不应该隐藏真正的 bug
2. **调试**: 堆栈追踪帮助定位问题
3. **分级处理**: 只处理预期的异常

**实践**:
```python
# ✅ 好：处理预期异常
try:
    await sandbox.execute_command(cmd)
except SecurityViolationError:
    logger.warning(f"Security violation: {cmd}")
except TimeoutError:
    logger.error(f"Command timed out: {cmd}")

# ❌ 坏：隐藏所有错误
try:
    do_something()
except Exception:
    pass  # 不要这样做！
```

---

## 8. 测试策略

### 决策：单元测试 + 集成测试

**单元测试**:
- 每个模块独立测试
- Mock 外部依赖
- 覆盖率目标 >80%

**集成测试**:
- 测试模块间交互
- 真实执行（不 mock）
- 端到端场景

### 决策：pytest 作为测试框架

**理由**:
1. **简单**: 无需 boilerplate
2. **强大**: fixture、parametrize、mark
3. **生态**: 丰富的插件
4. **异步支持**: pytest-asyncio

---

## 9. 与 DeerFlow 的差异

### 架构差异

| 方面 | DeerFlow | AgentM | 理由 |
|------|----------|--------|------|
| 中间件数量 | 9 个 | 5 个核心 | 精简核心，按需扩展 |
| 记忆存储 | JSON | JSON | 保持一致性 |
| 沙箱模式 | 本地+Docker | 本地 (Docker TBD) | 先实现核心功能 |
| SSE 实现 | FastAPI | 独立模块 | 解耦，可复用 |
| 子 Agent | 简单并发 | 完整执行器 | 更好的资源控制 |

### 设计哲学差异

**DeerFlow**: 功能完整，生产就绪
**AgentM**: 学习参考，精简核心，教育友好

AgentM 的目标不是完全复制 DeerFlow，而是：
1. 理解核心设计原理
2. 用自己的方式实现
3. 添加详细文档和注释
4. 便于学习和扩展

---

## 10. 未来改进

### 短期 (v0.2)
- [ ] Docker 沙箱提供者
- [ ] 记忆向量搜索
- [ ] 中间件热插拔

### 中期 (v0.3)
- [ ] 工作流编排引擎
- [ ] 分布式子 Agent
- [ ] MCP 集成

### 长期 (v1.0)
- [ ] 数据库存储选项
- [ ] 多租户支持
- [ ] 插件系统
