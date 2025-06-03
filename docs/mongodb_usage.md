# MongoDB连接使用指南

本项目已集成MongoDB连接功能，提供了完整的异步MongoDB客户端封装。

## 📋 目录

- [环境准备](#环境准备)
- [配置说明](#配置说明) 
- [基本使用](#基本使用)
- [API参考](#api参考)
- [示例代码](#示例代码)
- [常见问题](#常见问题)

## 🚀 环境准备

### 1. 安装依赖

```bash
pip install motor pymongo
```

### 2. 启动MongoDB服务

使用Docker Compose启动MongoDB：

```bash
docker-compose up -d mongodb
```

MongoDB服务配置：
- 端口: 27017
- 用户名: root
- 密码: 123456
- 认证数据库: admin

## ⚙️ 配置说明

MongoDB配置位于 [`config.dev.yaml`](../config/config.dev.yaml) 文件中：

```yaml
mongodb:
  host: "localhost"              # MongoDB主机地址
  port: 27017                   # MongoDB端口
  database: "copilot"           # 数据库名称
  username: "root"              # 用户名
  password: "123456"            # 密码
  auth_source: "admin"          # 认证数据库
  max_pool_size: 10             # 最大连接池大小
  min_pool_size: 1              # 最小连接池大小
  connect_timeout: 30000        # 连接超时(毫秒)
  server_selection_timeout: 30000 # 服务器选择超时(毫秒)
```

## 💻 基本使用

### 导入客户端

```python
from copilot.utils.mongo_client import MongoClient
```

### 使用上下文管理器

```python
async def example():
    async with MongoClient() as mongo:
        # 检查连接
        is_connected = await mongo.ping()
        print(f"MongoDB连接状态: {is_connected}")
        
        # 进行数据库操作...
```

### 手动管理连接

```python
async def example():
    mongo = MongoClient()
    await mongo.connect()
    
    try:
        # 进行数据库操作...
        pass
    finally:
        await mongo.close()
```

## 📚 API参考

### 连接管理

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `connect()` | 连接到MongoDB | `None` |
| `close()` | 关闭连接 | `None` |
| `ping()` | 检查连接状态 | `bool` |
| `get_collection(name)` | 获取集合对象 | `AsyncIOMotorCollection` |

### 文档操作

#### 插入操作

```python
# 插入单个文档
doc_id = await mongo.insert_one("users", {
    "name": "张三",
    "email": "zhangsan@example.com"
})

# 插入多个文档
doc_ids = await mongo.insert_many("users", [
    {"name": "李四", "email": "lisi@example.com"},
    {"name": "王五", "email": "wangwu@example.com"}
])
```

#### 查询操作

```python
# 查询单个文档
user = await mongo.find_one("users", {"name": "张三"})

# 查询多个文档
users = await mongo.find_many("users", {"age": {"$gte": 18}})

# 带排序和限制的查询
users = await mongo.find_many(
    "users", 
    {"status": "active"},
    limit=10,
    skip=0,
    sort=[("created_at", -1)]
)
```

#### 更新操作

```python
# 更新单个文档
updated_count = await mongo.update_one(
    "users",
    {"name": "张三"},
    {"$set": {"age": 30}}
)

# 更新多个文档
updated_count = await mongo.update_many(
    "users",
    {"status": "inactive"},
    {"$set": {"status": "active"}}
)
```

#### 删除操作

```python
# 删除单个文档
deleted_count = await mongo.delete_one("users", {"name": "张三"})

# 删除多个文档
deleted_count = await mongo.delete_many("users", {"status": "inactive"})
```

#### 其他操作

```python
# 统计文档数量
count = await mongo.count_documents("users", {"age": {"$gte": 18}})

# 创建索引
index_name = await mongo.create_index("users", "email", unique=True)
```

## 🔥 示例代码

### 用户管理示例

```python
import asyncio
from datetime import datetime
from copilot.utils.mongo_client import MongoClient

async def user_management():
    async with MongoClient() as mongo:
        # 创建用户
        user_data = {
            "username": "john_doe",
            "email": "john@example.com",
            "profile": {
                "first_name": "John",
                "last_name": "Doe",
                "age": 28
            },
            "created_at": datetime.now(),
            "status": "active"
        }
        
        user_id = await mongo.insert_one("users", user_data)
        print(f"创建用户: {user_id}")
        
        # 查询用户
        user = await mongo.find_one("users", {"username": "john_doe"})
        print(f"用户信息: {user}")
        
        # 更新用户
        await mongo.update_one(
            "users",
            {"_id": user_id},
            {"$set": {"profile.age": 29}}
        )
        
        # 删除用户
        await mongo.delete_one("users", {"_id": user_id})

if __name__ == "__main__":
    asyncio.run(user_management())
```

### 文章管理示例

更多完整示例请查看 [`mongo_example.py`](../examples/mongo_example.py)

## 🛠️ 运行示例

```bash
# 进入项目目录
cd /data/agent_backend

# 确保MongoDB服务运行
docker-compose up -d mongodb

# 运行示例
python copilot/examples/mongo_example.py
```

## ❓ 常见问题

### 1. 连接失败

**问题**: `PyMongoError: [Errno 111] Connection refused`

**解决方案**:
- 确保MongoDB服务已启动: `docker-compose up -d mongodb`
- 检查配置文件中的主机和端口设置
- 确认防火墙设置

### 2. 认证失败

**问题**: `PyMongoError: Authentication failed`

**解决方案**:
- 检查配置中的用户名和密码
- 确认认证数据库设置正确
- 验证MongoDB用户权限

### 3. 依赖包未安装

**问题**: `ModuleNotFoundError: No module named 'motor'`

**解决方案**:
```bash
pip install motor pymongo
```

### 4. 索引创建失败

**问题**: 重复创建相同索引

**解决方案**:
- 索引已存在时会抛出异常，这是正常行为
- 可以使用 `try-except` 处理重复创建的情况

### 5. 类型检查警告

**问题**: Pylance类型检查警告

**解决方案**:
- 这些警告不影响代码运行
- 确保安装了motor和pymongo依赖包
- 可以在开发环境中忽略这些警告

## 🔧 高级用法

### 自定义连接池

```python
# 在配置文件中调整连接池设置
mongodb:
  max_pool_size: 50      # 增加最大连接数
  min_pool_size: 5       # 增加最小连接数
```

### 事务支持

```python
async with mongo._client.start_session() as session:
    async with session.start_transaction():
        await mongo.insert_one("users", user_data, session=session)
        await mongo.insert_one("profiles", profile_data, session=session)
        # 事务会自动提交或回滚
```

### 聚合查询

```python
collection = mongo.get_collection("users")
pipeline = [
    {"$match": {"status": "active"}},
    {"$group": {"_id": "$department", "count": {"$sum": 1}}},
    {"$sort": {"count": -1}}
]
results = await collection.aggregate(pipeline).to_list(None)
```

## 📝 最佳实践

1. **使用上下文管理器**: 确保连接正确关闭
2. **异常处理**: 捕获并处理`PyMongoError`异常
3. **索引优化**: 为经常查询的字段创建索引
4. **数据验证**: 在插入前验证数据格式
5. **连接池配置**: 根据应用负载调整连接池大小

---

如有其他问题，请查看项目文档或提交Issue。