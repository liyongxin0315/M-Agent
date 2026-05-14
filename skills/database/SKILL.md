# Database Skill - 数据库操作技能

## 功能描述
提供 SQLite 和 PostgreSQL 数据库的异步操作能力，支持 CRUD、事务处理、连接池管理。

## 激活条件
当用户提到以下关键词时激活：
- 数据库操作
- SQLite / PostgreSQL
- 数据存储 / 查询
- CRUD 操作
- 数据库连接

## 依赖安装
```bash
pip install aiosqlite asyncpg pytest pytest-asyncio
```

## 使用示例

### 创建 SQLite 数据库
```python
from agentm.skills.database.database_skill import create_sqlite

# 快速创建
db = await create_sqlite("mydb", "/path/to/database.db")

# 创建表
await db.create_table("users", {
    "id": "INTEGER PRIMARY KEY",
    "name": "TEXT NOT NULL",
    "email": "TEXT UNIQUE"
})

# 插入数据
await db.insert("users", {
    "id": 1,
    "name": "张三",
    "email": "zhangsan@example.com"
})

# 查询数据
user = await db.fetch_one("SELECT * FROM users WHERE id = ?", (1,))
all_users = await db.fetch_all("SELECT * FROM users")

# 更新数据
await db.update("users", {"email": "new@example.com"}, "id = ?", (1,))

# 删除数据
await db.delete("users", "id = ?", (1,))

# 事务处理
async with db.transaction():
    await db.insert("users", {"id": 2, "name": "李四"})
    # 如果这里抛出异常，整个事务会回滚
```

### 创建 PostgreSQL 数据库
```python
from agentm.skills.database.database_skill import create_postgresql

db = await create_postgresql(
    name="prod_db",
    host="localhost",
    port=5432,
    database="myapp",
    user="dbuser",
    password="dbpass"
)
```

### 使用 DatabaseSkill 管理多个数据库
```python
from agentm.skills.database.database_skill import DatabaseSkill, DatabaseConfig, DatabaseType

skill = DatabaseSkill()

# 创建 SQLite 数据库
sqlite_config = DatabaseConfig(
    db_type=DatabaseType.SQLITE,
    sqlite_path="/tmp/app.db"
)
sqlite_db = skill.create_database("app_db", sqlite_config)
await sqlite_db.connect()

# 创建 PostgreSQL 数据库
pg_config = DatabaseConfig(
    db_type=DatabaseType.POSTGRESQL,
    host="localhost",
    port=5432,
    database="analytics",
    user="analyst",
    password="secret"
)
pg_db = skill.create_database("analytics_db", pg_config)
await pg_db.connect()

# 获取数据库实例
db = skill.get_database("app_db")

# 关闭所有连接
await skill.close_all()
```

## 异常处理
所有数据库操作异常都会抛出 `DatabaseError`，包含：
- `operation`: 失败的操作类型
- `details`: 详细上下文信息

```python
from agentm.skills.database.database_skill import DatabaseError

try:
    await db.fetch_all("SELECT * FROM invalid_table")
except DatabaseError as e:
    print(f"操作失败：{e.operation}")
    print(f"错误详情：{e.details}")
```

## 测试
```bash
cd /home/liyongxin/.openclaw/workspace/agentm/skills/database
pytest test_database.py -v
```

## 文件结构
```
database/
├── SKILL.md              # 技能说明文档
├── README.md             # 快速入门
├── database_skill.py     # 核心实现
├── test_database.py      # 单元测试
└── __init__.py           # 模块初始化
```
