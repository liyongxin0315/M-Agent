"""
Database Skill - 数据库操作模块

支持 SQLite 和 PostgreSQL 的异步操作
"""

import logging
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class DatabaseType(Enum):
    """数据库类型枚举"""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


@dataclass
class DatabaseConfig:
    """数据库配置"""
    db_type: DatabaseType
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    sqlite_path: Optional[str] = None
    
    def __post_init__(self) -> None:
        """验证配置"""
        if self.db_type == DatabaseType.SQLITE and not self.sqlite_path:
            raise ValueError("SQLite 数据库必须指定 sqlite_path")
        if self.db_type == DatabaseType.POSTGRESQL:
            if not all([self.host, self.database, self.user]):
                raise ValueError("PostgreSQL 必须指定 host, database, user")


class DatabaseError(Exception):
    """数据库操作异常"""
    def __init__(self, message: str, operation: str = "", details: Optional[Dict] = None):
        self.operation = operation
        self.details = details or {}
        super().__init__(f"[{operation}] {message}")


class BaseDatabase(ABC):
    """数据库基类"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._connection = None
        self._cursor = None
    
    @abstractmethod
    async def connect(self) -> None:
        """建立数据库连接"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """关闭数据库连接"""
        pass
    
    @abstractmethod
    async def execute(self, query: str, params: Optional[tuple] = None) -> int:
        """执行写操作（INSERT/UPDATE/DELETE）"""
        pass
    
    @abstractmethod
    async def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """执行查询并返回所有结果"""
        pass
    
    @abstractmethod
    async def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """执行查询并返回单条结果"""
        pass
    
    @asynccontextmanager
    async def transaction(self):
        """事务上下文管理器"""
        if not self._connection:
            await self.connect()
        
        try:
            yield self
            await self._commit()
        except Exception as e:
            await self._rollback()
            raise DatabaseError(str(e), "transaction", {"query_type": "transaction"})
    
    @abstractmethod
    async def _commit(self) -> None:
        """提交事务"""
        pass
    
    @abstractmethod
    async def _rollback(self) -> None:
        """回滚事务"""
        pass


class SQLiteDatabase(BaseDatabase):
    """SQLite 数据库实现"""
    
    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self._import_dependencies()
    
    def _import_dependencies(self) -> None:
        """延迟导入依赖"""
        try:
            import aiosqlite
            self._aiosqlite = aiosqlite
        except ImportError as e:
            logger.error("缺少依赖：pip install aiosqlite")
            raise DatabaseError(f"缺少依赖 aiosqlite: {e}", "import")
    
    async def connect(self) -> None:
        """建立 SQLite 连接"""
        try:
            db_path = Path(self.config.sqlite_path) if self.config.sqlite_path else Path("database.db")
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._connection = await self._aiosqlite.connect(str(db_path))
            self._connection.row_factory = self._aiosqlite.Row
            logger.info(f"SQLite 连接成功：{db_path}")
        except Exception as e:
            raise DatabaseError(str(e), "connect", {"db_type": "sqlite", "path": self.config.sqlite_path})
    
    async def disconnect(self) -> None:
        """关闭 SQLite 连接"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("SQLite 连接已关闭")
    
    async def execute(self, query: str, params: Optional[tuple] = None) -> int:
        """执行写操作"""
        if not self._connection:
            await self.connect()
        
        try:
            cursor = await self._connection.execute(query, params or ())
            await self._connection.commit()
            return cursor.rowcount
        except Exception as e:
            raise DatabaseError(str(e), "execute", {"query": query[:100]})
    
    async def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """执行查询返回所有结果"""
        if not self._connection:
            await self.connect()
        
        try:
            cursor = await self._connection.execute(query, params or ())
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            raise DatabaseError(str(e), "fetch_all", {"query": query[:100]})
    
    async def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """执行查询返回单条结果"""
        if not self._connection:
            await self.connect()
        
        try:
            cursor = await self._connection.execute(query, params or ())
            row = await cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            raise DatabaseError(str(e), "fetch_one", {"query": query[:100]})
    
    async def _commit(self) -> None:
        """提交事务"""
        if self._connection:
            await self._connection.commit()
    
    async def _rollback(self) -> None:
        """回滚事务"""
        if self._connection:
            await self._connection.rollback()
    
    async def create_table(self, table_name: str, columns: Dict[str, str]) -> None:
        """创建表"""
        column_defs = ", ".join(f"{name} {dtype}" for name, dtype in columns.items())
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({column_defs})"
        await self.execute(query)
        logger.info(f"创建表成功：{table_name}")
    
    async def insert(self, table_name: str, data: Dict[str, Any]) -> int:
        """插入数据"""
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        return await self.execute(query, tuple(data.values()))
    
    async def update(self, table_name: str, data: Dict[str, Any], where: str, where_params: tuple) -> int:
        """更新数据"""
        set_clause = ", ".join(f"{col} = ?" for col in data.keys())
        query = f"UPDATE {table_name} SET {set_clause} WHERE {where}"
        return await self.execute(query, (*data.values(), *where_params))
    
    async def delete(self, table_name: str, where: str, where_params: tuple) -> int:
        """删除数据"""
        query = f"DELETE FROM {table_name} WHERE {where}"
        return await self.execute(query, where_params)


