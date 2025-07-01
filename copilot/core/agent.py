"""
核心Agent - 支持多个LLM提供商和MCP工具
"""

from typing import Any, AsyncGenerator, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from copilot.core.llm_factory import LLMFactory
from copilot.mcp_client.mcp_server_manager import mcp_server_manager
from copilot.utils.logger import logger
from copilot.utils.token_calculator import TokenCalculator


class CoreAgent:
    """核心Agent - 支持多个LLM提供商和MCP工具"""

    def __init__(self, provider: Optional[str] = None, model_name: Optional[str] = None, tools: List = None, **llm_kwargs):
        """
        初始化Agent

        Args:
            provider: LLM提供商 (deepseek, openai, claude, moonshot, zhipu, qwen, gemini)
            model_name: 模型名称
            tools: 工具列表
            **llm_kwargs: 传递给LLM的额外参数
        """
        self.provider = provider
        self.model_name = model_name
        self.tools = tools or []
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

        # 合并MCP工具和传统工具
        all_tools = self._merge_tools()

        # 创建LangGraph agent
        self.graph = create_react_agent(
            self.llm, tools=all_tools, prompt="You are a helpful assistant. Please respond in Chinese.", checkpointer=self.memory
        )

    def _merge_tools(self) -> List:
        """合并传统工具和MCP工具"""
        merged_tools = self.tools.copy()

        if self.enable_mcp_tools:
            # 添加MCP工具包装器
            mcp_tools = self._create_mcp_tool_wrappers()
            merged_tools.extend(mcp_tools)

        return merged_tools

    def _create_mcp_tool_wrappers(self) -> List:
        """创建MCP工具的LangChain包装器"""
        wrappers = []

        # 获取所有可用的MCP工具
        available_tools = mcp_server_manager.get_available_tools()

        for tool_info in available_tools:
            # 创建工具函数
            async def mcp_tool_func(session_id: str, **kwargs):
                return await mcp_server_manager.call_tool(
                    tool_name=tool_info["full_name"], parameters=kwargs, session_id=session_id, require_permission=True
                )

            # 这里需要创建LangChain工具包装器
            # 具体实现取决于LangChain的工具接口
            # wrappers.append(create_langchain_tool(tool_info, mcp_tool_func))

        return wrappers

    async def chat(
        self,
        message: str,
        thread_id: Optional[str] = None,
        session_id: Optional[str] = None,
        images: Optional[List] = None,
        enable_tools: bool = True,
    ):
        """
        统一的流式聊天接口，支持多模态、工具调用

        Args:
            message: 用户消息
            thread_id: 线程ID（用于会话管理）
            session_id: 会话ID（用于MCP工具权限管理）
            images: 图片列表（多模态输入）
            enable_tools: 是否启用工具调用

        Yields:
            str: 响应片段
        """
        # 1. 准备配置
        config = self._prepare_config(thread_id, session_id)

        # 2. 构建输入消息
        inputs = await self._build_inputs(message, images, session_id, enable_tools)

        # 3. 使用流式输出
        async for chunk in self._chat_stream_internal(inputs, config):
            yield chunk

    def _prepare_config(self, thread_id: Optional[str], session_id: Optional[str]) -> Dict:
        """准备LangGraph配置"""
        config = {}
        if thread_id:
            config["configurable"] = {"thread_id": thread_id}
        if session_id:
            config.setdefault("configurable", {})["session_id"] = session_id
        return config

    async def _build_inputs(self, message: str, images: Optional[List], session_id: Optional[str], enable_tools: bool) -> Dict:
        """构建输入消息"""
        # 处理MCP工具的session_id注入
        if session_id and enable_tools and self.enable_mcp_tools:
            message = f"[SESSION_ID:{session_id}] {message}"

        # 构建消息内容
        if images and self._supports_multimodal():
            # 多模态输入
            content = [{"type": "text", "text": message}]
            for img in images:
                processed_img = await self._preprocess_image(img)
                content.append(processed_img)
        else:
            # 纯文本输入
            content = message

        return {"messages": [{"role": "user", "content": content}]}

    def _supports_multimodal(self) -> bool:
        """检查当前提供商是否支持多模态"""
        return self.provider in ["openai", "claude", "gemini"]

    async def _chat_stream_internal(self, inputs: Dict, config: Dict) -> AsyncGenerator[str, None]:
        """内部流式聊天方法"""
        try:
            # 尝试使用流式输出
            async for chunk in self.graph.astream(inputs, config=config, stream_mode="messages"):
                if chunk and len(chunk) >= 2:
                    message_chunk, _ = chunk
                    if hasattr(message_chunk, "content") and message_chunk.content:
                        yield str(message_chunk.content)
            return
        except Exception as e:
            logger.warning(f"Streaming failed: {str(e)}, falling back to chunk mode")

        # 回退到分块模式
        try:
            async for chunk in self.graph.astream(inputs, config=config, stream_mode="updates"):
                if "agent" in chunk and "messages" in chunk["agent"]:
                    for msg in chunk["agent"]["messages"]:
                        if hasattr(msg, "content") and msg.content:
                            content = str(msg.content)
                            # 简单分块
                            for i in range(0, len(content), 30):
                                yield content[i : i + 30]
                            return
        except Exception as e:
            logger.error(f"Error in chat_stream: {str(e)}")
            yield f"处理请求时出现错误: {str(e)}"

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

            # 重新创建agent - 注意要使用合并后的工具
            all_tools = self._merge_tools()
            self.graph = create_react_agent(
                self.llm, tools=all_tools, prompt="You are a helpful assistant. Please respond in Chinese.", checkpointer=self.memory
            )

            logger.info(f"Successfully switched to provider: {provider}, model: {model_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to switch provider: {str(e)}")
            return False

    async def _preprocess_image(self, image_data: dict) -> dict:
        """
        图片预处理
        - 格式转换
        - 尺寸调整
        - 质量压缩
        """
        # 根据不同提供商处理图片格式
        if self.provider == "openai":
            return {
                "type": "image_url",
                "image_url": {"url": image_data.get("url") or f"data:{image_data.get('mime_type', 'image/jpeg')};base64,{image_data.get('base64')}"},
            }
        elif self.provider == "claude":
            return {
                "type": "image",
                "source": {"type": "base64", "media_type": image_data.get("mime_type", "image/jpeg"), "data": image_data.get("base64")},
            }
        else:
            # 默认格式
            return {
                "type": "image",
                "source": {"type": "base64", "media_type": image_data.get("mime_type", "image/jpeg"), "data": image_data.get("base64")},
            }

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
