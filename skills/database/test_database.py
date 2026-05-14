"""
Database Skill 单元测试
"""

import asyncio
import pytest
from pathlib import Path
from database_skill import (
    DatabaseSkill,
    DatabaseConfig,
    DatabaseType,
    DatabaseError,
    SQLiteDatabase,
    create_sqlite
)


class TestDatabaseConfig:
    """测试数据库配置"""
    
    def test_sqlite_config_valid(self):
        """测试有效的 SQLite 配置"""
        config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_path="/tmp/test.db"
        )
        assert config.db_type == DatabaseType.SQLITE
        assert config.sqlite_path == "/tmp/test.db"
    
    def test_sqlite_config_invalid(self):
        """测试无效的 SQLite 配置"""
        with pytest.raises(ValueError, match="sqlite_path"):
            DatabaseConfig(db_type=DatabaseType.SQLITE)
    
    def test_postgresql_config_valid(self):
        """测试有效的 PostgreSQL 配置"""
        config = DatabaseConfig(
            db_type=DatabaseType.POSTGRESQL,
            host="localhost",
            port=5432,
            database="testdb",
            user="testuser",
            password="testpass"
        )
        assert config.db_type == DatabaseType.POSTGRESQL
        assert config.host == "localhost"
    
    def test_postgresql_config_invalid(self):
        """测试无效的 PostgreSQL 配置"""
        with pytest.raises(ValueError, match="host"):
            DatabaseConfig(
                db_type=DatabaseType.POSTGRESQL,
                database="testdb"
            )


