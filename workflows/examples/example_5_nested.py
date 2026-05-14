"""
示例工作流 5 - 子工作流嵌套调用

演示工作流嵌套和复用。
"""

import asyncio
import logging
from typing import Any, Dict

from agentm.workflows.workflow_engine import BaseWorkflow, WorkflowResult
from agentm import create_nested_engine, WorkflowRegistry
from agentm.nodes import (
    HttpRequestNode,
    CodeNode,
    ConditionNode,
    VariableNode,
    SubWorkflowNode,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============ 子工作流 1: 数据验证 ============

class DataValidationSubWorkflow(BaseWorkflow):
    """数据验证子工作流"""

    def _setup_steps(self) -> None:
        self.engine.add_step(
            name="validate_format",
            func=self._validate_format,
            description="验证数据格式",
            retry_count=1
        )
        self.engine.add_step(
            name="validate_content",
            func=self._validate_content,
            description="验证数据内容",
            retry_count=1
        )

    async def _validate_format(self, context: Dict[str, Any]) -> Dict:
        """验证格式"""
        data = context.get("data", {})

        if not isinstance(data, dict):
            return {"valid": False, "error": "数据必须是对象"}

        required_fields = ["id", "name", "value"]
        missing = [f for f in required_fields if f not in data]

        if missing:
            return {"valid": False, "error": f"缺少字段：{missing}"}

        return {"valid": True, "fields": list(data.keys())}

    async def _validate_content(self, context: Dict[str, Any]) -> Dict:
        """验证内容"""
        data = context.get("data", {})

        # 检查值类型
        if not isinstance(data.get("value"), (int, float)):
            return {"valid": False, "error": "value 必须是数字"}

        # 检查值范围
        value = data.get("value", 0)
        if value < 0 or value > 1000:
            return {"valid": False, "error": "value 必须在 0-1000 范围内"}

        return {"valid": True, "score": 100}


# ============ 子工作流 2: 数据处理 ============

class DataProcessingSubWorkflow(BaseWorkflow):
    """数据处理子工作流"""

    def _setup_steps(self) -> None:
        self.engine.add_step(
            name="transform",
            func=self._transform_data,
            description="转换数据",
            retry_count=2
        )
        self.engine.add_step(
            name="enrich",
            func=self._enrich_data,
            description="增强数据",
            retry_count=1
        )

    async def _transform_data(self, context: Dict[str, Any]) -> Dict:
        """转换数据"""
        data = context.get("data", {})

        transformed = {
            "item_id": data.get("id"),
            "item_name": data.get("name", "").upper(),
            "item_value": float(data.get("value", 0)) * 1.1,  # 10% 增幅
            "transformed": True
        }

        return transformed

    async def _enrich_data(self, context: Dict[str, Any]) -> Dict:
        """增强数据"""
        transformed = context.get("transform_data", {})

        # 添加元数据
        enriched = {
            **transformed,
            "metadata": {
                "processed_at": asyncio.get_event_loop().time(),
                "version": "1.0",
                "source": "DataProcessingSubWorkflow"
            }
        }

        return enriched


# ============ 主工作流 ============

class NestedWorkflowExample(BaseWorkflow):
    """嵌套工作流示例 - 主工作流"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        
        # 创建嵌套引擎
        self.nested_engine = create_nested_engine()
        
        # 注册子工作流
        self.nested_engine.register_workflow("data_validation", DataValidationSubWorkflow)
        self.nested_engine.register_workflow("data_processing", DataProcessingSubWorkflow)

    def _setup_steps(self) -> None:
        """设置工作流步骤"""
        # 步骤 1: 准备数据
        self.engine.add_step(
            name="prepare_data",
            func=self._prepare_data,
            description="准备测试数据",
            retry_count=0
        )

        # 步骤 2: 调用验证子工作流
        self.engine.add_step(
            name="validate",
            func=self._call_validation,
            description="调用验证子工作流",
            retry_count=2
        )

        # 步骤 3: 条件判断
        self.engine.add_step(
            name="check_validation",
            func=self._check_validation,
            description="检查验证结果",
            retry_count=0
        )

        # 步骤 4: 调用处理子工作流（如果验证通过）
        self.engine.add_step(
            name="process",
            func=self._call_processing,
            description="调用处理子工作流",
            retry_count=2,
            skip_on_error=True
        )

        # 步骤 5: 汇总结果
        self.engine.add_step(
            name="summarize",
            func=self._summarize,
            description="汇总所有结果",
            retry_count=1
        )

    async def _prepare_data(self, context: Dict[str, Any]) -> Dict:
        """准备数据"""
        # 生成测试数据
        test_data = {
            "id": 123,
            "name": "测试项目",
            "value": 500,
            "category": "A"
        }

        context["input_data"] = test_data
        logger.info(f"准备数据：{test_data}")

        return test_data

    async def _call_validation(self, context: Dict[str, Any]) -> Dict:
        """调用验证子工作流"""
        input_data = context.get("input_data", {})

        result = await self.nested_engine.execute_subworkflow(
            workflow_id="data_validation",
            input_data={"data": input_data},
            parent_context=context
        )

        context["validation_result"] = result
        logger.info(f"验证结果：{result}")

        return result

    async def _check_validation(self, context: Dict[str, Any]) -> Dict:
        """检查验证结果"""
        validation_result = context.get("validation_result", {})

        # 检查是否有效
        is_valid = validation_result.get("valid", False)

        if isinstance(validation_result, dict):
            # 检查子工作流的输出
            for key, value in validation_result.items():
                if isinstance(value, dict) and "valid" in value:
                    is_valid = value.get("valid", False)
                    break

        context["validation_passed"] = is_valid
        logger.info(f"验证通过：{is_valid}")

        return {"passed": is_valid}

    async def _call_processing(self, context: Dict[str, Any]) -> Dict:
        """调用处理子工作流"""
        validation_passed = context.get("validation_passed", False)

        if not validation_passed:
            logger.warning("验证未通过，跳过处理")
            return {"skipped": True, "reason": "验证失败"}

        input_data = context.get("input_data", {})

        result = await self.nested_engine.execute_subworkflow(
            workflow_id="data_processing",
            input_data={"data": input_data},
            parent_context=context
        )

        context["processing_result"] = result
        logger.info(f"处理结果：{result}")

        return result

    async def _summarize(self, context: Dict[str, Any]) -> Dict:
        """汇总结果"""
        input_data = context.get("input_data", {})
        validation_result = context.get("validation_result", {})
        processing_result = context.get("processing_result", {})
        validation_passed = context.get("validation_passed", False)

        summary = {
            "input": input_data,
            "validation": {
                "passed": validation_passed,
                "result": validation_result
            },
            "processing": {
                "executed": validation_passed and processing_result,
                "result": processing_result if validation_passed else None
            },
            "final_status": "success" if validation_passed else "failed"
        }

        context["final_summary"] = summary
        logger.info("汇总完成")

        return summary


async def run_nested_workflow_example() -> WorkflowResult:
    """运行嵌套工作流示例"""
    config = {}

    workflow = NestedWorkflowExample(config)
    result = await workflow.execute()

    return result


# 测试代码
if __name__ == "__main__":
    async def main():
        print("=" * 60)
        print("示例 5: 嵌套工作流示例")
        print("=" * 60)

        result = await run_nested_workflow_example()

        print(f"\n工作流状态：{result.status.value}")
        print(f"总耗时：{result.total_duration:.2f}秒")

        print("\n步骤执行详情:")
        for step_result in result.step_results:
            print(f"\n  {step_result.step_name}: {step_result.status.value}")
            if step_result.output:
                if isinstance(step_result.output, dict):
                    for key, value in step_result.output.items():
                        if key != "result":  # 跳过大型结果
                            print(f"    - {key}: {value}")
                else:
                    print(f"    输出：{step_result.output}")

        # 打印最终汇总
        print("\n" + "=" * 60)
        print("最终汇总:")
        print("=" * 60)
        
        for step_result in result.step_results:
            if step_result.step_name == "summarize" and step_result.output:
                summary = step_result.output
                print(f"输入数据：{summary.get('input', {})}")
                print(f"验证状态：{'✅ 通过' if summary.get('validation', {}).get('passed') else '❌ 失败'}")
                print(f"最终状态：{summary.get('final_status', 'unknown')}")

    asyncio.run(main())
