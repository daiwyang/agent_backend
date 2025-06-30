"""
WebSocket路由 - 处理实时通信
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from copilot.utils.websocket_manager import handle_websocket_connection
from copilot.utils.logger import logger

router = APIRouter()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket端点 - 用于实时通信和工具权限确认"""
    try:
        await handle_websocket_connection(websocket, session_id)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")


@router.websocket("/ws")
async def websocket_endpoint_with_query(websocket: WebSocket, session_id: str = Query(...)):
    """WebSocket端点 - 使用查询参数"""
    try:
        await handle_websocket_connection(websocket, session_id)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
