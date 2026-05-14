"""
Video Generation Node - 视频生成节点

集成 video-generation 技能，提供视频生成能力。
"""

import logging
from typing import Any, Dict, List, Optional

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


class VideoGenerationNode(BaseNode):
    """视频生成节点"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("video_generation", config)
        self._default_model = config.get("model", "sora") if config else "sora"
        self._default_duration = config.get("duration", 5) if config else 5  # 秒
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """
        执行视频生成
        
        Args:
            context: 执行上下文，包含:
                - prompt: 视频描述
                - model: 模型名称
                - duration: 视频时长 (秒)
                - frames: 输入帧列表 (可选)
                - output_path: 输出路径
        
        Returns:
            NodeResult: 生成的视频信息
        """
        try:
            prompt = context.get("prompt")
            model = context.get("model", self._default_model)
            duration = context.get("duration", self._default_duration)
            frames = context.get("frames", [])
            output_path = context.get("output_path")
            
            if not prompt and not frames:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    error="缺少必需参数：prompt 或 frames",
                    node_name=self.name
                )
            
            # 调用 video-generation 技能
            result = await self._generate_video(
                prompt=prompt,
                model=model,
                duration=duration,
                frames=frames,
                output_path=output_path
            )
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                output=result,
                node_name=self.name
            )
        
        except Exception as e:
            logger.error(f"视频生成失败：{e}")
            return NodeResult(
                status=NodeStatus.FAILED,
                error=str(e),
                node_name=self.name
            )
    
    async def _generate_video(
        self,
        prompt: Optional[str] = None,
        model: str = "sora",
        duration: int = 5,
        frames: Optional[List[str]] = None,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成视频
        """
        import subprocess
        from pathlib import Path
        
        # 使用 ffmpeg 从帧生成视频（降级方案）
        if frames:
            return await self._generate_from_frames(frames, duration, output_path)
        
        # 调用视频生成 API（需要相应 API key）
        if model == "sora":
            return await self._generate_with_sora(prompt, duration, output_path)
        else:
            return await self._generate_with_stable_video(prompt, duration, output_path)
    
    async def _generate_from_frames(
        self,
        frames: List[str],
        duration: int,
        output_path: Optional[str]
    ) -> Dict[str, Any]:
        """
        从帧生成视频
        """
        import subprocess
        from pathlib import Path
        
        if not output_path:
            output_path = "output_video.mp4"
        
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建帧列表文件
        list_file = path.parent / "frames.txt"
        with open(list_file, "w") as f:
            for frame in frames:
                f.write(f"file '{frame}'\n")
                f.write(f"duration {duration / len(frames):.2f}\n")
        
        # 使用 ffmpeg 合成视频
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg 失败：{result.stderr}")
        
        return {
            "output_path": str(path),
            "frames_count": len(frames),
            "duration": duration,
            "format": "mp4"
        }
    
    async def _generate_with_sora(
        self,
        prompt: str,
        duration: int,
        output_path: Optional[str]
    ) -> Dict[str, Any]:
        """
        使用 Sora 生成视频（模拟）
        """
        # Sora API 尚未公开，这里提供模拟实现
        logger.warning("Sora API 尚未公开，使用模拟实现")
        
        return {
            "status": "simulated",
            "prompt": prompt,
            "model": "sora",
            "duration": duration,
            "message": "Sora API 尚未公开，此为模拟响应"
        }
    
    async def _generate_with_stable_video(
        self,
        prompt: str,
        duration: int,
        output_path: Optional[str]
    ) -> Dict[str, Any]:
        """
        使用 Stable Video Diffusion 生成视频
        """
        import os
        import requests
        
        api_key = os.environ.get("STABILITY_API_KEY")
        
        if not api_key:
            raise RuntimeError("缺少 STABILITY_API_KEY 环境变量")
        
        # Stability AI API
        url = "https://api.stability.ai/v2beta/image-to-video"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }
        
        # 这里需要先生成初始帧
        # 简化实现：返回模拟结果
        return {
            "status": "simulated",
            "prompt": prompt,
            "model": "stable-video",
            "duration": duration,
            "message": "需要实现完整的 Stability AI 视频生成流程"
        }
    
    def get_schema(self) -> Dict[str, Any]:
        """返回节点输入输出 schema"""
        return {
            "inputs": {
                "prompt": {"type": "string", "required": False, "description": "视频描述"},
                "model": {
                    "type": "string",
                    "required": False,
                    "default": "sora",
                    "enum": ["sora", "stable-video", "runway"]
                },
                "duration": {"type": "integer", "required": False, "default": 5, "minimum": 1, "maximum": 60},
                "frames": {
                    "type": "array",
                    "items": {"type": "string"},
                    "required": False,
                    "description": "输入帧文件路径列表"
                },
                "output_path": {"type": "string", "required": False, "description": "输出文件路径"}
            },
            "outputs": {
                "generated_video": {"type": "object", "description": "生成的视频信息"}
            }
        }
