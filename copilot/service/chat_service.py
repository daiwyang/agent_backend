"""
会话服务 - 处理会话相关的业务逻辑
"""

import asyncio
from typing import List, Dict, Any, AsyncGenerator
from dataclasses import dataclass

from copilot.core.agent import CoreAgent
from copilot.core.session_manager import session_manager, SessionInfo
from copilot.utils.logger import logger


@dataclass
class ChatMessage:
    """聊天消息"""

    role: str  # "user" 或 "assistant"
    content: str
    timestamp: str = None


@dataclass
class ChatResponse:
    """聊天响应"""

    session_id: str
    messages: List[ChatMessage]
    context: Dict[str, Any]


class ChatService:
    """会话服务 - 组合CoreAgent和会话管理"""

    def __init__(self, model_name: str = "deepseek-chat", tools: List = None):
        self.core_agent = CoreAgent(model_name, tools)
        self._chat_history_manager = None

    @property
    def chat_history_manager(self):
        """延迟初始化聊天历史管理器"""
        if self._chat_history_manager is None:
            from copilot.service.history_service import chat_history_manager

            self._chat_history_manager = chat_history_manager
        return self._chat_history_manager

    async def create_session(self, user_id: str, window_id: str = None) -> str:
        """创建新的对话会话"""
        return await session_manager.create_session(user_id, window_id)

    async def chat(self, session_id: str, message: str) -> ChatResponse:
        """
        发送消息并获取回复

        Args:
            session_id: 会话ID
            message: 用户消息

        Returns:
            ChatResponse: 聊天响应
        """
        session_info = await session_manager.get_session(session_id)
        if not session_info:
            raise ValueError(f"Session {session_id} not found or expired")

        # 使用核心Agent进行聊天
        response_content = await self.core_agent.chat(session_info.thread_id, message)

        # 保存消息到数据库
        await self._save_messages(session_id, message, response_content)

        # 更新会话活动时间
        await session_manager.get_session(session_id)

        response_message = ChatMessage(role="assistant", content=response_content)
        return ChatResponse(session_id=session_id, messages=[response_message], context=session_info.context)

    async def chat_stream(self, session_id: str, message: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式聊天

        Args:
            session_id: 会话ID
            message: 用户消息

        Yields:
            Dict: 响应片段
        """
        session_info = await session_manager.get_session(session_id)
        if not session_info:
            yield {"error": f"Session {session_id} not found or expired"}
            return

        try:
            full_response = ""

            # 使用核心Agent进行流式聊天
            async for content in self.core_agent.chat_stream(session_info.thread_id, message):
                if content:
                    yield {"content": content}
                    full_response += content

            # 保存完整对话到数据库
            if full_response:
                await self._save_messages(session_id, message, full_response)

            # 更新会话活动时间
            await session_manager.get_session(session_id)

        except Exception as e:
            logger.error(f"Error in chat_stream for session {session_id}: {str(e)}")
            yield {"error": "处理请求时出现错误"}

    async def _save_messages(self, session_id: str, user_message: str, assistant_message: str):
        """保存消息到数据库"""
        try:
            timestamp = asyncio.get_event_loop().time()

            await self.chat_history_manager.save_message(session_id=session_id, role="user", content=user_message, metadata={"timestamp": timestamp})

            await self.chat_history_manager.save_message(
                session_id=session_id, role="assistant", content=assistant_message, metadata={"timestamp": timestamp}
            )
        except Exception as e:
            logger.warning(f"Failed to save messages to database: {str(e)}")

    # 会话管理方法
    async def get_user_sessions(self, user_id: str) -> List[SessionInfo]:
        """获取用户的所有活跃会话"""
        return await session_manager.get_user_sessions(user_id)

    async def delete_session(self, session_id: str):
        """删除会话"""
        await session_manager.delete_session(session_id)

    async def update_session_context(self, session_id: str, context: Dict[str, Any]):
        """更新会话上下文"""
        await session_manager.update_session_context(session_id, context)

    # 历史记录方法
    async def get_chat_history(self, session_id: str, from_db: bool = False) -> List[ChatMessage]:
        """获取聊天历史"""
        if from_db:
            try:
                db_messages = await self.chat_history_manager.get_session_messages(session_id)
                return [
                    ChatMessage(role=msg.role, content=msg.content, timestamp=msg.timestamp.isoformat() if msg.timestamp else None)
                    for msg in db_messages
                ]
            except Exception as e:
                logger.error(f"Error getting chat history from database: {str(e)}")
                return []
        else:
            # 从LangGraph内存获取
            session_info = await session_manager.get_session(session_id)
            if not session_info:
                return []

            try:
                config = {"configurable": {"thread_id": session_info.thread_id}}
                state = self.core_agent.graph.get_state(config)
                messages = state.values.get("messages", [])

                return [
                    ChatMessage(
                        role=msg.type if hasattr(msg, "type") else "unknown", content=str(msg.content) if hasattr(msg, "content") else str(msg)
                    )
                    for msg in messages
                ]
            except Exception as e:
                logger.error(f"Error getting chat history from memory: {str(e)}")
                return []
