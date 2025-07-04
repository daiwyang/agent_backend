"""
聊天流处理器 - 处理流式聊天输出和权限确认
"""

from typing import AsyncGenerator, Dict, Optional

from copilot.utils.logger import logger


class ChatStreamHandler:
    """聊天流处理器 - 负责处理流式输出和权限确认流程"""
    
    def __init__(self, graph):
        """
        初始化聊天流处理器
        
        Args:
            graph: LangGraph实例
        """
        self.graph = graph
    
    async def handle_stream_with_permission(self, inputs: Dict, config: Dict, 
                                          session_id: Optional[str]) -> AsyncGenerator[str, None]:
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
        """内部流式聊天方法"""
        try:
            # 尝试使用流式输出
            async for chunk in self.graph.astream(inputs, config=config, stream_mode="messages"):
                if chunk and len(chunk) >= 2:
                    message_chunk, _ = chunk
                    if hasattr(message_chunk, "content") and message_chunk.content:
                        content = str(message_chunk.content)
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
                            content = str(msg.content)
                            
                            # 简单分块
                            for i in range(0, len(content), 30):
                                yield content[i : i + 30]
                            return
        except Exception as e:
            logger.error(f"Error in chat_stream: {str(e)}")
            yield f"处理请求时出现错误: {str(e)}"

    def prepare_config(self, thread_id: Optional[str], session_id: Optional[str]) -> Dict:
        """准备LangGraph配置"""
        config = {}
        if thread_id:
            config["configurable"] = {"thread_id": thread_id}
        if session_id:
            config.setdefault("configurable", {})["session_id"] = session_id
        return config 