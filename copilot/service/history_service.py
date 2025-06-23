"""
聊天历史管理器
负责对话历史的持久化存储和检索
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

from copilot.utils.logger import logger
from copilot.utils.mongo_client import get_mongo_manager


@dataclass
class ChatHistoryMessage:
    """聊天历史消息"""

    role: str  # "user" 或 "assistant"
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = None


@dataclass
class ChatSession:
    """聊天会话记录"""

    session_id: str
    user_id: str
    window_id: str
    thread_id: str
    created_at: datetime
    last_activity: datetime
    messages: List[ChatHistoryMessage]
    context: Dict[str, Any] = None
    status: str = "available"  # available, deleted


class ChatHistoryManager:
    """聊天历史管理器"""

    def __init__(self):
        self.sessions_collection = "chat_sessions"
        self.messages_collection = "chat_messages"
        self._mongo_manager = None
        self._redis_client = None

    async def _get_mongo_manager(self):
        """获取MongoDB连接管理器"""
        if self._mongo_manager is None:
            self._mongo_manager = await get_mongo_manager()
        return self._mongo_manager

    async def _get_redis_client(self):
        """获取Redis客户端"""
        if self._redis_client is None:
            from copilot.utils.redis_client import redis_client

            await redis_client.initialize()
            self._redis_client = redis_client
        return self._redis_client

    async def save_message(self, session_id: str, role: str, content: str, metadata: Dict[str, Any] = None):
        """
        保存单条消息到数据库和Redis

        Args:
            session_id: 会话ID
            role: 消息角色 ("user" 或 "assistant")
            content: 消息内容
            metadata: 消息元数据
        """
        try:
            mongo_manager = await self._get_mongo_manager()
            redis_client = await self._get_redis_client()
            timestamp = datetime.now()

            # 保存到MongoDB
            messages_collection = await mongo_manager.get_collection(self.messages_collection)
            message_doc = {"session_id": session_id, "role": role, "content": content, "timestamp": timestamp, "metadata": metadata or {}}
            await messages_collection.insert_one(message_doc)

            # 保存到Redis
            redis_key = f"chat:{session_id}:messages"
            message_data = {"role": role, "content": content, "timestamp": timestamp.isoformat(), "metadata": metadata or {}}
            await redis_client.rpush(redis_key, json.dumps(message_data))

            # 更新会话的最后活动时间
            sessions_collection = await mongo_manager.get_collection(self.sessions_collection)
            await sessions_collection.update_one({"session_id": session_id}, {"$set": {"last_activity": timestamp}}, upsert=False)

            logger.debug(f"Saved message for session {session_id} to both MongoDB and Redis")

        except Exception as e:
            logger.error(f"Failed to save message for session {session_id}: {str(e)}")
            raise

    async def save_session(self, session_id: str, user_id: str, window_id: str, thread_id: str, context: Dict[str, Any] = None):
        """
        保存会话信息到数据库

        Args:
            session_id: 会话ID
            user_id: 用户ID
            window_id: 窗口ID
            thread_id: 线程ID
            context: 会话上下文
        """
        try:
            mongo_manager = await self._get_mongo_manager()
            sessions_collection = await mongo_manager.get_collection(self.sessions_collection)

            now = datetime.now()
            session_doc = {
                "session_id": session_id,
                "user_id": user_id,
                "window_id": window_id,
                "thread_id": thread_id,
                "created_at": now,
                "last_activity": now,
                "context": context or {},
                "status": "available",
            }

            await sessions_collection.insert_one(session_doc)
            logger.info(f"Saved session {session_id} to database")

        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {str(e)}")
            raise

    async def get_session_messages(self, session_id: str, limit: int = 100, offset: int = 0) -> List[ChatHistoryMessage]:
        """
        获取会话的消息历史，优先从Redis获取

        Args:
            session_id: 会话ID
            limit: 返回消息数量限制
            offset: 偏移量

        Returns:
            List[ChatHistoryMessage]: 消息列表
        """
        try:
            redis_client = await self._get_redis_client()
            redis_key = f"chat:{session_id}:messages"

            # 首先尝试从Redis获取
            redis_messages = await redis_client.lrange(redis_key, offset, offset + limit - 1)
            if redis_messages:
                messages = []
                for msg_json in redis_messages:
                    msg_data = json.loads(msg_json)
                    messages.append(
                        ChatHistoryMessage(
                            role=msg_data["role"],
                            content=msg_data["content"],
                            timestamp=datetime.fromisoformat(msg_data["timestamp"]),
                            metadata=msg_data.get("metadata", {}),
                        )
                    )
                return messages

            # Redis中没有则从MongoDB获取
            mongo_manager = await self._get_mongo_manager()
            messages_collection = await mongo_manager.get_collection(self.messages_collection)

            cursor = messages_collection.find({"session_id": session_id}).sort("timestamp", 1)

            if offset:
                cursor = cursor.skip(offset)
            if limit:
                cursor = cursor.limit(limit)

            messages = await cursor.to_list(length=None)

            return [
                ChatHistoryMessage(role=msg["role"], content=msg["content"], timestamp=msg["timestamp"], metadata=msg.get("metadata", {}))
                for msg in messages
            ]

        except Exception as e:
            logger.error(f"Failed to get messages for session {session_id}: {str(e)}")
            return []

    async def get_user_sessions(self, user_id: str, include_deleted: bool = False, limit: int = 50) -> List[ChatSession]:
        """
        获取用户的会话列表

        Args:
            user_id: 用户ID
            include_deleted: 是否包含已删除的会话
            limit: 返回数量限制

        Returns:
            List[ChatSession]: 会话列表
        """
        try:
            mongo_manager = await self._get_mongo_manager()
            sessions_collection = await mongo_manager.get_collection(self.sessions_collection)

            # 构建查询条件
            query = {"user_id": user_id}
            if not include_deleted:
                query["status"] = {"$ne": "deleted"}

            cursor = sessions_collection.find(query).sort("last_activity", -1)

            if limit:
                cursor = cursor.limit(limit)

            sessions = await cursor.to_list(length=None)

            result = []
            for session in sessions:
                # 获取每个会话的消息
                messages = await self.get_session_messages(session["session_id"])

                # 判断会话的实际状态
                actual_status = await self._get_session_actual_status(session["session_id"], session.get("status", "available"))

                chat_session = ChatSession(
                    session_id=session["session_id"],
                    user_id=session["user_id"],
                    window_id=session["window_id"],
                    thread_id=session["thread_id"],
                    created_at=session["created_at"],
                    last_activity=session["last_activity"],
                    messages=messages,
                    context=session.get("context", {}),
                    status=actual_status,
                )
                result.append(chat_session)

            return result

        except Exception as e:
            logger.error(f"Failed to get sessions for user {user_id}: {str(e)}")
            return []

    async def archive_session(self, session_id: str):
        """
        归档会话（从Redis中移除，但保持数据库状态为available）
        
        Args:
            session_id: 会话ID
        """
        try:
            # 归档只是从Redis中移除，不改变数据库状态
            from copilot.core.session_manager import session_manager
            from copilot.utils.redis_client import get_redis
            
            async with get_redis() as redis:
                # 从Redis中删除会话数据
                session_key = f"{session_manager.redis_prefix}{session_id}"
                await redis.delete(session_key)
                
                # 从用户会话列表中移除（需要知道user_id）
                mongo_manager = await self._get_mongo_manager()
                sessions_collection = await mongo_manager.get_collection(self.sessions_collection)
                session_doc = await sessions_collection.find_one({"session_id": session_id})
                
                if session_doc:
                    user_sessions_key = f"{session_manager.user_sessions_prefix}{session_doc['user_id']}"
                    await redis.srem(user_sessions_key, session_id)
                    
                    # 可选：记录归档时间（但不改变status）
                    await sessions_collection.update_one(
                        {"session_id": session_id}, 
                        {"$set": {"archived_at": datetime.now()}}
                    )

            logger.info(f"Archived session {session_id} (removed from Redis)")

        except Exception as e:
            logger.error(f"Failed to archive session {session_id}: {str(e)}")
            raise

    async def delete_session(self, session_id: str, hard_delete: bool = False):
        """
        删除会话

        Args:
            session_id: 会话ID
            hard_delete: 是否物理删除（True）或逻辑删除（False）
        """
        try:
            mongo_manager = await self._get_mongo_manager()
            sessions_collection = await mongo_manager.get_collection(self.sessions_collection)
            messages_collection = await mongo_manager.get_collection(self.messages_collection)

            if hard_delete:
                # 物理删除
                await messages_collection.delete_many({"session_id": session_id})
                result = await sessions_collection.delete_one({"session_id": session_id})

                if result.deleted_count > 0:
                    logger.info(f"Hard deleted session {session_id}")
                else:
                    logger.warning(f"Session {session_id} not found for deletion")
            else:
                # 逻辑删除：标记为deleted并从Redis中移除
                result = await sessions_collection.update_one(
                    {"session_id": session_id}, 
                    {"$set": {"status": "deleted", "deleted_at": datetime.now()}}
                )

                if result.modified_count > 0:
                    # 同时从Redis中移除
                    from copilot.core.session_manager import session_manager
                    from copilot.utils.redis_client import get_redis
                    
                    async with get_redis() as redis:
                        session_key = f"{session_manager.redis_prefix}{session_id}"
                        await redis.delete(session_key)
                        
                        # 从用户会话列表中移除
                        session_doc = await sessions_collection.find_one({"session_id": session_id})
                        if session_doc:
                            user_sessions_key = f"{session_manager.user_sessions_prefix}{session_doc['user_id']}"
                            await redis.srem(user_sessions_key, session_id)
                    
                    logger.info(f"Soft deleted session {session_id}")
                else:
                    logger.warning(f"Session {session_id} not found for deletion")

        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {str(e)}")
            raise

    async def restore_session_from_archive(self, session_id: str, user_id: str, window_id: str, thread_id: str) -> bool:
        """
        从数据库恢复会话到Redis（用于会话超时后的恢复）

        Args:
            session_id: 会话ID
            user_id: 用户ID
            window_id: 窗口ID
            thread_id: 线程ID

        Returns:
            bool: 是否成功恢复
        """
        try:
            mongo_manager = await self._get_mongo_manager()
            sessions_collection = await mongo_manager.get_collection(self.sessions_collection)

            # 查找会话记录
            session = await sessions_collection.find_one({"session_id": session_id, "user_id": user_id})

            if not session:
                logger.warning(f"Session {session_id} not found in archive")
                return False

            # 获取消息历史
            messages = await self.get_session_messages(session_id)

            logger.info(f"Found archived session {session_id} with {len(messages)} messages")
            return True

        except Exception as e:
            logger.error(f"Failed to restore session {session_id}: {str(e)}")
            return False

    async def search_messages(self, user_id: str, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        搜索用户的消息历史

        Args:
            user_id: 用户ID
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            List[Dict]: 搜索结果
        """
        try:
            mongo_manager = await self._get_mongo_manager()
            sessions_collection = await mongo_manager.get_collection(self.sessions_collection)
            messages_collection = await mongo_manager.get_collection(self.messages_collection)

            # 首先获取用户的所有会话ID
            cursor = sessions_collection.find({"user_id": user_id}, {"session_id": 1})
            sessions = await cursor.to_list(length=None)

            session_ids = [s["session_id"] for s in sessions]

            if not session_ids:
                return []

            # 在这些会话中搜索消息
            cursor = messages_collection.find(
                {"session_id": {"$in": session_ids}, "content": {"$regex": query, "$options": "i"}}  # 不区分大小写搜索
            ).sort("timestamp", -1)

            if limit:
                cursor = cursor.limit(limit)

            messages = await cursor.to_list(length=None)

            # 转换ObjectId为字符串
            for msg in messages:
                if "_id" in msg:
                    msg["_id"] = str(msg["_id"])

            return messages

        except Exception as e:
            logger.error(f"Failed to search messages for user {user_id}: {str(e)}")
            return []

    async def get_stats(self, user_id: str = None) -> Dict[str, Any]:
        """
        获取统计信息

        Args:
            user_id: 用户ID（可选，不提供则返回全局统计）

        Returns:
            Dict: 统计信息
        """
        try:
            mongo_manager = await self._get_mongo_manager()
            sessions_collection = await mongo_manager.get_collection(self.sessions_collection)
            messages_collection = await mongo_manager.get_collection(self.messages_collection)

            filter_dict = {"user_id": user_id} if user_id else {}

            session_count = await sessions_collection.count_documents(filter_dict)

            message_filter = {}
            if user_id:
                # 获取用户的会话ID
                cursor = sessions_collection.find({"user_id": user_id}, {"session_id": 1})
                sessions = await cursor.to_list(length=None)
                session_ids = [s["session_id"] for s in sessions]
                message_filter = {"session_id": {"$in": session_ids}}

            message_count = await messages_collection.count_documents(message_filter)

            return {"total_sessions": session_count, "total_messages": message_count, "user_id": user_id}

        except Exception as e:
            logger.error(f"Failed to get stats: {str(e)}")
            return {}

    async def reactivate_session(self, session_id: str):
        """
        重新激活会话（将非活跃会话重新加载到Redis）

        Args:
            session_id: 会话ID

        Returns:
            bool: 是否成功激活
        """
        try:
            mongo_manager = await self._get_mongo_manager()
            sessions_collection = await mongo_manager.get_collection(self.sessions_collection)

            # 只能激活available状态的会话
            session_doc = await sessions_collection.find_one({
                "session_id": session_id, 
                "status": "available"
            })

            if not session_doc:
                logger.warning(f"Session {session_id} not found or not available for reactivation")
                return False

            # 检查是否已经在Redis中（避免重复操作）
            from copilot.core.session_manager import SessionInfo, session_manager
            existing_session = await session_manager.get_session(session_id)
            if existing_session:
                logger.info(f"Session {session_id} is already active")
                return True

            # 重建SessionInfo并加载到Redis
            from copilot.utils.redis_client import get_redis
            
            session_info = SessionInfo(
                session_id=session_doc["session_id"],
                user_id=session_doc["user_id"],
                window_id=session_doc["window_id"],
                created_at=session_doc["created_at"],
                last_activity=datetime.now(),  # 更新为当前时间
                context=session_doc.get("context", {}),
                thread_id=session_doc["thread_id"],
            )

            # 保存到Redis
            async with get_redis() as redis:
                session_key = f"{session_manager.redis_prefix}{session_id}"
                session_data = session_manager._serialize_session(session_info)
                await redis.set(session_key, session_data, ex=session_manager.session_timeout)

                # 添加到用户会话列表
                user_sessions_key = f"{session_manager.user_sessions_prefix}{session_info.user_id}"
                await redis.sadd(user_sessions_key, session_id)
                await redis.expire(user_sessions_key, session_manager.session_timeout)

            # 更新数据库中的最后活动时间
            await sessions_collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "last_activity": datetime.now(),
                        "reactivated_at": datetime.now()
                    }
                }
            )
            
            logger.info(f"Successfully reactivated session {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to reactivate session {session_id}: {str(e)}")
            raise

    async def _get_session_actual_status(self, session_id: str, db_status: str) -> str:
        """
        获取会话的实际状态（结合Redis和MongoDB）
        
        Args:
            session_id: 会话ID
            db_status: 数据库中的状态
            
        Returns:
            str: 实际状态 (active, inactive, deleted)
        """
        try:
            # 如果数据库中标记为删除，直接返回deleted
            if db_status == "deleted":
                return "deleted"
            
            # 检查Redis中是否存在
            from copilot.core.session_manager import session_manager
            session_info = await session_manager.get_session(session_id)
            
            if session_info:
                return "active"  # Redis中存在 = 活跃
            else:
                return "inactive"  # Redis中不存在但数据库中可用 = 非活跃（可恢复）
                
        except Exception as e:
            logger.error(f"Failed to get actual status for session {session_id}: {str(e)}")
            return "inactive"


# 全局聊天历史管理器实例
chat_history_manager = ChatHistoryManager()
