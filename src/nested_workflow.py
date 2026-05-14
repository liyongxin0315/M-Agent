"""
Sub-Workflow Support - 子工作流支持

提供工作流嵌套调用能力。
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .variable_system import VariableContext, VariableSystem

logger = logging.getLogger(__name__)


@dataclass
class SubWorkflowConfig:
    """子工作流配置"""
    workflow_id: str
    workflow_name: str
    input_mapping: Dict[str, str] = field(default_factory=dict)
    output_mapping: Dict[str, str] = field(default_factory=dict)
    timeout: Optional[float] = None
    retry_count: int = 0
    retry_delay: float = 1.0
    skip_on_error: bool = False


class SubWorkflowExecutor:
    """子工作流执行器"""
    
    def __init__(
        self,
        workflow_registry: "WorkflowRegistry",
        variable_system: VariableSystem
    ):
        self.workflow_registry = workflow_registry
        self.variable_system = variable_system
    
    async def execute(
        self,
        config: SubWorkflowConfig,
        parent_context: VariableContext,
        execution_id: str
    ) -> Dict[str, Any]:
        """执行子工作流"""
        logger.info(f"开始执行子工作流：{config.workflow_name} (ID: {config.workflow_id})")
        
        workflow_class = self.workflow_registry.get_workflow(config.workflow_id)
        if not workflow_class:
            raise ValueError(f"未找到工作流：{config.workflow_id}")
        
        child_context = self.variable_system.create_workflow_context(execution_id)
        
        input_data = self._prepare_input(config.input_mapping, parent_context)
        for key, value in input_data.items():
            child_context.set(key, value, description=f"来自父工作流的输入：{key}")
        
        try:
            workflow_instance = workflow_class(config={"_execution_id": execution_id})
            
            if hasattr(workflow_instance, 'execute_with_context'):
                result = await workflow_instance.execute_with_context(child_context)
            else:
                result = await workflow_instance.execute()
            
            output_data = self._extract_output(config.output_mapping, child_context, result)
            
            logger.info(f"子工作流执行完成：{config.workflow_name}")
            return output_data
        
        except Exception as e:
            logger.error(f"子工作流执行失败：{config.workflow_name} - {e}")
            
            if config.skip_on_error:
                logger.warning(f"跳过子工作流错误：{config.workflow_name}")
                return {"_skipped": True, "_error": str(e)}
            
            if config.retry_count > 0:
                return await self._retry_execute(config, parent_context, execution_id)
            
            raise
    
    def _prepare_input(
        self,
        input_mapping: Dict[str, str],
        parent_context: VariableContext
    ) -> Dict[str, Any]:
        """准备输入数据"""
        input_data = {}
        
        for target_key, source_expr in input_mapping.items():
            value = self._resolve_expression(source_expr, parent_context)
            input_data[target_key] = value
            logger.debug(f"输入映射：{target_key} = {value}")
        
        return input_data
    
    def _extract_output(
        self,
        output_mapping: Dict[str, str],
        child_context: VariableContext,
        workflow_result: Any
    ) -> Dict[str, Any]:
        """提取输出数据"""
        output_data = {}
        
        if output_mapping:
            for target_key, source_key in output_mapping.items():
                value = child_context.get(source_key)
                if value is not None:
                    output_data[target_key] = value
                    logger.debug(f"输出映射：{target_key} = {value}")
        else:
            output_data = child_context.all()
        
        if workflow_result:
            output_data["_result"] = workflow_result
        
        return output_data
    
    def _resolve_expression(self, expr: str, context: VariableContext) -> Any:
        """解析表达式"""
        if not isinstance(expr, str):
            return expr
        
        if expr.startswith("{{") and expr.endswith("}}"):
            var_name = expr[2:-2].strip()
            return context.get(var_name)
        
        return expr
    
    async def _retry_execute(
        self,
        config: SubWorkflowConfig,
        parent_context: VariableContext,
        execution_id: str
    ) -> Dict[str, Any]:
        """重试执行"""
        for attempt in range(config.retry_count):
            logger.info(f"重试子工作流：{config.workflow_name} (尝试 {attempt + 1}/{config.retry_count})")
            await asyncio.sleep(config.retry_delay * (attempt + 1))
            
            try:
                return await self.execute(config, parent_context, execution_id)
            except Exception as e:
                if attempt == config.retry_count - 1:
                    raise
                continue
        
        return {"_skipped": True, "_error": "重试失败"}


class WorkflowRegistry:
    """工作流注册表"""
    
    def __init__(self):
        self._workflows: Dict[str, type] = {}
    
    def register(self, workflow_id: str, workflow_class: type) -> None:
        """注册工作流"""
        self._workflows[workflow_id] = workflow_class
        logger.info(f"注册工作流：{workflow_id} -> {workflow_class.__name__}")
    
    def unregister(self, workflow_id: str) -> bool:
        """注销工作流"""
        if workflow_id in self._workflows:
            del self._workflows[workflow_id]
            logger.info(f"注销工作流：{workflow_id}")
            return True
        return False
    
    def get_workflow(self, workflow_id: str) -> Optional[type]:
        """获取工作流类"""
        return self._workflows.get(workflow_id)
    
    def list_workflows(self) -> Dict[str, str]:
        """列出所有工作流"""
        return {
            workflow_id: cls.__name__
            for workflow_id, cls in self._workflows.items()
        }
    
    def has_workflow(self, workflow_id: str) -> bool:
        """检查工作流是否存在"""
        return workflow_id in self._workflows


class NestedWorkflowEngine:
    """嵌套工作流引擎"""
    
    def __init__(self, variable_system: VariableSystem):
        self.variable_system = variable_system
        self.workflow_registry = WorkflowRegistry()
        self.subworkflow_executor: Optional[SubWorkflowExecutor] = None
    
    def initialize(self) -> None:
        """初始化"""
        self.subworkflow_executor = SubWorkflowExecutor(
            self.workflow_registry,
            self.variable_system
        )
    
    def register_workflow(self, workflow_id: str, workflow_class: type) -> None:
        """注册工作流"""
        self.workflow_registry.register(workflow_id, workflow_class)
    
    async def execute_subworkflow(
        self,
        workflow_id: str,
        input_data: Dict[str, Any],
        parent_context: VariableContext
    ) -> Dict[str, Any]:
        """执行子工作流"""
        if not self.subworkflow_executor:
            self.initialize()
        
        execution_id = f"{workflow_id}_{int(time.time() * 1000)}"
        
        config = SubWorkflowConfig(
            workflow_id=workflow_id,
            workflow_name=workflow_id,
            input_mapping={k: f"{{{{{k}}}}}" for k in input_data.keys()}
        )
        
        for key, value in input_data.items():
            parent_context.set(key, value)
        
        return await self.subworkflow_executor.execute(
            config,
            parent_context,
            execution_id
        )


def create_nested_engine() -> NestedWorkflowEngine:
    """创建嵌套工作流引擎"""
    from .variable_system import create_variable_system
    variable_system = create_variable_system()
    engine = NestedWorkflowEngine(variable_system)
    engine.initialize()
    return engine
