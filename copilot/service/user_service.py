"""
用户服务模块
处理用户注册、登录、认证等业务逻辑
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from copilot.model.user_model import UserRegisterRequest, UserResponse
from copilot.service.user_session_service import get_user_session_service
from copilot.utils.error_codes import ErrorCodes, ErrorHandler, raise_auth_error, raise_system_error, raise_user_error
from copilot.utils.logger import logger
from copilot.utils.mongo_client import get_mongo_manager


class UserService:
    """用户服务类"""

    # Token配置
    DEFAULT_TOKEN_EXPIRE_SECONDS = 24 * 3600  # 默认24小时

    def __init__(self):
        self.collection_name = "users"
        self.session_service = get_user_session_service()
        logger.info("UserService initialized")

    async def hash_password(self, password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()

    async def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return hashlib.sha256(plain_password.encode()).hexdigest() == hashed_password

    async def create_access_token(self, user_id: str, username: str) -> str:
        """创建随机token并存入Redis"""
        logger.debug(f"Creating access token for user: {username}")
        token = str(uuid.uuid4())
        await self.session_service.create_user_session(user_id=user_id, username=username, token=token, expire_seconds=24 * 3600)  # 24小时有效期
        logger.debug(f"Access token created successfully for user: {username}")
        return token

    async def verify_token(self, token: str) -> Optional[dict]:
        """验证token有效性（纯Redis验证）"""
        logger.debug("Verifying token in Redis")
        try:
            session_data = await self.session_service.get_session_by_token(token)
            if not session_data:
                logger.warning("Token verification failed: no active session found")
                return None
            logger.debug(f"Token verification successful for user: {session_data.get('username')}")
            return session_data
        except Exception as e:
            logger.error(f"Token verification error: {str(e)}")
            return None
        except Exception as e:
            # 记录错误但不抛出异常，返回None表示验证失败
            logger.error(f"Token verification error: {str(e)}")
            return None

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        """根据用户名获取用户"""
        logger.debug(f"Getting user by username: {username}")
        try:
            mongo_manager = await get_mongo_manager()
            collection = await mongo_manager.get_collection(self.collection_name)
            user = await collection.find_one({"username": username})

            if user:
                logger.debug(f"User found: {username}")
            else:
                logger.debug(f"User not found: {username}")

            return user
        except Exception as e:
            logger.error(f"Failed to get user by username {username}: {str(e)}")
            raise ErrorHandler.handle_database_error(e, "用户查询")

    async def get_user_by_email(self, email: str) -> Optional[dict]:
        """根据邮箱获取用户"""
        logger.debug(f"Getting user by email: {email}")
        try:
            mongo_manager = await get_mongo_manager()
            collection = await mongo_manager.get_collection(self.collection_name)
            user = await collection.find_one({"email": email})

            if user:
                logger.debug(f"User found by email: {email}")
            else:
                logger.debug(f"User not found by email: {email}")

            return user
        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {str(e)}")
            raise ErrorHandler.handle_database_error(e, "用户邮箱查询")

    async def register_user(self, user_data: UserRegisterRequest) -> UserResponse:
        """用户注册"""
        logger.info(f"Starting user registration for username: {user_data.username}")

        # 检查用户名是否已存在
        existing_user = await self.get_user_by_username(user_data.username)
        if existing_user:
            logger.warning(f"Registration failed: username already exists: {user_data.username}")
            raise_user_error(ErrorCodes.USERNAME_EXISTS)

        # 检查邮箱是否已存在
        existing_email = await self.get_user_by_email(user_data.email)
        if existing_email:
            logger.warning(f"Registration failed: email already exists: {user_data.email}")
            raise_user_error(ErrorCodes.EMAIL_EXISTS)

        # 创建新用户
        user_id = str(uuid.uuid4())
        hashed_password = await self.hash_password(user_data.password)
        logger.debug(f"Generated user_id: {user_id} for username: {user_data.username}")

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
            collection = await mongo_manager.get_collection(self.collection_name)
            await collection.insert_one(user_dict)

            logger.info(f"User registration successful: {user_data.username} (ID: {user_id})")

            return UserResponse(
                user_id=user_id,
                username=user_data.username,
                email=user_data.email,
                full_name=user_data.full_name,
                created_at=user_dict["created_at"],
                is_active=True,
            )
        except Exception as e:
            logger.error(f"User registration failed for {user_data.username}: {str(e)}")
            raise ErrorHandler.handle_database_error(e, "用户创建")

    async def authenticate_user(self, username: str, password: str) -> Optional[dict]:
        """用户认证"""
        logger.debug(f"Authenticating user: {username}")
        user = await self.get_user_by_username(username)
        if not user:
            logger.warning(f"Authentication failed: user not found: {username}")
            return None

        if not await self.verify_password(password, user["password_hash"]):
            logger.warning(f"Authentication failed: invalid password for user: {username}")
            return None

        logger.info(f"User authentication successful: {username}")
        return user

    async def login_user(self, username: str, password: str, device_info: Optional[dict] = None) -> Optional[dict]:
        """
        用户登录，创建JWT token和Redis会话

        Args:
            username: 用户名
            password: 密码
            device_info: 设备信息（可选）

        Returns:
            包含token和用户信息的字典，或None（登录失败）
        """
        logger.info(f"User login attempt: {username}")

        # 验证用户身份
        user = await self.authenticate_user(username, password)
        if not user:
            logger.warning(f"Login failed: invalid credentials for user: {username}")
            return None

        # 检查用户是否被禁用
        if not user.get("is_active", True):
            logger.warning(f"Login failed: user account disabled: {username}")
            raise_auth_error(ErrorCodes.ACCOUNT_DISABLED)

        try:
            # 创建随机token并存入Redis
            access_token = await self.create_access_token(user_id=user["user_id"], username=user["username"])

            # 获取会话ID
            session_data = await self.session_service.get_session_by_token(access_token)
            session_id = session_data["session_id"]

            logger.info(f"User login successful: {username} (session_id: {session_id})")

            return {
                "access_token": access_token,
                "token_type": "bearer",
                "session_id": session_id,
                "user": {
                    "user_id": user["user_id"],
                    "username": user["username"],
                    "email": user["email"],
                    "full_name": user.get("full_name"),
                    "is_active": user.get("is_active", True),
                },
            }

        except Exception as e:
            logger.error(f"Login failed for user {username}: {str(e)}")
            raise ErrorHandler.handle_system_error(e, "用户登录")

    async def logout_user(self, token: str) -> bool:
        """
        用户退出登录，清理Redis会话

        Args:
            token: JWT token

        Returns:
            是否退出成功
        """
        logger.debug("User logout attempt")
        try:
            # 直接通过token删除会话
            result = await self.session_service.delete_session_by_token(token)

            if result:
                logger.info(f"User logout successful with token")
            else:
                logger.warning("Logout failed: session not found or deletion failed")

            return result

        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            return False

    async def logout_all_sessions(self, user_id: str) -> int:
        """
        用户退出所有会话

        Args:
            user_id: 用户ID

        Returns:
            撤销的会话数量
        """
        logger.info(f"Revoking all sessions for user: {user_id}")
        try:
            revoked_count = await self.session_service.revoke_user_sessions(user_id)
            logger.info(f"Revoked {revoked_count} sessions for user: {user_id}")
            return revoked_count
        except Exception as e:
            logger.error(f"Logout all sessions failed for user {user_id}: {str(e)}")
            return 0

    async def get_user_sessions(self, user_id: str) -> list:
        """
        获取用户的所有活跃会话

        Args:
            user_id: 用户ID

        Returns:
            会话列表
        """
        logger.debug(f"Getting user sessions for user: {user_id}")
        try:
            sessions = await self.session_service.get_user_sessions(user_id)
            logger.debug(f"Found {len(sessions)} active sessions for user: {user_id}")
            return sessions
        except Exception as e:
            logger.error(f"Get user sessions failed for user {user_id}: {str(e)}")
            return []

    async def get_user_info(self, user_id: str) -> Optional[UserResponse]:
        """获取用户信息"""
        logger.debug(f"Getting user info for user_id: {user_id}")
        try:
            mongo_manager = await get_mongo_manager()
            collection = await mongo_manager.get_collection(self.collection_name)
            user = await collection.find_one({"user_id": user_id})

            if not user:
                logger.warning(f"User not found for user_id: {user_id}")
                return None

            logger.debug(f"User info retrieved successfully for user_id: {user_id}")
            return UserResponse(
                user_id=user["user_id"],
                username=user["username"],
                email=user["email"],
                full_name=user.get("full_name"),
                created_at=user["created_at"],
                is_active=user.get("is_active", True),
            )
        except Exception as e:
            logger.error(f"Failed to get user info for user_id {user_id}: {str(e)}")
            raise ErrorHandler.handle_database_error(e, "用户信息获取")
