"""
核心Agent实现 - 支持多LLM、多模态、MCP工具、流式输出和权限管理
"""

import asyncio
import traceback
from typing import Any, AsyncGenerator, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from copilot.core.chat_stream_handler import ChatStreamHandler
from copilot.core.mcp_tool_wrapper import MCPToolWrapper
from copilot.core.multimodal_handler import MultimodalHandler
from copilot.utils.llm_manager import LLMFactory
from copilot.utils.logger import logger
from copilot.utils.token_calculator import TokenCalculator


class ExecutionAgent:
    """核心Agent - 支持多个LLM提供商和MCP工具"""

    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        tools: List = None,
        mcp_tools: List = None,
        context_memory_enabled: bool = True,
        max_history_messages: int = 10,
        max_context_tokens: int = None,
        **llm_kwargs,
    ):
        """
        初始化Agent

        Args:
            provider: LLM提供商 (deepseek, openai, claude, moonshot, zhipu, qwen, gemini)
            model_name: 模型名称
            tools: 传统工具列表
            mcp_tools: MCP工具列表（从外部传入）
            context_memory_enabled: 是否启用上下文记忆
            max_history_messages: 最大历史消息数量（用于控制上下文长度）
            max_context_tokens: 最大上下文token数量（如果不提供则使用默认值）
            **llm_kwargs: 传递给LLM的额外参数
        """
        self.provider = provider
        self.model_name = model_name
        self.tools = tools or []
        self.mcp_tools = mcp_tools or []
        self.llm_kwargs = llm_kwargs
        self.context_memory_enabled = context_memory_enabled
        self.max_history_messages = max_history_messages

        # 设置最大上下文token数量（根据不同模型设置不同的默认值）
        self.max_context_tokens = max_context_tokens or self._get_default_max_tokens(provider, model_name)

        # 延迟初始化历史管理器
        self._chat_history_manager = None

        self.memory = MemorySaver()
        self.enable_mcp_tools = True  # 启用MCP工具支持

        # 初始化LLM
        try:
            self.llm = LLMFactory.create_llm(provider=provider, model=model_name, **llm_kwargs)
            logger.info(f"ExecutionAgent initialized with provider: {provider or 'default'}, model: {model_name or 'default'}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {str(e)}")
            raise

        # 初始化处理器
        self.multimodal_handler = MultimodalHandler(self.provider)

        # 合并MCP工具和传统工具
        all_tools = self._merge_tools()

        # 创建LangGraph agent
        self.graph = create_react_agent(
            self.llm, tools=all_tools, prompt="You are a helpful assistant. Please respond in Chinese.", checkpointer=self.memory
        )

        # 初始化聊天流处理器
        self.chat_stream_handler = ChatStreamHandler(self.graph)

        # 当前会话ID（用于MCP工具）
        self._current_session_id = None

        logger.info(f"ExecutionAgent initialized with max_context_tokens: {self.max_context_tokens}")

    @property
    def chat_history_manager(self):
        """延迟初始化聊天历史管理器"""
        if self._chat_history_manager is None:
            from copilot.service.history_service import chat_history_manager

            self._chat_history_manager = chat_history_manager
        return self._chat_history_manager

    def _merge_tools(self) -> List:
        """合并传统工具和MCP工具"""
        merged_tools = self.tools.copy()

        if self.enable_mcp_tools and self.mcp_tools:
            merged_tools.extend(self.mcp_tools)
            logger.info(f"Added {len(self.mcp_tools)} MCP tools to agent")

        return merged_tools

    @classmethod
    async def create_with_mcp_tools(
        cls,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        tools: List = None,
        context_memory_enabled: bool = True,
        max_history_messages: int = 10,
        max_context_tokens: int = None,
        **llm_kwargs,
    ):
        """
        异步创建Agent实例，自动加载MCP工具

        Args:
            provider: LLM提供商
            model_name: 模型名称
            tools: 传统工具列表
            context_memory_enabled: 是否启用上下文记忆
            max_history_messages: 最大历史消息数量
            max_context_tokens: 最大上下文token数量
            **llm_kwargs: 传递给LLM的额外参数

        Returns:
            ExecutionAgent: 配置好的Agent实例
        """
        # 获取可用的MCP工具
        mcp_tools = await MCPToolWrapper.get_mcp_tools()

        logger.info(
            f"Creating ExecutionAgent with provider: {provider}, model: {model_name}, tools: {len(tools) if tools else 0}, mcp_tools: {len(mcp_tools)}, context_memory: {context_memory_enabled}"
        )

        # 创建Agent实例
        return cls(
            provider=provider,
            model_name=model_name,
            tools=tools,
            mcp_tools=mcp_tools,
            context_memory_enabled=context_memory_enabled,
            max_history_messages=max_history_messages,
            max_context_tokens=max_context_tokens,
            **llm_kwargs,
        )

    async def chat(
        self,
        message: str,
        thread_id: Optional[str] = None,
        session_id: Optional[str] = None,
        images: Optional[List] = None,
        enable_tools: bool = True,
    ):
        """
        统一的流式聊天接口，支持多模态、工具调用和权限确认

        Args:
            message: 用户消息
            thread_id: 线程ID（用于会话管理）
            session_id: 会话ID（用于MCP工具权限管理）
            images: 图片列表（多模态输入）
            enable_tools: 是否启用工具调用

        Yields:
            str: 响应片段
        """
        # 设置当前会话ID，供MCP工具使用
        self._current_session_id = session_id

        try:
            # 导入agent_state_manager和AgentExecutionState
            from copilot.core.agent_state_manager import AgentExecutionState, agent_state_manager

            # 创建或获取执行上下文
            if session_id:
                context = agent_state_manager.get_execution_context(session_id)
                if not context:
                    context = agent_state_manager.create_execution_context(session_id, thread_id)
                context.update_state(AgentExecutionState.RUNNING)

            # 1. 准备配置
            config = self.chat_stream_handler.prepare_config(thread_id, session_id)

            # 2. 构建输入消息
            inputs = await self._build_inputs(message, images, session_id, enable_tools)

            # 3. 使用流式输出
            async for chunk in self.chat_stream_handler.handle_stream_with_permission(inputs, config, session_id):
                yield chunk

        finally:
            # 清理会话ID
            self._current_session_id = None

    async def _build_inputs(self, message: str, images: Optional[List], session_id: Optional[str], enable_tools: bool) -> Dict:
        """
        构建输入消息，包含历史对话上下文

        Args:
            message: 当前用户消息
            images: 图片列表（多模态输入）
            session_id: 会话ID（用于加载历史记录）
            enable_tools: 是否启用工具调用

        Returns:
            Dict: 包含完整对话上下文的消息输入
        """
        # 构建当前消息内容 - 使用多模态处理器
        current_content = await self.multimodal_handler.build_multimodal_content(message, images)

        # 构建消息列表
        messages = []

        # 如果启用上下文记忆且有session_id，加载历史对话
        if self.context_memory_enabled and session_id:
            try:
                # 从历史服务加载对话记录
                history_messages = await self._load_conversation_history(session_id)

                # 将历史记录转换为LLM格式
                for hist_msg in history_messages:
                    messages.append({"role": hist_msg.role, "content": hist_msg.content})

                logger.debug(f"Loaded {len(history_messages)} history messages for session {session_id}")

            except Exception as e:
                logger.warning(f"Failed to load conversation history for session {session_id}: {str(e)}")
                # 如果加载历史失败，继续处理当前消息

        # 添加当前用户消息
        messages.append({"role": "user", "content": current_content})

        logger.debug(f"Built input with {len(messages)} messages (including {len(messages)-1} history messages)")

        return {"messages": messages}

    async def _load_conversation_history(self, session_id: str):
        """
        加载会话的对话历史，支持智能截断和token优化

        Args:
            session_id: 会话ID

        Returns:
            List[ChatHistoryMessage]: 优化后的历史消息列表
        """
        try:
            # 获取历史消息，获取比需要更多的消息用于智能选择
            raw_history_messages = await self.chat_history_manager.get_session_messages(
                session_id=session_id, limit=self.max_history_messages * 2, offset=0  # 获取更多消息用于优化选择
            )

            if not raw_history_messages:
                return []

            # 按时间顺序排序（确保对话顺序正确）
            raw_history_messages.sort(key=lambda x: x.timestamp if x.timestamp else "")

            # 进行智能截断和优化
            optimized_messages = await self._optimize_context_messages(raw_history_messages)

            logger.debug(
                f"Loaded and optimized {len(optimized_messages)} messages from {len(raw_history_messages)} raw messages for session {session_id}"
            )

            return optimized_messages

        except Exception as e:
            logger.error(f"Error loading conversation history: {str(e)}")
            return []

    async def _optimize_context_messages(self, messages):
        """
        智能优化上下文消息，防止token过多

        Args:
            messages: 原始历史消息列表

        Returns:
            List[ChatHistoryMessage]: 优化后的消息列表
        """
        if not messages:
            return []

        try:
            # 如果消息数量在限制内，直接检查token数量
            if len(messages) <= self.max_history_messages:
                # 估算token数量
                total_tokens = self._estimate_messages_tokens(messages)
                if total_tokens <= self.max_context_tokens * 0.7:  # 保留30%空间给当前对话
                    return messages

            # 需要优化：使用多种策略
            optimized = await self._apply_context_optimization_strategies(messages)

            return optimized

        except Exception as e:
            logger.warning(f"Context optimization failed: {str(e)}")
            # 如果优化失败，返回最近的消息
            return messages[-self.max_history_messages :] if len(messages) > self.max_history_messages else messages

    async def _apply_context_optimization_strategies(self, messages):
        """
        应用多种上下文优化策略

        策略优先级：
        1. 保留最近的重要对话
        2. 移除重复或相似内容
        3. 压缩长消息
        4. 保持对话连贯性
        """
        if not messages:
            return []

        # 策略1：首先按数量限制
        recent_messages = messages[-self.max_history_messages :]

        # 策略2：检查token数量，如果仍然过多则进一步优化
        estimated_tokens = self._estimate_messages_tokens(recent_messages)
        target_tokens = int(self.max_context_tokens * 0.7)  # 保留30%空间

        if estimated_tokens <= target_tokens:
            return recent_messages

        # 策略3：如果仍然太多，逐步减少，但保持对话的连贯性
        optimized_messages = []
        current_tokens = 0

        # 从最新的消息开始，向前添加
        for msg in reversed(recent_messages):
            msg_tokens = self._estimate_single_message_tokens(msg)

            if current_tokens + msg_tokens <= target_tokens:
                optimized_messages.insert(0, msg)  # 插入到开头保持顺序
                current_tokens += msg_tokens
            else:
                # 如果单条消息就超过限制，尝试截断长消息
                if len(optimized_messages) == 0 and len(msg.content) > 200:
                    truncated_content = msg.content[:200] + "...[消息被截断]"
                    truncated_msg = type(msg)(
                        role=msg.role, content=truncated_content, timestamp=msg.timestamp, message_id=msg.message_id, metadata=msg.metadata
                    )
                    optimized_messages.insert(0, truncated_msg)
                break

        logger.debug(
            f"Context optimization: {len(messages)} -> {len(recent_messages)} -> {len(optimized_messages)} messages, "
            f"estimated tokens: {estimated_tokens} -> {current_tokens}"
        )

        return optimized_messages

    def _estimate_messages_tokens(self, messages) -> int:
        """估算消息列表的总token数量"""
        if not messages:
            return 0

        total_tokens = 0
        for msg in messages:
            total_tokens += self._estimate_single_message_tokens(msg)

        return total_tokens

    def _estimate_single_message_tokens(self, message) -> int:
        """估算单条消息的token数量"""
        try:
            # 获取当前模型的key用于token计算
            model_key = TokenCalculator.get_model_key(self.provider, self.model_name)

            # 使用TokenCalculator估算
            usage = TokenCalculator.calculate_usage(message.content, "", model_key)
            return usage.prompt_tokens

        except Exception as e:
            logger.warning(f"Token estimation failed for message: {str(e)}")
            # 简单估算：中文约2个字符=1个token，英文约4个字符=1个token
            content_length = len(message.content)
            # 保守估算，假设平均2.5个字符=1个token
            return max(1, content_length // 2)

    def _get_default_max_tokens(self, provider: str, model_name: str) -> int:
        """根据不同的模型获取默认的最大token数量"""
        # 常见模型的上下文窗口大小
        model_limits = {
            # DeepSeek
            "deepseek-chat": 32768,
            "deepseek-coder": 16384,
        }

        # 尝试精确匹配模型名
        if model_name and model_name in model_limits:
            max_tokens = model_limits[model_name]
        else:
            # 尝试模糊匹配
            max_tokens = 8192  # 默认值
            if model_name:
                model_lower = model_name.lower()
                for model_key, limit in model_limits.items():
                    if model_key.lower() in model_lower or model_lower in model_key.lower():
                        max_tokens = limit
                        break

        # 为了安全起见，使用模型限制的60%作为实际限制
        actual_limit = int(max_tokens * 0.6)

        logger.info(f"Set max_context_tokens to {actual_limit} for model {provider}/{model_name} (model limit: {max_tokens})")

        return actual_limit

    def configure_context_memory(self, enabled: bool = True, max_history_messages: int = 10, max_context_tokens: int = None):
        """
        配置上下文记忆功能

        Args:
            enabled: 是否启用上下文记忆
            max_history_messages: 最大历史消息数量
            max_context_tokens: 最大上下文token数量
        """
        self.context_memory_enabled = enabled
        self.max_history_messages = max_history_messages

        if max_context_tokens is not None:
            self.max_context_tokens = max_context_tokens

        logger.info(f"Context memory configured: enabled={enabled}, max_history={max_history_messages}, max_tokens={self.max_context_tokens}")

    def get_context_memory_info(self) -> Dict[str, Any]:
        """
        获取上下文记忆配置信息

        Returns:
            Dict[str, Any]: 记忆配置信息
        """
        return {
            "context_memory_enabled": self.context_memory_enabled,
            "max_history_messages": self.max_history_messages,
            "max_context_tokens": self.max_context_tokens,
        }

    def get_provider_info(self) -> Dict[str, Any]:
        """
        获取当前使用的提供商信息

        Returns:
            Dict[str, Any]: 提供商信息
        """
        return {"provider": self.provider, "model": self.model_name, "available_providers": LLMFactory.get_available_providers()}

    def switch_provider(self, provider: str, model_name: Optional[str] = None, **llm_kwargs) -> bool:
        """
        切换LLM提供商

        Args:
            provider: 新的提供商
            model_name: 新的模型名称
            **llm_kwargs: 传递给LLM的额外参数

        Returns:
            bool: 是否切换成功
        """
        try:
            # 验证提供商是否可用
            if not LLMFactory.validate_provider(provider):
                logger.error(f"Provider {provider} is not available (missing API key)")
                return False

            # 创建新的LLM实例
            new_llm = LLMFactory.create_llm(provider=provider, model=model_name, **llm_kwargs)

            # 更新实例变量
            self.provider = provider
            self.model_name = model_name
            self.llm_kwargs = llm_kwargs
            self.llm = new_llm

            # 更新多模态处理器
            self.multimodal_handler = MultimodalHandler(self.provider)

            # 重新创建agent - 注意要使用合并后的工具
            all_tools = self._merge_tools()
            self.graph = create_react_agent(
                self.llm, tools=all_tools, prompt="You are a helpful assistant. Please respond in Chinese.", checkpointer=self.memory
            )

            # 重新初始化聊天流处理器
            self.chat_stream_handler = ChatStreamHandler(self.graph)

            logger.info(f"Successfully switched to provider: {provider}, model: {model_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to switch provider: {str(e)}")
            return False

    def _estimate_token_usage(self, prompt: str, completion: str) -> Dict[str, int]:
        """
        估算token使用量

        Args:
            prompt: 用户输入
            completion: 模型回复

        Returns:
            Dict[str, int]: token使用量统计
        """
        try:
            # 获取当前模型的key
            model_key = TokenCalculator.get_model_key(self.provider, self.model_name)

            # 计算token使用量
            usage = TokenCalculator.calculate_usage(prompt, completion, model_key)

            return usage.to_dict()

        except Exception as e:
            logger.warning(f"Token estimation failed: {str(e)}")
            # 返回默认值，避免系统崩溃
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def get_token_calculator(self) -> TokenCalculator:
        """获取token计算器实例"""
        return TokenCalculator()

    async def update_mcp_tools(self, mcp_tools: List) -> bool:
        """
        动态更新Agent的MCP工具

        Args:
            mcp_tools: 新的MCP工具列表

        Returns:
            bool: 是否更新成功
        """
        try:
            # 更新MCP工具列表
            self.mcp_tools = mcp_tools

            # 重新合并所有工具
            all_tools = self._merge_tools()

            # 重新创建LangGraph agent
            self.graph = create_react_agent(
                self.llm, tools=all_tools, prompt="You are a helpful assistant. Please respond in Chinese.", checkpointer=self.memory
            )

            # 重新初始化聊天流处理器
            self.chat_stream_handler = ChatStreamHandler(self.graph)

            logger.info(f"Successfully updated Agent with {len(mcp_tools)} MCP tools")
            return True

        except Exception as e:
            logger.error(f"Failed to update MCP tools: {e}")
            return False

    async def reload_mcp_tools_from_servers(self, server_ids: List[str]) -> bool:
        """
        从指定服务器重新加载MCP工具

        Args:
            server_ids: MCP服务器ID列表

        Returns:
            bool: 是否重新加载成功
        """
        try:
            # 获取指定服务器的MCP工具
            mcp_tools = await MCPToolWrapper.get_mcp_tools_for_servers(server_ids)

            # 更新工具
            return await self.update_mcp_tools(mcp_tools)

        except Exception as e:
            logger.error(f"Failed to reload MCP tools from servers {server_ids}: {e}")
            return False
