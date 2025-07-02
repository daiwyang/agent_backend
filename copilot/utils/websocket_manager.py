"""
WebSocket处理器 - 用于实时通知和Agent执行状态管理
"""

import json
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from copilot.utils.logger import logger
from copilot.utils.redis_client import redis_client


class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        # session_id -> Set[WebSocket]
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """建立WebSocket连接"""
        await websocket.accept()

        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()

        self.active_connections[session_id].add(websocket)
        logger.info(f"WebSocket connected for session: {session_id}")

        # 订阅Redis通知频道
        await self._subscribe_to_notifications(session_id)

    def disconnect(self, websocket: WebSocket, session_id: str):
        """断开WebSocket连接"""
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)

            # 如果该会话没有其他连接，清理
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

        logger.info(f"WebSocket disconnected for session: {session_id}")

    async def send_to_session(self, session_id: str, message: dict):
        """向指定会话的所有连接发送消息"""
        if session_id in self.active_connections:
            connections_to_remove = set()

            for connection in self.active_connections[session_id].copy():
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as e:
                    logger.warning(f"Failed to send message to WebSocket: {e}")
                    connections_to_remove.add(connection)

            # 清理失效连接
            for connection in connections_to_remove:
                self.active_connections[session_id].discard(connection)

    async def _subscribe_to_notifications(self, session_id: str):
        """订阅Redis通知"""
        try:
            # 这里实现Redis发布订阅逻辑
            # 实际使用中需要在后台任务中处理
            pass
        except Exception as e:
            logger.error(f"Failed to subscribe to notifications: {e}")


# 全局连接管理器
connection_manager = ConnectionManager()


class WebSocketMessage(BaseModel):
    """WebSocket消息模型"""

    type: str
    data: dict


async def handle_websocket_connection(websocket: WebSocket, session_id: str):
    """处理WebSocket连接"""
    await connection_manager.connect(websocket, session_id)

    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            message = json.loads(data)

            await handle_websocket_message(websocket, session_id, message)

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        connection_manager.disconnect(websocket, session_id)


async def handle_websocket_message(websocket: WebSocket, session_id: str, message: dict):
    """处理WebSocket消息"""
    try:
        msg_type = message.get("type")
        data = message.get("data", {})

        if msg_type == "agent_tool_permission_response":
            # 处理Agent工具权限响应
            execution_id = data.get("execution_id")
            approved = data.get("approved", False)
            
            # 导入agent_state_manager
            from copilot.core.agent_state_manager import agent_state_manager
            
            success = await agent_state_manager.handle_permission_response(
                session_id=session_id,
                execution_id=execution_id,
                approved=approved
            )
            
            # 发送确认
            response = {
                "type": "agent_tool_permission_response_ack",
                "data": {
                    "execution_id": execution_id,
                    "success": success,
                    "approved": approved
                }
            }
            await websocket.send_text(json.dumps(response))

        elif msg_type == "get_agent_status":
            # 获取Agent执行状态
            from copilot.core.agent_state_manager import agent_state_manager
            
            status = agent_state_manager.get_session_status(session_id)
            response = {"type": "agent_status", "data": {"status": status}}
            await websocket.send_text(json.dumps(response))

        elif msg_type == "ping":
            # 心跳检测
            response = {"type": "pong", "data": {"timestamp": data.get("timestamp")}}
            await websocket.send_text(json.dumps(response))
        
        else:
            # 未知消息类型
            logger.warning(f"Unknown WebSocket message type: {msg_type}")
            error_response = {"type": "error", "data": {"message": f"Unknown message type: {msg_type}"}}
            await websocket.send_text(json.dumps(error_response))

    except Exception as e:
        logger.error(f"Error handling WebSocket message: {e}")

        # 发送错误响应
        error_response = {"type": "error", "data": {"message": str(e)}}
        await websocket.send_text(json.dumps(error_response))


async def notify_tool_permission_request(session_id: str, request_data: dict):
    """通知前端有新的工具权限请求"""
    message = {"type": "tool_permission_request", "data": request_data}
    await connection_manager.send_to_session(session_id, message)


async def notify_tool_execution_result(session_id: str, result_data: dict):
    """通知前端工具执行结果"""
    message = {"type": "tool_execution_result", "data": result_data}
    await connection_manager.send_to_session(session_id, message)
