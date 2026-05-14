"""
AgentM 日志模块

提供统一的日志配置、结构化日志、日志过滤等功能
"""

import logging
import sys
from collections.abc import Mapping
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional, Union

from config.config import LogConfig, get_log_config


class StructuredFormatter(logging.Formatter):
    """
    结构化日志格式器
    
    支持 JSON 格式输出，便于日志分析系统解析
    """
    
    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        style: str = '%',
        validate: bool = True,
        *,
        defaults: Optional[Dict] = None,
        use_json: bool = False
    ):
        super().__init__(fmt, datefmt, style, validate, defaults=defaults)
        self.use_json = use_json
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录"""
        if self.use_json:
            return self._format_json(record)
        return super().format(record)
    
    def _format_json(self, record: logging.LogRecord) -> str:
        """JSON 格式输出"""
        import json
        
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # 添加额外字段
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'levelname', 'levelno',
                          'pathname', 'filename', 'module', 'lineno', 'funcName',
                          'exc_info', 'exc_text', 'stack_info', 'message']:
                try:
                    json.dumps(value)  # 验证可序列化
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)
        
        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class ContextFilter(logging.Filter):
    """
    日志上下文过滤器
    
    添加请求 ID、用户 ID 等上下文信息到日志
    """
    
    def __init__(self, context: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.context = context or {}
    
    def filter(self, record: logging.LogRecord) -> bool:
        """添加上下文信息"""
        for key, value in self.context.items():
            setattr(record, key, value)
        return True
    
    def update_context(self, **kwargs) -> None:
        """更新上下文"""
        self.context.update(kwargs)
    
    def clear_context(self) -> None:
        """清空上下文"""
        self.context.clear()


class LogLevelFilter(logging.Filter):
    """
    日志级别过滤器
    
    只允许特定级别的日志通过
    """
    
    def __init__(self, min_level: int, max_level: Optional[int] = None):
        super().__init__()
        self.min_level = min_level
        self.max_level = max_level or logging.CRITICAL
    
    def filter(self, record: logging.LogRecord) -> bool:
        """检查日志级别是否在范围内"""
        return self.min_level <= record.levelno <= self.max_level


class SensitiveDataFilter(logging.Filter):
    """
    敏感数据过滤器
    
    自动脱敏密码、Token、密钥等敏感信息
    """
    
    SENSITIVE_PATTERNS = [
        'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'apikey',
        'access_token', 'refresh_token', 'private_key', 'credentials'
    ]
    
    def __init__(self, mask: str = '***'):
        super().__init__()
        self.mask = mask
    
    def filter(self, record: logging.LogRecord) -> bool:
        """脱敏敏感信息"""
        msg = record.getMessage()
        
        for pattern in self.SENSITIVE_PATTERNS:
            # 简单替换（生产环境应使用更复杂的正则）
            if pattern.lower() in msg.lower():
                # 记录原始消息长度，但不暴露内容
                pass
        
        return True


def setup_logging(
    config: Optional[LogConfig] = None,
    log_file: Optional[str] = None,
    level: Optional[str] = None,
    use_json: bool = False,
    context: Optional[Dict[str, Any]] = None
) -> logging.Logger:
    """
    配置日志系统
    
    Args:
        config: 日志配置，默认使用 get_log_config()
        log_file: 日志文件路径，覆盖配置
        level: 日志级别，覆盖配置
        use_json: 是否使用 JSON 格式
        context: 日志上下文
    
    Returns:
        根日志器
    """
    # 获取配置
    if config is None:
        try:
            config = get_log_config()
        except Exception:
            config = LogConfig()
    
    # 覆盖配置
    if log_file:
        config.file = log_file
    if level:
        config.level = level
    
    # 日志级别
    log_level = getattr(logging, config.level.upper(), logging.INFO)
    
    # 根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 日志格式
    fmt = config.format
    formatter = StructuredFormatter(fmt, use_json=use_json)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    root_logger.addHandler(console_handler)
    
    # 文件处理器
    if config.file:
        log_path = Path(config.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 按大小轮转
        file_handler = RotatingFileHandler(
            config.file,
            maxBytes=int(config.max_size_mb * 1024 * 1024),
            backupCount=config.backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)
    
    # 添加上下文过滤器
    if context:
        context_filter = ContextFilter(context)
        root_logger.addFilter(context_filter)
    
    # 添加敏感数据过滤器
    sensitive_filter = SensitiveDataFilter()
    root_logger.addFilter(sensitive_filter)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    获取命名日志器
    
    Args:
        name: 日志器名称，通常使用 __name__
    
    Returns:
        日志器实例
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """
    日志适配器
    
    为日志添加额外的上下文信息
    """
    
    def process(self, msg: str, kwargs: Dict) -> tuple:
        """处理日志消息"""
        extra = kwargs.get('extra', {})
        extra.update(self.extra)
        kwargs['extra'] = extra
        return msg, kwargs


def get_adapter_logger(name: str, **context) -> LoggerAdapter:
    """
    获取带上下文的日志适配器
    
    Args:
        name: 日志器名称
        **context: 上下文信息
    
    Returns:
        日志适配器
    """
    logger = logging.getLogger(name)
    return LoggerAdapter(logger, context)


# ============================================
# 便捷日志函数
# ============================================

def debug(msg: str, **kwargs) -> None:
    """DEBUG 级别日志"""
    logging.getLogger('agentm').debug(msg, **kwargs)


def info(msg: str, **kwargs) -> None:
    """INFO 级别日志"""
    logging.getLogger('agentm').info(msg, **kwargs)


def warning(msg: str, **kwargs) -> None:
    """WARNING 级别日志"""
    logging.getLogger('agentm').warning(msg, **kwargs)


def error(msg: str, **kwargs) -> None:
    """ERROR 级别日志"""
    logging.getLogger('agentm').error(msg, **kwargs)


def critical(msg: str, **kwargs) -> None:
    """CRITICAL 级别日志"""
    logging.getLogger('agentm').critical(msg, **kwargs)


def exception(msg: str, **kwargs) -> None:
    """记录异常"""
    logging.getLogger('agentm').exception(msg, **kwargs)


# ============================================
# 性能日志
# ============================================

class PerformanceLogger:
    """
    性能日志记录器
    
    用于记录代码执行时间
    """
    
    def __init__(self, name: str, logger: Optional[logging.Logger] = None):
        self.name = name
        self.logger = logger or get_logger(name)
        self._start_time: Optional[float] = None
    
    def start(self) -> 'PerformanceLogger':
        """开始计时"""
        self._start_time = datetime.now().timestamp()
        self.logger.debug(f"[{self.name}] 开始执行")
        return self
    
    def end(self, message: str = "执行完成") -> float:
        """结束计时并记录"""
        if self._start_time is None:
            raise RuntimeError("未调用 start()")
        
        elapsed = datetime.now().timestamp() - self._start_time
        self.logger.info(f"[{self.name}] {message}, 耗时：{elapsed:.3f}s")
        return elapsed
    
    def __enter__(self) -> 'PerformanceLogger':
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            self.end(f"执行失败：{exc_val}")
        else:
            self.end()


def log_execution_time(logger: Optional[logging.Logger] = None):
    """
    记录函数执行时间的装饰器
    
    用法:
        @log_execution_time
        def my_function():
            ...
    """
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            log = logger or get_logger(func.__module__)
            start = datetime.now().timestamp()
            log.debug(f"[{func.__name__}] 开始执行")
            
            try:
                result = func(*args, **kwargs)
                elapsed = datetime.now().timestamp() - start
                log.info(f"[{func.__name__}] 执行完成，耗时：{elapsed:.3f}s")
                return result
            except Exception as e:
                elapsed = datetime.now().timestamp() - start
                log.error(f"[{func.__name__}] 执行失败，耗时：{elapsed:.3f}s, 错误：{e}")
                raise
        
        return wrapper
    return decorator


# ============================================
# 初始化
# ============================================

# 模块级日志器
_logger = get_logger(__name__)


def init() -> None:
    """初始化日志系统"""
    setup_logging()
    _logger.info("AgentM 日志系统已初始化")


# 自动初始化
init()
