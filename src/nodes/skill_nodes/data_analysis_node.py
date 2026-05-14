"""
Data Analysis Node - 数据分析节点

集成 data-analysis 技能，提供数据分析能力。
"""

import logging
from typing import Any, Dict, List, Optional

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


class DataAnalysisNode(BaseNode):
    """数据分析节点"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("data_analysis", config)
        self._supported_formats = ["csv", "excel", "json", "parquet"]
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """
        执行数据分析
        
        Args:
            context: 执行上下文，包含:
                - data_path: 数据文件路径
                - analysis_type: 分析类型 (descriptive, exploratory, statistical)
                - columns: 要分析的列
                - output_format: 输出格式
        
        Returns:
            NodeResult: 分析结果
        """
        try:
            data_path = context.get("data_path")
            analysis_type = context.get("analysis_type", "descriptive")
            columns = context.get("columns")
            output_format = context.get("output_format", "json")
            
            if not data_path:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    error="缺少必需参数：data_path",
                    node_name=self.name
                )
            
            # 调用 data-analysis 技能
            result = await self._run_analysis(
                data_path=data_path,
                analysis_type=analysis_type,
                columns=columns,
                output_format=output_format
            )
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                output=result,
                node_name=self.name
            )
        
        except Exception as e:
            logger.error(f"数据分析失败：{e}")
            return NodeResult(
                status=NodeStatus.FAILED,
                error=str(e),
                node_name=self.name
            )
    
    async def _run_analysis(
        self,
        data_path: str,
        analysis_type: str,
        columns: Optional[List[str]] = None,
        output_format: str = "json"
    ) -> Dict[str, Any]:
        """
        运行数据分析
        
        通过 clawhub 调用 data-analysis 技能
        """
        import subprocess
        import json
        
        # 构建分析命令
        cmd = ["clawhub", "run", "data-analysis"]
        cmd.extend(["--input", data_path])
        cmd.extend(["--type", analysis_type])
        
        if columns:
            cmd.extend(["--columns", ",".join(columns)])
        
        cmd.extend(["--output-format", output_format])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 分钟超时
            )
            
            if result.returncode == 0:
                return json.loads(result.stdout) if result.stdout else {"status": "success"}
            else:
                raise RuntimeError(f"分析失败：{result.stderr}")
        
        except subprocess.TimeoutExpired:
            raise RuntimeError("分析超时（5 分钟）")
        except FileNotFoundError:
            # clawhub 不可用时，使用 pandas 进行基础分析
            return await self._fallback_analysis(data_path, analysis_type, columns)
    
    async def _fallback_analysis(
        self,
        data_path: str,
        analysis_type: str,
        columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        降级分析（当 clawhub 不可用时）
        """
        import pandas as pd
        from pathlib import Path
        
        path = Path(data_path)
        if not path.exists():
            raise FileNotFoundError(f"数据文件不存在：{data_path}")
        
        # 读取数据
        if path.suffix == ".csv":
            df = pd.read_csv(path)
        elif path.suffix in [".xlsx", ".xls"]:
            df = pd.read_excel(path)
        elif path.suffix == ".json":
            df = pd.read_json(path)
        else:
            raise ValueError(f"不支持的文件格式：{path.suffix}")
        
        # 选择列
        if columns:
            df = df[columns]
        
        # 执行分析
        result = {
            "shape": {"rows": len(df), "columns": len(df.columns)},
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "missing_values": df.isnull().sum().to_dict(),
        }
        
        if analysis_type in ["descriptive", "exploratory"]:
            result["describe"] = df.describe(include="all").to_dict()
            result["correlations"] = df.corr(numeric_only=True).to_dict()
        
        return result
    
    def get_schema(self) -> Dict[str, Any]:
        """返回节点输入输出 schema"""
        return {
            "inputs": {
                "data_path": {"type": "string", "required": True, "description": "数据文件路径"},
                "analysis_type": {
                    "type": "string",
                    "required": False,
                    "default": "descriptive",
                    "enum": ["descriptive", "exploratory", "statistical"]
                },
                "columns": {"type": "array", "items": {"type": "string"}, "required": False},
                "output_format": {
                    "type": "string",
                    "required": False,
                    "default": "json",
                    "enum": ["json", "csv", "html"]
                }
            },
            "outputs": {
                "analysis_result": {"type": "object", "description": "分析结果"}
            }
        }
