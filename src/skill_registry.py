"""
Skill Registry - 技能注册系统

提供技能的注册、发现、加载和执行功能。
"""

import importlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

from .base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


class SkillCategory(Enum):
    """技能类别"""
    DATA_PROCESSING = "data_processing"
    CONTENT_GENERATION = "content_generation"
    DEVELOPMENT_TOOLS = "development_tools"
    UTILITY_TOOLS = "utility_tools"


@dataclass
class SkillInfo:
    """技能信息"""
    name: str
    class_name: str
    category: SkillCategory
    description: str
    module_path: str
    node_class: Optional[Type[BaseNode]] = None
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "class_name": self.class_name,
            "category": self.category.value,
            "description": self.description,
            "module_path": self.module_path,
            "enabled": self.enabled,
            "metadata": self.metadata,
            "registered_at": self.registered_at.isoformat()
        }


@dataclass
class SkillExecutionResult:
    """技能执行结果"""
    skill_name: str
    result: NodeResult
    duration: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "skill_name": self.skill_name,
            "result": self.result.to_dict(),
            "duration": self.duration,
            "timestamp": self.timestamp.isoformat()
        }


class SkillRegistry:
    """技能注册表"""
    
    _instance: Optional["SkillRegistry"] = None
    _initialized: bool = False
    
    def __new__(cls) -> "SkillRegistry":
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if SkillRegistry._initialized:
            return
        
        self._skills: Dict[str, SkillInfo] = {}
        self._instances: Dict[str, BaseNode] = {}
        self._execution_history: List[SkillExecutionResult] = []
        self._max_history = 100
        
        SkillRegistry._initialized = True
        logger.info("SkillRegistry 初始化完成")
    
    @classmethod
    def get_instance(cls) -> "SkillRegistry":
        """获取单例实例"""
        return cls()
    
    def register(
        self,
        name: str,
        class_name: str,
        category: SkillCategory,
        description: str,
        module_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        注册技能
        
        Args:
            name: 技能名称
            class_name: 类名
            category: 技能类别
            description: 技能描述
            module_path: 模块路径
            metadata: 额外元数据
        """
        if name in self._skills:
            logger.warning(f"技能已存在，覆盖：{name}")
        
        skill_info = SkillInfo(
            name=name,
            class_name=class_name,
            category=category,
            description=description,
            module_path=module_path,
            metadata=metadata or {}
        )
        
        self._skills[name] = skill_info
        logger.info(f"技能注册成功：{name} ({category.value})")
    
    def unregister(self, name: str) -> bool:
        """
        注销技能
        
        Args:
            name: 技能名称
        
        Returns:
            bool: 是否成功
        """
        if name in self._skills:
            del self._skills[name]
            if name in self._instances:
                del self._instances[name]
            logger.info(f"技能注销成功：{name}")
            return True
        
        logger.warning(f"技能不存在：{name}")
        return False
    
    def get_skill(self, name: str) -> Optional[SkillInfo]:
        """
        获取技能信息
        
        Args:
            name: 技能名称
        
        Returns:
            Optional[SkillInfo]: 技能信息
        """
        return self._skills.get(name)
    
    def list_skills(
        self,
        category: Optional[SkillCategory] = None,
        enabled_only: bool = True
    ) -> List[SkillInfo]:
        """
        列出技能
        
        Args:
            category: 按类别筛选
            enabled_only: 只列出启用的技能
        
        Returns:
            List[SkillInfo]: 技能列表
        """
        skills = list(self._skills.values())
        
        if category:
            skills = [s for s in skills if s.category == category]
        
        if enabled_only:
            skills = [s for s in skills if s.enabled]
        
        return skills
    
    def get_node(self, name: str) -> Optional[BaseNode]:
        """
        获取技能节点实例
        
        Args:
            name: 技能名称
        
        Returns:
            Optional[BaseNode]: 节点实例
        """
        # 检查缓存
        if name in self._instances:
            return self._instances[name]
        
        # 加载技能
        skill_info = self._skills.get(name)
        if not skill_info:
            logger.error(f"技能不存在：{name}")
            return None
        
        try:
            # 动态导入模块
            module = importlib.import_module(skill_info.module_path)
            node_class = getattr(module, skill_info.class_name)
            
            # 创建实例
            instance = node_class()
            self._instances[name] = instance
            skill_info.node_class = node_class
            
            logger.info(f"技能节点加载成功：{name}")
            return instance
        
        except Exception as e:
            logger.error(f"技能节点加载失败：{name}, 错误：{e}")
            return None
    
    async def execute(
        self,
        name: str,
        context: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> SkillExecutionResult:
        """
        执行技能
        
        Args:
            name: 技能名称
            context: 执行上下文
            config: 配置
        
        Returns:
            SkillExecutionResult: 执行结果
        """
        import time
        
        start_time = time.time()
        
        # 获取节点
        node = self.get_node(name)
        if not node:
            result = SkillExecutionResult(
                skill_name=name,
                result=NodeResult(
                    status=NodeStatus.FAILED,
                    node_name=name,
                    error=f"技能不存在或未加载：{name}"
                ),
                duration=time.time() - start_time
            )
            self._record_execution(result)
            return result
        
        # 验证输入
        is_valid, error_msg = node.validate_input(context)
        if not is_valid:
            result = SkillExecutionResult(
                skill_name=name,
                result=NodeResult(
                    status=NodeStatus.FAILED,
                    node_name=name,
                    error=error_msg
                ),
                duration=time.time() - start_time
            )
            self._record_execution(result)
            return result
        
        # 执行
        node_result = await node.run(context)
        
        result = SkillExecutionResult(
            skill_name=name,
            result=node_result,
            duration=time.time() - start_time
        )
        
        self._record_execution(result)
        return result
    
    def _record_execution(self, result: SkillExecutionResult) -> None:
        """记录执行历史"""
        self._execution_history.append(result)
        
        # 限制历史记录数量
        if len(self._execution_history) > self._max_history:
            self._execution_history = self._execution_history[-self._max_history:]
    
    def get_execution_history(
        self,
        skill_name: Optional[str] = None,
        limit: int = 10
    ) -> List[SkillExecutionResult]:
        """
        获取执行历史
        
        Args:
            skill_name: 按技能名称筛选
            limit: 限制数量
        
        Returns:
            List[SkillExecutionResult]: 执行历史
        """
        history = self._execution_history
        
        if skill_name:
            history = [h for h in history if h.skill_name == skill_name]
        
        return history[-limit:]
    
    def enable(self, name: str) -> bool:
        """启用技能"""
        if name in self._skills:
            self._skills[name].enabled = True
            logger.info(f"技能已启用：{name}")
            return True
        return False
    
    def disable(self, name: str) -> bool:
        """禁用技能"""
        if name in self._skills:
            self._skills[name].enabled = False
            if name in self._instances:
                del self._instances[name]
            logger.info(f"技能已禁用：{name}")
            return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_executions = len(self._execution_history)
        successful = sum(1 for h in self._execution_history if h.result.status == NodeStatus.COMPLETED)
        failed = sum(1 for h in self._execution_history if h.result.status == NodeStatus.FAILED)
        
        avg_duration = (
            sum(h.duration for h in self._execution_history) / total_executions
            if total_executions > 0 else 0
        )
        
        return {
            "total_skills": len(self._skills),
            "enabled_skills": sum(1 for s in self._skills.values() if s.enabled),
            "total_executions": total_executions,
            "successful_executions": successful,
            "failed_executions": failed,
            "success_rate": successful / total_executions if total_executions > 0 else 0,
            "average_duration": avg_duration
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "skills": {name: info.to_dict() for name, info in self._skills.items()},
            "stats": self.get_stats()
        }


# 全局注册表实例
_registry: Optional[SkillRegistry] = None


def get_registry() -> SkillRegistry:
    """获取全局注册表实例"""
    global _registry
    if _registry is None:
        _registry = SkillRegistry.get_instance()
    return _registry


def register_default_skills() -> None:
    """注册默认技能"""
    registry = get_registry()
    
    # 数据处理类
    registry.register(
        name="data_analysis",
        class_name="DataAnalysisNode",
        category=SkillCategory.DATA_PROCESSING,
        description="数据分析技能",
        module_path="agentm.src.nodes.skill_nodes.data_analysis_node"
    )
    
    # 研究类
    registry.register(
        name="deep_research",
        class_name="DeepResearchNode",
        category=SkillCategory.DATA_PROCESSING,
        description="深度研究技能",
        module_path="agentm.src.nodes.skill_nodes.deep_research_node"
    )
    
    registry.register(
        name="github_research",
        class_name="GitHubResearchNode",
        category=SkillCategory.DATA_PROCESSING,
        description="GitHub 代码库研究技能",
        module_path="agentm.src.nodes.skill_nodes.github_research_node"
    )
    
    # 内容生成类
    registry.register(
        name="image_generation",
        class_name="ImageGenerationNode",
        category=SkillCategory.CONTENT_GENERATION,
        description="图片生成技能",
        module_path="agentm.src.nodes.skill_nodes.image_generation_node"
    )
    
    registry.register(
        name="video_generation",
        class_name="VideoGenerationNode",
        category=SkillCategory.CONTENT_GENERATION,
        description="视频生成技能",
        module_path="agentm.src.nodes.skill_nodes.video_generation_node"
    )
    
    registry.register(
        name="ppt_generation",
        class_name="PPTGenerationNode",
        category=SkillCategory.CONTENT_GENERATION,
        description="PPT 生成技能",
        module_path="agentm.src.nodes.skill_nodes.ppt_generation_node"
    )
    
    registry.register(
        name="frontend_design",
        class_name="FrontendDesignNode",
        category=SkillCategory.CONTENT_GENERATION,
        description="前端设计技能",
        module_path="agentm.src.nodes.skill_nodes.frontend_design_node"
    )
    
    # 开发工具类
    registry.register(
        name="coding_agent",
        class_name="CodingAgentNode",
        category=SkillCategory.DEVELOPMENT_TOOLS,
        description="编码助手技能",
        module_path="agentm.src.nodes.skill_nodes.coding_agent_node"
    )
    
    # 其他工具类
    registry.register(
        name="chart_visualization",
        class_name="ChartVisualizationNode",
        category=SkillCategory.UTILITY_TOOLS,
        description="图表可视化技能",
        module_path="agentm.src.nodes.skill_nodes.chart_visualization_node"
    )
    
    registry.register(
        name="weather",
        class_name="WeatherNode",
        category=SkillCategory.UTILITY_TOOLS,
        description="天气查询技能",
        module_path="agentm.src.nodes.skill_nodes.weather_node"
    )
    
    registry.register(
        name="whisper",
        class_name="WhisperNode",
        category=SkillCategory.UTILITY_TOOLS,
        description="语音识别技能",
        module_path="agentm.src.nodes.skill_nodes.whisper_node"
    )
    
    registry.register(
        name="pdf",
        class_name="PDFNode",
        category=SkillCategory.UTILITY_TOOLS,
        description="PDF 处理技能",
        module_path="agentm.src.nodes.skill_nodes.pdf_node"
    )
    
    logger.info(f"已注册 {len(registry.list_skills())} 个默认技能")
