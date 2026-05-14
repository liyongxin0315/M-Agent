"""
API Integration Skill - API 集成模块

支持 REST 和 GraphQL API 的异步调用
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class AuthType(Enum):
    """认证类型枚举"""
    NONE = "none"
    BEARER = "bearer"
    API_KEY = "api_key"
    BASIC = "basic"
    CUSTOM = "custom"


@dataclass
class AuthConfig:
    """认证配置"""
    auth_type: AuthType = AuthType.NONE
    token: Optional[str] = None
    api_key: Optional[str] = None
    api_key_header: str = "X-API-Key"
    username: Optional[str] = None
    password: Optional[str] = None
    custom_headers: Dict[str, str] = field(default_factory=dict)
    
    def get_headers(self) -> Dict[str, str]:
        """获取认证头"""
        headers = {}
        
        if self.auth_type == AuthType.BEARER and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.auth_type == AuthType.API_KEY and self.api_key:
            headers[self.api_key_header] = self.api_key
        elif self.auth_type == AuthType.BASIC and self.username and self.password:
            import base64
            credentials = f"{self.username}:{self.password}"
            encoded = base64.b64encode(credentials.encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        elif self.auth_type == AuthType.CUSTOM:
            headers.update(self.custom_headers)
        
        return headers


@dataclass
class APIConfig:
    """API 配置"""
    base_url: str
    auth: AuthConfig = field(default_factory=AuthConfig)
    timeout: float = 30.0
    retry_count: int = 3
    retry_delay: float = 1.0
    cache_enabled: bool = True
    cache_ttl: int = 300  # 缓存存活时间（秒）


class APIError(Exception):
    """API 调用异常"""
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[Dict] = None,
        url: str = ""
    ):
        self.status_code = status_code
        self.response_body = response_body or {}
        self.url = url
        super().__init__(f"[{status_code}] {message} - {url}")


class RESTClient:
    """REST API 客户端"""
    
    def __init__(self, config: APIConfig):
        self.config = config
        self._client = None
        self._cache: Dict[str, Any] = {}
        self._import_dependencies()
    
    def _import_dependencies(self) -> None:
        """延迟导入依赖"""
        try:
            import httpx
            self._httpx = httpx
        except ImportError as e:
            logger.error("缺少依赖：pip install httpx")
            raise APIError(f"缺少依赖 httpx: {e}", url=self.config.base_url)
    
    async def _get_client(self) -> "httpx.AsyncClient":
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = self._httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self._httpx.Timeout(self.config.timeout),
                headers={"Content-Type": "application/json"}
            )
        return self._client
    
    async def close(self) -> None:
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("REST 客户端已关闭")
    
    def _get_cache_key(self, method: str, url: str, params: Optional[Dict]) -> str:
        """生成缓存键"""
        key_data = f"{method}:{url}:{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """检查缓存是否有效"""
        import time
        return time.time() - cache_entry["timestamp"] < self.config.cache_ttl
    
    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> "httpx.Response":
        """带重试的请求"""
        client = await self._get_client()
        last_error = None
        
        for attempt in range(self.config.retry_count):
            try:
                response = await client.request(method, url, **kwargs)
                return response
            except (self._httpx.ConnectError, self._httpx.TimeoutException) as e:
                last_error = e
                if attempt < self.config.retry_count - 1:
                    import asyncio
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
                    logger.warning(f"请求重试 {attempt + 1}/{self.config.retry_count}: {url}")
        
        raise APIError(
            f"请求失败，已重试 {self.config.retry_count} 次：{str(last_error)}",
            url=url
        )
    
    async def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """发送 HTTP 请求"""
        # 合并头
        request_headers = self.config.auth.get_headers()
        if headers:
            request_headers.update(headers)
        
        # 检查缓存（仅 GET 请求）
        if self.config.cache_enabled and method.upper() == "GET":
            cache_key = self._get_cache_key(method, endpoint, params)
            if cache_key in self._cache:
                cache_entry = self._cache[cache_key]
                if self._is_cache_valid(cache_entry):
                    logger.debug(f"使用缓存：{endpoint}")
                    return cache_entry["data"]
                else:
                    del self._cache[cache_key]
        
        # 发送请求
        response = await self._request_with_retry(
            method=method.upper(),
            url=endpoint,
            params=params,
            json=json_data,
            headers=request_headers
        )
        
        # 处理响应
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = {"text": response.text}
        
        if response.status_code >= 400:
            raise APIError(
                message=f"HTTP {response.status_code}",
                status_code=response.status_code,
                response_body=response_data,
                url=endpoint
            )
        
        # 缓存响应（仅 GET 请求）
        if self.config.cache_enabled and method.upper() == "GET":
            cache_key = self._get_cache_key(method, endpoint, params)
            self._cache[cache_key] = {
                "data": response_data,
                "timestamp": __import__("time").time()
            }
        
        return response_data
    
    async def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """GET 请求"""
        return await self.request("GET", endpoint, params=params)
    
    async def post(
        self,
        endpoint: str,
        json_data: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """POST 请求"""
        return await self.request("POST", endpoint, json_data=json_data, headers=headers)
    
    async def put(
        self,
        endpoint: str,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """PUT 请求"""
        return await self.request("PUT", endpoint, json_data=json_data)
    
    async def patch(
        self,
        endpoint: str,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """PATCH 请求"""
        return await self.request("PATCH", endpoint, json_data=json_data)
    
    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """DELETE 请求"""
        return await self.request("DELETE", endpoint)
    
    def clear_cache(self) -> None:
        """清除缓存"""
        self._cache.clear()
        logger.info("API 缓存已清除")


@dataclass
class GraphQLQuery:
    """GraphQL 查询"""
    query: str
    variables: Optional[Dict[str, Any]] = None
    operation_name: Optional[str] = None


class GraphQLClient:
    """GraphQL API 客户端"""
    
    def __init__(self, config: APIConfig):
        self.config = config
        self._client = None
        self._session = None
        self._import_dependencies()
    
    def _import_dependencies(self) -> None:
        """延迟导入依赖"""
        try:
            from gql import Client, gql
            from gql.transport.httpx import HTTPXAsyncTransport
            self._gql = gql
            self._Client = Client
            self._HTTPXAsyncTransport = HTTPXAsyncTransport
        except ImportError as e:
            logger.error("缺少依赖：pip install gql[transport-httpx]")
            raise APIError(f"缺少依赖 gql: {e}", url=self.config.base_url)
    
    async def _get_client(self) -> "Client":
        """获取 GraphQL 客户端"""
        if self._client is None:
            transport = self._HTTPXAsyncTransport(
                url=self.config.base_url,
                headers=self.config.auth.get_headers()
            )
            self._client = self._Client(
                transport=transport,
                fetch_schema_from_transport=True,
                execute_timeout=self.config.timeout
            )
        return self._client
    
    async def close(self) -> None:
        """关闭客户端"""
        if self._client:
            await self._client.close_async()
            self._client = None
            logger.info("GraphQL 客户端已关闭")
    
    async def execute(self, query: GraphQLQuery) -> Dict[str, Any]:
        """执行 GraphQL 查询"""
        client = await self._get_client()
        
        gql_query = self._gql(query.query)
        
        try:
            result = await client.execute_async(
                gql_query,
                variable_values=query.variables,
                operation_name=query.operation_name
            )
            return result
        except Exception as e:
            raise APIError(
                message=f"GraphQL 执行失败：{str(e)}",
                url=self.config.base_url
            )
    
    async def query(self, query_str: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """执行查询操作"""
        return await self.execute(GraphQLQuery(query=query_str, variables=variables))
    
    async def mutate(self, mutation_str: str, variables: Optional[Dict] = None) -> Dict[str, Any]:
        """执行变更操作"""
        return await self.execute(GraphQLQuery(query=mutation_str, variables=variables))


class APISkill:
    """API 技能主类"""
    
    def __init__(self):
        self._rest_clients: Dict[str, RESTClient] = {}
        self._graphql_clients: Dict[str, GraphQLClient] = {}
    
    def create_rest_client(self, name: str, config: APIConfig) -> RESTClient:
        """创建 REST 客户端"""
        client = RESTClient(config)
        self._rest_clients[name] = client
        logger.info(f"创建 REST 客户端：{name} ({config.base_url})")
        return client
    
    def create_graphql_client(self, name: str, config: APIConfig) -> GraphQLClient:
        """创建 GraphQL 客户端"""
        client = GraphQLClient(config)
        self._graphql_clients[name] = client
        logger.info(f"创建 GraphQL 客户端：{name} ({config.base_url})")
        return client
    
    def get_rest_client(self, name: str) -> RESTClient:
        """获取 REST 客户端"""
        if name not in self._rest_clients:
            raise APIError(f"REST 客户端不存在：{name}", url="")
        return self._rest_clients[name]
    
    def get_graphql_client(self, name: str) -> GraphQLClient:
        """获取 GraphQL 客户端"""
        if name not in self._graphql_clients:
            raise APIError(f"GraphQL 客户端不存在：{name}", url="")
        return self._graphql_clients[name]
    
    async def close_all(self) -> None:
        """关闭所有客户端"""
        for name, client in self._rest_clients.items():
            try:
                await client.close()
                logger.info(f"REST 客户端已关闭：{name}")
            except Exception as e:
                logger.error(f"关闭 REST 客户端 {name} 失败：{e}")
        
        for name, client in self._graphql_clients.items():
            try:
                await client.close()
                logger.info(f"GraphQL 客户端已关闭：{name}")
            except Exception as e:
                logger.error(f"关闭 GraphQL 客户端 {name} 失败：{e}")


# 便捷函数
def create_rest_client(
    name: str,
    base_url: str,
    auth_type: AuthType = AuthType.NONE,
    token: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = 30.0
) -> RESTClient:
    """快速创建 REST 客户端"""
    auth = AuthConfig(
        auth_type=auth_type,
        token=token,
        api_key=api_key
    )
    config = APIConfig(
        base_url=base_url,
        auth=auth,
        timeout=timeout
    )
    skill = APISkill()
    return skill.create_rest_client(name, config)


def create_graphql_client(
    name: str,
    endpoint: str,
    auth_type: AuthType = AuthType.NONE,
    token: Optional[str] = None,
    timeout: float = 30.0
) -> GraphQLClient:
    """快速创建 GraphQL 客户端"""
    auth = AuthConfig(
        auth_type=auth_type,
        token=token
    )
    config = APIConfig(
        base_url=endpoint,
        auth=auth,
        timeout=timeout
    )
    skill = APISkill()
    return skill.create_graphql_client(name, config)
