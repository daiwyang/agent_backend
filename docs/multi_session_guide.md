# Agent多轮对话和会话管理指南

## 概述

本指南展示了如何实现支持多用户、多窗口的Agent对话系统，每个会话都维护独立的上下文和对话历史。

## 核心概念

### 1. 会话(Session)

- **定义**: 一次完整的对话过程，从用户开始对话到结束对话
- **特点**: 每个会话有唯一的ID，维护独立的对话历史和上下文
- **生命周期**: 创建 → 活跃对话 → 超时或手动删除

### 2. 多窗口支持

- **场景**: 同一用户可能在多个设备/窗口同时与Agent对话
- **实现**: 通过`user_id` + `window_id`区分不同的对话会话
- **优势**: 用户可以在桌面和手机上同时进行不同主题的对话

### 3. 会话管理

- **会话存储**: 使用Redis存储会话信息（生产环境）或内存存储（演示）
- **会话超时**: 自动清理长时间未活跃的会话
- **会话查询**: 支持查询用户的所有活跃会话

## 架构设计

### 系统组件

```text
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client Apps   │    │  FastAPI Server │    │ Session Manager │
│                 │    │                 │    │                 │
│ - Web UI        │───▶│ - HTTP API      │───▶│ - Redis Storage │
│ - Mobile App    │    │ - Route Handler │    │ - Session CRUD  │
│ - Desktop App   │    │ - Validation    │    │ - Auto Cleanup  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ LangGraph Agent │
                       │                 │
                       │ - Multi-turn    │
                       │ - Tool Calling  │
                       │ - Memory Save   │
                       └─────────────────┘
```

**组件说明**：

- **Client Apps**: 客户端应用（Web界面、移动APP、桌面应用）
- **FastAPI Server**: FastAPI服务（HTTP API、路由处理、请求验证）
- **Session Manager**: 会话管理器（Redis存储、会话CRUD、超时清理）
- **LangGraph Agent**: LangGraph代理（多轮对话、工具调用、记忆保存）

### 数据流

1. **创建会话**: 客户端 → API → 会话管理器 → Redis
2. **发送消息**: 客户端 → API → Agent → 响应返回
3. **获取历史**: 客户端 → API → Agent → 对话历史
4. **会话管理**: 定时任务清理过期会话

## 核心实现

### 1. 会话管理器 (`session_manager.py`)

```python
class SessionManager:
    """会话管理器"""
    
    async def create_session(self, user_id: str, window_id: str = None) -> str:
        """创建新会话"""
        
    async def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """获取会话信息"""
        
    async def get_user_sessions(self, user_id: str) -> List[SessionInfo]:
        """获取用户的所有活跃会话"""
        
    async def delete_session(self, session_id: str):
        """删除会话"""
```

**关键特性**:

- 基于Redis的分布式会话存储
- 自动超时清理机制
- 支持用户多会话查询
- 线程安全的并发操作

### 2. 多会话Agent (`multi_session_agent.py`)

```python
class MultiSessionAgent:
    """多会话Agent"""
    
    async def create_session(self, user_id: str, window_id: str = None) -> str:
        """创建新的对话会话"""
        
    async def chat(self, session_id: str, message: str) -> ChatResponse:
        """发送消息并获取回复"""
        
    async def chat_stream(self, session_id: str, message: str) -> AsyncGenerator:
        """流式聊天，实时返回响应片段"""
        
    async def get_chat_history(self, session_id: str) -> List[ChatMessage]:
        """获取聊天历史"""
```

**关键特性**:

- 基于LangGraph的对话管理
- 支持流式响应
- 独立的线程ID确保会话隔离
- 错误处理和恢复机制

### 3. Web API (`chat_api.py`)

```python
@app.post("/sessions", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """创建新的聊天会话"""

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """发送聊天消息"""

@app.get("/users/{user_id}/sessions", response_model=List[SessionInfo])
async def get_user_sessions(user_id: str):
    """获取用户的所有会话"""
```

**关键特性**:

