"""
测试会话重新激活功能

这个脚本展示了如何将一个已归档或已删除的会话重新激活为活跃状态
"""

import asyncio
import json
from datetime import datetime

async def test_session_reactivation():
    """测试会话重新激活功能"""
    
    print("=== 会话重新激活功能测试 ===\n")
    
    # 模拟的API调用示例
    print("1. 获取会话状态：")
    print("GET /chat/sessions/{session_id}/status")
    print("Response:")
    print(json.dumps({
        "session_id": "test-session-123",
        "user_id": "user-456", 
        "window_id": "window-789",
        "status": "archived",
        "created_at": "2025-06-20T10:00:00",
        "last_activity": "2025-06-22T15:30:00", 
        "is_active_in_redis": False,
        "archived_at": "2025-06-23T09:00:00",
        "deleted_at": None,
        "reactivated_at": None
    }, indent=2))
    
    print("\n" + "="*50 + "\n")
    
    print("2. 重新激活会话：")
    print("PATCH /chat/sessions/{session_id}/reactivate")
    print("Response:")
    print(json.dumps({
        "message": "会话已成功重新激活",
        "session_id": "test-session-123",
        "status": "active",
        "reactivated_at": datetime.now().isoformat()
    }, indent=2))
    
    print("\n" + "="*50 + "\n")
    
    print("3. 确认会话状态已更新：")
    print("GET /chat/sessions/{session_id}/status")
    print("Response:")
    print(json.dumps({
        "session_id": "test-session-123",
        "user_id": "user-456",
        "window_id": "window-789", 
        "status": "active",
        "created_at": "2025-06-20T10:00:00",
        "last_activity": datetime.now().isoformat(),
        "is_active_in_redis": True,
        "archived_at": "2025-06-23T09:00:00",
        "deleted_at": None,
        "reactivated_at": datetime.now().isoformat()
    }, indent=2))

async def show_usage_examples():
    """显示使用示例"""
    
    print("\n" + "="*60)
    print("使用示例：")
    print("="*60 + "\n")
    
    print("1. 使用curl命令获取会话状态：")
    print("""
curl -X GET "http://localhost:8000/chat/sessions/your-session-id/status" \\
     -H "Authorization: Bearer your-token" \\
     -H "Content-Type: application/json"
    """)
    
    print("2. 使用curl命令重新激活会话：")
    print("""
curl -X PATCH "http://localhost:8000/chat/sessions/your-session-id/reactivate" \\
     -H "Authorization: Bearer your-token" \\
     -H "Content-Type: application/json"
    """)
    
    print("3. 使用Python requests库：")
    print("""
import requests

# 获取会话状态
response = requests.get(
    "http://localhost:8000/chat/sessions/your-session-id/status",
    headers={"Authorization": "Bearer your-token"}
)
session_status = response.json()
print(f"会话状态: {session_status['status']}")

# 重新激活会话
if session_status['status'] in ['archived', 'deleted']:
    response = requests.patch(
        "http://localhost:8000/chat/sessions/your-session-id/reactivate",
        headers={"Authorization": "Bearer your-token"}
    )
    result = response.json()
    print(f"激活结果: {result['message']}")
    """)

async def main():
    """主函数"""
    await test_session_reactivation()
    await show_usage_examples()
    
    print("\n" + "="*60)
    print("功能说明：")
    print("="*60)
    print("""
会话重新激活功能允许用户将已归档或已删除的会话重新转为活跃状态。

主要特性：
1. 支持将 'archived' 状态的会话重新激活
2. 支持将 'deleted' 状态的会话重新激活  
3. 重新激活后会话状态变为 'active'
4. 同时在Redis中恢复会话信息，确保可以正常使用
5. 记录重新激活的时间戳
6. 更新会话的最后活动时间

安全性：
- 只有会话的所有者可以重新激活会话
- 需要有效的身份认证token
- 自动验证用户权限

使用场景：
- 用户需要恢复之前归档的重要对话
- 意外删除会话后需要恢复
- 长时间未使用的会话需要重新激活
    """)

if __name__ == "__main__":
    asyncio.run(main())
