"""
多会话聊天客户端示例
演示如何与聊天API交互
"""
import asyncio
import aiohttp
import json
from datetime import datetime


class ChatClient:
    """聊天客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.sessions = {}  # 本地会话缓存
    
    async def create_session(self, user_id: str, window_id: str = None) -> str:
        """创建新会话"""
        async with aiohttp.ClientSession() as session:
            payload = {"user_id": user_id}
            if window_id:
                payload["window_id"] = window_id
            
            async with session.post(f"{self.base_url}/sessions", json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    session_id = data["session_id"]
                    self.sessions[session_id] = data
                    print(f"✅ 创建会话成功: {session_id}")
                    return session_id
                else:
                    print(f"❌ 创建会话失败: {resp.status}")
                    return None
    
    async def send_message(self, session_id: str, message: str) -> str:
        """发送消息"""
        async with aiohttp.ClientSession() as session:
            payload = {"session_id": session_id, "message": message}
            
            async with session.post(f"{self.base_url}/chat", json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["response"]
                else:
                    return f"❌ 发送消息失败: {resp.status}"
    
    async def get_user_sessions(self, user_id: str) -> list:
        """获取用户的所有会话"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/users/{user_id}/sessions") as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    print(f"❌ 获取会话列表失败: {resp.status}")
                    return []
    
    async def delete_session(self, session_id: str):
        """删除会话"""
        async with aiohttp.ClientSession() as session:
            async with session.delete(f"{self.base_url}/sessions/{session_id}") as resp:
                if resp.status == 200:
                    if session_id in self.sessions:
                        del self.sessions[session_id]
                    print(f"✅ 删除会话成功: {session_id}")
                else:
                    print(f"❌ 删除会话失败: {resp.status}")


async def demo_multi_window_chat():
    """演示多窗口聊天场景"""
    client = ChatClient()
    
    print("🔥 多窗口聊天演示")
    print("=" * 50)
    
    # Alice在两个窗口创建会话
    alice_window1 = await client.create_session("alice", "desktop_browser")
    alice_window2 = await client.create_session("alice", "mobile_app")
    
    # Bob创建一个会话
    bob_window1 = await client.create_session("bob", "web_browser")
    
    print("\n💬 开始多窗口对话...")
    
    # Alice窗口1: 天气相关对话
    print(f"\n👤 Alice (桌面浏览器): 你好")
    response = await client.send_message(alice_window1, "你好")
    print(f"🤖 助手: {response}")
    
    print(f"\n👤 Alice (桌面浏览器): 北京今天天气怎么样？")
    response = await client.send_message(alice_window1, "北京今天天气怎么样？")
    print(f"🤖 助手: {response}")
    
    # Alice窗口2: Python相关对话
    print(f"\n👤 Alice (手机APP): 帮我介绍一下Python")
    response = await client.send_message(alice_window2, "帮我介绍一下Python")
    print(f"🤖 助手: {response}")
    
    # Bob窗口1: 天气查询
    print(f"\n👤 Bob (网页浏览器): 上海天气如何？")
    response = await client.send_message(bob_window1, "上海天气如何？")
    print(f"🤖 助手: {response}")
    
    # 继续Alice窗口1的对话
    print(f"\n👤 Alice (桌面浏览器): 那上海呢？")
    response = await client.send_message(alice_window1, "那上海呢？")
    print(f"🤖 助手: {response}")
    
    # 继续Alice窗口2的对话
    print(f"\n👤 Alice (手机APP): Python有什么优势？")
    response = await client.send_message(alice_window2, "Python有什么优势？")
    print(f"🤖 助手: {response}")
    
    # 查看用户会话
    print(f"\n📊 Alice的会话列表:")
    alice_sessions = await client.get_user_sessions("alice")
    for session in alice_sessions:
        print(f"  📱 会话 {session['session_id'][:8]}... (窗口: {session['window_id']})")
        print(f"     创建时间: {session['created_at']}")
    
    print(f"\n📊 Bob的会话列表:")
    bob_sessions = await client.get_user_sessions("bob")
    for session in bob_sessions:
        print(f"  📱 会话 {session['session_id'][:8]}... (窗口: {session['window_id']})")
        print(f"     创建时间: {session['created_at']}")
    
    print(f"\n🏁 演示完成!")
    print(f"📋 总结:")
    print(f"  - Alice同时在2个窗口进行不同主题的对话")
    print(f"  - Bob在1个窗口进行对话")
    print(f"  - 每个会话维护独立的对话上下文")
    print(f"  - 支持实时会话管理和查询")


async def interactive_chat():
    """交互式聊天"""
    client = ChatClient()
    
    print("🤖 欢迎使用多会话聊天客户端!")
    user_id = input("请输入您的用户ID: ")
    window_id = input("请输入窗口ID (回车使用自动生成): ").strip() or None
    
    session_id = await client.create_session(user_id, window_id)
    if not session_id:
        print("❌ 创建会话失败")
        return
    
    print(f"✅ 会话创建成功! 会话ID: {session_id}")
    print("💡 输入 'quit' 退出, 'sessions' 查看会话列表")
    
    while True:
        try:
            message = input("\n👤 您: ").strip()
            
            if message.lower() == 'quit':
                break
            elif message.lower() == 'sessions':
                sessions = await client.get_user_sessions(user_id)
                print(f"\n📊 您的会话列表:")
                for session in sessions:
                    print(f"  📱 {session['session_id'][:8]}... (窗口: {session['window_id']})")
                continue
            elif not message:
                continue
            
            response = await client.send_message(session_id, message)
            print(f"🤖 助手: {response}")
            
        except KeyboardInterrupt:
            break
    
    print(f"\n👋 再见!")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "interactive":
        asyncio.run(interactive_chat())
    else:
        asyncio.run(demo_multi_window_chat())
