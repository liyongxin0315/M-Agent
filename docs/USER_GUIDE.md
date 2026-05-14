# AgentM 使用指南

## 快速开始

### 安装

```bash
# 克隆或复制到项目
cd your_project
cp -r agentm/src ./

# 或者作为包安装（未来）
pip install agentm
```

### 依赖

```bash
pip install fastapi  # 可选，用于 SSE
pip install pytest pytest-asyncio  # 测试
```

### 最小示例

```python
import asyncio
from agentm import MiddlewareChain, MiddlewareContext

async def main():
    # 创建链
    chain = MiddlewareChain()
    
    # 设置执行器
    async def core(ctx):
        return {"answer": f"Processed: {ctx.query}"}
    
    chain.set_core_executor(core)
    
    # 执行
    ctx = MiddlewareContext(
        thread_id="test",
        query="Hello!",
    )
    result = await chain.execute(ctx)
    
    print(result)  # {'answer': 'Processed: Hello!'}

asyncio.run(main())
```

---

## 核心场景

### 场景 1: 带沙箱的文件处理

```python
import asyncio
from agentm import (
    MiddlewareChain,
    MiddlewareContext,
    ThreadIsolationMiddleware,
    SandboxMiddleware,
)

async def main():
    chain = MiddlewareChain(base_path="/tmp/agentm")
    
    # 添加中间件
    chain.add(ThreadIsolationMiddleware())
    chain.add(SandboxMiddleware())
    
    # 核心逻辑：使用沙箱处理文件
    async def core(ctx):
        # 写入文件
        await ctx.sandbox.write_file(
            "/workspace/input.txt",
            ctx.query,
        )
        
        # 执行命令处理
        output = await ctx.sandbox.execute_command(
            "cat /workspace/input.txt | wc -c",
        )
        
        return {"char_count": int(output.strip())}
    
    chain.set_core_executor(core)
    
    # 执行
    ctx = MiddlewareContext(
        thread_id="file-test",
        query="Hello, World!",
    )
    result = await chain.execute(ctx)
    
    print(result)  # {'char_count': 13}

asyncio.run(main())
```

### 场景 2: 带记忆注入的对话

```python
import asyncio
from agentm import (
    MiddlewareChain,
    MiddlewareContext,
    MemoryMiddleware,
    MemoryManager,
    MemoryFact,
)

async def main():
    # 准备记忆
    memory_mgr = MemoryManager("/tmp/memory.json")
    memory_mgr.load()
    memory_mgr.add_fact(MemoryFact(
        content="用户喜欢简洁的回答",
        category="preference",
        confidence=0.9,
    ))
    memory_mgr.add_fact(MemoryFact(
        content="正在开发 AgentM 项目",
        category="work",
        confidence=0.95,
    ))
    memory_mgr.flush()
    
    # 创建链
    chain = MiddlewareChain()
    chain.add(MemoryMiddleware(
        storage_path="/tmp/memory.json",
        confidence_threshold=0.7,
        max_facts=5,
    ))
    
    # 核心逻辑：使用注入的记忆
    async def core(ctx):
        facts = ctx.state.get("injected_facts", [])
        
        return {
            "query": ctx.query,
            "context_facts": facts,
            "response": f"基于 {len(facts)} 条记忆事实回答：{ctx.query}",
        }
    
    chain.set_core_executor(core)
    
    # 执行
    ctx = MiddlewareContext(
        thread_id="memory-test",
        query="我在做什么项目？",
    )
    result = await chain.execute(ctx)
    
    print(result)
    # {
    #     'query': '我在做什么项目？',
    #     'context_facts': ['正在开发 AgentM 项目', '用户喜欢简洁的回答'],
    #     'response': '基于 2 条记忆事实回答：我在做什么项目？'
    # }

asyncio.run(main())
```

### 场景 3: 并发子 Agent 任务

```python
import asyncio
from agentm import SubagentExecutor

async def main():
    # 创建执行器
    executor = SubagentExecutor(
        max_concurrent=3,
        default_timeout=60,
    )
    
    # 模拟 Agent 处理器
    async def agent_handler(agent_type, task):
        print(f"Running {agent_type}: {task}")
        await asyncio.sleep(1)  # 模拟工作
        return {"result": f"Done: {task}"}
    
    executor.set_agent_handler(agent_handler)
    
    # 提交多个任务
    tasks = [
        executor.execute("research", f"Research topic {i}")
        for i in range(5)
    ]
    
    # 并发执行
    results = await asyncio.gather(*tasks)
    
    for i, result in enumerate(results):
        print(f"Task {i}: {result}")
    
    # 清理
    await executor.cleanup()

asyncio.run(main())
```

