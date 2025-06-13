#!/usr/bin/env python3
"""
测试流式输出的脚本
"""
import asyncio
import aiohttp
import json

async def test_streaming():
    """测试流式聊天接口"""
    url = "http://localhost:8001/agent_backend/chat/chat"
    
    # 首先创建一个会话
    session_data = {
        "user_id": "test_user",
        "window_id": "test_window"
    }
    
    async with aiohttp.ClientSession() as session:
        # 创建会话
        async with session.post("http://localhost:8001/agent_backend/chat/sessions", json=session_data) as resp:
            if resp.status == 200:
                session_info = await resp.json()
                session_id = session_info["session_id"]
                print(f"创建会话成功: {session_id}")
            else:
                print(f"创建会话失败: {resp.status}")
                return
        
        # 发送聊天消息
        chat_data = {
            "session_id": session_id,
            "message": "请告诉我一个关于人工智能的简短故事"
        }
        
        print("发送聊天请求...")
        async with session.post(url, json=chat_data) as resp:
            print(f"响应状态: {resp.status}")
            print(f"响应头: {dict(resp.headers)}")
            
            # 逐行读取流式响应
            async for line in resp.content:
                if line:
                    try:
                        data = json.loads(line.decode('utf-8').strip())
                        print(f"收到数据: {data}")
                    except json.JSONDecodeError as e:
                        print(f"JSON解析错误: {e}, 原始数据: {line}")

if __name__ == "__main__":
    asyncio.run(test_streaming())
