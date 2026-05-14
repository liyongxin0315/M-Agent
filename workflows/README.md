# AgentM Workflows - 工作流模板库

## 目录
- 数据同步工作流
- 定时报告工作流
- API 集成工作流
- AI 辅助工作流

## 依赖安装
```bash
pip install aioschedule pyyaml
```

## 使用方式
```python
from agentm.workflows import DataSyncWorkflow, ScheduledReportWorkflow

# 创建工作流实例
workflow = DataSyncWorkflow(config={...})

# 执行工作流
await workflow.execute()
```
