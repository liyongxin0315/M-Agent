# AgentM 使用指南

## 快速开始

### 1. 安装依赖

```bash
cd /home/liyongxin/.openclaw/workspace/agentm
pip install -r requirements.txt
```

### 2. 配置环境

```bash
# 复制配置文件
cp config.yaml config.local.yaml

# 编辑配置（根据需要修改）
vim config.local.yaml
```

### 3. 运行示例

```bash
# 运行简单工作流
python -m workflows.examples.skill_workflows

# 启动 WebUI
cd webui
python webui.py
# 访问 http://localhost:5000
```

## 核心概念

### 工作流 (Workflow)

工作流是由多个节点组成的任务序列。每个节点执行特定功能，节点之间通过数据流连接。

### 节点 (Node)

节点是工作流的基本执行单元。AgentM 提供 24 种节点类型：

#### 核心节点
- **HTTP Request**: 发送 HTTP 请求
- **Code**: 执行 Python/JavaScript 代码
- **Condition**: 条件判断
- **Loop**: 循环处理
- **Delay**: 延时/定时
- **Merge**: 数据合并
- **Split**: 数据拆分
- **Variable**: 变量操作
- **Sub-Workflow**: 子工作流调用
- **Error Handler**: 错误处理
- **Webhook**: Webhook 触发
- **Database Query**: 数据库查询

#### 技能节点
- **Weather**: 天气查询
- **Image Generation**: 图像生成
- **Video Generation**: 视频生成
- **Data Analysis**: 数据分析
- **Chart Visualization**: 图表可视化
- **PDF**: PDF 处理
- **Whisper**: 语音转文字
- **Coding Agent**: 代码生成
- **Frontend Design**: 前端设计
- **Deep Research**: 深度研究
- **GitHub Research**: GitHub 研究
- **PPT Generation**: PPT 生成

### 变量 (Variable)

变量用于在工作流中存储和传递数据。支持 4 种作用域：

- **Global**: 全局变量，所有工作流可访问
- **Workflow**: 工作流变量，当前工作流内访问
- **Node**: 节点变量，节点内部访问
- **Temp**: 临时变量，当前执行上下文

### 数据流 (Data Flow)

数据以 JSON 格式在节点间传递。支持多种数据转换：

- `identity`: 原样传递
- `to_list`: 转为数组
- `flatten`: 扁平化
- `filter`: 过滤
- `map`: 映射
- `reduce`: 归约

## 使用示例

### 示例 1: 简单 HTTP 请求工作流

```python
import asyncio
from agentm.workflows.workflow_engine import WorkflowEngine, BaseWorkflow

class SimpleAPIWorkflow(BaseWorkflow):
    """简单 API 调用工作流"""
    
    def _setup_steps(self):
        # 步骤 1: HTTP 请求
        self.engine.add_step(
            name="fetch_data",
            func=self._fetch_data,
            description="从 API 获取数据",
            retry_count=3
        )
        
        # 步骤 2: 处理数据
        self.engine.add_step(
            name="process_data",
            func=self._process_data,
            description="处理返回的数据"
        )
        
        # 步骤 3: 保存结果
        self.engine.add_step(
            name="save_result",
            func=self._save_result,
            description="保存处理结果"
        )
    
    async def _fetch_data(self, context):
        from agentm.nodes import HttpRequestNode
        
        node = HttpRequestNode("api_call", {
            "url": "https://api.example.com/data",
            "method": "GET"
        })
        
        result = await node.execute(context)
        return result.output
    
    async def _process_data(self, context):
        data = context.get("fetch_data", {})
        # 处理数据逻辑
        return {"processed": True, "data": data}
    
    async def _save_result(self, context):
        result = context.get("process_data")
        # 保存逻辑
        return {"saved": True}

# 运行工作流
async def main():
    workflow = SimpleAPIWorkflow()
    result = await workflow.execute()
    print(f"状态：{result.status}")
    print(f"步骤结果：{result.step_results}")

asyncio.run(main())
```

### 示例 2: 条件分支工作流

```python
from agentm.nodes import ConditionNode, HttpRequestNode, CodeNode

async def conditional_workflow():
    context = {"data": [1, 2, 3, 4, 5]}
    
    # 条件判断
    condition_node = ConditionNode("check_data", {
        "conditions": [
            {"branch": "has_data", "condition": "len(data) > 0"},
            {"branch": "no_data", "condition": "len(data) == 0"}
        ]
    })
    
    result = await condition_node.execute(context)
    branch = result.output["matched_branch"]
    
    if branch == "has_data":
        # 有数据，进行处理
        http_node = HttpRequestNode("fetch_detail", {
            "url": "https://api.example.com/detail",
            "method": "POST",
            "json": {"ids": context["data"]}
        })
        result = await http_node.execute(context)
    else:
        # 无数据，创建默认数据
        code_node = CodeNode("create_default", {
            "language": "python",
            "code": "return {'default': True}"
        })
        result = await code_node.execute(context)
    
    return result
```

### 示例 3: 循环处理工作流

```python
from agentm.nodes import LoopNode, HttpRequestNode

async def loop_workflow():
    context = {
        "items": [
            {"id": 1, "name": "Item 1"},
            {"id": 2, "name": "Item 2"},
            {"id": 3, "name": "Item 3"}
        ]
    }
    
    # 创建循环节点
    loop_node = LoopNode("process_items", {
        "items_key": "items",
        "parallel": True,
        "max_concurrency": 3
    })
    
    # 设置循环函数
    async def process_item(item_context):
        item = item_context["item"]
        index = item_context["index"]
        
        # 处理每个 item
        http_node = HttpRequestNode(f"fetch_{index}", {
            "url": f"https://api.example.com/item/{item['id']}"
        })
        result = await http_node.execute(item_context)
        return result.output
    
    loop_node.set_loop_function(process_item)
    
    result = await loop_node.execute(context)
    print(f"处理了 {result.output['count']} 个物品")
    return result
```

