"""
会话管理器
支持多用户、多窗口的对话会话管理
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from copilot.utils.redis_client import RedisClient
from copilot.utils.logger import logger


@dataclass
class SessionInfo:
    """会话信息"""

    session_id: str
    user_id: str
    window_id: str  # 用户可能有多个窗口
    created_at: datetime
    last_activity: datetime
    context: Dict[str, Any]  # 存储用户上下文信息
    thread_id: str  # LangGraph的线程ID


class SessionManager:
    """会话管理器"""

    def __init__(self, session_timeout: int = 3600):  # 1小时超时
        self.session_timeout = session_timeout
        self.redis_prefix = "agent_session:"
        self.user_sessions_prefix = "user_sessions:"

    async def create_session(self, user_id: str, window_id: str) -> str:
        """
        创建新会话

        Args:
            user_id: 用户ID
            window_id: 窗口ID，如果不提供则自动生成

        Returns:
            session_id: 会话ID
        """
        session_id = str(uuid.uuid4())
        thread_id = f"{user_id}_{session_id}"

        if window_id is None:
            window_id = str(uuid.uuid4())

        now = datetime.now()
        session_info = SessionInfo(
            session_id=session_id, user_id=user_id, window_id=window_id, created_at=now, last_activity=now, context={}, thread_id=thread_id
        )

        async with RedisClient() as redis:
            # 保存会话信息
            session_key = f"{self.redis_prefix}{session_id}"
            session_data = self._serialize_session(session_info)
            await redis.set(session_key, session_data, ex=self.session_timeout)

            # 维护用户的会话列表
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            await redis.sadd(user_sessions_key, session_id)
            await redis.expire(user_sessions_key, self.session_timeout)

        logger.info(f"Created session {session_id} for user {user_id}, window {window_id}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """
        获取会话信息

        Args:
            session_id: 会话ID

        Returns:
            SessionInfo or None
        """
        async with RedisClient() as redis:
            session_key = f"{self.redis_prefix}{session_id}"
            session_data = await redis.get(session_key)

            if not session_data:
                return None

            session_info = self._deserialize_session(session_data)

            # 更新最后活动时间
            session_info.last_activity = datetime.now()
            updated_data = self._serialize_session(session_info)
            await redis.set(session_key, updated_data, ex=self.session_timeout)

            return session_info

    async def update_session_context(self, session_id: str, context: Dict[str, Any]):
        """
        更新会话上下文

        Args:
            session_id: 会话ID
            context: 要更新的上下文信息
        """
        session_info = await self.get_session(session_id)
        if not session_info:
            logger.warning(f"Session {session_id} not found for context update")
            return

        session_info.context.update(context)

        async with RedisClient() as redis:
            session_key = f"{self.redis_prefix}{session_id}"
            session_data = self._serialize_session(session_info)
            await redis.set(session_key, session_data, ex=self.session_timeout)

    async def get_user_sessions(self, user_id: str) -> List[SessionInfo]:
        """
        获取用户的所有活跃会话

        Args:
            user_id: 用户ID

        Returns:
            List[SessionInfo]: 用户的所有活跃会话
        """
        async with RedisClient() as redis:
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            session_ids = await redis.smembers(user_sessions_key)

            sessions = []
            for session_id in session_ids:
                session_info = await self.get_session(session_id)
                if session_info:
                    sessions.append(session_info)
                else:
                    # 清理无效的会话ID
                    await redis.srem(user_sessions_key, session_id)

            return sessions

    async def delete_session(self, session_id: str):
        """
        删除会话

        Args:
            session_id: 会话ID
        """
        session_info = await self.get_session(session_id)
        if not session_info:
            return

        async with RedisClient() as redis:
            # 删除会话数据
            session_key = f"{self.redis_prefix}{session_id}"
            await redis.delete(session_key)

            # 从用户会话列表中移除
            user_sessions_key = f"{self.user_sessions_prefix}{session_info.user_id}"
            await redis.srem(user_sessions_key, session_id)

        logger.info(f"Deleted session {session_id}")

    async def cleanup_expired_sessions(self):
        """清理过期会话（可以作为定时任务运行）"""
        # Redis的过期机制会自动清理过期的键
        # 这里主要是清理用户会话列表中的无效引用
        async with RedisClient() as redis:
            # 获取所有用户会话键
            pattern = f"{self.user_sessions_prefix}*"
            keys = await redis.keys(pattern)

            for key in keys:
                session_ids = await redis.smembers(key)
                for session_id in session_ids:
                    session_key = f"{self.redis_prefix}{session_id}"
                    if not await redis.exists(session_key):
                        await redis.srem(key, session_id)

    def _serialize_session(self, session_info: SessionInfo) -> str:
        """序列化会话信息"""
        data = asdict(session_info)
        # 处理datetime对象
        data["created_at"] = session_info.created_at.isoformat()
        data["last_activity"] = session_info.last_activity.isoformat()
        return json.dumps(data)

    def _deserialize_session(self, session_data: str) -> SessionInfo:
        """反序列化会话信息"""
        data = json.loads(session_data)
        # 处理datetime对象
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["last_activity"] = datetime.fromisoformat(data["last_activity"])
        return SessionInfo(**data)


# 全局会话管理器实例
session_manager = SessionManager()
