# AgentM 配置管理

## 概述

配置管理模块提供统一的配置加载、验证和热更新功能。所有配置参数从 YAML 文件或环境变量读取，杜绝硬编码。

## 快速开始

### 1. 创建配置文件

复制默认配置文件到项目根目录：

```bash
cd /home/liyongxin/.openclaw/workspace/agentm
cp config/default_config.yaml config.yaml
```

### 2. 修改配置

编辑 `config.yaml`，根据实际需求调整参数：

```yaml
environment: production

rag:
  top_k: 10
  embedding_model: "all-MiniLM-L6-v2"

webui:
  port: 8080
  debug: false

log:
  level: "WARNING"
  file: "/var/log/agentm/agentm.log"
```

### 3. 使用配置

```python
from agentm.config import get_config, get_rag_config, get_webui_config

# 获取全部配置
config = get_config()
print(f"环境：{config.environment}")

# 获取特定模块配置
rag_config = get_rag_config()
print(f"RAG top_k: {rag_config.top_k}")

webui_config = get_webui_config()
print(f"WebUI 端口：{webui_config.port}")
```

## 配置项说明

### 环境配置 (`environment`)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| environment | string | development | 运行环境：development/testing/production |

### RAG 引擎配置 (`rag`)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| persist_directory | string | ./agentm_data/rag_db | 向量数据库持久化目录 |
| embedding_model | string | all-MiniLM-L6-v2 | 嵌入模型名称 |
| collection_name | string | agentm_knowledge | ChromaDB 集合名称 |
| top_k | int | 5 | 默认返回的检索结果数量 |
| bm25_k1 | float | 1.5 | BM25 k1 参数 |
| bm25_b | float | 0.75 | BM25 b 参数 |
| hybrid_alpha | float | 0.5 | 混合检索向量权重 |
| max_content_length | int | 4000 | 最大内容长度 |
| chunk_size | int | 500 | 分块大小 |
| chunk_overlap | int | 50 | 分块重叠 |

### 熔断器配置 (`circuit_breaker`)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| failure_threshold | int | 5 | 失败阈值 |
| success_threshold | int | 3 | 成功阈值 |
| recovery_timeout_seconds | float | 30.0 | 恢复超时时间（秒） |
| half_open_max_requests | int | 3 | 半开状态最大请求数 |
| timeout_seconds | float/null | null | 请求超时时间 |
| fallback_strategy | string | fail_fast | 降级策略 |
| enabled | bool | true | 是否启用 |

### 缓存配置 (`cache`)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| max_size | int | 1000 | 最大缓存条目数 |
| max_memory_mb | float | 100.0 | 最大内存占用（MB） |
| default_ttl_seconds | int/null | 300 | 默认过期时间（秒） |

### Agent 配置 (`agent`)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| max_message_queue_size | int | 10000 | 最大消息队列大小 |
| task_max_retries | int | 3 | 任务最大重试次数 |
| task_timeout_seconds | float | 300.0 | 任务超时时间（秒） |
| heartbeat_interval_seconds | float | 30.0 | 心跳间隔（秒） |
| persistence_enabled | bool | true | 是否启用持久化 |
| persistence_db_path | string | ./agentm_data/agents.db | 持久化数据库路径 |

### 工作流配置 (`workflow`)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| default_step_timeout_seconds | float | 60.0 | 默认步骤超时时间 |
| max_concurrent_workflows | int | 10 | 最大并发工作流数 |
| execution_history_retention_days | int | 30 | 执行历史保留天数 |
| persistence_db_path | string | ./agentm_data/workflows.db | 持久化数据库路径 |

### WebUI 配置 (`webui`)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| host | string | 0.0.0.0 | 监听地址 |
| port | int | 5000 | 监听端口 |
| debug | bool | false | 调试模式 |
| secret_key | string/null | null | 会话密钥 |
| session_timeout_minutes | int | 60 | 会话超时时间（分钟） |

### 日志配置 (`log`)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| level | string | INFO | 日志级别 |
| format | string | %(asctime)s... | 日志格式 |
| file | string/null | ./agentm_data/logs/agentm.log | 日志文件路径 |
| max_size_mb | float | 10.0 | 日志文件最大大小（MB） |
| backup_count | int | 5 | 备份文件数量 |

