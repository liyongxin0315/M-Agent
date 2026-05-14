"""
GitHub Research Node - GitHub 研究节点

集成 github-deep-research 技能，提供 GitHub 代码库研究能力。
"""

import logging
from typing import Any, Dict, List, Optional

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


class GitHubResearchNode(BaseNode):
    """GitHub 研究节点"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("github_research", config)
        self._github_token = config.get("github_token") if config else None
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """
        执行 GitHub 研究
        
        Args:
            context: 执行上下文，包含:
                - repo: 仓库名称 (格式：owner/repo)
                - query: 搜索/研究问题
                - search_type: 搜索类型 (code, issues, prs, files)
                - branch: 分支名称
        
        Returns:
            NodeResult: 研究结果
        """
        try:
            repo = context.get("repo")
            query = context.get("query")
            search_type = context.get("search_type", "code")
            branch = context.get("branch", "main")
            
            if not repo:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    error="缺少必需参数：repo",
                    node_name=self.name
                )
            
            # 调用 github-deep-research 技能
            result = await self._run_github_research(
                repo=repo,
                query=query,
                search_type=search_type,
                branch=branch
            )
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                output=result,
                node_name=self.name
            )
        
        except Exception as e:
            logger.error(f"GitHub 研究失败：{e}")
            return NodeResult(
                status=NodeStatus.FAILED,
                error=str(e),
                node_name=self.name
            )
    
    async def _run_github_research(
        self,
        repo: str,
        query: Optional[str] = None,
        search_type: str = "code",
        branch: str = "main"
    ) -> Dict[str, Any]:
        """
        运行 GitHub 研究
        """
        import subprocess
        import json
        
        # 解析 repo
        parts = repo.split("/")
        if len(parts) != 2:
            raise ValueError(f"无效的仓库格式：{repo} (应为 owner/repo)")
        
        owner, repo_name = parts
        
        # 构建 gh 命令
        if search_type == "code":
            cmd = ["gh", "search", "code", "--limit", "100"]
            if query:
                cmd.extend(["-q", f"repo:{owner}/{repo_name} {query}"])
            else:
                cmd.extend(["-q", f"repo:{owner}/{repo_name}"])
        elif search_type == "issues":
            cmd = ["gh", "issue", "list", "--repo", f"{owner}/{repo_name}", "--limit", "50"]
            if query:
                cmd.extend(["--search", query])
        elif search_type == "prs":
            cmd = ["gh", "pr", "list", "--repo", f"{owner}/{repo_name}", "--limit", "50"]
            if query:
                cmd.extend(["--search", query])
        else:
            raise ValueError(f"不支持的搜索类型：{search_type}")
        
        cmd.extend(["--json", "title,url,body,author,createdAt"])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                env={**subprocess.os.environ, "GH_TOKEN": self._github_token} if self._github_token else None
            )
            
            if result.returncode == 0:
                return {
                    "repo": repo,
                    "search_type": search_type,
                    "query": query,
                    "results": json.loads(result.stdout) if result.stdout else [],
                    "total_count": len(json.loads(result.stdout)) if result.stdout else 0
                }
            else:
                raise RuntimeError(f"GitHub CLI 失败：{result.stderr}")
        
        except subprocess.TimeoutExpired:
            raise RuntimeError("GitHub 研究超时（1 分钟）")
        except FileNotFoundError:
            # gh CLI 不可用时，使用 API
            return await self._fallback_research(owner, repo_name, query, search_type)
    
    async def _fallback_research(
        self,
        owner: str,
        repo_name: str,
        query: Optional[str],
        search_type: str
    ) -> Dict[str, Any]:
        """
        降级研究（使用 GitHub API）
        """
        import requests
        
        base_url = "https://api.github.com"
        
        if search_type == "code":
            url = f"{base_url}/search/code"
            params = {"q": f"repo:{owner}/{repo_name}"}
            if query:
                params["q"] += f" {query}"
        elif search_type == "issues":
            url = f"{base_url}/repos/{owner}/{repo_name}/issues"
            params = {"state": "all", "per_page": 50}
        elif search_type == "prs":
            url = f"{base_url}/repos/{owner}/{repo_name}/pulls"
            params = {"state": "all", "per_page": 50}
        else:
            raise ValueError(f"不支持的搜索类型：{search_type}")
        
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self._github_token:
            headers["Authorization"] = f"token {self._github_token}"
        
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        return {
            "repo": f"{owner}/{repo_name}",
            "search_type": search_type,
            "query": query,
            "results": data.get("items", data) if isinstance(data, dict) else data,
            "total_count": data.get("total_count", len(data) if isinstance(data, list) else 0)
        }
    
    def get_schema(self) -> Dict[str, Any]:
        """返回节点输入输出 schema"""
        return {
            "inputs": {
                "repo": {
                    "type": "string",
                    "required": True,
                    "description": "仓库名称 (格式：owner/repo)"
                },
                "query": {
                    "type": "string",
                    "required": False,
                    "description": "搜索/研究问题"
                },
                "search_type": {
                    "type": "string",
                    "required": False,
                    "default": "code",
                    "enum": ["code", "issues", "prs", "files"]
                },
                "branch": {
                    "type": "string",
                    "required": False,
                    "default": "main"
                }
            },
            "outputs": {
                "research_result": {"type": "object", "description": "GitHub 研究结果"}
            }
        }