class TestSQLiteDatabase:
    """测试 SQLite 数据库操作"""
    
    @pytest.fixture
    async def sqlite_db(self, tmp_path):
        """创建临时 SQLite 数据库"""
        db_path = tmp_path / "test.db"
        config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_path=str(db_path)
        )
        skill = DatabaseSkill()
        db = skill.create_database("test", config)
        await db.connect()
        yield db
        await db.disconnect()
    
    @pytest.mark.asyncio
    async def test_create_table(self, sqlite_db: SQLiteDatabase):
        """测试创建表"""
        await sqlite_db.create_table("users", {
            "id": "INTEGER PRIMARY KEY",
            "name": "TEXT NOT NULL",
            "email": "TEXT UNIQUE"
        })
        # 验证表存在
        result = await sqlite_db.fetch_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        assert result is not None
        assert result["name"] == "users"
    
    @pytest.mark.asyncio
    async def test_insert_and_fetch(self, sqlite_db: SQLiteDatabase):
        """测试插入和查询数据"""
        # 创建表
        await sqlite_db.create_table("users", {
            "id": "INTEGER PRIMARY KEY",
            "name": "TEXT",
            "email": "TEXT"
        })
        
        # 插入数据
        await sqlite_db.insert("users", {
            "id": 1,
            "name": "张三",
            "email": "zhangsan@example.com"
        })
        
        # 查询数据
        result = await sqlite_db.fetch_one(
            "SELECT * FROM users WHERE id = ?",
            (1,)
        )
        assert result is not None
        assert result["name"] == "张三"
        assert result["email"] == "zhangsan@example.com"
    
    @pytest.mark.asyncio
    async def test_update(self, sqlite_db: SQLiteDatabase):
        """测试更新数据"""
        # 创建表并插入数据
        await sqlite_db.create_table("users", {
            "id": "INTEGER PRIMARY KEY",
            "name": "TEXT",
            "email": "TEXT"
        })
        await sqlite_db.insert("users", {
            "id": 1,
            "name": "张三",
            "email": "zhangsan@example.com"
        })
        
        # 更新数据
        rows = await sqlite_db.update(
            "users",
            {"email": "newemail@example.com"},
            "id = ?",
            (1,)
        )
        assert rows == 1
        
        # 验证更新
        result = await sqlite_db.fetch_one(
            "SELECT * FROM users WHERE id = ?",
            (1,)
        )
        assert result["email"] == "newemail@example.com"
    
    @pytest.mark.asyncio
    async def test_delete(self, sqlite_db: SQLiteDatabase):
        """测试删除数据"""
        # 创建表并插入数据
        await sqlite_db.create_table("users", {
            "id": "INTEGER PRIMARY KEY",
            "name": "TEXT"
        })
        await sqlite_db.insert("users", {"id": 1, "name": "张三"})
        await sqlite_db.insert("users", {"id": 2, "name": "李四"})
        
        # 删除数据
        rows = await sqlite_db.delete("users", "id = ?", (1,))
        assert rows == 1
        
        # 验证删除
        all_users = await sqlite_db.fetch_all("SELECT * FROM users")
        assert len(all_users) == 1
        assert all_users[0]["name"] == "李四"
    
    @pytest.mark.asyncio
    async def test_transaction_commit(self, sqlite_db: SQLiteDatabase):
        """测试事务提交"""
        await sqlite_db.create_table("users", {
            "id": "INTEGER PRIMARY KEY",
            "name": "TEXT"
        })
        
        async with sqlite_db.transaction():
            await sqlite_db.insert("users", {"id": 1, "name": "张三"})
            await sqlite_db.insert("users", {"id": 2, "name": "李四"})
        
        # 验证数据已提交
        all_users = await sqlite_db.fetch_all("SELECT * FROM users")
        assert len(all_users) == 2
    
    @pytest.mark.asyncio
    async def test_transaction_rollback(self, sqlite_db: SQLiteDatabase):
        """测试事务回滚"""
        await sqlite_db.create_table("users", {
            "id": "INTEGER PRIMARY KEY",
            "name": "TEXT"
        })
        
        try:
            async with sqlite_db.transaction():
                await sqlite_db.insert("users", {"id": 1, "name": "张三"})
                # 故意引发异常
                raise ValueError("测试回滚")
        except ValueError:
            pass
        
        # 验证数据已回滚
        all_users = await sqlite_db.fetch_all("SELECT * FROM users")
        assert len(all_users) == 0
    
    @pytest.mark.asyncio
    async def test_fetch_all(self, sqlite_db: SQLiteDatabase):
        """测试批量查询"""
        await sqlite_db.create_table("users", {
            "id": "INTEGER PRIMARY KEY",
            "name": "TEXT"
        })
        
        for i in range(5):
            await sqlite_db.insert("users", {"id": i, "name": f"用户{i}"})
        
        all_users = await sqlite_db.fetch_all("SELECT * FROM users")
        assert len(all_users) == 5
    
    @pytest.mark.asyncio
    async def test_error_handling(self, sqlite_db: SQLiteDatabase):
        """测试错误处理"""
        with pytest.raises(DatabaseError) as exc_info:
            await sqlite_db.fetch_all("SELECT * FROM nonexistent_table")
        
        assert exc_info.value.operation == "fetch_all"
        assert "nonexistent_table" in str(exc_info.value)


class TestDatabaseSkill:
    """测试 DatabaseSkill 主类"""
    
    def test_create_multiple_databases(self, tmp_path):
        """测试创建多个数据库实例"""
        skill = DatabaseSkill()
        
        db1_path = tmp_path / "db1.db"
        db2_path = tmp_path / "db2.db"
        
        config1 = DatabaseConfig(db_type=DatabaseType.SQLITE, sqlite_path=str(db1_path))
        config2 = DatabaseConfig(db_type=DatabaseType.SQLITE, sqlite_path=str(db2_path))
        
        skill.create_database("db1", config1)
        skill.create_database("db2", config2)
        
        assert len(skill._databases) == 2
        assert "db1" in skill._databases
        assert "db2" in skill._databases
    
    def test_get_database_exists(self, tmp_path):
        """测试获取存在的数据库"""
        skill = DatabaseSkill()
        db_path = tmp_path / "test.db"
        config = DatabaseConfig(db_type=DatabaseType.SQLITE, sqlite_path=str(db_path))
        skill.create_database("test", config)
        
        db = skill.get_database("test")
        assert db is not None
    
    def test_get_database_not_exists(self):
        """测试获取不存在的数据库"""
        skill = DatabaseSkill()
        
        with pytest.raises(DatabaseError, match="不存在"):
            skill.get_database("nonexistent")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
