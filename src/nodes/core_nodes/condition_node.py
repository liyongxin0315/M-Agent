"""
Condition Node - 条件判断节点

根据条件表达式决定执行路径。
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Union

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


class ConditionEvaluator:
    """条件评估器"""
    
    @staticmethod
    def evaluate(condition: str, context: Dict[str, Any]) -> bool:
        """评估条件"""
        try:
            safe_dict = ConditionEvaluator._create_safe_dict(context)
            return bool(eval(condition, {"__builtins__": {}}, safe_dict))
        except Exception as e:
            logger.error(f"条件评估失败：{e}")
            return False
    
    @staticmethod
    def _create_safe_dict(context: Dict[str, Any]) -> Dict[str, Any]:
        """创建安全字典"""
        safe_dict = {
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "sum": sum,
            "min": min,
            "max": max,
            "any": any,
            "all": all,
        }
        
        for key, value in context.items():
            if not key.startswith("_"):
                safe_dict[key] = value
        
        return safe_dict


class ConditionNode(BaseNode):
    """条件判断节点"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.conditions: List[Dict[str, Any]] = config.get("conditions", []) if config else []
        self.default_branch = config.get("default_branch", "else") if config else "else"
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """执行条件判断"""
        try:
            matched_branch = self._evaluate_conditions(context)
            
            output = {
                "matched_branch": matched_branch,
                "condition_result": True if matched_branch != "else" else False
            }
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                node_name=self.name,
                output=output
            )
        
        except Exception as e:
            return NodeResult(
                status=NodeStatus.FAILED,
                node_name=self.name,
                error=f"条件判断失败：{e}"
            )
    
    def _evaluate_conditions(self, context: Dict[str, Any]) -> str:
        """评估所有条件"""
        for condition_config in self.conditions:
            branch = condition_config.get("branch", "if")
            condition = condition_config.get("condition", "")
            
            if not condition:
                continue
            
            if ConditionEvaluator.evaluate(condition, context):
                logger.debug(f"条件匹配：{branch}")
                return branch
        
        logger.debug("无条件匹配，返回默认分支")
        return self.default_branch
    
    def add_condition(self, branch: str, condition: str) -> "ConditionNode":
        """添加条件"""
        self.conditions.append({
            "branch": branch,
            "condition": condition
        })
        return self
    
    def get_branches(self) -> List[str]:
        """获取所有分支"""
        branches = [cond["branch"] for cond in self.conditions]
        branches.append(self.default_branch)
        return branches
    
    def get_schema(self) -> Dict[str, Any]:
        """获取节点 schema"""
        return {
            "name": "condition",
            "description": "条件判断",
            "inputs": {
                "conditions": {
                    "type": "array",
                    "required": True,
                    "description": "条件列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "branch": {"type": "string", "description": "分支名称"},
                            "condition": {"type": "string", "description": "条件表达式"}
                        }
                    }
                },
                "default_branch": {
                    "type": "string",
                    "required": False,
                    "default": "else",
                    "description": "默认分支"
                }
            },
            "outputs": {
                "matched_branch": {
                    "type": "string",
                    "description": "匹配的分支"
                },
                "condition_result": {
                    "type": "boolean",
                    "description": "条件结果"
                }
            },
            "branches": self.get_branches()
        }
