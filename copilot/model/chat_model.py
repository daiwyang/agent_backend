from datetime import datetime
from typing import Dict, List, Optional, Any

from pydantic import BaseModel


# Pydantic模型
class CreateSessionRequest(BaseModel):
    user_id: str
    window_id: Optional[str] = None


class CreateSessionResponse(BaseModel):
    session_id: str
    user_id: str
    window_id: str
    thread_id: str


class ChatRequest(BaseModel):
    session_id: str
    message: str
    enable_mcp_tools: Optional[bool] = True  # 默认启用MCP工具
    attachments: Optional[List[dict]] = None  # 多模态附件


class ChatResponse(BaseModel):
    session_id: str
    response: str
    timestamp: datetime


class SessionInfo(BaseModel):
    session_id: str
    user_id: str
    window_id: str
    created_at: datetime
    last_activity: datetime


class ChatMessage(BaseModel):
    message_id: Optional[str] = None  # MongoDB的_id字段转换而来
    role: str
    content: str
    timestamp: Optional[str] = None


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[ChatMessage]
    total_count: int


# 新增：多模态聊天请求模型
class MultiModalChatRequest(BaseModel):
    """多模态聊天请求模型，支持文本和图片"""

    session_id: str
    message: str
    attachments: Optional[List[Dict[str, str]]] = None  # 支持图片等附件


class ImageAttachment(BaseModel):
    """图片附件模型"""

    type: str = "image"  # image, file, etc.
    url: Optional[str] = None  # 图片URL
    base64: Optional[str] = None  # base64编码的图片数据
    mime_type: str = None  # 图片MIME类型，如image/jpeg, image/png等
    filename: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 20


class SearchResult(BaseModel):
    session_id: str
    role: str
    content: str
    timestamp: datetime


class CreateSessionRequestWithAuth(BaseModel):
    window_id: Optional[str] = None


# 新增：工具权限确认相关模型
class ToolPermissionRequest(BaseModel):
    """工具权限请求模型"""

    request_id: str
    tool_name: str
    tool_description: str
    parameters: Dict
    risk_level: str  # "low", "medium", "high"
    reasoning: Optional[str] = None  # 为什么需要这个工具


class ToolExecutionStatus(BaseModel):
    """工具执行状态模型"""

    request_id: str
    tool_name: str
    status: str  # "waiting", "executing", "completed", "failed", "cancelled"
    result: Optional[Any] = None  # 支持任意类型的工具结果：dict, str, list等
    error: Optional[str] = None
    progress: Optional[int] = None  # 0-100的进度百分比


class PermissionResponseRequest(BaseModel):
    """权限响应请求模型（用于HTTP API）"""

    session_id: str
    request_id: str
    approved: bool
    user_feedback: Optional[str] = None


# 聊天流消息基类
class ChatStreamMessage(BaseModel):
    """聊天流消息基类"""

    type: str
    session_id: str
    timestamp: Optional[datetime] = None

    def to_json_string(self) -> str:
        """转换为JSON字符串，用于流式输出"""
        import json

        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False)


class StartMessage(ChatStreamMessage):
    """聊天开始消息"""

    type: str = "start"


class ContentMessage(ChatStreamMessage):
    """聊天内容消息"""

    type: str = "content"
    content: str





class SystemMessage(ChatStreamMessage):
    """系统消息"""

    type: str = "system"
    content: str


class EndMessage(ChatStreamMessage):
    """聊天结束消息"""

    type: str = "end"
    message_ids: Optional[Dict[str, str]] = None


class ErrorMessage(ChatStreamMessage):
    """错误消息"""

    type: str = "error"
    content: str
    error_code: Optional[str] = None


class ToolPermissionRequestMessage(ChatStreamMessage):
    """工具权限请求消息"""

    type: str = "tool_permission_request"
    data: ToolPermissionRequest


class ToolExecutionStatusMessage(ChatStreamMessage):
    """工具执行状态消息"""

    type: str = "tool_execution_status"
    data: ToolExecutionStatus