### 场景 4: SSE 实时推送

```python
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from agentm import SSEServer

app = FastAPI()
server = SSEServer()

@app.post("/runs/{run_id}/stream")
async def stream_run(run_id: str, request: Request):
    """SSE 流式端点"""
    
    async def event_generator():
        # 发送开始事件
        await server.emit_run_start(run_id, {"query": "Processing..."})
        
        # 模拟处理过程
        for i in range(10):
            await asyncio.sleep(0.5)
            await server.emit_progress(
                run_id,
                progress=(i + 1) * 10,
                message=f"Step {i + 1}/10",
            )
        
        # 发送结果
        await server.emit_result(run_id, {"answer": "Complete!"})
        await server.emit_run_end(run_id)
        
        # 生成 SSE 流
        async for event in server.create_stream(run_id, request):
            yield event
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
```

**客户端代码**:

```javascript
const eventSource = new EventSource('/runs/run-123/stream');

eventSource.addEventListener('run_start', (event) => {
    const data = JSON.parse(event.data);
    console.log('Started:', data);
});

eventSource.addEventListener('progress', (event) => {
    const data = JSON.parse(event.data);
    console.log(`Progress: ${data.progress}% - ${data.message}`);
});

eventSource.addEventListener('result', (event) => {
    const data = JSON.parse(event.data);
    console.log('Result:', data);
    eventSource.close();
});

eventSource.addEventListener('error', (event) => {
    const data = JSON.parse(event.data);
    console.error('Error:', data.error);
    eventSource.close();
});
```

---

## 完整示例

### 示例 1: 研究助手

完整的研究任务处理流程。

```python
"""
研究助手示例：演示中间件、沙箱、记忆、子 Agent 的综合使用
"""

import asyncio
from pathlib import Path
from agentm import (
    MiddlewareChain,
    MiddlewareContext,
    ThreadIsolationMiddleware,
    SandboxMiddleware,
    MemoryMiddleware,
    SubagentExecutor,
    MemoryManager,
    MemoryFact,
)

async def research_assistant():
    # 1. 初始化组件
    base_path = "/tmp/agentm-research"
    memory_path = "/tmp/agentm-research/memory.json"
    
    # 2. 准备记忆
    memory_mgr = MemoryManager(memory_path)
    memory_mgr.load()
    memory_mgr.add_fact(MemoryFact(
        content="用户关注 AI 和机器学习领域",
        category="work",
        confidence=0.9,
    ))
    memory_mgr.flush()
    
    # 3. 创建中间件链
    chain = MiddlewareChain(base_path=base_path)
    chain.add(ThreadIsolationMiddleware(base_path=base_path))
    chain.add(SandboxMiddleware(timeout_seconds=120))
    chain.add(MemoryMiddleware(
        storage_path=memory_path,
        confidence_threshold=0.7,
    ))
    
    # 4. 子 Agent 执行器
    subagent_executor = SubagentExecutor(max_concurrent=2)
    
    async def agent_handler(agent_type, task):
        # 模拟不同类型的 Agent
        await asyncio.sleep(1)
        return {
            "type": agent_type,
            "summary": f"Research summary for: {task[:50]}...",
            "sources": ["source1.com", "source2.com"],
        }
    
    subagent_executor.set_agent_handler(agent_handler)
    
    # 5. 核心逻辑
    async def core(ctx):
        # 使用沙箱创建工作目录
        await ctx.sandbox.write_file(
            "/workspace/research_query.txt",
            ctx.query,
        )
        
        # 提交研究任务
        research_result = await subagent_executor.execute(
            agent_type="research",
            task=ctx.query,
            timeout_seconds=300,
        )
        
        # 保存结果
        await ctx.sandbox.write_file(
            "/workspace/research_result.json",
            str(research_result),
        )
        
        # 生成报告
        report = f"""
# 研究报告

## 查询
{ctx.query}

## 记忆上下文
{chr(10).join('- ' + f for f in ctx.state.get('injected_facts', []))}

## 研究结果
{research_result['summary']}

## 来源
{chr(10).join('- ' + s for s in research_result['sources'])}
        """
        
        await ctx.sandbox.write_file(
            "/workspace/report.md",
            report,
        )
        
        return {
            "status": "complete",
            "research": research_result,
            "report_path": "/workspace/report.md",
        }
    
    chain.set_core_executor(core)
    
    # 6. 执行
    ctx = MiddlewareContext(
        thread_id="research-001",
        query="Latest developments in large language models 2024",
    )
    
    result = await chain.execute(ctx)
    
    print("Research complete!")
    print(f"Report saved to: {ctx.virtual_paths['/workspace']}/report.md")
    
    # 7. 清理
    await subagent_executor.cleanup()
    
    return result

# 运行
if __name__ == "__main__":
    result = asyncio.run(research_assistant())
    print(result)
```

