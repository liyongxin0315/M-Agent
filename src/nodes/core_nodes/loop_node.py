"""
Loop Node - 循环节点

对数组或集合进行循环处理。
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


@dataclass
class LoopConfig:
    """循环配置"""
    items_key: str = "items"
    result_key: str = "results"
    parallel: bool = False
    max_concurrency: int = 5
    break_on_error: bool = True
    continue_on_error: bool = False


class LoopNode(BaseNode):
    """循环节点"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.loop_config = self._parse_config(config or {})
        self._loop_func: Optional[Callable] = None
    
    def _parse_config(self, config: Dict[str, Any]) -> LoopConfig:
        """解析配置"""
        return LoopConfig(
            items_key=config.get("items_key", "items"),
            result_key=config.get("result_key", "results"),
            parallel=config.get("parallel", False),
            max_concurrency=config.get("max_concurrency", 5),
            break_on_error=config.get("break_on_error", True),
            continue_on_error=config.get("continue_on_error", False)
        )
    
    def set_loop_function(self, func: Callable) -> "LoopNode":
        """设置循环函数"""
        self._loop_func = func
        return self
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """执行循环"""
        try:
            items = context.get(self.loop_config.items_key, [])
            
            if not isinstance(items, list):
                return NodeResult(
                    status=NodeStatus.FAILED,
                    node_name=self.name,
                    error=f"{self.loop_config.items_key} 必须是数组"
                )
            
            if not items:
                return NodeResult(
                    status=NodeStatus.COMPLETED,
                    node_name=self.name,
                    output={self.loop_config.result_key: []}
                )
            
            if self._loop_func:
                if self.loop_config.parallel:
                    results = await self._execute_parallel(items, context)
                else:
                    results = await self._execute_sequential(items, context)
            else:
                results = items
            
            output = {
                self.loop_config.result_key: results,
                "count": len(results),
                "success_count": len([r for r in results if not isinstance(r, dict) and r.get("_error") is None])
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
                error=f"循环执行失败：{e}"
            )
    
    async def _execute_sequential(
        self,
        items: List[Any],
        context: Dict[str, Any]
    ) -> List[Any]:
        """顺序执行"""
        results = []
        
        for i, item in enumerate(items):
            try:
                item_context = {**context, "item": item, "index": i, "total": len(items)}
                
                if asyncio.iscoroutinefunction(self._loop_func):
                    result = await self._loop_func(item_context)
                else:
                    result = self._loop_func(item_context)
                
                results.append(result)
            
            except Exception as e:
                if self.loop_config.break_on_error:
                    raise
                elif self.loop_config.continue_on_error:
                    results.append({"_error": str(e), "_index": i})
                else:
                    results.append({"_error": str(e), "_index": i})
        
        return results
    
    async def _execute_parallel(
        self,
        items: List[Any],
        context: Dict[str, Any]
    ) -> List[Any]:
        """并行执行"""
        semaphore = asyncio.Semaphore(self.loop_config.max_concurrency)
        
        async def process_item(i: int, item: Any) -> Any:
            async with semaphore:
                try:
                    item_context = {**context, "item": item, "index": i, "total": len(items)}
                    
                    if asyncio.iscoroutinefunction(self._loop_func):
                        return await self._loop_func(item_context)
                    else:
                        return self._loop_func(item_context)
                
                except Exception as e:
                    if self.loop_config.break_on_error:
                        raise
                    return {"_error": str(e), "_index": i}
        
        tasks = [process_item(i, item) for i, item in enumerate(items)]
        results = await asyncio.gather(*tasks)
        
        return list(results)
    
    def get_schema(self) -> Dict[str, Any]:
        """获取节点 schema"""
        return {
            "name": "loop",
            "description": "循环处理",
            "inputs": {
                "items": {
                    "type": "array",
                    "required": True,
                    "description": "要循环的数组"
                },
                "parallel": {
                    "type": "boolean",
                    "required": False,
                    "default": False,
                    "description": "是否并行执行"
                },
                "max_concurrency": {
                    "type": "number",
                    "required": False,
                    "default": 5,
                    "description": "最大并发数"
                }
            },
            "outputs": {
                "results": {
                    "type": "array",
                    "description": "处理结果"
                },
                "count": {
                    "type": "number",
                    "description": "处理数量"
                }
            }
        }
