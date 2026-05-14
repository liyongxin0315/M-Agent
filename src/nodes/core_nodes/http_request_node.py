"""
HTTP Request Node - HTTP 请求节点

发送 HTTP 请求并处理响应。
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


@dataclass
class HttpRequestConfig:
    """HTTP 请求配置"""
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    params: Optional[Dict[str, Any]] = None
    json: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None
    timeout: float = 30.0
    follow_redirects: bool = True
    max_retries: int = 3


class HttpRequestNode(BaseNode):
    """HTTP 请求节点"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.request_config = self._parse_config(config or {})
    
    def _parse_config(self, config: Dict[str, Any]) -> HttpRequestConfig:
        """解析配置"""
        return HttpRequestConfig(
            url=config.get("url", ""),
            method=config.get("method", "GET").upper(),
            headers=config.get("headers"),
            params=config.get("params"),
            json=config.get("json"),
            data=config.get("data"),
            timeout=config.get("timeout", 30.0),
            follow_redirects=config.get("follow_redirects", True),
            max_retries=config.get("max_retries", 3)
        )
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """执行 HTTP 请求"""
        try:
            config = self._merge_config(context)
            
            async with httpx.AsyncClient(
                timeout=config.timeout,
                follow_redirects=config.follow_redirects
            ) as client:
                response = await client.request(
                    method=config.method,
                    url=config.url,
                    headers=config.headers,
                    params=config.params,
                    json=config.json,
                    data=config.data
                )
                
                result_data = {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": self._parse_response_body(response),
                    "url": str(response.url)
                }
                
                if response.status_code >= 400:
                    return NodeResult(
                        status=NodeStatus.FAILED,
                        node_name=self.name,
                        output=result_data,
                        error=f"HTTP 错误：{response.status_code}"
                    )
                
                return NodeResult(
                    status=NodeStatus.COMPLETED,
                    node_name=self.name,
                    output=result_data
                )
        
        except httpx.TimeoutException as e:
            return NodeResult(
                status=NodeStatus.FAILED,
                node_name=self.name,
                error=f"请求超时：{e}"
            )
        except httpx.RequestError as e:
            return NodeResult(
                status=NodeStatus.FAILED,
                node_name=self.name,
                error=f"请求失败：{e}"
            )
        except Exception as e:
            return NodeResult(
                status=NodeStatus.FAILED,
                node_name=self.name,
                error=f"未知错误：{e}"
            )
    
    def _merge_config(self, context: Dict[str, Any]) -> HttpRequestConfig:
        """合并配置"""
        config = self.request_config
        
        if "url" in context:
            config.url = context["url"]
        if "method" in context:
            config.method = context["method"].upper()
        if "headers" in context:
            config.headers = context["headers"]
        if "params" in context:
            config.params = context["params"]
        if "json" in context:
            config.json = context["json"]
        if "data" in context:
            config.data = context["data"]
        
        return config
    
    def _parse_response_body(self, response: httpx.Response) -> Any:
        """解析响应体"""
        content_type = response.headers.get("content-type", "")
        
        if "application/json" in content_type:
            try:
                return response.json()
            except Exception:
                return response.text
        elif "text/" in content_type:
            return response.text
        else:
            return response.text[:1000]
    
    def get_schema(self) -> Dict[str, Any]:
        """获取节点 schema"""
        return {
            "name": "http_request",
            "description": "发送 HTTP 请求",
            "inputs": {
                "url": {
                    "type": "string",
                    "required": True,
                    "description": "请求 URL"
                },
                "method": {
                    "type": "string",
                    "required": False,
                    "default": "GET",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
                    "description": "HTTP 方法"
                },
                "headers": {
                    "type": "object",
                    "required": False,
                    "description": "请求头"
                },
                "params": {
                    "type": "object",
                    "required": False,
                    "description": "查询参数"
                },
                "json": {
                    "type": "object",
                    "required": False,
                    "description": "JSON 请求体"
                },
                "timeout": {
                    "type": "number",
                    "required": False,
                    "default": 30.0,
                    "description": "超时时间（秒）"
                }
            },
            "outputs": {
                "status_code": {
                    "type": "number",
                    "description": "HTTP 状态码"
                },
                "headers": {
                    "type": "object",
                    "description": "响应头"
                },
                "body": {
                    "type": "any",
                    "description": "响应体"
                }
            }
        }
