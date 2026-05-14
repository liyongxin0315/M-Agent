"""
示例工作流 2 - 条件分支处理

根据数据条件执行不同的处理路径。
"""

import asyncio
import logging
from typing import Any, Dict

from agentm.workflows.workflow_engine import BaseWorkflow, WorkflowResult
from agentm.nodes import (
    HttpRequestNode,
    ConditionNode,
    CodeNode,
    MergeNode,
    VariableNode,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConditionalProcessingWorkflow(BaseWorkflow):
    """条件分支处理工作流"""

    def _setup_steps(self) -> None:
        """设置工作流步骤"""
        # 步骤 1: 获取用户数据
        self.engine.add_step(
            name="get_user",
            func=self._get_user_data,
            description="获取用户信息",
            retry_count=3
        )

        # 步骤 2: 判断用户类型
        self.engine.add_step(
            name="check_user_type",
            func=self._check_user_type,
            description="判断用户类型",
            retry_count=0
        )

        # 步骤 3: 根据类型执行不同处理
        self.engine.add_step(
            name="process_by_type",
            func=self._process_by_type,
            description="按用户类型处理",
            retry_count=2
        )

        # 步骤 4: 合并结果
        self.engine.add_step(
            name="merge_results",
            func=self._merge_results,
            description="合并处理结果",
            retry_count=1
        )

        # 步骤 5: 发送通知
        self.engine.add_step(
            name="send_notification",
            func=self._send_notification,
            description="发送处理通知",
            skip_on_error=True
        )

    async def _get_user_data(self, context: Dict[str, Any]) -> Dict:
        """获取用户数据"""
        user_id = self.config.get("user_id", "1")
        
        # 使用模拟 API
        node = HttpRequestNode("get_user", {
            "url": f"https://jsonplaceholder.typicode.com/users/{user_id}",
            "method": "GET"
        })

        result = await node.execute(context)
        
        if result.status.value == "failed":
            # 使用默认数据
            user_data = {
                "id": int(user_id),
                "name": "Test User",
                "email": "test@example.com",
                "username": "testuser"
            }
        else:
            user_data = result.output.get("body", {})

        context["user_data"] = user_data
        logger.info(f"获取用户：{user_data.get('name', 'Unknown')}")

        return user_data

    async def _check_user_type(self, context: Dict[str, Any]) -> Dict:
        """判断用户类型"""
        user_data = context.get("user_data", {})
        user_id = user_data.get("id", 0)

        # 创建条件判断节点
        condition_node = ConditionNode("user_type_check", {
            "conditions": [
                {"branch": "vip", "condition": "user_id > 5"},
                {"branch": "regular", "condition": "user_id > 0"}
            ],
            "default_branch": "guest"
        })

        result = await condition_node.execute({"user_id": user_id})
        user_type = result.output["matched_branch"]

        # 设置变量
        var_node = VariableNode("set_type", {
            "operation": "set",
            "variables": {
                "user_type": user_type,
                "user_level": "high" if user_type == "vip" else "normal"
            }
        })

        await var_node.execute(context)

        logger.info(f"用户类型：{user_type}")
        context["user_type"] = user_type

        return {
            "user_type": user_type,
            "user_id": user_id
        }

    async def _process_by_type(self, context: Dict[str, Any]) -> Dict:
        """按类型处理"""
        user_type = context.get("user_type", "guest")
        user_data = context.get("user_data", {})

        if user_type == "vip":
            # VIP 用户处理
            code = """
# VIP 用户特殊处理
user = context.get('user_data', {})
result = {
    'type': 'vip',
    'benefits': ['free_shipping', 'priority_support', 'exclusive_discounts'],
    'discount_rate': 0.2,
    'message': f"尊敬的 VIP 用户 {user.get('name', '')}，您好！"
}
return result
"""
        elif user_type == "regular":
            # 普通用户处理
            code = """
# 普通用户处理
user = context.get('user_data', {})
result = {
    'type': 'regular',
    'benefits': ['standard_shipping', 'email_support'],
    'discount_rate': 0.1,
    'message': f"亲爱的用户 {user.get('name', '')}，您好！"
}
return result
"""
        else:
            # 访客处理
            code = """
# 访客处理
result = {
    'type': 'guest',
    'benefits': [],
    'discount_rate': 0.0,
    'message': "欢迎访问，请登录或注册！"
}
return result
"""

        node = CodeNode("process", {
            "language": "python",
            "code": code
        })

        result = await node.execute(context)
        process_result = result.output

        context["process_result"] = process_result
        logger.info(f"处理完成：{process_result.get('type')}")

        return process_result

    async def _merge_results(self, context: Dict[str, Any]) -> Dict:
        """合并结果"""
        user_data = context.get("user_data", {})
        process_result = context.get("process_result", {})

        merged = {
            **user_data,
            **process_result,
            "processed_at": asyncio.get_event_loop().time()
        }

        context["final_result"] = merged
        logger.info("结果已合并")

        return merged

    async def _send_notification(self, context: Dict[str, Any]) -> Dict:
        """发送通知"""
        final_result = context.get("final_result", {})
        user_type = context.get("user_type", "guest")

        # 模拟发送通知
        notification = {
            "to": final_result.get("email", "unknown"),
            "subject": f"{'VIP' if user_type == 'vip' else '普通'}用户处理完成",
            "body": final_result.get("message", ""),
            "sent": True
        }

        logger.info(f"通知已发送：{notification['to']}")
        
        return notification


async def run_conditional_processing(
    user_id: str = "1"
) -> WorkflowResult:
    """运行条件分支处理工作流"""
    config = {
        "user_id": user_id
    }

    workflow = ConditionalProcessingWorkflow(config)
    result = await workflow.execute()

    return result


# 测试代码
if __name__ == "__main__":
    async def main():
        print("=" * 60)
        print("示例 2: 条件分支处理工作流")
        print("=" * 60)

        # 测试不同用户类型
        for uid in ["1", "6", "99"]:
            print(f"\n测试用户 ID: {uid}")
            print("-" * 40)
            
            result = await run_conditional_processing(user_id=uid)

            print(f"工作流状态：{result.status.value}")
            
            # 查找处理结果
            for step_result in result.step_results:
                if step_result.step_name == "merge_results" and step_result.output:
                    final = step_result.output
                    print(f"用户类型：{final.get('user_type')}")
                    print(f"消息：{final.get('message')}")
                    print(f"优惠：{final.get('discount_rate', 0) * 100}%")

    asyncio.run(main())
