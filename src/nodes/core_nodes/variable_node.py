"""
Variable Node - 变量操作节点

设置、获取、删除变量。
"""

import logging
from typing import Any, Dict, List, Optional

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


class VariableNode(BaseNode):
    """变量操作节点"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.operation = config.get("operation", "set") if config else "set"
        self.variables = config.get("variables", {}) if config else {}
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """执行变量操作"""
        try:
            operation = context.get("operation", self.operation)
            variables = context.get("variables", self.variables)
            
            if operation == "set":
                return self._set_variables(context, variables)
            elif operation == "get":
                return self._get_variables(context, variables)
            elif operation == "delete":
                return self._delete_variables(context, variables)
            elif operation == "list":
                return self._list_variables(context)
            else:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    node_name=self.name,
                    error=f"未知操作：{operation}"
                )
        
        except Exception as e:
            return NodeResult(
                status=NodeStatus.FAILED,
                node_name=self.name,
                error=f"变量操作失败：{e}"
            )
    
    def _set_variables(
        self,
        context: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> NodeResult:
        """设置变量"""
        set_vars = {}
        
        for key, value in variables.items():
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                ref_key = value[2:-2].strip()
                value = context.get(ref_key, value)
            
            context[key] = value
            set_vars[key] = value
            logger.debug(f"设置变量：{key} = {value}")
        
        return NodeResult(
            status=NodeStatus.COMPLETED,
            node_name=self.name,
            output={
                "operation": "set",
                "variables": set_vars,
                "count": len(set_vars)
            }
        )
    
    def _get_variables(
        self,
        context: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> NodeResult:
        """获取变量"""
        keys = variables.get("keys", [])
        
        if not keys:
            keys = list(context.keys())
        
        result = {}
        for key in keys:
            if key in context:
                result[key] = context[key]
        
        return NodeResult(
            status=NodeStatus.COMPLETED,
            node_name=self.name,
            output={
                "operation": "get",
                "variables": result
            }
        )
    
    def _delete_variables(
        self,
        context: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> NodeResult:
        """删除变量"""
        keys = variables.get("keys", [])
        deleted = []
        
        for key in keys:
            if key in context and not key.startswith("_"):
                del context[key]
                deleted.append(key)
                logger.debug(f"删除变量：{key}")
        
        return NodeResult(
            status=NodeStatus.COMPLETED,
            node_name=self.name,
            output={
                "operation": "delete",
                "deleted": deleted,
                "count": len(deleted)
            }
        )
    
    def _list_variables(self, context: Dict[str, Any]) -> NodeResult:
        """列出变量"""
        keys = [k for k in context.keys() if not k.startswith("_")]
        
        return NodeResult(
            status=NodeStatus.COMPLETED,
            node_name=self.name,
            output={
                "operation": "list",
                "variables": keys,
                "count": len(keys)
            }
        )
    
    def get_schema(self) -> Dict[str, Any]:
        """获取节点 schema"""
        return {
            "name": "variable",
            "description": "变量操作",
            "inputs": {
                "operation": {
                    "type": "string",
                    "required": True,
                    "enum": ["set", "get", "delete", "list"],
                    "description": "操作类型"
                },
                "variables": {
                    "type": "object",
                    "required": False,
                    "description": "变量配置"
                }
            },
            "outputs": {
                "operation": {
                    "type": "string",
                    "description": "执行的操作"
                },
                "variables": {
                    "type": "any",
                    "description": "操作结果"
                },
                "count": {
                    "type": "number",
                    "description": "操作数量"
                }
            }
        }


class SubWorkflowNode(BaseNode):
    """子工作流调用节点"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.workflow_id = config.get("workflow_id", "") if config else ""
        self.input_mapping = config.get("input_mapping", {}) if config else {}
        self.output_mapping = config.get("output_mapping", {}) if config else {}
        self._workflow_registry = None
    
    def set_workflow_registry(self, registry) -> "SubWorkflowNode":
        """设置工作流注册表"""
        self._workflow_registry = registry
        return self
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """执行子工作流"""
        try:
            if not self._workflow_registry:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    node_name=self.name,
                    error="未设置工作流注册表"
                )
            
            workflow_class = self._workflow_registry.get_workflow(self.workflow_id)
            
            if not workflow_class:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    node_name=self.name,
                    error=f"未找到工作流：{self.workflow_id}"
                )
            
            input_data = self._prepare_input(context)
            
            workflow_instance = workflow_class(config=input_data)
            
            if hasattr(workflow_instance, 'execute_with_context'):
                result = await workflow_instance.execute_with_context(context)
            else:
                result = await workflow_instance.execute()
            
            output = self._extract_output(result, context)
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                node_name=self.name,
                output=output
            )
        
        except Exception as e:
            return NodeResult(
                status=NodeStatus.FAILED,
                node_name=self.name,
                error=f"子工作流执行失败：{e}"
            )
    
    def _prepare_input(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """准备输入"""
        input_data = {}
        
        for target_key, source_expr in self.input_mapping.items():
            if source_expr.startswith("{{") and source_expr.endswith("}}"):
                source_key = source_expr[2:-2].strip()
                value = context.get(source_key)
            else:
                value = source_expr
            
            input_data[target_key] = value
        
        return input_data
    
    def _extract_output(
        self,
        result: Any,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """提取输出"""
        if self.output_mapping:
            output = {}
            for target_key, source_key in self.output_mapping.items():
                if isinstance(result, dict) and source_key in result:
                    output[target_key] = result[source_key]
                else:
                    output[target_key] = context.get(source_key)
            return output
        
        if isinstance(result, dict):
            return result
        
        return {"result": result}
    
    def get_schema(self) -> Dict[str, Any]:
        """获取节点 schema"""
        return {
            "name": "subworkflow",
            "description": "子工作流调用",
            "inputs": {
                "workflow_id": {
                    "type": "string",
                    "required": True,
                    "description": "工作流 ID"
                },
                "input_mapping": {
                    "type": "object",
                    "required": False,
                    "description": "输入映射"
                }
            },
            "outputs": {
                "result": {
                    "type": "any",
                    "description": "工作流执行结果"
                }
            }
        }


class ErrorHandlerNode(BaseNode):
    """错误处理节点

    捕获和处理错误。
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.error_types = config.get("error_types", ["all"]) if config else ["all"]
        self.fallback_value = config.get("fallback_value") if config else None
        self.retry_count = config.get("retry_count", 0) if config else 0
        self.on_error_action = config.get("on_error_action", "continue") if config else "continue"
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """执行错误处理"""
        try:
            error = context.get("_error")
            error_type = context.get("_error_type", "unknown")
            
            if not error:
                return NodeResult(
                    status=NodeStatus.COMPLETED,
                    node_name=self.name,
                    output={"handled": False, "reason": "无错误"}
                )
            
            if "all" not in self.error_types and error_type not in self.error_types:
                return NodeResult(
                    status=NodeStatus.COMPLETED,
                    node_name=self.name,
                    output={"handled": False, "reason": f"错误类型不匹配：{error_type}"}
                )
            
            output = {
                "handled": True,
                "error": error,
                "error_type": error_type,
                "action": self.on_error_action
            }
            
            if self.fallback_value is not None:
                output["fallback_value"] = self.fallback_value
            
            if self.retry_count > 0:
                output["retry_count"] = self.retry_count
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                node_name=self.name,
                output=output
            )
        
        except Exception as e:
            return NodeResult(
                status=NodeStatus.FAILED,
                node_name=self.name,
                error=f"错误处理失败：{e}"
            )
    
    def get_schema(self) -> Dict[str, Any]:
        """获取节点 schema"""
        return {
            "name": "error_handler",
            "description": "错误处理",
            "inputs": {
                "error_types": {
                    "type": "array",
                    "required": False,
                    "default": ["all"],
                    "description": "要处理的错误类型"
                },
                "fallback_value": {
                    "type": "any",
                    "required": False,
                    "description": "降级值"
                },
                "retry_count": {
                    "type": "number",
                    "required": False,
                    "default": 0,
                    "description": "重试次数"
                },
                "on_error_action": {
                    "type": "string",
                    "required": False,
                    "default": "continue",
                    "enum": ["continue", "abort", "retry"],
                    "description": "错误处理动作"
                }
            },
            "outputs": {
                "handled": {
                    "type": "boolean",
                    "description": "是否处理了错误"
                },
                "error": {
                    "type": "string",
                    "description": "错误信息"
                },
                "fallback_value": {
                    "type": "any",
                    "description": "降级值"
                }
            }
        }
