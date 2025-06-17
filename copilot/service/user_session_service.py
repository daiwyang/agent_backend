"""
用户会话管理服务
负责用户登录状态的Redis存储和管理
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from copilot.utils.redis_client import redis_client
from copilot.utils.logger import logger


class UserSessionService:
    """用户会话管理服务"""
    
    def __init__(self):
        self.redis_client = redis_client
        # Redis键前缀
        self.session_prefix = "user_session:"
        self.user_sessions_prefix = "user_sessions:"
        self.token_prefix = "token:"
        # 默认会话过期时间（秒）
        self.default_session_expire = 24 * 60 * 60  # 24小时
        self.token_expire = 30 * 60  # 30分钟
    
    async def create_user_session(self, user_id: str, username: str, token: str, 
                                device_info: Optional[Dict] = None, 
                                expire_seconds: Optional[int] = None) -> str:
        """
        创建用户会话
        
        Args:
            user_id: 用户ID
            username: 用户名
            token: JWT token
            device_info: 设备信息
            expire_seconds: 过期时间（秒）
            
        Returns:
            session_id: 会话ID
        """
        session_id = str(uuid.uuid4())
        expire_time = expire_seconds or self.default_session_expire
        
        # 创建会话数据
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "username": username,
            "token": token,
            "device_info": device_info or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_active": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=expire_time)).isoformat()
        }
        
        try:
            # 存储会话数据
            session_key = f"{self.session_prefix}{session_id}"
            await self.redis_client.set(session_key, json.dumps(session_data), ex=expire_time)
            
            # 存储token到session_id的映射
            token_key = f"{self.token_prefix}{token}"
            await self.redis_client.set(token_key, session_id, ex=self.token_expire)
            
            # 将session_id添加到用户的会话集合中
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            await self.redis_client.sadd(user_sessions_key, session_id)
            await self.redis_client.expire(user_sessions_key, expire_time)
            
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
            session_id = await self.redis_client.get(token_key)
            
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
            session_data = await self.redis_client.get(session_key)
            
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
            session_data = await self.redis_client.get(session_key)
            
            if not session_data:
                return False
            
            session_dict = json.loads(session_data)
            session_dict["last_active"] = datetime.now(timezone.utc).isoformat()
            
            # 获取剩余TTL并重新设置
            ttl = await self.redis_client.client.ttl(session_key)
            if ttl > 0:
                await self.redis_client.set(session_key, json.dumps(session_dict), ex=ttl)
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
            session_ids = await self.redis_client.smembers(user_sessions_key)
            
            sessions = []
            for session_id in session_ids:
                session_data = await self.get_session_by_id(session_id)
                if session_data:
                    sessions.append(session_data)
                else:
                    # 清理无效的session_id
                    await self.redis_client.srem(user_sessions_key, session_id)
            
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to get user sessions for {user_id}: {str(e)}")
            return []
    
    async def revoke_session(self, session_id: str) -> bool:
        """
        撤销/删除会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            是否撤销成功
        """
        try:
            # 获取会话数据
            session_data = await self.get_session_by_id(session_id)
            if not session_data:
                return False
            
            user_id = session_data["user_id"]
            token = session_data["token"]
            
            # 删除会话数据
            session_key = f"{self.session_prefix}{session_id}"
            await self.redis_client.delete(session_key)
            
            # 删除token映射
            token_key = f"{self.token_prefix}{token}"
            await self.redis_client.delete(token_key)
            
            # 从用户会话集合中移除
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            await self.redis_client.srem(user_sessions_key, session_id)
            
            logger.info(f"Revoked session {session_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke session {session_id}: {str(e)}")
            return False
    
    async def revoke_user_sessions(self, user_id: str) -> int:
        """
        撤销用户的所有会话
        
        Args:
            user_id: 用户ID
            
        Returns:
            撤销的会话数量
        """
        try:
            sessions = await self.get_user_sessions(user_id)
            revoked_count = 0
            
            for session in sessions:
                if await self.revoke_session(session["session_id"]):
                    revoked_count += 1
            
            logger.info(f"Revoked {revoked_count} sessions for user {user_id}")
            return revoked_count
            
        except Exception as e:
            logger.error(f"Failed to revoke user sessions for {user_id}: {str(e)}")
            return 0
    
    async def cleanup_expired_sessions(self) -> int:
        """
        清理过期的会话
        
        Returns:
            清理的会话数量
        """
        try:
            # 获取所有会话键
            session_keys = await self.redis_client.keys(f"{self.session_prefix}*")
            expired_count = 0
            
            for session_key in session_keys:
                # Redis会自动处理过期键，这里主要是清理用户会话集合中的引用
                session_data = await self.redis_client.get(session_key)
                if not session_data:
                    # 从session_key中提取session_id
                    session_id = session_key.replace(self.session_prefix, "")
                    
                    # 从所有用户会话集合中移除这个session_id
                    user_sessions_keys = await self.redis_client.keys(f"{self.user_sessions_prefix}*")
                    for user_sessions_key in user_sessions_keys:
                        await self.redis_client.srem(user_sessions_key, session_id)
                    
                    expired_count += 1
            
            logger.info(f"Cleaned up {expired_count} expired sessions")
            return expired_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {str(e)}")
            return 0
    
    async def is_session_valid(self, session_id: str) -> bool:
        """
        检查会话是否有效
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话是否有效
        """
        session_data = await self.get_session_by_id(session_id)
        return session_data is not None
    
    async def extend_session(self, session_id: str, extend_seconds: int = None) -> bool:
        """
        延长会话过期时间
        
        Args:
            session_id: 会话ID
            extend_seconds: 延长时间（秒）
            
        Returns:
            是否延长成功
        """
        try:
            extend_time = extend_seconds or self.default_session_expire
            session_key = f"{self.session_prefix}{session_id}"
            
            # 检查会话是否存在
            if not await self.redis_client.exists(session_key):
                return False
            
            # 延长过期时间
            await self.redis_client.expire(session_key, extend_time)
            
            # 更新会话数据中的过期时间
            session_data = await self.redis_client.get(session_key)
            if session_data:
                session_dict = json.loads(session_data)
                session_dict["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=extend_time)).isoformat()
                await self.redis_client.set(session_key, json.dumps(session_dict), ex=extend_time)
            
            logger.info(f"Extended session {session_id} by {extend_time} seconds")
            return True
            
        except Exception as e:
            logger.error(f"Failed to extend session {session_id}: {str(e)}")
            return False


# 创建全局会话服务实例
user_session_service = UserSessionService()


def get_user_session_service() -> UserSessionService:
    """获取用户会话服务实例"""
    return user_session_service
