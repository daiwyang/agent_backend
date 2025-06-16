"""
测试配置和公共工具
"""

import os
from typing import Dict, Any


class TestConfig:
    """测试配置类"""
    
    # 服务器配置
    BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
    
    # 测试用户数据
    TEST_USER = {
        "username": "test_user_auth",
        "email": "test_auth@example.com", 
        "password": "test_password123",
        "full_name": "认证测试用户"
    }
    
    # 测试超时时间
    REQUEST_TIMEOUT = 30
    
    # API路径
    API_PATHS = {
        "user_register": "/agent_backend/user/register",
        "user_login": "/agent_backend/user/login",
        "user_logout": "/agent_backend/user/logout",
        "user_logout_all": "/agent_backend/user/logout-all",
        "user_me": "/agent_backend/user/me",
        "user_sessions": "/agent_backend/user/sessions",
        "chat_sessions": "/agent_backend/chat/sessions",
        "chat_search": "/agent_backend/chat/search",
        "chat_history": "/agent_backend/chat/chat-history",
        "chat_stats": "/agent_backend/chat/stats",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/agent_backend/user/health"
    }


def create_auth_headers(token: str) -> Dict[str, str]:
    """创建认证头"""
    return {"Authorization": f"Bearer {token}"}


def create_json_headers(token: str = None) -> Dict[str, str]:
    """创建JSON请求头"""
    headers = {"Content-Type": "application/json"}
    if token:
        headers.update(create_auth_headers(token))
    return headers


def print_test_section(title: str):
    """打印测试段落标题"""
    print(f"\n{'='*3} {title} {'='*3}")


def print_test_result(endpoint: str, status: int, expected: int = None):
    """打印测试结果"""
    if expected and status == expected:
        status_symbol = "✅"
    elif status >= 400:
        status_symbol = "❌"
    else:
        status_symbol = "ℹ️"
    
    print(f"{status_symbol} {endpoint}: {status}")


def format_response_data(data: Any, max_length: int = 100) -> str:
    """格式化响应数据用于显示"""
    import json
    try:
        formatted = json.dumps(data, ensure_ascii=False, indent=2)
        if len(formatted) > max_length:
            return formatted[:max_length] + "..."
        return formatted
    except:
        return str(data)[:max_length]
