"""
聊天历史管理器
负责对话历史的持久化存储和检索
"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from copilot.utils.mongo_client import get_mongo_manager
from copilot.utils.logger import logger


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
    status: str = "active"  # active, archived, deleted


class ChatHistoryManager:
    """聊天历史管理器"""

    def __init__(self):
        self.sessions_collection = "chat_sessions"
        self.messages_collection = "chat_messages"
        self._mongo_manager = None

    async def _get_mongo_manager(self):
        """获取MongoDB连接管理器"""
        if self._mongo_manager is None:
            self._mongo_manager = await get_mongo_manager()
        return self._mongo_manager

    async def save_message(self, session_id: str, role: str, content: str, metadata: Dict[str, Any] = None):
        """
        保存单条消息到数据库

        Args:
            session_id: 会话ID
            role: 消息角色 ("user" 或 "assistant")
            content: 消息内容
            metadata: 消息元数据
        """
        try:
            mongo_manager = await self._get_mongo_manager()

            # 保存消息
            messages_collection = await mongo_manager.get_collection(self.messages_collection)
            message_doc = {"session_id": session_id, "role": role, "content": content, "timestamp": datetime.now(), "metadata": metadata or {}}

            await messages_collection.insert_one(message_doc)

            # 更新会话的最后活动时间
            sessions_collection = await mongo_manager.get_collection(self.sessions_collection)
            await sessions_collection.update_one({"session_id": session_id}, {"$set": {"last_activity": datetime.now()}}, upsert=False)

            logger.debug(f"Saved message for session {session_id}")

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
                "status": "active",
            }

            await sessions_collection.insert_one(session_doc)
            logger.info(f"Saved session {session_id} to database")

        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {str(e)}")
            raise

    async def get_session_messages(self, session_id: str, limit: int = 100, offset: int = 0) -> List[ChatHistoryMessage]:
        """
        获取会话的消息历史

        Args:
            session_id: 会话ID
            limit: 返回消息数量限制
            offset: 偏移量

        Returns:
            List[ChatHistoryMessage]: 消息列表
        """
        try:
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

    async def get_user_sessions(self, user_id: str, status: str = "active", limit: int = 50) -> List[ChatSession]:
        """
        获取用户的会话列表

        Args:
            user_id: 用户ID
            status: 会话状态过滤
            limit: 返回数量限制

        Returns:
            List[ChatSession]: 会话列表
        """
        try:
            mongo_manager = await self._get_mongo_manager()
            sessions_collection = await mongo_manager.get_collection(self.sessions_collection)

            cursor = sessions_collection.find({"user_id": user_id, "status": status}).sort("last_activity", -1)  # 按最后活动时间降序

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
                    status=session.get("status", "active"),
                )
                result.append(chat_session)

            return result

        except Exception as e:
            logger.error(f"Failed to get sessions for user {user_id}: {str(e)}")
            return []

    async def archive_session(self, session_id: str):
        """
        归档会话（标记为已归档但不删除）

        Args:
            session_id: 会话ID
        """
        try:
            mongo_manager = await self._get_mongo_manager()
            sessions_collection = await mongo_manager.get_collection(self.sessions_collection)

            result = await sessions_collection.update_one({"session_id": session_id}, {"$set": {"status": "archived", "archived_at": datetime.now()}})

            if result.modified_count > 0:
                logger.info(f"Archived session {session_id}")
            else:
                logger.warning(f"Session {session_id} not found for archiving")

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
                # 逻辑删除
                result = await sessions_collection.update_one(
                    {"session_id": session_id}, {"$set": {"status": "deleted", "deleted_at": datetime.now()}}
                )

                if result.modified_count > 0:
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


# 全局聊天历史管理器实例
chat_history_manager = ChatHistoryManager()
