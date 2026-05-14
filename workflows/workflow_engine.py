"""
AgentM Workflows - 工作流引擎和模板

提供常用工作流模板：数据同步、定时报告、API 集成、AI 辅助
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """步骤执行结果"""
    step_name: str
    status: StepStatus
    output: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WorkflowResult:
    """工作流执行结果"""
    workflow_name: str
    status: WorkflowStatus
    step_results: List[StepResult] = field(default_factory=list)
    total_duration: float = 0.0
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "workflow_name": self.workflow_name,
            "status": self.status.value,
            "step_results": [
                {
                    "step_name": r.step_name,
                    "status": r.status.value,
                    "output": str(r.output)[:100] if r.output else None,
                    "error": r.error,
                    "duration": r.duration
                }
                for r in self.step_results
            ],
            "total_duration": self.total_duration,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "error": self.error
        }


@dataclass
class WorkflowStep:
    """工作流步骤"""
    name: str
    func: Callable
    description: str = ""
    retry_count: int = 0
    retry_delay: float = 1.0
    skip_on_error: bool = False
    timeout: Optional[float] = None
    
    def __post_init__(self):
        """验证步骤配置"""
        if not callable(self.func):
            raise ValueError(f"步骤 {self.name} 的 func 必须是可调用对象")


class WorkflowEngine:
    """工作流引擎"""
    
    def __init__(self, name: str, config: Optional[Dict] = None):
        self.name = name
        self.config = config or {}
        self._steps: List[WorkflowStep] = []
        self._context: Dict[str, Any] = {}
        self._status = WorkflowStatus.PENDING
    
    @property
    def status(self) -> WorkflowStatus:
        """获取当前状态"""
        return self._status
    
    @property
    def context(self) -> Dict[str, Any]:
        """获取执行上下文"""
        return self._context
    
    def add_step(
        self,
        name: str,
        func: Callable,
        description: str = "",
        retry_count: int = 0,
        retry_delay: float = 1.0,
        skip_on_error: bool = False,
        timeout: Optional[float] = None
    ) -> "WorkflowEngine":
        """添加步骤"""
        step = WorkflowStep(
            name=name,
            func=func,
            description=description,
            retry_count=retry_count,
            retry_delay=retry_delay,
            skip_on_error=skip_on_error,
            timeout=timeout
        )
        self._steps.append(step)
        logger.info(f"[{self.name}] 添加步骤：{name}")
        return self
    
    async def _execute_step(self, step: WorkflowStep) -> StepResult:
        """执行单个步骤（带重试）"""
        import time
        start_time = time.time()
        
        for attempt in range(step.retry_count + 1):
            try:
                logger.info(f"[{self.name}] 执行步骤：{step.name} (尝试 {attempt + 1}/{step.retry_count + 1})")
                
                # 执行步骤（支持同步和异步函数）
                if asyncio.iscoroutinefunction(step.func):
                    result = await step.func(self._context)
                else:
                    result = step.func(self._context)
                
                # 更新上下文
                if result:
                    self._context[step.name] = result
                
                duration = time.time() - start_time
                
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.COMPLETED,
                    output=result,
                    duration=duration
                )
            
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[{self.name}] 步骤 {step.name} 失败：{error_msg}")
                
                if attempt < step.retry_count:
                    await asyncio.sleep(step.retry_delay * (attempt + 1))
                    continue
                
                if step.skip_on_error:
                    return StepResult(
                        step_name=step.name,
                        status=StepStatus.SKIPPED,
                        error=error_msg,
                        duration=time.time() - start_time
                    )
                
                return StepResult(
                    step_name=step.name,
                    status=StepStatus.FAILED,
                    error=error_msg,
                    duration=time.time() - start_time
                )
        
        return StepResult(
            step_name=step.name,
            status=StepStatus.FAILED,
            error="未知错误",
            duration=time.time() - start_time
        )
    
    async def execute(self) -> WorkflowResult:
        """执行工作流"""
        import time
        start_time = time.time()
        
        self._status = WorkflowStatus.RUNNING
        logger.info(f"[{self.name}] 工作流开始执行")
        
        step_results = []
        
        for step in self._steps:
            result = await self._execute_step(step)
            step_results.append(result)
            
            if result.status == StepStatus.FAILED and not step.skip_on_error:
                self._status = WorkflowStatus.FAILED
                logger.error(f"[{self.name}] 工作流执行失败于步骤：{step.name}")
                break
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        if self._status != WorkflowStatus.FAILED:
            self._status = WorkflowStatus.COMPLETED
            logger.info(f"[{self.name}] 工作流执行完成，耗时：{total_duration:.2f}s")
        
        return WorkflowResult(
            workflow_name=self.name,
            status=self._status,
            step_results=step_results,
            total_duration=total_duration,
            start_time=datetime.now(),
            end_time=datetime.now(),
            error=next((r.error for r in step_results if r.status == StepStatus.FAILED), None)
        )


class BaseWorkflow(ABC):
    """工作流基类"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.engine = WorkflowEngine(self.__class__.__name__, self.config)
        self._setup_steps()
    
    @abstractmethod
    def _setup_steps(self) -> None:
        """设置工作流步骤（子类实现）"""
        pass
    
    async def execute(self) -> WorkflowResult:
        """执行工作流"""
        return await self.engine.execute()
    
    def get_status(self) -> Dict[str, Any]:
        """获取工作流状态"""
        return {
            "name": self.__class__.__name__,
            "status": self.engine.status.value,
            "config": self.config
        }