### 示例 4: 变量系统使用

```python
from agentm import create_variable_system

# 创建变量系统
vs = create_variable_system()

# 设置全局变量
vs.set_global("api_key", "sk-xxx", description="API 密钥", is_readonly=True)
vs.set_global("base_url", "https://api.example.com")

# 创建工作流上下文
ctx = vs.create_workflow_context("workflow_1")
ctx.set("user_name", "张三")
ctx.set("items", [1, 2, 3])

# 模板渲染
template = "Hello, {{ user_name }}! You have {{ items|length }} items."
result = vs.render(template)
print(result)  # Hello, 张三！You have 3 items.

# 渲染对象
obj = {
    "message": "Welcome, {{ user_name }}!",
    "url": "{{ base_url }}/user/{{ user_name }}"
}
rendered = vs.render_object(obj)
print(rendered)
```

### 示例 5: 数据流转换

```python
from agentm import create_data_flow

# 创建数据流管理器
df = create_data_flow()

# 添加字段映射
df.add_mapping("node_a", "node_b", {
    "user_id": "id",
    "user_name": "name"
})

# 数据转换
data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

# Filter
filtered = df.transform_data(data, "filter", {
    "condition": {"id": {"op": "gt", "value": 1}}
})
print(filtered)  # [{'id': 2, 'name': 'Bob'}]

# Map
mapped = df.transform_data(data, "map", {
    "mapping": {"uid": "id", "full_name": "name"}
})
print(mapped)  # [{'uid': 1, 'full_name': 'Alice'}, ...]

# Group By
grouped = df.transform_data(data, "group_by", {"key": "name"})
print(grouped)
```

### 示例 6: 子工作流调用

```python
from agentm import create_nested_engine
from agentm.workflows.workflow_engine import BaseWorkflow

# 定义子工作流
class DataProcessingWorkflow(BaseWorkflow):
    def _setup_steps(self):
        self.engine.add_step(
            name="validate",
            func=lambda ctx: {"valid": True},
            description="验证数据"
        )
        self.engine.add_step(
            name="process",
            func=lambda ctx: {"processed": True},
            description="处理数据"
        )

# 创建嵌套引擎
engine = create_nested_engine()

# 注册子工作流
engine.register_workflow("data_processing", DataProcessingWorkflow)

# 在主工作流中调用子工作流
async def main_workflow():
    context = {"input_data": "test.csv"}
    
    result = await engine.execute_subworkflow(
        workflow_id="data_processing",
        input_data={"file": context["input_data"]},
        parent_context=context
    )
    
    print(f"子工作流结果：{result}")
    return result
```

## 工作流定义（JSON 格式）

创建 `workflows/my_workflow.json`:

```json
{
  "workflow_id": "my_workflow",
  "name": "我的工作流",
  "description": "示例工作流",
  "version": "1.0.0",
  "nodes": [
    {
      "id": "start",
      "type": "http_request",
      "name": "获取数据",
      "config": {
        "url": "https://api.example.com/data",
        "method": "GET"
      }
    },
    {
      "id": "process",
      "type": "code",
      "name": "处理数据",
      "config": {
        "language": "python",
        "code": "return {'processed': True, 'data': context.get('start', {})}"
      }
    },
    {
      "id": "save",
      "type": "database_query",
      "name": "保存数据",
      "config": {
        "connection_string": "./data.db",
        "query": "INSERT INTO results (data) VALUES (?)"
      }
    }
  ],
  "edges": [
    {"from": "start", "to": "process"},
    {"from": "process", "to": "save"}
  ]
}
```

## 最佳实践

### 1. 错误处理

```python
# 使用重试机制
self.engine.add_step(
    name="api_call",
    func=self._call_api,
    retry_count=3,
    retry_delay=2.0,
    skip_on_error=False
)

# 使用错误处理节点
error_handler = ErrorHandlerNode("handle_error", {
    "error_types": ["all"],
    "fallback_value": {"default": True},
    "on_error_action": "continue"
})
```

### 2. 性能优化

```python
# 并行处理
loop_node = LoopNode("parallel_process", {
    "parallel": True,
    "max_concurrency": 10
})

# 使用缓存
from agentm.optimizer import LRUCache
cache = LRUCache(max_size=1000)
```

### 3. 日志记录

```python
import logging
logger = logging.getLogger(__name__)

# 分级日志
logger.debug("调试信息")
logger.info("一般信息")
logger.warning("警告")
logger.error("错误")
```

### 4. 配置管理

```python
# 从环境变量读取
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("API_KEY")
db_url = os.getenv("DATABASE_URL")
```

## 故障排除

### 常见问题

**Q: 工作流执行失败**
- 检查日志输出
- 验证节点配置
- 确认网络连接

**Q: 变量未生效**
- 检查变量作用域
- 确认变量名称正确
- 检查模板语法

**Q: 性能慢**
- 使用并行处理
- 启用缓存
- 优化数据库查询

## 参考资源

- [架构设计文档](ARCHITECTURE.md)
- [节点参考手册](NODE_REFERENCE.md)
- [示例工作流](workflows/examples/)
- [API 文档](webui/api_docs)

---

*最后更新：2026-04-01*
