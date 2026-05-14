"""
API Integration Skill 单元测试
"""

import pytest
from api_skill import (
    APISkill,
    APIConfig,
    AuthConfig,
    AuthType,
    RESTClient,
    GraphQLClient,
    APIError,
    create_rest_client,
    create_graphql_client
)


class TestAuthConfig:
    """测试认证配置"""
    
    def test_no_auth(self):
        """测试无认证"""
        auth = AuthConfig(auth_type=AuthType.NONE)
        headers = auth.get_headers()
        assert headers == {}
    
    def test_bearer_auth(self):
        """测试 Bearer Token 认证"""
        auth = AuthConfig(auth_type=AuthType.BEARER, token="test_token")
        headers = auth.get_headers()
        assert headers["Authorization"] == "Bearer test_token"
    
    def test_api_key_auth(self):
        """测试 API Key 认证"""
        auth = AuthConfig(
            auth_type=AuthType.API_KEY,
            api_key="test_key",
            api_key_header="X-API-Key"
        )
        headers = auth.get_headers()
        assert headers["X-API-Key"] == "test_key"
    
    def test_basic_auth(self):
        """测试 Basic 认证"""
        auth = AuthConfig(
            auth_type=AuthType.BASIC,
            username="user",
            password="pass"
        )
        headers = auth.get_headers()
        assert headers["Authorization"].startswith("Basic ")
    
    def test_custom_auth(self):
        """测试自定义认证"""
        auth = AuthConfig(
            auth_type=AuthType.CUSTOM,
            custom_headers={"X-Custom": "value"}
        )
        headers = auth.get_headers()
        assert headers["X-Custom"] == "value"


class TestAPIConfig:
    """测试 API 配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = APIConfig(base_url="https://api.example.com")
        assert config.timeout == 30.0
        assert config.retry_count == 3
        assert config.cache_enabled is True
        assert config.cache_ttl == 300
    
    def test_custom_config(self):
        """测试自定义配置"""
        auth = AuthConfig(auth_type=AuthType.BEARER, token="token")
        config = APIConfig(
            base_url="https://api.example.com",
            auth=auth,
            timeout=60.0,
            retry_count=5,
            cache_enabled=False
        )
        assert config.timeout == 60.0
        assert config.retry_count == 5
        assert config.cache_enabled is False


class TestRESTClient:
    """测试 REST 客户端"""
    
    def test_create_client(self):
        """测试创建客户端"""
        config = APIConfig(base_url="https://api.example.com")
        client = RESTClient(config)
        assert client is not None
    
    def test_cache_key_generation(self):
        """测试缓存键生成"""
        config = APIConfig(base_url="https://api.example.com")
        client = RESTClient(config)
        
        key1 = client._get_cache_key("GET", "/users", {"id": 1})
        key2 = client._get_cache_key("GET", "/users", {"id": 1})
        key3 = client._get_cache_key("GET", "/users", {"id": 2})
        
        assert key1 == key2
        assert key1 != key3
    
    def test_cache_validity(self):
        """测试缓存有效性"""
        config = APIConfig(base_url="https://api.example.com", cache_ttl=300)
        client = RESTClient(config)
        
        import time
        cache_entry = {
            "data": {"test": "value"},
            "timestamp": time.time()
        }
        assert client._is_cache_valid(cache_entry) is True
        
        # 模拟过期缓存
        expired_entry = {
            "data": {"test": "value"},
            "timestamp": time.time() - 400
        }
        assert client._is_cache_valid(expired_entry) is False
    
    def test_clear_cache(self):
        """测试清除缓存"""
        config = APIConfig(base_url="https://api.example.com")
        client = RESTClient(config)
        
        client._cache["key1"] = {"data": "value1", "timestamp": 0}
        client._cache["key2"] = {"data": "value2", "timestamp": 0}
        
        client.clear_cache()
        assert len(client._cache) == 0


class TestGraphQLClient:
    """测试 GraphQL 客户端"""
    
    def test_create_client(self):
        """测试创建客户端"""
        config = APIConfig(base_url="https://api.example.com/graphql")
        client = GraphQLClient(config)
        assert client is not None
    
    def test_graphql_query_creation(self):
        """测试 GraphQL 查询创建"""
        from api_skill import GraphQLQuery
        
        query = GraphQLQuery(
            query="query { user(id: $id) { name email } }",
            variables={"id": 123},
            operation_name="GetUser"
        )
        
        assert "user" in query.query
        assert query.variables == {"id": 123}
        assert query.operation_name == "GetUser"


class TestAPISkill:
    """测试 API 技能主类"""
    
    def test_create_rest_client(self):
        """测试创建 REST 客户端"""
        skill = APISkill()
        config = APIConfig(base_url="https://api.example.com")
        
        client = skill.create_rest_client("test_api", config)
        assert isinstance(client, RESTClient)
        assert "test_api" in skill._rest_clients
    
    def test_create_graphql_client(self):
        """测试创建 GraphQL 客户端"""
        skill = APISkill()
        config = APIConfig(base_url="https://api.example.com/graphql")
        
        client = skill.create_graphql_client("test_gql", config)
        assert isinstance(client, GraphQLClient)
        assert "test_gql" in skill._graphql_clients
    
    def test_get_rest_client_exists(self):
        """测试获取存在的 REST 客户端"""
        skill = APISkill()
        config = APIConfig(base_url="https://api.example.com")
        skill.create_rest_client("test", config)
        
        client = skill.get_rest_client("test")
        assert client is not None
    
    def test_get_rest_client_not_exists(self):
        """测试获取不存在的 REST 客户端"""
        skill = APISkill()
        
        with pytest.raises(APIError, match="不存在"):
            skill.get_rest_client("nonexistent")
    
    def test_get_graphql_client_not_exists(self):
        """测试获取不存在的 GraphQL 客户端"""
        skill = APISkill()
        
        with pytest.raises(APIError, match="不存在"):
            skill.get_graphql_client("nonexistent")
    
    def test_create_multiple_clients(self):
        """测试创建多个客户端"""
        skill = APISkill()
        
        config1 = APIConfig(base_url="https://api1.example.com")
        config2 = APIConfig(base_url="https://api2.example.com")
        
        skill.create_rest_client("api1", config1)
        skill.create_rest_client("api2", config2)
        
        assert len(skill._rest_clients) == 2


class TestConvenienceFunctions:
    """测试便捷函数"""
    
    def test_create_rest_client_function(self):
        """测试 REST 客户端便捷函数"""
        client = create_rest_client(
            name="test",
            base_url="https://api.example.com",
            auth_type=AuthType.BEARER,
            token="test_token",
            timeout=60.0
        )
        assert isinstance(client, RESTClient)
        assert client.config.timeout == 60.0
    
    def test_create_graphql_client_function(self):
        """测试 GraphQL 客户端便捷函数"""
        client = create_graphql_client(
            name="test",
            endpoint="https://api.example.com/graphql",
            auth_type=AuthType.BEARER,
            token="test_token"
        )
        assert isinstance(client, GraphQLClient)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
