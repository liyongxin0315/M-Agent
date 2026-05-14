"""
Variable System - 变量系统

提供变量作用域管理和模板语法支持。
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from jinja2 import Template, TemplateError

logger = logging.getLogger(__name__)


class VariableScope(Enum):
    """变量作用域"""
    GLOBAL = "global"  # 全局变量
    WORKFLOW = "workflow"  # 工作流变量
    NODE = "node"  # 节点变量
    TEMP = "temp"  # 临时变量


@dataclass
class Variable:
    """变量定义"""
    name: str
    value: Any
    scope: VariableScope = VariableScope.TEMP
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    is_readonly: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "value": self.value,
            "scope": self.scope.value,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_readonly": self.is_readonly
        }


class VariableContext:
    """变量上下文"""
    
    def __init__(self, parent: Optional["VariableContext"] = None):
        self._variables: Dict[str, Variable] = {}
        self._parent = parent
    
    def set(
        self,
        name: str,
        value: Any,
        scope: VariableScope = VariableScope.TEMP,
        description: str = "",
        is_readonly: bool = False
    ) -> Variable:
        """设置变量"""
        if name in self._variables:
            existing = self._variables[name]
            if existing.is_readonly:
                raise ValueError(f"变量 {name} 是只读的，无法修改")
            var = Variable(
                name=name,
                value=value,
                scope=scope,
                description=description,
                created_at=existing.created_at,
                updated_at=datetime.now(),
                is_readonly=is_readonly
            )
        else:
            var = Variable(
                name=name,
                value=value,
                scope=scope,
                description=description,
                is_readonly=is_readonly
            )
        
        self._variables[name] = var
        logger.debug(f"设置变量：{name} = {value}")
        return var
    
    def get(self, name: str, default: Any = None) -> Any:
        """获取变量值"""
        if name in self._variables:
            return self._variables[name].value
        
        if self._parent:
            return self._parent.get(name, default)
        
        return default
    
    def get_variable(self, name: str) -> Optional[Variable]:
        """获取变量对象"""
        if name in self._variables:
            return self._variables[name]
        
        if self._parent:
            return self._parent.get_variable(name)
        
        return None
    
    def delete(self, name: str) -> bool:
        """删除变量"""
        if name in self._variables:
            if self._variables[name].is_readonly:
                raise ValueError(f"变量 {name} 是只读的，无法删除")
            del self._variables[name]
            logger.debug(f"删除变量：{name}")
            return True
        return False
    
    def has(self, name: str) -> bool:
        """检查变量是否存在"""
        if name in self._variables:
            return True
        if self._parent:
            return self._parent.has(name)
        return False
    
    def all(self) -> Dict[str, Any]:
        """获取所有变量值"""
        result = {}
        
        if self._parent:
            result.update(self._parent.all())
        
        result.update({name: var.value for name, var in self._variables.items()})
        return result
    
    def all_variables(self) -> Dict[str, Variable]:
        """获取所有变量对象"""
        result = {}
        
        if self._parent:
            result.update(self._parent.all_variables())
        
        result.update(self._variables)
        return result
    
    def child(self) -> "VariableContext":
        """创建子上下文"""
        return VariableContext(parent=self)
    
    def clear(self, scope: Optional[VariableScope] = None) -> int:
        """清除变量"""
        if scope is None:
            count = len(self._variables)
            self._variables.clear()
            return count
        
        to_delete = [
            name for name, var in self._variables.items()
            if var.scope == scope
        ]
        for name in to_delete:
            del self._variables[name]
        return len(to_delete)


class TemplateEngine:
    """模板引擎"""
    
    def __init__(self, context: VariableContext):
        self.context = context
    
    def render(self, template_str: str) -> str:
        """渲染模板字符串"""
        if not isinstance(template_str, str):
            return template_str
        
        if "{{" not in template_str and "{%" not in template_str:
            return template_str
        
        try:
            template = Template(template_str)
            variables = self.context.all()
            return template.render(**variables)
        except TemplateError as e:
            logger.error(f"模板渲染失败：{e}")
            return template_str
    
    def render_object(self, obj: Any) -> Any:
        """渲染对象（递归处理）"""
        if isinstance(obj, str):
            return self.render(obj)
        elif isinstance(obj, dict):
            return {
                self.render(key): self.render_object(value)
                for key, value in obj.items()
            }
        elif isinstance(obj, list):
            return [self.render_object(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self.render_object(item) for item in obj)
        else:
            return obj


class VariableSystem:
    """变量系统"""
    
    def __init__(self):
        self.global_context = VariableContext()
        self._workflow_contexts: Dict[str, VariableContext] = {}
        self.template_engine: Optional[TemplateEngine] = None
    
    def create_workflow_context(self, workflow_id: str) -> VariableContext:
        """创建工作流上下文"""
        context = VariableContext(parent=self.global_context)
        self._workflow_contexts[workflow_id] = context
        self.template_engine = TemplateEngine(context)
        logger.info(f"创建工作流上下文：{workflow_id}")
        return context
    
    def get_workflow_context(self, workflow_id: str) -> Optional[VariableContext]:
        """获取工作流上下文"""
        return self._workflow_contexts.get(workflow_id)
    
    def delete_workflow_context(self, workflow_id: str) -> bool:
        """删除工作流上下文"""
        if workflow_id in self._workflow_contexts:
            del self._workflow_contexts[workflow_id]
            logger.info(f"删除工作流上下文：{workflow_id}")
            return True
        return False
    
    def set_global(self, name: str, value: Any, **kwargs) -> Variable:
        """设置全局变量"""
        return self.global_context.set(name, value, VariableScope.GLOBAL, **kwargs)
    
    def get_global(self, name: str, default: Any = None) -> Any:
        """获取全局变量"""
        return self.global_context.get(name, default)
    
    def render(self, template_str: str) -> str:
        """渲染模板"""
        if self.template_engine:
            return self.template_engine.render(template_str)
        return template_str
    
    def render_object(self, obj: Any) -> Any:
        """渲染对象"""
        if self.template_engine:
            return self.template_engine.render_object(obj)
        return obj
    
    def get_all_variables(self, workflow_id: Optional[str] = None) -> Dict[str, Any]:
        """获取所有变量"""
        if workflow_id and workflow_id in self._workflow_contexts:
            return self._workflow_contexts[workflow_id].all()
        return self.global_context.all()


# 便捷函数
def create_variable_system() -> VariableSystem:
    """创建变量系统"""
    return VariableSystem()
