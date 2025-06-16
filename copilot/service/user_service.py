"""
用户服务模块
处理用户注册、登录、认证等业务逻辑
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, status

from copilot.model.user_model import UserRegisterRequest, UserResponse
from copilot.utils.mongo_client import get_mongo_manager


class UserService:
    """用户服务类"""

    # JWT配置
    SECRET_KEY = "your-secret-key-here"  # 在生产环境中应该使用环境变量
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

    def __init__(self):
        self.collection_name = "users"

    async def hash_password(self, password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()

    async def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password

    async def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        """创建JWT访问令牌"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt

    async def verify_token(self, token: str) -> Optional[str]:
        """验证JWT令牌"""
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                return None
            return username
        except jwt.PyJWTError:
            return None

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        """根据用户名获取用户"""
        try:
            mongo_manager = await get_mongo_manager()
            collection = mongo_manager.get_collection(self.collection_name)
            user = await collection.find_one({"username": username})
            return user
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"查询用户失败: {str(e)}")

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """根据邮箱获取用户"""
        try:
            mongo_manager = await get_mongo_manager()
            collection = mongo_manager.get_collection(self.collection_name)
            user = await collection.find_one({"email": email})
            return user
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"查询用户失败: {str(e)}")

    async def register_user(self, user_data: UserRegisterRequest) -> UserResponse:
        """用户注册"""
        # 检查用户名是否已存在
        existing_user = await self.get_user_by_username(user_data.username)
        if existing_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")

        # 检查邮箱是否已存在
        existing_email = await self.get_user_by_email(user_data.email)
        if existing_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册")

        # 创建新用户
        user_id = str(uuid.uuid4())
        hashed_password = await self.hash_password(user_data.password)

        user_dict = {
            "user_id": user_id,
            "username": user_data.username,
            "email": user_data.email,
            "password_hash": hashed_password,
            "full_name": user_data.full_name,
            "created_at": datetime.now(timezone.utc),
            "is_active": True,
        }

        try:
            mongo_manager = await get_mongo_manager()
            collection = mongo_manager.get_collection(self.collection_name)
            await collection.insert_one(user_dict)

            return UserResponse(
                user_id=user_id,
                username=user_data.username,
                email=user_data.email,
                full_name=user_data.full_name,
                created_at=user_dict["created_at"],
                is_active=True,
            )
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"创建用户失败: {str(e)}")

    async def authenticate_user(self, username: str, password: str) -> Optional[dict]:
        """用户认证"""
        user = await self.get_user_by_username(username)
        if not user:
            return None
        if not await self.verify_password(password, user["password_hash"]):
            return None
        return user

    async def get_user_info(self, user_id: str) -> Optional[UserResponse]:
        """获取用户信息"""
        try:
            mongo_manager = await get_mongo_manager()
            collection = mongo_manager.get_collection(self.collection_name)
            user = await collection.find_one({"user_id": user_id})

            if not user:
                return None

            return UserResponse(
                user_id=user["user_id"],
                username=user["username"],
                email=user["email"],
                full_name=user.get("full_name"),
                created_at=user["created_at"],
                is_active=user.get("is_active", True),
            )
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"获取用户信息失败: {str(e)}")
