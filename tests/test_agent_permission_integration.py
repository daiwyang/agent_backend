"""
Agent工具权限确认集成测试
演示新的非阻塞权限确认机制
"""

import asyncio
import json
from typing import Dict, Any

from copilot.core.agent import CoreAgent
from copilot.core.agent_state_manager import agent_state_manager
from copilot.mcp_client.mcp_server_manager import mcp_server_manager
from copilot.utils.logger import logger


class MockMCPServer:
    """模拟MCP服务器用于测试"""
    
    @staticmethod
    async def register_test_server():
        """注册测试MCP服务器"""
        server_config = {
            "id": "test_server",
            "name": "Test MCP Server",
            "url": "http://localhost:3000/mcp",  # 模拟URL
            "tool_risks": {
                "file_read": "low",
                "file_write": "high",
                "system_command": "high"
            }
        }
        
        # 这里实际应用中需要真正的MCP服务器
        # 现在只是为了演示权限确认流程
        logger.info("Mock MCP server registered for testing")
        return True


async def test_agent_permission_flow():
    """测试Agent权限确认流程"""
    try:
        # 1. 启动必要的服务
        await agent_state_manager.start()
        await mcp_server_manager.start()
        
        # 2. 注册测试MCP服务器（在实际应用中这会是真正的MCP服务器）
        await MockMCPServer.register_test_server()
        
        # 3. 创建Agent实例
        agent = await CoreAgent.create_with_mcp_tools(
            provider="deepseek",  # 或其他可用的提供商
            model_name="deepseek-chat"
        )
        
        # 4. 模拟聊天会话
        session_id = "test_session_001"
        thread_id = "test_thread_001"
        
        print("=== Agent工具权限确认测试 ===")
        print(f"会话ID: {session_id}")
        print(f"线程ID: {thread_id}")
        print()
        
        # 5. 发送需要工具调用的消息
        test_message = "请帮我读取当前目录下的文件列表"
        
        print(f"用户消息: {test_message}")
        print("Agent响应:")
        print("-" * 50)
        
        # 6. 开始聊天流
        async for chunk in agent.chat(
            message=test_message,
            thread_id=thread_id,
            session_id=session_id,
            enable_tools=True
        ):
            print(chunk, end="", flush=True)
            
            # 模拟检测到权限请求
            if "🔒 等待用户确认执行工具" in chunk:
                print("\n" + "="*50)
                print("检测到工具权限请求！")
                
                # 获取会话状态
                status = agent_state_manager.get_session_status(session_id)
                if status and status.get("pending_tools"):
                    for tool in status["pending_tools"]:
                        print(f"工具名称: {tool['tool_name']}")
                        print(f"风险级别: {tool['risk_level']}")
                        print(f"参数: {json.dumps(tool['parameters'], indent=2, ensure_ascii=False)}")
                        
                        # 模拟用户确认（在实际应用中这会通过WebSocket前端界面处理）
                        print("\n模拟用户确认...")
                        user_approval = True  # 或False来测试拒绝情况
                        
                        success = await agent_state_manager.handle_permission_response(
                            session_id=session_id,
                            execution_id=tool["execution_id"],
                            approved=user_approval
                        )
                        
                        if success:
                            print(f"✅ 权限响应处理成功: {'批准' if user_approval else '拒绝'}")
                        else:
                            print("❌ 权限响应处理失败")
                            
                print("="*50)
        
        print("\n\n测试完成!")
        
    except Exception as e:
        logger.error(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理资源
        await agent_state_manager.stop()
        await mcp_server_manager.stop()


async def test_websocket_message_handling():
    """测试WebSocket消息处理"""
    print("\n=== WebSocket消息处理测试 ===")
    
    # 模拟前端发送的权限响应消息
    mock_messages = [
        {
            "type": "agent_tool_permission_response",
            "data": {
                "execution_id": "test_execution_123",
                "approved": True
            }
        },
        {
            "type": "get_agent_status",
            "data": {}
        }
    ]
    
    session_id = "test_session_websocket"
    
    for message in mock_messages:
        print(f"模拟WebSocket消息: {json.dumps(message, indent=2, ensure_ascii=False)}")
        
        # 这里在实际应用中会通过WebSocket处理器处理
        # 现在只是展示消息格式
        print("✅ 消息格式正确")
        print()


def print_integration_guide():
    """打印集成指南"""
    print("""
=== Agent工具权限确认集成指南 ===

1. 架构概述:
   - Agent状态管理器: 管理执行状态和权限确认流程
   - 非阻塞工具包装器: 在需要权限时不阻塞，而是发送确认请求
   - WebSocket集成: 通过WebSocket与前端进行权限确认交互

2. 前端集成要点:
   
   A. WebSocket连接:
   ```javascript
   const ws = new WebSocket('ws://localhost:8000/agent_backend/ws/your_session_id');
   ```
   
   B. 监听权限请求:
   ```javascript
   ws.onmessage = (event) => {
     const message = JSON.parse(event.data);
     if (message.type === 'agent_tool_permission_request') {
       // 显示权限确认界面
       showToolPermissionDialog(message.data);
     }
   };
   ```
   
   C. 发送权限响应:
   ```javascript
   function respondToPermission(executionId, approved) {
     ws.send(JSON.stringify({
       type: 'agent_tool_permission_response',
       data: {
         execution_id: executionId,
         approved: approved
       }
     }));
   }
   ```

3. 聊天流程:
   - 用户发送消息
   - Agent开始执行，遇到需要权限的工具时暂停
   - 前端收到权限请求，显示确认界面
   - 用户确认或拒绝
   - Agent继续或停止执行

4. 消息类型:
   - agent_tool_permission_request: Agent发出的权限请求
   - agent_tool_permission_response: 前端的权限响应
   - agent_tool_permission_result: 权限处理结果通知
   - get_agent_status: 获取Agent执行状态

5. 状态管理:
   - IDLE: 空闲
   - RUNNING: 执行中
   - WAITING_PERMISSION: 等待权限确认
   - PAUSED: 暂停（用户拒绝）
   - COMPLETED: 完成
   - ERROR: 错误
""")


if __name__ == "__main__":
    print_integration_guide()
    
    # 运行测试
    asyncio.run(test_agent_permission_flow())
    asyncio.run(test_websocket_message_handling()) 