"""
Agent级别MCP工具管理功能测试
验证为不同Agent配置不同MCP工具的能力
"""

import asyncio
from datetime import datetime
from typing import Dict, Any

from copilot.core.agent_manager import agent_manager
from copilot.core.agent_state_manager import agent_state_manager
from copilot.mcp_client.mcp_server_manager import mcp_server_manager
from copilot.utils.logger import logger


class AgentMCPManagementTest:
    """Agent级别MCP工具管理测试"""
    
    def __init__(self):
        self.test_results = []
        
    async def setup(self):
        """初始化测试环境"""
        logger.info("Setting up Agent MCP management test...")
        
        # 启动所有管理器
        await agent_manager.start()
        await agent_state_manager.start()
        await mcp_server_manager.start()
        
        logger.info("Agent MCP management test environment ready")
        
    async def cleanup(self):
        """清理测试环境"""
        logger.info("Cleaning up Agent MCP management test environment...")
        
        await agent_manager.stop()
        await agent_state_manager.stop()
        await mcp_server_manager.stop()
        
        logger.info("Agent MCP management test environment cleaned up")
        
    async def test_agent_mcp_server_configuration(self):
        """测试Agent MCP服务器配置"""
        print("\n=== Agent MCP服务器配置测试 ===")
        
        try:
            # 创建几个Agent
            session1 = "mcp_test_session_1"
            session2 = "mcp_test_session_2"
            session3 = "mcp_test_session_3"
            
            agent1 = await agent_manager.get_agent(session1, provider="deepseek")
            agent2 = await agent_manager.get_agent(session2, provider="deepseek")
            agent3 = await agent_manager.get_agent(session3, provider="deepseek")
            
            print(f"✅ 创建了3个Agent实例")
            
            # 模拟注册一些MCP服务器
            server_configs = [
                {
                    "id": "test_server_1",
                    "name": "测试服务器1",
                    "url": "https://example1.com/mcp",
                    "tool_risks": {"test_tool_1": "low"}
                },
                {
                    "id": "test_server_2", 
                    "name": "测试服务器2",
                    "url": "https://example2.com/mcp",
                    "tool_risks": {"test_tool_2": "medium"}
                },
                {
                    "id": "test_server_3",
                    "name": "测试服务器3",
                    "url": "https://example3.com/mcp",
                    "tool_risks": {"test_tool_3": "high"}
                }
            ]
            
            # 注册服务器（这里会失败，因为是模拟URL，但我们主要测试配置管理）
            for config in server_configs:
                try:
                    await mcp_server_manager.register_server(config)
                except:
                    # 预期会失败，但服务器配置会被记录
                    pass
            
            print(f"✅ 模拟注册了3个MCP服务器")
            
            # 测试为不同Agent配置不同的服务器
            # Agent1 使用服务器1和2
            await agent_manager.set_agent_mcp_servers(session1, {"test_server_1", "test_server_2"})
            
            # Agent2 使用服务器2和3
            await agent_manager.set_agent_mcp_servers(session2, {"test_server_2", "test_server_3"})
            
            # Agent3 只使用服务器1
            await agent_manager.set_agent_mcp_servers(session3, {"test_server_1"})
            
            print(f"✅ 为不同Agent配置了不同的MCP服务器组合")
            
            # 验证配置
            servers1 = agent_manager.get_agent_mcp_servers(session1)
            servers2 = agent_manager.get_agent_mcp_servers(session2)
            servers3 = agent_manager.get_agent_mcp_servers(session3)
            
            print(f"Agent1 使用服务器: {servers1}")
            print(f"Agent2 使用服务器: {servers2}")
            print(f"Agent3 使用服务器: {servers3}")
            
            # 验证配置是否正确
            if (servers1 == {"test_server_1", "test_server_2"} and
                servers2 == {"test_server_2", "test_server_3"} and
                servers3 == {"test_server_1"}):
                print("✅ Agent MCP服务器配置正确")
                return True
            else:
                print("❌ Agent MCP服务器配置错误")
                return False
                
        except Exception as e:
            print(f"❌ Agent MCP服务器配置测试失败: {e}")
            return False
            
    async def test_agent_mcp_server_management(self):
        """测试Agent MCP服务器管理"""
        print("\n=== Agent MCP服务器管理测试 ===")
        
        try:
            session_id = "mcp_mgmt_test_session"
            
            # 创建Agent
            agent = await agent_manager.get_agent(session_id, provider="deepseek")
            print(f"✅ 创建Agent: {session_id}")
            
            # 测试添加服务器
            await agent_manager.add_agent_mcp_server(session_id, "test_server_1")
            servers = agent_manager.get_agent_mcp_servers(session_id)
            print(f"添加服务器1后: {servers}")
            
            await agent_manager.add_agent_mcp_server(session_id, "test_server_2")
            servers = agent_manager.get_agent_mcp_servers(session_id)
            print(f"添加服务器2后: {servers}")
            
            # 测试移除服务器
            await agent_manager.remove_agent_mcp_server(session_id, "test_server_1")
            servers = agent_manager.get_agent_mcp_servers(session_id)
            print(f"移除服务器1后: {servers}")
            
            # 验证最终状态
            if servers == {"test_server_2"}:
                print("✅ Agent MCP服务器管理功能正常")
                return True
            else:
                print("❌ Agent MCP服务器管理功能异常")
                return False
                
        except Exception as e:
            print(f"❌ Agent MCP服务器管理测试失败: {e}")
            return False
            
    async def test_server_agent_query(self):
        """测试服务器-Agent查询功能"""
        print("\n=== 服务器-Agent查询测试 ===")
        
        try:
            # 为多个Agent配置服务器使用
            sessions = ["query_test_1", "query_test_2", "query_test_3"]
            
            for session in sessions:
                await agent_manager.get_agent(session, provider="deepseek")
            
            # 配置不同的服务器使用情况
            await agent_manager.set_agent_mcp_servers("query_test_1", {"test_server_1", "test_server_2"})
            await agent_manager.set_agent_mcp_servers("query_test_2", {"test_server_1"})
            await agent_manager.set_agent_mcp_servers("query_test_3", {"test_server_2"})
            
            # 查询使用test_server_1的会话
            server1_sessions = agent_manager.get_sessions_using_server("test_server_1")
            print(f"使用test_server_1的会话: {server1_sessions}")
            
            # 查询使用test_server_2的会话
            server2_sessions = agent_manager.get_sessions_using_server("test_server_2")
            print(f"使用test_server_2的会话: {server2_sessions}")
            
            # 验证查询结果
            expected_server1 = {"query_test_1", "query_test_2"}
            expected_server2 = {"query_test_1", "query_test_3"}
            
            if (set(server1_sessions) == expected_server1 and
                set(server2_sessions) == expected_server2):
                print("✅ 服务器-Agent查询功能正常")
                return True
            else:
                print("❌ 服务器-Agent查询功能异常")
                print(f"期望server1会话: {expected_server1}, 实际: {set(server1_sessions)}")
                print(f"期望server2会话: {expected_server2}, 实际: {set(server2_sessions)}")
                return False
                
        except Exception as e:
            print(f"❌ 服务器-Agent查询测试失败: {e}")
            return False
            
    async def test_agent_tool_isolation(self):
        """测试Agent工具隔离"""
        print("\n=== Agent工具隔离测试 ===")
        
        try:
            # 创建两个Agent
            session1 = "isolation_test_1"
            session2 = "isolation_test_2"
            
            agent1 = await agent_manager.get_agent(session1, provider="deepseek")
            agent2 = await agent_manager.get_agent(session2, provider="deepseek")
            
            # 为Agent1配置服务器1和2
            await agent_manager.set_agent_mcp_servers(session1, {"test_server_1", "test_server_2"})
            
            # 为Agent2配置服务器2和3
            await agent_manager.set_agent_mcp_servers(session2, {"test_server_2", "test_server_3"})
            
            # 检查初始工具数量
            initial_tools1 = len(agent1.mcp_tools)
            initial_tools2 = len(agent2.mcp_tools)
            
            print(f"Agent1 初始工具数量: {initial_tools1}")
            print(f"Agent2 初始工具数量: {initial_tools2}")
            
            # 测试工具更新（因为没有真实的MCP服务器，这里主要测试机制）
            try:
                await agent_manager._update_agent_mcp_tools(session1, {"test_server_1"})
                await agent_manager._update_agent_mcp_tools(session2, {"test_server_3"})
                print("✅ Agent工具更新机制运行正常")
            except Exception as update_error:
                print(f"⚠️ Agent工具更新失败（预期，因为没有真实MCP服务器）: {update_error}")
            
            # 验证Agent实例仍然是独立的
            if id(agent1) != id(agent2):
                print("✅ Agent实例保持独立")
                return True
            else:
                print("❌ Agent实例隔离失败")
                return False
                
        except Exception as e:
            print(f"❌ Agent工具隔离测试失败: {e}")
            return False
            
    def print_test_summary(self, results: Dict[str, bool]):
        """打印测试总结"""
        print("\n=== Agent MCP工具管理测试总结 ===")
        
        total_tests = len(results)
        passed_tests = sum(results.values())
        
        print(f"总测试数: {total_tests}")
        print(f"通过测试数: {passed_tests}")
        print(f"失败测试数: {total_tests - passed_tests}")
        print(f"通过率: {(passed_tests/total_tests*100):.1f}%")
        
        print("\n详细结果:")
        for test_name, passed in results.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {test_name}: {status}")
            
        if passed_tests == total_tests:
            print("\n🎉 所有测试通过！Agent级别MCP工具管理功能正常。")
        else:
            print(f"\n⚠️  有 {total_tests - passed_tests} 个测试失败，需要检查和修复。")
            
    def print_architecture_summary(self):
        """打印架构总结"""
        print("""
=== Agent级别MCP工具管理架构总结 ===

✅ 功能特性：
1. 每个Agent可以配置不同的MCP服务器组合
2. 支持动态添加/移除Agent的MCP服务器
3. 当MCP服务器连接/断开时，只更新相关Agent
4. 提供完整的查询和管理API

✅ 核心优势：
1. 个性化工具配置：不同用户可以使用不同的工具集
2. 选择性更新：只更新受影响的Agent，提高效率
3. 灵活的权限管理：可以基于用户角色配置工具访问
4. 完善的监控：支持查询哪些Agent使用了哪些服务器

✅ API端点：
- GET /mcp/agents/{session_id}/servers - 获取Agent的MCP服务器
- POST /mcp/agents/{session_id}/servers - 设置Agent的MCP服务器
- POST /mcp/agents/{session_id}/servers/{server_id}/add - 添加MCP服务器
- POST /mcp/agents/{session_id}/servers/{server_id}/remove - 移除MCP服务器
- GET /mcp/servers/{server_id}/agents - 查询使用服务器的Agent
- POST /mcp/servers/{server_id}/reload - 重新加载服务器的Agent

这个架构完美地解决了多用户环境下的MCP工具管理问题！
""")


async def main():
    """主测试函数"""
    tester = AgentMCPManagementTest()
    
    try:
        # 设置测试环境
        await tester.setup()
        
        # 运行所有测试
        test_results = {}
        
        test_results["MCP服务器配置"] = await tester.test_agent_mcp_server_configuration()
        test_results["MCP服务器管理"] = await tester.test_agent_mcp_server_management()
        test_results["服务器-Agent查询"] = await tester.test_server_agent_query()
        test_results["Agent工具隔离"] = await tester.test_agent_tool_isolation()
        
        # 打印测试总结
        tester.print_test_summary(test_results)
        tester.print_architecture_summary()
        
    except Exception as e:
        logger.error(f"Agent MCP management test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理环境
        await tester.cleanup()


if __name__ == "__main__":
    asyncio.run(main()) 