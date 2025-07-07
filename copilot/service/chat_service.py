"""
会话服务 - 处理会话相关的业务逻辑
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

from copilot.core.agent_coordinator import AgentCoordinator
from copilot.core.agent_manager import agent_manager
from copilot.core.execution_agent import ExecutionAgent
from copilot.core.session_manager import SessionInfo, session_manager
from copilot.core.thinking_agent import ThinkingAgent
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
    """会话服务 - 基于Agent管理器，为每个会话提供独立的Agent实例"""

    def __init__(self):
        """初始化ChatService"""
        self._chat_history_manager = None
        # 默认的Agent配置
        self.default_provider = None
        self.default_model_name = None
        self.default_tools = None
        self.default_llm_kwargs = {}

        # 上下文记忆配置
        self.default_context_memory_enabled = True
        self.default_max_history_messages = 10
        self.default_max_context_tokens = None

        # 思考模式配置
        self.thinking_mode_enabled = True
        self.thinking_provider = "deepseek"  # 思考Agent使用的提供商
        self.thinking_model = "deepseek-chat"  # 思考Agent使用的模型
        self.save_thinking_process = True

        # AgentCoordinator缓存
        self._coordinators = {}  # session_id -> AgentCoordinator

    @classmethod
    async def create(
        cls,
        provider: str = None,
        model_name: str = None,
        tools: List = None,
        context_memory_enabled: bool = True,
        max_history_messages: int = 10,
        max_context_tokens: int = None,
        thinking_mode_enabled: bool = True,
        thinking_provider: str = "deepseek",
        thinking_model: str = "deepseek-chat",
        save_thinking_process: bool = True,
        **llm_kwargs,
    ):
        """
        异步创建ChatService实例

        Args:
            provider: 默认LLM提供商 (deepseek, openai, claude, moonshot, zhipu, qwen, gemini)
            model_name: 默认模型名称
            tools: 默认工具列表
            context_memory_enabled: 是否启用上下文记忆
            max_history_messages: 最大历史消息数量
            max_context_tokens: 最大上下文token数量
            thinking_mode_enabled: 是否启用思考模式
            thinking_provider: 思考Agent的提供商
            thinking_model: 思考Agent的模型
            save_thinking_process: 是否保存思考过程
            **llm_kwargs: 传递给LLM的额外参数
        """
        service = cls()
        service.default_provider = provider
        service.default_model_name = model_name
        service.default_tools = tools or []
        service.default_llm_kwargs = llm_kwargs

        # 配置上下文记忆
        service.default_context_memory_enabled = context_memory_enabled
        service.default_max_history_messages = max_history_messages
        service.default_max_context_tokens = max_context_tokens

        # 配置思考模式
        service.thinking_mode_enabled = thinking_mode_enabled
        service.thinking_provider = thinking_provider
        service.thinking_model = thinking_model
        service.save_thinking_process = save_thinking_process

        logger.info(
            f"ChatService created with default provider: {provider}, model: {model_name}, "
            f"context_memory: {context_memory_enabled}, max_history: {max_history_messages}, max_tokens: {max_context_tokens}, "
            f"thinking_mode: {thinking_mode_enabled}, thinking_model: {thinking_provider}/{thinking_model}"
        )
        return service

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

    async def get_agent_for_session(
        self,
        session_id: str,
        provider: str = None,
        model_name: str = None,
        tools: List = None,
        context_memory_enabled: bool = None,
        max_history_messages: int = None,
        max_context_tokens: int = None,
        **llm_kwargs,
    ) -> ExecutionAgent:
        """
        获取会话专用的Agent实例 - 从AgentManager获取

        Args:
            session_id: 会话ID
            provider: LLM提供商，如果不提供则使用默认值
            model_name: 模型名称，如果不提供则使用默认值
            tools: 工具列表，如果不提供则使用默认值
            context_memory_enabled: 是否启用上下文记忆，如果不提供则使用默认值
            max_history_messages: 最大历史消息数量，如果不提供则使用默认值
            max_context_tokens: 最大上下文token数量，如果不提供则使用默认值
            **llm_kwargs: LLM参数

        Returns:
            ExecutionAgent: 会话专用的Agent实例
        """
        from copilot.core.agent_manager import agent_manager

        # 使用提供的参数或默认值
        final_provider = provider or self.default_provider
        final_model_name = model_name or self.default_model_name
        final_tools = tools or self.default_tools
        final_context_memory_enabled = context_memory_enabled if context_memory_enabled is not None else self.default_context_memory_enabled
        final_max_history_messages = max_history_messages if max_history_messages is not None else self.default_max_history_messages
        final_max_context_tokens = max_context_tokens if max_context_tokens is not None else self.default_max_context_tokens

        # 合并LLM参数
        final_llm_kwargs = {**self.default_llm_kwargs, **llm_kwargs}

        # 从AgentManager获取会话专用的Agent实例
        agent = await agent_manager.get_agent(
            session_id=session_id,
            provider=final_provider,
            model_name=final_model_name,
            tools=final_tools,
            context_memory_enabled=final_context_memory_enabled,
            max_history_messages=final_max_history_messages,
            max_context_tokens=final_max_context_tokens,
            **final_llm_kwargs,
        )

        logger.debug(
            f"Retrieved agent for session {session_id}: {final_provider}/{final_model_name}, "
            f"context_memory: {final_context_memory_enabled}, max_history: {final_max_history_messages}, max_tokens: {final_max_context_tokens}"
        )

        return agent

    async def get_coordinator_for_session(
        self,
        session_id: str,
        provider: str = None,
        model_name: str = None,
        tools: List = None,
        context_memory_enabled: bool = None,
        max_history_messages: int = None,
        max_context_tokens: int = None,
        **llm_kwargs,
    ) -> AgentCoordinator:
        """
        获取会话专用的AgentCoordinator实例

        Args:
            session_id: 会话ID
            provider: 执行Agent的LLM提供商
            model_name: 执行Agent的模型名称
            tools: 工具列表
            context_memory_enabled: 是否启用上下文记忆
            max_history_messages: 最大历史消息数量
            max_context_tokens: 最大上下文token数量
            **llm_kwargs: LLM参数

        Returns:
            AgentCoordinator: 会话专用的协调器实例
        """
        # 如果缓存中已有该会话的协调器，直接返回
        if session_id in self._coordinators:
            return self._coordinators[session_id]

        try:
            # 使用agent_manager的get_coordinator方法，它会自动加载MCP工具
            from copilot.core.agent_manager import agent_manager
            
            coordinator = await agent_manager.get_coordinator(
                session_id=session_id,
                thinking_provider=self.thinking_provider,
                thinking_model=self.thinking_model,
                execution_provider=provider or self.default_provider,
                execution_model=model_name or self.default_model_name,
                enable_thinking_mode=self.thinking_mode_enabled,
                save_thinking_process=self.save_thinking_process,
                **llm_kwargs,
            )

            # 缓存协调器
            self._coordinators[session_id] = coordinator

            logger.debug(f"Created AgentCoordinator for session {session_id} with MCP tools")
            return coordinator

        except Exception as e:
            logger.error(f"Failed to create AgentCoordinator for session {session_id}: {str(e)}")
            raise

    async def get_provider_info(self, session_id: str = None) -> Dict[str, Any]:
        """
        获取提供商信息

        Args:
            session_id: 会话ID（可选，用于获取特定会话的Agent信息）

        Returns:
            Dict[str, Any]: 提供商信息
        """
        if session_id:
            try:
                agent = await self.get_agent_for_session(session_id)
                return agent.get_provider_info()
            except Exception as e:
                logger.warning(f"Failed to get agent info for session {session_id}: {e}")

        # 返回默认配置信息
        from copilot.core.llm_factory import LLMFactory

        return {"provider": self.default_provider, "model": self.default_model_name, "available_providers": LLMFactory.get_available_providers()}

    async def switch_provider(self, session_id: str, provider: str, model_name: str = None, **llm_kwargs) -> bool:
        """
        为指定会话切换LLM提供商

        Args:
            session_id: 会话ID
            provider: 新的提供商
            model_name: 新的模型名称
            **llm_kwargs: 传递给LLM的额外参数

        Returns:
            bool: 是否切换成功
        """
        try:
            # 移除旧的Agent实例，下次调用时会用新配置创建
            await agent_manager.remove_agent(session_id)

            # 获取新的Agent实例（会使用新配置创建）
            agent = await self.get_agent_for_session(session_id=session_id, provider=provider, model_name=model_name, **llm_kwargs)

            logger.info(f"Successfully switched provider for session {session_id} to {provider}/{model_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to switch provider for session {session_id}: {e}")
            return False

    def get_available_providers(self) -> Dict[str, Any]:
        """
        获取可用的提供商信息

        Returns:
            Dict[str, Any]: 可用提供商信息
        """
        from copilot.utils.llm_manager import LLMProviderManager

        return LLMProviderManager.get_provider_recommendations()

    async def chat(self, session_id: str, message: str, attachments: List[dict] = None, enable_tools: bool = True, use_thinking_mode: bool = None):
        """
        智能聊天接口 - 支持思考-执行双Agent模式

        Args:
            session_id: 会话ID
            message: 用户消息
            attachments: 附件列表（包含图片等）
            enable_tools: 是否启用工具调用
            use_thinking_mode: 是否使用思考模式，None表示使用默认配置

        Yields:
            Dict: 响应数据，包含content、finished、error等字段
        """
        # 决定是否使用思考模式
        thinking_enabled = use_thinking_mode if use_thinking_mode is not None else self.thinking_mode_enabled

        if thinking_enabled:
            # 使用思考-执行双Agent模式
            async for chunk in self._chat_with_thinking(session_id, message, attachments, enable_tools):
                yield chunk
        else:
            # 使用传统单Agent模式
            async for chunk in self._chat_legacy(session_id, message, attachments, enable_tools):
                yield chunk

    async def _chat_with_thinking(self, session_id: str, message: str, attachments: List[dict] = None, enable_tools: bool = True):
        """
        使用思考-执行双Agent模式的聊天

        Args:
            session_id: 会话ID
            message: 用户消息
            attachments: 附件列表
            enable_tools: 是否启用工具调用

        Yields:
            Dict: 响应数据
        """
        try:
            # 1. 验证会话
            session_info = await self._validate_session(session_id)

            # 2. 预处理输入
            images = self._extract_images(attachments)

            # 3. 获取协调器
            coordinator = await self.get_coordinator_for_session(session_id)

            # 4. 构建上下文信息
            context = {"session_id": session_id, "user_id": session_info.user_id, "window_id": session_info.window_id, "attachments": attachments}

            # 5. 使用协调器处理
            full_response = ""
            token_usage = None
            has_thinking = False
            has_execution = False

            async for chunk in coordinator.process_user_input(
                user_input=message, session_id=session_id, thread_id=session_info.thread_id, images=images, enable_tools=enable_tools, context=context
            ):
                if chunk:
                    chunk_type = chunk.get("type", "content")
                    chunk_phase = chunk.get("phase", "unknown")
                    chunk_content = chunk.get("content", "")

                    # 传递所有chunk信息给前端
                    yield chunk

                    # 记录阶段状态
                    if chunk_phase == "thinking":
                        has_thinking = True
                    elif chunk_phase == "execution":
                        has_execution = True

                    # 收集执行阶段的内容用于保存
                    if chunk_phase == "execution" and chunk_content:
                        full_response += chunk_content

                    # 处理token使用信息
                    if chunk_type == "tool_result" and chunk.get("token_usage"):
                        token_usage = chunk.get("token_usage")

            # 6. 保存对话（只保存执行阶段的内容）
            if full_response:
                # 如果协调器没有提供token信息，手动估算
                if not token_usage:
                    execution_agent = coordinator.execution_agent
                    token_usage = execution_agent._estimate_token_usage(message, full_response)

                message_ids = await self._save_conversation(session_id, message, full_response, token_usage, attachments)

                # 返回最终统计信息
                yield {
                    "finished": True,
                    "token_usage": token_usage,
                    "total_tokens": token_usage.get("total_tokens", 0),
                    "message_ids": message_ids,
                    "thinking_enabled": True,
                    "phases_completed": {"thinking": has_thinking, "execution": has_execution},
                }

            # 7. 更新会话活动时间
            await session_manager.get_session(session_info.session_id)

        except Exception as e:
            logger.error(f"Error in thinking chat for session {session_id}: {str(e)}")
            yield {"error": f"思考模式处理出错: {str(e)}", "type": "error"}

    async def _chat_legacy(self, session_id: str, message: str, attachments: List[dict] = None, enable_tools: bool = True):
        """
        传统单Agent模式的聊天（保持原有逻辑）

        Args:
            session_id: 会话ID
            message: 用户消息
            attachments: 附件列表
            enable_tools: 是否启用工具调用

        Yields:
            Dict: 响应数据
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
        """内部流式聊天方法 - 使用会话专用的Agent实例"""
        try:
            full_response = ""

            # 获取该会话专用的Agent实例
            agent = await self.get_agent_for_session(session_info.session_id)

            logger.debug(f"Using agent for session {session_info.session_id}: {agent.provider}/{agent.model_name}")

            # 使用会话专用Agent进行流式聊天
            async for chunk in agent.chat(
                message=message,
                thread_id=session_info.thread_id,
                session_id=session_info.session_id,
                images=images if images else None,
                enable_tools=enable_tools,
            ):
                if chunk:
                    # 处理字典格式的chunk
                    if isinstance(chunk, dict):
                        chunk_content = chunk.get("content", "")
                        chunk_type = chunk.get("type", "content")

                        if chunk_content:
                            # 传递完整的chunk信息，包括类型
                            yield {"content": chunk_content, "type": chunk_type}
                            full_response += chunk_content
                    else:
                        # 兼容旧格式（字符串）
                        yield {"content": chunk, "type": "content"}
                        full_response += chunk

            # 计算token使用量并保存对话
            if full_response:
                token_usage = agent._estimate_token_usage(message, full_response)
                message_ids = await self._save_conversation(session_info.session_id, message, full_response, token_usage, attachments)

                # 返回最终统计信息
                yield {"finished": True, "token_usage": token_usage, "total_tokens": token_usage.get("total_tokens", 0), "message_ids": message_ids}

            # 更新会话活动时间
            await session_manager.get_session(session_info.session_id)

        except Exception as e:
            logger.error(f"Error in stream chat for session {session_info.session_id}: {str(e)}")
            yield {"error": "处理请求时出现错误", "type": "error"}

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

    async def reload_agent(self, session_id: str = None) -> bool:
        """
        重新加载 agent（重新创建以获取最新的 MCP 工具）

        当 MCP server 连接/断开时，由 mcp_router 调用此方法来刷新 agent

        Args:
            session_id: 指定会话ID，如果为None则重新加载所有Agent实例

        Returns:
            bool: 是否成功重新创建 agent
        """
        try:
            logger.info(f"Reloading agents to refresh MCP tools for session: {session_id or 'all'}")

            if session_id:
                # 重新加载指定会话的Agent
                success = await agent_manager.remove_agent(session_id)
                if success:
                    logger.info(f"Successfully removed agent for session {session_id}, will recreate on next request")
                    return True
                else:
                    logger.warning(f"No agent found to remove for session {session_id}")
                    return True  # 没有Agent也算成功，下次请求时会创建新的
            else:
                # 重新加载所有Agent实例
                stats_before = agent_manager.get_agent_stats()

                # 清除所有Agent实例，它们会在下次请求时重新创建
                # 这里我们通过重启Agent管理器来实现
                await agent_manager.stop()
                await agent_manager.start()

                stats_after = agent_manager.get_agent_stats()

                logger.info(f"Successfully reloaded all agents: {stats_before['total_agents']} -> {stats_after['total_agents']}")
                return True

        except Exception as e:
            logger.error(f"Failed to reload agent for session {session_id}: {str(e)}")
            return False

    def configure_context_memory(self, enabled: bool = True, max_history_messages: int = 10, max_context_tokens: int = None):
        """
        配置全局上下文记忆设置

        Args:
            enabled: 是否启用上下文记忆
            max_history_messages: 最大历史消息数量
            max_context_tokens: 最大上下文token数量
        """
        self.default_context_memory_enabled = enabled
        self.default_max_history_messages = max_history_messages

        if max_context_tokens is not None:
            self.default_max_context_tokens = max_context_tokens

        logger.info(f"Global context memory configured: enabled={enabled}, max_history={max_history_messages}, max_tokens={max_context_tokens}")

    def get_context_memory_config(self) -> Dict[str, Any]:
        """
        获取上下文记忆配置信息

        Returns:
            Dict[str, Any]: 记忆配置信息
        """
        return {
            "context_memory_enabled": self.default_context_memory_enabled,
            "max_history_messages": self.default_max_history_messages,
            "max_context_tokens": self.default_max_context_tokens,
        }

    async def get_session_context_memory_info(self, session_id: str) -> Dict[str, Any]:
        """
        获取指定会话的上下文记忆信息

        Args:
            session_id: 会话ID

        Returns:
            Dict[str, Any]: 包含记忆配置和历史消息统计的信息
        """
        try:
            # 获取Agent实例的记忆配置
            agent = await self.get_agent_for_session(session_id)
            agent_memory_info = agent.get_context_memory_info()

            # 获取实际的历史消息数量
            history_messages = await self.chat_history_manager.get_session_messages(session_id, limit=100)

            return {**agent_memory_info, "actual_history_count": len(history_messages), "session_id": session_id}

        except Exception as e:
            logger.error(f"Error getting context memory info for session {session_id}: {str(e)}")
            return {"context_memory_enabled": False, "max_history_messages": 0, "actual_history_count": 0, "error": str(e)}

    # ========== 思考模式相关方法 ==========

    def configure_thinking_mode(
        self, enabled: bool = True, thinking_provider: str = "deepseek", thinking_model: str = "deepseek-chat", save_thinking_process: bool = True
    ):
        """
        配置全局思考模式设置

        Args:
            enabled: 是否启用思考模式
            thinking_provider: 思考Agent的提供商
            thinking_model: 思考Agent的模型
            save_thinking_process: 是否保存思考过程
        """
        self.thinking_mode_enabled = enabled
        self.thinking_provider = thinking_provider
        self.thinking_model = thinking_model
        self.save_thinking_process = save_thinking_process

        # 清除现有的协调器缓存，强制重新创建
        self._coordinators.clear()

        logger.info(
            f"Global thinking mode configured: enabled={enabled}, "
            f"model={thinking_provider}/{thinking_model}, save_process={save_thinking_process}"
        )

    def get_thinking_mode_config(self) -> Dict[str, Any]:
        """
        获取思考模式配置信息

        Returns:
            Dict[str, Any]: 思考模式配置信息
        """
        return {
            "thinking_mode_enabled": self.thinking_mode_enabled,
            "thinking_provider": self.thinking_provider,
            "thinking_model": self.thinking_model,
            "save_thinking_process": self.save_thinking_process,
            "cached_coordinators": len(self._coordinators),
        }

    async def get_session_thinking_info(self, session_id: str) -> Dict[str, Any]:
        """
        获取指定会话的思考模式信息

        Args:
            session_id: 会话ID

        Returns:
            Dict[str, Any]: 包含思考配置和历史信息
        """
        try:
            info = {
                "session_id": session_id,
                "thinking_mode_enabled": self.thinking_mode_enabled,
                "thinking_provider": self.thinking_provider,
                "thinking_model": self.thinking_model,
                "save_thinking_process": self.save_thinking_process,
                "has_coordinator": session_id in self._coordinators,
                "thinking_history_count": 0,
                "latest_thinking": None,
            }

            # 如果已有协调器，获取思考历史
            if session_id in self._coordinators:
                coordinator = self._coordinators[session_id]
                thinking_history = coordinator.get_thinking_history(session_id)
                info["thinking_history_count"] = len(thinking_history)

                if thinking_history:
                    latest = thinking_history[-1]
                    info["latest_thinking"] = {
                        "user_intent": latest.user_intent,
                        "estimated_complexity": latest.estimated_complexity,
                        "execution_plan_steps": len(latest.execution_plan),
                        "timestamp": latest.timestamp.isoformat() if latest.timestamp else None,
                    }

                # 获取协调器统计信息
                coordinator_stats = coordinator.get_coordinator_stats()
                info["coordinator_stats"] = coordinator_stats

            return info

        except Exception as e:
            logger.error(f"Error getting thinking info for session {session_id}: {str(e)}")
            return {"session_id": session_id, "thinking_mode_enabled": False, "error": str(e)}

    async def get_thinking_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取会话的思考历史

        Args:
            session_id: 会话ID
            limit: 返回的历史记录数量限制

        Returns:
            List[Dict[str, Any]]: 思考历史记录
        """
        try:
            if session_id not in self._coordinators:
                return []

            coordinator = self._coordinators[session_id]
            thinking_history = coordinator.get_thinking_history(session_id)

            # 转换为可序列化的格式
            result = []
            for thinking in thinking_history[-limit:]:
                result.append(
                    {
                        "user_intent": thinking.user_intent,
                        "problem_analysis": thinking.problem_analysis,
                        "execution_plan": [
                            {
                                "step_id": step.step_id,
                                "description": step.description,
                                "reasoning": step.reasoning,
                                "expected_tools": step.expected_tools,
                                "parameters": step.parameters,
                                "priority": step.priority,
                                "dependencies": step.dependencies,
                            }
                            for step in thinking.execution_plan
                        ],
                        "estimated_complexity": thinking.estimated_complexity,
                        "suggested_model": thinking.suggested_model,
                        "context_requirements": thinking.context_requirements,
                        "timestamp": thinking.timestamp.isoformat() if thinking.timestamp else None,
                    }
                )

            return result

        except Exception as e:
            logger.error(f"Error getting thinking history for session {session_id}: {str(e)}")
            return []

    async def clear_thinking_history(self, session_id: str) -> bool:
        """
        清除会话的思考历史

        Args:
            session_id: 会话ID

        Returns:
            bool: 是否成功清除
        """
        try:
            if session_id in self._coordinators:
                coordinator = self._coordinators[session_id]
                coordinator.clear_thinking_history(session_id)
                logger.info(f"Cleared thinking history for session {session_id}")
                return True
            else:
                logger.warning(f"No coordinator found for session {session_id}")
                return True  # 没有协调器也算成功

        except Exception as e:
            logger.error(f"Error clearing thinking history for session {session_id}: {str(e)}")
            return False

    async def refine_and_retry(self, session_id: str, feedback: str, original_input: str, attachments: List[dict] = None, enable_tools: bool = True):
        """
        根据反馈优化计划并重试执行

        Args:
            session_id: 会话ID
            feedback: 用户反馈或错误信息
            original_input: 原始用户输入
            attachments: 附件列表
            enable_tools: 是否启用工具

        Yields:
            Dict: 响应数据
        """
        try:
            # 验证会话
            session_info = await self._validate_session(session_id)

            # 获取协调器
            if session_id not in self._coordinators:
                yield {"error": "该会话尚未使用思考模式，无法进行优化重试", "type": "error"}
                return

            coordinator = self._coordinators[session_id]
            images = self._extract_images(attachments)

            # 使用协调器进行优化重试
            full_response = ""
            token_usage = None

            async for chunk in coordinator.refine_and_retry(
                session_id=session_id,
                feedback=feedback,
                original_input=original_input,
                thread_id=session_info.thread_id,
                images=images,
                enable_tools=enable_tools,
            ):
                if chunk:
                    chunk_type = chunk.get("type", "content")
                    chunk_phase = chunk.get("phase", "unknown")
                    chunk_content = chunk.get("content", "")

                    # 传递所有chunk信息给前端
                    yield chunk

                    # 收集执行阶段的内容用于保存
                    if chunk_phase in ["retry_execution"] and chunk_content:
                        full_response += chunk_content

                    # 处理token使用信息
                    if chunk_type == "tool_result" and chunk.get("token_usage"):
                        token_usage = chunk.get("token_usage")

            # 保存重试后的对话
            if full_response:
                # 如果协调器没有提供token信息，手动估算
                if not token_usage:
                    execution_agent = coordinator.execution_agent
                    token_usage = execution_agent._estimate_token_usage(original_input, full_response)

                message_ids = await self._save_conversation(session_id, original_input, full_response, token_usage, attachments)

                # 返回最终统计信息
                yield {
                    "finished": True,
                    "token_usage": token_usage,
                    "total_tokens": token_usage.get("total_tokens", 0),
                    "message_ids": message_ids,
                    "refined_execution": True,
                }

        except Exception as e:
            logger.error(f"Error in refine and retry for session {session_id}: {str(e)}")
            yield {"error": f"优化重试出错: {str(e)}", "type": "error"}

    async def reload_coordinator(self, session_id: str = None) -> bool:
        """
        重新加载协调器（当配置变更时）

        Args:
            session_id: 指定会话ID，如果为None则重新加载所有协调器

        Returns:
            bool: 是否成功重新加载
        """
        try:
            if session_id:
                # 重新加载指定会话的协调器
                if session_id in self._coordinators:
                    del self._coordinators[session_id]
                    logger.info(f"Removed coordinator for session {session_id}, will recreate on next request")
                return True
            else:
                # 重新加载所有协调器
                coordinator_count = len(self._coordinators)
                self._coordinators.clear()
                logger.info(f"Cleared all {coordinator_count} coordinators, will recreate on next request")
                return True

        except Exception as e:
            logger.error(f"Failed to reload coordinator for session {session_id}: {str(e)}")
            return False
