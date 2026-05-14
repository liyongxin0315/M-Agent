"""
示例工作流 3 - 循环并行处理

并行处理大量数据项。
"""

import asyncio
import logging
import random
from typing import Any, Dict, List

from agentm.workflows.workflow_engine import BaseWorkflow, WorkflowResult
from agentm.nodes import LoopNode, HttpRequestNode, CodeNode, MergeNode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ParallelProcessingWorkflow(BaseWorkflow):
    """循环并行处理工作流"""

    def _setup_steps(self) -> None:
        """设置工作流步骤"""
        # 步骤 1: 生成测试数据
        self.engine.add_step(
            name="generate_items",
            func=self._generate_items,
            description="生成测试数据",
            retry_count=0
        )

        # 步骤 2: 并行处理每个项目
        self.engine.add_step(
            name="parallel_process",
            func=self._parallel_process,
            description="并行处理所有项目",
            retry_count=2
        )

        # 步骤 3: 汇总统计
        self.engine.add_step(
            name="aggregate_stats",
            func=self._aggregate_stats,
            description="汇总统计信息",
            retry_count=1
        )

        # 步骤 4: 生成报告
        self.engine.add_step(
            name="generate_report",
            func=self._generate_report,
            description="生成处理报告",
            retry_count=1
        )

    async def _generate_items(self, context: Dict[str, Any]) -> Dict:
        """生成测试数据"""
        item_count = self.config.get("item_count", 20)
        
        items = [
            {
                "id": i + 1,
                "name": f"Item_{i + 1}",
                "value": random.randint(1, 100),
                "category": random.choice(["A", "B", "C"])
            }
            for i in range(item_count)
        ]

        context["items"] = items
        logger.info(f"生成了 {item_count} 个测试项目")

        return {"count": item_count, "sample": items[:3]}

    async def _parallel_process(self, context: Dict[str, Any]) -> Dict:
        """并行处理"""
        max_concurrency = self.config.get("max_concurrency", 5)
        
        # 创建循环节点
        loop_node = LoopNode("process_items", {
            "items_key": "items",
            "result_key": "processed_items",
            "parallel": True,
            "max_concurrency": max_concurrency,
            "continue_on_error": True
        })

        # 设置处理函数
        async def process_item(item_context: Dict) -> Dict:
            item = item_context["item"]
            index = item_context["index"]

            try:
                # 模拟 API 调用
                await asyncio.sleep(random.uniform(0.1, 0.5))

                # 处理逻辑
                processed = {
                    "id": item["id"],
                    "original_value": item["value"],
                    "processed_value": item["value"] * 1.1,  # 10% 增长
                    "category": item["category"],
                    "status": "success",
                    "processed_at": asyncio.get_event_loop().time()
                }

                return processed

            except Exception as e:
                logger.error(f"处理项目 {item['id']} 失败：{e}")
                return {
                    "id": item["id"],
                    "status": "failed",
                    "error": str(e)
                }

        loop_node.set_loop_function(process_item)

        # 执行循环
        result = await loop_node.execute(context)
        
        processed_items = result.output.get("processed_items", [])
        context["processed_items"] = processed_items

        success_count = sum(
            1 for item in processed_items
            if item.get("status") == "success"
        )

        logger.info(f"处理完成：{success_count}/{len(processed_items)} 成功")

        return {
            "total": len(processed_items),
            "success": success_count,
            "failed": len(processed_items) - success_count
        }

    async def _aggregate_stats(self, context: Dict[str, Any]) -> Dict:
        """汇总统计"""
        processed_items = context.get("processed_items", [])

        if not processed_items:
            return {"error": "无数据可统计"}

        # 使用 Code 节点进行统计分析
        code = """
import statistics

items = context.get('processed_items', [])
successful = [i for i in items if i.get('status') == 'success']

if not successful:
    return {'error': '无成功数据'}

values = [i['processed_value'] for i in successful]

stats = {
    'count': len(successful),
    'sum': sum(values),
    'avg': statistics.mean(values),
    'min': min(values),
    'max': max(values),
    'median': statistics.median(values),
    'by_category': {}
}

# 按类别分组
for item in successful:
    cat = item['category']
    if cat not in stats['by_category']:
        stats['by_category'][cat] = []
    stats['by_category'][cat].append(item['processed_value'])

# 计算每类的平均值
for cat in stats['by_category']:
    stats['by_category'][cat] = sum(stats['by_category'][cat]) / len(stats['by_category'][cat])

return stats
"""

        node = CodeNode("stats", {
            "language": "python",
            "code": code
        })

        result = await node.execute(context)
        stats = result.output

        context["stats"] = stats
        logger.info(f"统计完成：平均值={stats.get('avg', 0):.2f}")

        return stats

    async def _generate_report(self, context: Dict[str, Any]) -> Dict:
        """生成报告"""
        stats = context.get("stats", {})
        items = context.get("items", [])
        processed = context.get("processed_items", [])

        report = {
            "summary": {
                "total_items": len(items),
                "processed_items": len(processed),
                "success_rate": f"{stats.get('count', 0) / len(items) * 100:.1f}%" if items else "0%"
            },
            "statistics": {
                "total_value": f"{stats.get('sum', 0):.2f}",
                "average_value": f"{stats.get('avg', 0):.2f}",
                "min_value": f"{stats.get('min', 0):.2f}",
                "max_value": f"{stats.get('max', 0):.2f}",
                "median_value": f"{stats.get('median', 0):.2f}"
            },
            "by_category": {
                cat: f"{avg:.2f}"
                for cat, avg in stats.get("by_category", {}).items()
            },
            "recommendations": []
        }

        # 生成建议
        if stats.get("avg", 0) > 50:
            report["recommendations"].append("平均值较高，表现良好")
        if stats.get("count", 0) < len(items) * 0.9:
            report["recommendations"].append("成功率低于 90%，建议检查失败原因")

        context["report"] = report
        logger.info("报告已生成")

        return report


async def run_parallel_processing(
    item_count: int = 20,
    max_concurrency: int = 5
) -> WorkflowResult:
    """运行并行处理工作流"""
    config = {
        "item_count": item_count,
        "max_concurrency": max_concurrency
    }

    workflow = ParallelProcessingWorkflow(config)
    result = await workflow.execute()

    return result


# 测试代码
if __name__ == "__main__":
    async def main():
        print("=" * 60)
        print("示例 3: 循环并行处理工作流")
        print("=" * 60)

        result = await run_parallel_processing(
            item_count=15,
            max_concurrency=3
        )

        print(f"\n工作流状态：{result.status.value}")
        print(f"总耗时：{result.total_duration:.2f}秒")

        print("\n处理结果:")
        for step_result in result.step_results:
            print(f"\n  {step_result.step_name}:")
            if step_result.output:
                for key, value in step_result.output.items():
                    if isinstance(value, dict):
                        print(f"    {key}:")
                        for k, v in value.items():
                            print(f"      {k}: {v}")
                    else:
                        print(f"    {key}: {value}")

    asyncio.run(main())
