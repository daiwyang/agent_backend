"""
改进的多轮对话示例，支持多会话管理
"""
import asyncio
import os
from typing import Dict, Any
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
import uuid
from datetime import datetime

# 设置环境变量
os.environ["DEEPSEEK_API_KEY"] = "sk-0b06b15af19c4b009f7f44fe04abdabd"


def check_weather(location: str) -> str:
    """Return the weather forecast for the specified location."""
    return f"It's always sunny in {location}"


class SimpleSessionManager:
    """简单的内存会话管理器（演示用）"""
    
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_session(self, user_id: str, window_id: str = None) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())
        thread_id = f"{user_id}_{session_id}"
        
        if window_id is None:
            window_id = str(uuid.uuid4())
        
        self.sessions[session_id] = {
            "user_id": user_id,
            "window_id": window_id,
            "thread_id": thread_id,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "context": {}
        }
        
        print(f"✅ 创建会话 {session_id} (用户: {user_id}, 窗口: {window_id})")
        return session_id
    
    def get_session(self, session_id: str) -> Dict[str, Any]:
        """获取会话信息"""
        session = self.sessions.get(session_id)
        if session:
            session["last_activity"] = datetime.now()
        return session
    
    def get_user_sessions(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """获取用户的所有会话"""
        return {
            sid: session for sid, session in self.sessions.items()
            if session["user_id"] == user_id
        }


class MultiWindowChatAgent:
    """支持多窗口的聊天Agent"""
    
    def __init__(self):
        self.session_manager = SimpleSessionManager()
        
        # 创建带有记忆的agent
        self.memory = MemorySaver()
        self.graph = create_react_agent(
            "deepseek:deepseek-chat",
            tools=[check_weather],
            prompt="You are a helpful assistant. Please respond in Chinese and ask for location if needed for weather queries.",
            checkpointer=self.memory
        )
    
    def create_session(self, user_id: str, window_id: str = None) -> str:
        """创建新会话"""
        return self.session_manager.create_session(user_id, window_id)
    
    def chat(self, session_id: str, message: str) -> str:
        """在指定会话中聊天"""
        session = self.session_manager.get_session(session_id)
        if not session:
            return f"❌ 会话 {session_id} 不存在或已过期"
        
        # 使用会话的thread_id进行对话
        config = {"configurable": {"thread_id": session["thread_id"]}}
        inputs = {"messages": [{"role": "user", "content": message}]}
        
        responses = []
        try:
            for chunk in self.graph.stream(inputs, config=config, stream_mode="updates"):
                if "agent" in chunk:
                    for msg in chunk["agent"]["messages"]:
                        if msg.content:
                            responses.append(msg.content)
        except Exception as e:
            return f"❌ 处理消息时出错: {str(e)}"
        
        return "\n".join(responses) if responses else "🤔 没有收到回复"
    
    def get_chat_history(self, session_id: str) -> list:
        """获取聊天历史"""
        session = self.session_manager.get_session(session_id)
        if not session:
            return []
        
        config = {"configurable": {"thread_id": session["thread_id"]}}
        try:
            state = self.graph.get_state(config)
            return state.values.get("messages", [])
        except:
            return []
    
    def list_user_sessions(self, user_id: str):
        """列出用户的所有会话"""
        sessions = self.session_manager.get_user_sessions(user_id)
        print(f"\n👤 用户 {user_id} 的活跃会话:")
        for session_id, session_info in sessions.items():
            print(f"  📱 会话 {session_id[:8]}... (窗口: {session_info['window_id'][:8]}...)")
            print(f"     创建时间: {session_info['created_at'].strftime('%H:%M:%S')}")
            print(f"     最后活动: {session_info['last_activity'].strftime('%H:%M:%S')}")


def demo_multi_window_chat():
    """演示多窗口聊天"""
    agent = MultiWindowChatAgent()
    
    # 用户Alice在两个窗口中创建会话
    print("🔥 演示多窗口聊天场景")
    print("=" * 50)
    
    # Alice的第一个窗口
    alice_session1 = agent.create_session("alice", "window_1")
    print(f"💬 Alice窗口1聊天:")
    response1 = agent.chat(alice_session1, "你好，我想了解天气")
    print(f"🤖 {response1}\n")
    
    # Alice的第二个窗口
    alice_session2 = agent.create_session("alice", "window_2")
    print(f"💬 Alice窗口2聊天:")
    response2 = agent.chat(alice_session2, "帮我介绍一下Python")
    print(f"🤖 {response2}\n")
    
    # 继续第一个窗口的对话
    print(f"💬 Alice窗口1继续聊天:")
    response3 = agent.chat(alice_session1, "北京今天天气怎么样？")
    print(f"🤖 {response3}\n")
    
    # 继续第二个窗口的对话
    print(f"💬 Alice窗口2继续聊天:")
    response4 = agent.chat(alice_session2, "Python有哪些优势？")
    print(f"🤖 {response4}\n")
    
    # 用户Bob创建一个会话
    bob_session = agent.create_session("bob", "window_1")
    print(f"💬 Bob窗口1聊天:")
    response5 = agent.chat(bob_session, "上海今天天气如何？")
    print(f"🤖 {response5}\n")
    
    # 显示所有用户的会话
    agent.list_user_sessions("alice")
    agent.list_user_sessions("bob")
    
    # 演示会话历史
    print(f"\n📚 Alice会话1的对话历史:")
    history = agent.get_chat_history(alice_session1)
    for i, msg in enumerate(history):
        if hasattr(msg, 'content'):
            role = getattr(msg, 'type', 'unknown')
            print(f"  {i+1}. [{role}] {msg.content}")


if __name__ == "__main__":
    demo_multi_window_chat()
