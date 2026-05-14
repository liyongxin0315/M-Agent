"""
AgentM 配置管理模块

提供统一的配置加载、验证、热更新功能
所有配置参数从 config.yaml 或环境变量读取
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class Environment(Enum):
    """运行环境"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


@dataclass
class RAGConfig:
    """RAG 引擎配置"""
    persist_directory: str = "./agentm_data/rag_db"
    embedding_model: str = "all-MiniLM-L6-v2"
    collection_name: str = "agentm_knowledge"
    top_k: int = 5
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    hybrid_alpha: float = 0.5
    max_content_length: int = 4000
    chunk_size: int = 500
    chunk_overlap: int = 50
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RAGConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5
    success_threshold: int = 3
    recovery_timeout_seconds: float = 30.0
    half_open_max_requests: int = 3
    timeout_seconds: Optional[float] = None
    fallback_strategy: str = "fail_fast"
    default_value: Any = None
    enabled: bool = True
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CircuitBreakerConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CacheConfig:
    """缓存配置"""
    max_size: int = 1000
    max_memory_mb: float = 100.0
    default_ttl_seconds: Optional[float] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AgentConfig:
    """Agent 配置"""
    max_message_queue_size: int = 10000
    task_max_retries: int = 3
    task_timeout_seconds: float = 300.0
    heartbeat_interval_seconds: float = 30.0
    persistence_enabled: bool = True
    persistence_db_path: str = "./agentm_data/agents.db"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class WorkflowConfig:
    """工作流配置"""
    default_step_timeout_seconds: float = 60.0
    max_concurrent_workflows: int = 10
    execution_history_retention_days: int = 30
    persistence_db_path: str = "./agentm_data/workflows.db"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class WebUIConfig:
    """WebUI 配置"""
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = False
    secret_key: Optional[str] = None
    session_timeout_minutes: int = 60
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WebUIConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class LogConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    file: Optional[str] = None
    max_size_mb: float = 10.0
    backup_count: int = 5
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DatabaseConfig:
    """数据库配置"""
    type: str = "sqlite"
    path: str = "./agentm_data/agentm.db"
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    pool_size: int = 5
    echo: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatabaseConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Config:
    """
    主配置类
    
    所有配置项的中央存储库
    """
    environment: Environment = Environment.DEVELOPMENT
    project_root: str = field(default_factory=lambda: str(Path(__file__).parent.parent))
    
    rag: RAGConfig = field(default_factory=RAGConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    webui: WebUIConfig = field(default_factory=WebUIConfig)
    log: LogConfig = field(default_factory=LogConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    
    # 原始配置数据（用于热更新）
    _raw_data: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        """从字典创建配置"""
        config = cls()
        config._raw_data = data
        
        if "environment" in data:
            config.environment = Environment(data["environment"])
        
        if "rag" in data:
            config.rag = RAGConfig.from_dict(data["rag"])
        
        if "circuit_breaker" in data:
            config.circuit_breaker = CircuitBreakerConfig.from_dict(data["circuit_breaker"])
        
        if "cache" in data:
            config.cache = CacheConfig.from_dict(data["cache"])
        
        if "agent" in data:
            config.agent = AgentConfig.from_dict(data["agent"])
        
        if "workflow" in data:
            config.workflow = WorkflowConfig.from_dict(data["workflow"])
        
        if "webui" in data:
            config.webui = WebUIConfig.from_dict(data["webui"])
        
        if "log" in data:
            config.log = LogConfig.from_dict(data["log"])
        
        if "database" in data:
            config.database = DatabaseConfig.from_dict(data["database"])
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "environment": self.environment.value,
            "project_root": self.project_root,
            "rag": {
                "persist_directory": self.rag.persist_directory,
                "embedding_model": self.rag.embedding_model,
                "collection_name": self.rag.collection_name,
                "top_k": self.rag.top_k,
                "bm25_k1": self.rag.bm25_k1,
                "bm25_b": self.rag.bm25_b,
                "hybrid_alpha": self.rag.hybrid_alpha,
                "max_content_length": self.rag.max_content_length,
                "chunk_size": self.rag.chunk_size,
                "chunk_overlap": self.rag.chunk_overlap,
            },
            "circuit_breaker": {
                "failure_threshold": self.circuit_breaker.failure_threshold,
                "success_threshold": self.circuit_breaker.success_threshold,
                "recovery_timeout_seconds": self.circuit_breaker.recovery_timeout_seconds,
                "half_open_max_requests": self.circuit_breaker.half_open_max_requests,
                "timeout_seconds": self.circuit_breaker.timeout_seconds,
                "fallback_strategy": self.circuit_breaker.fallback_strategy,
                "enabled": self.circuit_breaker.enabled,
            },
            "cache": {
                "max_size": self.cache.max_size,
                "max_memory_mb": self.cache.max_memory_mb,
                "default_ttl_seconds": self.cache.default_ttl_seconds,
            },
            "agent": {
                "max_message_queue_size": self.agent.max_message_queue_size,
                "task_max_retries": self.agent.task_max_retries,
                "task_timeout_seconds": self.agent.task_timeout_seconds,
                "heartbeat_interval_seconds": self.agent.heartbeat_interval_seconds,
                "persistence_enabled": self.agent.persistence_enabled,
                "persistence_db_path": self.agent.persistence_db_path,
            },
            "workflow": {
                "default_step_timeout_seconds": self.workflow.default_step_timeout_seconds,
                "max_concurrent_workflows": self.workflow.max_concurrent_workflows,
                "execution_history_retention_days": self.workflow.execution_history_retention_days,
                "persistence_db_path": self.workflow.persistence_db_path,
            },
            "webui": {
                "host": self.webui.host,
                "port": self.webui.port,
                "debug": self.webui.debug,
                "session_timeout_minutes": self.webui.session_timeout_minutes,
            },
            "log": {
                "level": self.log.level,
                "format": self.log.format,
                "file": self.log.file,
                "max_size_mb": self.log.max_size_mb,
                "backup_count": self.log.backup_count,
            },
            "database": {
                "type": self.database.type,
                "path": self.database.path,
                "pool_size": self.database.pool_size,
                "echo": self.database.echo,
            },
        }


class ConfigManager:
    """
    配置管理器
    
    特性:
    - 从 YAML 文件加载配置
    - 环境变量覆盖
    - 配置验证
    - 热更新支持
    - 单例模式
    """
    
    _instance: Optional["ConfigManager"] = None
    _config: Optional[Config] = None
    _config_path: Optional[str] = None
    
    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._config = None  # 延迟加载
            self._config_path = None
    
    @classmethod
    def get_instance(cls) -> "ConfigManager":
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def load(
        self,
        config_path: Optional[str] = None,
        environment: Optional[str] = None
    ) -> Config:
        """
        加载配置
        
        Args:
            config_path: 配置文件路径，默认查找:
                - ./config.yaml
                - ./config/config.yaml
                - ~/.agentm/config.yaml
            environment: 运行环境，覆盖配置文件中的设置
        
        Returns:
            Config 对象
        """
        # 查找配置文件
        if config_path:
            paths_to_try = [Path(config_path)]
        else:
            paths_to_try = [
                Path("config.yaml"),
                Path("config/config.yaml"),
                Path.home() / ".agentm" / "config.yaml",
            ]
        
        config_file = None
        for path in paths_to_try:
            if path.is_absolute() and path.exists():
                config_file = path
                break
            # 相对于项目根目录
            project_root = Path(__file__).parent.parent
            full_path = project_root / path
            if full_path.exists():
                config_file = full_path
                break
        
        # 加载配置
        if config_file and config_file.exists():
            logger.info(f"从 {config_file} 加载配置")
            with open(config_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        else:
            logger.warning("未找到配置文件，使用默认配置")
            data = {}
        
        # 环境变量覆盖
        data = self._apply_env_overrides(data)
        
        # 环境参数覆盖
        if environment:
            data["environment"] = environment
        
        # 创建配置对象
        self._config = Config.from_dict(data)
        self._config_path = str(config_file) if config_file else None
        
        # 配置日志
        self._setup_logging()
        
        logger.info(f"配置加载完成，环境：{self._config.environment.value}")
        return self._config
    
    def _apply_env_overrides(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """应用环境变量覆盖"""
        env_mapping = {
            "AGENTM_ENVIRONMENT": "environment",
            "AGENTM_RAG_PERSIST_DIRECTORY": ("rag", "persist_directory"),
            "AGENTM_RAG_EMBEDDING_MODEL": ("rag", "embedding_model"),
            "AGENTM_RAG_TOP_K": ("rag", "top_k"),
            "AGENTM_CACHE_MAX_SIZE": ("cache", "max_size"),
            "AGENTM_CACHE_MAX_MEMORY_MB": ("cache", "max_memory_mb"),
            "AGENTM_WEBUI_HOST": ("webui", "host"),
            "AGENTM_WEBUI_PORT": ("webui", "port"),
            "AGENTM_WEBUI_DEBUG": ("webui", "debug"),
            "AGENTM_LOG_LEVEL": ("log", "level"),
            "AGENTM_DB_PATH": ("database", "path"),
        }
        
        for env_var, config_key in env_mapping.items():
            value = os.environ.get(env_var)
            if value:
                if isinstance(config_key, tuple):
                    section, key = config_key
                    if section not in data:
                        data[section] = {}
                    # 类型转换
                    if key in ["top_k", "max_size", "port"]:
                        value = int(value)
                    elif key in ["max_memory_mb", "bm25_k1", "bm25_b", "hybrid_alpha"]:
                        value = float(value)
                    elif key in ["debug", "persistence_enabled"]:
                        value = value.lower() in ["true", "1", "yes"]
                    data[section][key] = value
                else:
                    data[config_key] = value
                logger.debug(f"环境变量覆盖：{env_var}={value}")
        
        return data
    
    def _setup_logging(self) -> None:
        """配置日志"""
        if not self._config:
            return
        
        log_config = self._config.log
        
        # 日志级别
        level = getattr(logging, log_config.level.upper(), logging.INFO)
        
        # 日志格式
        formatter = logging.Formatter(log_config.format)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        
        # 根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        root_logger.addHandler(console_handler)
        
        # 文件处理器
        if log_config.file:
            from logging.handlers import RotatingFileHandler
            # 确保日志目录存在
            log_path = Path(log_config.file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = RotatingFileHandler(
                log_config.file,
                maxBytes=int(log_config.max_size_mb * 1024 * 1024),
                backupCount=log_config.backup_count,
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level)
            root_logger.addHandler(file_handler)
            logger.info(f"日志文件：{log_config.file}")
    
    def get(self) -> Config:
        """获取当前配置"""
        if self._config is None:
            return self.load()
        return self._config
    
    def reload(self) -> Config:
        """重新加载配置（热更新）"""
        logger.info("重新加载配置")
        # 使用之前保存的配置文件路径
        return self.load(config_path=self._config_path)
    
    def update(self, updates: Dict[str, Any]) -> None:
        """
        更新配置
        
        Args:
            updates: 配置更新，格式：{"section": {"key": value}}
        """
        if not self._config:
            raise RuntimeError("配置未加载")
        
        # 更新原始数据
        self._deep_update(self._config._raw_data, updates)
        
        # 重新创建配置对象
        self._config = Config.from_dict(self._config._raw_data)
        
        # 重新配置日志
        self._setup_logging()
        
        logger.info("配置已更新")
    
    def _deep_update(self, base: Dict, updates: Dict) -> None:
        """深度更新字典"""
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def get_config() -> Config:
    """获取全局配置"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager.get_instance()
        _config_manager.load()
    return _config_manager.get()


def reload_config() -> Config:
    """重新加载配置"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager.get_instance()
    return _config_manager.reload()


def update_config(updates: Dict[str, Any]) -> None:
    """更新配置"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager.get_instance()
        _config_manager.load()
    _config_manager.update(updates)


# 便捷函数
def get_rag_config() -> RAGConfig:
    """获取 RAG 配置"""
    return get_config().rag


def get_circuit_breaker_config() -> CircuitBreakerConfig:
    """获取熔断器配置"""
    return get_config().circuit_breaker


def get_cache_config() -> CacheConfig:
    """获取缓存配置"""
    return get_config().cache


def get_agent_config() -> AgentConfig:
    """获取 Agent 配置"""
    return get_config().agent


def get_workflow_config() -> WorkflowConfig:
    """获取工作流配置"""
    return get_config().workflow


def get_webui_config() -> WebUIConfig:
    """获取 WebUI 配置"""
    return get_config().webui


def get_log_config() -> LogConfig:
    """获取日志配置"""
    return get_config().log


def get_database_config() -> DatabaseConfig:
    """获取数据库配置"""
    return get_config().database


if __name__ == "__main__":
    # 测试配置模块
    logging.basicConfig(level=logging.INFO)
    
    # 加载配置
    config_manager = ConfigManager.get_instance()
    config = config_manager.load()
    
    # 打印配置
    import json
    print(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))
    
    # 测试便捷函数
    print(f"\nRAG 配置：{get_rag_config()}")
    print(f"缓存配置：{get_cache_config()}")
    print(f"WebUI 配置：{get_webui_config()}")
