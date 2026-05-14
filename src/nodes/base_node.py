"""
Base Node - 节点基类

定义所有技能节点的通用接口和抽象基类。
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class NodeStatus(Enum):
    """节点状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class NodeResult:
    """节点执行结果"""
    status: NodeStatus
    node_name: str
    output: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "status": self.status.value,
            "node_name": self.node_name,
            "output": self._serialize_output(self.output),
            "error": self.error,
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }
    
    def _serialize_output(self, output: Any) -> Any:
        """序列化输出"""
        if output is None:
            return None
        elif isinstance(output, (str, int, float, bool, list, dict)):
            return output
        else:
            return str(output)[:1000]  # 限制长度


class BaseNode(ABC):
    """节点基类"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        self._status = NodeStatus.PENDING
        self._last_result: Optional[NodeResult] = None
    
    @property
    def status(self) -> NodeStatus:
        """获取节点状态"""
        return self._status
    
    @property
    def last_result(self) -> Optional[NodeResult]:
        """获取上次执行结果"""
        return self._last_result
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """
        执行节点
        
        Args:
            context: 执行上下文
        
        Returns:
            NodeResult: 执行结果
        """
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """
        获取节点 schema
        
        Returns:
            Dict: 输入输出 schema 定义
        """
        pass
    
    async def run(self, context: Dict[str, Any]) -> NodeResult:
        """
        运行节点（带状态管理）
        
        Args:
            context: 执行上下文
        
        Returns:
            NodeResult: 执行结果
        """
        import time
        
        self._status = NodeStatus.RUNNING
        start_time = time.time()
        
        try:
            result = await self.execute(context)
            result.duration = time.time() - start_time
            self._last_result = result
            self._status = result.status
            return result
        
        except Exception as e:
            duration = time.time() - start_time
            result = NodeResult(
                status=NodeStatus.FAILED,
                node_name=self.name,
                error=str(e),
                duration=duration
            )
            self._last_result = result
            self._status = NodeStatus.FAILED
            logger.error(f"节点 {self.name} 执行失败：{e}")
            return result
    
    def validate_input(self, context: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        验证输入
        
        Args:
            context: 执行上下文
        
        Returns:
            tuple: (是否有效，错误信息)
        """
        schema = self.get_schema()
        inputs = schema.get("inputs", {})
        
        for param_name, param_schema in inputs.items():
            if param_schema.get("required", False) and param_name not in context:
                return False, f"缺少必需参数：{param_name}"
        
        return True, None
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', status={self.status.value})"
