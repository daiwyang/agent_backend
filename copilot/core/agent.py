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

    async def process_multimodal_input(self, thread_id: str, message: str, images: List = None) -> str:
        """
        处理多模态输入（文本+图片）

        Args:
            thread_id: 线程ID
            message: 文本消息
            images: 图片列表（base64或URL）

        Returns:
            str: 模型回复
        """
        # 1. 图片预处理
        processed_images = []
        if images:
            for img in images:
                # 图片压缩、格式转换、编码等
                processed_img = await self._preprocess_image(img)
                processed_images.append(processed_img)

        # 2. 构造多模态输入
        multimodal_input = {"text": message, "images": processed_images, "thread_id": thread_id}

        # 3. 发送到多模态模型
        # 这里需要集成支持视觉的模型，如 GPT-4V、Claude-3、Gemini Pro Vision 等
        response = await self._call_multimodal_model(multimodal_input)

        return response

    async def _preprocess_image(self, image_data: dict) -> dict:
        """
        图片预处理
        - 格式转换
        - 尺寸调整
        - 质量压缩
        """
        # 实现图片预处理逻辑
        return {
            "type": "image",
            "source": {"type": "base64", "media_type": image_data.get("mime_type", "image/jpeg"), "data": image_data.get("base64")},
        }

    async def _call_multimodal_model(self, input_data: dict) -> str:
        """
        调用多模态模型API
        支持的模型：
        - OpenAI GPT-4V
        - Anthropic Claude-3
        - Google Gemini Pro Vision
        """
        # 这里需要根据具体使用的模型进行实现
        # 示例：使用 OpenAI GPT-4V

        # 构造消息格式
        messages = [{"role": "user", "content": [{"type": "text", "text": input_data["text"]}] + input_data.get("images", [])}]

        # 调用模型API
        # response = await openai_client.chat.completions.create(
        #     model="gpt-4-vision-preview",
        #     messages=messages,
        #     max_tokens=4096
        # )

        # 暂时返回模拟响应
        return f"我看到了您提供的图片。{input_data['text']}"

    async def chat_stream_multimodal(self, thread_id: str, message: str, images: List = None) -> AsyncGenerator[str, None]:
        """
        多模态流式聊天接口

        Args:
            thread_id: 线程ID
            message: 用户消息
            images: 图片列表

        Yields:
            str: 响应片段
        """
        config = {"configurable": {"thread_id": thread_id}}

        # 构造多模态输入
        content = [{"type": "text", "text": message}]

        if images:
            for img in images:
                content.append(
                    {"type": "image_url", "image_url": {"url": img.get("url") or f"data:{img.get('mime_type')};base64,{img.get('base64')}"}}
                )

        inputs = {"messages": [{"role": "user", "content": content}]}

        # 检查是否使用支持视觉的API
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")

        if api_key:
            # 使用真正的多模态流式输出
            try:
                async for chunk in self.graph.astream(inputs, config=config, stream_mode="messages"):
                    if chunk and len(chunk) >= 2:
                        message_chunk, _ = chunk
                        if hasattr(message_chunk, "content") and message_chunk.content:
                            yield str(message_chunk.content)
                return
            except Exception as e:
                logger.warning(f"Multimodal streaming failed: {str(e)}, falling back")
                yield f"抱歉，处理图片时出现错误：{str(e)}"
        else:
            # 模拟输出
            yield "我看到了您上传的图片，但当前配置不支持图片分析功能。"
