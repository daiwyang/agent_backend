#!/usr/bin/env python3
"""
测试 JWT 认证和 Chat API
"""

import requests
import json
import sys

def test_auth_flow():
    """测试完整的认证流程"""
    base_url = "http://127.0.0.1:8000/agent_backend"
    
    # 1. 登录获取token
    print("1. 测试登录...")
    login_data = {"username": "testuser", "password": "testpass123"}
    login_response = requests.post(f"{base_url}/user/login", json=login_data)
    
    print(f"登录状态码: {login_response.status_code}")
    print(f"登录响应: {login_response.text}")
    
    if login_response.status_code != 200:
        print("❌ 登录失败")
        return False
    
    # 2. 提取token
    login_data = login_response.json()
    token = login_data.get("access_token")
    if not token:
        print("❌ 未获取到access_token")
        print(f"登录响应内容: {login_data}")
        return False
    
    print(f"✅ 获取到token: {token[:50]}...")
    
    # 3. 创建会话
    print("\n2. 创建聊天会话...")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    create_session_data = {
        "user_id": login_data.get("user_id"),
        "session_name": "测试会话"
    }
    
    session_response = requests.post(f"{base_url}/chat/sessions", json=create_session_data, headers=headers)
    print(f"创建会话状态码: {session_response.status_code}")
    print(f"创建会话响应: {session_response.text}")
    
    if session_response.status_code == 200:
        session_data = session_response.json()
        session_id = session_data.get("session_id")
        print(f"✅ 会话创建成功: {session_id}")
    else:
        # 如果创建会话失败，使用一个测试会话ID
        session_id = "test-session-123"
        print(f"⚠️ 会话创建失败，使用测试会话ID: {session_id}")
    
    # 4. 测试聊天接口
    print("\n3. 测试聊天接口...")
    chat_data = {
        "session_id": session_id,
        "message": "Hello, this is a test message!"
    }
    
    chat_response = requests.post(f"{base_url}/chat/chat", json=chat_data, headers=headers)
    print(f"聊天接口状态码: {chat_response.status_code}")
    print(f"聊天接口响应: {chat_response.text[:500]}")
    
    if chat_response.status_code == 200:
        print("✅ 聊天接口调用成功")
        return True
    else:
        print("❌ 聊天接口调用失败")
        return False

if __name__ == "__main__":
    success = test_auth_flow()
    sys.exit(0 if success else 1)
