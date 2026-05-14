# AgentM 外部 Skills 集成指南

## 📦 概述

AgentM 已集成 12 个外部 Skills，提供丰富的 AI 能力和工具调用功能。所有 Skills 通过统一的节点适配器（Node Adapters）和执行器（Skill Executor）进行调用。

## 🎯 已集成的 Skills

| 序号 | Skill 名称 | 功能描述 | 节点类 | 状态 |
|------|-----------|---------|--------|------|
| 1 | **weather** | 天气查询（wttr.in API） | `WeatherNode` | ✅ 完成 |
| 2 | **coding-agent** | 代码生成与审查（Codex/Claude Code） | `CodingAgentNode` | ✅ 完成 |
| 3 | **data-analysis** | 数据分析（DuckDB + Pandas） | `DataAnalysisNode` | ✅ 完成 |
| 4 | **deep-research** | 深度研究（Tavily API） | `DeepResearchNode` | ✅ 完成 |
| 5 | **frontend-design** | 前端设计生成 | `FrontendDesignNode` | ✅ 完成 |
| 6 | **image-generation** | 图片生成（AIGC） | `ImageGenerationNode` | ✅ 完成 |
| 7 | **nano-pdf** | PDF 编辑（nano-pdf CLI） | `PDFNode` | ✅ 完成 |
| 8 | **openai-whisper** | 语音转文字（Whisper） | `WhisperNode` | ✅ 完成 |
| 9 | **ppt-generation** | PPT 演示文稿生成 | `PPTGenerationNode` | ✅ 完成 |
| 10 | **chart-visualization** | 图表可视化（AntV） | `ChartVisualizationNode` | ✅ 完成 |
| 11 | **video-generation** | 视频生成（AIGC） | `VideoGenerationNode` | ✅ 完成 |
| 12 | **frontend-design** | 前端界面设计 | `FrontendDesignNode` | ✅ 完成 |

## 📁 目录结构

```
agentm/
├── skills_external/              # 外部 Skills 源文件
│   ├── weather/
│   ├── coding-agent/
│   ├── data-analysis/
│   ├── deep-research/
│   ├── frontend-design/
│   ├── image-generation/
│   ├── nano-pdf/
│   ├── openai-whisper/
│   ├── ppt-generation/
│   ├── chart-visualization/
│   └── video-generation/
│
├── src/
│   ├── nodes/
│   │   └── skill_nodes/         # 节点适配器
│   │       ├── base_node.py     # 节点基类
│   │       ├── weather_node.py
│   │       ├── coding_agent_node.py
│   │       ├── data_analysis_node.py
│   │       ├── deep_research_node.py
│   │       ├── frontend_design_node.py
│   │       ├── image_generation_node.py
│   │       ├── pdf_node.py
│   │       ├── whisper_node.py
│   │       ├── ppt_generation_node.py
│   │       ├── chart_visualization_node.py
│   │       └── video_generation_node.py
│   │
│   └── skill_executor.py         # 统一技能执行器
│
└── workflows/
    └── examples/
        └── skill_workflows.py    # 示例工作流
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd /home/liyongxin/.openclaw/workspace/agentm
pip install -r requirements.txt
```

### 2. 使用 Skill Executor（推荐）

```python
import asyncio
from agentm.src.skill_executor import SkillExecutor, SkillType

async def main():
    # 创建执行器
    executor = SkillExecutor()
    
    # 查询天气
    result = await executor.execute(
        SkillType.WEATHER,
        {"location": "Beijing"}
    )
    
    if result.status.value == "completed":
        print(f"天气：{result.output}")
    else:
        print(f"错误：{result.error}")
    
    # 批量执行
    results = await executor.execute_batch([
        {"skill_type": SkillType.WEATHER, "input_data": {"location": "Shanghai"}},
        {"skill_type": SkillType.WEATHER, "input_data": {"location": "Guangzhou"}}
    ], parallel=True)
    
    for r in results:
        print(f"状态：{r.status.value}")

asyncio.run(main())
```

### 3. 直接使用节点

```python
from agentm.src.nodes.skill_nodes.weather_node import WeatherNode

async def get_weather():
    node = WeatherNode()
    result = await node.execute({"location": "Beijing"})
    print(result.output)
```

### 4. 使用示例工作流

```python
from agentm.workflows.examples.skill_workflows import (
    DataAnalysisVisualizationWorkflow,
    ResearchReportWorkflow,
    SmartAssistantWorkflow
)

async def run_workflows():
    from agentm.src.skill_executor import SkillExecutor
    
    executor = SkillExecutor()
    
    # 数据分析工作流
    analysis_wf = DataAnalysisVisualizationWorkflow(executor)
    result = await analysis_wf.run(
        data_path="/path/to/data.csv",
        chart_types=["bar_chart", "line_chart"]
    )
    
    # 研究报告工作流
    research_wf = ResearchReportWorkflow(executor)
    result = await research_wf.run(
        topic="AI 技术发展趋势",
        ppt_style="business"
    )
    
    # 智能助手工作流
    assistant = SmartAssistantWorkflow(executor)
    result = await assistant.run("北京天气怎么样？")
```

