# AgentM 节点参考手册

## 节点类型总览

AgentM 提供 **24 种节点类型**，分为两大类：

- **Core Nodes** (12 种): 核心功能节点
- **Skill Nodes** (12 种): 外部技能节点

---

## Core Nodes (核心节点)

### 1. HttpRequestNode - HTTP 请求节点

**功能**: 发送 HTTP/HTTPS 请求

**配置参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| url | string | ✅ | - | 请求 URL |
| method | string | ❌ | GET | HTTP 方法 |
| headers | object | ❌ | - | 请求头 |
| params | object | ❌ | - | 查询参数 |
| json | object | ❌ | - | JSON 请求体 |
| data | object | ❌ | - | 表单数据 |
| timeout | number | ❌ | 30.0 | 超时时间（秒） |
| follow_redirects | boolean | ❌ | true | 跟随重定向 |
| max_retries | number | ❌ | 3 | 最大重试次数 |

**输出**:
```json
{
  "status_code": 200,
  "headers": {...},
  "body": {...},
  "url": "https://..."
}
```

**示例**:
```python
node = HttpRequestNode("api_call", {
    "url": "https://api.github.com/users/octocat",
    "method": "GET",
    "headers": {"Authorization": "Bearer token"}
})
result = await node.execute(context)
```

---

### 2. CodeNode - 代码执行节点

**功能**: 执行 Python 或 JavaScript 代码

**配置参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| language | string | ✅ | python | 编程语言 (python/javascript) |
| code | string | ✅ | - | 要执行的代码 |
| timeout | number | ❌ | 30.0 | 超时时间（秒） |
| sandbox | boolean | ❌ | true | 沙箱模式 |

**输出**:
```json
{
  "result": {...}
}
```

**示例**:
```python
node = CodeNode("calc", {
    "language": "python",
    "code": """
total = sum(context.get('items', []))
return {'total': total}
"""
})
result = await node.execute({"items": [1, 2, 3, 4, 5]})
# result.output = {"total": 15}
```

---

### 3. ConditionNode - 条件判断节点

**功能**: 根据条件表达式决定执行路径

**配置参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| conditions | array | ✅ | - | 条件列表 |
| default_branch | string | ❌ | else | 默认分支 |

**conditions 格式**:
```json
[
  {"branch": "if", "condition": "value > 10"},
  {"branch": "elif", "condition": "value > 5"},
  {"branch": "else", "condition": ""}
]
```

**输出**:
```json
{
  "matched_branch": "if",
  "condition_result": true
}
```

**示例**:
```python
node = ConditionNode("check", {
    "conditions": [
        {"branch": "adult", "condition": "age >= 18"},
        {"branch": "child", "condition": "age < 18"}
    ]
})
result = await node.execute({"age": 25})
# result.output["matched_branch"] = "adult"
```

---

### 4. LoopNode - 循环节点

**功能**: 对数组进行循环处理

**配置参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| items_key | string | ❌ | items | 输入数组的 key |
| result_key | string | ❌ | results | 输出结果的 key |
| parallel | boolean | ❌ | false | 并行执行 |
| max_concurrency | number | ❌ | 5 | 最大并发数 |
| break_on_error | boolean | ❌ | true | 错误时中断 |
| continue_on_error | boolean | ❌ | false | 错误时继续 |

**输出**:
```json
{
  "results": [...],
  "count": 10,
  "success_count": 9
}
```

**示例**:
```python
node = LoopNode("process", {
    "items_key": "users",
    "parallel": True,
    "max_concurrency": 3
})

async def process_user(ctx):
    user = ctx["item"]
    return {"processed": True, "user": user}

node.set_loop_function(process_user)
result = await node.execute({"users": [...]})
```

---

### 5. DelayNode - 延时节点

**功能**: 延时或定时执行

**配置参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| delay_seconds | number | ❌ | 1.0 | 延时秒数 |
| until_time | string | ❌ | - | 执行时间 (ISO 8601) |

**输出**:
```json
{
  "delayed": true,
  "delay_seconds": 5.0,
  "timestamp": "2026-04-01T12:00:00"
}
```

---

### 6. MergeNode - 合并节点

**功能**: 合并多个输入数据

**配置参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| merge_strategy | string | ❌ | concat | 合并策略 |
| output_key | string | ❌ | merged | 输出 key |

**merge_strategy**:
- `concat`: 数组合并
- `merge_objects`: 对象合并
- `first`: 取第一个
- `last`: 取最后一个

