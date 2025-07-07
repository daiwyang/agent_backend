#!/usr/bin/env python3
"""
MCP工具诊断脚本
用于检查MCP工具的状态和连接问题
"""

import asyncio
import sys
import traceback
from typing import List, Dict, Any

# 添加项目路径
sys.path.append("../")

from copilot.utils.logger import logger
from copilot.core.mcp_tool_wrapper import MCPToolWrapper
from copilot.mcp_client.mcp_server_manager import mcp_server_manager


async def diagnose_mcp_tools():
    """诊断MCP工具状态"""
    print("🔍 开始诊断MCP工具状态...")
    print("=" * 60)
    
    try:
        # 1. 检查MCP服务器管理器状态
        print("📡 检查MCP服务器管理器状态...")
        server_count = len(mcp_server_manager.servers)
        print(f"   已配置服务器数量: {server_count}")
        
        for server_id, server_info in mcp_server_manager.servers.items():
            print(f"   服务器 {server_id}: {server_info.get('status', 'unknown')}")
        
        # 2. 尝试获取所有MCP工具
        print("\n🛠️  获取MCP工具列表...")
        try:
            tools = await MCPToolWrapper.get_mcp_tools()
            print(f"   成功获取 {len(tools)} 个工具")
            
            # 列出所有工具
            for i, tool in enumerate(tools, 1):
                print(f"   {i}. {tool.name}")
                
        except Exception as e:
            print(f"   ❌ 获取工具失败: {e}")
            print(f"   详细错误: {traceback.format_exc()}")
            
        # 3. 特别检查biorxiv_search_articles工具
        print("\n🧬 特别检查 biorxiv_search_articles 工具...")
        try:
            # 查找工具
            biorxiv_tool = None
            for tool in tools:
                if tool.name == "biorxiv_search_articles":
                    biorxiv_tool = tool
                    break
            
            if biorxiv_tool:
                print("   ✅ 找到 biorxiv_search_articles 工具")
                
                # 检查工具属性
                print(f"   工具类型: {type(biorxiv_tool)}")
                print(f"   是否有 _arun: {hasattr(biorxiv_tool, '_arun')}")
                print(f"   是否有 arun: {hasattr(biorxiv_tool, 'arun')}")
                
                # 获取工具信息
                try:
                    tool_info = await mcp_server_manager._get_tool_info("biorxiv_search_articles")
                    print(f"   工具信息: {tool_info}")
                except Exception as info_e:
                    print(f"   ❌ 获取工具信息失败: {info_e}")
                
                # 尝试简单调用（不执行实际功能）
                print("   🧪 尝试测试调用...")
                try:
                    # 这里我们不实际调用，只是检查工具是否可调用
                    original_arun = getattr(biorxiv_tool, '_arun', None) or getattr(biorxiv_tool, 'arun', None)
                    if original_arun and callable(original_arun):
                        print("   ✅ 工具方法可调用")
                    else:
                        print("   ❌ 工具方法不可调用")
                        
                except Exception as call_e:
                    print(f"   ❌ 工具调用检查失败: {call_e}")
                    
            else:
                print("   ❌ 未找到 biorxiv_search_articles 工具")
                
        except Exception as biorxiv_e:
            print(f"   ❌ 检查 biorxiv_search_articles 失败: {biorxiv_e}")
            
        # 4. 检查网络连接
        print("\n🌐 检查网络连接...")
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                # 测试连接到bioRxiv
                async with session.get("https://api.biorxiv.org/details/biorxiv/2023-01-01/2023-01-02", timeout=10) as response:
                    if response.status == 200:
                        print("   ✅ bioRxiv API 连接正常")
                    else:
                        print(f"   ⚠️  bioRxiv API 响应状态: {response.status}")
        except Exception as net_e:
            print(f"   ❌ 网络连接测试失败: {net_e}")
            
        # 5. 检查服务器配置
        print("\n⚙️  检查服务器配置...")
        try:
            from copilot.config.settings import settings
            print(f"   MCP配置: {hasattr(settings, 'mcp_servers')}")
            if hasattr(settings, 'mcp_servers'):
                print(f"   配置的服务器: {list(settings.mcp_servers.keys()) if settings.mcp_servers else '无'}")
        except Exception as config_e:
            print(f"   ❌ 配置检查失败: {config_e}")
            
    except Exception as e:
        print(f"❌ 诊断过程出错: {e}")
        print(f"详细错误: {traceback.format_exc()}")
        
    print("\n" + "=" * 60)
    print("🏁 诊断完成")


async def test_tool_execution():
    """测试工具执行（安全模式）"""
    print("\n🧪 安全模式工具执行测试...")
    
    try:
        tools = await MCPToolWrapper.get_mcp_tools()
        
        # 找到一个低风险的工具进行测试
        test_tool = None
        for tool in tools:
            # 寻找一个看起来安全的工具
            if "search" in tool.name.lower() and "biorxiv" not in tool.name.lower():
                test_tool = tool
                break
        
        if test_tool:
            print(f"   测试工具: {test_tool.name}")
            
            # 模拟工具调用参数
            test_args = ()
            test_kwargs = {
                "config": {
                    "configurable": {
                        "session_id": "diagnostic_test_session"
                    }
                }
            }
            
            print("   ⚠️  注意：这是一个真实的工具调用测试")
            print("   如果工具有副作用，请谨慎使用")
            
            # 询问用户是否继续
            # response = input("   是否继续执行测试? (y/N): ")
            # if response.lower() != 'y':
            #     print("   跳过工具执行测试")
            #     return
            
            print("   跳过实际工具执行测试以避免副作用")
            
        else:
            print("   未找到合适的测试工具")
            
    except Exception as e:
        print(f"   ❌ 工具执行测试失败: {e}")


if __name__ == "__main__":
    asyncio.run(diagnose_mcp_tools())
    asyncio.run(test_tool_execution()) 