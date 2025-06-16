# 错误编码系统使用指南

## 概述

错误编码系统提供了统一的错误管理和处理机制，所有后端错误信息都通过错误编码类进行管理。该系统具有以下特点：

- **统一的错误编码格式**：采用分类+编号的方式（如 AUTH001、USER002）
- **标准化的错误响应**：包含错误编码、消息、详细信息和类别
- **便捷的错误处理**：提供多种便捷函数和处理器
- **易于维护**：集中管理所有错误信息

## 错误编码格式

错误编码采用 `{类别}{编号}` 的格式：

- **AUTH**：认证相关错误（AUTH001-AUTH999）
- **AUTHZ**：授权相关错误（AUTHZ001-AUTHZ999）
- **USER**：用户相关错误（USER001-USER999）
- **CHAT**：聊天相关错误（CHAT001-CHAT999）
- **SESSION**：会话相关错误（SESSION001-SESSION999）
- **DB**：数据库相关错误（DB001-DB999）
- **REDIS**：Redis相关错误（REDIS001-REDIS999）
- **VALID**：数据验证错误（VALID001-VALID999）
- **SYS**：系统错误（SYS001-SYS999）
- **NET**：网络相关错误（NET001-NET999）

## 基本使用方法

### 1. 导入错误编码类

```python
from copilot.utils.error_codes import (
    ErrorCodes, ErrorHandler, 
    raise_auth_error, raise_user_error, raise_system_error
)
```

### 2. 使用预定义错误

```python
# 方式一：使用便捷函数
def some_user_function():
    if user_not_found:
        raise_user_error(ErrorCodes.USER_NOT_FOUND)
    
    if username_exists:
        raise_user_error(ErrorCodes.USERNAME_EXISTS)

# 方式二：使用ErrorHandler
def some_auth_function():
    if invalid_token:
        ErrorHandler.raise_error(ErrorCodes.INVALID_TOKEN)
    
    if account_disabled:
        ErrorHandler.raise_error(ErrorCodes.ACCOUNT_DISABLED)

# 方式三：直接转换为HTTPException
def some_validation_function():
    if invalid_data:
        raise ErrorCodes.INVALID_DATA_FORMAT.to_http_exception()
```

### 3. 自定义错误详情

```python
# 提供自定义的详细错误信息
def login_user(username: str, password: str):
    user = get_user(username)
    if not user:
        raise_user_error(
            ErrorCodes.USER_NOT_FOUND, 
            detail=f"用户名 '{username}' 不存在"
        )
    
    if not verify_password(password, user.password_hash):
        raise_auth_error(
            ErrorCodes.AUTHENTICATION_FAILED,
            detail="密码错误，请检查后重试"
        )
```

### 4. 处理数据库错误

```python
async def create_user(user_data):
    try:
        # 数据库操作
        await collection.insert_one(user_data)
    except Exception as e:
        # 统一处理数据库错误
        raise ErrorHandler.handle_database_error(e, "用户创建")
```

### 5. 处理系统错误

```python
async def complex_operation():
    try:
        # 复杂的业务逻辑
        result = await some_complex_operation()
        return result
    except Exception as e:
        # 统一处理系统错误
        raise ErrorHandler.handle_system_error(e, "复杂操作")
```

## 错误响应格式

使用错误编码系统的API会返回以下格式的错误响应：

```json
{
  "detail": {
    "error_code": "AUTH001",
    "message": "缺少认证信息",
    "detail": "请提供有效的认证信息",
    "category": "AUTH"
  }
}
```

## 常用错误编码

### 认证相关 (AUTH)

- `AUTH001`: 缺少认证信息
- `AUTH002`: 无效的认证格式
- `AUTH003`: 认证失败
- `AUTH004`: 无效的访问令牌
- `AUTH005`: 访问令牌已过期
- `AUTH006`: 会话无效

### 用户相关 (USER)

- `USER001`: 用户不存在
- `USER002`: 用户名已存在
- `USER003`: 邮箱已被注册
- `USER004`: 用户创建失败
- `USER005`: 用户信息获取失败
- `USER006`: 用户信息更新失败
- `USER007`: 密码错误

### 聊天相关 (CHAT)

- `CHAT001`: 聊天会话创建失败
- `CHAT002`: 聊天会话不存在
- `CHAT003`: 消息发送失败
- `CHAT004`: 聊天历史获取失败
- `CHAT005`: 会话列表获取失败

## 实际应用示例

### 用户注册示例

