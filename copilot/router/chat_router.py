"""
基于FastAPI的多会话聊天API
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

# 导入实际的会话管理器和Agent
from copilot.agent.multi_session_agent import MultiSessionAgent
from copilot.agent.session_manager import session_manager
from copilot.model.chat_model import (
    ChatHistoryResponse,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    SearchRequest,
    SearchResult,
    SessionInfo,
)

# 创建全局Agent实例
agent = MultiSessionAgent()

# FastAPI应用
router = APIRouter(prefix="/chat")


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """创建新的聊天会话"""
    try:
        session_id = await agent.create_session(request.user_id, request.window_id)
        session = await session_manager.get_session(session_id)

        return CreateSessionResponse(session_id=session_id, user_id=session.user_id, window_id=session.window_id, thread_id=session.thread_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """发送聊天消息"""
    try:
        response = await agent.chat(request.session_id, request.message)

        # 取第一个响应消息
        response_text = response.messages[0].content if response.messages else "无响应"

        return ChatResponse(session_id=request.session_id, response=response_text, timestamp=datetime.now())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str,
    from_db: bool = Query(False, description="是否从数据库获取完整历史"),
    limit: int = Query(100, description="返回消息数量限制"),
    offset: int = Query(0, description="偏移量"),
):
    """获取会话的聊天历史"""
    try:
        messages = await agent.get_chat_history(session_id, from_db=from_db)

        # 应用分页
        total_count = len(messages)
        paginated_messages = messages[offset : offset + limit]

        return ChatHistoryResponse(
            session_id=session_id,
            messages=[ChatMessage(role=msg.role, content=msg.content, timestamp=msg.timestamp) for msg in paginated_messages],
            total_count=total_count,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}/sessions", response_model=List[SessionInfo])
async def get_user_sessions(user_id: str):
    """获取用户的所有活跃会话"""
    try:
        sessions = await agent.get_user_sessions(user_id)
        return [
            SessionInfo(
                session_id=session.session_id,
                user_id=session.user_id,
                window_id=session.window_id,
                created_at=session.created_at,
                last_activity=session.last_activity,
            )
            for session in sessions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}/chat-history")
async def get_user_chat_history(user_id: str):
    """获取用户的所有聊天历史"""
    try:
        history = await agent.get_user_chat_history(user_id)
        return {"user_id": user_id, "sessions": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_chat_history(request: SearchRequest):
    """搜索用户的聊天历史"""
    try:
        results = await agent.search_chat_history(request.user_id, request.query, request.limit)

        return {
            "user_id": request.user_id,
            "query": request.query,
            "results": [
                SearchResult(session_id=result["session_id"], role=result["role"], content=result["content"], timestamp=result["timestamp"])
                for result in results
            ],
            "total_count": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_chat_stats(user_id: Optional[str] = Query(None, description="用户ID（可选）")):
    """获取聊天统计信息"""
    try:
        stats = await agent.get_chat_stats(user_id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, archive: bool = Query(True, description="是否归档到数据库")):
    """删除会话"""
    try:
        await agent.delete_session(session_id)
        return {"message": f"Session deleted successfully (archived: {archive})"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now()}
