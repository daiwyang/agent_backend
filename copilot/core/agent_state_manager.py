"""
Agent状态管理器 - 处理Agent执行状态、暂停/恢复和工具权限确认
"""

import asyncio
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from copilot.utils.logger import logger


class AgentExecutionState(Enum):
    """Agent执行状态"""

    IDLE = "idle"  # 空闲状态
    RUNNING = "running"  # 正在执行
    WAITING_PERMISSION = "waiting_permission"  # 等待工具权限确认
    PAUSED = "paused"  # 暂停执行
    COMPLETED = "completed"  # 执行完成
    ERROR = "error"  # 执行错误


class PendingToolExecution:
    """待执行的工具信息"""

    def __init__(self, tool_name: str, parameters: Dict[str, Any], callback: Callable, risk_level: str = "medium"):
        self.execution_id = str(uuid.uuid4())
        self.tool_name = tool_name
        self.parameters = parameters
        self.callback = callback
        self.risk_level = risk_level
        self.created_at = datetime.now(UTC)
        self.status = "pending"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "execution_id": self.execution_id,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "risk_level": self.risk_level,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
        }


class AgentExecutionContext:
    """Agent执行上下文"""

    def __init__(self, session_id: str, thread_id: Optional[str] = None):
        self.session_id = session_id
        self.thread_id = thread_id
        self.execution_id = str(uuid.uuid4())
        self.state = AgentExecutionState.IDLE
        self.current_message = ""
        self.error_message = ""
        self.pending_tools: List[PendingToolExecution] = []
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        self.permission_event = asyncio.Event()  # 权限确认事件

        # 添加工具结果缓存
        self.last_tool_result = None  # 缓存最后一个工具的执行结果

        # 添加基于request_id的权限决策记录
        self.permission_decisions: Dict[str, bool] = {}  # request_id -> approved

    def update_state(self, new_state: AgentExecutionState, message: Optional[str] = None, error: Optional[str] = None):
        """更新执行状态"""
        self.state = new_state
        self.updated_at = datetime.now(UTC)

        if message:
            self.current_message = message
        if error:
            self.error_message = error

        logger.info(f"Agent context {self.execution_id} state updated to: {new_state.value}")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "session_id": self.session_id,
            "thread_id": self.thread_id,
            "execution_id": self.execution_id,
            "state": self.state.value,
            "current_message": self.current_message,
            "pending_tools": [tool.to_dict() for tool in self.pending_tools],
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class AgentStateManager:
    """Agent状态管理器"""

    def __init__(self):
        self.active_contexts: Dict[str, AgentExecutionContext] = {}  # session_id -> context
        self.cleanup_task = None

    async def start(self):
        """启动状态管理器"""
        self.cleanup_task = asyncio.create_task(self._cleanup_expired_contexts())
        logger.info("AgentStateManager started")

    async def stop(self):
        """停止状态管理器"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("AgentStateManager stopped")

    def create_execution_context(self, session_id: str, thread_id: Optional[str] = None) -> AgentExecutionContext:
        """创建执行上下文"""
        context = AgentExecutionContext(session_id, thread_id)
        self.active_contexts[session_id] = context
        logger.info(f"Created execution context for session: {session_id}")
        return context

    def get_execution_context(self, session_id: str) -> Optional[AgentExecutionContext]:
        """获取执行上下文"""
        return self.active_contexts.get(session_id)

    async def request_tool_permission(
        self, session_id: str, tool_name: str, parameters: Dict[str, Any], callback: Optional[Callable], risk_level: str = "medium"
    ) -> bool:
        """
        请求工具执行权限（非阻塞）

        Args:
            session_id: 会话ID
            tool_name: 工具名称
            parameters: 工具参数
            callback: 工具执行回调函数（可选，如果为None则不创建PendingToolExecution）
            risk_level: 风险级别

        Returns:
            bool: 是否应该继续执行（低风险工具直接返回True）
        """
        context = self.get_execution_context(session_id)
        if not context:
            logger.error(f"No execution context found for session: {session_id}")
            return False

        # 低风险工具直接执行
        if risk_level == "low":
            if callback:
                try:
                    await callback()
                    return True
                except Exception as e:
                    logger.error(f"Low-risk tool execution failed: {e}")
                    return False
            else:
                # 没有回调，返回True让主流程执行
                return True

        # 中高风险工具需要用户确认
        if callback:
            # 传统模式：创建待执行工具并注册回调
            pending_tool = PendingToolExecution(tool_name, parameters, callback, risk_level)
            context.pending_tools.append(pending_tool)

        context.update_state(AgentExecutionState.WAITING_PERMISSION, f"等待用户确认工具执行: {tool_name}")

        # 设置等待状态，但不阻塞
        context.permission_event.clear()

        return False  # 返回False表示需要等待权限确认

    async def handle_permission_response(self, session_id: str, request_id: str, approved: bool) -> bool:
        """
        处理权限响应 - 基于request_id的精确权限控制

        Args:
            session_id: 会话ID
            request_id: 工具请求ID（唯一标识具体的工具实例）
            approved: 是否批准

        Returns:
            bool: 处理是否成功
        """
        context = self.get_execution_context(session_id)
        if not context:
            logger.error(f"No execution context found for session: {session_id}")
            return False

        try:
            # 记录权限决策
            context.permission_decisions[request_id] = approved

            if approved:
                # 用户批准特定工具
                context.update_state(AgentExecutionState.RUNNING, f"用户已确认工具执行权限 (request_id: {request_id[:8]})")
                logger.info(f"Permission approved for session: {session_id}, request_id: {request_id}")
            else:
                # 用户拒绝特定工具
                context.update_state(AgentExecutionState.PAUSED, f"用户拒绝了工具执行权限 (request_id: {request_id[:8]})")
                logger.info(f"Permission denied for session: {session_id}, request_id: {request_id}")

            # 设置权限事件，唤醒等待的工具执行
            context.permission_event.set()
            return True

        except Exception as e:
            logger.error(f"Error handling permission response: {e}")
            context.update_state(AgentExecutionState.ERROR, f"处理权限响应时发生错误: {str(e)}")
            return False

    async def handle_permission_response_simple(
        self, session_id: str, request_id: str = None, approved: bool = True, user_feedback: str = None
    ) -> bool:
        """
        简化的权限响应处理 - 适用于HTTP方案
        支持request_id匹配或处理最新的权限请求

        Args:
            session_id: 会话ID
            request_id: 权限请求ID（可选，如果提供则精确匹配）
            approved: 是否批准
            user_feedback: 用户反馈（可选）

        Returns:
            bool: 处理是否成功
        """
        context = self.get_execution_context(session_id)
        if not context:
            logger.error(f"No execution context found for session: {session_id}")
            return False

        # 获取待执行工具
        if not context.pending_tools:
            logger.warning(f"No pending tools for session: {session_id}")
            return False

        # 如果提供了request_id，尝试匹配
        pending_tool = None
        if request_id:
            for tool in context.pending_tools:
                if tool.execution_id == request_id:
                    pending_tool = tool
                    break

            if not pending_tool:
                logger.warning(f"No pending tool found with request_id: {request_id}")
                return False
        else:
            # 如果没有提供request_id，处理最新的待执行工具
            pending_tool = context.pending_tools[-1]

        try:
            if approved:
                # 执行工具
                result = await pending_tool.callback()
                pending_tool.status = "approved"

                # 缓存工具执行结果到上下文
                context.last_tool_result = result

                context.update_state(AgentExecutionState.RUNNING, "继续执行...")
                logger.info(f"Tool executed successfully: {pending_tool.tool_name} (request_id: {pending_tool.execution_id})")
            else:
                # 用户拒绝
                pending_tool.status = "rejected"
                context.update_state(AgentExecutionState.PAUSED, f"用户拒绝了工具执行: {pending_tool.tool_name}")
                logger.info(f"Tool execution rejected: {pending_tool.tool_name} (request_id: {pending_tool.execution_id})")

            # 记录用户反馈
            if user_feedback:
                logger.info(f"User feedback for {pending_tool.tool_name}: {user_feedback}")

            # 从待执行列表中移除
            context.pending_tools.remove(pending_tool)

            # 如果没有更多待确认的工具，设置事件
            if not context.pending_tools:
                context.permission_event.set()

            return True

        except Exception as e:
            logger.error(f"Error handling permission response: {e}")
            pending_tool.status = "error"
            context.update_state(AgentExecutionState.ERROR, f"工具执行错误: {str(e)}")
            return False

    async def handle_permission_response_simple_v2(self, session_id: str, approved: bool) -> bool:
        """
        简化的权限响应处理 - 用于非回调模式
        直接设置权限事件，不依赖待执行工具列表

        Args:
            session_id: 会话ID
            approved: 是否批准

        Returns:
            bool: 处理是否成功
        """
        context = self.get_execution_context(session_id)
        if not context:
            logger.error(f"No execution context found for session: {session_id}")
            return False

        try:
            if approved:
                # 用户批准
                context.update_state(AgentExecutionState.RUNNING, "用户已确认工具执行权限")
                logger.info(f"Permission approved for session: {session_id}")
            else:
                # 用户拒绝
                context.update_state(AgentExecutionState.PAUSED, "用户拒绝了工具执行权限")
                logger.info(f"Permission denied for session: {session_id}")

            # 设置权限事件，唤醒等待的工具执行
            context.permission_event.set()
            return True

        except Exception as e:
            logger.error(f"Error handling permission response: {e}")
            context.update_state(AgentExecutionState.ERROR, f"处理权限响应时发生错误: {str(e)}")
            return False

    async def check_permission_decision(self, session_id: str, request_id: str) -> Optional[bool]:
        """
        检查特定工具请求的权限决策

        Args:
            session_id: 会话ID
            request_id: 工具请求ID

        Returns:
            Optional[bool]: 权限决策结果，None表示还未决策
        """
        context = self.get_execution_context(session_id)
        if not context:
            return None

        return context.permission_decisions.get(request_id)

    async def wait_for_permission_by_request_id(self, session_id: str, request_id: str, timeout: int = 30) -> bool:
        """
        等待特定工具请求的权限确认

        Args:
            session_id: 会话ID
            request_id: 工具请求ID
            timeout: 超时时间（秒）

        Returns:
            bool: 是否获得权限
        """
        context = self.get_execution_context(session_id)
        if not context:
            return False

        original_timeout = timeout  # 保存原始超时时间

        try:
            # 等待权限事件或超时
            while timeout > 0:
                # 检查是否已有权限决策
                decision = await self.check_permission_decision(session_id, request_id)
                if decision is not None:
                    return decision

                # 等待权限事件（带超时）
                try:
                    await asyncio.wait_for(context.permission_event.wait(), timeout=1.0)
                    # 事件被设置，重新检查权限决策
                    context.permission_event.clear()  # 清除事件以便下次使用
                except asyncio.TimeoutError:
                    # 1秒超时，继续循环检查
                    timeout -= 1

        except Exception as e:
            logger.error(f"Error waiting for permission: {e}")

        # 超时处理
        await self._handle_permission_timeout_by_request_id(session_id, request_id, original_timeout)
        return False

    async def _handle_permission_timeout_by_request_id(self, session_id: str, request_id: str, original_timeout: int):
        """
        处理特定工具请求的权限确认超时

        Args:
            session_id: 会话ID
            request_id: 工具请求ID
            original_timeout: 原始超时时间（秒）
        """
        context = self.get_execution_context(session_id)
        if not context:
            return

        try:
            logger.warning(f"Permission timeout for session {session_id}, request_id {request_id} after {original_timeout}s")

            # 导入StreamNotifier以发送取消通知
            from copilot.core.stream_notifier import StreamNotifier

            # 记录权限决策为超时拒绝
            context.permission_decisions[request_id] = False

            # 发送工具执行状态通知：取消
            await StreamNotifier.send_tool_execution_status(
                session_id=session_id,
                request_id=request_id,
                tool_name="unknown",  # 工具名称会在调用处补充
                status="cancelled",
                error=f"权限请求超时（{original_timeout}秒），工具执行已取消",
            )

            # 更新执行上下文状态
            context.update_state(AgentExecutionState.PAUSED, f"权限确认超时，已取消工具执行 (request_id: {request_id[:8]})")

            logger.info(f"Tool request {request_id} cancelled due to permission timeout")

        except Exception as e:
            logger.error(f"Error handling permission timeout: {e}")
            context.update_state(AgentExecutionState.ERROR, f"处理权限超时时发生错误: {str(e)}")

    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        context = self.get_execution_context(session_id)
        if context:
            return context.to_dict()
        return None

    async def _cleanup_expired_contexts(self):
        """清理过期的执行上下文"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟清理一次

                current_time = datetime.now(UTC)
                expired_sessions = []

                for session_id, context in self.active_contexts.items():
                    # 清理30分钟未活动的上下文
                    if (current_time - context.updated_at).total_seconds() > 1800:
                        expired_sessions.append(session_id)

                for session_id in expired_sessions:
                    del self.active_contexts[session_id]
                    logger.info(f"Cleaned up expired execution context: {session_id}")

            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")

    async def wait_for_permission(self, session_id: str, timeout: int = 30) -> bool:
        """
        等待权限确认完成（向后兼容方法）

        注意：这个方法已弃用，建议使用 wait_for_permission_by_request_id

        Args:
            session_id: 会话ID
            timeout: 超时时间（秒）

        Returns:
            bool: 是否获得权限（或所有权限都已处理）
        """
        context = self.get_execution_context(session_id)
        if not context:
            return False

        # 🔥 关键修复：优先检查最终状态
        # 如果状态已经是COMPLETED或PAUSED，不需要等待
        if context.state in [AgentExecutionState.COMPLETED, AgentExecutionState.PAUSED]:
            logger.debug(f"Session {session_id} already in final state: {context.state.value}")
            return context.state == AgentExecutionState.COMPLETED

        # 检查是否真的需要等待权限确认
        # 如果没有pending_tools且状态不是WAITING_PERMISSION，说明没有权限请求
        if not context.pending_tools and context.state != AgentExecutionState.WAITING_PERMISSION:
            logger.debug(f"No permission requests pending for session {session_id}, returning True")
            return True

        try:
            await asyncio.wait_for(context.permission_event.wait(), timeout=timeout)

            # 检查是否有被拒绝的工具（如果有待执行工具的话）
            if context.pending_tools:
                rejected_tools = [tool for tool in context.pending_tools if tool.status == "rejected"]
                if rejected_tools:
                    return False

            # 检查上下文状态：如果状态为RUNNING或COMPLETED，说明权限被确认
            # 如果状态为PAUSED，说明权限被拒绝
            if context.state in [AgentExecutionState.RUNNING, AgentExecutionState.COMPLETED]:
                return True
            elif context.state == AgentExecutionState.PAUSED:
                return False

            return True

        except asyncio.TimeoutError:
            # 🔥 关键修复：如果没有权限请求而超时，直接返回True
            if not context.pending_tools and context.state != AgentExecutionState.WAITING_PERMISSION:
                logger.debug(f"Timeout but no permission requests for session {session_id}, returning True")
                return True
            
            # 处理超时情况
            await self._handle_permission_timeout(session_id, timeout)
            return False

    async def _handle_permission_timeout(self, session_id: str, timeout: int):
        """
        处理权限确认超时（向后兼容方法）

        Args:
            session_id: 会话ID
            timeout: 超时时间（秒）
        """
        context = self.get_execution_context(session_id)
        if not context:
            return

        try:
            # 获取所有超时的工具
            timeout_tools = [tool for tool in context.pending_tools if tool.status == "pending"]

            if timeout_tools:
                logger.warning(f"Permission timeout for session {session_id}: {len(timeout_tools)} tools cancelled after {timeout}s")

                # 导入StreamNotifier以发送取消通知
                from copilot.core.stream_notifier import StreamNotifier

                # 为每个超时工具发送取消通知
                for tool in timeout_tools:
                    # 更新工具状态为取消
                    tool.status = "timeout"

                    # 发送工具执行状态通知：取消
                    await StreamNotifier.send_tool_execution_status(
                        session_id=session_id,
                        request_id=tool.execution_id,
                        tool_name=tool.tool_name,
                        status="cancelled",
                        error=f"权限请求超时（{timeout}秒），工具执行已取消",
                    )

                    logger.info(f"Tool {tool.tool_name} cancelled due to permission timeout")

                # 清理所有超时的工具
                context.pending_tools = [tool for tool in context.pending_tools if tool.status != "timeout"]

                # 更新执行上下文状态
                if timeout_tools:
                    cancelled_names = [tool.tool_name for tool in timeout_tools]
                    context.update_state(
                        AgentExecutionState.PAUSED, f"权限确认超时，已取消 {len(timeout_tools)} 个工具的执行: {', '.join(cancelled_names)}"
                    )

                # 如果没有更多待确认的工具，设置完成事件
                if not context.pending_tools:
                    context.permission_event.set()

        except Exception as e:
            logger.error(f"Error handling permission timeout: {e}")
            context.update_state(AgentExecutionState.ERROR, f"处理权限超时时发生错误: {str(e)}")


# 全局实例
agent_state_manager = AgentStateManager()
