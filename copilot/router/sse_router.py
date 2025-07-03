"""
Server-Sent Events (SSE) 路由 - 优化版本
基于Redis发布订阅的高性能实时推送方案
"""

import asyncio
import json
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sse_starlette import EventSourceResponse

from copilot.core.simple_notifier import SimpleNotifier
from copilot.utils.auth import UserSession, get_authenticated_user
from copilot.utils.logger import logger
from copilot.utils.redis_client import redis_client


# SSE专用认证依赖函数
async def get_sse_user_session(request: Request, token: str = None) -> UserSession:
    """SSE专用的用户认证依赖函数"""
    return await get_authenticated_user(request, None, token)


async def verify_chat_session_access(chat_session_id: str, user_session: UserSession) -> bool:
    """
    验证用户是否有权限访问指定的聊天会话

    Args:
        chat_session_id: 聊天会话ID（路径参数）
        user_session: 认证后的用户会话信息

    Returns:
        bool: 是否有权限访问
    """
    try:
        # 从会话管理器获取聊天会话信息
        from copilot.core.session_manager import session_manager

        session_info = await session_manager.get_session(chat_session_id)
        if not session_info:
            logger.warning(f"Chat session {chat_session_id} not found")
            return False

        # 检查聊天会话是否属于当前用户
        if session_info.user_id != user_session.user_id:
            logger.warning(f"User {user_session.user_id} tried to access chat session {chat_session_id} owned by {session_info.user_id}")
            return False

        return True

    except Exception as e:
        logger.error(f"Error verifying chat session access: {e}")
        return False


async def get_sse_user_with_chat_permission(chat_session_id: str, request: Request, token: str = None) -> UserSession:
    """
    SSE专用认证依赖函数，同时验证聊天会话权限

    Args:
        chat_session_id: 聊天会话ID
        request: 请求对象
        token: 可选的token参数

    Returns:
        UserSession: 认证后的用户会话信息

    Raises:
        HTTPException: 401 认证失败 或 403 无权限访问
    """
    # 先进行用户认证
    user_session = await get_authenticated_user(request, None, token)

    # 再验证聊天会话权限
    has_access = await verify_chat_session_access(chat_session_id, user_session)
    if not has_access:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问该聊天会话")

    return user_session


router = APIRouter(prefix="/api/sse", tags=["SSE推送"])


class PermissionResponse(BaseModel):
    """权限响应模型"""

    approved: bool
    reason: str = ""


class SSEEventManager:
    """SSE事件管理器 - 处理Redis订阅和事件分发"""

    def __init__(self):
        self.subscribers = {}  # session_id -> list of queues
        self.pubsub_task = None

    async def start(self):
        """启动Redis订阅"""
        if self.pubsub_task is None:
            self.pubsub_task = asyncio.create_task(self._redis_subscriber())
            logger.info("SSE Event Manager started")

    async def stop(self):
        """停止Redis订阅"""
        if self.pubsub_task:
            self.pubsub_task.cancel()
            try:
                await self.pubsub_task
            except asyncio.CancelledError:
                pass
            self.pubsub_task = None
            logger.info("SSE Event Manager stopped")

    async def subscribe_session(self, session_id: str) -> asyncio.Queue:
        """为会话订阅事件"""
        if session_id not in self.subscribers:
            self.subscribers[session_id] = []

        event_queue = asyncio.Queue(maxsize=100)
        self.subscribers[session_id].append(event_queue)

        logger.info(f"SSE subscription added for session: {session_id}")
        return event_queue

    async def unsubscribe_session(self, session_id: str, event_queue: asyncio.Queue):
        """取消会话的事件订阅"""
        if session_id in self.subscribers:
            try:
                self.subscribers[session_id].remove(event_queue)
                if not self.subscribers[session_id]:
                    del self.subscribers[session_id]
                logger.info(f"SSE subscription removed for session: {session_id}")
            except ValueError:
                pass

    async def notify_session(self, session_id: str, event_data: dict):
        """向指定会话发送事件"""
        if session_id in self.subscribers:
            disconnected_queues = []

            for queue in self.subscribers[session_id]:
                try:
                    # 非阻塞放入队列，如果队列满了就跳过旧消息
                    if queue.full():
                        try:
                            queue.get_nowait()  # 移除最旧的消息
                        except asyncio.QueueEmpty:
                            pass
                    queue.put_nowait(event_data)
                except Exception as e:
                    logger.warning(f"Failed to notify SSE queue: {e}")
                    disconnected_queues.append(queue)

            # 清理断开的队列
            for queue in disconnected_queues:
                await self.unsubscribe_session(session_id, queue)

    async def _redis_subscriber(self):
        """Redis订阅处理器"""
        try:
            pubsub = redis_client.pubsub()
            await pubsub.subscribe("sse_events")

            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        event_data = json.loads(message["data"])
                        session_id = event_data.get("session_id")

                        if session_id:
                            await self.notify_session(session_id, event_data)

                    except Exception as e:
                        logger.error(f"Error processing Redis message: {e}")

        except Exception as e:
            logger.error(f"Redis subscriber error: {e}")


# 全局SSE事件管理器
sse_manager = SSEEventManager()


