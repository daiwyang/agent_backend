"""
用户路由模块
提供用户注册、登录、用户信息管理等API端点
"""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from copilot.service.user_service import UserService
from copilot.model.user_model import (
    BaseResponse,
    UserLoginRequest,
    UserLoginResponse,
    UserRegisterRequest,
    UserResponse,
    UserUpdateRequest,
)
from copilot.utils.auth import get_current_active_user

# 创建路由器
router = APIRouter(prefix="/user", tags=["用户管理"])

# 创建用户服务实例
user_service = UserService()


@router.post("/register", response_model=BaseResponse, summary="用户注册")
async def register(user_data: UserRegisterRequest):
    """
    用户注册
    
    - **username**: 用户名，必须唯一
    - **email**: 邮箱地址，必须唯一
    - **password**: 密码
    - **full_name**: 全名（可选）
    """
    try:
        user = await user_service.register_user(user_data)
        return BaseResponse(
            code=200,
            message="注册成功",
            data={
                "user_id": user.user_id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "created_at": user.created_at.isoformat()
            }
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"注册失败: {str(e)}"
        )


@router.post("/login", response_model=UserLoginResponse, summary="用户登录")
async def login(login_data: UserLoginRequest):
    """
    用户登录
    
    - **username**: 用户名
    - **password**: 密码
    
    返回JWT访问令牌和用户信息
    """
    user = await user_service.authenticate_user(login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 创建访问令牌
    access_token_expires = timedelta(minutes=user_service.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = await user_service.create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    
    # 构建用户响应
    user_response = UserResponse(
        user_id=user["user_id"],
        username=user["username"],
        email=user["email"],
        full_name=user.get("full_name"),
        created_at=user["created_at"],
        is_active=user.get("is_active", True)
    )
    
    return UserLoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_response
    )


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    """
    获取当前登录用户的信息
    
    需要提供有效的JWT令牌
    """
    return UserResponse(
        user_id=current_user["user_id"],
        username=current_user["username"],
        email=current_user["email"],
        full_name=current_user.get("full_name"),
        created_at=current_user["created_at"],
        is_active=current_user.get("is_active", True)
    )


@router.get("/profile/{user_id}", response_model=UserResponse, summary="根据用户ID获取用户信息")
async def get_user_profile(user_id: str):
    """
    根据用户ID获取用户信息
    
    - **user_id**: 用户ID
    """
    user = await user_service.get_user_info(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    return user


@router.put("/me", response_model=BaseResponse, summary="更新当前用户信息")
async def update_current_user(
    update_data: UserUpdateRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    更新当前登录用户的信息
    
    - **full_name**: 全名（可选）
    - **email**: 邮箱地址（可选）
    
    需要提供有效的JWT令牌
    """
    try:
        # 检查邮箱是否已被其他用户使用
        if update_data.email:
            existing_user = await user_service.get_user_by_email(update_data.email)
            if existing_user and existing_user["user_id"] != current_user["user_id"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="邮箱已被其他用户使用"
                )
        
        # 更新用户信息
        from copilot.utils.mongo_client import get_mongo_manager
        
        mongo_manager = await get_mongo_manager()
        collection = mongo_manager.get_collection("users")
        
        update_fields = {}
        if update_data.full_name is not None:
            update_fields["full_name"] = update_data.full_name
        if update_data.email is not None:
            update_fields["email"] = update_data.email
        
        if update_fields:
            await collection.update_one(
                {"user_id": current_user["user_id"]},
                {"$set": update_fields}
            )
        
        return BaseResponse(
            code=200,
            message="用户信息更新成功",
            data=update_fields
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新用户信息失败: {str(e)}"
        )


@router.post("/logout", response_model=BaseResponse, summary="用户退出登录")
async def logout(current_user: dict = Depends(get_current_active_user)):
    """
    用户退出登录
    
    需要提供有效的JWT令牌
    注意：由于JWT是无状态的，此端点主要用于客户端确认退出
    实际的令牌失效需要客户端主动删除本地存储的令牌
    """
    return BaseResponse(
        code=200,
        message="退出登录成功",
        data={"username": current_user["username"]}
    )


@router.get("/health", summary="健康检查")
async def health_check():
    """用户服务健康检查"""
    return {"status": "healthy", "service": "user_service"} 