# ============ 数据同步工作流 ============

class DataSyncWorkflow(BaseWorkflow):
    """数据同步工作流"""
    
    def _setup_steps(self) -> None:
        """设置数据同步步骤"""
        self.engine.add_step(
            name="validate_config",
            func=self._validate_config,
            description="验证配置",
            retry_count=0
        )
        self.engine.add_step(
            name="connect_source",
            func=self._connect_source,
            description="连接数据源",
            retry_count=3,
            retry_delay=2.0
        )
        self.engine.add_step(
            name="connect_target",
            func=self._connect_target,
            description="连接目标",
            retry_count=3,
            retry_delay=2.0
        )
        self.engine.add_step(
            name="extract_data",
            func=self._extract_data,
            description="提取数据",
            retry_count=2,
            timeout=300.0
        )
        self.engine.add_step(
            name="transform_data",
            func=self._transform_data,
            description="转换数据",
            retry_count=1
        )
        self.engine.add_step(
            name="load_data",
            func=self._load_data,
            description="加载数据",
            retry_count=3,
            retry_delay=5.0
        )
        self.engine.add_step(
            name="verify_sync",
            func=self._verify_sync,
            description="验证同步结果",
            skip_on_error=True
        )
    
    def _validate_config(self, context: Dict) -> bool:
        """验证配置"""
        required_keys = ["source", "target"]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"缺少必需配置：{key}")
        logger.info("配置验证通过")
        return True
    
    def _connect_source(self, context: Dict) -> Any:
        """连接数据源"""
        source_config = self.config.get("source", {})
        logger.info(f"连接数据源：{source_config.get('type', 'unknown')}")
        # 实际实现中这里会创建数据库连接或 API 客户端
        context["source_connection"] = {"connected": True, "config": source_config}
        return context["source_connection"]
    
    def _connect_target(self, context: Dict) -> Any:
        """连接目标"""
        target_config = self.config.get("target", {})
        logger.info(f"连接目标：{target_config.get('type', 'unknown')}")
        context["target_connection"] = {"connected": True, "config": target_config}
        return context["target_connection"]
    
    def _extract_data(self, context: Dict) -> List[Dict]:
        """提取数据"""
        logger.info("开始提取数据")
        # 实际实现中这里会从源读取数据
        context["extracted_data"] = []
        return context["extracted_data"]
    
    def _transform_data(self, context: Dict) -> List[Dict]:
        """转换数据"""
        logger.info("开始转换数据")
        # 实际实现中这里会进行数据转换
        context["transformed_data"] = context.get("extracted_data", [])
        return context["transformed_data"]
    
    def _load_data(self, context: Dict) -> int:
        """加载数据"""
        logger.info("开始加载数据")
        # 实际实现中这里会写入目标
        context["loaded_count"] = len(context.get("transformed_data", []))
        return context["loaded_count"]
    
    def _verify_sync(self, context: Dict) -> bool:
        """验证同步结果"""
        logger.info("验证同步结果")
        return True


# ============ 定时报告工作流 ============

class ScheduledReportWorkflow(BaseWorkflow):
    """定时报告工作流"""
    
    def _setup_steps(self) -> None:
        """设置定时报告步骤"""
        self.engine.add_step(
            name="collect_data",
            func=self._collect_data,
            description="收集数据",
            retry_count=3,
            retry_delay=5.0
        )
        self.engine.add_step(
            name="analyze_data",
            func=self._analyze_data,
            description="分析数据",
            retry_count=1
        )
        self.engine.add_step(
            name="generate_report",
            func=self._generate_report,
            description="生成报告",
            retry_count=2
        )
        self.engine.add_step(
            name="send_report",
            func=self._send_report,
            description="发送报告",
            retry_count=3,
            retry_delay=10.0,
            skip_on_error=True
        )
    
    def _collect_data(self, context: Dict) -> Dict:
        """收集数据"""
        logger.info("收集报告数据")
        context["raw_data"] = {}
        return context["raw_data"]
    
    def _analyze_data(self, context: Dict) -> Dict:
        """分析数据"""
        logger.info("分析数据")
        context["analysis"] = {"metrics": {}}
        return context["analysis"]
    
    def _generate_report(self, context: Dict) -> str:
        """生成报告"""
        logger.info("生成报告")
        report_path = self.config.get("output_path", "report.pdf")
        context["report_path"] = report_path
        return report_path
    
    def _send_report(self, context: Dict) -> bool:
        """发送报告"""
        logger.info(f"发送报告：{context.get('report_path')}")
        return True


