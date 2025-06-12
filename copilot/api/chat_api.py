"""
基于FastAPI的多会话聊天API
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import uuid
from datetime import datetime

# 简化版的会话管理器（生产环境应该使用Redis）
class InMemorySessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.user_sessions: Dict[str, List[str]] = {}  # user_id -> [session_ids]
    
    async def create_session(self, user_id: str, window_id: str = None) -> str:
        session_id = str(uuid.uuid4())
        thread_id = f"{user_id}_{session_id}"
        
        if window_id is None:
            window_id = str(uuid.uuid4())
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "window_id": window_id,
            "thread_id": thread_id,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "context": {}
        }
        
        self.sessions[session_id] = session_data
        
        # 维护用户会话列表
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = []
        self.user_sessions[user_id].append(session_id)
        
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        session = self.sessions.get(session_id)
        if session:
            session["last_activity"] = datetime.now()
        return session
    
    async def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        session_ids = self.user_sessions.get(user_id, [])
        return [self.sessions[sid] for sid in session_ids if sid in self.sessions]
    
    async def delete_session(self, session_id: str):
        if session_id in self.sessions:
            user_id = self.sessions[session_id]["user_id"]
            del self.sessions[session_id]
            
            if user_id in self.user_sessions:
                self.user_sessions[user_id] = [
                    sid for sid in self.user_sessions[user_id] if sid != session_id
                ]


# 全局会话管理器
session_manager = InMemorySessionManager()

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

# FastAPI应用
app = FastAPI(title="Multi-Session Chat API", version="1.0.0")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/sessions", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """创建新的聊天会话"""
    try:
        session_id = await session_manager.create_session(
            request.user_id, request.window_id
        )
        session = await session_manager.get_session(session_id)
        
        return CreateSessionResponse(
            session_id=session_id,
            user_id=session["user_id"],
            window_id=session["window_id"],
            thread_id=session["thread_id"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """发送聊天消息"""
    session = await session_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        # 这里应该调用您的Agent
        # 为了演示，我们返回一个模拟响应
        response_text = f"收到消息: {request.message}"
        
        # 如果消息包含天气相关词汇，返回天气信息
        if "天气" in request.message:
            if "北京" in request.message:
                response_text = "北京今天晴天，温度25°C"
            elif "上海" in request.message:
                response_text = "上海今天多云，温度22°C"
            else:
                response_text = "请告诉我您想查询哪个城市的天气？"
        
        return ChatResponse(
            session_id=request.session_id,
            response=response_text,
            timestamp=datetime.now()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/sessions", response_model=List[SessionInfo])
async def get_user_sessions(user_id: str):
    """获取用户的所有会话"""
    try:
        sessions = await session_manager.get_user_sessions(user_id)
        return [
            SessionInfo(
                session_id=session["session_id"],
                user_id=session["user_id"],
                window_id=session["window_id"],
                created_at=session["created_at"],
                last_activity=session["last_activity"]
            )
            for session in sessions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    try:
        await session_manager.delete_session(session_id)
        return {"message": "Session deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now()}

if __name__ == "__main__":
    import uvicorn
    print("🚀 启动多会话聊天API服务器...")
    print("📖 API文档: http://localhost:8000/docs")
    print("💡 使用示例:")
    print("   1. POST /sessions - 创建会话")
    print("   2. POST /chat - 发送消息")
    print("   3. GET /users/{user_id}/sessions - 获取用户会话")
    uvicorn.run(app, host="0.0.0.0", port=8000)