**输出**:
```json
{
  "merged": [...],
  "count": 3
}
```

---

### 7. SplitNode - 拆分节点

**功能**: 将数组拆分为多个块

**配置参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| input_key | string | ❌ | items | 输入数组的 key |
| chunk_size | number | ❌ | 1 | 每块大小 |

**输出**:
```json
{
  "chunks": [[...], [...], ...],
  "total": 10,
  "chunk_count": 5
}
```

---

### 8. VariableNode - 变量操作节点

**功能**: 设置、获取、删除变量

**配置参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| operation | string | ✅ | set | 操作类型 |
| variables | object | ❌ | - | 变量配置 |

**operation**:
- `set`: 设置变量
- `get`: 获取变量
- `delete`: 删除变量
- `list`: 列出变量

**示例**:
```python
node = VariableNode("set_var", {
    "operation": "set",
    "variables": {
        "api_key": "{{ secrets.api_key }}",
        "count": 10
    }
})
```

---

### 9. SubWorkflowNode - 子工作流节点

**功能**: 调用子工作流

**配置参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| workflow_id | string | ✅ | - | 工作流 ID |
| input_mapping | object | ❌ | - | 输入映射 |
| output_mapping | object | ❌ | - | 输出映射 |

---

### 10. ErrorHandlerNode - 错误处理节点

**功能**: 捕获和处理错误

**配置参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| error_types | array | ❌ | ["all"] | 错误类型 |
| fallback_value | any | ❌ | - | 降级值 |
| retry_count | number | ❌ | 0 | 重试次数 |
| on_error_action | string | ❌ | continue | 处理动作 |

---

### 11. WebhookNode - Webhook 节点

**功能**: 触发和接收 Webhook

**配置参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| webhook_id | string | ✅ | - | Webhook ID |
| method | string | ❌ | POST | HTTP 方法 |
| expected_fields | array | ❌ | - | 期望字段 |
| response_template | object | ❌ | - | 响应模板 |

---

### 12. DatabaseQueryNode - 数据库查询节点

**功能**: 执行 SQL 查询

**配置参数**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| connection_string | string | ✅ | - | 数据库连接 |
| query | string | ✅ | - | SQL 查询 |
| params | array | ❌ | [] | 查询参数 |
| fetch_mode | string | ❌ | all | 获取模式 |

**fetch_mode**:
- `all`: 获取所有行
- `one`: 获取一行
- `many`: 获取多行

---

## Skill Nodes (技能节点)

### 13. WeatherNode - 天气查询

**功能**: 查询天气预报

**配置**:
```python
node = WeatherNode("weather", {
    "location": "Beijing",
    "days": 3
})
```

---

### 14. ImageGenerationNode - 图像生成

**功能**: AI 生成图像

**配置**:
```python
node = ImageGenerationNode("gen_image", {
    "prompt": "A beautiful sunset",
    "size": "1024x1024"
})
```

---

### 15. VideoGenerationNode - 视频生成

**功能**: AI 生成视频

---

### 16. DataAnalysisNode - 数据分析

**功能**: 数据分析处理

---

### 17. ChartVisualizationNode - 图表可视化

**功能**: 生成各种图表

---

### 18. PDFNode - PDF 处理

**功能**: PDF 文件操作

---

### 19. WhisperNode - 语音转文字

**功能**: 语音识别

---

### 20. CodingAgentNode - 代码生成

**功能**: AI 生成代码

---

### 21. FrontendDesignNode - 前端设计

**功能**: 生成前端页面

---

### 22. DeepResearchNode - 深度研究

**功能**: 深度网络研究

---

### 23. GithubResearchNode - GitHub 研究

**功能**: GitHub 仓库分析

---

### 24. PPTGenerationNode - PPT 生成

**功能**: 生成演示文稿

---

## 节点通用接口

所有节点都继承自 `BaseNode`，提供以下通用方法：

```python
class BaseNode:
    async def execute(self, context: Dict) -> NodeResult:
        """执行节点"""
        pass
    
    def get_schema(self) -> Dict:
        """获取节点 schema"""
        pass
    
    async def run(self, context: Dict) -> NodeResult:
        """运行节点（带状态管理）"""
        pass
    
    def validate_input(self, context: Dict) -> tuple[bool, str]:
        """验证输入"""
        pass
```

---

*最后更新：2026-04-01*
