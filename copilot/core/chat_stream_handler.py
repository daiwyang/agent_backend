"""
聊天流处理器 - 处理流式聊天输出和权限确认
"""

from typing import AsyncGenerator, Dict, Optional

from copilot.utils.logger import logger
from copilot.config.settings import conf

# from copilot.config.settings import Config, ChatConfig


# 临时硬编码配置，后续可以从配置文件读取
class ChatConfig:
    """聊天配置"""

    ENABLE_AI_THINKING_CLASSIFICATION = True  # 是否启用AI思考和回答分类
    THINKING_EMOJI = "🤔"  # 思考阶段的表情符号
    RESPONSE_EMOJI = "💬"  # 回答阶段的表情符号
    THINKING_PREFIX = "**AI思考中**："  # 思考阶段的前缀
    RESPONSE_PREFIX = "**AI回答**："  # 回答阶段的前缀

    # 思考模式的关键词 - 包括各种思维过程
    THINKING_KEYWORDS_ZH = [
        # 行动规划类
        "我需要",
        "让我",
        "首先",
        "我应该",
        "为了回答",
        "为了获取",
        "我来",
        "现在让我",
        "接下来我",
        "我想",
        "我会",
        "我将",
        "我要",
        "我先",
        "让我们",
        "我们需要",
        "我们来",
        "我们先",
        "我们应该",
        # 问题分析类
        "这个问题",
        "这里需要考虑",
        "我们来分析",
        "让我分析",
        "分析一下",
        "考虑到",
        "需要注意",
        "值得思考",
        "关键在于",
        "问题的核心",
        # 推理思考类
        "从逻辑上",
        "推理过程",
        "因此可以",
        "由此可见",
        "综合考虑",
        "权衡利弊",
        "比较分析",
        "深入思考",
        "仔细考虑",
        "进一步分析",
        # 方案规划类
        "制定策略",
        "规划方案",
        "设计思路",
        "解决方案",
        "实现步骤",
        "具体做法",
        "采用方法",
        "选择策略"
    ]

    THINKING_KEYWORDS_EN = [
        # Action planning
        "I need to",
        "Let me",
        "I should",
        "To answer",
        "In order to",
        "I'll",
        "I will",
        "I want to",
        "I'm going to",
        "Let's",
        "We need to",
        "We should",
        "First, I'll",
        "Now I'll",
        # Problem analysis
        "This problem",
        "We need to consider",
        "Let me analyze",
        "Analyzing this",
        "Considering",
        "It's important to note",
        "The key is",
        "The core issue",
        "Worth thinking about",
        # Reasoning process
        "Logically speaking",
        "From a logical perspective",
        "Therefore",
        "Thus we can",
        "Given that",
        "Weighing the options",
        "Comparing",
        "Thinking deeper",
        "Upon reflection",
        "Further analysis shows"
    ]

    # 回答模式的关键词
    RESPONSE_KEYWORDS_ZH = [
        "根据查询结果",
        "基于搜索结果",
        "查询结果显示",
        "根据工具返回",
        "基于获取的信息",
        "从结果中可以看到",
        "搜索结果表明",
        "通过查询发现",
        "根据分析结果",
        "查询到的信息",
        "搜索得到",
        "获取的数据显示",
    ]

    RESPONSE_KEYWORDS_EN = [
        "Based on the results",
        "According to the search",
        "The results show",
        "From the search results",
        "The query returned",
        "Based on the data",
        "According to the analysis",
        "The search revealed",
        "Results indicate",
    ]


