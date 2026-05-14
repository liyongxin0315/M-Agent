"""
Webhook Node - Webhook 节点

触发和接收 Webhook。
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


@dataclass
class WebhookConfig:
    """Webhook 配置"""
    webhook_id: str
    method: str = "POST"
    expected_fields: List[str] = None
    response_template: Optional[Dict[str, Any]] = None
    secret: Optional[str] = None


class WebhookNode(BaseNode):
    """Webhook 节点"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.webhook_config = self._parse_config(config or {})
    
    def _parse_config(self, config: Dict[str, Any]) -> WebhookConfig:
        """解析配置"""
        return WebhookConfig(
            webhook_id=config.get("webhook_id", ""),
            method=config.get("method", "POST"),
            expected_fields=config.get("expected_fields", []),
            response_template=config.get("response_template"),
            secret=config.get("secret")
        )
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """执行 Webhook"""
        try:
            payload = context.get("payload", {})
            method = context.get("method", self.webhook_config.method)
            
            if method != self.webhook_config.method:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    node_name=self.name,
                    error=f"不支持的方法：{method}"
                )
            
            if self.webhook_config.expected_fields:
                missing_fields = self._check_fields(payload, self.webhook_config.expected_fields)
                if missing_fields:
                    return NodeResult(
                        status=NodeStatus.FAILED,
                        node_name=self.name,
                        error=f"缺少字段：{', '.join(missing_fields)}"
                    )
            
            response = self.webhook_config.response_template or {
                "success": True,
                "webhook_id": self.webhook_config.webhook_id,
                "received_fields": list(payload.keys())
            }
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                node_name=self.name,
                output={
                    "webhook_id": self.webhook_config.webhook_id,
                    "payload": payload,
                    "response": response
                }
            )
        
        except Exception as e:
            return NodeResult(
                status=NodeStatus.FAILED,
                node_name=self.name,
                error=f"Webhook 处理失败：{e}"
            )
    
    def _check_fields(self, payload: Dict[str, Any], expected: List[str]) -> List[str]:
        """检查字段"""
        missing = []
        for field in expected:
            if field not in payload:
                missing.append(field)
        return missing
    
    def get_webhook_url(self, base_url: str) -> str:
        """获取 Webhook URL"""
        return f"{base_url}/webhook/{self.webhook_config.webhook_id}"
    
    def get_schema(self) -> Dict[str, Any]:
        """获取节点 schema"""
        return {
            "name": "webhook",
            "description": "Webhook 触发",
            "inputs": {
                "webhook_id": {
                    "type": "string",
                    "required": True,
                    "description": "Webhook ID"
                },
                "method": {
                    "type": "string",
                    "required": False,
                    "default": "POST",
                    "enum": ["GET", "POST", "PUT", "DELETE"],
                    "description": "HTTP 方法"
                },
                "payload": {
                    "type": "object",
                    "required": False,
                    "description": "Webhook 载荷"
                }
            },
            "outputs": {
                "webhook_id": {
                    "type": "string",
                    "description": "Webhook ID"
                },
                "payload": {
                    "type": "object",
                    "description": "接收的载荷"
                },
                "response": {
                    "type": "object",
                    "description": "响应数据"
                }
            }
        }


class DatabaseQueryNode(BaseNode):
    """数据库查询节点

    执行 SQL 查询。
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.connection_string = config.get("connection_string", "") if config else ""
        self.query = config.get("query", "") if config else ""
        self.params = config.get("params", []) if config else []
        self.fetch_mode = config.get("fetch_mode", "all") if config else "all"
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """执行数据库查询"""
        try:
            import aiosqlite
            
            connection_string = context.get("connection_string", self.connection_string)
            query = context.get("query", self.query)
            params = context.get("params", self.params)
            fetch_mode = context.get("fetch_mode", self.fetch_mode)
            
            if not query:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    node_name=self.name,
                    error="未提供 SQL 查询"
                )
            
            if not connection_string:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    node_name=self.name,
                    error="未提供数据库连接字符串"
                )
            
            async with aiosqlite.connect(connection_string) as db:
                db.row_factory = aiosqlite.Row
                
                async with db.execute(query, params) as cursor:
                    if query.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")):
                        await db.commit()
                        rows_affected = cursor.rowcount
                        
                        return NodeResult(
                            status=NodeStatus.COMPLETED,
                            node_name=self.name,
                            output={
                                "rows_affected": rows_affected,
                                "last_row_id": cursor.lastrowid
                            }
                        )
                    else:
                        if fetch_mode == "all":
                            rows = await cursor.fetchall()
                        elif fetch_mode == "one":
                            row = await cursor.fetchone()
                            rows = [row] if row else []
                        elif fetch_mode == "many":
                            size = context.get("fetch_size", 10)
                            rows = await cursor.fetchmany(size)
                        else:
                            rows = await cursor.fetchall()
                        
                        result = [dict(row) for row in rows]
                        
                        return NodeResult(
                            status=NodeStatus.COMPLETED,
                            node_name=self.name,
                            output={
                                "rows": result,
                                "count": len(result)
                            }
                        )
        
        except Exception as e:
            return NodeResult(
                status=NodeStatus.FAILED,
                node_name=self.name,
                error=f"数据库查询失败：{e}"
            )
    
    def get_schema(self) -> Dict[str, Any]:
        """获取节点 schema"""
        return {
            "name": "database_query",
            "description": "数据库查询",
            "inputs": {
                "connection_string": {
                    "type": "string",
                    "required": True,
                    "description": "数据库连接字符串"
                },
                "query": {
                    "type": "string",
                    "required": True,
                    "description": "SQL 查询"
                },
                "params": {
                    "type": "array",
                    "required": False,
                    "default": [],
                    "description": "查询参数"
                },
                "fetch_mode": {
                    "type": "string",
                    "required": False,
                    "default": "all",
                    "enum": ["all", "one", "many"],
                    "description": "获取模式"
                }
            },
            "outputs": {
                "rows": {
                    "type": "array",
                    "description": "查询结果"
                },
                "count": {
                    "type": "number",
                    "description": "结果数量"
                },
                "rows_affected": {
                    "type": "number",
                    "description": "影响行数（写操作）"
                }
            }
        }
