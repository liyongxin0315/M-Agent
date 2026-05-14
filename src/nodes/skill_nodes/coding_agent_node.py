"""
Coding Agent Node - 编码助手节点

集成 coding-agent 技能，提供代码生成和编辑能力。
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


class CodingAgentNode(BaseNode):
    """编码助手节点"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("coding_agent", config)
        self._default_agent = config.get("agent", "claude-code") if config else "claude-code"
        self._workdir = config.get("workdir") if config else None
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """
        执行编码任务
        
        Args:
            context: 执行上下文，包含:
                - task: 编码任务描述
                - agent: 使用的编码代理
                - workdir: 工作目录
                - files: 相关文件列表
                - background: 是否后台执行
        
        Returns:
            NodeResult: 执行结果
        """
        try:
            task = context.get("task")
            agent = context.get("agent", self._default_agent)
            workdir = context.get("workdir", self._workdir)
            files = context.get("files", [])
            background = context.get("background", False)
            
            if not task:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    error="缺少必需参数：task",
                    node_name=self.name
                )
            
            # 调用 coding-agent 技能
            result = await self._run_coding_agent(
                task=task,
                agent=agent,
                workdir=workdir,
                files=files,
                background=background
            )
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                output=result,
                node_name=self.name
            )
        
        except Exception as e:
            logger.error(f"编码代理执行失败：{e}")
            return NodeResult(
                status=NodeStatus.FAILED,
                error=str(e),
                node_name=self.name
            )
    
    async def _run_coding_agent(
        self,
        task: str,
        agent: str = "claude-code",
        workdir: Optional[str] = None,
        files: Optional[List[str]] = None,
        background: bool = False
    ) -> Dict[str, Any]:
        """
        运行编码代理
        """
        import subprocess
        import os
        from pathlib import Path
        
        if not workdir:
            workdir = os.getcwd()
        
        work_path = Path(workdir)
        if not work_path.exists():
            work_path.mkdir(parents=True, exist_ok=True)
        
        # 根据代理类型构建命令
        if agent == "claude-code":
            return await self._run_claude_code(task, work_path, files, background)
        elif agent == "codex":
            return await self._run_codex(task, work_path, background)
        elif agent == "pi":
            return await self._run_pi(task, work_path, background)
        else:
            raise ValueError(f"不支持的编码代理：{agent}")
    
    async def _run_claude_code(
        self,
        task: str,
        work_path: Path,
        files: Optional[List[str]],
        background: bool
    ) -> Dict[str, Any]:
        """
        运行 Claude Code
        """
        import subprocess
        
        # 构建命令
        cmd = [
            "claude",
            "--permission-mode", "bypassPermissions",
            "--print",
            task
        ]
        
        # 添加文件上下文
        if files:
            for file in files:
                if Path(file).exists():
                    with open(file, "r") as f:
                        task = f"参考文件 {file}:\n{f.read()}\n\n{task}"
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 分钟超时
                cwd=str(work_path)
            )
            
            return {
                "agent": "claude-code",
                "workdir": str(work_path),
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
                "returncode": result.returncode,
                "background": background
            }
        
        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude Code 执行超时（10 分钟）")
        except FileNotFoundError:
            raise RuntimeError("Claude Code CLI 未安装，请先运行：npm install -g @anthropic-ai/claude-code")
    
    async def _run_codex(
        self,
        task: str,
        work_path: Path,
        background: bool
    ) -> Dict[str, Any]:
        """
        运行 Codex
        """
        import subprocess
        
        # Codex 需要 git 仓库
        git_init = subprocess.run(["git", "init"], cwd=str(work_path), capture_output=True)
        if git_init.returncode != 0 and "already exists" not in git_init.stderr:
            logger.warning(f"git init 失败：{git_init.stderr}")
        
        cmd = ["codex", "exec", "--full-auto", task]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(work_path)
            )
            
            return {
                "agent": "codex",
                "workdir": str(work_path),
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
                "returncode": result.returncode
            }
        
        except subprocess.TimeoutExpired:
            raise RuntimeError("Codex 执行超时（10 分钟）")
    
    async def _run_pi(
        self,
        task: str,
        work_path: Path,
        background: bool
    ) -> Dict[str, Any]:
        """
        运行 Pi Coding Agent
        """
        import subprocess
        
        cmd = ["pi", "-p", task]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(work_path)
            )
            
            return {
                "agent": "pi",
                "workdir": str(work_path),
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None,
                "returncode": result.returncode
            }
        
        except subprocess.TimeoutExpired:
            raise RuntimeError("Pi 执行超时（10 分钟）")
    
    def get_schema(self) -> Dict[str, Any]:
        """返回节点输入输出 schema"""
        return {
            "inputs": {
                "task": {"type": "string", "required": True, "description": "编码任务描述"},
                "agent": {
                    "type": "string",
                    "required": False,
                    "default": "claude-code",
                    "enum": ["claude-code", "codex", "pi"]
                },
                "workdir": {"type": "string", "required": False, "description": "工作目录"},
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "required": False,
                    "description": "相关文件列表"
                },
                "background": {"type": "boolean", "required": False, "default": False}
            },
            "outputs": {
                "coding_result": {"type": "object", "description": "编码执行结果"}
            }
        }
