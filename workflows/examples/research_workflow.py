"""
Research Workflow - 研究工作流示例

演示如何使用技能节点进行深度研究。
"""

import logging
from typing import Any, Dict, List, Optional

from agentm.workflows.workflow_engine import BaseWorkflow, WorkflowResult
from agentm.src.nodes.skill_nodes import DeepResearchNode, GitHubResearchNode

logger = logging.getLogger(__name__)


class ResearchWorkflow(BaseWorkflow):
    """研究工作流"""
    
    def _setup_steps(self) -> None:
        """设置工作流步骤"""
        # 初始化技能节点
        self._research_node = DeepResearchNode(self.config.get("research_config"))
        self._github_node = GitHubResearchNode(self.config.get("github_config"))
        
        # 添加步骤
        self.engine.add_step(
            name="web_research",
            func=self._web_research,
            description="执行网络研究",
            retry_count=2
        )
        
        self.engine.add_step(
            name="github_research",
            func=self._github_research,
            description="执行 GitHub 研究",
            skip_on_error=True
        )
        
        self.engine.add_step(
            name="synthesize_results",
            func=self._synthesize_results,
            description="综合研究结果",
            retry_count=1
        )
        
        self.engine.add_step(
            name="generate_report",
            func=self._generate_report,
            description="生成研究报告",
            retry_count=1
        )
    
    def _web_research(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行网络研究"""
        query = self.config.get("query")
        
        if not query:
            raise ValueError("缺少研究主题配置")
        
        logger.info(f"开始网络研究：{query}")
        
        context["query"] = query
        context["research_started"] = True
        
        return {"status": "started", "query": query}
    
    async def _web_research_execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行网络研究（异步）"""
        query = context.get("query", self.config.get("query"))
        max_sources = self.config.get("max_sources", 10)
        time_range = self.config.get("time_range", "month")
        
        logger.info(f"执行深度研究：{query}")
        
        research_context = {
            "query": query,
            "max_sources": max_sources,
            "time_range": time_range,
            "include_answer": True
        }
        
        result = await self._research_node.execute(research_context)
        
        if result.status.value == "failed":
            raise RuntimeError(f"网络研究失败：{result.error}")
        
        context["web_research_result"] = result.output
        return result.output
    
    async def _github_research(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行 GitHub 研究"""
        repos = self.config.get("repos", [])
        query = context.get("query", self.config.get("query"))
        
        if not repos:
            logger.info("未配置 GitHub 仓库，跳过 GitHub 研究")
            return {"status": "skipped", "reason": "no repos configured"}
        
        logger.info(f"执行 GitHub 研究：{repos}")
        
        github_results = []
        
        for repo in repos:
            github_context = {
                "repo": repo,
                "query": query,
                "search_type": "code",
                "branch": "main"
            }
            
            result = await self._github_node.execute(github_context)
            
            if result.status.value == "completed":
                github_results.append({
                    "repo": repo,
                    "result": result.output
                })
        
        context["github_research_result"] = github_results
        return {"github_results": github_results}
    
    def _synthesize_results(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """综合研究结果"""
        logger.info("综合研究结果")
        
        web_result = context.get("web_research_result", {})
        github_result = context.get("github_research_result", [])
        
        synthesis = {
            "query": context.get("query"),
            "web_sources_count": web_result.get("total_results", 0),
            "github_repos_analyzed": len(github_result),
            "key_findings": [],
            "sources": []
        }
        
        # 提取关键发现
        if web_result.get("answer"):
            synthesis["key_findings"].append({
                "source": "web",
                "content": web_result.get("answer")
            })
        
        # 收集来源
        for result in web_result.get("results", [])[:5]:
            synthesis["sources"].append({
                "type": "web",
                "title": result.get("title"),
                "url": result.get("url")
            })
        
        for gh_result in github_result:
            synthesis["sources"].append({
                "type": "github",
                "repo": gh_result.get("repo"),
                "results_count": gh_result.get("result", {}).get("total_count", 0)
            })
        
        context["synthesis"] = synthesis
        return synthesis
    
    def _generate_report(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成研究报告"""
        logger.info("生成研究报告")
        
        synthesis = context.get("synthesis", {})
        
        report = {
            "title": f"研究报告：{synthesis.get('query', 'Unknown')}",
            "executive_summary": synthesis.get("key_findings", [{}])[0].get("content", "")[:500],
            "methodology": {
                "web_research": True,
                "github_research": len(context.get("github_research_result", [])) > 0,
                "sources_analyzed": synthesis.get("web_sources_count", 0) + synthesis.get("github_repos_analyzed", 0)
            },
            "findings": synthesis.get("key_findings", []),
            "sources": synthesis.get("sources", []),
            "generated_at": self._get_timestamp()
        }
        
        # 保存报告
        output_path = self.config.get("report_path", "output/research_report.json")
        
        import json
        from pathlib import Path
        
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        context["report_path"] = output_path
        return {"report_path": output_path}
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    # 重写 execute 方法以支持异步步骤
    async def execute(self) -> WorkflowResult:
        """执行工作流（支持异步步骤）"""
        # 先执行同步的 web_research 初始化
        context = {"query": self.config.get("query")}
        self.engine._context = context
        self._web_research(context)
        
        # 然后执行异步步骤
        await self._web_research_execute(context)
        await self._github_research(context)
        self._synthesize_results(context)
        self._generate_report(context)
        
        # 返回结果
        return WorkflowResult(
            workflow_name=self.__class__.__name__,
            status=self.engine.status,
            step_results=[],
            error=context.get("error")
        )
    
    def get_workflow_info(self) -> Dict[str, Any]:
        """获取工作流信息"""
        return {
            "name": "ResearchWorkflow",
            "description": "研究工作流 - 结合网络研究和 GitHub 代码库研究",
            "steps": [
                "web_research - 执行网络深度研究",
                "github_research - 执行 GitHub 代码库研究",
                "synthesize_results - 综合研究结果",
                "generate_report - 生成研究报告"
            ],
            "config": self.config
        }


async def run_research(
    query: str,
    repos: Optional[List[str]] = None,
    max_sources: int = 10,
    time_range: str = "month",
    output_path: str = "output/research_report.json"
) -> WorkflowResult:
    """
    便捷函数：运行研究工作流
    
    Args:
        query: 研究主题
        repos: GitHub 仓库列表
        max_sources: 最大来源数量
        time_range: 时间范围
        output_path: 报告输出路径
    
    Returns:
        WorkflowResult: 执行结果
    """
    config = {
        "query": query,
        "repos": repos or [],
        "max_sources": max_sources,
        "time_range": time_range,
        "report_path": output_path
    }
    
    workflow = ResearchWorkflow(config)
    return await workflow.execute()