```python
async def register_user(user_data: UserRegisterRequest) -> UserResponse:
    # 检查用户名是否已存在
    existing_user = await get_user_by_username(user_data.username)
    if existing_user:
        raise_user_error(ErrorCodes.USERNAME_EXISTS)

    # 检查邮箱是否已存在
    existing_email = await get_user_by_email(user_data.email)
    if existing_email:
        raise_user_error(ErrorCodes.EMAIL_EXISTS)

    try:
        # 创建用户
        user = await create_user(user_data)
        return user
    except Exception as e:
        raise ErrorHandler.handle_database_error(e, "用户创建")
```

### 用户登录示例

```python
async def login_user(username: str, password: str):
    # 验证用户身份
    user = await authenticate_user(username, password)
    if not user:
        raise_auth_error(ErrorCodes.AUTHENTICATION_FAILED)
    
    # 检查用户是否被禁用
    if not user.get("is_active", True):
        raise_auth_error(ErrorCodes.ACCOUNT_DISABLED)
    
    try:
        # 创建会话
        session = await create_session(user)
        return session
    except Exception as e:
        raise ErrorHandler.handle_system_error(e, "用户登录")
```

### 路由处理示例

```python
@router.post("/login", response_model=UserLoginResponse)
async def login(login_data: UserLoginRequest):
    try:
        login_result = await user_service.login_user(
            login_data.username, 
            login_data.password
        )
        if not login_result:
            raise_auth_error(ErrorCodes.AUTHENTICATION_FAILED)
        
        return UserLoginResponse(**login_result)
    except HTTPException:
        # 重新抛出HTTPException（包含错误编码）
        raise
    except Exception as e:
        # 处理未预期的系统错误
        raise ErrorHandler.handle_system_error(e, "用户登录")
```

## 最佳实践

### 1. 优先使用预定义错误

```python
# 好的做法
raise_user_error(ErrorCodes.USER_NOT_FOUND)

# 避免的做法
raise HTTPException(status_code=404, detail="用户不存在")
```

### 2. 提供有意义的错误详情

```python
# 好的做法
raise_user_error(
    ErrorCodes.USERNAME_EXISTS,
    detail=f"用户名 '{username}' 已被注册，请选择其他用户名"
)

# 基本做法
raise_user_error(ErrorCodes.USERNAME_EXISTS)
```

### 3. 统一处理异常

```python
# 好的做法
try:
    result = await database_operation()
except Exception as e:
    raise ErrorHandler.handle_database_error(e, "数据操作")

# 避免的做法
try:
    result = await database_operation()
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

### 4. 在路由层处理HTTPException

```python
@router.get("/users/{user_id}")
async def get_user(user_id: str):
    try:
        user = await user_service.get_user(user_id)
        return user
    except HTTPException:
        # 重新抛出已处理的错误
        raise
    except Exception as e:
        # 处理未预期的错误
        raise ErrorHandler.handle_system_error(e, "获取用户信息")
```

## 扩展错误编码

如果需要添加新的错误编码，请按照以下步骤：

1. 在 `ErrorCodes` 类中添加新的错误定义
2. 选择合适的错误类别和编号
3. 提供清晰的错误消息和HTTP状态码
4. 更新相关文档

```python
class ErrorCodes:
    # 新增聊天相关错误
    CHAT_MESSAGE_TOO_LONG = ErrorCode(
        category=ErrorCategory.CHAT,
        code="006",
        message="聊天消息过长",
        http_status=400,
        detail="聊天消息长度不能超过1000字符"
    )
```

## 前端处理建议

前端可以根据错误编码进行不同的处理：

```javascript
// JavaScript示例
async function handleApiCall() {
    try {
        const response = await api.call();
        return response.data;
    } catch (error) {
        const errorDetail = error.response.data.detail;
        
        switch (errorDetail.error_code) {
            case 'AUTH001':
            case 'AUTH004':
            case 'AUTH005':
                // 认证失败，跳转到登录页
                redirectToLogin();
                break;
                
            case 'USER002':
                // 用户名已存在，提示用户更换
                showError('该用户名已被注册，请选择其他用户名');
                break;
                
            case 'NET002':
                // 请求过于频繁，提示用户稍后重试
                showError('请求过于频繁，请稍后重试');
                break;
                
            default:
                // 显示通用错误信息
                showError(errorDetail.message);
        }
    }
}
```

通过使用错误编码系统，可以实现更好的错误处理、用户体验和系统维护性。
