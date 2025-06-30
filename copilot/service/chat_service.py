"""
会话服务 - 处理会话相关的业务逻辑
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List

from copilot.core.agent import CoreAgent
from copilot.core.session_manager import SessionInfo, session_manager
from copilot.utils.logger import logger
from copilot.utils.token_calculator import TokenCalculator, TokenUsage


@dataclass
class ChatMessage:
    """聊天消息"""

    role: str  # "user" 或 "assistant"
    content: str
    message_id: str = None  # 消息ID（MongoDB的_id）
    timestamp: str = None
    token_count: int = 0  # 该消息的token数量
    total_tokens: int = None  # 总token数量（仅assistant消息）


@dataclass
class ChatResponse:
    """聊天响应"""

    session_id: str
    messages: List[ChatMessage]
    context: Dict[str, Any]


class ChatService:
    """会话服务 - 组合CoreAgent和会话管理，支持多个LLM提供商"""

    def __init__(self, provider: str = None, model_name: str = None, tools: List = None, **llm_kwargs):
        """
        初始化ChatService

        Args:
            provider: LLM提供商 (deepseek, openai, claude, moonshot, zhipu, qwen, gemini)
            model_name: 模型名称
            tools: 工具列表
            **llm_kwargs: 传递给LLM的额外参数
        """
        self.core_agent = CoreAgent(provider=provider, model_name=model_name, tools=tools, **llm_kwargs)
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

    def get_provider_info(self) -> Dict[str, Any]:
        """
        获取当前使用的提供商信息

        Returns:
            Dict[str, Any]: 提供商信息
        """
        return self.core_agent.get_provider_info()

    def switch_provider(self, provider: str, model_name: str = None, **llm_kwargs) -> bool:
        """
        切换LLM提供商

        Args:
            provider: 新的提供商
            model_name: 新的模型名称
            **llm_kwargs: 传递给LLM的额外参数

        Returns:
            bool: 是否切换成功
        """
        return self.core_agent.switch_provider(provider, model_name, **llm_kwargs)

    def get_available_providers(self) -> Dict[str, Any]:
        """
        获取可用的提供商信息

        Returns:
            Dict[str, Any]: 可用提供商信息
        """
        from copilot.utils.llm_manager import LLMProviderManager

        return LLMProviderManager.get_provider_recommendations()

    async def chat(self, session_id: str, message: str, attachments: List[dict] = None, enable_tools: bool = True):
        """
        统一的流式聊天接口，支持多模态、工具调用

        Args:
            session_id: 会话ID
            message: 用户消息
            attachments: 附件列表（包含图片等）
            enable_tools: 是否启用工具调用

        Yields:
            Dict: 响应数据，包含content、finished、error等字段
        """
        # 1. 验证会话
        session_info = await self._validate_session(session_id)

        # 2. 预处理输入
        images = self._extract_images(attachments)

        # 3. 使用流式处理
        async for chunk in self._chat_stream_internal(session_info, message, images, enable_tools, attachments):
            yield chunk

    async def _validate_session(self, session_id: str) -> SessionInfo:
        """验证会话有效性"""
        session_info = await session_manager.get_session(session_id)
        if not session_info:
            raise ValueError(f"Session {session_id} not found or expired")
        return session_info

    def _extract_images(self, attachments: List[dict] = None) -> List[dict]:
        """从附件中提取图片"""
        if not attachments:
            return []
        return [att for att in attachments if att.get("type") == "image"]

    async def _chat_stream_internal(
        self, session_info: SessionInfo, message: str, images: List[dict], enable_tools: bool, attachments: List[dict] = None
    ):
        """内部流式聊天方法"""
        try:
            full_response = ""

            # 使用核心Agent进行流式聊天
            async for content in self.core_agent.chat(
                message=message,
                thread_id=session_info.thread_id,
                session_id=session_info.session_id,
                images=images if images else None,
                enable_tools=enable_tools,
            ):
                if content:
                    yield {"content": content}
                    full_response += content

            # 计算token使用量并保存对话
            if full_response:
                token_usage = self.core_agent._estimate_token_usage(message, full_response)
                message_ids = await self._save_conversation(session_info.session_id, message, full_response, token_usage, attachments)

                # 返回最终统计信息
                yield {"finished": True, "token_usage": token_usage, "total_tokens": token_usage.get("total_tokens", 0), "message_ids": message_ids}

            # 更新会话活动时间
            await session_manager.get_session(session_info.session_id)

        except Exception as e:
            logger.error(f"Error in stream chat for session {session_info.session_id}: {str(e)}")
            yield {"error": "处理请求时出现错误"}

    async def _save_conversation(
        self, session_id: str, user_message: str, assistant_message: str, token_usage: Dict[str, int] = None, attachments: List[dict] = None
    ):
        """
        统一的对话保存方法

        Args:
            session_id: 会话ID
            user_message: 用户消息
            assistant_message: 助手回复
            token_usage: token使用量统计
            attachments: 附件列表（可选，用于多模态）

        Returns:
            Dict[str, str]: 包含用户消息和助手消息的message_id
        """
        try:
            timestamp = datetime.now().isoformat()

            # 安全地提取token信息
            usage = TokenCalculator.safe_extract_tokens(token_usage)

            # 保存用户消息
            user_metadata = {
                "timestamp": timestamp,
                "token_count": usage.prompt_tokens,
            }

            # 如果有附件，添加附件信息
            if attachments:
                user_metadata.update({"attachments": attachments, "is_multimodal": True})

            user_message_id = await self.chat_history_manager.save_message(
                session_id=session_id, role="user", content=user_message, metadata=user_metadata
            )

            # 保存助手消息
            assistant_metadata = {
                "timestamp": timestamp,
                "token_count": usage.completion_tokens,
                "token_usage": usage.to_dict(),
                "total_tokens": usage.total_tokens,
            }

            # 如果是多模态回复，添加标识
            if attachments:
                assistant_metadata["is_multimodal_response"] = True

            assistant_message_id = await self.chat_history_manager.save_message(
                session_id=session_id, role="assistant", content=assistant_message, metadata=assistant_metadata
            )

            logger.debug(f"Saved conversation with token usage: {usage.to_dict()}")

            # 返回message_id
            return {"user_message_id": user_message_id, "assistant_message_id": assistant_message_id}

        except Exception as e:
            logger.warning(f"Failed to save conversation to database: {str(e)}")
            raise

    async def _save_messages(self, session_id: str, user_message: str, assistant_message: str, token_usage: Dict[str, int] = None):
        """保存消息到数据库，包含 token 统计信息"""
        # 调用统一的保存方法，保持向后兼容
        return await self._save_conversation(session_id, user_message, assistant_message, token_usage)

    async def _save_multimodal_messages(
        self, session_id: str, user_message: str, assistant_message: str, attachments: List[dict] = None, token_usage: Dict[str, int] = None
    ):
        """保存多模态消息，包含附件信息和token统计"""
        # 调用统一的保存方法，保持向后兼容
        return await self._save_conversation(session_id, user_message, assistant_message, token_usage, attachments)

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
    async def get_chat_history(self, session_id: str, limit: int = 100, offset: int = 0) -> List[ChatMessage]:
        """
        获取聊天历史
        实现策略：优先从 Redis 获取，Redis 中没有则从 MongoDB 获取并自动恢复到 Redis

        Args:
            session_id: 会话ID
            limit: 返回消息数量限制
            offset: 偏移量

        Returns:
            List[ChatMessage]: 聊天消息列表，包含token统计信息
        """
        try:
            messages = await self.chat_history_manager.get_session_messages(session_id=session_id, limit=limit, offset=offset)

            chat_messages = []
            for msg in messages:
                # 安全地从 metadata 中提取 token 信息
                token_count = 0
                total_tokens = 0

                if msg.metadata:
                    token_count = msg.metadata.get("token_count", 0)
                    total_tokens = msg.metadata.get("total_tokens", 0)

                chat_message = ChatMessage(
                    message_id=msg.message_id,  # 包含消息ID
                    role=msg.role,
                    content=msg.content,
                    timestamp=msg.timestamp.isoformat() if msg.timestamp else None,
                    token_count=token_count,
                    total_tokens=total_tokens if msg.role == "assistant" else None,
                )
                chat_messages.append(chat_message)

            return chat_messages

        except Exception as e:
            logger.error(f"Error getting chat history for session {session_id}: {str(e)}")
            return []

    async def restore_chat_history_to_cache(self, session_id: str = None) -> Dict[str, int]:
        """
        恢复聊天历史到缓存
        用于系统维护或缓存失效后的数据恢复

        Args:
            session_id: 指定会话ID，如果为None则恢复所有活跃会话

        Returns:
            Dict[str, int]: 恢复统计信息
        """
        try:
            return await self.chat_history_manager.restore_messages_to_redis(session_id)
        except Exception as e:
            logger.error(f"Error restoring chat history to cache: {str(e)}")
            return {"restored_sessions": 0, "restored_messages": 0}

    async def cleanup_chat_cache(self, max_age_days: int = 30) -> Dict[str, int]:
        """
        清理过期的聊天缓存

        Args:
            max_age_days: 最大保留天数

        Returns:
            Dict[str, int]: 清理统计信息
        """
        try:
            return await self.chat_history_manager.cleanup_redis_cache(max_age_days)
        except Exception as e:
            logger.error(f"Error cleaning up chat cache: {str(e)}")
            return {"scanned_keys": 0, "cleaned_keys": 0}

    async def get_session_token_stats(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话的 token 使用统计

        Args:
            session_id: 会话ID

        Returns:
            Dict[str, Any]: token 使用统计信息
        """
        try:
            messages = await self.chat_history_manager.get_session_messages(session_id)

            stats = {
                "session_id": session_id,
                "total_messages": len(messages),
                "user_messages": 0,
                "assistant_messages": 0,
                "total_tokens": 0,
                "user_tokens": 0,
                "assistant_tokens": 0,
                "conversations": 0,  # 对话轮次
                "average_tokens_per_conversation": 0,
            }

            conversation_tokens = []
            current_conversation_tokens = 0

            for msg in messages:
                if msg.metadata:
                    token_count = msg.metadata.get("token_count", 0)
                    stats["total_tokens"] += token_count

                    if msg.role == "user":
                        stats["user_messages"] += 1
                        stats["user_tokens"] += token_count
                        current_conversation_tokens = token_count  # 开始新对话
                    elif msg.role == "assistant":
                        stats["assistant_messages"] += 1
                        stats["assistant_tokens"] += token_count
                        current_conversation_tokens += token_count
                        conversation_tokens.append(current_conversation_tokens)
                        stats["conversations"] += 1

            # 计算平均值
            if stats["conversations"] > 0:
                stats["average_tokens_per_conversation"] = sum(conversation_tokens) / len(conversation_tokens)

            return stats

        except Exception as e:
            logger.error(f"Error getting token stats for session {session_id}: {str(e)}")
            return {"error": str(e)}

    async def get_user_token_stats(self, user_id: str, days: int = 7) -> Dict[str, Any]:
        """
        获取用户的 token 使用统计

        Args:
            user_id: 用户ID
            days: 统计天数

        Returns:
            Dict[str, Any]: 用户 token 使用统计
        """
        try:
            from datetime import datetime, timedelta

            # 获取用户的会话
            sessions = await self.get_user_sessions(user_id)

            stats = {
                "user_id": user_id,
                "days": days,
                "total_sessions": len(sessions),
                "active_sessions": 0,
                "total_tokens": 0,
                "user_tokens": 0,
                "assistant_tokens": 0,
                "total_conversations": 0,
                "sessions_detail": [],
            }

            cutoff_date = datetime.now() - timedelta(days=days)

            for session in sessions:
                if session.last_activity >= cutoff_date:
                    stats["active_sessions"] += 1

                    session_stats = await self.get_session_token_stats(session.session_id)
                    if "error" not in session_stats:
                        stats["total_tokens"] += session_stats["total_tokens"]
                        stats["user_tokens"] += session_stats["user_tokens"]
                        stats["assistant_tokens"] += session_stats["assistant_tokens"]
                        stats["total_conversations"] += session_stats["conversations"]

                        stats["sessions_detail"].append(
                            {
                                "session_id": session.session_id,
                                "last_activity": session.last_activity.isoformat(),
                                "tokens": session_stats["total_tokens"],
                                "conversations": session_stats["conversations"],
                            }
                        )

            return stats

        except Exception as e:
            logger.error(f"Error getting user token stats for user {user_id}: {str(e)}")
            return {"error": str(e)}

    async def get_message_by_id(self, message_id: str, user_id: str) -> Dict[str, Any]:
        """
        根据消息ID获取具体的消息记录

        Args:
            message_id: 消息ID (MongoDB的_id)
            user_id: 用户ID (用于权限验证)

        Returns:
            Dict[str, Any]: 消息详情，如果没有权限则返回None
        """
        try:
            return await self.chat_history_manager.get_message_by_id(message_id, user_id)
        except Exception as e:
            logger.error(f"Error getting message {message_id} for user {user_id}: {str(e)}")
            return None
