"""
MCP 工具执行同意管理器
处理用户对工具执行的同意/拒绝逻辑
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from copilot.utils.logger import logger
from copilot.utils.redis_client import redis_client


class ToolPermissionStatus(Enum):
    """工具执行权限状态"""

    PENDING = "pending"  # 等待用户确认
    APPROVED = "approved"  # 用户同意
    REJECTED = "rejected"  # 用户拒绝
    EXPIRED = "expired"  # 请求过期
    TIMEOUT = "timeout"  # 等待超时


class ToolExecutionRequest:
    """工具执行请求"""

    def __init__(self, session_id: str, tool_name: str, tool_description: str, parameters: Dict[str, Any], risk_level: str = "medium"):
        self.request_id = str(uuid.uuid4())
        self.session_id = session_id
        self.tool_name = tool_name
        self.tool_description = tool_description
        self.parameters = parameters
        self.risk_level = risk_level
        self.created_at = datetime.now(datetime.UTC)  # 使用UTC时间
        self.status = ToolPermissionStatus.PENDING
        self.user_response = None
        self.expiry_time = self.created_at + timedelta(minutes=5)  # 5分钟过期

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "tool_description": self.tool_description,
            "parameters": self.parameters,
            "risk_level": self.risk_level,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "expiry_time": self.expiry_time.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolExecutionRequest":
        """从字典创建实例"""
        request = cls.__new__(cls)
        request.request_id = data["request_id"]
        request.session_id = data["session_id"]
        request.tool_name = data["tool_name"]
        request.tool_description = data["tool_description"]
        request.parameters = data["parameters"]
        request.risk_level = data["risk_level"]
        request.created_at = datetime.fromisoformat(data["created_at"])
        request.status = ToolPermissionStatus(data["status"])
        request.expiry_time = datetime.fromisoformat(data["expiry_time"])
        return request


class ToolPermissionManager:
    """工具执行权限管理器"""

    def __init__(self):
        self.pending_requests: Dict[str, ToolExecutionRequest] = {}
        self.approval_events: Dict[str, asyncio.Event] = {}
        self.cleanup_task = None

    async def start(self):
        """启动权限管理器"""
        self.cleanup_task = asyncio.create_task(self._cleanup_expired_requests())
        logger.info("ToolPermissionManager started")

    async def stop(self):
        """停止权限管理器"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("ToolPermissionManager stopped")

    async def request_tool_permission(
        self, session_id: str, tool_name: str, tool_description: str, parameters: Dict[str, Any], risk_level: str = "medium", timeout: int = 300
    ) -> bool:
        """
        请求工具执行权限

        Args:
            session_id: 会话ID
            tool_name: 工具名称
            tool_description: 工具描述
            parameters: 工具参数
            risk_level: 风险级别 (low, medium, high)
            timeout: 等待超时时间（秒）

        Returns:
            bool: 是否获得权限
        """
        # 创建执行请求
        request = ToolExecutionRequest(
            session_id=session_id, tool_name=tool_name, tool_description=tool_description, parameters=parameters, risk_level=risk_level
        )

        # 存储请求
        self.pending_requests[request.request_id] = request

        # 创建等待事件
        approval_event = asyncio.Event()
        self.approval_events[request.request_id] = approval_event

        try:
            # 存储到Redis以便前端获取
            await self._store_request_to_redis(request)

            # 发送通知给前端
            await self._notify_frontend(request)

            logger.info(f"Tool permission requested: {tool_name} for session {session_id}")

            # 等待用户响应或超时
            try:
                await asyncio.wait_for(approval_event.wait(), timeout=timeout)

                # 检查最终状态
                if request.status == ToolPermissionStatus.APPROVED:
                    logger.info(f"Tool permission approved: {tool_name}")
                    return True
                else:
                    logger.info(f"Tool permission rejected: {tool_name}")
                    return False

            except asyncio.TimeoutError:
                request.status = ToolPermissionStatus.TIMEOUT
                logger.warning(f"Tool permission timeout: {tool_name}")
                return False

        finally:
            # 清理资源
            self.pending_requests.pop(request.request_id, None)
            self.approval_events.pop(request.request_id, None)
            await self._remove_request_from_redis(request.request_id)

    async def handle_user_response(self, request_id: str, approved: bool, session_id: str = None) -> bool:
        """
        处理用户响应

        Args:
            request_id: 请求ID
            approved: 是否同意
            session_id: 会话ID（用于验证）

        Returns:
            bool: 处理是否成功
        """
        request = self.pending_requests.get(request_id)
        if not request:
            logger.warning(f"Tool permission request not found: {request_id}")
            return False

        # 验证会话ID
        if session_id and request.session_id != session_id:
            logger.warning(f"Session ID mismatch for request: {request_id}")
            return False

        # 检查请求是否过期
        if datetime.now(datetime.UTC) > request.expiry_time:
            request.status = ToolPermissionStatus.EXPIRED
            logger.warning(f"Tool permission request expired: {request_id}")
            return False

        # 更新状态
        request.status = ToolPermissionStatus.APPROVED if approved else ToolPermissionStatus.REJECTED
        request.user_response = approved

        # 触发等待事件
        event = self.approval_events.get(request_id)
        if event:
            event.set()

        logger.info(f"Tool permission response: {request_id} -> {'approved' if approved else 'rejected'}")
        return True

    async def get_pending_requests(self, session_id: str) -> List[Dict[str, Any]]:
        """获取指定会话的待处理请求"""
        requests = []
        for request in self.pending_requests.values():
            if (
                request.session_id == session_id
                and request.status == ToolPermissionStatus.PENDING
                and datetime.now(datetime.UTC) <= request.expiry_time
            ):
                requests.append(request.to_dict())
        return requests

    async def _store_request_to_redis(self, request: ToolExecutionRequest):
        """将请求存储到Redis"""
        try:
            key = f"tool_permission:{request.session_id}:{request.request_id}"
            await redis_client.setex(key, 300, request.to_dict())  # 5分钟过期
        except Exception as e:
            logger.error(f"Failed to store request to Redis: {e}")

    async def _remove_request_from_redis(self, request_id: str):
        """从Redis中移除请求"""
        try:
            # 查找并删除
            pattern = f"tool_permission:*:{request_id}"
            keys = await redis_client.keys(pattern)
            if keys:
                await redis_client.delete(*keys)
        except Exception as e:
            logger.error(f"Failed to remove request from Redis: {e}")

    async def _notify_frontend(self, request: ToolExecutionRequest):
        """通知前端有新的工具执行请求"""
        try:
            # 这里可以通过WebSocket、Server-Sent Events等方式通知前端
            # 或者通过Redis发布订阅模式
            channel = f"tool_permission_notifications:{request.session_id}"
            message = {"type": "tool_permission_request", "data": request.to_dict()}
            await redis_client.publish(channel, message)
            logger.info(f"Frontend notification sent for request: {request.request_id}")
        except Exception as e:
            logger.error(f"Failed to notify frontend: {e}")

    async def _cleanup_expired_requests(self):
        """定期清理过期的请求"""
        while True:
            try:
                current_time = datetime.utcnow()
                expired_requests = []

                for request_id, request in self.pending_requests.items():
                    if current_time > request.expiry_time and request.status == ToolPermissionStatus.PENDING:
                        request.status = ToolPermissionStatus.EXPIRED
                        expired_requests.append(request_id)

                        # 触发等待事件，让等待的协程知道请求已过期
                        event = self.approval_events.get(request_id)
                        if event:
                            event.set()

                if expired_requests:
                    logger.info(f"Cleaned up {len(expired_requests)} expired tool permission requests")

                # 每30秒检查一次
                await asyncio.sleep(30)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(30)


# 全局实例
tool_permission_manager = ToolPermissionManager()
