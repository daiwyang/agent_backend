"""
认证工具模块
提供JWT认证相关的依赖项和工具函数
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from copilot.service.user_service import UserService
from copilot.model.user_model import TokenData

# 创建HTTPBearer实例
security = HTTPBearer()

# 创建用户服务实例
user_service = UserService()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[dict]:
    """获取当前用户的依赖项"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证信息",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 验证token
        username = await user_service.verify_token(credentials.credentials)
        if username is None:
            raise credentials_exception
            
        # 获取用户信息
        user = await user_service.get_user_by_username(username)
        if user is None:
            raise credentials_exception
            
        return user
    except Exception:
        raise credentials_exception


async def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """获取当前活跃用户的依赖项"""
    if not current_user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="用户账户已被禁用"
        )
    return current_user


def create_token_data(username: str) -> TokenData:
    """创建token数据"""
    return TokenData(username=username) 