class ChatStreamHandler:
    """聊天流处理器 - 负责处理流式输出和权限确认流程"""

    def __init__(self, graph):
        """
        初始化聊天流处理器

        Args:
            graph: LangGraph实例
        """
        self.graph = graph

    async def handle_stream_with_permission(self, inputs: Dict, config: Dict, session_id: Optional[str]) -> AsyncGenerator[str, None]:
        """带权限处理的流式聊天方法"""
        try:
            from copilot.core.agent_state_manager import AgentExecutionState, agent_state_manager

            # 获取执行上下文（不重复设置状态，因为agent.py中已经设置了）
            context = None
            if session_id:
                context = agent_state_manager.get_execution_context(session_id)
                # 如果没有上下文，说明可能有问题，但不在这里创建，因为应该在agent.py中创建
                if not context:
                    logger.warning(f"No execution context found for session {session_id} in ChatStreamHandler")
                    context = agent_state_manager.create_execution_context(session_id)
                    context.update_state(AgentExecutionState.RUNNING)

            # 流式处理聊天
            has_content = False
            permission_handled = False

            async for chunk in self._stream_internal(inputs, config):
                has_content = True

                # 检查是否遇到权限确认请求
                if "🔒 等待用户确认执行工具:" in str(chunk):
                    yield chunk

                    # 如果有session_id，等待权限确认
                    if session_id and not permission_handled:
                        permission_handled = True
                        context = agent_state_manager.get_execution_context(session_id)
                        if context and context.state == AgentExecutionState.WAITING_PERMISSION:
                            yield "\n\n⏳ 请在聊天界面中确认是否允许执行此工具...\n"

                            # 等待用户权限确认
                            permission_granted = await agent_state_manager.wait_for_permission(session_id, timeout=30)

                            if permission_granted:
                                yield "✅ 权限已确认，继续执行...\n"
                                # 继续执行 - 这里可能需要重新调用Agent或恢复执行
                                # 由于权限确认后工具已经在回调中执行，这里主要是状态同步
                                context.update_state(AgentExecutionState.COMPLETED)
                            else:
                                yield "❌ 权限被拒绝或超时，执行已停止。\n"
                                context.update_state(AgentExecutionState.PAUSED)
                                break
                else:
                    # 直接输出所有内容，不再需要过滤逻辑
                    yield chunk

            # 🔥 关键修复：确保执行状态正确结束
            if session_id and context:
                if has_content:
                    # 如果没有处理权限确认，说明没有工具需要权限，直接完成
                    if not permission_handled:
                        context.update_state(AgentExecutionState.COMPLETED)
                        logger.info(f"Chat completed without tool permission requests for session: {session_id}")
                else:
                    # 如果没有输出内容，可能是错误状态
                    context.update_state(AgentExecutionState.IDLE)
                    logger.info(f"Chat completed with no content for session: {session_id}")

        except Exception as e:
            logger.error(f"Error in chat_stream_with_permission_handling: {str(e)}")

            # 🔥 关键修复：异常时也要更新状态
            if session_id:
                context = agent_state_manager.get_execution_context(session_id)
                if context:
                    context.update_state(AgentExecutionState.ERROR, error=str(e))

            yield f"处理请求时出现错误: {str(e)}"

    async def _stream_internal(self, inputs: Dict, config: Dict) -> AsyncGenerator[str, None]:
        """内部流式聊天方法 - 区分AI思考和正式回答"""
        try:
            # 尝试使用流式输出
            async for chunk in self.graph.astream(inputs, config=config, stream_mode="messages"):
                if chunk and len(chunk) >= 2:
                    message_chunk, _ = chunk
                    if hasattr(message_chunk, "content") and message_chunk.content:
                        # 只输出AI助手的消息，过滤掉工具消息
                        if self._is_ai_message(message_chunk):
                            content = str(message_chunk.content)

                            # 检查是否包含工具调用，区分思考和回答
                            message_type = self._classify_ai_message(message_chunk)

                            if message_type == "thinking":
                                # 思考阶段 - 添加思考标识
                                if ChatConfig.ENABLE_AI_THINKING_CLASSIFICATION:
                                    yield f"{ChatConfig.THINKING_EMOJI} {ChatConfig.THINKING_PREFIX}{content}"
                                else:
                                    yield content
                            elif message_type == "response":
                                # 正式回答阶段 - 添加回答标识
                                if ChatConfig.ENABLE_AI_THINKING_CLASSIFICATION:
                                    yield f"{ChatConfig.RESPONSE_EMOJI} {ChatConfig.RESPONSE_PREFIX}{content}"
                                else:
                                    yield content
                            else:
                                # 默认输出
                                yield content
            return
        except Exception as e:
            logger.warning(f"Streaming failed: {str(e)}, falling back to chunk mode")

        # 回退到分块模式
        try:
            async for chunk in self.graph.astream(inputs, config=config, stream_mode="updates"):
                if "agent" in chunk and "messages" in chunk["agent"]:
                    for msg in chunk["agent"]["messages"]:
                        if hasattr(msg, "content") and msg.content:
                            # 只输出AI助手的消息，过滤掉工具消息
                            if self._is_ai_message(msg):
                                content = str(msg.content)

                                # 检查是否包含工具调用，区分思考和回答
                                message_type = self._classify_ai_message(msg)

                                if message_type == "thinking":
                                    # 思考阶段
                                    if ChatConfig.ENABLE_AI_THINKING_CLASSIFICATION:
                                        formatted_content = f"{ChatConfig.THINKING_EMOJI} {ChatConfig.THINKING_PREFIX}{content}"
                                    else:
                                        formatted_content = content
                                elif message_type == "response":
                                    # 正式回答阶段
                                    if ChatConfig.ENABLE_AI_THINKING_CLASSIFICATION:
                                        formatted_content = f"{ChatConfig.RESPONSE_EMOJI} {ChatConfig.RESPONSE_PREFIX}{content}"
                                    else:
                                        formatted_content = content
                                else:
                                    formatted_content = content

                                # 简单分块
                                for i in range(0, len(formatted_content), 30):
                                    yield formatted_content[i : i + 30]
                            return
        except Exception as e:
            logger.error(f"Error in chat_stream: {str(e)}")
            yield f"处理请求时出现错误: {str(e)}"

    def _is_ai_message(self, message) -> bool:
        """
        判断是否是AI助手的消息

        Args:
            message: 消息对象

        Returns:
            bool: 是否是AI助手的消息
        """
        try:
            # 检查消息类型 - AI助手的消息通常是AIMessage或AIMessageChunk
            message_type = type(message).__name__
            if message_type in ["AIMessage", "AIMessageChunk"]:
                return True

            # 检查消息的role属性 - AI助手的role通常是"assistant"
            if hasattr(message, "role") and message.role == "assistant":
                return True

            # 检查消息的type属性 - AI助手的type通常是"ai"
            if hasattr(message, "type") and message.type == "ai":
                return True

            # 如果没有明确的类型信息，通过排除法判断
            # 排除工具消息
            if hasattr(message, "tool_call_id"):
                return False

            if hasattr(message, "role") and message.role == "tool":
                return False

            if hasattr(message, "type") and message.type == "tool":
                return False

            if message_type in ["ToolMessage", "ToolMessageChunk"]:
                return False

            # 排除用户消息
            if hasattr(message, "role") and message.role == "user":
                return False

            if hasattr(message, "type") and message.type == "human":
                return False

            if message_type in ["HumanMessage", "HumanMessageChunk"]:
                return False

            # 如果都不是，可能是AI消息，保守输出
            logger.debug(f"Unknown message type {message_type}, treating as AI message")
            return True

        except Exception as e:
            logger.debug(f"Error checking AI message: {e}")
            return False

    def _classify_ai_message(self, message) -> str:
        """
        分类AI消息类型：思考 vs 回答

        Args:
            message: AI消息对象

        Returns:
            str: "thinking" | "response" | "default"
        """
        try:
            # 如果未启用分类功能，直接返回默认
            if not ChatConfig.ENABLE_AI_THINKING_CLASSIFICATION:
                return "default"

            # 检查消息内容
            content = str(message.content) if message.content else ""
            if not content.strip():
                return "default"

            # 获取所有思考和回答模式的关键词
            thinking_patterns = ChatConfig.THINKING_KEYWORDS_ZH + ChatConfig.THINKING_KEYWORDS_EN + ["Action:", "Thought:"]  # ReAct模式的特殊标识
            response_patterns = ChatConfig.RESPONSE_KEYWORDS_ZH + ChatConfig.RESPONSE_KEYWORDS_EN

            # 优先基于内容特征判断
            # 1. 如果内容包含思考模式关键词，归类为思考
            if any(pattern in content for pattern in thinking_patterns):
                logger.debug(f"Message classified as thinking based on content patterns")
                return "thinking"

            # 2. 如果内容包含回答模式关键词，归类为回答
            if any(pattern in content for pattern in response_patterns):
                logger.debug(f"Message classified as response based on content patterns")
                return "response"

            # 3. 检查是否有工具调用作为辅助判断
            has_tool_calls = False

            # 检查tool_calls属性
            if hasattr(message, "tool_calls") and message.tool_calls:
                has_tool_calls = True
                logger.debug(f"Found tool_calls in message: {len(message.tool_calls)} calls")

            # 检查additional_kwargs中的tool_calls（OpenAI格式）
            if hasattr(message, "additional_kwargs") and message.additional_kwargs:
                if "tool_calls" in message.additional_kwargs and message.additional_kwargs["tool_calls"]:
                    has_tool_calls = True
                    logger.debug(f"Found tool_calls in additional_kwargs")

            # 4. 如果有工具调用但没有明确的关键词模式，也倾向于归类为思考
            # 因为通常在调用工具前AI会有思考过程
            if has_tool_calls:
                logger.debug(f"Message classified as thinking due to tool calls")
                return "thinking"

            # 5. 默认情况 - 普通对话
            return "default"

        except Exception as e:
            logger.debug(f"Error classifying AI message: {e}")
            return "default"

    def prepare_config(self, thread_id: Optional[str], session_id: Optional[str]) -> Dict:
        """准备LangGraph配置"""
        config = {}
        if thread_id:
            config["configurable"] = {"thread_id": thread_id}
        if session_id:
            config.setdefault("configurable", {})["session_id"] = session_id
        return config