- RESTful API设计
- 请求/响应模型验证
- CORS支持
- 错误处理和状态码

## 使用示例

### 1. 基本用法

```python
# 创建Agent实例
agent = MultiSessionAgent()

# 用户在桌面浏览器创建会话
desktop_session = await agent.create_session("alice", "desktop")

# 用户在手机APP创建会话
mobile_session = await agent.create_session("alice", "mobile")

# 在不同会话中进行对话
desktop_response = await agent.chat(desktop_session, "北京天气怎么样？")
mobile_response = await agent.chat(mobile_session, "介绍一下Python")
```

### 2. 多窗口场景

**用户Alice的使用场景**:

1. 在桌面浏览器查询天气信息
2. 同时在手机APP学习编程知识
3. 两个对话保持独立的上下文

**实现代码**:

```python
# Alice桌面会话 - 天气主题
alice_desktop = await agent.create_session("alice", "desktop_browser")
await agent.chat(alice_desktop, "你好")
await agent.chat(alice_desktop, "今天天气怎么样？")
await agent.chat(alice_desktop, "北京的天气")

# Alice手机会话 - 学习主题  
alice_mobile = await agent.create_session("alice", "mobile_app")
await agent.chat(alice_mobile, "帮我介绍一下Python")
await agent.chat(alice_mobile, "它有什么优势？")
```

### 3. API调用示例

```bash
# 创建会话
curl -X POST "http://localhost:8001/sessions" \
     -H "Content-Type: application/json" \
     -d '{"user_id": "alice", "window_id": "desktop"}'

# 发送消息
curl -X POST "http://localhost:8001/chat" \
     -H "Content-Type: application/json" \
     -d '{"session_id": "xxx", "message": "你好"}'

# 获取用户会话
curl "http://localhost:8001/users/alice/sessions"
```

## 最佳实践

### 1. 会话生命周期管理

```python
# 设置合适的超时时间
session_manager = SessionManager(session_timeout=3600)  # 1小时

# 定时清理过期会话
async def cleanup_task():
    while True:
        await session_manager.cleanup_expired_sessions()
        await asyncio.sleep(300)  # 每5分钟清理一次
```

### 2. 错误处理

```python
async def safe_chat(session_id: str, message: str):
    try:
        return await agent.chat(session_id, message)
    except ValueError as e:
        # 会话不存在或过期
        return {"error": "Session expired", "code": "SESSION_EXPIRED"}
    except Exception as e:
        # 其他错误
        return {"error": "Internal error", "code": "INTERNAL_ERROR"}
```

### 3. 性能优化

- **连接池**: 使用Redis连接池减少连接开销
- **缓存**: 缓存频繁访问的会话信息
- **异步**: 全异步设计避免阻塞
- **批量操作**: 批量处理会话清理任务

### 4. 安全考虑

- **用户验证**: 验证用户身份
- **会话隔离**: 确保会话间数据隔离
- **访问控制**: 用户只能访问自己的会话
- **数据加密**: 敏感数据加密存储

## 部署指南

### 1. 依赖安装

```bash
pip install langgraph langchain-openai fastapi uvicorn redis aiohttp
```

### 2. 配置文件

```yaml
# config.yaml
redis:
  host: "localhost"
  port: 6379
  db: 0
  max_connections: 10

agent:
  model: "deepseek:deepseek-chat"
  session_timeout: 3600
```

### 3. 启动服务

```bash
# 启动API服务器
python -m uvicorn copilot.api.chat_api:app --host 0.0.0.0 --port 8001

# 启动清理任务
python -m copilot.tasks.cleanup_sessions
```

## 扩展功能

### 1. 会话分析

- 统计会话数量和时长
- 分析用户对话模式
- 监控系统性能指标

### 2. 个性化

- 基于历史对话的个性化响应
- 用户偏好学习和记忆
- 上下文感知的智能推荐

### 3. 集成能力

- 与第三方系统集成
- 支持Webhook通知
- 多模态对话支持（文本、语音、图片）

## 监控和维护

### 1. 关键指标

