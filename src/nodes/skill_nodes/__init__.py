"""
Skill Nodes - 全栈技能节点适配器

提供对各类技能的统一接口封装，用于工作流集成。
"""

from ..base_node import BaseNode, NodeResult, NodeStatus

from .data_analysis_node import DataAnalysisNode
from .deep_research_node import DeepResearchNode
from .github_research_node import GitHubResearchNode
from .image_generation_node import ImageGenerationNode
from .video_generation_node import VideoGenerationNode
from .ppt_generation_node import PPTGenerationNode
from .frontend_design_node import FrontendDesignNode
from .coding_agent_node import CodingAgentNode
from .chart_visualization_node import ChartVisualizationNode
from .weather_node import WeatherNode
from .whisper_node import WhisperNode
from .pdf_node import PDFNode

__all__ = [
    # Base
    "BaseNode",
    "NodeResult",
    "NodeStatus",
    
    # Skill Nodes
    "DataAnalysisNode",
    "DeepResearchNode",
    "GitHubResearchNode",
    "ImageGenerationNode",
    "VideoGenerationNode",
    "PPTGenerationNode",
    "FrontendDesignNode",
    "CodingAgentNode",
    "ChartVisualizationNode",
    "WeatherNode",
    "WhisperNode",
    "PDFNode",
]
