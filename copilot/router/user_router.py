"""
用户路由模块
提供用户注册、登录、用户信息管理等API端点
"""

from datetime import timedelta, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request

from copilot.model.user_model import BaseResponse, UserLoginRequest, UserLoginResponse, UserRegisterRequest, UserResponse, UserUpdateRequest
from copilot.service.user_service import UserService
from copilot.utils.auth import get_current_user
from copilot.utils.logger import logger
from copilot.utils.error_codes import ErrorCodes, ErrorHandler, raise_auth_error, raise_user_error

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
                "created_at": user.created_at.isoformat(),
            },
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise ErrorHandler.handle_system_error(e, "用户注册")


@router.post("/login", response_model=UserLoginResponse, summary="用户登录")
async def login(login_data: UserLoginRequest):
    """
    用户登录

    - **username**: 用户名
    - **password**: 密码

    返回JWT访问令牌和用户信息，同时在Redis中创建会话
    """
    login_result = await user_service.login_user(login_data.username, login_data.password)
    if not login_result:
        raise_auth_error(ErrorCodes.AUTHENTICATION_FAILED)

    # 构建用户响应
    user_info = login_result["user"]
    user_response = UserResponse(
        user_id=user_info["user_id"],
        username=user_info["username"],
        email=user_info["email"],
        full_name=user_info.get("full_name"),
        created_at=user_info.get("created_at", datetime.now(timezone.utc)),
        is_active=user_info.get("is_active", True),
    )

    return UserLoginResponse(
        access_token=login_result["access_token"], token_type=login_result["token_type"], user=user_response, session_id=login_result["session_id"]
    )


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
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
        is_active=current_user.get("is_active", True),
    )


@router.get("/profile/{user_id}", response_model=UserResponse, summary="根据用户ID获取用户信息")
async def get_user_profile(user_id: str):
    """
    根据用户ID获取用户信息

    - **user_id**: 用户ID
    """
    user = await user_service.get_user_info(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return user


@router.put("/me", response_model=BaseResponse, summary="更新当前用户信息")
async def update_current_user(update_data: UserUpdateRequest, current_user: dict = Depends(get_current_user)):
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
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被其他用户使用")

        # 更新用户信息
        from copilot.utils.mongo_client import get_mongo_manager

        mongo_manager = await get_mongo_manager()
        collection = await mongo_manager.get_collection("users")

        update_fields = {}
        if update_data.full_name is not None:
            update_fields["full_name"] = update_data.full_name
        if update_data.email is not None:
            update_fields["email"] = update_data.email

        if update_fields:
            await collection.update_one({"user_id": current_user["user_id"]}, {"$set": update_fields})

        return BaseResponse(code=200, message="用户信息更新成功", data=update_fields)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"更新用户信息失败: {str(e)}")


@router.post("/logout", response_model=BaseResponse, summary="用户退出登录")
async def logout(request: Request, current_user: dict = Depends(get_current_user)):
    """
    用户退出登录

    需要提供有效的JWT令牌
    会清理Redis中的用户会话信息
    """
    try:
        # 从Authorization header获取token
        authorization = request.headers.get("Authorization")
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]

            # 调用用户服务的退出登录方法
            success = await user_service.logout_user(token)

            if success:
                return BaseResponse(code=200, message="退出登录成功", data={"username": current_user["username"]})
            else:
                return BaseResponse(code=200, message="退出登录完成（会话可能已过期）", data={"username": current_user["username"]})
        else:
            return BaseResponse(code=200, message="退出登录完成", data={"username": current_user["username"]})
    except Exception as e:
        logger.error(f"Logout error for user {current_user['username']}: {str(e)}")
        return BaseResponse(code=200, message="退出登录完成", data={"username": current_user["username"]})


@router.get("/health", summary="健康检查")
async def health_check():
    """用户服务健康检查"""
    return {"status": "healthy", "service": "user_service"}


@router.get("/sessions", summary="获取当前用户的所有会话")
async def get_user_sessions(current_user: dict = Depends(get_current_user)):
    """
    获取当前用户的所有活跃会话

    需要提供有效的JWT令牌
    """
    try:
        sessions = await user_service.get_user_sessions(current_user["user_id"])
        return BaseResponse(code=200, message="获取会话列表成功", data={"sessions": sessions, "total": len(sessions)})
    except Exception as e:
        logger.error(f"Get sessions error for user {current_user['username']}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取会话列表失败")


@router.post("/logout-all", response_model=BaseResponse, summary="退出所有设备登录")
async def logout_all_sessions(current_user: dict = Depends(get_current_user)):
    """
    用户退出所有设备的登录

    需要提供有效的JWT令牌
    会清理该用户在Redis中的所有会话信息
    """
    try:
        revoked_count = await user_service.logout_all_sessions(current_user["user_id"])
        return BaseResponse(
            code=200, message=f"成功退出{revoked_count}个设备的登录", data={"username": current_user["username"], "revoked_sessions": revoked_count}
        )
    except Exception as e:
        logger.error(f"Logout all sessions error for user {current_user['username']}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="退出所有设备登录失败")


@router.delete("/sessions/{session_id}", response_model=BaseResponse, summary="撤销指定会话")
async def revoke_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """
    撤销指定的会话

    需要提供有效的JWT令牌
    只能撤销属于当前用户的会话
    """
    try:
        from copilot.service.user_session_service import get_user_session_service

        session_service = get_user_session_service()

        # 检查会话是否属于当前用户
        session_data = await session_service.get_session_by_id(session_id)
        if not session_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")

        if session_data["user_id"] != current_user["user_id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限操作此会话")

        # 撤销会话
        success = await session_service.revoke_session(session_id)
        if success:
            return BaseResponse(code=200, message="会话撤销成功", data={"session_id": session_id})
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="会话撤销失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Revoke session error for user {current_user['username']}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="撤销会话失败")
