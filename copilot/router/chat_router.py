"""
基于FastAPI的多会话聊天API
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from copilot.core.session_manager import session_manager
from copilot.model.chat_model import (
    ChatHistoryResponse,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    CreateSessionRequestWithAuth,
    CreateSessionResponse,
    SearchRequest,
    SearchResult,
    SessionInfo,
)

# 导入简化的服务
from copilot.service.chat_service import ChatService
from copilot.service.stats_service import StatsService
from copilot.utils.auth import get_current_user_from_state
from copilot.utils.error_codes import ErrorCodes, ErrorHandler, raise_chat_error, raise_system_error, raise_validation_error
from copilot.utils.logger import logger

# 全局服务实例（延迟初始化）
chat_service = None
stats_service = StatsService()

# FastAPI应用
router = APIRouter(prefix="/chat")


async def get_chat_service():
    """获取聊天服务实例，如果未初始化则先初始化"""
    global chat_service
    if chat_service is None:
        try:
            chat_service = await ChatService.create()
            logger.info("ChatService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ChatService: {str(e)}")
            raise
    return chat_service


@router.get("/providers")
async def get_providers():
    """获取可用的LLM提供商信息"""
    try:
        service = await get_chat_service()
        return {"current_provider": service.get_provider_info(), "available_providers": service.get_available_providers()}
    except Exception as e:
        raise_system_error(f"获取提供商信息失败: {str(e)}")


@router.post("/providers/switch")
async def switch_provider(provider: str, model: Optional[str] = None, current_user: dict = Depends(get_current_user_from_state)):
    """切换LLM提供商"""
    try:
        # 验证用户权限（可以根据需要添加管理员检查）
        user_id = current_user.get("user_id")
        if not user_id:
            raise_validation_error("用户ID缺失")

        service = await get_chat_service()
        success = service.switch_provider(provider, model)
        if success:
            return {"success": True, "message": f"成功切换到提供商: {provider}", "provider_info": service.get_provider_info()}
        else:
            raise_chat_error(f"切换提供商失败: {provider}")

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise_system_error(f"切换提供商时发生错误: {str(e)}")


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequestWithAuth, current_user: dict = Depends(get_current_user_from_state)):
    """创建新的聊天会话"""
    try:
        # 从认证依赖获取当前用户ID
        user_id = current_user.get("user_id")
        if not user_id:
            raise_validation_error("用户ID缺失")

        service = await get_chat_service()
        session_id = await service.create_session(user_id, request.window_id)
        session = await session_manager.get_session(session_id)

        return CreateSessionResponse(session_id=session_id, user_id=session.user_id, window_id=session.window_id, thread_id=session.thread_id)
    except HTTPException:
        raise
    except Exception as e:
        raise ErrorHandler.handle_system_error(e, "创建聊天会话")


@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user_from_state),
):
    """统一的流式聊天接口"""
    try:
        # 验证session属于当前用户
        user_id = current_user.get("user_id")
        if not user_id:
            raise_validation_error("用户ID缺失")

        # 获取session并验证所有权
        session = await session_manager.get_session(request.session_id)
        if session is None:
            raise_chat_error(ErrorCodes.CHAT_SESSION_NOT_FOUND, "会话不存在")

        if session.user_id != user_id:
            raise_chat_error(ErrorCodes.CHAT_PERMISSION_DENIED, "无权访问此会话")

        # 始终返回流式响应
        return StreamingResponse(
            _generate_stream_response(request),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no", "Content-Encoding": "identity"},
        )

    except ValueError as e:
        raise_chat_error(ErrorCodes.CHAT_SESSION_NOT_FOUND, str(e))
    except Exception as e:
        raise ErrorHandler.handle_system_error(e, "聊天消息处理")


async def _generate_stream_response(request: ChatRequest):
    """生成流式响应的内部方法"""
    import asyncio
    import json

    try:
        # 发送开始事件
        start_data = json.dumps({"type": "start", "session_id": request.session_id}) + "\n"
        yield start_data.encode("utf-8")

        content_buffer = ""
        message_ids = None

        # 使用统一的流式聊天方法
        service = await get_chat_service()
        async for chunk in service.chat(
            session_id=request.session_id, message=request.message, attachments=request.attachments, enable_tools=request.enable_mcp_tools
        ):
            if "error" in chunk:
                error_data = json.dumps({"type": "error", "content": chunk["error"]}) + "\n"
                yield error_data.encode("utf-8")
                return
            elif "content" in chunk:
                content_buffer += chunk["content"]

                # 当缓冲区达到一定大小或遇到标点符号时发送数据
                if len(content_buffer) >= 5 or any(char in content_buffer for char in "，。！？；：\n"):
                    content_data = json.dumps({"type": "content", "content": content_buffer}) + "\n"
                    yield content_data.encode("utf-8")
                    content_buffer = ""
                    await asyncio.sleep(0)
            elif "finished" in chunk and chunk["finished"]:
                message_ids = chunk.get("message_ids", {})

        # 发送剩余的缓冲内容
        if content_buffer:
            content_data = json.dumps({"type": "content", "content": content_buffer}) + "\n"
            yield content_data.encode("utf-8")

        # 发送结束事件
        end_data = json.dumps({"type": "end", "session_id": request.session_id, "message_ids": message_ids}) + "\n"
        yield end_data.encode("utf-8")

    except Exception as e:
        error_data = json.dumps({"type": "error", "content": f"处理请求时出现错误: {str(e)}"}) + "\n"
        yield error_data.encode("utf-8")


@router.get("/sessions/{session_id}/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str,
    limit: int = Query(100, description="返回消息数量限制"),
    offset: int = Query(0, description="偏移量"),
):
    """获取会话的聊天历史"""
    try:
        service = await get_chat_service()
        messages = await service.get_chat_history(session_id)

        # 应用分页
        total_count = len(messages)
        paginated_messages = messages[offset : offset + limit]

        return ChatHistoryResponse(
            session_id=session_id,
            messages=[
                ChatMessage(message_id=msg.message_id, role=msg.role, content=msg.content, timestamp=msg.timestamp) for msg in paginated_messages
            ],
            total_count=total_count,
        )
    except Exception as e:
        raise ErrorHandler.handle_system_error(e, "获取聊天历史")


@router.get("/sessions")
async def get_user_sessions(
    current_user: dict = Depends(get_current_user_from_state),
    include_deleted: bool = Query(False, description="是否包含已删除的会话"),
    limit: int = Query(50, description="返回数量限制"),
):
    """获取当前用户的所有会话（包括活跃和非活跃的）"""
    try:
        # 从认证依赖获取当前用户ID
        user_id = current_user.get("user_id")
        if not user_id:
            raise_validation_error("用户ID缺失")

        # 直接从数据库查询所有会话
        from copilot.utils.mongo_client import get_mongo_manager

        mongo_manager = await get_mongo_manager()
        sessions_collection = await mongo_manager.get_collection("chat_sessions")

        # 构建查询条件
        query = {"user_id": user_id}
        if not include_deleted:
            query["status"] = {"$ne": "deleted"}

        cursor = sessions_collection.find(query).sort("last_activity", -1)
        if limit:
            cursor = cursor.limit(limit)

        sessions = await cursor.to_list(length=None)

        # 转换为响应格式
        result = []
        for session in sessions:
            result.append(
                {
                    "session_id": session["session_id"],
                    "user_id": session["user_id"],
                    "window_id": session["window_id"],
                    "thread_id": session["thread_id"],
                    "created_at": session["created_at"].isoformat(),
                    "last_activity": session["last_activity"].isoformat(),
                    "status": session.get("status", "available"),
                }
            )

        return {"user_id": user_id, "sessions": result, "total_count": len(result)}
    except HTTPException:
        raise
    except Exception as e:
        raise ErrorHandler.handle_system_error(e, "获取用户会话列表")


@router.get("/chat-history")
async def get_user_chat_history(current_user: dict = Depends(get_current_user_from_state)):
    """获取当前用户的所有聊天历史"""
    try:
        # 从认证依赖获取当前用户ID
        user_id = current_user.get("user_id")
        if not user_id:
            raise_validation_error("用户ID缺失")

        history = await stats_service.get_user_chat_history(user_id)
        return {"user_id": user_id, "sessions": history}
    except HTTPException:
        raise
    except Exception as e:
        raise ErrorHandler.handle_system_error(e, "获取用户聊天历史")


@router.post("/search")
async def search_chat_history(request: SearchRequest, current_user: dict = Depends(get_current_user_from_state)):
    """搜索当前用户的聊天历史"""
    try:
        # 从认证依赖获取当前用户ID
        user_id = current_user.get("user_id")
        if not user_id:
            raise_validation_error("用户ID缺失")

        results = await stats_service.search_chat_history(user_id, request.query, request.limit)

        return {
            "user_id": user_id,
            "query": request.query,
            "results": [
                SearchResult(session_id=result["session_id"], role=result["role"], content=result["content"], timestamp=result["timestamp"])
                for result in results
            ],
            "total_count": len(results),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise ErrorHandler.handle_system_error(e, "搜索聊天历史")


@router.get("/stats")
async def get_chat_stats(current_user: dict = Depends(get_current_user_from_state)):
    """获取当前用户的聊天统计信息"""
    try:
        # 从认证依赖获取当前用户ID
        user_id = current_user.get("user_id")
        if not user_id:
            raise_validation_error("用户ID缺失")

        stats = await stats_service.get_chat_stats(user_id)
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise ErrorHandler.handle_system_error(e, "获取聊天统计信息")


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, archive: bool = Query(True, description="是否归档到数据库")):
    """删除会话"""
    try:
        service = await get_chat_service()
        await service.delete_session(session_id)
        return {"message": f"Session deleted successfully (archived: {archive})"}
    except Exception as e:
        raise ErrorHandler.handle_system_error(e, "删除会话")


@router.get("/messages/{message_id}")
async def get_message_by_id(message_id: str, current_user: dict = Depends(get_current_user_from_state)):
    """根据消息ID获取具体的消息记录"""
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise_validation_error("用户ID缺失")

        # 获取消息详情
        service = await get_chat_service()
        message = await service.get_message_by_id(message_id, user_id)

        if not message:
            raise_validation_error("消息不存在或无权限访问")

        return {
            "message_id": message_id,
            "session_id": message.get("session_id"),
            "role": message.get("role"),
            "content": message.get("content"),
            "timestamp": message.get("timestamp"),
            "metadata": message.get("metadata", {}),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise_system_error(f"获取消息失败: {str(e)}")


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now()}
