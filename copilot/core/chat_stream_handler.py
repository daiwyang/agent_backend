"""
聊天流处理器 - 处理流式聊天输出和权限确认
"""

from typing import AsyncGenerator, Dict, Optional

from copilot.config.settings import conf
from copilot.utils.logger import logger

# from copilot.config.settings import Config, ChatConfig


# 简化配置，只保留基础设置
class ChatConfig:
    """聊天配置"""

    ENABLE_STREAM_NOTIFIER = True  # 是否启用流式通知器
    STREAM_NOTIFIER_TIMEOUT = 5  # 流式通知器超时时间（秒）


class ChatStreamHandler:
    """聊天流处理器 - 处理流式聊天输出和权限确认"""

    def __init__(self, graph):
        """初始化聊天流处理器"""
        self.graph = graph

    async def handle_stream_with_permission(self, inputs: Dict, config: Dict, session_id: Optional[str]) -> AsyncGenerator[Dict, None]:
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
                chunk_content = chunk.get("content", "") if isinstance(chunk, dict) else str(chunk)
                if "🔒 等待用户确认执行工具:" in chunk_content:
                    yield chunk

                    # 如果有session_id，等待权限确认
                    if session_id and not permission_handled:
                        permission_handled = True
                        context = agent_state_manager.get_execution_context(session_id)
                        if context and context.state == AgentExecutionState.WAITING_PERMISSION:
                            yield {"content": "\n\n⏳ 请在聊天界面中确认是否允许执行此工具...\n", "type": "system"}

                            # 等待用户权限确认
                            permission_granted = await agent_state_manager.wait_for_permission(session_id, timeout=30)

                            if permission_granted:
                                yield {"content": "✅ 权限已确认，继续执行...\n", "type": "system"}
                                # 继续执行 - 这里可能需要重新调用Agent或恢复执行
                                # 由于权限确认后工具已经在回调中执行，这里主要是状态同步
                                context.update_state(AgentExecutionState.COMPLETED)
                            else:
                                yield {"content": "❌ 权限被拒绝或超时，执行已停止。\n", "type": "system"}
                                context.update_state(AgentExecutionState.PAUSED)
                                break
                else:
                    # 直接输出所有内容，保持字典格式
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

            yield {"content": f"处理请求时出现错误: {str(e)}", "type": "error"}

    async def _stream_internal(self, inputs: Dict, config: Dict) -> AsyncGenerator[Dict, None]:
        """内部流式聊天方法 - 简化版本，统一输出content类型"""
        try:
            # 尝试使用流式输出
            async for chunk in self.graph.astream(inputs, config=config, stream_mode="messages"):
                if chunk and len(chunk) >= 2:
                    message_chunk, _ = chunk
                    if hasattr(message_chunk, "content") and message_chunk.content:
                        # 只输出AI助手的消息，过滤掉工具消息
                        if self._is_ai_message(message_chunk):
                            content = str(message_chunk.content)
                            yield {"content": content, "type": "content"}
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

                                # 简单分块
                                for i in range(0, len(content), 30):
                                    chunk_content = content[i : i + 30]
                                    yield {"content": chunk_content, "type": "content"}
            return
        except Exception as e:
            logger.error(f"Error in chat_stream: {str(e)}")
            yield {"content": f"处理请求时出现错误: {str(e)}", "type": "error"}

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

    def prepare_config(self, thread_id: Optional[str], session_id: Optional[str]) -> Dict:
        """准备LangGraph配置"""
        config = {}
        if thread_id:
            config["configurable"] = {"thread_id": thread_id}
        if session_id:
            config.setdefault("configurable", {})["session_id"] = session_id
        return config
