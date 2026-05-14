"""
Deep Research Node - 深度研究节点

集成 deep-research 技能，提供深度研究能力。
"""

import logging
from typing import Any, Dict, List, Optional

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


class DeepResearchNode(BaseNode):
    """深度研究节点"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("deep_research", config)
        self._max_depth = config.get("max_depth", 3) if config else 3
        self._time_limit = config.get("time_limit", 300) if config else 300  # 秒
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """
        执行深度研究
        
        Args:
            context: 执行上下文，包含:
                - query: 研究主题/问题
                - max_sources: 最大来源数量
                - time_range: 时间范围 (day, week, month, year)
                - include_answer: 是否包含 AI 总结
        
        Returns:
            NodeResult: 研究报告
        """
        try:
            query = context.get("query")
            max_sources = context.get("max_sources", 10)
            time_range = context.get("time_range", "month")
            include_answer = context.get("include_answer", True)
            
            if not query:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    error="缺少必需参数：query",
                    node_name=self.name
                )
            
            # 调用 deep-research 技能
            result = await self._run_research(
                query=query,
                max_sources=max_sources,
                time_range=time_range,
                include_answer=include_answer
            )
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                output=result,
                node_name=self.name
            )
        
        except Exception as e:
            logger.error(f"深度研究失败：{e}")
            return NodeResult(
                status=NodeStatus.FAILED,
                error=str(e),
                node_name=self.name
            )
    
    async def _run_research(
        self,
        query: str,
        max_sources: int = 10,
        time_range: str = "month",
        include_answer: bool = True
    ) -> Dict[str, Any]:
        """
        运行深度研究
        
        通过 Tavily API 进行深度研究
        """
        from tavily_search import tavily_search
        
        try:
            # 使用 Tavily 进行深度搜索
            search_result = tavily_search(
                query=query,
                search_depth="advanced",
                max_results=max_sources,
                time_range=time_range,
                include_answer=include_answer,
                topic="general"
            )
            
            # 处理结果
            research_data = {
                "query": query,
                "answer": search_result.get("answer") if include_answer else None,
                "results": [],
                "total_results": len(search_result.get("results", []))
            }
            
            for result in search_result.get("results", [])[:max_sources]:
                research_data["results"].append({
                    "title": result.get("title"),
                    "url": result.get("url"),
                    "content": result.get("content"),
                    "score": result.get("score"),
                    "published_date": result.get("published_date")
                })
            
            return research_data
        
        except Exception as e:
            logger.error(f"Tavily 搜索失败：{e}")
            # 降级到基础 web_search
            return await self._fallback_research(query, max_sources)
    
    async def _fallback_research(
        self,
        query: str,
        max_sources: int = 10
    ) -> Dict[str, Any]:
        """
        降级研究（当 Tavily 不可用时）
        """
        from ..tools.web_search import web_search
        
        results = web_search(query=query, count=max_sources)
        
        return {
            "query": query,
            "answer": None,
            "results": results,
            "total_results": len(results)
        }
    
    def get_schema(self) -> Dict[str, Any]:
        """返回节点输入输出 schema"""
        return {
            "inputs": {
                "query": {"type": "string", "required": True, "description": "研究主题/问题"},
                "max_sources": {"type": "integer", "required": False, "default": 10},
                "time_range": {
                    "type": "string",
                    "required": False,
                    "default": "month",
                    "enum": ["day", "week", "month", "year"]
                },
                "include_answer": {"type": "boolean", "required": False, "default": True}
            },
            "outputs": {
                "research_report": {"type": "object", "description": "研究报告"}
            }
        }
