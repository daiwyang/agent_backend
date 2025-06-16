# 用户认证系统说明

## 概述

在main.py中添加了用户登录状态校验中间件，确保受保护的API接口只能被已认证的用户访问。

## 实现细节

### 1. 认证中间件 (authentication_middleware)

- **位置**: `copilot/main.py`
- **功能**: 拦截所有HTTP请求，对受保护的路径进行认证验证
- **验证流程**:
  1. 检查请求路径是否为公开路径（无需认证）
  2. 检查请求路径是否为受保护路径（需要认证）
  3. 验证Authorization header中的Bearer token
  4. 通过UserService验证token有效性
  5. 获取用户信息并验证用户状态
  6. 将用户信息存储到request.state中供后续使用

### 2. 路径配置

#### 受保护路径 (PROTECTED_PATHS)

- `/agent_backend/chat*` - 所有聊天相关接口
- `/agent_backend/user/profile*` - 用户信息管理
- `/agent_backend/user/update*` - 用户信息更新
- `/agent_backend/user/me*` - 获取当前用户信息

#### 公开路径 (PUBLIC_PATHS)

- `/agent_backend/user/register` - 用户注册
- `/agent_backend/user/login` - 用户登录
- `/agent_backend/chat/health` - 健康检查
- `/docs` - API文档
- `/openapi.json` - OpenAPI规范
- `/redoc` - ReDoc文档
- `/` - 根路径

### 3. 聊天路由修改

#### 用户信息获取

- 添加了 `get_current_user_from_request()` 辅助函数
- 从request.state中获取认证中间件设置的用户信息

#### 接口修改

- **创建会话**: 使用当前认证用户的ID创建会话
- **获取会话列表**: 只返回当前用户的会话
- **聊天**: 验证session属于当前用户
- **聊天历史**: 只返回当前用户的聊天历史
- **搜索**: 只搜索当前用户的聊天记录
- **统计信息**: 只返回当前用户的统计数据

### 4. 错误处理

#### 认证失败情况

- **缺少认证信息**: HTTP 401, "缺少认证信息"
- **无效认证格式**: HTTP 401, "无效的认证格式"
- **无效token**: HTTP 401, "认证失败"
- **用户不存在**: HTTP 401, "用户不存在"
- **用户被禁用**: HTTP 403, "用户账户已被禁用"

#### 响应格式

```json
{
    "code": 401,
    "message": "错误描述",
    "detail": "详细错误信息"
}
```

## 使用方式

### 1. 用户注册和登录

```bash
# 注册用户
curl -X POST "http://localhost:8000/agent_backend/user/register" \\
     -H "Content-Type: application/json" \\
     -d '{
       "username": "testuser",
       "email": "test@example.com",
       "password": "password123",
       "full_name": "测试用户"
     }'

# 用户登录
curl -X POST "http://localhost:8000/agent_backend/user/login" \\
     -H "Content-Type: application/json" \\
     -d '{
       "username": "testuser",
       "password": "password123"
     }'
```

### 2. 访问受保护接口

```bash
# 使用获取的token访问受保护接口
curl -X GET "http://localhost:8000/agent_backend/chat/sessions" \\
     -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### 3. 测试认证系统

```bash
# 运行测试脚本
python test_authentication.py
```

## 安全特性

1. **JWT Token验证**: 使用JWT进行无状态认证
2. **用户状态检查**: 验证用户账户是否被禁用
3. **会话所有权验证**: 确保用户只能访问自己的会话
4. **路径级别保护**: 灵活配置需要保护的API路径
5. **详细错误信息**: 提供清晰的认证失败原因

## 注意事项

1. **中间件顺序**: 认证中间件必须在其他业务中间件之前执行
2. **token存储**: 客户端需要安全存储JWT token
3. **token过期**: token有过期时间，客户端需要处理token刷新
4. **用户信息**: 认证后的用户信息通过request.state传递给后续处理器
5. **性能影响**: 每个受保护请求都会进行数据库查询验证用户状态

## 扩展建议

1. **Token刷新机制**: 实现refresh token机制
2. **权限控制**: 基于角色的访问控制(RBAC)
3. **请求限流**: 防止暴力破解攻击
4. **日志记录**: 记录认证成功/失败的详细日志
5. **会话管理**: 实现用户会话管理和强制退出功能
