"""
核心Agent - 只负责LLM交互
"""

import os
from typing import List, Dict, Any, AsyncGenerator
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_deepseek import ChatDeepSeek
from copilot.utils.logger import logger


class CoreAgent:
    """核心Agent - 专注于LLM交互"""

    def __init__(self, model_name: str = "deepseek-chat", tools: List = None):
        self.model_name = model_name
        self.tools = tools or []
        self.memory = MemorySaver()

        # 初始化LLM
        self.llm = self._create_llm()

        # 创建LangGraph agent
        self.graph = create_react_agent(
            self.llm, tools=self.tools, prompt="You are a helpful assistant. Please respond in Chinese.", checkpointer=self.memory
        )

        logger.info(f"CoreAgent initialized with model: {model_name}")

    def _create_llm(self):
        """创建LLM实例"""
        api_key = os.getenv("DEEPSEEK_API_KEY")

        if api_key:
            return ChatDeepSeek(
                model=self.model_name,
                temperature=0.7,
                streaming=True,
                api_key=api_key,
                max_tokens=4096,
            )
        else:
            logger.warning("DEEPSEEK_API_KEY not found, using fallback mode")
            return f"deepseek:{self.model_name}"

    async def chat(self, thread_id: str, message: str) -> str:
        """
        简单聊天接口

        Args:
            thread_id: 线程ID
            message: 用户消息

        Returns:
            str: 助手回复
        """
        config = {"configurable": {"thread_id": thread_id}}
        inputs = {"messages": [{"role": "user", "content": message}]}

        try:
            for chunk in self.graph.stream(inputs, config=config, stream_mode="updates"):
                if "agent" in chunk:
                    for msg in chunk["agent"]["messages"]:
                        if msg.content:
                            return str(msg.content)
        except Exception as e:
            logger.error(f"Error in chat: {str(e)}")
            return "抱歉，处理您的请求时出现了错误。"

        return "未能获取到回复。"

    async def chat_stream(self, thread_id: str, message: str) -> AsyncGenerator[str, None]:
        """
        流式聊天接口

        Args:
            thread_id: 线程ID
            message: 用户消息

        Yields:
            str: 响应片段
        """
        config = {"configurable": {"thread_id": thread_id}}
        inputs = {"messages": [{"role": "user", "content": message}]}

        # 检查是否使用DeepSeek API
        api_key = os.getenv("DEEPSEEK_API_KEY")

        if api_key:
            # 使用真正的流式输出
            try:
                async for chunk in self.graph.astream(inputs, config=config, stream_mode="messages"):
                    if chunk and len(chunk) >= 2:
                        message_chunk, _ = chunk
                        if hasattr(message_chunk, "content") and message_chunk.content:
                            yield str(message_chunk.content)
                return
            except Exception as e:
                logger.warning(f"Streaming failed: {str(e)}, falling back")

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
            yield "处理请求时出现错误"
