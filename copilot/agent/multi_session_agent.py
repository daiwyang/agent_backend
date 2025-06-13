"""
多轮对话Agent
支持基于会话的多轮对话管理
"""

import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from dataclasses import dataclass

from copilot.agent.session_manager import session_manager, SessionInfo
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


class MultiSessionAgent:
    """多会话Agent"""

    def __init__(self, model_name: str = "deepseek:deepseek-chat", tools: List = None):
        self.model_name = model_name
        self.tools = tools or []

        # 创建带有记忆的agent
        self.memory = MemorySaver()
        self.graph = create_react_agent(
            model_name, tools=self.tools, prompt="You are a helpful assistant. Please respond in Chinese.", checkpointer=self.memory
        )
        
        # 延迟导入避免循环依赖
        self._chat_history_manager = None

        logger.info(f"MultiSessionAgent initialized with model: {model_name}")
    
    @property
    def chat_history_manager(self):
        """延迟初始化聊天历史管理器"""
        if self._chat_history_manager is None:
            from copilot.agent.chat_history_manager import chat_history_manager
            self._chat_history_manager = chat_history_manager
        return self._chat_history_manager

    async def create_session(self, user_id: str, window_id: str = None) -> str:
        """
        创建新的对话会话

        Args:
            user_id: 用户ID
            window_id: 窗口ID（可选）

        Returns:
            session_id: 会话ID
        """
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

        # 保存用户消息到数据库
        try:
            await self.chat_history_manager.save_message(
                session_id=session_id,
                role="user",
                content=message,
                metadata={"timestamp": asyncio.get_event_loop().time()}
            )
        except Exception as e:
            logger.warning(f"Failed to save user message to database: {str(e)}")

        # 构建LangGraph配置
        config = {"configurable": {"thread_id": session_info.thread_id}}

        # 构建输入消息
        inputs = {"messages": [{"role": "user", "content": message}]}

        # 获取响应
        response_messages = []
        try:
            for chunk in self.graph.stream(inputs, config=config, stream_mode="updates"):
                if "agent" in chunk:
                    for msg in chunk["agent"]["messages"]:
                        if msg.content:
                            response_messages.append(ChatMessage(role="assistant", content=msg.content))
        except Exception as e:
            logger.error(f"Error in chat for session {session_id}: {str(e)}")
            response_messages.append(ChatMessage(role="assistant", content="抱歉，处理您的请求时出现了错误。"))

        # 保存助手响应到数据库
        for response_msg in response_messages:
            try:
                await self.chat_history_manager.save_message(
                    session_id=session_id,
                    role="assistant",
                    content=response_msg.content,
                    metadata={"timestamp": asyncio.get_event_loop().time()}
                )
            except Exception as e:
                logger.warning(f"Failed to save assistant message to database: {str(e)}")

        # 更新会话活动时间
        await session_manager.get_session(session_id)

        return ChatResponse(session_id=session_id, messages=response_messages, context=session_info.context)

    async def chat_stream(self, session_id: str, message: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式聊天，实时返回响应片段

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

        config = {"configurable": {"thread_id": session_info.thread_id}}
        inputs = {"messages": [{"role": "user", "content": message}]}

        try:
            # 使用流式模式获取响应
            full_response = ""
            async for chunk in self.graph.astream(inputs, config=config, stream_mode="values"):
                if "messages" in chunk:
                    # 获取最新的消息
                    messages = chunk["messages"]
                    if messages:
                        last_message = messages[-1]
                        # 只处理助手的消息
                        if hasattr(last_message, 'type') and last_message.type == "ai" and last_message.content:
                            new_content = last_message.content
                            if new_content != full_response:
                                # 如果是完整的新响应，逐字符流式输出
                                if len(full_response) == 0:
                                    # 模拟逐字符流式输出
                                    for i in range(0, len(new_content), 3):  # 每次发送3个字符
                                        chunk_text = new_content[i:i+3]
                                        yield {"content": chunk_text}
                                        await asyncio.sleep(0.05)  # 模拟网络延迟
                                    full_response = new_content
                                else:
                                    # 发送新增的内容
                                    new_part = new_content[len(full_response):]
                                    full_response = new_content
                                    yield {"content": new_part}
                                    await asyncio.sleep(0.01)
                        elif hasattr(last_message, 'content') and last_message.content:
                            # 兼容不同的消息格式
                            new_content = str(last_message.content)
                            if new_content != full_response:
                                # 如果是完整的新响应，逐字符流式输出
                                if len(full_response) == 0:
                                    # 模拟逐字符流式输出
                                    for i in range(0, len(new_content), 3):  # 每次发送3个字符
                                        chunk_text = new_content[i:i+3]
                                        yield {"content": chunk_text}
                                        await asyncio.sleep(0.05)  # 模拟网络延迟
                                    full_response = new_content
                                else:
                                    # 发送新增的内容
                                    new_part = new_content[len(full_response):]
                                    full_response = new_content
                                    yield {"content": new_part}
                                    await asyncio.sleep(0.01)
                            
            # 更新会话活动时间
            await session_manager.get_session(session_id)
            
        except Exception as e:
            logger.error(f"Error in chat_stream for session {session_id}: {str(e)}")
            yield {"error": "处理请求时出现错误"}

    async def get_chat_history(self, session_id: str, from_db: bool = False) -> List[ChatMessage]:
        """
        获取聊天历史

        Args:
            session_id: 会话ID
            from_db: 是否从数据库获取历史记录（默认从LangGraph内存获取）

        Returns:
            List[ChatMessage]: 聊天历史
        """
        if from_db:
            # 从数据库获取完整历史
            try:
                db_messages = await self.chat_history_manager.get_session_messages(session_id)
                return [
                    ChatMessage(
                        role=msg.role,
                        content=msg.content,
                        timestamp=msg.timestamp.isoformat() if msg.timestamp else None
                    )
                    for msg in db_messages
                ]
            except Exception as e:
                logger.error(f"Error getting chat history from database for session {session_id}: {str(e)}")
                return []
        else:
            # 从LangGraph内存获取当前会话历史
            session_info = await session_manager.get_session(session_id)
            if not session_info:
                return []

            config = {"configurable": {"thread_id": session_info.thread_id}}

            try:
                state = self.graph.get_state(config)
                messages = state.values.get("messages", [])

                chat_messages = []
                for msg in messages:
                    chat_messages.append(
                        ChatMessage(
                            role=msg.type if hasattr(msg, "type") else "unknown", 
                            content=str(msg.content) if hasattr(msg, "content") else str(msg)
                        )
                    )

                return chat_messages
            except Exception as e:
                logger.error(f"Error getting chat history from memory for session {session_id}: {str(e)}")
                return []

    async def get_user_sessions(self, user_id: str) -> List[SessionInfo]:
        """
        获取用户的所有活跃会话

        Args:
            user_id: 用户ID

        Returns:
            List[SessionInfo]: 用户的所有活跃会话
        """
        return await session_manager.get_user_sessions(user_id)

    async def delete_session(self, session_id: str):
        """
        删除会话

        Args:
            session_id: 会话ID
        """
        await session_manager.delete_session(session_id)
        logger.info(f"Deleted session {session_id}")

    async def update_session_context(self, session_id: str, context: Dict[str, Any]):
        """
        更新会话上下文

        Args:
            session_id: 会话ID
            context: 要更新的上下文信息
        """
        await session_manager.update_session_context(session_id, context)

    async def get_user_chat_history(self, user_id: str) -> List:
        """
        获取用户的所有聊天历史

        Args:
            user_id: 用户ID

        Returns:
            List: 用户的所有会话历史
        """
        try:
            return await self.chat_history_manager.get_user_sessions(user_id)
        except Exception as e:
            logger.error(f"Error getting user chat history for {user_id}: {str(e)}")
            return []

    async def search_chat_history(self, user_id: str, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        搜索用户的聊天历史

        Args:
            user_id: 用户ID
            query: 搜索关键词
            limit: 返回数量限制

        Returns:
            List[Dict]: 搜索结果
        """
        try:
            return await self.chat_history_manager.search_messages(user_id, query, limit)
        except Exception as e:
            logger.error(f"Error searching chat history for {user_id}: {str(e)}")
            return []

    async def get_chat_stats(self, user_id: str = None) -> Dict[str, Any]:
        """
        获取聊天统计信息

        Args:
            user_id: 用户ID（可选）

        Returns:
            Dict: 统计信息
        """
        try:
            return await self.chat_history_manager.get_stats(user_id)
        except Exception as e:
            logger.error(f"Error getting chat stats: {str(e)}")
            return {}
