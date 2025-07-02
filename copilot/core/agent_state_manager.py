"""
Agent状态管理器 - 处理Agent执行状态、暂停/恢复和工具权限确认
"""

import asyncio
import uuid
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

from copilot.utils.logger import logger
from copilot.utils.websocket_manager import connection_manager


class AgentExecutionState(Enum):
    """Agent执行状态"""
    IDLE = "idle"                           # 空闲状态
    RUNNING = "running"                     # 正在执行
    WAITING_PERMISSION = "waiting_permission"  # 等待工具权限确认
    PAUSED = "paused"                       # 暂停执行
    COMPLETED = "completed"                 # 执行完成
    ERROR = "error"                         # 执行错误


class PendingToolExecution:
    """待执行的工具信息"""
    
    def __init__(self, tool_name: str, parameters: Dict[str, Any], 
                 callback: Callable, risk_level: str = "medium"):
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
            "status": self.status
        }


class AgentExecutionContext:
    """Agent执行上下文"""
    
    def __init__(self, session_id: str, thread_id: Optional[str] = None):
        self.session_id = session_id
        self.thread_id = thread_id
        self.execution_id = str(uuid.uuid4())
        self.state = AgentExecutionState.IDLE
        self.current_message = ""
        self.pending_tools: List[PendingToolExecution] = []
        self.execution_result = None
        self.error_message = None
        self.created_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        
        # 用于异步等待的事件
        self.permission_event = asyncio.Event()
        self.completion_event = asyncio.Event()
        
    def update_state(self, new_state: AgentExecutionState, 
                    message: Optional[str] = None, error: Optional[str] = None):
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
            "updated_at": self.updated_at.isoformat()
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
        
    def create_execution_context(self, session_id: str, 
                                thread_id: Optional[str] = None) -> AgentExecutionContext:
        """创建执行上下文"""
        context = AgentExecutionContext(session_id, thread_id)
        self.active_contexts[session_id] = context
        logger.info(f"Created execution context for session: {session_id}")
        return context
        
    def get_execution_context(self, session_id: str) -> Optional[AgentExecutionContext]:
        """获取执行上下文"""
        return self.active_contexts.get(session_id)
        
    async def request_tool_permission(self, session_id: str, tool_name: str, 
                                    parameters: Dict[str, Any], callback: Callable,
                                    risk_level: str = "medium") -> bool:
        """
        请求工具执行权限（非阻塞）
        
        Args:
            session_id: 会话ID
            tool_name: 工具名称
            parameters: 工具参数
            callback: 工具执行回调函数
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
            try:
                await callback()
                return True
            except Exception as e:
                logger.error(f"Low-risk tool execution failed: {e}")
                return False
                
        # 中高风险工具需要用户确认
        pending_tool = PendingToolExecution(tool_name, parameters, callback, risk_level)
        context.pending_tools.append(pending_tool)
        context.update_state(AgentExecutionState.WAITING_PERMISSION, 
                           f"等待用户确认工具执行: {tool_name}")
        
        # 通知前端
        await self._notify_permission_request(context, pending_tool)
        
        # 设置等待状态，但不阻塞
        context.permission_event.clear()
        
        return False  # 返回False表示需要等待权限确认
        
    async def handle_permission_response(self, session_id: str, execution_id: str, 
                                       approved: bool) -> bool:
        """
        处理用户权限响应
        
        Args:
            session_id: 会话ID
            execution_id: 工具执行ID
            approved: 是否批准
            
        Returns:
            bool: 处理是否成功
        """
        context = self.get_execution_context(session_id)
        if not context:
            logger.error(f"No execution context found for session: {session_id}")
            return False
            
        # 查找对应的待执行工具
        pending_tool = None
        for tool in context.pending_tools:
            if tool.execution_id == execution_id:
                pending_tool = tool
                break
                
        if not pending_tool:
            logger.error(f"Pending tool not found: {execution_id}")
            return False
            
        try:
            if approved:
                # 执行工具
                result = await pending_tool.callback()
                pending_tool.status = "approved"
                context.update_state(AgentExecutionState.RUNNING, "继续执行...")
                logger.info(f"Tool executed successfully: {pending_tool.tool_name}")
            else:
                # 用户拒绝
                pending_tool.status = "rejected"
                context.update_state(AgentExecutionState.PAUSED, "用户拒绝了工具执行")
                
            # 从待执行列表中移除
            context.pending_tools.remove(pending_tool)
            
            # 如果没有更多待确认的工具，设置事件
            if not context.pending_tools:
                context.permission_event.set()
                
            # 通知前端处理结果
            await self._notify_permission_result(context, pending_tool, approved)
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling permission response: {e}")
            pending_tool.status = "error"
            context.update_state(AgentExecutionState.ERROR, f"工具执行错误: {str(e)}")
            return False
            
    async def wait_for_permission(self, session_id: str, timeout: int = 300) -> bool:
        """
        等待权限确认完成
        
        Args:
            session_id: 会话ID
            timeout: 超时时间（秒）
            
        Returns:
            bool: 是否获得权限（或所有权限都已处理）
        """
        context = self.get_execution_context(session_id)
        if not context:
            return False
            
        try:
            await asyncio.wait_for(context.permission_event.wait(), timeout=timeout)
            
            # 检查是否有被拒绝的工具
            rejected_tools = [tool for tool in context.pending_tools if tool.status == "rejected"]
            if rejected_tools:
                return False
                
            return True
            
        except asyncio.TimeoutError:
            context.update_state(AgentExecutionState.ERROR, "工具权限确认超时")
            logger.warning(f"Permission timeout for session: {session_id}")
            return False
            
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        context = self.get_execution_context(session_id)
        if context:
            return context.to_dict()
        return None
        
    async def _notify_permission_request(self, context: AgentExecutionContext, 
                                       pending_tool: PendingToolExecution):
        """通知前端权限请求"""
        message = {
            "type": "agent_tool_permission_request",
            "data": {
                "session_id": context.session_id,
                "execution_id": pending_tool.execution_id,
                "tool_name": pending_tool.tool_name,
                "parameters": pending_tool.parameters,
                "risk_level": pending_tool.risk_level,
                "message": f"Agent想要执行工具: {pending_tool.tool_name}"
            }
        }
        
        await connection_manager.send_to_session(context.session_id, message)
        logger.info(f"Sent permission request for tool: {pending_tool.tool_name}")
        
    async def _notify_permission_result(self, context: AgentExecutionContext,
                                      pending_tool: PendingToolExecution, approved: bool):
        """通知前端权限处理结果"""
        message = {
            "type": "agent_tool_permission_result",
            "data": {
                "session_id": context.session_id,
                "execution_id": pending_tool.execution_id,
                "tool_name": pending_tool.tool_name,
                "approved": approved,
                "status": pending_tool.status
            }
        }
        
        await connection_manager.send_to_session(context.session_id, message)
        logger.info(f"Sent permission result for tool: {pending_tool.tool_name} -> {approved}")
        
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


# 全局实例
agent_state_manager = AgentStateManager() 