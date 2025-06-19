"""
用户会话管理服务
负责用户登录状态的Redis存储和管理
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from copilot.utils.redis_client import get_redis
from copilot.utils.logger import logger


class UserSessionService:
    """用户会话管理服务"""

    def __init__(self):
        # Redis键前缀
        self.session_prefix = "user_session:"
        self.user_sessions_prefix = "user_sessions:"
        self.token_prefix = "token:"
        # 默认会话过期时间（秒）
        self.default_session_expire = 24 * 60 * 60  # 24小时
        self.token_expire = 24 * 60 * 60  # 与JWT token过期时间保持一致

    async def create_user_session(
        self, user_id: str, username: str, token: str, device_info: Optional[Dict] = None, expire_seconds: Optional[int] = None
    ) -> str:
        """
        创建用户会话

        Args:
            user_id: 用户ID
            username: 用户名
            token: JWT token
            device_info: 设备信息
            expire_seconds: 过期时间（秒）

        Returns:
            会话ID
        """
        session_id = str(uuid.uuid4())
        expire_time = expire_seconds or self.default_session_expire

        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "username": username,
            "token": token,
            "device_info": device_info or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_active": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expire_time)).isoformat(),
        }

        try:
            # 存储会话数据
            session_key = f"{self.session_prefix}{session_id}"
            async with get_redis() as redis:
                await redis.set(session_key, json.dumps(session_data), ex=expire_time)

                # 存储token到session_id的映射
                token_key = f"{self.token_prefix}{token}"
                await redis.set(token_key, session_id, ex=expire_seconds or self.default_session_expire)

                # 将session_id添加到用户的会话集合中
                user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
                await redis.sadd(user_sessions_key, session_id)
                await redis.expire(user_sessions_key, expire_time)

            logger.info(f"Created session {session_id} for user {username}")
            return session_id

        except Exception as e:
            logger.error(f"Failed to create session for user {username}: {str(e)}")
            raise

    async def get_session_by_token(self, token: str) -> Optional[Dict]:
        """
        通过token获取会话信息

        Args:
            token: JWT token

        Returns:
            会话数据字典或None
        """
        try:
            # 从token获取session_id
            token_key = f"{self.token_prefix}{token}"
            async with get_redis() as redis:
                session_id = await redis.get(token_key)

            if not session_id:
                return None

            # 获取会话数据
            return await self.get_session_by_id(session_id)

        except Exception as e:
            logger.error(f"Failed to get session by token: {str(e)}")
            return None

    async def get_session_by_id(self, session_id: str) -> Optional[Dict]:
        """
        通过session_id获取会话信息

        Args:
            session_id: 会话ID

        Returns:
            会话数据字典或None
        """
        try:
            session_key = f"{self.session_prefix}{session_id}"
            async with get_redis() as redis:
                session_data = await redis.get(session_key)

            if not session_data:
                return None

            session_dict = json.loads(session_data)

            # 更新最后活跃时间
            await self.update_session_last_active(session_id)

            return session_dict

        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {str(e)}")
            return None

    async def update_session_last_active(self, session_id: str) -> bool:
        """
        更新会话最后活跃时间

        Args:
            session_id: 会话ID

        Returns:
            是否更新成功
        """
        try:
            session_key = f"{self.session_prefix}{session_id}"
            async with get_redis() as redis:
                session_data = await redis.get(session_key)

                if not session_data:
                    return False

                session_dict = json.loads(session_data)
                session_dict["last_active"] = datetime.now(timezone.utc).isoformat()

                # 获取剩余TTL并重新设置
                ttl = await redis.ttl(session_key)
                if ttl > 0:
                    await redis.set(session_key, json.dumps(session_dict), ex=ttl)
                    return True

            return False

        except Exception as e:
            logger.error(f"Failed to update session last active {session_id}: {str(e)}")
            return False

    async def get_user_sessions(self, user_id: str) -> List[Dict]:
        """
        获取用户的所有活跃会话

        Args:
            user_id: 用户ID

        Returns:
            会话列表
        """
        try:
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            async with get_redis() as redis:
                session_ids = await redis.smembers(user_sessions_key)

            sessions = []
            for session_id in session_ids:
                session_data = await self.get_session_by_id(session_id)
                if session_data:
                    sessions.append(session_data)
                else:
                    # 清理无效的session_id
                    async with get_redis() as redis:
                        await redis.srem(user_sessions_key, session_id)

            return sessions

        except Exception as e:
            logger.error(f"Failed to get user sessions for user {user_id}: {str(e)}")
            return []

    async def delete_session(self, session_id: str) -> bool:
        """
        删除指定会话

        Args:
            session_id: 会话ID

        Returns:
            是否删除成功
        """
        try:
            session_key = f"{self.session_prefix}{session_id}"

            # 先获取会话信息以便清理相关数据
            session_data = await self.get_session_by_id(session_id)
            if not session_data:
                return True  # 会话不存在，认为删除成功

            async with get_redis() as redis:
                # 删除会话数据
                await redis.delete(session_key)

                # 删除token映射
                token_key = f"{self.token_prefix}{session_data['token']}"
                await redis.delete(token_key)

                # 从用户会话集合中移除
                user_sessions_key = f"{self.user_sessions_prefix}{session_data['user_id']}"
                await redis.srem(user_sessions_key, session_id)

            logger.info(f"Deleted session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {str(e)}")
            return False

    async def delete_user_sessions(self, user_id: str) -> int:
        """
        删除用户的所有会话

        Args:
            user_id: 用户ID

        Returns:
            删除的会话数量
        """
        try:
            sessions = await self.get_user_sessions(user_id)
            deleted_count = 0

            for session in sessions:
                if await self.delete_session(session["session_id"]):
                    deleted_count += 1

            logger.info(f"Deleted {deleted_count} sessions for user {user_id}")
            return deleted_count

        except Exception as e:
            logger.error(f"Failed to delete user sessions for user {user_id}: {str(e)}")
            return 0

    async def cleanup_expired_sessions(self) -> int:
        """
        清理过期的会话

        Returns:
            清理的会话数量
        """
        try:
            cleaned_count = 0
            async with get_redis() as redis:
                # 获取所有会话键
                session_keys = await redis.keys(f"{self.session_prefix}*")

            for session_key in session_keys:
                try:
                    async with get_redis() as redis:
                        session_data = await redis.get(session_key)
                    if not session_data:
                        # 会话已过期或不存在
                        session_id = session_key.replace(self.session_prefix, "")
                        # 清理可能残留的用户会话集合引用
                        async with get_redis() as redis:
                            user_sessions_keys = await redis.keys(f"{self.user_sessions_prefix}*")
                        for user_sessions_key in user_sessions_keys:
                            async with get_redis() as redis:
                                await redis.srem(user_sessions_key, session_id)
                        cleaned_count += 1

                except Exception as e:
                    logger.warning(f"Error processing session key {session_key}: {str(e)}")
                    continue

            logger.info(f"Cleaned up {cleaned_count} expired sessions")
            return cleaned_count

        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {str(e)}")
            return 0

    async def get_session_info(self, session_id: str) -> Optional[Dict]:
        """
        获取会话基本信息（不更新活跃时间）

        Args:
            session_id: 会话ID

        Returns:
            会话信息字典或None
        """
        try:
            session_key = f"{self.session_prefix}{session_id}"
            async with get_redis() as redis:
                session_data = await redis.get(session_key)

            if not session_data:
                return None

            return json.loads(session_data)

        except Exception as e:
            logger.error(f"Failed to get session info {session_id}: {str(e)}")
            return None

    async def extend_session(self, session_id: str, extend_seconds: int = 3600) -> bool:
        """
        延长会话过期时间

        Args:
            session_id: 会话ID
            extend_seconds: 延长时间（秒），默认1小时

        Returns:
            是否延长成功
        """
        try:
            session_key = f"{self.session_prefix}{session_id}"
            async with get_redis() as redis:
                # 检查会话是否存在
                if not await redis.exists(session_key):
                    return False

                # 延长过期时间
                await redis.expire(session_key, extend_seconds)

                # 更新会话数据中的过期时间
                session_data = await redis.get(session_key)
            if session_data:
                session_dict = json.loads(session_data)
                session_dict["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=extend_seconds)).isoformat()
                async with get_redis() as redis:
                    await redis.set(session_key, json.dumps(session_dict), ex=extend_seconds)

            logger.info(f"Extended session {session_id} by {extend_seconds} seconds")
            return True

        except Exception as e:
            logger.error(f"Failed to extend session {session_id}: {str(e)}")
            return False


# 创建全局实例
_user_session_service: Optional[UserSessionService] = None


def get_user_session_service() -> UserSessionService:
    """获取用户会话服务实例（单例模式）"""
    global _user_session_service
    if _user_session_service is None:
        _user_session_service = UserSessionService()
    return _user_session_service
