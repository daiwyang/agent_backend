"""
统一的认证工具模块
提供认证相关的依赖项和工具函数
"""

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from copilot.model.user_model import TokenData
from copilot.service.user_service import UserService

# 创建HTTPBearer实例（可选使用）
security = HTTPBearer(auto_error=False)

# 创建用户服务实例
user_service = UserService()


class UserSession:
    """用户会话信息 - 统一的认证返回对象"""

    def __init__(self, user_id: str, username: str, login_session_id: str, session_data: dict, user_info: dict):
        self.user_id = user_id
        self.username = username
        self.login_session_id = login_session_id  # 用户登录会话ID（从Redis获取）
        self.session_data = session_data
        self.user_info = user_info  # 完整的用户信息字典

    def to_dict(self) -> dict:
        """转换为字典格式（向后兼容）"""
        return self.user_info

    @property
    def session_id(self) -> str:
        """向后兼容属性 - 返回登录会话ID"""
        return self.login_session_id


async def get_authenticated_user(
    request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security), token: Optional[str] = None
) -> UserSession:
    """
    统一的用户认证函数 - 支持多种token获取方式

    优先级：
    1. 请求状态中的用户信息（中间件已认证，性能最佳）
    2. HTTPBearer token
    3. 查询参数token
    4. Authorization header手动解析

    返回:
        UserSession: 统一的用户会话信息对象

    抛出:
        HTTPException: 401 认证失败
        HTTPException: 403 用户被禁用
    """
    # 1. 优先从请求状态获取（中间件已认证，性能最佳）
    if hasattr(request.state, "current_user") and hasattr(request.state, "session_data"):
        user = request.state.current_user
        session_data = request.state.session_data
        return UserSession(
            user_id=user.get("user_id"),  # 使用数据库中的user_id字段（UUID格式）
            username=user.get("username"),
            login_session_id=session_data.get("session_id", ""),
            session_data=session_data,
            user_info=user,
        )

    # 2. 获取token进行认证
    auth_token = None

    # 从HTTPBearer获取token
    if credentials and credentials.credentials:
        auth_token = credentials.credentials
    # 从查询参数获取token（用于EventSource等场景）
    elif token:
        auth_token = token
    # 手动从Authorization header解析
    elif request.headers.get("Authorization"):
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            auth_token = authorization.split(" ")[1]

    # 如果没有token，抛出异常
    if not auth_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少认证信息", headers={"WWW-Authenticate": "Bearer"})

    try:
        # 验证token
        session_data = await user_service.verify_token(auth_token)
        if session_data is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的token", headers={"WWW-Authenticate": "Bearer"})

        # 获取用户名
        username = session_data.get("username")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话数据无效", headers={"WWW-Authenticate": "Bearer"})

        # 获取用户信息
        user = await user_service.get_user_by_username(username)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在", headers={"WWW-Authenticate": "Bearer"})

        # 检查用户是否被禁用
        if not user.get("is_active", True):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户账户已被禁用")

        # 返回统一的用户会话信息
        return UserSession(
            user_id=user.get("user_id"),
            username=username,
            login_session_id=session_data.get("session_id", ""),
            session_data=session_data,
            user_info=user,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证验证失败", headers={"WWW-Authenticate": "Bearer"})


# === 简化的便捷函数 ===


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    获取当前用户信息字典（向后兼容）
    简化版本：直接调用统一认证函数
    """
    # 创建一个简单的request对象
    from starlette.datastructures import URL, Headers
    from starlette.requests import Request

    # 创建最小化的request对象
    fake_request = Request(
        {
            "type": "http",
            "method": "GET",
            "url": str(URL("http://localhost/")),
            "headers": Headers({"authorization": f"Bearer {credentials.credentials}" if credentials else ""}).raw,
            "query_string": b"",
        }
    )

    # 调用统一认证函数
    user_session = await get_authenticated_user(fake_request, credentials, None)
    return user_session.user_info


async def get_current_user_from_state(request: Request) -> dict:
    """从请求状态中获取当前用户信息的依赖项（向后兼容）"""
    user_session = await get_authenticated_user(request, None, None)
    return user_session.user_info


# === 工具函数 ===


def create_token_data(username: str) -> TokenData:
    """创建token数据"""
    return TokenData(username=username)