async def event_stream(session_id: str, event_queue: asyncio.Queue) -> AsyncGenerator[str, None]:
    """
    SSE事件流生成器 - 优化版本
    基于队列和Redis订阅的高性能事件流
    """
    heartbeat_interval = 30  # 30秒心跳
    last_heartbeat = time.time()

    try:
        # 发送初始状态
        await _send_initial_state(session_id, event_queue)

        while True:
            try:
                current_time = time.time()

                # 检查是否需要发送心跳
                if current_time - last_heartbeat >= heartbeat_interval:
                    heartbeat_event = {"type": "heartbeat", "timestamp": current_time}
                    yield f"data: {json.dumps(heartbeat_event)}\n\n"
                    last_heartbeat = current_time

                # 等待事件或超时
                try:
                    event_data = await asyncio.wait_for(event_queue.get(), timeout=5.0)
                    yield f"data: {json.dumps(event_data)}\n\n"
                except asyncio.TimeoutError:
                    # 超时，继续循环检查心跳
                    continue

            except Exception as e:
                logger.error(f"Error in SSE event stream: {e}")
                error_event = {"type": "error", "message": str(e)}
                yield f"data: {json.dumps(error_event)}\n\n"
                await asyncio.sleep(2)

    except asyncio.CancelledError:
        logger.info(f"SSE stream cancelled for session: {session_id}")
        raise
    finally:
        # 清理订阅
        await sse_manager.unsubscribe_session(session_id, event_queue)


async def _send_initial_state(session_id: str, event_queue: asyncio.Queue):
    """发送初始状态"""
    try:
        # 获取当前状态
        tool_status = await SimpleNotifier.get_tool_status(session_id)
        permission_request = await SimpleNotifier.get_permission_request(session_id)
        tool_result = await SimpleNotifier.get_tool_result(session_id)

        # 发送存在的状态
        if tool_status:
            await event_queue.put({"type": "tool_status", "data": tool_status})

        if permission_request:
            await event_queue.put({"type": "permission_request", "data": permission_request})

        if tool_result:
            await event_queue.put({"type": "tool_result", "data": tool_result})

    except Exception as e:
        logger.warning(f"Failed to send initial state: {e}")


# SSE管理器的启动和关闭在main.py的lifespan中处理


@router.get("/events/{chat_session_id}")
async def sse_events(chat_session_id: str, request: Request, token: str = Query(None, description="认证token（可选，用于EventSource）")):
    """
    建立SSE连接，推送实时事件

    Args:
        chat_session_id: 聊天会话ID（标识具体的对话会话）
        token: 可选的认证token（用于JavaScript EventSource API）
    """
    try:
        # 进行用户认证并验证聊天会话权限
        user_session = await get_sse_user_with_chat_permission(chat_session_id, request, token)

        # 为聊天会话创建事件队列
        event_queue = await sse_manager.subscribe_session(chat_session_id)

        logger.info(f"SSE connection established for chat session: {chat_session_id}")

        return EventSourceResponse(
            event_stream(chat_session_id, event_queue),
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用nginx缓冲
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error establishing SSE connection: {e}")
        raise HTTPException(status_code=500, detail="建立SSE连接失败")


@router.post("/permission-response/{chat_session_id}")
async def submit_permission_response_sse(
    chat_session_id: str, response: PermissionResponse, request: Request, token: str = Query(None, description="认证token")
):
    """
    通过HTTP POST提交权限响应（配合SSE使用）

    Args:
        chat_session_id: 聊天会话ID
        response: 权限响应数据
        token: 认证token
    """
    try:
        # 进行用户认证并验证聊天会话权限
        user_session = await get_sse_user_with_chat_permission(chat_session_id, request, token)

        # 处理权限响应
        from copilot.core.agent_state_manager import agent_state_manager

        success = await agent_state_manager.handle_permission_response_simple(session_id=chat_session_id, approved=response.approved)

        if success:
            # 清除权限请求
            await SimpleNotifier.clear_permission_request(chat_session_id)

            # 通过SSE推送响应结果
            await sse_manager.notify_session(
                chat_session_id,
                {"type": "permission_response_result", "data": {"approved": response.approved, "reason": response.reason, "processed": True}},
            )

            return {"success": True, "message": "权限响应已处理"}
        else:
            return {"success": False, "message": "没有待处理的权限请求"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting permission response: {e}")
        raise HTTPException(status_code=500, detail="提交权限响应失败")


@router.get("/health/{chat_session_id}")
async def sse_health_check(chat_session_id: str, request: Request, token: str = Query(None, description="认证token")):
    """
    SSE健康检查端点

    Args:
        chat_session_id: 聊天会话ID
        token: 认证token
    """
    try:
        # 进行用户认证并验证聊天会话权限
        user_session = await get_sse_user_with_chat_permission(chat_session_id, request, token)

        subscriber_count = len(sse_manager.subscribers.get(chat_session_id, []))

        return {
            "success": True,
            "data": {
                "chat_session_id": chat_session_id,
                "user_id": user_session.user_id,
                "connected": subscriber_count > 0,
                "subscriber_count": subscriber_count,
                "manager_status": "running" if sse_manager.pubsub_task else "stopped",
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in SSE health check: {e}")
        raise HTTPException(status_code=500, detail="SSE健康检查失败")
