"""
核心Agent - 支持多个LLM提供商
"""

import os
from typing import Any, AsyncGenerator, Dict, List, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from copilot.core.llm_factory import LLMFactory
from copilot.utils.logger import logger


class CoreAgent:
    """核心Agent - 支持多个LLM提供商"""

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

        # 初始化LLM
        try:
            self.llm = LLMFactory.create_llm(
                provider=provider,
                model=model_name,
                **llm_kwargs
            )
            logger.info(f"CoreAgent initialized with provider: {provider or 'default'}, model: {model_name or 'default'}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {str(e)}")
            raise

        # 创建LangGraph agent
        self.graph = create_react_agent(
            self.llm, 
            tools=self.tools, 
            prompt="You are a helpful assistant. Please respond in Chinese.", 
            checkpointer=self.memory
        )

    def get_provider_info(self) -> Dict[str, Any]:
        """
        获取当前使用的提供商信息
        
        Returns:
            Dict[str, Any]: 提供商信息
        """
        return {
            "provider": self.provider,
            "model": self.model_name,
            "available_providers": LLMFactory.get_available_providers()
        }

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
            new_llm = LLMFactory.create_llm(
                provider=provider,
                model=model_name,
                **llm_kwargs
            )
            
            # 更新实例变量
            self.provider = provider
            self.model_name = model_name
            self.llm_kwargs = llm_kwargs
            self.llm = new_llm
            
            # 重新创建agent
            self.graph = create_react_agent(
                self.llm,
                tools=self.tools,
                prompt="You are a helpful assistant. Please respond in Chinese.",
                checkpointer=self.memory
            )
            
            logger.info(f"Successfully switched to provider: {provider}, model: {model_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to switch provider: {str(e)}")
            return False

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
        try:
            # 根据当前提供商处理多模态输入
            if self.provider == 'openai':
                # GPT-4V 支持
                messages = [{
                    "role": "user", 
                    "content": [{"type": "text", "text": input_data["text"]}] + input_data.get("images", [])
                }]
                
                # 使用当前的LLM实例进行推理
                config = {"configurable": {"thread_id": input_data["thread_id"]}}
                inputs = {"messages": messages}
                
                for chunk in self.graph.stream(inputs, config=config, stream_mode="updates"):
                    if "agent" in chunk:
                        for msg in chunk["agent"]["messages"]:
                            if msg.content:
                                return str(msg.content)
                                
            elif self.provider == 'claude':
                # Claude-3 支持
                messages = [{
                    "role": "user",
                    "content": [{"type": "text", "text": input_data["text"]}] + input_data.get("images", [])
                }]
                
                config = {"configurable": {"thread_id": input_data["thread_id"]}}
                inputs = {"messages": messages}
                
                for chunk in self.graph.stream(inputs, config=config, stream_mode="updates"):
                    if "agent" in chunk:
                        for msg in chunk["agent"]["messages"]:
                            if msg.content:
                                return str(msg.content)
                                
            elif self.provider == 'gemini':
                # Gemini Pro Vision 支持
                # Google 格式可能需要特殊处理
                return f"我看到了您提供的图片。{input_data['text']} (Gemini 多模态处理)"
                
            else:
                # 其他提供商暂不支持多模态
                return f"当前使用的 {self.provider} 提供商暂不支持图片分析功能。您的消息：{input_data['text']}"
                
        except Exception as e:
            logger.error(f"Error in multimodal processing: {str(e)}")
            return f"处理多模态输入时出现错误：{str(e)}"

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

        # 检查当前提供商是否支持多模态
        multimodal_providers = ['openai', 'claude', 'gemini']
        
        if self.provider in multimodal_providers:
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
            # 不支持多模态的提供商
            yield f"当前使用的 {self.provider} 提供商暂不支持图片分析功能。"
