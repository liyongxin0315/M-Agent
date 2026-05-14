"""
示例工作流 1 - 数据同步管道

从 API 获取数据，转换后存入数据库。
"""

import asyncio
import logging
from typing import Any, Dict

from agentm.workflows.workflow_engine import BaseWorkflow, WorkflowResult
from agentm.nodes import (
    HttpRequestNode,
    ConditionNode,
    LoopNode,
    DatabaseQueryNode,
    ErrorHandlerNode,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataSyncPipelineWorkflow(BaseWorkflow):
    """数据同步管道工作流"""

    def _setup_steps(self) -> None:
        """设置工作流步骤"""
        # 步骤 1: 从 API 获取数据
        self.engine.add_step(
            name="fetch_data",
            func=self._fetch_data,
            description="从外部 API 获取数据",
            retry_count=3,
            retry_delay=2.0,
            timeout=60.0
        )

        # 步骤 2: 验证数据
        self.engine.add_step(
            name="validate_data",
            func=self._validate_data,
            description="验证数据格式",
            retry_count=1
        )

        # 步骤 3: 数据转换
        self.engine.add_step(
            name="transform_data",
            func=self._transform_data,
            description="转换数据格式",
            retry_count=2
        )

        # 步骤 4: 批量插入数据库
        self.engine.add_step(
            name="save_to_db",
            func=self._save_to_db,
            description="保存到数据库",
            retry_count=3,
            retry_delay=5.0
        )

        # 步骤 5: 验证结果
        self.engine.add_step(
            name="verify_result",
            func=self._verify_result,
            description="验证同步结果",
            skip_on_error=True
        )

    async def _fetch_data(self, context: Dict[str, Any]) -> Dict:
        """从 API 获取数据"""
        api_url = self.config.get("api_url", "https://api.example.com/data")
        
        node = HttpRequestNode("fetch", {
            "url": api_url,
            "method": "GET",
            "timeout": 30.0
        })

        result = await node.execute(context)
        
        if result.status.value == "failed":
            raise Exception(f"API 请求失败：{result.error}")

        data = result.output.get("body", [])
        logger.info(f"获取到 {len(data)} 条数据")
        
        context["raw_data"] = data
        return {"count": len(data), "source": api_url}

    async def _validate_data(self, context: Dict[str, Any]) -> Dict:
        """验证数据"""
        raw_data = context.get("raw_data", [])

        if not isinstance(raw_data, list):
            raise Exception("数据格式错误：必须是数组")

        # 检查必填字段
        valid_count = 0
        for item in raw_data:
            if isinstance(item, dict) and "id" in item:
                valid_count += 1

        context["valid_data"] = [
            item for item in raw_data
            if isinstance(item, dict) and "id" in item
        ]

        logger.info(f"验证通过：{valid_count}/{len(raw_data)}")
        
        return {
            "total": len(raw_data),
            "valid": valid_count,
            "invalid": len(raw_data) - valid_count
        }

    async def _transform_data(self, context: Dict[str, Any]) -> Dict:
        """转换数据"""
        valid_data = context.get("valid_data", [])

        transformed = []
        for item in valid_data:
            transformed_item = {
                "external_id": item.get("id"),
                "name": item.get("name", "Unknown"),
                "value": item.get("value", 0),
                "created_at": item.get("created_at"),
                "synced_at": asyncio.get_event_loop().time()
            }
            transformed.append(transformed_item)

        context["transformed_data"] = transformed
        logger.info(f"转换完成：{len(transformed)} 条")

        return {"count": len(transformed), "sample": transformed[:3]}

    async def _save_to_db(self, context: Dict[str, Any]) -> Dict:
        """保存到数据库"""
        db_path = self.config.get("db_path", "./agentm_data/sync.db")
        transformed_data = context.get("transformed_data", [])

        if not transformed_data:
            logger.warning("无数据可保存")
            return {"saved": 0}

        # 创建表（如果不存在）
        create_table_node = DatabaseQueryNode("create_table", {
            "connection_string": db_path,
            "query": """
                CREATE TABLE IF NOT EXISTS synced_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT UNIQUE,
                    name TEXT,
                    value REAL,
                    created_at TEXT,
                    synced_at REAL
                )
            """
        })

        await create_table_node.execute(context)

        # 批量插入
        saved_count = 0
        for item in transformed_data:
            try:
                insert_node = DatabaseQueryNode("insert", {
                    "connection_string": db_path,
                    "query": """
                        INSERT OR REPLACE INTO synced_data 
                        (external_id, name, value, created_at, synced_at)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                    "params": [
                        item["external_id"],
                        item["name"],
                        item["value"],
                        item["created_at"],
                        item["synced_at"]
                    ]
                })

                result = await insert_node.execute(context)
                if result.status.value == "completed":
                    saved_count += 1

            except Exception as e:
                logger.error(f"插入失败：{e}")
                continue

        logger.info(f"保存完成：{saved_count} 条")
        context["saved_count"] = saved_count

        return {"saved": saved_count}

    async def _verify_result(self, context: Dict[str, Any]) -> Dict:
        """验证结果"""
        db_path = self.config.get("db_path", "./agentm_data/sync.db")

        verify_node = DatabaseQueryNode("verify", {
            "connection_string": db_path,
            "query": "SELECT COUNT(*) as count FROM synced_data",
            "fetch_mode": "one"
        })

        result = await verify_node.execute(context)
        count = result.output.get("rows", [{}])[0].get("count", 0)

        logger.info(f"数据库中共有 {count} 条记录")

        return {"total_records": count}


async def run_data_sync_pipeline(
    api_url: str = "https://api.example.com/data",
    db_path: str = "./agentm_data/sync.db"
) -> WorkflowResult:
    """运行数据同步管道"""
    config = {
        "api_url": api_url,
        "db_path": db_path
    }

    workflow = DataSyncPipelineWorkflow(config)
    result = await workflow.execute()

    return result


# 测试代码
if __name__ == "__main__":
    async def main():
        # 使用模拟数据测试
        result = await run_data_sync_pipeline(
            api_url="https://jsonplaceholder.typicode.com/posts",
            db_path="./test_sync.db"
        )

        print(f"\n工作流状态：{result.status.value}")
        print(f"总耗时：{result.total_duration:.2f}秒")
        print("\n步骤结果:")
        for step_result in result.step_results:
            print(f"  - {step_result.step_name}: {step_result.status.value}")
            if step_result.output:
                print(f"    输出：{step_result.output}")
            if step_result.error:
                print(f"    错误：{step_result.error}")

    asyncio.run(main())
