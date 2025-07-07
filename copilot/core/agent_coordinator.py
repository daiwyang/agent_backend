"""
Agent协调器 - 管理思考Agent和执行Agent的协作
实现"思考-执行"双Agent工作流
"""

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from copilot.core.execution_agent import ExecutionAgent
from copilot.core.thinking_agent import ThinkingAgent, ThinkingResult
from copilot.utils.logger import logger


class AgentCoordinator:
    """Agent协调器 - 管理思考和执行Agent的协作"""

    def __init__(
        self, thinking_agent: ThinkingAgent, execution_agent: ExecutionAgent, enable_thinking_mode: bool = True, save_thinking_process: bool = True
    ):
        """
        初始化协调器

        Args:
            thinking_agent: 思考Agent实例
            execution_agent: 执行Agent实例
            enable_thinking_mode: 是否启用思考模式
            save_thinking_process: 是否保存思考过程
        """
        self.thinking_agent = thinking_agent
        self.execution_agent = execution_agent
        self.enable_thinking_mode = enable_thinking_mode
        self.save_thinking_process = save_thinking_process

        # 思考过程存储
        self.thinking_history: Dict[str, List[ThinkingResult]] = {}

        logger.info(f"AgentCoordinator initialized with thinking_mode={enable_thinking_mode}")

    async def process_user_input(
        self,
        user_input: str,
        session_id: str,
        thread_id: Optional[str] = None,
        images: Optional[List] = None,
        enable_tools: bool = True,
        context: Dict[str, Any] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理用户输入，协调思考和执行过程

        Args:
            user_input: 用户输入
            session_id: 会话ID
            thread_id: 线程ID
            images: 图片列表
            enable_tools: 是否启用工具
            context: 上下文信息

        Yields:
            Dict[str, Any]: 流式响应数据
        """
        try:
            # 如果启用思考模式，先进行思考
            if self.enable_thinking_mode:
                async for chunk in self._process_with_thinking(user_input, session_id, thread_id, images, enable_tools, context):
                    yield chunk
            else:
                # 直接执行模式
                async for chunk in self._process_direct_execution(user_input, session_id, thread_id, images, enable_tools):
                    yield chunk

        except Exception as e:
            logger.error(f"AgentCoordinator处理出错: {str(e)}")
            yield {"type": "error", "content": f"协调器处理出错: {str(e)}", "timestamp": datetime.now().isoformat()}

    async def _process_with_thinking(
        self, user_input: str, session_id: str, thread_id: Optional[str], images: Optional[List], enable_tools: bool, context: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """带思考的处理流程"""

        # 1. 开始思考阶段
        yield {"type": "thinking_start", "content": "🤔 正在分析您的需求...", "phase": "thinking", "timestamp": datetime.now().isoformat()}

        try:
            # 2. 获取对话历史用于思考
            conversation_history = await self._get_conversation_history(session_id)

            # 3. 思考Agent分析
            thinking_result = await self.thinking_agent.think(user_input=user_input, context=context, conversation_history=conversation_history)

            # 4. 保存思考过程
            if self.save_thinking_process:
                self._save_thinking_result(session_id, thinking_result)

            # 5. 输出思考结果
            yield {
                "type": "thinking_result",
                "content": self._format_thinking_result(thinking_result),
                "thinking_data": asdict(thinking_result),
                "phase": "thinking",
                "timestamp": datetime.now().isoformat(),
            }

            # 6. 开始执行阶段
            yield {
                "type": "execution_start",
                "content": "⚡ 开始执行任务...",
                "phase": "execution",
                "execution_plan": [asdict(step) for step in thinking_result.execution_plan],
                "timestamp": datetime.now().isoformat(),
            }

            # 7. 构建增强的执行输入
            enhanced_input = self._build_enhanced_input(user_input, thinking_result)

            # 8. 执行Agent处理
            async for chunk in self.execution_agent.chat(
                message=enhanced_input, thread_id=thread_id, session_id=session_id, images=images, enable_tools=enable_tools
            ):
                # 为执行阶段的输出添加标识
                if isinstance(chunk, dict):
                    chunk["phase"] = "execution"
                    yield chunk
                else:
                    yield {"type": "content", "content": chunk, "phase": "execution", "timestamp": datetime.now().isoformat()}

            # 9. 执行完成
            yield {"type": "execution_complete", "content": "✅ 任务执行完成", "phase": "complete", "timestamp": datetime.now().isoformat()}

        except Exception as e:
            logger.error(f"思考-执行流程出错: {str(e)}")
            yield {"type": "error", "content": f"思考或执行过程出错: {str(e)}", "phase": "error", "timestamp": datetime.now().isoformat()}

    async def _process_direct_execution(
        self, user_input: str, session_id: str, thread_id: Optional[str], images: Optional[List], enable_tools: bool
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """直接执行模式"""

        yield {"type": "execution_start", "content": "直接处理您的请求...", "phase": "execution", "timestamp": datetime.now().isoformat()}

        async for chunk in self.execution_agent.chat(
            message=user_input, thread_id=thread_id, session_id=session_id, images=images, enable_tools=enable_tools
        ):
            if isinstance(chunk, dict):
                chunk["phase"] = "execution"
                yield chunk
            else:
                yield {"type": "content", "content": chunk, "phase": "execution", "timestamp": datetime.now().isoformat()}

    def _format_thinking_result(self, result: ThinkingResult) -> str:
        """格式化思考结果为用户可读的文本"""
        formatted_text = f"""💭 **分析结果**

**用户意图**: {result.user_intent}

**问题分析**: {result.problem_analysis}

**执行计划**:
"""

        for i, step in enumerate(result.execution_plan, 1):
            formatted_text += f"\n{i}. **{step.description}**"
            formatted_text += f"\n   - 原因: {step.reasoning}"
            if step.expected_tools:
                formatted_text += f"\n   - 预期工具: {', '.join(step.expected_tools)}"
            if step.dependencies:
                formatted_text += f"\n   - 依赖: {', '.join(step.dependencies)}"

        formatted_text += f"\n\n**复杂度评估**: {result.estimated_complexity}"

        if result.suggested_model:
            formatted_text += f"\n**建议模型**: {result.suggested_model}"

        return formatted_text

    def _build_enhanced_input(self, original_input: str, thinking_result: ThinkingResult) -> str:
        """构建增强的执行输入，包含思考结果"""

        enhanced_input = f"""用户原始输入: {original_input}

基于深度分析，我需要按以下计划执行:

用户意图: {thinking_result.user_intent}
问题分析: {thinking_result.problem_analysis}

执行步骤:
"""

        for i, step in enumerate(thinking_result.execution_plan, 1):
            enhanced_input += f"\n{i}. {step.description}"
            enhanced_input += f"\n   原因: {step.reasoning}"
            if step.expected_tools:
                enhanced_input += f"\n   需要工具: {', '.join(step.expected_tools)}"
            if step.parameters:
                enhanced_input += f"\n   参数: {json.dumps(step.parameters, ensure_ascii=False)}"

        enhanced_input += "\n\n请按照这个计划执行，确保每个步骤都得到适当的处理。"

        return enhanced_input

    async def _get_conversation_history(self, session_id: str) -> List[Dict]:
        """获取对话历史"""
        try:
            # 从执行Agent的历史管理器获取历史记录
            if hasattr(self.execution_agent, "chat_history_manager"):
                history_messages = await self.execution_agent.chat_history_manager.get_session_messages(session_id=session_id, limit=10)

                # 转换为简单的字典格式
                conversation_history = []
                for msg in history_messages:
                    conversation_history.append(
                        {"role": msg.role, "content": msg.content, "timestamp": msg.timestamp.isoformat() if msg.timestamp else None}
                    )

                return conversation_history

        except Exception as e:
            logger.warning(f"获取对话历史失败: {str(e)}")

        return []

    def _save_thinking_result(self, session_id: str, result: ThinkingResult):
        """保存思考结果"""
        if session_id not in self.thinking_history:
            self.thinking_history[session_id] = []

        self.thinking_history[session_id].append(result)

        # 只保留最近20次思考记录
        if len(self.thinking_history[session_id]) > 20:
            self.thinking_history[session_id] = self.thinking_history[session_id][-20:]

    def get_thinking_history(self, session_id: str) -> List[ThinkingResult]:
        """获取会话的思考历史"""
        return self.thinking_history.get(session_id, [])

    def clear_thinking_history(self, session_id: str):
        """清除会话的思考历史"""
        if session_id in self.thinking_history:
            del self.thinking_history[session_id]

    def configure_thinking_mode(self, enabled: bool):
        """配置思考模式"""
        self.enable_thinking_mode = enabled
        logger.info(f"Thinking mode set to: {enabled}")

    def get_coordinator_stats(self) -> Dict[str, Any]:
        """获取协调器统计信息"""
        total_thinking_sessions = len(self.thinking_history)
        total_thinking_records = sum(len(history) for history in self.thinking_history.values())

        return {
            "thinking_mode_enabled": self.enable_thinking_mode,
            "save_thinking_process": self.save_thinking_process,
            "total_thinking_sessions": total_thinking_sessions,
            "total_thinking_records": total_thinking_records,
            "thinking_agent_stats": self.thinking_agent.get_thinking_stats(),
            "execution_agent_info": {
                "provider": self.execution_agent.provider,
                "model": self.execution_agent.model_name,
                "context_memory_enabled": getattr(self.execution_agent, "context_memory_enabled", False),
            },
        }

    async def refine_and_retry(
        self,
        session_id: str,
        feedback: str,
        original_input: str,
        thread_id: Optional[str] = None,
        images: Optional[List] = None,
        enable_tools: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        根据反馈优化计划并重试执行

        Args:
            session_id: 会话ID
            feedback: 用户反馈或错误信息
            original_input: 原始用户输入
            thread_id: 线程ID
            images: 图片列表
            enable_tools: 是否启用工具

        Yields:
            Dict[str, Any]: 流式响应数据
        """
        try:
            # 获取最近的思考结果
            thinking_history = self.get_thinking_history(session_id)
            if not thinking_history:
                yield {"type": "error", "content": "没有找到之前的思考记录，无法优化", "timestamp": datetime.now().isoformat()}
                return

            last_thinking = thinking_history[-1]

            # 优化计划
            yield {
                "type": "refining_start",
                "content": "🔄 正在根据反馈优化执行计划...",
                "phase": "refining",
                "timestamp": datetime.now().isoformat(),
            }

            refined_result = await self.thinking_agent.refine_plan(last_thinking, feedback)

            # 保存优化后的计划
            if self.save_thinking_process:
                self._save_thinking_result(session_id, refined_result)

            # 输出优化结果
            yield {
                "type": "refined_plan",
                "content": f"📋 优化后的执行计划:\n{self._format_thinking_result(refined_result)}",
                "thinking_data": asdict(refined_result),
                "phase": "refining",
                "timestamp": datetime.now().isoformat(),
            }

            # 重新执行
            yield {
                "type": "retry_execution_start",
                "content": "🔄 开始重新执行...",
                "phase": "retry_execution",
                "timestamp": datetime.now().isoformat(),
            }

            enhanced_input = self._build_enhanced_input(original_input, refined_result)

            async for chunk in self.execution_agent.chat(
                message=enhanced_input, thread_id=thread_id, session_id=session_id, images=images, enable_tools=enable_tools
            ):
                if isinstance(chunk, dict):
                    chunk["phase"] = "retry_execution"
                    yield chunk
                else:
                    yield {"type": "content", "content": chunk, "phase": "retry_execution", "timestamp": datetime.now().isoformat()}

        except Exception as e:
            logger.error(f"优化重试过程出错: {str(e)}")
            yield {"type": "error", "content": f"优化重试过程出错: {str(e)}", "timestamp": datetime.now().isoformat()}
