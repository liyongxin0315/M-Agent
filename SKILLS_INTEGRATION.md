# AgentM Skills Integration

全栈 Skills 集成到 AgentM 工作流系统。

## 📁 目录结构

```
agentm/
├── src/
│   ├── nodes/
│   │   ├── base_node.py              # 节点基类
│   │   └── skill_nodes/              # 技能节点适配器
│   │       ├── __init__.py
│   │       ├── data_analysis_node.py
│   │       ├── deep_research_node.py
│   │       ├── github_research_node.py
│   │       ├── image_generation_node.py
│   │       ├── video_generation_node.py
│   │       ├── ppt_generation_node.py
│   │       ├── frontend_design_node.py
│   │       ├── coding_agent_node.py
│   │       ├── chart_visualization_node.py
│   │       ├── weather_node.py
│   │       ├── whisper_node.py
│   │       └── pdf_node.py
│   └── skill_registry.py             # 技能注册系统
├── workflows/
│   ├── examples/                     # 示例工作流
│   │   ├── __init__.py
│   │   ├── data_analysis_workflow.py
│   │   ├── research_workflow.py
│   │   ├── content_creation_workflow.py
│   │   └── dev_assistant_workflow.py
│   └── workflow_engine.py            # 工作流引擎
└── requirements_skills.txt           # 依赖要求
```

## 🎯 集成的 Skills

### 数据处理类
| Skill | 节点类 | 描述 |
|-------|--------|------|
| data-analysis | `DataAnalysisNode` | 数据分析 |
| deep-research | `DeepResearchNode` | 深度研究 |
| github-deep-research | `GitHubResearchNode` | GitHub 代码库研究 |

### 内容生成类
| Skill | 节点类 | 描述 |
|-------|--------|------|
| image-generation | `ImageGenerationNode` | 图片生成 |
| video-generation | `VideoGenerationNode` | 视频生成 |
| ppt-generation | `PPTGenerationNode` | PPT 生成 |
| frontend-design | `FrontendDesignNode` | 前端设计 |

### 开发工具类
| Skill | 节点类 | 描述 |
|-------|--------|------|
| coding-agent | `CodingAgentNode` | 编码助手 |

### 其他工具类
| Skill | 节点类 | 描述 |
|-------|--------|------|
| chart-visualization | `ChartVisualizationNode` | 图表可视化 |
| weather | `WeatherNode` | 天气查询 |
| openai-whisper | `WhisperNode` | 语音识别 |
| nano-pdf | `PDFNode` | PDF 处理 |

## 🚀 快速开始

### 1. 安装依赖

```bash
cd agentm
pip install -r requirements_skills.txt
```

### 2. 初始化技能注册表

```python
from agentm.src.skill_registry import get_registry, register_default_skills

# 注册默认技能
register_default_skills()

# 获取注册表
registry = get_registry()

# 列出所有技能
skills = registry.list_skills()
for skill in skills:
    print(f"- {skill.name}: {skill.description}")
```

### 3. 使用技能节点

```python
from agentm.src.nodes.skill_nodes import DataAnalysisNode

# 创建节点
node = DataAnalysisNode()

# 执行
result = await node.execute({
    "data_path": "data/sample.csv",
    "analysis_type": "descriptive"
})

print(result.output)
```

### 4. 运行示例工作流

```python
from agentm.workflows.examples import DataAnalysisWorkflow

# 创建工作流
workflow = DataAnalysisWorkflow(config={
    "data_path": "data/sample.csv",
    "analysis_type": "descriptive",
    "output_dir": "output"
})

# 执行
result = await workflow.execute()
print(result.to_dict())
```

## 📖 示例工作流

### 数据分析工作流

```python
from agentm.workflows.examples import run_data_analysis

result = await run_data_analysis(
    data_path="data/sales.csv",
    analysis_type="exploratory",
    chart_types=["line", "bar"]
)
```

### 研究工作流

```python
from agentm.workflows.examples import run_research

result = await run_research(
    query="Python async programming best practices",
    repos=["python/cpython", "asyncio"],
    max_sources=15
)
```

### 内容创作工作流

```python
from agentm.workflows.examples import run_content_creation

result = await run_content_creation(
    title="产品发布会",
    content="# 产品介绍\n## 功能亮点\n- 特性 1\n- 特性 2",
    image_prompts=["现代科技风格的产品图片"],
    landing_page_description="创建一个产品展示页面"
)
```

### 开发助手工作流

```python
from agentm.workflows.examples import run_dev_assistant

result = await run_dev_assistant(
    task="为用户认证模块添加 OAuth2 支持",
    workdir="/path/to/project",
    coding_agent="claude-code"
)
```

## 🔧 自定义技能节点

创建新的技能节点：

```python
from agentm.src.nodes.base_node import BaseNode, NodeResult, NodeStatus

class MyCustomNode(BaseNode):
    """自定义技能节点"""
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        # 实现逻辑
        return NodeResult(
            status=NodeStatus.COMPLETED,
            output={"result": "success"},
            node_name=self.name
        )
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "inputs": {
                "param1": {"type": "string", "required": True}
            },
            "outputs": {
                "result": {"type": "object"}
            }
        }
```

注册技能：

```python
from agentm.src.skill_registry import get_registry, SkillCategory

registry = get_registry()
registry.register(
    name="my_custom_skill",
    class_name="MyCustomNode",
    category=SkillCategory.UTILITY_TOOLS,
    description="我的自定义技能",
    module_path="my_module.my_custom_node"
)
```

## 📊 技能注册表 API

```python
from agentm.src.skill_registry import get_registry

registry = get_registry()

# 列出技能
skills = registry.list_skills()
skills_by_category = registry.list_skills(category=SkillCategory.DATA_PROCESSING)

# 获取技能信息
skill_info = registry.get_skill("data_analysis")

# 获取节点实例
node = registry.get_node("data_analysis")

# 执行技能
result = await registry.execute("data_analysis", {
    "data_path": "data.csv"
})

# 查看统计
stats = registry.get_stats()
print(f"成功率：{stats['success_rate']:.2%}")

# 执行历史
history = registry.get_execution_history(limit=10)
```

## ⚙️ 配置

通过环境变量配置：

```bash
# OpenAI API (用于图片生成)
export OPENAI_API_KEY="your-api-key"

# Stability AI (用于视频生成)
export STABILITY_API_KEY="your-api-key"

# GitHub Token (用于 GitHub 研究)
export GITHUB_TOKEN="your-token"
```

## 🧪 测试

```bash
# 运行测试
pytest agentm/workflows/examples/ -v

# 运行单个测试
pytest agentm/workflows/examples/test_data_analysis.py -v
```

## 📝 注意事项

1. **依赖管理**: 部分技能需要额外的 API Key 或 CLI 工具
2. **错误处理**: 所有节点都有降级方案，当主要服务不可用时会自动切换
3. **异步执行**: 工作流支持异步步骤，确保使用 `await` 调用
4. **日志记录**: 所有操作都有详细日志，便于调试

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License
