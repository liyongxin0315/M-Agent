# API Integration Skill - API 集成技能

## 功能描述
提供 REST 和 GraphQL API 的异步调用能力，支持多种认证方式、请求重试、响应缓存。

## 激活条件
当用户提到以下关键词时激活：
- API 调用 / HTTP 请求
- REST / GraphQL
- Webhook / 接口集成
- 第三方服务对接

## 依赖安装
```bash
pip install httpx gql[transport-httpx] pytest pytest-asyncio
```

## 使用示例

### REST API 调用

#### 基础用法
```python
from agentm.skills.api-integration.api_skill import create_rest_client, AuthType

# 创建客户端
client = create_rest_client(
    name="github",
    base_url="https://api.github.com",
    auth_type=AuthType.BEARER,
    token="your_github_token"
)

# GET 请求
user_info = await client.get("/user")

# POST 请求
new_repo = await client.post(
    "/user/repos",
    json_data={"name": "my-repo", "private": True}
)

# PUT 请求
updated = await client.put(
    "/repos/user/my-repo",
    json_data={"description": "Updated description"}
)

# DELETE 请求
await client.delete("/repos/user/my-repo")
```

#### 带认证的请求
```python
from agentm.skills.api-integration.api_skill import (
    APISkill,
    APIConfig,
    AuthConfig,
    AuthType
)

skill = APISkill()

# API Key 认证
auth = AuthConfig(
    auth_type=AuthType.API_KEY,
    api_key="your_api_key",
    api_key_header="X-API-Key"
)
config = APIConfig(
    base_url="https://api.example.com",
    auth=auth,
    timeout=60.0,
    retry_count=5
)
client = skill.create_rest_client("myapi", config)

# Basic 认证
basic_auth = AuthConfig(
    auth_type=AuthType.BASIC,
    username="user",
    password="pass"
)
```

#### 错误处理
```python
from agentm.skills.api-integration.api_skill import APIError

try:
    result = await client.get("/protected/resource")
except APIError as e:
    print(f"状态码：{e.status_code}")
    print(f"错误信息：{e.response_body}")
    print(f"请求 URL: {e.url}")
```

#### 缓存控制
```python
# 清除缓存
client.clear_cache()

# 禁用缓存
config = APIConfig(
    base_url="https://api.example.com",
    cache_enabled=False
)
```

### GraphQL API 调用

#### 基础用法
```python
from agentm.skills.api-integration.api_skill import create_graphql_client, AuthType

# 创建客户端
client = create_graphql_client(
    name="graphql_api",
    endpoint="https://api.example.com/graphql",
    auth_type=AuthType.BEARER,
    token="your_token"
)

# 查询操作
result = await client.query("""
    query GetUser($id: ID!) {
        user(id: $id) {
            id
            name
            email
            posts {
                title
                content
            }
        }
    }
""", variables={"id": "123"})

# 变更操作
result = await client.mutate("""
    mutation CreatePost($input: PostInput!) {
        createPost(input: $input) {
            id
            title
            createdAt
        }
    }
""", variables={
    "input": {
        "title": "New Post",
        "content": "Post content"
    }
})
```

#### 管理多个 API 客户端
```python
from agentm.skills.api-integration.api_skill import APISkill

skill = APISkill()

# 创建多个 REST 客户端
rest_config1 = APIConfig(base_url="https://api.github.com")
rest_config2 = APIConfig(base_url="https://api.slack.com")

skill.create_rest_client("github", rest_config1)
skill.create_rest_client("slack", rest_config2)

# 创建 GraphQL 客户端
gql_config = APIConfig(base_url="https://api.example.com/graphql")
skill.create_graphql_client("main_graphql", gql_config)

# 获取客户端
github_client = skill.get_rest_client("github")
graphql_client = skill.get_graphql_client("main_graphql")

# 关闭所有客户端
await skill.close_all()
```

## 配置选项

### APIConfig
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| base_url | str | - | API 基础 URL |
| auth | AuthConfig | 无认证 | 认证配置 |
| timeout | float | 30.0 | 请求超时（秒） |
| retry_count | int | 3 | 重试次数 |
| retry_delay | float | 1.0 | 重试延迟（秒） |
| cache_enabled | bool | True | 启用缓存 |
| cache_ttl | int | 300 | 缓存存活时间（秒） |

### AuthConfig
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| auth_type | AuthType | NONE | 认证类型 |
| token | str | None | Bearer Token |
| api_key | str | None | API Key |
| api_key_header | str | X-API-Key | API Key 头名称 |
| username | str | None | Basic 认证用户名 |
| password | str | None | Basic 认证密码 |
| custom_headers | dict | {} | 自定义头 |

## 测试
```bash
cd /home/liyongxin/.openclaw/workspace/agentm/skills/api-integration
pytest test_api.py -v
```

## 文件结构
```
api-integration/
├── SKILL.md              # 技能说明文档
├── README.md             # 快速入门
├── api_skill.py          # 核心实现
├── test_api.py           # 单元测试
└── __init__.py           # 模块初始化
```
