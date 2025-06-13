# 聊天历史持久化功能

## 概述

本次更新解决了原系统中 `session_timeout` 导致的对话数据丢失问题，新增了完整的聊天历史持久化功能。

## 🎯 解决的问题

### 原有问题
- ❌ **数据丢失**: 会话超时后对话历史永久丢失
- ❌ **体验断裂**: 无法跨会话保持上下文
- ❌ **无法追溯**: 用户无法查看历史对话
- ❌ **缺少分析**: 没有长期数据支持业务分析

### 现在的解决方案
- ✅ **双重保障**: Redis + MongoDB 双层存储
- ✅ **自动恢复**: 会话超时后可自动从数据库恢复
- ✅ **完整历史**: 支持查看和搜索所有历史对话
- ✅ **数据分析**: 提供统计接口支持业务洞察

## 🏗️ 架构设计

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   Redis         │    │   MongoDB       │
│   (API层)       │    │   (会话缓存)      │    │   (持久化存储)    │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • 会话管理      │◄──►│ • 活跃会话      │    │ • 历史会话      │
│ • 消息处理      │    │ • 临时数据      │    │ • 所有消息      │
│ • 历史查询      │    │ • 快速访问      │    │ • 搜索索引      │
│ • 搜索接口      │    │                 │    │ • 统计数据      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 新增文件

1. **`copilot/agent/chat_history_manager.py`** - 聊天历史管理器
2. **`scripts/init_db_indexes.py`** - 数据库索引初始化
3. **`examples/chat_history_demo.py`** - 功能演示脚本

## 🔧 修改文件

1. **`copilot/agent/session_manager.py`** - 集成数据库持久化
2. **`copilot/agent/multi_session_agent.py`** - 添加历史管理功能
3. **`copilot/api/chat_api.py`** - 新增历史相关API
4. **`docs/multi_session_guide.md`** - 更新文档

## 🚀 核心特性

### 1. 自动会话恢复
```python
# 会话超时后自动恢复
session = await session_manager.get_session(session_id)
# 如果Redis中没有，自动从MongoDB恢复
```

### 2. 实时消息保存
```python
# 每条消息实时保存到数据库
await chat_history_manager.save_message(
    session_id=session_id,
    role="user",
    content=message
)
```

### 3. 灵活历史查询
```python
# 从内存获取（当前会话）
history = await agent.get_chat_history(session_id, from_db=False)

# 从数据库获取（完整历史）
history = await agent.get_chat_history(session_id, from_db=True)
```

### 4. 强大搜索功能
```python
# 搜索用户的所有对话
results = await agent.search_chat_history(user_id, "关键词")
```

## 🔌 API接口

### 新增接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/sessions/{session_id}/history` | 获取会话历史 |
| GET | `/users/{user_id}/chat-history` | 获取用户所有对话 |
| POST | `/search` | 搜索对话内容 |
| GET | `/stats` | 获取统计信息 |

### 参数说明

**获取会话历史**:
- `from_db`: 是否从数据库获取完整历史（默认false）
- `limit`: 返回消息数量限制
- `offset`: 分页偏移量

**删除会话**:
- `archive`: 是否归档到数据库（默认true）

## 📊 数据库设计

### chat_sessions 集合
```javascript
{
  session_id: "uuid",      // 会话ID（唯一）
  user_id: "string",       // 用户ID
  window_id: "string",     // 窗口ID  
  thread_id: "string",     // 线程ID
  created_at: Date,        // 创建时间
  last_activity: Date,     // 最后活动时间
  context: {},             // 会话上下文
  status: "active"         // 状态：active/archived/deleted
}
```

### chat_messages 集合
```javascript
{
  session_id: "uuid",      // 会话ID
  role: "user",            // 角色：user/assistant
  content: "string",       // 消息内容
  timestamp: Date,         // 时间戳
  metadata: {}             // 元数据
}
```

## 🎮 快速开始

### 1. 初始化数据库
```bash
python scripts/init_db_indexes.py
```

### 2. 运行演示
```bash
python examples/chat_history_demo.py
```

### 3. 启动API服务
```bash
python copilot/api/chat_api.py
```

### 4. 测试API
```bash
# 创建会话
curl -X POST "http://localhost:8000/sessions" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "window_id": "test_window"}'

# 发送消息
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "your_session_id", "message": "你好"}'

# 获取历史
curl "http://localhost:8000/sessions/your_session_id/history?from_db=true"
```

## 💡 使用场景

### 1. 客服系统
- 客户可以随时查看历史对话
- 客服可以快速了解客户历史问题
- 支持跨会话的连续服务

### 2. 智能助手
- 记住用户偏好和历史上下文
- 提供个性化的服务体验
- 支持长期学习和改进

### 3. 教育平台
- 学生可以回顾学习历史
- 老师可以追踪学习进度
- 支持知识点检索和复习

## 🔧 配置选项

### session_timeout 的新作用
```python
class SessionManager:
    def __init__(self, session_timeout: int = 3600):
        # session_timeout 现在主要控制Redis缓存时间
        # 数据会永久保存在MongoDB中
        # 超时后会自动从数据库恢复会话
```

### 存储策略
- **热数据**: 活跃会话保存在Redis（快速访问）
- **冷数据**: 历史会话保存在MongoDB（长期存储）
- **自动切换**: 系统自动在两者间切换，用户无感知

## 📈 性能优化

### 数据库索引
- `session_id` 唯一索引
- `user_id` + `status` 复合索引
- `content` 文本搜索索引
- `timestamp` 时间排序索引

### 查询优化
- 分页查询避免大数据量传输
- 索引优化提升搜索性能
- 缓存策略减少数据库访问

## 🛡️ 数据安全

### 备份策略
- MongoDB 自动备份
- 支持数据导出/导入
- 多副本保证数据安全

### 隐私保护
- 支持用户数据删除
- 敏感信息加密存储
- 访问权限控制

## 🔮 未来扩展

1. **高级分析**: 对话质量分析、用户行为洞察
2. **智能推荐**: 基于历史对话的个性化推荐
3. **多模态支持**: 图片、语音等多媒体消息
4. **实时同步**: 多设备间的对话同步
5. **AI增强**: 利用历史数据训练专属模型

## ❓ 常见问题

**Q: 数据库存储会影响性能吗？**
A: 不会。写入是异步的，读取有Redis缓存，正常使用不会感知到性能差异。

**Q: 如何处理历史数据迁移？**
A: 系统会自动处理。现有会话在下次访问时会自动保存到数据库。

**Q: 数据库占用空间如何控制？**
A: 可以配置定期清理策略，如保留最近6个月的数据等。

**Q: 支持数据导出吗？**
A: 支持。可以通过API或直接操作数据库导出用户数据。

---

这次更新让系统具备了企业级的数据持久化能力，为构建更智能、更可靠的对话AI系统奠定了基础。