## 📖 详细 API 文档

### SkillExecutor

统一技能执行器，提供所有 Skills 的统一访问接口。

#### 初始化

```python
executor = SkillExecutor(configs=[
    SkillConfig(
        skill_type=SkillType.WEATHER,
        enabled=True,
        timeout=60,
        cache_enabled=True
    )
])
```

#### 方法

| 方法 | 说明 | 参数 | 返回值 |
|------|------|------|--------|
| `execute` | 执行单个技能 | `skill_type`, `input_data`, `use_cache` | `NodeResult` |
| `execute_batch` | 批量执行 | `executions`, `parallel` | `List[NodeResult]` |
| `clear_cache` | 清除缓存 | `skill_type` (可选) | `None` |
| `get_execution_history` | 获取执行历史 | `skill_type`, `limit` | `List[SkillExecution]` |
| `get_stats` | 获取统计信息 | - | `Dict` |
| `enable_skill` | 启用技能 | `skill_type` | `None` |
| `disable_skill` | 禁用技能 | `skill_type` | `None` |
| `get_available_skills` | 获取可用技能列表 | - | `List[str]` |

### SkillType 枚举

```python
class SkillType(Enum):
    DATA_ANALYSIS = "data_analysis"
    DEEP_RESEARCH = "deep_research"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    PPT_GENERATION = "ppt_generation"
    FRONTEND_DESIGN = "frontend_design"
    CODING_AGENT = "coding_agent"
    CHART_VISUALIZATION = "chart_visualization"
    WEATHER = "weather"
    WHISPER = "whisper"
    PDF = "pdf"
```

### NodeResult

技能执行结果数据结构。

```python
@dataclass
class NodeResult:
    status: NodeStatus          # 执行状态
    output: Any                 # 输出数据
    error: Optional[str]        # 错误信息
    node_name: str              # 节点名称
    execution_time: float       # 执行时间（秒）
    metadata: Dict[str, Any]    # 元数据
```

### 各 Skill 输入参数

#### 1. Weather

```python
{
    "location": "Beijing",              # 必需：地点
    "forecast_days": 0,                 # 可选：预报天数 (0-3)
    "format": "simple"                  # 可选：输出格式 (simple/detailed/json)
}
```

#### 2. Data Analysis

```python
{
    "data_path": "/path/to/data.csv",   # 必需：数据文件路径
    "analysis_type": "descriptive",     # 可选：分析类型
    "columns": ["col1", "col2"],        # 可选：要分析的列
    "output_format": "json"             # 可选：输出格式
}
```

#### 3. Deep Research

```python
{
    "query": "AI 技术发展趋势",           # 必需：研究主题
    "max_sources": 10,                  # 可选：最大来源数
    "time_range": "month",              # 可选：时间范围
    "include_answer": True              # 可选：是否包含 AI 总结
}
```

#### 4. Image Generation

```python
{
    "prompt": "A beautiful sunset",     # 必需：提示词
    "style": "realistic",               # 可选：风格
    "aspect_ratio": "16:9",             # 可选：宽高比
    "reference_images": [...]           # 可选：参考图片
}
```

#### 5. Video Generation

```python
{
    "prompt": "Short video about AI",   # 必需：提示词
    "reference_images": [...],          # 可选：参考图片
    "duration": 30,                     # 可选：时长（秒）
    "aspect_ratio": "16:9"              # 可选：宽高比
}
```

#### 6. PPT Generation

```python
{
    "title": "报告标题",                # 必需：标题
    "style": "business",                # 可选：风格
    "outline": [...],                   # 必需：大纲
    "aspect_ratio": "16:9"              # 可选：宽高比
}
```

#### 7. Chart Visualization

```python
{
    "chart_type": "bar_chart",          # 必需：图表类型
    "data": {...},                      # 必需：图表数据
    "title": "图表标题",                # 可选：标题
    "theme": "default",                 # 可选：主题
    "style": {...}                      # 可选：样式配置
}
```

#### 8. Coding Agent

```python
{
    "task": "创建一个 Flask API",        # 必需：任务描述
    "language": "python",               # 可选：编程语言
    "workdir": "/path/to/project"       # 可选：工作目录
}
```

#### 9. Frontend Design

```python
{
    "description": "创建一个登录页面",   # 必需：设计描述
    "framework": "react",               # 可选：框架
    "style": "minimal",                 # 可选：风格
    "output_dir": "/path/to/output"     # 可选：输出目录
}
```

#### 10. Whisper

