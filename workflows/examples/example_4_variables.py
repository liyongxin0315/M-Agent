"""
示例工作流 4 - 变量和模板系统

演示变量作用域和模板语法。
"""

import asyncio
import logging
from typing import Any, Dict

from agentm.workflows.workflow_engine import BaseWorkflow, WorkflowResult
from agentm import create_variable_system
from agentm.nodes import VariableNode, CodeNode, HttpRequestNode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VariableTemplateWorkflow(BaseWorkflow):
    """变量和模板系统工作流"""

    def _setup_steps(self) -> None:
        """设置工作流步骤"""
        # 步骤 1: 初始化变量
        self.engine.add_step(
            name="init_variables",
            func=self._init_variables,
            description="初始化变量系统",
            retry_count=0
        )

        # 步骤 2: 设置全局配置
        self.engine.add_step(
            name="set_global_config",
            func=self._set_global_config,
            description="设置全局配置",
            retry_count=0
        )

        # 步骤 3: 使用模板生成请求
        self.engine.add_step(
            name="generate_request",
            func=self._generate_request,
            description="使用模板生成 API 请求",
            retry_count=1
        )

        # 步骤 4: 执行 API 调用
        self.engine.add_step(
            name="call_api",
            func=self._call_api,
            description="调用外部 API",
            retry_count=3
        )

        # 步骤 5: 处理响应
        self.engine.add_step(
            name="process_response",
            func=self._process_response,
            description="处理 API 响应",
            retry_count=1
        )

        # 步骤 6: 生成最终报告
        self.engine.add_step(
            name="generate_final_report",
            func=self._generate_final_report,
            description="生成最终报告",
            retry_count=1
        )

    async def _init_variables(self, context: Dict[str, Any]) -> Dict:
        """初始化变量系统"""
        vs = create_variable_system()
        
        # 设置全局变量
        vs.set_global("app_name", "AgentM 工作流引擎", is_readonly=True)
        vs.set_global("version", "2.0.0", is_readonly=True)
        vs.set_global("api_base_url", "https://jsonplaceholder.typicode.com")

        context["variable_system"] = vs
        context["vs"] = vs  # 简写

        logger.info("变量系统已初始化")

        return {
            "initialized": True,
            "global_vars": ["app_name", "version", "api_base_url"]
        }

    async def _set_global_config(self, context: Dict[str, Any]) -> Dict:
        """设置全局配置"""
        vs = context.get("vs")
        if not vs:
            raise Exception("变量系统未初始化")

        # 设置工作流级变量
        workflow_ctx = vs.create_workflow_context("workflow_4")
        
        workflow_ctx.set("user_name", "张三")
        workflow_ctx.set("user_email", "zhangsan@example.com")
        workflow_ctx.set("request_count", 5)
        workflow_ctx.set("debug_mode", True)

        logger.info("工作流变量已设置")

        return {
            "workflow_context": "workflow_4",
            "vars_set": 4
        }

    async def _generate_request(self, context: Dict[str, Any]) -> Dict:
        """使用模板生成请求"""
        vs = context.get("vs")
        if not vs:
            raise Exception("变量系统未初始化")

        # 模板字符串
        url_template = "{{ api_base_url }}/posts?_page={{ page }}&_limit={{ limit }}"
        
        # 渲染 URL
        page = 1
        limit = context.get("request_count", 5)
        
        # 创建临时上下文用于渲染
        temp_ctx = vs.create_workflow_context("temp_render")
        temp_ctx.set("page", page)
        temp_ctx.set("limit", limit)

        rendered_url = vs.render(url_template)
        
        # 手动替换（因为模板在不同上下文）
        rendered_url = rendered_url.replace("{{ page }}", str(page))
        rendered_url = rendered_url.replace("{{ limit }}", str(limit))

        context["api_url"] = rendered_url
        context["page"] = page
        context["limit"] = limit

        logger.info(f"生成的 API URL: {rendered_url}")

        return {
            "url": rendered_url,
            "page": page,
            "limit": limit
        }

    async def _call_api(self, context: Dict[str, Any]) -> Dict:
        """调用 API"""
        api_url = context.get("api_url", "https://jsonplaceholder.typicode.com/posts")

        node = HttpRequestNode("fetch_posts", {
            "url": api_url,
            "method": "GET",
            "timeout": 30.0
        })

        result = await node.execute(context)
        
        if result.status.value == "failed":
            raise Exception(f"API 调用失败：{result.error}")

        posts = result.output.get("body", [])
        context["posts"] = posts

        logger.info(f"获取到 {len(posts)} 条数据")

        return {
            "count": len(posts),
            "source": api_url
        }

    async def _process_response(self, context: Dict[str, Any]) -> Dict:
        """处理响应"""
        posts = context.get("posts", [])
        vs = context.get("vs")
        user_name = context.get("user_name", "用户")

        # 使用 Code 节点处理数据
        code = f"""
posts = context.get('posts', [])

# 处理每条数据
processed = []
for post in posts:
    processed.append({{
        'id': post.get('id'),
        'title': post.get('title', '')[:50] + '...' if len(post.get('title', '')) > 50 else post.get('title', ''),
        'user': '{user_name}',
        'processed': True
    }})

return {{
    'posts': processed,
    'count': len(processed)
}}
"""

        node = CodeNode("process", {
            "language": "python",
            "code": code
        })

        result = await node.execute(context)
        processed_data = result.output

        context["processed_posts"] = processed_data.get("posts", [])

        logger.info(f"处理完成：{processed_data.get('count')} 条")

        return processed_data

    async def _generate_final_report(self, context: Dict[str, Any]) -> Dict:
        """生成最终报告"""
        vs = context.get("vs")
        app_name = vs.get_global("app_name", "AgentM")
        version = vs.get_global("version", "1.0.0")
        
        processed_posts = context.get("processed_posts", [])
        user_name = context.get("user_name", "用户")

        # 使用模板生成报告
        report_template = f"""
# {{app_name}} v{{version}} - 执行报告

## 基本信息
- **用户**: {user_name}
- **生成时间**: {{timestamp}}
- **处理数量**: {{count}}

## 处理结果
{{results}}

## 状态
✅ 执行成功
"""

        # 格式化结果
        results_text = "\n".join([
            f"- {post['id']}: {post['title']}"
            for post in processed_posts[:5]
        ])

        if len(processed_posts) > 5:
            results_text += f"\n- ... 还有 {len(processed_posts) - 5} 条"

        # 简单替换（实际应使用 vs.render）
        report = report_template.replace("{{app_name}}", app_name)
        report = report.replace("{{version}}", version)
        report = report.replace("{{timestamp}}", asyncio.get_event_loop().time())
        report = report.replace("{{count}}", str(len(processed_posts)))
        report = report.replace("{{results}}", results_text)

        context["final_report"] = report

        logger.info("最终报告已生成")

        return {
            "report": report,
            "length": len(report)
        }


async def run_variable_template_workflow() -> WorkflowResult:
    """运行变量和模板工作流"""
    config = {
        "request_count": 5
    }

    workflow = VariableTemplateWorkflow(config)
    result = await workflow.execute()

    return result


# 测试代码
if __name__ == "__main__":
    async def main():
        print("=" * 60)
        print("示例 4: 变量和模板系统工作流")
        print("=" * 60)

        result = await run_variable_template_workflow()

        print(f"\n工作流状态：{result.status.value}")
        print(f"总耗时：{result.total_duration:.2f}秒")

        # 打印最终报告
        for step_result in result.step_results:
            if step_result.step_name == "generate_final_report" and step_result.output:
                print("\n" + "=" * 60)
                print("最终报告:")
                print("=" * 60)
                print(step_result.output.get("report", "无报告"))

    asyncio.run(main())
