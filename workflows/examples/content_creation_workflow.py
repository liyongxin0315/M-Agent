"""
Content Creation Workflow - 内容创作工作流示例

演示如何使用技能节点进行内容创作（PPT、图片、前端页面）。
"""

import logging
from typing import Any, Dict, List, Optional

from agentm.workflows.workflow_engine import BaseWorkflow, WorkflowResult
from agentm.src.nodes.skill_nodes import (
    PPTGenerationNode,
    ImageGenerationNode,
    FrontendDesignNode
)

logger = logging.getLogger(__name__)


class ContentCreationWorkflow(BaseWorkflow):
    """内容创作工作流"""
    
    def _setup_steps(self) -> None:
        """设置工作流步骤"""
        # 初始化技能节点
        self._ppt_node = PPTGenerationNode(self.config.get("ppt_config"))
        self._image_node = ImageGenerationNode(self.config.get("image_config"))
        self._frontend_node = FrontendDesignNode(self.config.get("frontend_config"))
        
        # 添加步骤
        self.engine.add_step(
            name="generate_ppt",
            func=self._generate_ppt,
            description="生成 PPT 演示文稿",
            retry_count=1
        )
        
        self.engine.add_step(
            name="generate_images",
            func=self._generate_images,
            description="生成配图",
            skip_on_error=True
        )
        
        self.engine.add_step(
            name="create_landing_page",
            func=self._create_landing_page,
            description="创建落地页",
            skip_on_error=True
        )
        
        self.engine.add_step(
            name="package_deliverables",
            func=self._package_deliverables,
            description="打包交付物",
            retry_count=1
        )
    
    def _generate_ppt(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成 PPT"""
        title = self.config.get("title", "演示文稿")
        content = self.config.get("content", "")
        theme = self.config.get("theme", "default")
        
        logger.info(f"生成 PPT：{title}")
        
        context["ppt_title"] = title
        context["ppt_theme"] = theme
        
        return {"status": "started", "title": title}
    
    async def _generate_ppt_execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行 PPT 生成（异步）"""
        title = context.get("ppt_title", self.config.get("title"))
        content = self.config.get("content", "")
        output_path = self.config.get("ppt_output_path", "output/presentation.pptx")
        
        ppt_context = {
            "title": title,
            "content": content,
            "theme": self.config.get("theme", "default"),
            "output_path": output_path
        }
        
        result = await self._ppt_node.execute(ppt_context)
        
        if result.status.value == "failed":
            raise RuntimeError(f"PPT 生成失败：{result.error}")
        
        context["ppt_path"] = result.output.get("output_path")
        context["ppt_slides_count"] = result.output.get("slides_count", 0)
        
        return result.output
    
    async def _generate_images(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成配图"""
        prompts = self.config.get("image_prompts", [])
        
        if not prompts:
            logger.info("未配置图片生成提示词，跳过")
            return {"status": "skipped", "reason": "no prompts"}
        
        logger.info(f"生成 {len(prompts)} 张图片")
        
        image_paths = []
        
        for i, prompt in enumerate(prompts):
            image_context = {
                "prompt": prompt,
                "model": self.config.get("image_model", "dall-e-3"),
                "size": self.config.get("image_size", "1024x1024"),
                "output_path": f"output/images/image_{i+1}.png"
            }
            
            result = await self._image_node.execute(image_context)
            
            if result.status.value == "completed":
                img_info = result.output.get("images", [{}])[0]
                image_paths.append(img_info.get("local_path") or img_info.get("url"))
        
        context["image_paths"] = image_paths
        return {"images": image_paths}
    
    async def _create_landing_page(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """创建落地页"""
        description = self.config.get("landing_page_description", "")
        
        if not description:
            logger.info("未配置落地页描述，跳过")
            return {"status": "skipped", "reason": "no description"}
        
        logger.info("创建落地页")
        
        frontend_context = {
            "description": description,
            "framework": self.config.get("frontend_framework", "html"),
            "styling": self.config.get("frontend_styling", "tailwind"),
            "output_dir": "output/landing_page"
        }
        
        result = await self._frontend_node.execute(frontend_context)
        
        if result.status.value == "completed":
            context["landing_page_path"] = result.output.get("output_dir")
            context["landing_page_files"] = result.output.get("files", [])
        
        return result.output
    
    def _package_deliverables(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """打包交付物"""
        logger.info("打包交付物")
        
        deliverables = {
            "ppt": {
                "path": context.get("ppt_path"),
                "slides": context.get("ppt_slides_count", 0),
                "status": "completed" if context.get("ppt_path") else "failed"
            },
            "images": {
                "paths": context.get("image_paths", []),
                "count": len(context.get("image_paths", [])),
                "status": "completed" if context.get("image_paths") else "skipped"
            },
            "landing_page": {
                "path": context.get("landing_page_path"),
                "files": context.get("landing_page_files", []),
                "status": "completed" if context.get("landing_page_path") else "skipped"
            }
        }
        
        # 创建交付清单
        manifest = {
            "project": self.config.get("title", "Content Project"),
            "created_at": self._get_timestamp(),
            "deliverables": deliverables,
            "summary": {
                "total_items": (
                    (1 if deliverables["ppt"]["status"] == "completed" else 0) +
                    deliverables["images"]["count"] +
                    (1 if deliverables["landing_page"]["status"] == "completed" else 0)
                )
            }
        }
        
        # 保存清单
        import json
        from pathlib import Path
        
        manifest_path = Path("output/deliverables_manifest.json")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        
        context["manifest_path"] = str(manifest_path)
        return manifest
    
    def _get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    async def execute(self) -> WorkflowResult:
        """执行工作流（支持异步步骤）"""
        # 执行 PPT 生成
        context = {}
        self.engine._context = context
        self._generate_ppt(context)
        await self._generate_ppt_execute(context)
        
        # 执行图片生成
        await self._generate_images(context)
        
        # 执行落地页创建
        await self._create_landing_page(context)
        
        # 打包交付物
        self._package_deliverables(context)
        
        return WorkflowResult(
            workflow_name=self.__class__.__name__,
            status=self.engine.status,
            step_results=[],
            error=context.get("error")
        )
    
    def get_workflow_info(self) -> Dict[str, Any]:
        """获取工作流信息"""
        return {
            "name": "ContentCreationWorkflow",
            "description": "内容创作工作流 - 生成 PPT、配图和落地页",
            "steps": [
                "generate_ppt - 生成 PPT 演示文稿",
                "generate_images - 生成配图",
                "create_landing_page - 创建落地页",
                "package_deliverables - 打包交付物"
            ],
            "config": self.config
        }


async def run_content_creation(
    title: str,
    content: str,
    image_prompts: Optional[List[str]] = None,
    landing_page_description: Optional[str] = None,
    output_dir: str = "output"
) -> WorkflowResult:
    """
    便捷函数：运行内容创作工作流
    
    Args:
        title: 项目标题
        content: PPT 内容
        image_prompts: 图片生成提示词列表
        landing_page_description: 落地页描述
        output_dir: 输出目录
    
    Returns:
        WorkflowResult: 执行结果
    """
    config = {
        "title": title,
        "content": content,
        "image_prompts": image_prompts or [],
        "landing_page_description": landing_page_description,
        "ppt_output_path": f"{output_dir}/presentation.pptx"
    }
    
    workflow = ContentCreationWorkflow(config)
    return await workflow.execute()
