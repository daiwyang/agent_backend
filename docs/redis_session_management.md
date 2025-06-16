# Redis用户会话管理系统

## 概述

实现了基于Redis的用户登录状态管理系统，将用户会话信息存储在Redis中，提供更强大的会话控制和管理能力。

## 核心功能

### 1. 用户会话服务 (UserSessionService)

位置：`copilot/service/user_session_service.py`

#### 主要功能

- **会话创建**: 用户登录时创建会话并存储到Redis
- **会话验证**: 通过token验证用户登录状态
- **会话管理**: 获取、更新、撤销用户会话
- **会话清理**: 自动清理过期会话

#### Redis数据结构

```
# 会话数据 (Hash)
user_session:{session_id} = {
    "session_id": "uuid",
    "user_id": "user_id", 
    "username": "username",
    "token": "jwt_token",
    "device_info": {...},
    "created_at": "2025-06-16T10:30:00Z",
    "last_active": "2025-06-16T10:35:00Z",
    "expires_at": "2025-06-17T10:30:00Z"
}

# Token到Session映射
token:{jwt_token} = session_id

# 用户会话集合 (Set)
user_sessions:{user_id} = {session_id1, session_id2, ...}
```

### 2. 用户服务增强 (UserService)

#### 新增方法

- `login_user()`: 登录并创建Redis会话
- `logout_user()`: 退出登录并清理会话
- `logout_all_sessions()`: 退出所有设备登录
- `get_user_sessions()`: 获取用户所有会话
- `verify_token()`: 验证token时检查Redis会话状态

### 3. 新的API接口

#### 登录相关

```bash
# 用户登录（创建Redis会话）
POST /agent_backend/user/login
{
    "username": "user123",
    "password": "password"
}

# 响应包含session_id
{
    "access_token": "jwt_token",
    "token_type": "bearer",
    "session_id": "uuid",
    "user": {...}
}
```

#### 会话管理

```bash
# 获取当前用户的所有会话
GET /agent_backend/user/sessions
Authorization: Bearer {token}

# 退出当前设备登录
POST /agent_backend/user/logout
Authorization: Bearer {token}

# 退出所有设备登录
POST /agent_backend/user/logout-all
Authorization: Bearer {token}

# 撤销指定会话
DELETE /agent_backend/user/sessions/{session_id}
Authorization: Bearer {token}
```

## 安全增强

### 1. 双重认证机制

- **JWT验证**: 验证token的签名和过期时间
- **Redis会话验证**: 检查会话是否存在和有效

### 2. 会话控制

- **强制退出**: 管理员可以强制用户退出
- **设备管理**: 用户可以查看和管理登录设备
- **会话限制**: 可以限制用户同时登录的设备数量

### 3. 安全特性

- **即时失效**: 退出登录后token立即失效
- **活跃更新**: 自动更新用户最后活跃时间
- **过期清理**: 自动清理过期会话

## 配置说明

### Redis配置

```yaml
# config/config.dev.yaml
redis:
  host: "localhost"
  port: 6379
  db: 0
  password: null
  max_connections: 10
```

### 会话配置

```python
# 默认会话过期时间
default_session_expire = 24 * 60 * 60  # 24小时
token_expire = 30 * 60  # 30分钟
```

## 使用示例

### 1. 用户登录

```python
# 客户端登录
login_data = {
    "username": "testuser",
    "password": "password123"
}

response = await client.post("/agent_backend/user/login", json=login_data)
result = response.json()

# 保存token和session_id
token = result["access_token"]
session_id = result["session_id"]
```

### 2. 访问受保护接口

```python
# 使用token访问API
headers = {"Authorization": f"Bearer {token}"}
response = await client.get("/agent_backend/chat/sessions", headers=headers)
```

### 3. 会话管理

```python
# 查看所有登录设备
response = await client.get("/agent_backend/user/sessions", headers=headers)
sessions = response.json()["data"]["sessions"]

# 退出指定设备
await client.delete(f"/agent_backend/user/sessions/{session_id}", headers=headers)

# 退出所有设备
await client.post("/agent_backend/user/logout-all", headers=headers)
```

## 监控和维护

### 1. 会话统计

```python
# 获取用户活跃会话数量
async def get_active_sessions_count(user_id: str) -> int:
    sessions = await user_session_service.get_user_sessions(user_id)
    return len(sessions)
```

### 2. 清理过期会话

```python
# 定期清理过期会话（可以设置定时任务）
async def cleanup_expired_sessions():
    count = await user_session_service.cleanup_expired_sessions()
    logger.info(f"Cleaned up {count} expired sessions")
```

### 3. 监控Redis使用

```bash
# 查看Redis中的会话数据
redis-cli keys "user_session:*" | wc -l  # 活跃会话数
redis-cli keys "user_sessions:*" | wc -l  # 有会话的用户数
redis-cli keys "token:*" | wc -l  # token映射数
```

## 优势

1. **实时会话控制**: 可以立即撤销用户会话
2. **设备管理**: 用户可以管理多设备登录
3. **安全性提升**: 双重认证机制提高安全性
4. **灵活配置**: 可以灵活配置会话过期时间
5. **易于扩展**: 可以轻松添加更多会话管理功能

## 注意事项

1. **Redis依赖**: 系统依赖Redis服务的可用性
2. **内存使用**: 大量用户时需要考虑Redis内存使用
3. **网络延迟**: 每次请求都会查询Redis，考虑网络延迟
4. **备份策略**: 需要制定Redis数据备份策略
5. **监控告警**: 建议监控Redis连接状态和性能

## 未来扩展

1. **会话限制**: 限制用户同时登录设备数量
2. **地理位置**: 记录登录地理位置信息
3. **安全审计**: 记录登录、退出日志
4. **推送通知**: 新设备登录时推送通知
5. **会话分析**: 用户行为分析和统计
