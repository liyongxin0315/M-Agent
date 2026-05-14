"""
Image Generation Node - 图片生成节点

集成 image-generation 技能，提供图片生成能力。
"""

import logging
from typing import Any, Dict, Optional

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


class ImageGenerationNode(BaseNode):
    """图片生成节点"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("image_generation", config)
        self._default_model = config.get("model", "dall-e-3") if config else "dall-e-3"
        self._default_size = config.get("size", "1024x1024") if config else "1024x1024"
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """
        执行图片生成
        
        Args:
            context: 执行上下文，包含:
                - prompt: 图片描述
                - model: 模型名称
                - size: 图片尺寸
                - n: 生成数量
                - output_path: 输出路径
        
        Returns:
            NodeResult: 生成的图片信息
        """
        try:
            prompt = context.get("prompt")
            model = context.get("model", self._default_model)
            size = context.get("size", self._default_size)
            n = context.get("n", 1)
            output_path = context.get("output_path")
            
            if not prompt:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    error="缺少必需参数：prompt",
                    node_name=self.name
                )
            
            # 调用 image-generation 技能
            result = await self._generate_image(
                prompt=prompt,
                model=model,
                size=size,
                n=n,
                output_path=output_path
            )
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                output=result,
                node_name=self.name
            )
        
        except Exception as e:
            logger.error(f"图片生成失败：{e}")
            return NodeResult(
                status=NodeStatus.FAILED,
                error=str(e),
                node_name=self.name
            )
    
    async def _generate_image(
        self,
        prompt: str,
        model: str = "dall-e-3",
        size: str = "1024x1024",
        n: int = 1,
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成图片
        """
        import os
        import requests
        from pathlib import Path
        
        # 使用 OpenAI API 生成图片
        api_key = os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            raise RuntimeError("缺少 OPENAI_API_KEY 环境变量")
        
        url = "https://api.openai.com/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "prompt": prompt,
            "n": n,
            "size": size
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        response.raise_for_status()
        
        data = response.json()
        
        result = {
            "prompt": prompt,
            "model": model,
            "size": size,
            "images": []
        }
        
        # 下载图片
        for i, img_data in enumerate(data.get("data", [])):
            img_url = img_data.get("url")
            
            if output_path:
                # 下载并保存图片
                img_response = requests.get(img_url, timeout=30)
                img_response.raise_for_status()
                
                path = Path(output_path)
                if path.suffix == "":
                    path = path.with_suffix(".png")
                path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(path, "wb") as f:
                    f.write(img_response.content)
                
                result["images"].append({
                    "index": i,
                    "local_path": str(path),
                    "url": img_url
                })
            else:
                result["images"].append({
                    "index": i,
                    "url": img_url
                })
        
        return result
    
    def get_schema(self) -> Dict[str, Any]:
        """返回节点输入输出 schema"""
        return {
            "inputs": {
                "prompt": {"type": "string", "required": True, "description": "图片描述"},
                "model": {
                    "type": "string",
                    "required": False,
                    "default": "dall-e-3",
                    "enum": ["dall-e-3", "dall-e-2", "stable-diffusion"]
                },
                "size": {
                    "type": "string",
                    "required": False,
                    "default": "1024x1024",
                    "enum": ["1024x1024", "1792x1024", "1024x1792", "512x512", "256x256"]
                },
                "n": {"type": "integer", "required": False, "default": 1, "minimum": 1, "maximum": 10},
                "output_path": {"type": "string", "required": False, "description": "输出文件路径"}
            },
            "outputs": {
                "generated_images": {"type": "object", "description": "生成的图片信息"}
            }
        }
