"""
聊天历史管理器
负责对话历史的持久化存储和检索
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List

from copilot.utils.logger import logger
from copilot.utils.mongo_client import get_mongo_manager


@dataclass
class ChatHistoryMessage:
    """聊天历史消息"""

    role: str  # "user" 或 "assistant"
    content: str
    timestamp: datetime
    message_id: str = None  # MongoDB的_id字段
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
        保存单条消息（双写 Redis + MongoDB）
        策略：优先保证 MongoDB 持久化成功，然后写入 Redis 缓存

        Args:
            session_id: 会话ID
            role: 消息角色 ("user" 或 "assistant")
            content: 消息内容
            metadata: 消息元数据
        """
        timestamp = datetime.now()
        message_doc = {
            "session_id": session_id,
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "metadata": metadata or {}
        }

        try:
            # 1. 首先保存到 MongoDB（持久化存储优先）
            mongo_manager = await self._get_mongo_manager()
            messages_collection = await mongo_manager.get_collection(self.messages_collection)
            result = await messages_collection.insert_one(message_doc)
            
            # 获取插入后的_id
            message_id = str(result.inserted_id)

            # 2. 更新会话的最后活动时间
            sessions_collection = await mongo_manager.get_collection(self.sessions_collection)
            await sessions_collection.update_one(
                {"session_id": session_id},
                {"$set": {"last_activity": timestamp}},
                upsert=False
            )

            # 3. 保存到 Redis 缓存（提高读取性能）
            try:
                redis_client = await self._get_redis_client()
                redis_key = f"chat:{session_id}:messages"
                message_data = {
                    "message_id": message_id,  # 包含消息ID
                    "role": role,
                    "content": content,
                    "timestamp": timestamp.isoformat(),
                    "metadata": metadata or {}
                }
                await redis_client.rpush(redis_key, json.dumps(message_data))
                # 设置 Redis 键的过期时间（7天，防止内存占用过多）
                await redis_client.expire(redis_key, 7 * 24 * 3600)
                
                logger.debug(f"Successfully saved message for session {session_id} to both MongoDB and Redis")
                
            except Exception as redis_error:
                logger.warning(f"Failed to save message to Redis for session {session_id}: {str(redis_error)}")
                # Redis 写入失败不影响主流程，因为 MongoDB 已经成功

            # 返回生成的消息ID
            return message_id

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
        获取会话的消息历史
        读取策略：优先从 Redis 获取，如果 Redis 中没有，则从 MongoDB 获取并恢复到 Redis

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

            # 1. 首先尝试从 Redis 获取
            redis_messages = await redis_client.lrange(redis_key, offset, offset + limit - 1)
            if redis_messages:
                messages = []
                for msg_json in redis_messages:
                    msg_data = json.loads(msg_json)
                    messages.append(
                        ChatHistoryMessage(
                            message_id=msg_data.get("message_id"),
                            role=msg_data["role"],
                            content=msg_data["content"],
                            timestamp=datetime.fromisoformat(msg_data["timestamp"]),
                            metadata=msg_data.get("metadata", {}),
                        )
                    )
                logger.debug(f"Retrieved {len(messages)} messages for session {session_id} from Redis")
                return messages

            # 2. Redis 中没有，从 MongoDB 获取
            logger.info(f"Messages for session {session_id} not found in Redis, fetching from MongoDB")
            mongo_manager = await self._get_mongo_manager()
            messages_collection = await mongo_manager.get_collection(self.messages_collection)

            cursor = messages_collection.find({"session_id": session_id}).sort("timestamp", 1)

            if offset:
                cursor = cursor.skip(offset)
            if limit:
                cursor = cursor.limit(limit)

            messages_docs = await cursor.to_list(length=None)
            
            if not messages_docs:
                return []

            # 3. 转换为消息对象
            messages = [
                ChatHistoryMessage(
                    message_id=str(msg["_id"]) if "_id" in msg else None,
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=msg["timestamp"],
                    metadata=msg.get("metadata", {})
                )
                for msg in messages_docs
            ]
            
            # 4. 恢复到 Redis（异步，不影响返回）
            try:
                redis_data = []
                for msg in messages:
                    message_data = {
                        "message_id": msg.message_id,
                        "role": msg.role,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat(),
                        "metadata": msg.metadata
                    }
                    redis_data.append(json.dumps(message_data))
                
                if redis_data:
                    # 使用异步上下文管理器批量写入 Redis
                    client = redis_client._ensure_initialized()
                    async with client.pipeline() as pipe:
                        pipe.delete(redis_key)  # 清空旧数据
                        for data in redis_data:
                            pipe.rpush(redis_key, data)
                        pipe.expire(redis_key, 7 * 24 * 3600)  # 7天过期
                        await pipe.execute()
                    
                    logger.info(f"Restored {len(messages)} messages for session {session_id} to Redis")
                    
            except Exception as redis_error:
                logger.warning(f"Failed to restore messages to Redis for session {session_id}: {str(redis_error)}")
                # Redis 恢复失败不影响消息返回
            
            logger.debug(f"Retrieved {len(messages)} messages for session {session_id} from MongoDB")
            return messages

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

                chat_session = ChatSession(
                    session_id=session["session_id"],
                    user_id=session["user_id"],
                    window_id=session["window_id"],
                    thread_id=session["thread_id"],
                    created_at=session["created_at"],
                    last_activity=session["last_activity"],
                    messages=messages,
                    context=session.get("context", {}),
                    status=session.get("status", "available"),
                )
                result.append(chat_session)

            return result

        except Exception as e:
            logger.error(f"Failed to get sessions for user {user_id}: {str(e)}")
            return []

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


    async def restore_messages_to_redis(self, session_id: str = None, batch_size: int = 100) -> Dict[str, int]:
        """
        从 MongoDB 恢复消息到 Redis
        用于系统维护或 Redis 数据丢失后的批量恢复

        Args:
            session_id: 指定会话ID，如果为None则恢复所有活跃会话的消息
            batch_size: 批处理大小

        Returns:
            Dict[str, int]: 恢复统计信息 {"restored_sessions": 0, "restored_messages": 0}
        """
        stats = {"restored_sessions": 0, "restored_messages": 0}
        
        try:
            mongo_manager = await self._get_mongo_manager()
            redis_client = await self._get_redis_client()
            
            # 确定要恢复的会话列表
            sessions_to_restore = []
            if session_id:
                sessions_to_restore = [session_id]
            else:
                # 获取所有活跃会话
                sessions_collection = await mongo_manager.get_collection(self.sessions_collection)
                cursor = sessions_collection.find(
                    {"status": "available"}, 
                    {"session_id": 1}
                ).limit(batch_size)
                sessions = await cursor.to_list(length=None)
                sessions_to_restore = [s["session_id"] for s in sessions]
            
            logger.info(f"Starting restore operation for {len(sessions_to_restore)} sessions")
            
            # 逐个会话恢复消息
            messages_collection = await mongo_manager.get_collection(self.messages_collection)
            
            for sid in sessions_to_restore:
                try:
                    # 获取该会话的所有消息
                    cursor = messages_collection.find({"session_id": sid}).sort("timestamp", 1)
                    messages_docs = await cursor.to_list(length=None)
                    
                    if not messages_docs:
                        continue
                    
                    # 准备 Redis 数据
                    redis_key = f"chat:{sid}:messages"
                    redis_data = []
                    
                    for msg in messages_docs:
                        message_data = {
                            "role": msg["role"],
                            "content": msg["content"],
                            "timestamp": msg["timestamp"].isoformat(),
                            "metadata": msg.get("metadata", {})
                        }
                        redis_data.append(json.dumps(message_data))
                    
                    # 批量写入 Redis
                    if redis_data:
                        client = redis_client._ensure_initialized()
                        async with client.pipeline() as pipe:
                            pipe.delete(redis_key)  # 清空旧数据
                            for data in redis_data:
                                pipe.rpush(redis_key, data)
                            pipe.expire(redis_key, 7 * 24 * 3600)  # 7天过期
                            await pipe.execute()
                        
                        stats["restored_sessions"] += 1
                        stats["restored_messages"] += len(redis_data)
                        
                        logger.debug(f"Restored {len(redis_data)} messages for session {sid}")
                
                except Exception as session_error:
                    logger.error(f"Failed to restore session {sid}: {str(session_error)}")
                    continue
            
            logger.info(f"Restore operation completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to restore messages to Redis: {str(e)}")
            return stats

    async def cleanup_redis_cache(self, max_age_days: int = 30) -> Dict[str, int]:
        """
        清理过期的 Redis 缓存
        删除超过指定天数未活跃的会话消息缓存

        Args:
            max_age_days: 最大保留天数

        Returns:
            Dict[str, int]: 清理统计信息
        """
        stats = {"scanned_keys": 0, "cleaned_keys": 0}
        
        try:
            redis_client = await self._get_redis_client()
            mongo_manager = await self._get_mongo_manager()
            
            # 获取所有消息缓存键
            pattern = "chat:*:messages"
            keys = await redis_client.keys(pattern)
            stats["scanned_keys"] = len(keys)
            
            if not keys:
                return stats
            
            # 计算过期时间戳
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            sessions_collection = await mongo_manager.get_collection(self.sessions_collection)
            
            for key in keys:
                try:
                    # 从键名中提取 session_id
                    session_id = key.replace("chat:", "").replace(":messages", "")
                    
                    # 检查会话最后活动时间
                    session_doc = await sessions_collection.find_one(
                        {"session_id": session_id},
                        {"last_activity": 1}
                    )
                    
                    if not session_doc:
                        # 会话不存在，删除缓存
                        await redis_client.delete(key)
                        stats["cleaned_keys"] += 1
                        logger.debug(f"Cleaned orphaned cache key: {key}")
                        continue
                    
                    last_activity = session_doc.get("last_activity")
                    if last_activity and last_activity < cutoff_date:
                        # 会话过期，删除缓存
                        await redis_client.delete(key)
                        stats["cleaned_keys"] += 1
                        logger.debug(f"Cleaned expired cache key: {key}")
                
                except Exception as key_error:
                    logger.warning(f"Error processing cache key {key}: {str(key_error)}")
                    continue
            
            logger.info(f"Cache cleanup completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup Redis cache: {str(e)}")
            return stats

    async def get_message_by_id(self, message_id: str, user_id: str) -> Dict[str, Any]:
        """
        根据消息ID获取具体的消息记录，并验证用户权限
        
        Args:
            message_id: 消息ID (MongoDB的_id)
            user_id: 用户ID (用于权限验证)
            
        Returns:
            Dict[str, Any]: 消息详情，如果没有权限则返回None
        """
        try:
            from bson import ObjectId
            
            mongo_manager = await self._get_mongo_manager()
            messages_collection = await mongo_manager.get_collection(self.messages_collection)
            sessions_collection = await mongo_manager.get_collection(self.sessions_collection)
            
            # 根据消息ID查找消息
            try:
                message_obj_id = ObjectId(message_id)
            except Exception:
                logger.warning(f"Invalid message_id format: {message_id}")
                return None
                
            message = await messages_collection.find_one({"_id": message_obj_id})
            if not message:
                logger.warning(f"Message {message_id} not found")
                return None
            
            # 验证用户权限：检查消息所属会话是否属于当前用户
            session = await sessions_collection.find_one({
                "session_id": message["session_id"],
                "user_id": user_id
            })
            
            if not session:
                logger.warning(f"User {user_id} does not have permission to access message {message_id}")
                return None
            
            # 转换ObjectId为字符串并返回消息详情
            message["_id"] = str(message["_id"])
            message["message_id"] = message["_id"]
            
            return message
            
        except Exception as e:
            logger.error(f"Error getting message {message_id} for user {user_id}: {str(e)}")
            return None


# 全局聊天历史管理器实例
chat_history_manager = ChatHistoryManager()
