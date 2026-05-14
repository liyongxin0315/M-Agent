# AgentM 架构设计文档

## 1. 概述

AgentM 是一个强大的工作流平台，灵感来自 n8n 和扣子（Coze）。它提供可视化的工作流编排能力，支持 24 种节点类型、变量系统、数据流管理和工作流嵌套。

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        WebUI Layer                          │
│  (Dashboard, Workflow Editor, Execution Monitor, API Docs) │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway Layer                      │
│            (REST API, WebSocket, Webhook)                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Workflow Engine Layer                    │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │   Parser    │  │   Executor   │  │ State Manager   │    │
│  └─────────────┘  └──────────────┘  └─────────────────┘    │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │  Scheduler  │  │ Event Bus    │  │ History Store   │    │
│  └─────────────┘  └──────────────┘  └─────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Node Runtime Layer                     │
│  ┌─────────────────────┐  ┌─────────────────────────────┐  │
│  │   Core Nodes (12)   │  │    Skill Nodes (12)         │  │
│  │  - HTTP Request     │  │  - Weather                  │  │
│  │  - Code             │  │  - Image Generation         │  │
│  │  - Condition        │  │  - Video Generation         │  │
│  │  - Loop             │  │  - Data Analysis            │  │
│  │  - Delay            │  │  - Chart Visualization      │  │
│  │  - Merge/Split      │  │  - PDF                      │  │
│  │  - Variable         │  │  - Whisper                  │  │
│  │  - Sub-Workflow     │  │  - Coding Agent             │  │
│  │  - Error Handler    │  │  - Frontend Design          │  │
│  │  - Webhook          │  │  - Deep Research            │  │
│  │  - Database Query   │  │  - GitHub Research          │  │
│  │                     │  │  - PPT Generation           │  │
│  └─────────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Core Services Layer                       │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │  Variable   │  │   Data Flow  │  │    Circuit      │    │
│  │   System    │  │   Manager    │  │    Breaker      │    │
│  └─────────────┘  └──────────────┘  └─────────────────┘    │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │    RAG      │  │   Multi-     │  │     Auto        │    │
│  │   Engine    │  │   Agent      │  │    Planner      │    │
│  │             │  │ Coordinator  │  │                 │    │
│  └─────────────┘  └──────────────┘  └─────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    External Skills Layer                    │
│  (12 External Skills: Weather, Image, Video, PDF, etc.)     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Storage Layer                          │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │  SQLite/    │  │   File       │  │     Cache       │    │
│  │ PostgreSQL  │  │   System     │  │    (Redis)      │    │
│  └─────────────┘  └──────────────┘  └─────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## 3. 核心模块

### 3.1 工作流引擎 (Workflow Engine)

**位置**: `workflows/workflow_engine.py`

**职责**:
- 解析工作流定义（JSON/YAML）
- 执行工作流步骤
- 管理执行状态
- 处理错误和重试

**关键类**:
- `WorkflowEngine`: 工作流执行引擎
- `BaseWorkflow`: 工作流基类
- `WorkflowStep`: 工作流步骤
- `WorkflowResult`: 执行结果

### 3.2 变量系统 (Variable System)

**位置**: `src/variable_system.py`

**职责**:
- 管理变量作用域（全局/工作流/节点/临时）
- 提供模板语法支持（Jinja2）
- 变量生命周期管理

**关键类**:
- `VariableSystem`: 变量系统
- `VariableContext`: 变量上下文
- `Variable`: 变量定义
- `TemplateEngine`: 模板引擎

**使用示例**:
```python
from agentm import create_variable_system

vs = create_variable_system()

# 设置全局变量
vs.set_global("api_key", "sk-xxx")

# 创建工作流上下文
ctx = vs.create_workflow_context("workflow_1")
ctx.set("user_name", "张三")

# 模板渲染
result = vs.render("Hello, {{ user_name }}!")
# 输出: "Hello, 张三!"
```

### 3.3 数据流管理 (Data Flow)

**位置**: `src/data_flow.py`

**职责**:
- JSON 数组在节点间传递
- 数据转换（filter, map, reduce 等）
- 数据映射（字段映射）

**关键类**:
- `DataFlowManager`: 数据流管理器
- `DataTransformer`: 数据转换器
- `DataMapper`: 数据映射器
- `DataPacket`: 数据包

**转换类型**:
- `identity`: 原样传递
- `to_list`: 转为数组
- `to_dict`: 转为对象
- `flatten`: 扁平化
- `group_by`: 分组
- `filter`: 过滤
- `map`: 映射
- `reduce`: 归约
- `json_serialize`: JSON 序列化
- `json_deserialize`: JSON 反序列化

### 3.4 嵌套工作流 (Nested Workflow)

**位置**: `src/nested_workflow.py`

**职责**:
- 支持子工作流调用
- 工作流注册表管理
- 输入输出映射

**关键类**:
- `NestedWorkflowEngine`: 嵌套工作流引擎
- `WorkflowRegistry`: 工作流注册表
- `SubWorkflowExecutor`: 子工作流执行器

**使用示例**:
```python
from agentm import create_nested_engine

engine = create_nested_engine()

# 注册工作流
engine.register_workflow("data_processing", DataProcessingWorkflow)

# 执行子工作流
result = await engine.execute_subworkflow(
    workflow_id="data_processing",
    input_data={"input_file": "data.csv"},
    parent_context=context
)
```

### 3.5 节点系统 (Node System)

**位置**: `src/nodes/`

**节点类型**: 24 种

