# AgentM Workflows - 工作流模板库

## 功能描述
提供预定义的工作流模板，包括数据同步、定时报告、API 集成、AI 辅助等常用场景。

## 激活条件
当用户提到以下关键词时激活：
- 工作流 / 自动化流程
- 数据同步 / ETL
- 定时任务 / 报告生成
- API 集成 / 批量处理

## 依赖安装
```bash
pip install pyyaml pytest pytest-asyncio
```

## 工作流模板

### 1. 数据同步工作流 (DataSyncWorkflow)
用于在不同数据源之间同步数据。

**步骤：**
1. validate_config - 验证配置
2. connect_source - 连接源数据
3. connect_target - 连接目标
4. extract_data - 提取数据
5. transform_data - 转换数据
6. load_data - 加载数据
7. verify_sync - 验证同步

**配置示例：**
```python
config = {
    "source": {
        "type": "mysql",
        "host": "localhost",
        "port": 3306,
        "database": "source_db"
    },
    "target": {
        "type": "postgres",
        "host": "localhost",
        "port": 5432,
        "database": "target_db"
    },
    "transform_rules": {
        "mapping": {"old_field": "new_field"},
        "filters": ["status = 'active'"]
    }
}
```

**使用方式：**
```python
from agentm.workflows.workflow_engine import DataSyncWorkflow, run_data_sync

# 方式 1：使用类
workflow = DataSyncWorkflow(config)
result = await workflow.execute()

# 方式 2：使用便捷函数
result = await run_data_sync(config)

# 查看结果
print(f"状态：{result.status}")
print(f"耗时：{result.total_duration:.2f}s")
for step in result.step_results:
    print(f"  {step.step_name}: {step.status.value}")
```

### 2. 定时报告工作流 (ScheduledReportWorkflow)
用于生成和发送定时报告。

**步骤：**
1. collect_data - 收集数据
2. analyze_data - 分析数据
3. generate_report - 生成报告
4. send_report - 发送报告

**配置示例：**
```python
config = {
    "output_path": "reports/daily_report.pdf",
    "report_type": "daily",
    "metrics": ["sales", "users", "conversion"],
    "recipients": ["team@example.com"],
    "schedule": "0 9 * * *"  # 每天 9 点
}
```

**使用方式：**
```python
from agentm.workflows.workflow_engine import ScheduledReportWorkflow

workflow = ScheduledReportWorkflow(config)
result = await workflow.execute()

# 获取报告路径
report_path = result.step_results[2].output
```

### 3. API 集成工作流 (APIIntegrationWorkflow)
用于集成第三方 API。

**步骤：**
1. authenticate - 认证
2. fetch_data - 获取数据
3. process_response - 处理响应
4. store_result - 存储结果

**配置示例：**
```python
config = {
    "auth": {
        "type": "bearer",
        "token": "your_api_token",
        "refresh_url": "https://api.example.com/refresh"
    },
    "api": {
        "base_url": "https://api.example.com",
        "endpoints": {
            "data": "/v1/data",
            "update": "/v1/update"
        }
    },
    "storage": {
        "type": "database",
        "table": "api_data"
    }
}
```

**使用方式：**
```python
from agentm.workflows.workflow_engine import APIIntegrationWorkflow

workflow = APIIntegrationWorkflow(config)
result = await workflow.execute()

# 获取 API 响应
api_data = workflow.engine.context.get("api_response")
```

### 4. AI 辅助工作流 (AIAssistantWorkflow)
用于 AI 辅助任务处理。

**步骤：**
1. parse_request - 解析请求
2. select_model - 选择模型
3. generate_response - 生成响应
4. format_output - 格式化输出

**配置示例：**
```python
config = {
    "request": "分析销售数据并生成洞察",
    "model": "gpt-4",
    "context": {
        "data_source": "sales_db",
        "time_range": "last_30_days"
    },
    "output_format": "markdown"
}
```

**使用方式：**
```python
from agentm.workflows.workflow_engine import AIAssistantWorkflow

workflow = AIAssistantWorkflow(config)
result = await workflow.execute()

# 获取 AI 响应
ai_response = workflow.engine.context.get("ai_response")
```

## 自定义工作流

### 创建自定义工作流
```python
from agentm.workflows.workflow_engine import BaseWorkflow, WorkflowResult

class CustomWorkflow(BaseWorkflow):
    def _setup_steps(self) -> None:
        """设置自定义步骤"""
        self.engine.add_step(
            name="step1",
            func=self._step1,
            description="第一步",
            retry_count=2
        )
        self.engine.add_step(
            name="step2",
            func=self._step2,
            description="第二步"
        )
    
    def _step1(self, context: Dict) -> Any:
        """步骤 1 实现"""
        # 实现逻辑
        return result
    
    def _step2(self, context: Dict) -> Any:
        """步骤 2 实现"""
        # 使用 context["step1"] 获取上一步结果
        return result

# 使用
workflow = CustomWorkflow({"param": "value"})
result = await workflow.execute()
```

### 步骤执行上下文
每个步骤可以通过 `context` 参数共享数据：
```python
def step1(context):
    context["data"] = {"key": "value"}
    return context["data"]

def step2(context):
    # 访问上一步的数据
    data = context.get("data", {})
    return process(data)
```

## 错误处理

### 步骤重试
```python
engine.add_step(
    name="flaky_step",
    func=flaky_function,
    retry_count=3,        # 重试 3 次
    retry_delay=2.0       # 每次延迟 2 秒
)
```

### 跳过错误步骤
```python
engine.add_step(
    name="optional_step",
    func=optional_function,
    skip_on_error=True    # 失败时跳过，继续执行
)
```

### 超时控制
```python
engine.add_step(
    name="slow_step",
    func=slow_function,
    timeout=300.0         # 5 分钟超时
)
```

## 执行结果

### WorkflowResult 属性
| 属性 | 类型 | 说明 |
|------|------|------|
| workflow_name | str | 工作流名称 |
| status | WorkflowStatus | 执行状态 |
| step_results | List[StepResult] | 步骤结果列表 |
| total_duration | float | 总耗时（秒） |
| start_time | datetime | 开始时间 |
| end_time | datetime | 结束时间 |
| error | str | 错误信息 |

### StepResult 属性
| 属性 | 类型 | 说明 |
|------|------|------|
| step_name | str | 步骤名称 |
| status | StepStatus | 执行状态 |
| output | Any | 输出数据 |
| error | str | 错误信息 |
| duration | float | 耗时（秒） |
| timestamp | datetime | 时间戳 |

## 测试
```bash
cd /home/liyongxin/.openclaw/workspace/agentm/workflows
pytest test_workflows.py -v
```

## 文件结构
```
workflows/
├── SKILL.md                  # 技能说明文档
├── README.md                 # 快速入门
├── workflow_engine.py        # 工作流引擎和模板
├── test_workflows.py         # 单元测试
└── __init__.py               # 模块初始化
```
