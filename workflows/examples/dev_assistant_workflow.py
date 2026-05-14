"""
Dev Assistant Workflow - 开发助手工作流示例

演示如何使用技能节点辅助开发工作。
"""

import logging
from typing import Any, Dict, List, Optional

from agentm.workflows.workflow_engine import BaseWorkflow, WorkflowResult
from agentm.src.nodes.skill_nodes import CodingAgentNode, DataAnalysisNode

logger = logging.getLogger(__name__)


class DevAssistantWorkflow(BaseWorkflow):
    """开发助手工作流"""
    
    def _setup_steps(self) -> None:
        """设置工作流步骤"""
        # 初始化技能节点
        self._coding_node = CodingAgentNode(self.config.get("coding_config"))
        self._analysis_node = DataAnalysisNode(self.config.get("analysis_config"))
        
        # 添加步骤
        self.engine.add_step(
            name="analyze_codebase",
            func=self._analyze_codebase,
            description="分析代码库",
            retry_count=1
        )
        
        self.engine.add_step(
            name="implement_feature",
            func=self._implement_feature,
            description="实现功能",
            retry_count=2
        )
        
        self.engine.add_step(
            name="run_tests",
            func=self._run_tests,
            description="运行测试",
            skip_on_error=True
        )
        
        self.engine.add_step(
            name="generate_docs",
            func=self._generate_docs,
            description="生成文档",
            skip_on_error=True
        )
    
    def _analyze_codebase(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """分析代码库"""
        workdir = self.config.get("workdir", ".")
        
        logger.info(f"分析代码库：{workdir}")
        
        context["workdir"] = workdir
        context["codebase_analyzed"] = True
        
        return {"status": "started", "workdir": workdir}
    
    async def _implement_feature(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """实现功能"""
        task = self.config.get("task")
        
        if not task:
            raise ValueError("缺少开发任务配置")
        
        logger.info(f"实现功能：{task}")
        
        coding_context = {
            "task": task,
            "agent": self.config.get("coding_agent", "claude-code"),
            "workdir": context.get("workdir"),
            "background": False
        }
        
        result = await self._coding_node.execute(coding_context)
        
        if result.status.value == "failed":
            raise RuntimeError(f"功能实现失败：{result.error}")
        
        context["coding_result"] = result.output
        return result.output
    
    def _run_tests(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """运行测试"""
        workdir = context.get("workdir", ".")
        test_command = self.config.get("test_command", "pytest")
        
        logger.info(f"运行测试：{test_command}")
        
        import subprocess
        
        try:
            result = subprocess.run(
                test_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=workdir
            )
            
            test_result = {
                "success": result.returncode == 0,
                "output": result.stdout,
                "errors": result.stderr,
                "returncode": result.returncode
            }
            
            context["test_result"] = test_result
            return test_result
        
        except subprocess.TimeoutExpired:
            raise RuntimeError("测试执行超时（5 分钟）")
        except Exception as e:
            raise RuntimeError(f"测试执行失败：{e}")
    
    def _generate_docs(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成文档"""
        workdir = context.get("workdir", ".")
        
        logger.info("生成文档")
        
        # 使用编码代理生成文档
        doc_task = """
请为项目生成文档：
1. 创建 README.md 文件，包含项目介绍、安装说明、使用示例
2. 为所有公共函数生成 docstring
3. 创建 API 文档（如适用）
""".strip()
        
        coding_context = {
            "task": doc_task,
            "agent": self.config.get("coding_agent", "claude-code"),
            "workdir": workdir,
            "background": False
        }
        
        # 这里简化处理，实际应调用 coding_node
        context["docs_generated"] = True
        return {"status": "completed"}
    
    async def execute(self) -> WorkflowResult:
        """执行工作流（支持异步步骤）"""
        context = {}
        self.engine._context = context
        
        # 分析代码库
        self._analyze_codebase(context)
        
        # 实现功能
        await self._implement_feature(context)
        
        # 运行测试
        try:
            self._run_tests(context)
        except Exception as e:
            logger.warning(f"测试失败：{e}")
            context["test_error"] = str(e)
        
        # 生成文档
        try:
            self._generate_docs(context)
        except Exception as e:
            logger.warning(f"文档生成失败：{e}")
            context["docs_error"] = str(e)
        
        # 汇总结果
        result_summary = {
            "workdir": context.get("workdir"),
            "task": self.config.get("task"),
            "coding_completed": context.get("coding_result") is not None,
            "tests_passed": context.get("test_result", {}).get("success", False),
            "docs_generated": context.get("docs_generated", False),
            "errors": {
                "test": context.get("test_error"),
                "docs": context.get("docs_error")
            }
        }
        
        context["summary"] = result_summary
        
        return WorkflowResult(
            workflow_name=self.__class__.__name__,
            status=self.engine.status,
            step_results=[],
            error=context.get("coding_result", {}).get("error") if context.get("coding_result") else None
        )
    
    def get_workflow_info(self) -> Dict[str, Any]:
        """获取工作流信息"""
        return {
            "name": "DevAssistantWorkflow",
            "description": "开发助手工作流 - 辅助代码开发、测试和文档生成",
            "steps": [
                "analyze_codebase - 分析代码库",
                "implement_feature - 实现功能",
                "run_tests - 运行测试",
                "generate_docs - 生成文档"
            ],
            "config": self.config
        }


async def run_dev_assistant(
    task: str,
    workdir: str = ".",
    coding_agent: str = "claude-code",
    test_command: Optional[str] = None
) -> WorkflowResult:
    """
    便捷函数：运行开发助手工作流
    
    Args:
        task: 开发任务描述
        workdir: 工作目录
        coding_agent: 使用的编码代理
        test_command: 测试命令
    
    Returns:
        WorkflowResult: 执行结果
    """
    config = {
        "task": task,
        "workdir": workdir,
        "coding_agent": coding_agent,
        "test_command": test_command or "pytest"
    }
    
    workflow = DevAssistantWorkflow(config)
    return await workflow.execute()