### 示例 2: 文件处理管道

```python
"""
文件处理管道示例：演示文件上传、处理、输出的完整流程
"""

import asyncio
from agentm import (
    MiddlewareChain,
    MiddlewareContext,
    ThreadIsolationMiddleware,
    FileUploadMiddleware,
    SandboxMiddleware,
)

async def file_processing_pipeline():
    chain = MiddlewareChain(base_path="/tmp/agentm-files")
    
    # 添加中间件
    chain.add(ThreadIsolationMiddleware(base_path="/tmp/agentm-files"))
    chain.add(FileUploadMiddleware(
        max_file_size_mb=5,
        allowed_types=["text/plain", "text/csv", "application/json"],
    ))
    chain.add(SandboxMiddleware())
    
    # 核心处理逻辑
    async def core(ctx):
        results = []
        
        # 处理每个上传的文件
        for file_info in ctx.files:
            safe_name = file_info["safe_name"]
            
            # 假设文件已上传到指定位置
            input_path = f"/uploads/{safe_name}"
            output_path = f"/outputs/processed_{safe_name}"
            
            # 读取文件
            content = await ctx.sandbox.read_file(input_path)
            
            # 处理（示例：统计信息）
            stats = {
                "filename": safe_name,
                "lines": len(content.splitlines()),
                "words": len(content.split()),
                "chars": len(content),
            }
            
            # 写入结果
            import json
            await ctx.sandbox.write_file(
                output_path,
                json.dumps(stats, indent=2),
            )
            
            results.append(stats)
        
        return {"processed_files": results}
    
    chain.set_core_executor(core)
    
    # 模拟上传
    ctx = MiddlewareContext(
        thread_id="file-process-001",
        query="Process uploaded files",
        metadata={
            "files": [
                {"name": "data.csv", "size": 1024, "mime_type": "text/csv"},
                {"name": "config.json", "size": 512, "mime_type": "application/json"},
            ]
        },
    )
    
    result = await chain.execute(ctx)
    
    print(f"Processed {len(result['processed_files'])} files")
    for stats in result['processed_files']:
        print(f"  {stats['filename']}: {stats['lines']} lines, {stats['words']} words")
    
    return result

if __name__ == "__main__":
    result = asyncio.run(file_processing_pipeline())
```

### 示例 3: 多 Agent 协作

```python
"""
多 Agent 协作示例：演示多个子 Agent 并行执行并汇总结果
"""

import asyncio
from agentm import SubagentExecutor, TaskStatus

async def multi_agent_collaboration():
    executor = SubagentExecutor(
        max_concurrent=5,
        default_timeout=300,
        max_retries=2,
    )
    
    # 模拟不同类型的 Agent
    async def agent_handler(agent_type, task):
        print(f"[{agent_type}] Starting: {task[:30]}...")
        await asyncio.sleep(1)  # 模拟工作
        
        if agent_type == "research":
            return {"type": "research", "findings": ["fact1", "fact2"]}
        elif agent_type == "analysis":
            return {"type": "analysis", "insights": ["insight1"]}
        elif agent_type == "writing":
            return {"type": "writing", "draft": "Draft content..."}
        else:
            return {"type": "unknown", "result": "Done"}
    
    executor.set_agent_handler(agent_handler)
    
    # 定义工作流
    tasks = [
        {"agent_type": "research", "task": "Research AI trends 2024"},
        {"agent_type": "research", "task": "Research ML frameworks"},
        {"agent_type": "analysis", "task": "Analyze research findings"},
        {"agent_type": "writing", "task": "Write summary report"},
    ]
    
    # 提交所有任务
    print("Submitting tasks...")
    task_ids = []
    for task_spec in tasks:
        task_id = await executor.submit(
            agent_type=task_spec["agent_type"],
            task=task_spec["task"],
        )
        task_ids.append(task_id)
        print(f"  Submitted: {task_spec['task'][:30]}... (ID: {task_id[:8]})")
    
    # 等待所有完成
    print("\nWaiting for completion...")
    completed_tasks = await executor.wait_all(task_ids, timeout=600)
    
    # 汇总结果
    print("\n=== Results ===")
    for task in completed_tasks:
        status_emoji = {
            TaskStatus.COMPLETED: "✅",
            TaskStatus.FAILED: "❌",
            TaskStatus.TIMEOUT: "⏱️",
            TaskStatus.CANCELLED: "🚫",
        }.get(task.status, "❓")
        
        print(f"{status_emoji} {task.agent_type}: {task.task[:30]}...")
        if task.result:
            print(f"   Result: {task.result}")
        if task.error:
            print(f"   Error: {task.error}")
    
    # 统计
    stats = executor.stats
    print(f"\n=== Statistics ===")
    print(f"Total submitted: {stats['total_submitted']}")
    print(f"Total completed: {stats['total_completed']}")
    print(f"Total failed: {stats['total_failed']}")
    print(f"Total timeout: {stats['total_timeout']}")
    print(f"Total retries: {stats['total_retries']}")
    
    await executor.cleanup()

if __name__ == "__main__":
    asyncio.run(multi_agent_collaboration())
```

