"""
核心Agent - 支持多个LLM提供商和MCP工具
"""

from typing import Any, AsyncGenerator, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from copilot.core.chat_stream_handler import ChatStreamHandler
from copilot.core.llm_factory import LLMFactory
from copilot.core.mcp_tool_wrapper import MCPToolWrapper
from copilot.core.multimodal_handler import MultimodalHandler
from copilot.core.tool_result_processor import ToolResultProcessor
from copilot.utils.logger import logger
from copilot.utils.token_calculator import TokenCalculator


class CoreAgent:
    """核心Agent - 支持多个LLM提供商和MCP工具"""

    def __init__(self, provider: Optional[str] = None, model_name: Optional[str] = None, tools: List = None, mcp_tools: List = None, **llm_kwargs):
        """
        初始化Agent

        Args:
            provider: LLM提供商 (deepseek, openai, claude, moonshot, zhipu, qwen, gemini)
            model_name: 模型名称
            tools: 传统工具列表
            mcp_tools: MCP工具列表（从外部传入）
            **llm_kwargs: 传递给LLM的额外参数
        """
        self.provider = provider
        self.model_name = model_name
        self.tools = tools or []
        self.mcp_tools = mcp_tools or []
        self.llm_kwargs = llm_kwargs
        self.memory = MemorySaver()
        self.enable_mcp_tools = True  # 启用MCP工具支持

        # 初始化LLM
        try:
            self.llm = LLMFactory.create_llm(provider=provider, model=model_name, **llm_kwargs)
            logger.info(f"CoreAgent initialized with provider: {provider or 'default'}, model: {model_name or 'default'}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {str(e)}")
            raise

        # 初始化处理器
        self.multimodal_handler = MultimodalHandler(self.provider)
        self.tool_result_processor = ToolResultProcessor()

        # 合并MCP工具和传统工具
        all_tools = self._merge_tools()

        # 创建LangGraph agent
        self.graph = create_react_agent(
            self.llm, tools=all_tools, prompt="You are a helpful assistant. Please respond in Chinese.", checkpointer=self.memory
        )

        # 初始化聊天流处理器
        self.chat_stream_handler = ChatStreamHandler(self.graph, self.tool_result_processor)

    def _merge_tools(self) -> List:
        """合并传统工具和MCP工具"""
        merged_tools = self.tools.copy()

        if self.enable_mcp_tools and self.mcp_tools:
            merged_tools.extend(self.mcp_tools)
            logger.info(f"Added {len(self.mcp_tools)} MCP tools to agent")

        return merged_tools

    @classmethod
    async def create_with_mcp_tools(cls, provider: Optional[str] = None, model_name: Optional[str] = None, tools: List = None, **llm_kwargs):
        """
        异步创建带有MCP工具的Agent

        Args:
            provider: LLM提供商
            model_name: 模型名称
            tools: 传统工具列表
            **llm_kwargs: 传递给LLM的额外参数

        Returns:
            CoreAgent: 配置了MCP工具的Agent实例
        """
        # 获取MCP工具
        mcp_tools = await MCPToolWrapper.get_mcp_tools()

        logger.info(
            f"Creating CoreAgent with provider: {provider}, model: {model_name}, tools: {len(tools) if tools else 0}, mcp_tools: {len(mcp_tools)}"
        )

        # 创建Agent实例
        return cls(provider=provider, model_name=model_name, tools=tools, mcp_tools=mcp_tools, **llm_kwargs)

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
        """构建输入消息"""
        # 构建消息内容 - 使用多模态处理器
        content = await self.multimodal_handler.build_multimodal_content(message, images)

        logger.debug(f"Prepared input content: {content}")

        return {"messages": [{"role": "user", "content": content}]}

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
            self.chat_stream_handler = ChatStreamHandler(self.graph, self.tool_result_processor)

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
            self.chat_stream_handler = ChatStreamHandler(self.graph, self.tool_result_processor)

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
