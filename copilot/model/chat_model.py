import uuid
from datetime import datetime
from typing import Dict, List, Optional

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
