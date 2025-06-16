# 用户管理API使用示例

本文档展示了如何使用用户注册、登录和管理功能。

## API 端点

所有用户相关的API都在 `/agent_backend/user` 路径下。

### 1. 用户注册

**POST** `/agent_backend/user/register`

```json
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "securepassword",
  "full_name": "Test User"
}
```

**响应示例：**

```json
{
  "code": 200,
  "message": "注册成功",
  "data": {
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "username": "testuser",
    "email": "test@example.com",
    "full_name": "Test User",
    "created_at": "2024-01-01T12:00:00"
  }
}
```

### 2. 用户登录

**POST** `/agent_backend/user/login`

```json
{
  "username": "testuser",
  "password": "securepassword"
}
```

**响应示例：**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "username": "testuser",
    "email": "test@example.com",
    "full_name": "Test User",
    "created_at": "2024-01-01T12:00:00",
    "is_active": true
  }
}
```

### 3. 获取当前用户信息

**GET** `/agent_backend/user/me`

**请求头：**

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**响应示例：**

```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "username": "testuser",
  "email": "test@example.com",
  "full_name": "Test User",
  "created_at": "2024-01-01T12:00:00",
  "is_active": true
}
```

### 4. 更新用户信息

**PUT** `/agent_backend/user/me`

**请求头：**

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**请求体：**

```json
{
  "full_name": "Updated Name",
  "email": "updated@example.com"
}
```

**响应示例：**

```json
{
  "code": 200,
  "message": "用户信息更新成功",
  "data": {
    "full_name": "Updated Name",
    "email": "updated@example.com"
  }
}
```

### 5. 获取指定用户信息

**GET** `/agent_backend/user/profile/{user_id}`

**响应示例：**

```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "username": "testuser",
  "email": "test@example.com",
  "full_name": "Test User",
  "created_at": "2024-01-01T12:00:00",
  "is_active": true
}
```

### 6. 退出登录

**POST** `/agent_backend/user/logout`

**请求头：**

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**响应示例：**

```json
{
  "code": 200,
  "message": "退出登录成功",
  "data": {
    "username": "testuser"
  }
}
```

## 错误处理

### 常见错误响应

**400 Bad Request - 用户名已存在**

```json
{
  "detail": "用户名已存在"
}
```

**401 Unauthorized - 认证失败**

```json
{
  "detail": "用户名或密码错误"
}
```

**401 Unauthorized - Token无效**

```json
{
  "detail": "无效的认证信息"
}
```

**404 Not Found - 用户不存在**

```json
{
  "detail": "用户不存在"
}
```

## 使用流程

1. **注册用户**：使用 `/register` 端点创建新用户
2. **用户登录**：使用 `/login` 端点获取访问令牌
3. **访问受保护资源**：在请求头中包含 `Authorization: Bearer <token>`
4. **更新用户信息**：使用 `/me` 端点更新当前用户信息
5. **退出登录**：使用 `/logout` 端点（客户端需要删除本地token）

## 安全注意事项

1. **密码安全**：密码使用SHA256哈希存储
2. **Token过期**：JWT令牌默认30分钟过期
3. **HTTPS**：生产环境请使用HTTPS
4. **密钥管理**：请更改默认的JWT密钥

## 项目结构

用户相关文件组织如下：

- `copilot/model/user_model.py` - 用户数据模型
- `copilot/service/user_service.py` - 用户业务逻辑服务
- `copilot/router/user_router.py` - 用户API路由
- `copilot/utils/auth.py` - 认证工具和依赖项

## 数据库结构

用户数据存储在MongoDB的 `users` 集合中：

```json
{
  "_id": ObjectId("..."),
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "username": "testuser",
  "email": "test@example.com",
  "password_hash": "hashed_password",
  "full_name": "Test User",
  "created_at": "2024-01-01T12:00:00",
  "is_active": true
}
```
