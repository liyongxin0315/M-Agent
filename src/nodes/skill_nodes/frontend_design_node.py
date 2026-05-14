"""
Frontend Design Node - 前端设计节点

集成 frontend-design 技能，提供前端页面设计能力。
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from pathlib import Path
from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


class FrontendDesignNode(BaseNode):
    """前端设计节点"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("frontend_design", config)
        self._default_framework = config.get("framework", "react") if config else "react"
        self._default_styling = config.get("styling", "tailwind") if config else "tailwind"
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """
        执行前端设计
        
        Args:
            context: 执行上下文，包含:
                - description: 页面描述
                - framework: 前端框架
                - styling: CSS 框架
                - components: 需要的组件列表
                - output_dir: 输出目录
        
        Returns:
            NodeResult: 生成的前端代码信息
        """
        try:
            description = context.get("description")
            framework = context.get("framework", self._default_framework)
            styling = context.get("styling", self._default_styling)
            components = context.get("components", [])
            output_dir = context.get("output_dir")
            
            if not description:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    error="缺少必需参数：description",
                    node_name=self.name
                )
            
            # 调用 frontend-design 技能
            result = await self._generate_frontend(
                description=description,
                framework=framework,
                styling=styling,
                components=components,
                output_dir=output_dir
            )
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                output=result,
                node_name=self.name
            )
        
        except Exception as e:
            logger.error(f"前端设计失败：{e}")
            return NodeResult(
                status=NodeStatus.FAILED,
                error=str(e),
                node_name=self.name
            )
    
    async def _generate_frontend(
        self,
        description: str,
        framework: str = "react",
        styling: str = "tailwind",
        components: Optional[List[str]] = None,
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成前端代码
        """
        import subprocess
        from pathlib import Path
        
        if not output_dir:
            output_dir = "frontend_output"
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 根据框架生成不同的代码
        if framework == "react":
            return await self._generate_react(description, styling, components, output_path)
        elif framework == "vue":
            return await self._generate_vue(description, styling, components, output_path)
        elif framework == "html":
            return await self._generate_html(description, styling, output_path)
        else:
            raise ValueError(f"不支持的框架：{framework}")
    
    async def _generate_react(
        self,
        description: str,
        styling: str,
        components: Optional[List[str]],
        output_path: Path
    ) -> Dict[str, Any]:
        """
        生成 React 代码
        """
        # 创建 package.json
        package_json = {
            "name": "generated-app",
            "version": "1.0.0",
            "private": True,
            "dependencies": {
                "react": "^18.2.0",
                "react-dom": "^18.2.0"
            }
        }
        
        if styling == "tailwind":
            package_json["dependencies"]["tailwindcss"] = "^3.4.0"
        
        import json
        with open(output_path / "package.json", "w") as f:
            json.dump(package_json, f, indent=2)
        
        # 创建主组件
        app_component = self._create_react_app_component(description, styling)
        with open(output_path / "App.tsx", "w") as f:
            f.write(app_component)
        
        # 创建入口文件
        index_content = """import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

const root = ReactDOM.createRoot(document.getElementById('root') as HTMLElement);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
"""
        with open(output_path / "index.tsx", "w") as f:
            f.write(index_content)
        
        # 创建样式文件
        css_content = self._create_css_content(styling)
        with open(output_path / "index.css", "w") as f:
            f.write(css_content)
        
        return {
            "framework": "react",
            "styling": styling,
            "output_dir": str(output_path),
            "files": ["package.json", "App.tsx", "index.tsx", "index.css"],
            "description": description
        }
    
    async def _generate_vue(
        self,
        description: str,
        styling: str,
        components: Optional[List[str]],
        output_path: Path
    ) -> Dict[str, Any]:
        """
        生成 Vue 代码
        """
        # 创建 App.vue
        app_content = f"""<template>
  <div class="app-container">
    <h1>Generated App</h1>
    <p>{description}</p>
  </div>
</template>

<script setup lang="ts">
// Auto-generated Vue component
</script>

<style scoped>
.app-container {{
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}}
</style>
"""
        with open(output_path / "App.vue", "w") as f:
            f.write(app_content)
        
        return {
            "framework": "vue",
            "styling": styling,
            "output_dir": str(output_path),
            "files": ["App.vue"],
            "description": description
        }
    
    async def _generate_html(
        self,
        description: str,
        styling: str,
        output_path: Path
    ) -> Dict[str, Any]:
        """
        生成纯 HTML 代码
        """
        cdn_links = {
            "tailwind": '<script src="https://cdn.tailwindcss.com"></script>',
            "bootstrap": '<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">',
            "default": ""
        }
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Generated Page</title>
  {cdn_links.get(styling, "")}
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      padding: 2rem;
      max-width: 1200px;
      margin: 0 auto;
    }}
  </style>
</head>
<body>
  <h1>Generated Page</h1>
  <p>{description}</p>
</body>
</html>
"""
        with open(output_path / "index.html", "w") as f:
            f.write(html_content)
        
        return {
            "framework": "html",
            "styling": styling,
            "output_dir": str(output_path),
            "files": ["index.html"],
            "description": description
        }
    
    def _create_react_app_component(self, description: str, styling: str) -> str:
        """创建 React App 组件"""
        return f"""import React from 'react';
import './index.css';

function App() {{
  return (
    <div className="app-container">
      <h1 className="app-title">Generated App</h1>
      <p className="app-description">{description}</p>
    </div>
  );
}}

export default App;
"""
    
    def _create_css_content(self, styling: str) -> str:
        """创建 CSS 内容"""
        if styling == "tailwind":
            return """@tailwind base;
@tailwind components;
@tailwind utilities;

.app-container {
  @apply p-8 max-w-6xl mx-auto;
}

.app-title {
  @apply text-4xl font-bold mb-4;
}

.app-description {
  @apply text-lg text-gray-600;
}
"""
        return """
.app-container {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.app-title {
  font-size: 2rem;
  font-weight: bold;
  margin-bottom: 1rem;
}

.app-description {
  font-size: 1.125rem;
  color: #4b5563;
}
"""
    
    def get_schema(self) -> Dict[str, Any]:
        """返回节点输入输出 schema"""
        return {
            "inputs": {
                "description": {"type": "string", "required": True, "description": "页面描述"},
                "framework": {
                    "type": "string",
                    "required": False,
                    "default": "react",
                    "enum": ["react", "vue", "html"]
                },
                "styling": {
                    "type": "string",
                    "required": False,
                    "default": "tailwind",
                    "enum": ["tailwind", "bootstrap", "default"]
                },
                "components": {
                    "type": "array",
                    "items": {"type": "string"},
                    "required": False,
                    "description": "需要的组件列表"
                },
                "output_dir": {"type": "string", "required": False, "description": "输出目录"}
            },
            "outputs": {
                "frontend_code": {"type": "object", "description": "生成的前端代码信息"}
            }
        }
