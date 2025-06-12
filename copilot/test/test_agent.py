from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
import os
import uuid
from datetime import datetime

os.environ["DEEPSEEK_API_KEY"] = "sk-0b06b15af19c4b009f7f44fe04abdabd"


def check_weather(location: str) -> str:
    """Return the weather forecast for the specified location."""
    return f"It's always sunny in {location}"


# 创建带有记忆的agent - 支持多轮对话
memory = MemorySaver()
graph = create_react_agent(
    "deepseek:deepseek-chat", 
    tools=[check_weather], 
    prompt="You are a helpful assistant. Please respond in Chinese and ask for location if weather query lacks location info.",
    checkpointer=memory
)

# 会话管理示例
class ChatSession:
    def __init__(self, user_id: str, window_id: str = None):
        self.user_id = user_id
        self.window_id = window_id or str(uuid.uuid4())
        self.session_id = str(uuid.uuid4())
        self.thread_id = f"{user_id}_{self.session_id}"
        self.created_at = datetime.now()
        
    def chat(self, message: str):
        """发送消息并获取回复"""
        config = {"configurable": {"thread_id": self.thread_id}}
        inputs = {"messages": [{"role": "user", "content": message}]}
        
        print(f"\n👤 用户消息: {message}")
        print(f"📱 会话ID: {self.session_id[:8]}... (窗口: {self.window_id[:8]}...)")
        
        for chunk in graph.stream(inputs, config=config, stream_mode="updates"):
            if "agent" in chunk:
                for msg in chunk["agent"]["messages"]:
                    if msg.content:
                        print(f"🤖 助手回复: {msg.content}")

# 演示多会话对话
if __name__ == "__main__":
    print("🔥 多轮对话和多会话管理演示")
    print("=" * 50)
    
    # 用户Alice的第一个会话（比如桌面浏览器）
    alice_session1 = ChatSession("alice", "desktop_browser")
    alice_session1.chat("你好")
    alice_session1.chat("今天天气怎么样？")  # 缺少地点信息
    alice_session1.chat("北京的天气")  # 提供地点信息
    
    print("\n" + "="*30)
    
    # 用户Alice的第二个会话（比如手机APP）
    alice_session2 = ChatSession("alice", "mobile_app")
    alice_session2.chat("帮我介绍一下Python")
    alice_session2.chat("它有什么优势？")  # 上下文相关的问题
    
    print("\n" + "="*30)
    
    # 用户Bob的会话
    bob_session = ChatSession("bob", "web_browser")
    bob_session.chat("上海今天天气如何？")
    
    print("\n📋 会话总结:")
    print(f"Alice有2个活跃会话: desktop_browser, mobile_app")
    print(f"Bob有1个活跃会话: web_browser")
    print(f"每个会话都维护独立的对话历史和上下文")
