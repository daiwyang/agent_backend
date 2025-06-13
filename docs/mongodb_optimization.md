# MongoDB连接优化说明

## 问题描述

原有的代码中，每次调用 `chat` 方法时都需要打开和关闭MongoDB连接，这导致了以下问题：

1. **性能低下**：每次聊天至少需要建立2-3次数据库连接（保存用户消息、保存助手回复、更新会话状态）
2. **资源浪费**：频繁的连接建立和销毁消耗大量系统资源
3. **延迟增加**：每次连接建立都需要网络握手和认证过程

## 优化方案

### 1. 连接池管理器 (MongoConnectionManager)

实现了一个单例的MongoDB连接管理器，主要特性：

- **单例模式**：确保整个应用只有一个连接池实例
- **异步锁保护**：防止并发初始化问题
- **自动重连**：检测连接状态并自动重新连接
- **连接池配置**：支持最大/最小连接数等参数配置

```python
class MongoConnectionManager:
    _instance = None
    _lock = asyncio.Lock()
    
    @classmethod
    async def get_instance(cls):
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    await cls._instance._ensure_connected()
        return cls._instance
```

### 2. 兼容性设计 (MongoClient)

修改原有的MongoClient类，支持两种模式：

- **传统模式** (`use_shared_connection=False`)：保持向后兼容
- **连接池模式** (`use_shared_connection=True`)：默认使用共享连接

```python
# 传统模式
async with MongoClient(use_shared_connection=False) as mongo:
    await mongo.insert_one(collection_name, document)

# 连接池模式（推荐）
async with MongoClient() as mongo:  # 默认使用共享连接
    await mongo.insert_one(collection_name, document)
```

### 3. 聊天历史管理器优化 (ChatHistoryManager)

完全重构了所有数据库操作方法：

- **移除频繁连接**：不再使用 `async with MongoClient()` 模式
- **共享连接**：所有操作复用同一个连接池
- **延迟初始化**：连接管理器按需创建

```python
# 优化前
async def save_message(self, session_id: str, role: str, content: str, metadata: Dict[str, Any] = None):
    async with MongoClient() as mongo:  # 每次都创建新连接
        await mongo.insert_one(self.messages_collection, message_doc)

# 优化后
async def save_message(self, session_id: str, role: str, content: str, metadata: Dict[str, Any] = None):
    mongo_manager = await self._get_mongo_manager()  # 复用连接池
    collection = await mongo_manager.get_collection(self.messages_collection)
    await collection.insert_one(message_doc)
```

### 4. 应用生命周期管理

在FastAPI应用中添加了启动和关闭事件处理：

```python
@app.on_event("startup")
async def startup_event():
    """应用启动事件：初始化MongoDB连接池"""
    mongo_manager = await get_mongo_manager()
    logger.info("MongoDB connection pool initialized successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件：清理MongoDB连接"""
    mongo_manager = await get_mongo_manager()
    await mongo_manager.close()
    logger.info("MongoDB connections closed")
```

## 性能提升

### 预期改进

1. **连接开销减少**：从每次操作建立连接减少到应用启动时建立一次
2. **响应时间降低**：减少连接建立的网络延迟
3. **资源利用率提升**：连接池复用，减少系统资源消耗
4. **并发性能提升**：支持更高的并发聊天请求

### 测试建议

可以运行 `test_mongo_optimization.py` 来对比优化前后的性能差异：

```bash
cd /data/agent_backend
python test_mongo_optimization.py
```

## 配置说明

MongoDB连接池配置位于配置文件中：

```yaml
mongodb:
  host: localhost
  port: 27017
  database: copilot
  max_pool_size: 10      # 最大连接数
  min_pool_size: 1       # 最小连接数
  connect_timeout: 30000 # 连接超时时间（毫秒）
  server_selection_timeout: 30000 # 服务器选择超时时间（毫秒）
```

## 向后兼容性

- 保持了原有API接口不变
- 支持传统连接模式作为备选方案
- 无需修改现有的调用代码

## 注意事项

1. **线程安全**：连接管理器使用异步锁保护，确保并发安全
2. **错误处理**：增加了连接状态检测和自动重连机制
3. **资源清理**：应用关闭时会正确清理连接资源
4. **监控建议**：可以通过日志监控连接池的使用情况

## 后续优化建议

1. **连接池监控**：添加连接池使用率监控和报警
2. **读写分离**：支持读写分离的数据库架构
3. **缓存层**：考虑添加Redis缓存减少数据库访问
4. **批量操作**：对频繁的小操作进行批量优化
