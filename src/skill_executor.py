"""
Skill Executor - 统一技能执行器

提供对所有外部技能的统一调用接口，支持同步/异步执行、批量处理、缓存等功能。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from nodes.skill_nodes.base_node import BaseNode, NodeResult, NodeStatus
from .nodes.skill_nodes import (
    DataAnalysisNode,
    DeepResearchNode,
    ImageGenerationNode,
    VideoGenerationNode,
    PPTGenerationNode,
    FrontendDesignNode,
    CodingAgentNode,
    ChartVisualizationNode,
    WeatherNode,
    WhisperNode,
    PDFNode,
)

logger = logging.getLogger(__name__)


class SkillType(Enum):
    """技能类型枚举"""
    DATA_ANALYSIS = "data_analysis"
    DEEP_RESEARCH = "deep_research"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    PPT_GENERATION = "ppt_generation"
    FRONTEND_DESIGN = "frontend_design"
    CODING_AGENT = "coding_agent"
    CHART_VISUALIZATION = "chart_visualization"
    WEATHER = "weather"
    WHISPER = "whisper"
    PDF = "pdf"


@dataclass
class SkillConfig:
    """技能配置"""
    skill_type: SkillType
    enabled: bool = True
    timeout: int = 300  # 秒
    retry_count: int = 3
    cache_enabled: bool = False
    cache_ttl: int = 3600  # 秒
    custom_config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillExecution:
    """技能执行记录"""
    skill_type: SkillType
    input_data: Dict[str, Any]
    result: Optional[NodeResult] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    cached: bool = False


class SkillExecutor:
    """
    统一技能执行器
    
    提供对所有外部技能的统一访问接口，支持：
    - 同步/异步执行
    - 批量处理
    - 结果缓存
    - 自动重试
    - 执行监控
    """
    
    def __init__(self, configs: Optional[List[SkillConfig]] = None):
        """
        初始化执行器
        
        Args:
            configs: 技能配置列表
        """
        self._nodes: Dict[SkillType, BaseNode] = {}
        self._configs: Dict[SkillType, SkillConfig] = {}
        self._cache: Dict[str, NodeResult] = {}
        self._execution_history: List[SkillExecution] = []
        
        # 注册所有技能
        self._register_default_skills()
        
        # 应用自定义配置
        if configs:
            for config in configs:
                self._configs[config.skill_type] = config
    
    def _register_default_skills(self):
        """注册默认技能"""
        self._nodes[SkillType.DATA_ANALYSIS] = DataAnalysisNode()
        self._nodes[SkillType.DEEP_RESEARCH] = DeepResearchNode()
        self._nodes[SkillType.IMAGE_GENERATION] = ImageGenerationNode()
        self._nodes[SkillType.VIDEO_GENERATION] = VideoGenerationNode()
        self._nodes[SkillType.PPT_GENERATION] = PPTGenerationNode()
        self._nodes[SkillType.FRONTEND_DESIGN] = FrontendDesignNode()
        self._nodes[SkillType.CODING_AGENT] = CodingAgentNode()
        self._nodes[SkillType.CHART_VISUALIZATION] = ChartVisualizationNode()
        self._nodes[SkillType.WEATHER] = WeatherNode()
        self._nodes[SkillType.WHISPER] = WhisperNode()
        self._nodes[SkillType.PDF] = PDFNode()
        
        # 默认配置
        for skill_type in SkillType:
            self._configs[skill_type] = SkillConfig(skill_type=skill_type)
    
    def _generate_cache_key(self, skill_type: SkillType, input_data: Dict[str, Any]) -> str:
        """生成缓存键"""
        import hashlib
        data_str = str(sorted(input_data.items()))
        hash_key = hashlib.md5(data_str.encode()).hexdigest()
        return f"{skill_type.value}:{hash_key}"
    
    async def execute(
        self,
        skill_type: Union[SkillType, str],
        input_data: Dict[str, Any],
        use_cache: bool = True
    ) -> NodeResult:
        """
        执行单个技能
        
        Args:
            skill_type: 技能类型
            input_data: 输入数据
            use_cache: 是否使用缓存
        
        Returns:
            NodeResult: 执行结果
        """
        # 转换字符串为枚举
        if isinstance(skill_type, str):
            try:
                skill_type = SkillType(skill_type)
            except ValueError:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    error=f"未知技能类型：{skill_type}",
                    node_name="SkillExecutor"
                )
        
        # 检查技能是否启用
        config = self._configs.get(skill_type)
        if not config or not config.enabled:
            return NodeResult(
                status=NodeStatus.FAILED,
                error=f"技能未启用：{skill_type.value}",
                node_name="SkillExecutor"
            )
        
        # 检查缓存
        if use_cache and config.cache_enabled:
            cache_key = self._generate_cache_key(skill_type, input_data)
            if cache_key in self._cache:
                logger.debug(f"使用缓存结果：{skill_type.value}")
                cached_result = self._cache[cache_key]
                cached_result.metadata["cached"] = True
                return cached_result
        
        # 获取节点
        node = self._nodes.get(skill_type)
        if not node:
            return NodeResult(
                status=NodeStatus.FAILED,
                error=f"技能未注册：{skill_type.value}",
                node_name="SkillExecutor"
            )
        
        # 验证输入
        valid, error_msg = node.validate_input(input_data)
        if not valid:
            return NodeResult(
                status=NodeStatus.FAILED,
                error=error_msg,
                node_name="SkillExecutor"
            )
        
        # 执行技能
        execution = SkillExecution(
            skill_type=skill_type,
            input_data=input_data,
            start_time=datetime.now()
        )
        
        try:
            result = await asyncio.wait_for(
                node.execute(input_data),
                timeout=config.timeout
            )
            
            execution.result = result
            execution.end_time = datetime.now()
            
            # 缓存结果
            if config.cache_enabled and result.status == NodeStatus.COMPLETED:
                cache_key = self._generate_cache_key(skill_type, input_data)
                self._cache[cache_key] = result
            
            # 记录执行历史
            self._execution_history.append(execution)
            
            return result
        
        except asyncio.TimeoutError:
            error_msg = f"技能执行超时（{config.timeout}秒）"
            logger.error(error_msg)
            execution.error = error_msg
            execution.end_time = datetime.now()
            self._execution_history.append(execution)
            
            return NodeResult(
                status=NodeStatus.FAILED,
                error=error_msg,
                node_name="SkillExecutor"
            )
        
        except Exception as e:
            error_msg = f"技能执行失败：{str(e)}"
            logger.error(error_msg)
            execution.error = error_msg
            execution.end_time = datetime.now()
            self._execution_history.append(execution)
            
            return NodeResult(
                status=NodeStatus.FAILED,
                error=error_msg,
                node_name="SkillExecutor"
            )
    
    async def execute_batch(
        self,
        executions: List[Dict[str, Any]],
        parallel: bool = True
    ) -> List[NodeResult]:
        """
        批量执行技能
        
        Args:
            executions: 执行列表，每项包含：
                - skill_type: 技能类型
                - input_data: 输入数据
                - use_cache: 是否使用缓存（可选）
            parallel: 是否并行执行
        
        Returns:
            List[NodeResult]: 执行结果列表
        """
        if parallel:
            tasks = [
                self.execute(
                    exec_item["skill_type"],
                    exec_item["input_data"],
                    exec_item.get("use_cache", True)
                )
                for exec_item in executions
            ]
            return await asyncio.gather(*tasks, return_exceptions=False)
        else:
            results = []
            for exec_item in executions:
                result = await self.execute(
                    exec_item["skill_type"],
                    exec_item["input_data"],
                    exec_item.get("use_cache", True)
                )
                results.append(result)
            return results
    
    def clear_cache(self, skill_type: Optional[SkillType] = None):
        """
        清除缓存
        
        Args:
            skill_type: 技能类型，None 表示清除所有
        """
        if skill_type:
            keys_to_remove = [
                key for key in self._cache.keys()
                if key.startswith(f"{skill_type.value}:")
            ]
            for key in keys_to_remove:
                del self._cache[key]
            logger.info(f"已清除技能 {skill_type.value} 的缓存")
        else:
            self._cache.clear()
            logger.info("已清除所有缓存")
    
    def get_execution_history(
        self,
        skill_type: Optional[SkillType] = None,
        limit: int = 100
    ) -> List[SkillExecution]:
        """
        获取执行历史
        
        Args:
            skill_type: 技能类型过滤
            limit: 返回数量限制
        
        Returns:
            List[SkillExecution]: 执行历史记录
        """
        history = self._execution_history
        
        if skill_type:
            history = [h for h in history if h.skill_type == skill_type]
        
        return history[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            Dict: 统计数据
        """
        stats = {
            "total_executions": len(self._execution_history),
            "cache_size": len(self._cache),
            "skills": {}
        }
        
        for skill_type in SkillType:
            history = [h for h in self._execution_history if h.skill_type == skill_type]
            successful = sum(1 for h in history if h.result and h.result.status == NodeStatus.COMPLETED)
            failed = sum(1 for h in history if h.result and h.result.status == NodeStatus.FAILED)
            
            stats["skills"][skill_type.value] = {
                "total": len(history),
                "successful": successful,
                "failed": failed,
                "enabled": self._configs[skill_type].enabled
            }
        
        return stats
    
    def enable_skill(self, skill_type: Union[SkillType, str]):
        """启用技能"""
        if isinstance(skill_type, str):
            skill_type = SkillType(skill_type)
        if skill_type in self._configs:
            self._configs[skill_type].enabled = True
    
    def disable_skill(self, skill_type: Union[SkillType, str]):
        """禁用技能"""
        if isinstance(skill_type, str):
            skill_type = SkillType(skill_type)
        if skill_type in self._configs:
            self._configs[skill_type].enabled = False
    
    def get_available_skills(self) -> List[str]:
        """获取可用技能列表"""
        return [
            config.skill_type.value
            for config in self._configs.values()
            if config.enabled
        ]
