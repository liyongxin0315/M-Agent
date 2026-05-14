"""
Data Analysis Workflow - 数据分析工作流示例

演示如何使用技能节点进行数据分析。
"""

import logging
from typing import Any, Dict, Optional

from agentm.workflows.workflow_engine import BaseWorkflow, WorkflowResult
from agentm.src.nodes.skill_nodes import DataAnalysisNode, ChartVisualizationNode

logger = logging.getLogger(__name__)


class DataAnalysisWorkflow(BaseWorkflow):
    """数据分析工作流"""
    
    def _setup_steps(self) -> None:
        """设置工作流步骤"""
        # 初始化技能节点
        self._analysis_node = DataAnalysisNode(self.config.get("analysis_config"))
        self._chart_node = ChartVisualizationNode(self.config.get("chart_config"))
        
        # 添加步骤
        self.engine.add_step(
            name="load_data",
            func=self._load_data,
            description="加载数据文件",
            retry_count=2
        )
        
        self.engine.add_step(
            name="analyze_data",
            func=self._analyze_data,
            description="执行数据分析",
            retry_count=1
        )
        
        self.engine.add_step(
            name="generate_charts",
            func=self._generate_charts,
            description="生成可视化图表",
            skip_on_error=True
        )
        
        self.engine.add_step(
            name="generate_report",
            func=self._generate_report,
            description="生成分析报告",
            retry_count=1
        )
    
    def _load_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """加载数据"""
        data_path = self.config.get("data_path")
        
        if not data_path:
            raise ValueError("缺少数据文件路径配置")
        
        logger.info(f"加载数据文件：{data_path}")
        
        # 验证文件存在
        from pathlib import Path
        path = Path(data_path)
        if not path.exists():
            raise FileNotFoundError(f"数据文件不存在：{data_path}")
        
        context["data_path"] = data_path
        context["data_loaded"] = True
        
        return {"status": "success", "path": data_path}
    
    async def _analyze_data(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """分析数据"""
        analysis_type = self.config.get("analysis_type", "descriptive")
        
        logger.info(f"执行数据分析：{analysis_type}")
        
        # 使用数据分析节点
        analysis_context = {
            "data_path": context["data_path"],
            "analysis_type": analysis_type,
            "columns": self.config.get("columns"),
            "output_format": "json"
        }
        
        result = await self._analysis_node.execute(analysis_context)
        
        if result.status.value == "failed":
            raise RuntimeError(f"数据分析失败：{result.error}")
        
        context["analysis_result"] = result.output
        return result.output
    
    async def _generate_charts(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成图表"""
        logger.info("生成可视化图表")
        
        analysis_result = context.get("analysis_result", {})
        output_dir = self.config.get("output_dir", "output/charts")
        
        # 根据分析结果生成图表
        chart_types = self.config.get("chart_types", ["line", "bar"])
        chart_paths = []
        
        for chart_type in chart_types:
            chart_context = {
                "data": analysis_result.get("describe", {}),
                "chart_type": chart_type,
                "title": f"Data Analysis - {chart_type.title()} Chart",
                "output_path": f"{output_dir}/{chart_type}_chart.png"
            }
            
            result = await self._chart_node.execute(chart_context)
            
            if result.status.value == "completed":
                chart_paths.append(result.output.get("output_path"))
        
        context["chart_paths"] = chart_paths
        return {"charts": chart_paths}
    
    def _generate_report(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成报告"""
        logger.info("生成分析报告")
        
        report = {
            "summary": {
                "data_path": context.get("data_path"),
                "analysis_completed": True,
                "charts_generated": len(context.get("chart_paths", []))
            },
            "analysis": context.get("analysis_result", {}),
            "charts": context.get("chart_paths", [])
        }
        
        # 保存报告
        output_path = self.config.get("report_path", "output/analysis_report.json")
        
        import json
        from pathlib import Path
        
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        context["report_path"] = output_path
        return {"report_path": output_path}
    
    def get_workflow_info(self) -> Dict[str, Any]:
        """获取工作流信息"""
        return {
            "name": "DataAnalysisWorkflow",
            "description": "数据分析工作流 - 从数据加载到分析、可视化和报告生成",
            "steps": [
                "load_data - 加载数据文件",
                "analyze_data - 执行数据分析",
                "generate_charts - 生成可视化图表",
                "generate_report - 生成分析报告"
            ],
            "config": self.config
        }


async def run_data_analysis(
    data_path: str,
    analysis_type: str = "descriptive",
    output_dir: str = "output",
    chart_types: Optional[list] = None
) -> WorkflowResult:
    """
    便捷函数：运行数据分析工作流
    
    Args:
        data_path: 数据文件路径
        analysis_type: 分析类型
        output_dir: 输出目录
        chart_types: 图表类型列表
    
    Returns:
        WorkflowResult: 执行结果
    """
    config = {
        "data_path": data_path,
        "analysis_type": analysis_type,
        "output_dir": output_dir,
        "chart_types": chart_types or ["line", "bar"],
        "report_path": f"{output_dir}/analysis_report.json"
    }
    
    workflow = DataAnalysisWorkflow(config)
    return await workflow.execute()
