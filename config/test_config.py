"""
AgentM 配置管理模块单元测试

测试配置加载、验证、环境变量覆盖、热更新等功能
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import (
    Config,
    ConfigManager,
    Environment,
    RAGConfig,
    CircuitBreakerConfig,
    CacheConfig,
    AgentConfig,
    WorkflowConfig,
    WebUIConfig,
    LogConfig,
    DatabaseConfig,
    get_config,
    reload_config,
    update_config,
    get_rag_config,
    get_cache_config,
    get_webui_config,
    get_log_config,
)


class TestRAGConfig:
    """测试 RAG 配置"""
    
    def test_default_values(self):
        """测试默认值"""
        config = RAGConfig()
        assert config.persist_directory == "./agentm_data/rag_db"
        assert config.embedding_model == "all-MiniLM-L6-v2"
        assert config.top_k == 5
        assert config.chunk_size == 500
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "persist_directory": "/custom/path",
            "top_k": 10,
            "chunk_size": 1000,
        }
        config = RAGConfig.from_dict(data)
        assert config.persist_directory == "/custom/path"
        assert config.top_k == 10
        assert config.chunk_size == 1000
        # 未指定的字段使用默认值
        assert config.embedding_model == "all-MiniLM-L6-v2"


class TestCircuitBreakerConfig:
    """测试熔断器配置"""
    
    def test_default_values(self):
        """测试默认值"""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 3
        assert config.recovery_timeout_seconds == 30.0
        assert config.enabled is True
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "failure_threshold": 10,
            "recovery_timeout_seconds": 60.0,
            "enabled": False,
        }
        config = CircuitBreakerConfig.from_dict(data)
        assert config.failure_threshold == 10
        assert config.recovery_timeout_seconds == 60.0
        assert config.enabled is False


class TestCacheConfig:
    """测试缓存配置"""
    
    def test_default_values(self):
        """测试默认值"""
        config = CacheConfig()
        assert config.max_size == 1000
        assert config.max_memory_mb == 100.0
        assert config.default_ttl_seconds is None
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "max_size": 5000,
            "max_memory_mb": 200.0,
            "default_ttl_seconds": 600,
        }
        config = CacheConfig.from_dict(data)
        assert config.max_size == 5000
        assert config.max_memory_mb == 200.0
        assert config.default_ttl_seconds == 600


class TestConfig:
    """测试主配置类"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = Config()
        assert config.environment == Environment.DEVELOPMENT
        assert isinstance(config.rag, RAGConfig)
        assert isinstance(config.cache, CacheConfig)
        assert isinstance(config.circuit_breaker, CircuitBreakerConfig)
    
    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "environment": "production",
            "rag": {"top_k": 10},
            "cache": {"max_size": 2000},
        }
        config = Config.from_dict(data)
        assert config.environment == Environment.PRODUCTION
        assert config.rag.top_k == 10
        assert config.cache.max_size == 2000
    
    def test_to_dict(self):
        """测试转换为字典"""
        config = Config()
        data = config.to_dict()
        
        assert isinstance(data, dict)
        assert "environment" in data
        assert "rag" in data
        assert "cache" in data
        assert data["environment"] == "development"