#### Core Nodes (12 种)
1. `HttpRequestNode`: HTTP 请求
2. `CodeNode`: 代码执行（Python/JavaScript）
3. `ConditionNode`: 条件判断
4. `LoopNode`: 循环处理
5. `DelayNode`: 延时/定时
6. `MergeNode`: 数据合并
7. `SplitNode`: 数据拆分
8. `VariableNode`: 变量操作
9. `SubWorkflowNode`: 子工作流调用
10. `ErrorHandlerNode`: 错误处理
11. `WebhookNode`: Webhook 触发
12. `DatabaseQueryNode`: 数据库查询

#### Skill Nodes (12 种)
1. `WeatherNode`: 天气查询
2. `ImageGenerationNode`: 图像生成
3. `VideoGenerationNode`: 视频生成
4. `DataAnalysisNode`: 数据分析
5. `ChartVisualizationNode`: 图表可视化
6. `PDFNode`: PDF 处理
7. `WhisperNode`: 语音转文字
8. `CodingAgentNode`: 代码生成
9. `FrontendDesignNode`: 前端设计
10. `DeepResearchNode`: 深度研究
11. `GithubResearchNode`: GitHub 研究
12. `PPTGenerationNode`: PPT 生成

### 3.6 熔断器 (Circuit Breaker)

**位置**: `src/circuit_breaker.py`

**职责**:
- 防止级联故障
- 自动恢复机制
- 降级策略

**状态**:
- `CLOSED`: 正常状态
- `OPEN`: 熔断状态
- `HALF_OPEN`: 半开状态

### 3.7 RAG 引擎 (RAG Engine)

**位置**: `src/rag_engine.py`

**职责**:
- 文档检索
- 向量搜索
- BM25 搜索
- 混合检索

### 3.8 多 Agent 协调器 (Multi-Agent Coordinator)

**位置**: `src/multi_agent_coordinator.py`

**职责**:
- 多 Agent 协作
- 任务分配
- 会话管理

### 3.9 自主规划器 (Auto Planner)

**位置**: `src/auto_planner.py`

**职责**:
- 任务规划
- 依赖管理
- 执行计划生成

## 4. 数据流

### 4.1 节点间数据传递

```
Node A Output ──→ DataPacket ──→ Node B Input
                     │
                     ├──→ Transformation (optional)
                     │
                     └──→ Mapping (optional)
```

### 4.2 变量作用域

```
Global Context (全局)
    │
    └──→ Workflow Context (工作流)
             │
             └──→ Node Context (节点)
                      │
                      └──→ Temp Variables (临时)
```

## 5. 工作流定义格式

### JSON 格式示例

```json
{
  "workflow_id": "data_pipeline",
  "name": "数据处理管道",
  "description": "从 API 获取数据并处理",
  "version": "1.0.0",
  "nodes": [
    {
      "id": "node_1",
      "type": "http_request",
      "name": "获取数据",
      "config": {
        "url": "https://api.example.com/data",
        "method": "GET"
      }
    },
    {
      "id": "node_2",
      "type": "condition",
      "name": "数据验证",
      "config": {
        "conditions": [
          {"branch": "valid", "condition": "len(data) > 0"},
          {"branch": "invalid", "condition": "len(data) == 0"}
        ]
      }
    },
    {
      "id": "node_3",
      "type": "loop",
      "name": "处理每条数据",
      "config": {
        "items_key": "data",
        "parallel": true,
        "max_concurrency": 5
      }
    }
  ],
  "edges": [
    {"from": "node_1", "to": "node_2"},
    {"from": "node_2", "to": "node_3", "condition": "valid"}
  ]
}
```

## 6. 扩展机制

### 6.1 添加新节点

1. 继承 `BaseNode` 类
2. 实现 `execute()` 方法
3. 实现 `get_schema()` 方法
4. 在 `__init__.py` 中注册

### 6.2 添加新工作流

1. 继承 `BaseWorkflow` 类
2. 实现 `_setup_steps()` 方法
3. 在工作流注册表中注册

### 6.3 添加外部 Skill

1. 创建 Skill 目录
2. 实现 `SKILL.md` 说明
3. 实现技能逻辑
4. 在技能注册表中注册

## 7. 配置管理

**位置**: `config.yaml`

**配置项**:
- 运行环境
- RAG 引擎
- 熔断器
- 缓存
- Agent
- 工作流
- WebUI
- 日志
- 数据库

## 8. 性能优化

### 8.1 并发执行
- Loop 节点支持并行处理
- 使用 asyncio 异步 IO
- 线程池用于 CPU 密集型任务

### 8.2 缓存机制
- LRU 缓存
- 结果缓存
- 变量缓存

### 8.3 资源管理
- 连接池（数据库、HTTP）
- 上下文管理器
- 自动资源释放

## 9. 安全考虑

### 9.1 代码执行沙箱
- Code 节点在临时文件中执行
- 限制执行时间
- 捕获异常

### 9.2 输入验证
- 所有外部输入使用 pydantic 验证
- SQL 参数化查询
- XSS 防护

### 9.3 认证授权
- API Token 认证
- Webhook 签名验证
- 角色权限控制

## 10. 监控和日志

### 10.1 日志分级
- DEBUG: 调试信息
- INFO: 一般信息
- WARNING: 警告
- ERROR: 错误
- CRITICAL: 严重错误

### 10.2 执行追踪
- 工作流执行历史
- 节点执行时间
- 错误堆栈追踪

---

*最后更新：2026-04-01*