```python
{
    "audio_path": "/path/to/audio.mp3", # 必需：音频文件路径
    "model": "medium",                  # 可选：Whisper 模型
    "output_format": "txt",             # 可选：输出格式
    "language": "zh"                    # 可选：语言
}
```

#### 11. PDF

```python
{
    "pdf_path": "/path/to/file.pdf",    # 必需：PDF 文件路径
    "page": 1,                          # 必需：页码
    "instruction": "修改标题为'新标题'",  # 必需：编辑指令
    "output_path": "/path/to/output.pdf" # 可选：输出路径
}
```

## 🔧 扩展指南

### 添加新 Skill

1. **在 `skills_external/` 创建 Skill 目录**
   ```bash
   mkdir skills_external/new-skill
   cp -r /path/to/skill/* skills_external/new-skill/
   ```

2. **创建节点适配器**
   ```python
   # src/nodes/skill_nodes/new_skill_node.py
   from .base_node import BaseNode, NodeResult, NodeStatus
   
   class NewSkillNode(BaseNode):
       async def execute(self, context: Dict[str, Any]) -> NodeResult:
           # 实现技能逻辑
           pass
       
       def get_schema(self) -> Dict[str, Any]:
           # 返回输入输出 schema
           pass
   ```

3. **注册到执行器**
   ```python
   # src/skill_executor.py
   from .nodes.skill_nodes.new_skill_node import NewSkillNode
   
   class SkillType(Enum):
       NEW_SKILL = "new_skill"
   
   def _register_default_skills(self):
       self._nodes[SkillType.NEW_SKILL] = NewSkillNode()
   ```

4. **更新文档**
   更新本文档，添加新 Skill 的说明和示例。

### 创建自定义工作流

```python
from agentm.src.skill_executor import SkillExecutor, SkillType

class CustomWorkflow:
    def __init__(self, executor: SkillExecutor):
        self.executor = executor
    
    async def run(self, **kwargs):
        # Step 1: 调用技能 A
        result_a = await self.executor.execute(SkillType.WEATHER, {...})
        
        # Step 2: 基于结果 A 调用技能 B
        result_b = await self.executor.execute(SkillType.CHART_VISUALIZATION, {...})
        
        return {"step1": result_a, "step2": result_b}
```

## 📊 性能优化

### 1. 启用缓存

```python
executor = SkillExecutor(configs=[
    SkillConfig(
        skill_type=SkillType.DEEP_RESEARCH,
        cache_enabled=True,
        cache_ttl=3600  # 1 小时
    )
])
```

### 2. 批量并行执行

```python
# 并行执行多个独立任务
results = await executor.execute_batch(executions, parallel=True)
```

### 3. 调整超时时间

```python
SkillConfig(
    skill_type=SkillType.VIDEO_GENERATION,
    timeout=600  # 视频生成需要更长时间
)
```

## 🧪 测试

```bash
# 运行示例工作流
cd /home/liyongxin/.openclaw/workspace/agentm
python workflows/examples/skill_workflows.py

# 运行单元测试
pytest src/nodes/skill_nodes/ -v
pytest workflows/examples/ -v
```

## 📝 最佳实践

1. **始终检查执行状态**
   ```python
   if result.status == NodeStatus.COMPLETED:
       # 处理成功结果
   else:
       # 处理错误
   ```

2. **合理设置超时**
   - 天气查询：30 秒
   - 数据分析：300 秒
   - 视频生成：600 秒

3. **使用缓存减少重复调用**
   ```python
   result = await executor.execute(..., use_cache=True)
   ```

4. **批量执行时优先使用并行**
   ```python
   results = await executor.execute_batch(..., parallel=True)
   ```

5. **记录执行历史用于调试**
   ```python
   history = executor.get_execution_history(limit=50)
   ```

## 🐛 故障排查

### 常见问题

1. **技能未找到**
   - 检查 Skill 是否正确注册到 `SkillExecutor`
   - 确认 `SkillType` 枚举值正确

2. **执行超时**
   - 增加 `timeout` 配置
   - 检查外部依赖（API、CLI 工具）是否可用

3. **缓存未命中**
   - 确认 `cache_enabled=True`
   - 检查输入参数是否完全相同

4. **CLI 工具未找到**
   - 安装对应的 CLI 工具（如 `whisper`, `nano-pdf`）
   - 确认 PATH 环境变量配置正确

## 📚 相关资源

- [Weather Skill 文档](../../skills_external/weather/SKILL.md)
- [Data Analysis Skill 文档](../../skills_external/data-analysis/SKILL.md)
- [Deep Research Skill 文档](../../skills_external/deep-research/SKILL.md)
- [Image Generation Skill 文档](../../skills_external/image-generation/SKILL.md)
- [PPT Generation Skill 文档](../../skills_external/ppt-generation/SKILL.md)

## 📄 许可证

MIT License