- 活跃会话数量
- 平均响应时间
- 错误率
- 内存和CPU使用率

### 2. 日志管理

- 结构化日志输出
- 错误追踪和告警
- 性能监控数据

### 3. 故障恢复

- 会话数据备份
- 服务重启策略
- 降级方案

## 总结

通过本指南的实现，您可以构建一个完整的多会话Agent系统，支持：

✅ **多用户并发**：同时服务多个用户  
✅ **多窗口支持**：用户可在多个设备/窗口对话  
✅ **会话隔离**：每个会话独立的上下文和历史  
✅ **自动管理**：会话超时清理和错误恢复  
✅ **高性能**：异步设计和连接池优化  
✅ **易扩展**：模块化设计便于功能扩展  

这个架构可以满足大多数多轮对话应用的需求，并为进一步的功能扩展提供了坚实的基础。

## 聊天历史持久化

### 问题描述

之前的实现中，所有对话数据只存储在Redis中，存在以下问题：

1. **数据丢失风险**: 当会话超时后，所有对话历史都会丢失
2. **无法追溯**: 用户无法查看之前的对话记录
3. **体验不连续**: 新会话无法获取历史上下文
4. **无法分析**: 缺少长期数据用于改进AI服务

### 解决方案

新增了 `ChatHistoryManager` 来实现对话历史的持久化存储：

#### 1. 双层存储架构

- **Redis**: 用于活跃会话的快速访问（临时存储）
- **MongoDB**: 用于所有对话的长期持久化存储

#### 2. 核心功能

**会话恢复**:

```python
# 当Redis中的会话过期时，自动从数据库恢复
session = await session_manager.get_session(session_id)
# 如果Redis中没有，会自动从MongoDB恢复
```

**消息持久化**:

```python
# 每条消息都会同时保存到数据库
await chat_history_manager.save_message(
    session_id=session_id,
    role="user",  # 或 "assistant"
    content=message,
    metadata={"timestamp": datetime.now()}
)
```

**历史查询**:

```python
# 获取会话完整历史
messages = await agent.get_chat_history(session_id, from_db=True)

# 获取用户所有会话
user_sessions = await agent.get_user_chat_history(user_id)

# 搜索对话内容
results = await agent.search_chat_history(user_id, "关键词")
```

#### 3. API接口

新增了以下API端点：

- `GET /sessions/{session_id}/history` - 获取会话历史
- `GET /users/{user_id}/chat-history` - 获取用户所有对话
- `POST /search` - 搜索对话内容
- `GET /stats` - 获取统计信息

#### 4. 数据库结构

**chat_sessions集合**:

```javascript
{
  session_id: "uuid",
  user_id: "string",
  window_id: "string", 
  thread_id: "string",
  created_at: Date,
  last_activity: Date,
  context: {},
  status: "active|archived|deleted"
}
```

**chat_messages集合**:

```javascript
{
  session_id: "uuid",
  role: "user|assistant",
  content: "string",
  timestamp: Date,
  metadata: {}
}
```

#### 5. 使用示例

```python
from copilot.agent.multi_session_agent import MultiSessionAgent

agent = MultiSessionAgent()

# 创建会话
session_id = await agent.create_session("user123", "window1")

# 对话（自动保存到数据库）
response = await agent.chat(session_id, "你好")

# 会话超时后...
await agent.delete_session(session_id, archive=True)

# 重新访问时自动恢复
session = await agent.session_manager.get_session(session_id)
# 会话从数据库自动恢复到Redis

# 查看完整历史
history = await agent.get_chat_history(session_id, from_db=True)
```

#### 6. 优势

1. **数据安全**: 对话永不丢失，支持灾难恢复
2. **用户体验**: 跨会话的连续对话体验
3. **功能增强**: 支持历史搜索、数据分析
4. **性能平衡**: Redis提供高性能，MongoDB提供持久化
5. **扩展性**: 支持大规模用户和海量对话数据

#### 7. 配置和部署

```bash
# 初始化数据库索引
python scripts/init_db_indexes.py

# 运行演示
python examples/chat_history_demo.py
```