class PostgreSQLDatabase(BaseDatabase):
    """PostgreSQL 数据库实现"""
    
    def __init__(self, config: DatabaseConfig):
        super().__init__(config)
        self._import_dependencies()
    
    def _import_dependencies(self) -> None:
        """延迟导入依赖"""
        try:
            import asyncpg
            self._asyncpg = asyncpg
        except ImportError as e:
            logger.error("缺少依赖：pip install asyncpg")
            raise DatabaseError(f"缺少依赖 asyncpg: {e}", "import")
    
    def _build_connection_string(self) -> str:
        """构建连接字符串"""
        return (
            f"postgresql://{self.config.user}:{self.config.password}@"
            f"{self.config.host}:{self.config.port}/{self.config.database}"
        )
    
    async def connect(self) -> None:
        """建立 PostgreSQL 连接"""
        try:
            conn_string = self._build_connection_string()
            self._connection = await self._asyncpg.connect(conn_string)
            logger.info(f"PostgreSQL 连接成功：{self.config.host}:{self.config.port}/{self.config.database}")
        except Exception as e:
            raise DatabaseError(str(e), "connect", {"db_type": "postgresql", "host": self.config.host})
    
    async def disconnect(self) -> None:
        """关闭 PostgreSQL 连接"""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("PostgreSQL 连接已关闭")
    
    async def execute(self, query: str, params: Optional[tuple] = None) -> int:
        """执行写操作"""
        if not self._connection:
            await self.connect()
        
        try:
            result = await self._connection.execute(query, *(params or ()))
            # asyncpg 返回的是状态字符串如 "INSERT 0 1"
            parts = result.split()
            return int(parts[-1]) if parts[-1].isdigit() else 0
        except Exception as e:
            raise DatabaseError(str(e), "execute", {"query": query[:100]})
    
    async def fetch_all(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """执行查询返回所有结果"""
        if not self._connection:
            await self.connect()
        
        try:
            rows = await self._connection.fetch(query, *(params or ()))
            return [dict(row) for row in rows]
        except Exception as e:
            raise DatabaseError(str(e), "fetch_all", {"query": query[:100]})
    
    async def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
        """执行查询返回单条结果"""
        if not self._connection:
            await self.connect()
        
        try:
            row = await self._connection.fetchrow(query, *(params or ()))
            return dict(row) if row else None
        except Exception as e:
            raise DatabaseError(str(e), "fetch_one", {"query": query[:100]})
    
    async def _commit(self) -> None:
        """提交事务"""
        # PostgreSQL 的 asyncpg 在自动模式下处理事务
        pass
    
    async def _rollback(self) -> None:
        """回滚事务"""
        # PostgreSQL 的 asyncpg 在自动模式下处理事务
        pass
    
    async def create_table(self, table_name: str, columns: Dict[str, str]) -> None:
        """创建表"""
        column_defs = ", ".join(f"{name} {dtype}" for name, dtype in columns.items())
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({column_defs})"
        await self.execute(query)
        logger.info(f"创建表成功：{table_name}")
    
    async def insert(self, table_name: str, data: Dict[str, Any]) -> int:
        """插入数据"""
        columns = ", ".join(data.keys())
        placeholders = ", ".join([f"${i+1}" for i in range(len(data))])
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
        return await self.execute(query, tuple(data.values()))
    
    async def update(self, table_name: str, data: Dict[str, Any], where: str, where_params: tuple) -> int:
        """更新数据"""
        set_clause = ", ".join(f"{col} = ${i+1}" for i, col in enumerate(data.keys()))
        param_count = len(data)
        where_clause = where.replace("%s", lambda m: f"${param_count + int(m.group(0))}")
        query = f"UPDATE {table_name} SET {set_clause} WHERE {where}"
        return await self.execute(query, (*data.values(), *where_params))
    
    async def delete(self, table_name: str, where: str, where_params: tuple) -> int:
        """删除数据"""
        query = f"DELETE FROM {table_name} WHERE {where}"
        return await self.execute(query, where_params)


class DatabaseSkill:
    """数据库技能主类"""
    
    def __init__(self):
        self._databases: Dict[str, BaseDatabase] = {}
    
    def create_database(self, name: str, config: DatabaseConfig) -> BaseDatabase:
        """创建数据库实例"""
        if config.db_type == DatabaseType.SQLITE:
            db = SQLiteDatabase(config)
        elif config.db_type == DatabaseType.POSTGRESQL:
            db = PostgreSQLDatabase(config)
        else:
            raise DatabaseError(f"不支持的数据库类型：{config.db_type}", "create_database")
        
        self._databases[name] = db
        logger.info(f"创建数据库实例：{name} ({config.db_type.value})")
        return db
    
    def get_database(self, name: str) -> BaseDatabase:
        """获取数据库实例"""
        if name not in self._databases:
            raise DatabaseError(f"数据库实例不存在：{name}", "get_database")
        return self._databases[name]
    
    async def close_all(self) -> None:
        """关闭所有数据库连接"""
        for name, db in self._databases.items():
            try:
                await db.disconnect()
                logger.info(f"数据库连接已关闭：{name}")
            except Exception as e:
                logger.error(f"关闭数据库 {name} 失败：{e}")


# 便捷函数
async def create_sqlite(name: str, path: str) -> SQLiteDatabase:
    """快速创建 SQLite 数据库"""
    config = DatabaseConfig(
        db_type=DatabaseType.SQLITE,
        sqlite_path=path
    )
    skill = DatabaseSkill()
    db = skill.create_database(name, config)
    await db.connect()
    return db


async def create_postgresql(
    name: str,
    host: str,
    port: int,
    database: str,
    user: str,
    password: str
) -> PostgreSQLDatabase:
    """快速创建 PostgreSQL 数据库"""
    config = DatabaseConfig(
        db_type=DatabaseType.POSTGRESQL,
        host=host,
        port=port,
        database=database,
        user=user,
        password=password
    )
    skill = DatabaseSkill()
    db = skill.create_database(name, config)
    await db.connect()
    return db
