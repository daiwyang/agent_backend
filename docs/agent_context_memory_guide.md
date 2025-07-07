# Agent上下文记忆功能指南

## 概述

Agent上下文记忆功能让智能代理能够记住和使用之前的对话历史，提供更连贯、更智能的对话体验。该功能将Redis中的聊天记录与Agent的推理能力相结合，实现真正的上下文感知对话。

## 功能特点

### 🧠 智能记忆管理

- **自动加载历史对话**：Agent会自动从Redis/MongoDB加载相关的对话历史
- **智能上下文截断**：防止上下文过长，自动优化历史消息选择
- **Token优化**：基于模型限制智能控制上下文长度
- **多策略优化**：保留重要对话，压缩冗余信息

### ⚡ 高性能存储

- **双重存储**：Redis缓存 + MongoDB持久化
- **会话隔离**：每个用户会话独立的记忆空间
- **延迟加载**：按需加载历史记录，不影响响应速度

### 🛠 灵活配置

- **全局配置**：设置默认记忆参数
- **会话级配置**：为特定会话自定义记忆设置
- **实时调整**：支持动态修改记忆配置

## 核心组件

### 1. Agent核心类 (`CoreAgent`)

```python
# 支持上下文记忆的Agent初始化
agent = await CoreAgent.create_with_mcp_tools(
    provider="deepseek",
    model_name="deepseek-chat",
    context_memory_enabled=True,        # 启用上下文记忆
    max_history_messages=10,            # 最大历史消息数量
    max_context_tokens=20000           # 最大上下文token数量
)
```

### 2. 聊天服务 (`ChatService`)

```python
# 创建支持记忆的聊天服务
service = await ChatService.create(
    provider="deepseek",
    model_name="deepseek-chat",
    context_memory_enabled=True,
    max_history_messages=15,
    max_context_tokens=25000
)
```

### 3. Agent管理器 (`AgentManager`)

- 为每个会话维护独立的Agent实例
- 自动管理Agent生命周期和记忆配置
- 支持Agent配置热更新

## 配置参数

### 记忆相关参数

| 参数 | 类型 | 默认值 | 说明 |
|-----|------|--------|------|
| `context_memory_enabled` | bool | True | 是否启用上下文记忆 |
| `max_history_messages` | int | 10 | 最大历史消息数量 |
| `max_context_tokens` | int | 自动检测 | 最大上下文token数量 |

### 模型默认Token限制

| 模型 | 窗口大小 | 实际限制(60%) |
|------|----------|---------------|
| GPT-4 | 8,192 | 4,915 |
| GPT-4 Turbo | 128,000 | 76,800 |
| Claude-3.5 Sonnet | 200,000 | 120,000 |
| DeepSeek Chat | 32,768 | 19,661 |
| Moonshot V1 | 8,192 | 4,915 |

## API接口

### 1. 获取会话记忆信息

```bash
GET /agent_backend/chat/sessions/{session_id}/context-memory
Authorization: Bearer {token}
```

**响应示例：**

```json
{
    "context_memory_enabled": true,
    "max_history_messages": 10,
    "max_context_tokens": 19661,
    "actual_history_count": 8,
    "session_id": "abc123"
}
```

### 2. 获取全局记忆配置

```bash
GET /agent_backend/chat/context-memory/config
Authorization: Bearer {token}
```

**响应示例：**

```json
{
    "message": "上下文记忆配置信息",
    "config": {
        "context_memory_enabled": true,
        "max_history_messages": 10,
        "max_context_tokens": null
    }
}
```

### 3. 配置全局记忆设置

```bash
POST /agent_backend/chat/context-memory/configure
Authorization: Bearer {token}
Content-Type: application/json

{
    "enabled": true,
    "max_history_messages": 15
}
```

### 4. 获取Agent详细信息

```bash
GET /agent_backend/chat/sessions/{session_id}/agent-info
Authorization: Bearer {token}
```

**响应示例：**

```json
{
    "session_id": "abc123",
    "agent_info": {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "context_memory": {
            "context_memory_enabled": true,
            "max_history_messages": 10,
            "max_context_tokens": 19661,
            "actual_history_count": 8
        },
        "provider_info": {
            "provider": "deepseek",
            "model": "deepseek-chat"
        }
    }
}
```

## 智能优化策略

### 1. 消息数量控制

- 优先保留最近的对话
- 自动限制历史消息数量
- 保持对话的连贯性

### 2. Token优化

- 估算每条消息的token消耗
- 智能截断过长的消息
- 为当前对话保留足够空间（30%）

### 3. 内容优化

- 移除重复或相似内容
- 压缩过长的消息
- 保留关键上下文信息

## 使用示例

### 1. 基础对话

```python
# 第一轮对话
response1 = await chat_service.chat(
    session_id="session_123",
    message="你好，我叫Alice，我是一名软件工程师"
)

# 第二轮对话（Agent会记住用户是Alice，职业是软件工程师）
response2 = await chat_service.chat(
    session_id="session_123", 
    message="请推荐一些适合我的技术书籍"
)
```

### 2. 配置自定义记忆设置

```python
# 为特定会话配置更大的记忆容量
agent = await chat_service.get_agent_for_session(
    session_id="session_123",
    max_history_messages=20,
    max_context_tokens=50000
)
```

### 3. 动态调整记忆配置

```python
# 获取当前Agent
agent = await chat_service.get_agent_for_session("session_123")

# 调整记忆配置
agent.configure_context_memory(
    enabled=True,
    max_history_messages=15,
    max_context_tokens=30000
)
```

## 最佳实践

### 1. 记忆容量设置

- **短对话场景**：`max_history_messages=5-10`
- **长对话场景**：`max_history_messages=15-20`
- **技术支持场景**：`max_history_messages=10-15`
- **创意写作场景**：`max_history_messages=20-30`

### 2. Token限制设置

- **普通对话**：使用默认值（模型限制的60%）
- **长文档处理**：适当增加token限制
- **快速响应场景**：适当减少token限制

### 3. 性能优化

- 定期清理过期的Redis缓存
- 监控Agent实例数量
- 适当设置Agent TTL时间

## 监控和调试

### 1. 检查记忆状态

```python
# 获取记忆配置信息
memory_info = agent.get_context_memory_info()
print(f"记忆状态: {memory_info}")

# 获取实际历史消息数量
history_count = len(await chat_service.get_chat_history(session_id))
print(f"历史消息数量: {history_count}")
```

### 2. Token使用监控

```python
# 估算当前上下文的token使用
messages = await chat_service.get_chat_history(session_id, limit=10)
total_tokens = agent._estimate_messages_tokens(messages)
print(f"当前上下文token使用: {total_tokens}")
```

### 3. 日志监控

- 监控Agent创建和销毁日志
- 检查上下文优化日志
- 关注token超限警告

## 故障排除

### 1. 记忆功能未生效

- 检查`context_memory_enabled`配置
- 确认Redis连接正常
- 验证历史记录存在

### 2. 上下文过长错误

- 检查`max_context_tokens`设置
- 调整`max_history_messages`数量
- 查看上下文优化日志

### 3. 性能问题

- 检查Agent实例数量
- 监控Redis内存使用
- 优化历史消息查询

## 更新日志

### v1.0.0 (2024-01-XX)

- ✅ 基础上下文记忆功能
- ✅ 智能Token优化
- ✅ 多策略消息截断
- ✅ REST API接口
- ✅ 配置管理功能

### 未来计划

- 🔄 语义相似度去重
- 🔄 重要消息自动标记
- 🔄 跨会话记忆共享
- 🔄 记忆压缩算法优化
