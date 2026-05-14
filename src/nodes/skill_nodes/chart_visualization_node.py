"""
Chart Visualization Node - 图表可视化节点

集成 chart-visualization 技能，提供数据可视化能力。
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


class ChartVisualizationNode(BaseNode):
    """图表可视化节点"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("chart_visualization", config)
        self._default_theme = config.get("theme", "default") if config else "default"
        self._script_path = config.get(
            "script_path",
            "/home/liyongxin/.openclaw/workspace/agentm/skills_external/chart-visualization/scripts/generate.js"
        ) if config else "/home/liyongxin/.openclaw/workspace/agentm/skills_external/chart-visualization/scripts/generate.js"
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """
        执行图表生成
        
        Args:
            context: 执行上下文，包含:
                - chart_type: 图表类型
                - data: 图表数据
                - title: 图表标题
                - theme: 主题
                - style: 样式配置
                - output_path: 输出路径
        
        Returns:
            NodeResult: 图表生成结果
        """
        try:
            chart_type = context.get("chart_type")
            data = context.get("data")
            title = context.get("title", "")
            theme = context.get("theme", self._default_theme)
            style = context.get("style", {})
            output_path = context.get("output_path")
            
            if not chart_type:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    error="缺少必需参数：chart_type",
                    node_name=self.name
                )
            
            if not data:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    error="缺少必需参数：data",
                    node_name=self.name
                )
            
            # 调用 chart-visualization 技能
            result = await self._generate_chart(
                chart_type=chart_type,
                data=data,
                title=title,
                theme=theme,
                style=style,
                output_path=output_path
            )
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                output=result,
                node_name=self.name
            )
        
        except Exception as e:
            logger.error(f"图表生成失败：{e}")
            return NodeResult(
                status=NodeStatus.FAILED,
                error=str(e),
                node_name=self.name
            )
    
    async def _generate_chart(
        self,
        chart_type: str,
        data: Any,
        title: str,
        theme: str,
        style: Dict[str, Any],
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成图表
        
        使用 chart-visualization 脚本
        """
        import subprocess
        
        # 构建 payload
        payload = {
            "tool": f"generate_{chart_type}",
            "args": {
                "data": data,
                "title": title,
                "theme": theme,
                "style": style
            }
        }
        
        if output_path:
            payload["args"]["output"] = output_path
        
        # 构建命令
        cmd = ["node", self._script_path, json.dumps(payload)]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60  # 1 分钟超时
            )
            
            if result.returncode == 0:
                # 解析输出
                try:
                    output = json.loads(result.stdout)
                    return {
                        "status": "success",
                        "chart_url": output.get("url"),
                        "chart_spec": output.get("spec", payload["args"]),
                        "chart_type": chart_type
                    }
                except json.JSONDecodeError:
                    return {
                        "status": "success",
                        "raw_output": result.stdout,
                        "chart_type": chart_type
                    }
            else:
                raise RuntimeError(f"图表生成失败：{result.stderr}")
        
        except subprocess.TimeoutExpired:
            raise RuntimeError("图表生成超时（1 分钟）")
        except FileNotFoundError:
            raise RuntimeError("Node.js 不可用或未安装 chart-visualization 依赖")
    
    def get_schema(self) -> Dict[str, Any]:
        """返回节点输入输出 schema"""
        return {
            "inputs": {
                "chart_type": {
                    "type": "string",
                    "required": True,
                    "description": "图表类型",
                    "enum": [
                        "line_chart", "area_chart", "bar_chart", "column_chart",
                        "pie_chart", "scatter_chart", "histogram", "treemap",
                        "sankey_chart", "venn_chart", "radar_chart", "funnel_chart",
                        "liquid_chart", "word_cloud", "boxplot", "violin",
                        "district_map", "pin_map", "path_map",
                        "organization_chart", "mind_map", "network_graph",
                        "flow_diagram", "fishbone_diagram", "spreadsheet",
                        "dual_axes_chart"
                    ]
                },
                "data": {
                    "type": ["array", "object"],
                    "required": True,
                    "description": "图表数据"
                },
                "title": {
                    "type": "string",
                    "required": False,
                    "description": "图表标题"
                },
                "theme": {
                    "type": "string",
                    "required": False,
                    "default": "default",
                    "description": "图表主题"
                },
                "style": {
                    "type": "object",
                    "required": False,
                    "description": "样式配置"
                },
                "output_path": {
                    "type": "string",
                    "required": False,
                    "description": "输出文件路径"
                }
            },
            "outputs": {
                "chart_result": {"type": "object", "description": "图表生成结果"}
            }
        }