class TestConfigManager:
    """测试配置管理器"""
    
    def test_singleton(self):
        """测试单例模式"""
        manager1 = ConfigManager.get_instance()
        manager2 = ConfigManager.get_instance()
        assert manager1 is manager2
    
    def test_load_default(self):
        """测试加载默认配置"""
        # 重置单例
        ConfigManager._instance = None
        ConfigManager._config = None
        
        manager = ConfigManager.get_instance()
        config = manager.load()
        
        assert config is not None
        assert isinstance(config.environment, Environment)
    
    def test_load_from_file(self, tmp_path):
        """测试从文件加载配置"""
        # 创建临时配置文件
        config_file = tmp_path / "test_config.yaml"
        config_data = {
            "environment": "testing",
            "rag": {"top_k": 15},
            "webui": {"port": 8080},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        
        # 重置单例
        ConfigManager._instance = None
        ConfigManager._config = None
        
        # 加载配置
        manager = ConfigManager.get_instance()
        config = manager.load(config_path=str(config_file))
        
        assert config.environment == Environment.TESTING
        assert config.rag.top_k == 15
        assert config.webui.port == 8080
    
    def test_env_override(self, tmp_path, monkeypatch):
        """测试环境变量覆盖"""
        # 创建临时配置文件
        config_file = tmp_path / "test_config.yaml"
        config_data = {
            "environment": "development",
            "rag": {"top_k": 5},
            "webui": {"port": 5000},
        }
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        
        # 设置环境变量
        monkeypatch.setenv("AGENTM_ENVIRONMENT", "production")
        monkeypatch.setenv("AGENTM_RAG_TOP_K", "20")
        monkeypatch.setenv("AGENTM_WEBUI_PORT", "9000")
        
        # 重置单例
        ConfigManager._instance = None
        ConfigManager._config = None
        
        # 加载配置
        manager = ConfigManager.get_instance()
        config = manager.load(config_path=str(config_file))
        
        # 环境变量应该覆盖配置文件
        assert config.environment == Environment.PRODUCTION
        assert config.rag.top_k == 20
        assert config.webui.port == 9000
    
    def test_update_config(self, tmp_path):
        """测试配置更新"""
        # 创建临时配置文件
        config_file = tmp_path / "test_config.yaml"
        config_data = {"environment": "development"}
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        
        # 重置单例
        ConfigManager._instance = None
        ConfigManager._config = None
        
        # 加载并更新配置
        manager = ConfigManager.get_instance()
        config = manager.load(config_path=str(config_file))
        
        # 更新配置
        manager.update({
            "log": {"level": "DEBUG"},
            "cache": {"max_size": 5000},
        })
        
        # 验证更新
        updated_config = manager.get()
        assert updated_config.log.level == "DEBUG"
        assert updated_config.cache.max_size == 5000
    
    def test_reload_config(self, tmp_path):
        """测试重新加载配置"""
        # 创建临时配置文件
        config_file = tmp_path / "test_config.yaml"
        config_data = {"environment": "development", "rag": {"top_k": 5}}
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        
        # 重置单例
        ConfigManager._instance = None
        ConfigManager._config = None
        
        # 加载配置
        manager = ConfigManager.get_instance()
        config = manager.load(config_path=str(config_file))
        assert config.rag.top_k == 5
        
        # 修改配置文件
        config_data["rag"]["top_k"] = 25
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)
        
        # 重新加载
        config = manager.reload()
        assert config.rag.top_k == 25


class TestConvenienceFunctions:
    """测试便捷函数"""
    
    def setup_method(self):
        """每个测试前重置配置管理器并加载默认配置"""
        # 清除全局变量
        import config.config as config_module
        config_module._config_manager = None
        ConfigManager._instance = None
        ConfigManager._config = None
    
    def test_get_config(self):
        """测试 get_config"""
        config = get_config()
        assert isinstance(config, Config)
    
    def test_get_rag_config(self):
        """测试 get_rag_config"""
        rag_config = get_rag_config()
        assert isinstance(rag_config, RAGConfig)
        # 默认值或配置文件中的值
        assert rag_config.top_k >= 1
    
    def test_get_cache_config(self):
        """测试 get_cache_config"""
        cache_config = get_cache_config()
        assert isinstance(cache_config, CacheConfig)
        assert cache_config.max_size >= 1
    
    def test_get_webui_config(self):
        """测试 get_webui_config"""
        webui_config = get_webui_config()
        assert isinstance(webui_config, WebUIConfig)
        assert webui_config.port >= 1
    
    def test_get_log_config(self):
        """测试 get_log_config"""
        log_config = get_log_config()
        assert isinstance(log_config, LogConfig)
        assert log_config.level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class TestEnvironmentEnum:
    """测试环境枚举"""
    
    def test_environment_values(self):
        """测试环境值"""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.TESTING.value == "testing"
        assert Environment.PRODUCTION.value == "production"
    
    def test_environment_from_string(self):
        """测试从字符串创建环境"""
        env = Environment("development")
        assert env == Environment.DEVELOPMENT
        
        env = Environment("production")
        assert env == Environment.PRODUCTION
        
        with pytest.raises(ValueError):
            Environment("invalid")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
