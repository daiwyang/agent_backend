import uuid
from datetime import datetime
from typing import List, Optional

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