### 数据库配置 (`database`)

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| type | string | sqlite | 数据库类型 |
| path | string | ./agentm_data/agentm.db | SQLite 数据库路径 |
| host | string/null | null | 数据库主机 |
| port | int/null | null | 数据库端口 |
| username | string/null | null | 数据库用户名 |
| password | string/null | null | 数据库密码 |
| database | string/null | null | 数据库名称 |
| pool_size | int | 5 | 连接池大小 |
| echo | bool | false | 是否打印 SQL |

## 环境变量覆盖

配置可以通过环境变量覆盖，优先级：环境变量 > YAML 文件 > 默认值

| 环境变量 | 配置项 | 示例 |
|----------|--------|------|
| AGENTM_ENVIRONMENT | environment | `export AGENTM_ENVIRONMENT=production` |
| AGENTM_RAG_TOP_K | rag.top_k | `export AGENTM_RAG_TOP_K=10` |
| AGENTM_RAG_EMBEDDING_MODEL | rag.embedding_model | `export AGENTM_RAG_EMBEDDING_MODEL=all-MiniLM-L6-v2` |
| AGENTM_CACHE_MAX_SIZE | cache.max_size | `export AGENTM_CACHE_MAX_SIZE=2000` |
| AGENTM_CACHE_MAX_MEMORY_MB | cache.max_memory_mb | `export AGENTM_CACHE_MAX_MEMORY_MB=200` |
| AGENTM_WEBUI_HOST | webui.host | `export AGENTM_WEBUI_HOST=0.0.0.0` |
| AGENTM_WEBUI_PORT | webui.port | `export AGENTM_WEBUI_PORT=8080` |
| AGENTM_WEBUI_DEBUG | webui.debug | `export AGENTM_WEBUI_DEBUG=false` |
| AGENTM_LOG_LEVEL | log.level | `export AGENTM_LOG_LEVEL=DEBUG` |
| AGENTM_DB_PATH | database.path | `export AGENTM_DB_PATH=/data/agentm.db` |

## 配置热更新

```python
from agentm.config import update_config, reload_config

# 方式 1：更新部分配置
update_config({
    "log": {"level": "DEBUG"},
    "cache": {"max_size": 2000}
})

# 方式 2：重新从文件加载
reload_config()
```

## 最佳实践

### 1. 不同环境使用不同配置

```bash
# 开发环境
cp config/default_config.yaml config.development.yaml

# 生产环境
cp config/default_config.yaml config.production.yaml

# 启动时指定
export AGENTM_ENVIRONMENT=production
python -m agentm.webui.webui --config config.production.yaml
```

### 2. 敏感信息使用环境变量

```yaml
# config.yaml
database:
  password: null  # 不在文件中存储密码
```

```bash
export AGENTM_DB_PASSWORD="your_secure_password"
```

### 3. 生产环境配置建议

```yaml
environment: production

log:
  level: "WARNING"
  file: "/var/log/agentm/agentm.log"

webui:
  debug: false
  secret_key: "生成一个随机密钥"

cache:
  max_size: 5000
  max_memory_mb: 200.0

circuit_breaker:
  enabled: true
  failure_threshold: 3
```

## 故障排查

### 配置未生效

1. 检查配置文件路径是否正确
2. 检查 YAML 语法是否正确
3. 检查是否有环境变量覆盖

```bash
# 验证 YAML 语法
python -c "import yaml; yaml.safe_load(open('config.yaml'))"

# 检查环境变量
env | grep AGENTM
```

### 配置加载失败

查看日志输出：

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from agentm.config import get_config
config = get_config()
```

## API 参考

### ConfigManager

```python
from agentm.config import ConfigManager

manager = ConfigManager.get_instance()

# 加载配置
config = manager.load(config_path="config.yaml")

# 重新加载
config = manager.reload()

# 更新配置
manager.update({"log": {"level": "DEBUG"}})
```

### 便捷函数

```python
from agentm.config import (
    get_config,
    reload_config,
    update_config,
    get_rag_config,
    get_circuit_breaker_config,
    get_cache_config,
    get_agent_config,
    get_workflow_config,
    get_webui_config,
    get_log_config,
    get_database_config,
)
```