---

## 故障排除

### 常见问题

#### 1. 中间件不执行

**检查**:
- 是否调用了 `chain.set_core_executor()`
- 是否调用了 `await chain.execute(ctx)`
- 中间件是否正确添加到链

#### 2. 沙箱命令失败

**检查**:
- 虚拟路径是否正确配置
- 命令是否被安全策略阻止
- 是否超时

```python
# 调试：查看执行日志
log = sandbox.get_execution_log()
for entry in log:
    print(f"{entry['command']}: {entry['return_code']}")
```

#### 3. 记忆未注入

**检查**:
- 存储路径是否正确
- 置信度阈值是否太高
- 是否调用了 `manager.flush()`

```python
# 调试：查看记忆统计
stats = manager.get_statistics()
print(f"Total facts: {stats['total_facts']}")
print(f"Categories: {stats['categories']}")
```

#### 4. SSE 连接断开

**检查**:
- 心跳间隔是否太长
- Nginx 是否配置了 `X-Accel-Buffering: no`
- 客户端是否正确处理重连

### 日志配置

```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

# 调整特定模块日志级别
logging.getLogger('agentm.middleware').setLevel(logging.INFO)
logging.getLogger('agentm.sandbox').setLevel(logging.DEBUG)
```

---

## 最佳实践

### 1. 中间件顺序

```python
# 推荐顺序
chain.add(ThreadIsolationMiddleware())  # 10 - 最早
chain.add(FileUploadMiddleware())       # 20
chain.add(SandboxMiddleware())          # 30
chain.add(MemoryMiddleware())           # 40
chain.add(ClarificationMiddleware())    # 50 - 最晚
```

### 2. 错误处理

```python
from agentm import MiddlewareError, SecurityViolationError

try:
    result = await chain.execute(ctx)
except MiddlewareError as e:
    if e.recoverable:
        logger.warning(f"Recoverable error: {e}")
        # 尝试恢复
    else:
        logger.error(f"Non-recoverable error: {e}")
        raise
except SecurityViolationError as e:
    logger.error(f"Security violation: {e.command}")
    # 记录安全事件
```

### 3. 资源清理

```python
# 使用 try/finally 确保清理
executor = SubagentExecutor()
try:
    # 执行任务
    result = await executor.execute(...)
finally:
    await executor.cleanup()

# 或使用异步上下文管理器（未来版本）
async with SubagentExecutor() as executor:
    result = await executor.execute(...)
```

### 4. 性能优化

```python
# 批量添加记忆（减少 I/O）
for fact in facts:
    manager.add_fact(fact)
manager.flush()  # 一次性写入

# 限制并发数
executor = SubagentExecutor(max_concurrent=5)  # 根据资源调整

# 设置合理超时
result = await executor.execute(
    agent_type="research",
    task=task,
    timeout_seconds=300,  # 避免无限等待
)
```

---

## 下一步

- 阅读 [ARCHITECTURE.md](ARCHITECTURE.md) 了解系统设计
- 阅读 [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) 了解设计理由
- 查看测试文件学习更多示例
- 贡献代码或报告问题
