"""
简化后的认证工具模块
提供JWT认证相关的依赖项和工具函数
"""

from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from copilot.service.user_service import UserService
from copilot.model.user_model import TokenData

# 创建HTTPBearer实例
security = HTTPBearer()

# 创建用户服务实例
user_service = UserService()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    获取当前用户的依赖项（合并了活跃用户检查）
    
    返回:
        dict: 用户信息字典
        
    抛出:
        HTTPException: 401 无效认证信息
        HTTPException: 400 用户账户被禁用
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证信息",
        headers={"WWW-Authenticate": "Bearer"}
    )

    try:
        # 验证token（包含Redis会话检查）
        username = await user_service.verify_token(credentials.credentials)
        if not username:
            raise credentials_exception

        # 获取用户信息并检查活跃状态
        user = await user_service.get_user_by_username(username)
        if not user:
            raise credentials_exception
            
        if not user.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户账户已被禁用"
            )

        return user
    except HTTPException:
        raise
    except Exception:
        raise credentials_exception


def create_token_data(username: str) -> TokenData:
    """创建token数据"""
    return TokenData(username=username)


async def get_current_user_from_state(request: Request) -> dict:
    """从请求状态中获取当前用户信息的依赖项"""
    if not hasattr(request.state, "current_user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户未认证",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return request.state.current_user