# ============ API 集成工作流 ============

class APIIntegrationWorkflow(BaseWorkflow):
    """API 集成工作流"""
    
    def _setup_steps(self) -> None:
        """设置 API 集成步骤"""
        self.engine.add_step(
            name="authenticate",
            func=self._authenticate,
            description="认证",
            retry_count=3,
            retry_delay=2.0
        )
        self.engine.add_step(
            name="fetch_data",
            func=self._fetch_data,
            description="获取数据",
            retry_count=3,
            timeout=60.0
        )
        self.engine.add_step(
            name="process_response",
            func=self._process_response,
            description="处理响应",
            retry_count=1
        )
        self.engine.add_step(
            name="store_result",
            func=self._store_result,
            description="存储结果",
            retry_count=2
        )
    
    def _authenticate(self, context: Dict) -> Dict:
        """认证"""
        logger.info("API 认证")
        auth_config = self.config.get("auth", {})
        context["auth_token"] = "mock_token"
        return {"authenticated": True}
    
    def _fetch_data(self, context: Dict) -> Dict:
        """获取数据"""
        logger.info("获取 API 数据")
        api_config = self.config.get("api", {})
        context["api_response"] = {}
        return context["api_response"]
    
    def _process_response(self, context: Dict) -> Dict:
        """处理响应"""
        logger.info("处理 API 响应")
        context["processed_data"] = context.get("api_response", {})
        return context["processed_data"]
    
    def _store_result(self, context: Dict) -> int:
        """存储结果"""
        logger.info("存储结果")
        context["stored"] = True
        return 1


# ============ AI 辅助工作流 ============

class AIAssistantWorkflow(BaseWorkflow):
    """AI 辅助工作流"""
    
    def _setup_steps(self) -> None:
        """设置 AI 辅助步骤"""
        self.engine.add_step(
            name="parse_request",
            func=self._parse_request,
            description="解析请求",
            retry_count=1
        )
        self.engine.add_step(
            name="select_model",
            func=self._select_model,
            description="选择模型",
            retry_count=0
        )
        self.engine.add_step(
            name="generate_response",
            func=self._generate_response,
            description="生成响应",
            retry_count=2,
            timeout=120.0
        )
        self.engine.add_step(
            name="format_output",
            func=self._format_output,
            description="格式化输出",
            retry_count=1
        )
    
    def _parse_request(self, context: Dict) -> Dict:
        """解析请求"""
        logger.info("解析用户请求")
        request = self.config.get("request", "")
        context["parsed_request"] = {"query": request}
        return context["parsed_request"]
    
    def _select_model(self, context: Dict) -> str:
        """选择模型"""
        logger.info("选择 AI 模型")
        model = self.config.get("model", "default")
        context["selected_model"] = model
        return model
    
    def _generate_response(self, context: Dict) -> str:
        """生成响应"""
        logger.info("生成 AI 响应")
        context["ai_response"] = "AI 生成的响应内容"
        return context["ai_response"]
    
    def _format_output(self, context: Dict) -> str:
        """格式化输出"""
        logger.info("格式化输出")
        response = context.get("ai_response", "")
        context["formatted_output"] = response
        return context["formatted_output"]


# 便捷函数
async def run_data_sync(config: Dict) -> WorkflowResult:
    """运行数据同步工作流"""
    workflow = DataSyncWorkflow(config)
    return await workflow.execute()


async def run_scheduled_report(config: Dict) -> WorkflowResult:
    """运行定时报告工作流"""
    workflow = ScheduledReportWorkflow(config)
    return await workflow.execute()


async def run_api_integration(config: Dict) -> WorkflowResult:
    """运行 API 集成工作流"""
    workflow = APIIntegrationWorkflow(config)
    return await workflow.execute()


async def run_ai_assistant(config: Dict) -> WorkflowResult:
    """运行 AI 辅助工作流"""
    workflow = AIAssistantWorkflow(config)
    return await workflow.execute()
