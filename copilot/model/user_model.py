from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserRegisterRequest(BaseModel):
    """用户注册请求模型"""
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLoginRequest(BaseModel):
    """用户登录请求模型"""
    username: str
    password: str


class UserResponse(BaseModel):
    """用户响应模型"""
    user_id: str
    username: str
    email: str
    full_name: Optional[str] = None
    created_at: datetime
    is_active: bool = True


class UserLoginResponse(BaseModel):
    """用户登录响应模型"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    session_id: Optional[str] = None


class UserUpdateRequest(BaseModel):
    """用户信息更新请求模型"""
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class TokenData(BaseModel):
    """Token数据模型"""
    username: Optional[str] = None


class BaseResponse(BaseModel):
    """基础响应模型"""
    code: int = 200
    message: str = "success"
    data: Optional[dict] = None 