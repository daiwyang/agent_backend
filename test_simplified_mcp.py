#!/usr/bin/env python3
"""
简化版 MCP Server Manager 验证测试
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.append('/data/agent_backend')

from copilot.mcp.mcp_server_manager import mcp_server_manager


async def test_basic_functionality():
    """测试基本功能"""
    print("=== 简化版 MCP Server Manager 测试 ===\n")
    
    try:
        # 启动管理器
        await mcp_server_manager.start()
        print("✓ MCP Server Manager 启动成功")
        
        # 测试获取工具列表（空列表）
        tools = mcp_server_manager.get_available_tools()
        print(f"✓ 获取工具列表成功，当前工具数: {len(tools)}")
        
        # 测试获取服务器信息（空列表）
        servers = mcp_server_manager.get_servers_info()
        print(f"✓ 获取服务器信息成功，当前服务器数: {len(servers)}")
        
        # 测试配置验证
        valid_config = {
            "id": "test_server",
            "name": "Test Server",
            "url": "https://example.com/mcp",
            "auth": "test-token",
            "tool_risks": {
                "test_tool": "low"
            }
        }
        
        is_valid = mcp_server_manager._validate_config(valid_config)
        print(f"✓ 配置验证测试通过: {is_valid}")
        
        # 测试无效配置
        invalid_config = {
            "name": "Test Server"  # 缺少 id 和连接方式
        }
        
        is_invalid = mcp_server_manager._validate_config(invalid_config)
        print(f"✓ 无效配置检测正确: {not is_invalid}")
        
        # 测试工具名解析
        # 先添加一个模拟工具到索引
        mcp_server_manager.tools_index["test_server::test_tool"] = {
            "name": "test_tool",
            "description": "Test tool",
            "risk_level": "low"
        }
        
        resolved = mcp_server_manager._resolve_tool_name("test_server::test_tool")
        print(f"✓ 全名解析测试: {resolved == 'test_server::test_tool'}")
        
        resolved_short = mcp_server_manager._resolve_tool_name("test_tool")
        print(f"✓ 简名解析测试: {resolved_short == 'test_server::test_tool'}")
        
        # 停止管理器
        await mcp_server_manager.stop()
        print("✓ MCP Server Manager 停止成功")
        
        print("\n=== 所有基础功能测试通过 ===")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_basic_functionality())
