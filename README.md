# Agent Backend

一个基于FastAPI的智能代理后端系统，集成了Redis和MongoDB数据存储功能。

## 🚀 功能特性

- **FastAPI框架**: 高性能异步Web框架
- **Redis集成**: 缓存和会话管理
- **MongoDB集成**: 文档数据库存储
- **Docker支持**: 容器化部署
- **异步客户端**: 高效的数据库连接管理
- **配置管理**: YAML格式的环境配置

## 📦 项目结构

```txt
agent_backend/
├── copilot/                    # 主应用模块
│   ├── config/                 # 配置文件
│   │   └── config.dev.yaml    # 开发环境配置
│   ├── docs/                   # 文档目录
│   │   └── mongodb_usage.md   # MongoDB使用指南
│   ├── examples/               # 示例代码
│   │   └── mongo_example.py   # MongoDB使用示例
│   ├── tools/                  # 工具模块
│   ├── utils/                  # 工具类
│   │   ├── config.py          # 配置管理
│   │   ├── logger.py          # 日志管理
│   │   ├── redis_client.py    # Redis客户端
│   │   └── mongo_client.py    # MongoDB客户端
│   └── main.py                # 主应用入口
├── docker/                     # Docker配置
│   └── docker-compose.yml     # 服务编排配置
├── requirements.txt            # Python依赖
└── run.py                     # 应用启动脚本
```

## 🛠️ 环境准备

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动数据库服务

```bash
cd docker
docker-compose up -d
```

这将启动以下服务：

- **MongoDB**: localhost:27017 (用户: root, 密码: 123456)
- **Qdrant**: localhost:6333

## ⚙️ 配置说明

配置文件位于 `copilot/config/config.dev.yaml`:

```yaml
logger:
  dir: "/data/agent_backend/logs"
  level: "debug"

redis:
  host: "localhost"
  port: 6379
  db: 0
  password: null
  max_connections: 10

mongodb:
  host: "localhost"
  port: 27017
  database: "copilot"
  username: "root"
  password: "123456"
  auth_source: "admin"
  max_pool_size: 10
  min_pool_size: 1
  connect_timeout: 30000
  server_selection_timeout: 30000
```

## 💻 使用示例

### MongoDB操作

```python
from copilot.utils.mongo_client import MongoClient

async def example():
    async with MongoClient() as mongo:
        # 插入文档
        doc_id = await mongo.insert_one("users", {
            "name": "张三",
            "email": "zhangsan@example.com"
        })
        
        # 查询文档
        user = await mongo.find_one("users", {"name": "张三"})
        print(user)
```

### Redis操作

```python
from copilot.utils.redis_client import get_redis, redis_client

# 推荐方式：使用上下文管理器
async def example():
    async with get_redis() as redis:
        # 设置键值
        await redis.set("key", "value", ex=3600)
        
        # 获取键值
        value = await redis.get("key")
        print(value)
        
        # 集合操作
        await redis.sadd("myset", "item1", "item2")
        members = await redis.smembers("myset")

# 简单方式：直接使用全局实例
async def simple_example():
    await redis_client.set("simple_key", "simple_value")
    value = await redis_client.get("simple_key")
    
    # 便捷方法：缓存模式
    result = await redis_client.get_or_set(
        "cache_key", 
        lambda: "expensive_result", 
        ex=300
    )
```

## 🔧 运行示例

### MongoDB示例

```bash
python copilot/examples/mongo_example.py
```

### Redis测试

```bash
python copilot/utils/redis_client.py
```

## 📚 文档

- [MongoDB使用指南](copilot/docs/mongodb_usage.md) - 详细的MongoDB集成说明

## 🚀 快速开始

1. **克隆项目**

   ```bash
   git clone <repository-url>
   cd agent_backend
   ```

2. **安装依赖**

   ```bash
   pip install -r requirements.txt
   ```

3. **启动服务**

   ```bash
   docker-compose -f docker/docker-compose.yml up -d
   ```

4. **运行应用**

   ```bash
   python run.py
   ```

5. **测试连接**

   ```bash
   python copilot/examples/mongo_example.py
   ```

## 🐛 故障排除

### MongoDB连接问题

1. 确保Docker服务已启动
2. 检查配置文件中的连接信息
3. 验证MongoDB容器状态: `docker ps`

### 依赖安装问题

如果遇到外部管理环境错误，请使用虚拟环境：

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。
