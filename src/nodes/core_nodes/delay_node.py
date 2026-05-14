"""
Delay Node - 延时节点

延时或定时执行。
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


class DelayNode(BaseNode):
    """延时节点"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.delay_seconds = config.get("delay_seconds", 1.0) if config else 1.0
        self.until_time = config.get("until_time") if config else None
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """执行延时"""
        try:
            delay_seconds = context.get("delay_seconds", self.delay_seconds)
            until_time = context.get("until_time", self.until_time)
            
            if until_time:
                delay_seconds = self._calculate_delay_until(until_time)
            
            if delay_seconds <= 0:
                logger.debug("无需延时")
                return NodeResult(
                    status=NodeStatus.COMPLETED,
                    node_name=self.name,
                    output={"delayed": False, "delay_seconds": 0}
                )
            
            logger.info(f"延时 {delay_seconds} 秒")
            await asyncio.sleep(delay_seconds)
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                node_name=self.name,
                output={
                    "delayed": True,
                    "delay_seconds": delay_seconds,
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        except Exception as e:
            return NodeResult(
                status=NodeStatus.FAILED,
                node_name=self.name,
                error=f"延时失败：{e}"
            )
    
    def _calculate_delay_until(self, until_time: str) -> float:
        """计算到指定时间的延时"""
        try:
            if isinstance(until_time, str):
                target = datetime.fromisoformat(until_time)
            elif isinstance(until_time, datetime):
                target = until_time
            else:
                return 0
            
            now = datetime.now()
            delta = target - now
            
            if delta.total_seconds() <= 0:
                return 0
            
            return delta.total_seconds()
        
        except Exception as e:
            logger.error(f"计算延时失败：{e}")
            return self.delay_seconds
    
    def get_schema(self) -> Dict[str, Any]:
        """获取节点 schema"""
        return {
            "name": "delay",
            "description": "延时执行",
            "inputs": {
                "delay_seconds": {
                    "type": "number",
                    "required": False,
                    "default": 1.0,
                    "description": "延时秒数"
                },
                "until_time": {
                    "type": "string",
                    "required": False,
                    "description": "执行时间（ISO 8601 格式）"
                }
            },
            "outputs": {
                "delayed": {
                    "type": "boolean",
                    "description": "是否执行了延时"
                },
                "delay_seconds": {
                    "type": "number",
                    "description": "实际延时秒数"
                },
                "timestamp": {
                    "type": "string",
                    "description": "执行时间戳"
                }
            }
        }


class MergeNode(BaseNode):
    """合并节点

    合并多个输入数据。
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.merge_strategy = config.get("merge_strategy", "concat") if config else "concat"
        self.output_key = config.get("output_key", "merged") if config else "merged"
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """执行合并"""
        try:
            inputs = context.get("inputs", [])
            
            if not inputs:
                inputs = [v for k, v in context.items() if k.startswith("input_")]
            
            merged = self._merge_inputs(inputs)
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                node_name=self.name,
                output={
                    self.output_key: merged,
                    "count": len(inputs)
                }
            )
        
        except Exception as e:
            return NodeResult(
                status=NodeStatus.FAILED,
                node_name=self.name,
                error=f"合并失败：{e}"
            )
    
    def _merge_inputs(self, inputs: list) -> Any:
        """合并输入"""
        if not inputs:
            return []
        
        if self.merge_strategy == "concat":
            result = []
            for item in inputs:
                if isinstance(item, list):
                    result.extend(item)
                else:
                    result.append(item)
            return result
        
        elif self.merge_strategy == "merge_objects":
            result = {}
            for item in inputs:
                if isinstance(item, dict):
                    result.update(item)
            return result
        
        elif self.merge_strategy == "first":
            return inputs[0] if inputs else None
        
        elif self.merge_strategy == "last":
            return inputs[-1] if inputs else None
        
        else:
            return inputs
    
    def get_schema(self) -> Dict[str, Any]:
        """获取节点 schema"""
        return {
            "name": "merge",
            "description": "合并数据",
            "inputs": {
                "inputs": {
                    "type": "array",
                    "required": True,
                    "description": "输入数据列表"
                },
                "merge_strategy": {
                    "type": "string",
                    "required": False,
                    "default": "concat",
                    "enum": ["concat", "merge_objects", "first", "last"],
                    "description": "合并策略"
                }
            },
            "outputs": {
                "merged": {
                    "type": "any",
                    "description": "合并后的数据"
                },
                "count": {
                    "type": "number",
                    "description": "输入数量"
                }
            }
        }


class SplitNode(BaseNode):
    """拆分节点

    将数组拆分为多个单独输出。
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.input_key = config.get("input_key", "items") if config else "items"
        self.chunk_size = config.get("chunk_size", 1) if config else 1
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """执行拆分"""
        try:
            items = context.get(self.input_key, [])
            
            if not isinstance(items, list):
                return NodeResult(
                    status=NodeStatus.FAILED,
                    node_name=self.name,
                    error=f"{self.input_key} 必须是数组"
                )
            
            chunks = self._split_items(items)
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                node_name=self.name,
                output={
                    "chunks": chunks,
                    "total": len(items),
                    "chunk_count": len(chunks)
                }
            )
        
        except Exception as e:
            return NodeResult(
                status=NodeStatus.FAILED,
                node_name=self.name,
                error=f"拆分失败：{e}"
            )
    
    def _split_items(self, items: list) -> list:
        """拆分数组"""
        if self.chunk_size <= 0:
            return [[item] for item in items]
        
        chunks = []
        for i in range(0, len(items), self.chunk_size):
            chunk = items[i:i + self.chunk_size]
            chunks.append(chunk)
        
        return chunks
    
    def get_schema(self) -> Dict[str, Any]:
        """获取节点 schema"""
        return {
            "name": "split",
            "description": "拆分数据",
            "inputs": {
                "items": {
                    "type": "array",
                    "required": True,
                    "description": "要拆分的数组"
                },
                "chunk_size": {
                    "type": "number",
                    "required": False,
                    "default": 1,
                    "description": "每块大小"
                }
            },
            "outputs": {
                "chunks": {
                    "type": "array",
                    "description": "拆分后的块"
                },
                "chunk_count": {
                    "type": "number",
                    "description": "块数量"
                }
            }
        }
