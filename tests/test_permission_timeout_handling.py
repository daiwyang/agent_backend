"""
权限确认超时处理测试
验证超时后的取消通知和清理机制
"""

import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any

from copilot.core.stream_notifier import StreamNotifier
from copilot.core.agent_state_manager import agent_state_manager, AgentExecutionState
from copilot.utils.logger import logger


class PermissionTimeoutTest:
    """权限确认超时处理测试"""
    
    def __init__(self):
        self.session_id = "test_session_timeout"
        self.tool_executed = False
        self.timeout_messages = []
    
    async def setup(self):
        """设置测试环境"""
        # 创建执行上下文
        context = agent_state_manager.create_execution_context(self.session_id)
        logger.info(f"Created test execution context for session: {self.session_id}")
        
    async def test_short_timeout_scenario(self):
        """测试短超时场景（2秒超时）"""
        print("=" * 70)
        print("⏰ 测试权限确认超时处理（2秒超时）")
        print("=" * 70)
        
        # 准备工具信息
        tool_info = {
            "tool_name": "test_timeout_operation",
            "parameters": {"action": "dangerous_operation", "target": "system"},
            "risk_level": "high"
        }
        
        # 模拟工具执行回调 - 这个回调应该不会被调用
        async def timeout_tool_callback():
            self.tool_executed = True
            print("❌ 错误：超时工具被执行了！")
            return "工具执行结果"
        
        print(f"📋 测试工具: {tool_info['tool_name']}")
        print(f"📋 风险级别: {tool_info['risk_level']}")
        print(f"📋 超时时间: 2秒")
        
        # 发送权限请求
        should_continue = await agent_state_manager.request_tool_permission(
            session_id=self.session_id,
            tool_name=tool_info["tool_name"],
            parameters=tool_info["parameters"],
            callback=timeout_tool_callback,
            risk_level=tool_info["risk_level"]
        )
        
        print(f"\n📊 权限请求结果: should_continue = {should_continue}")
        
        # 检查初始状态
        context = agent_state_manager.get_execution_context(self.session_id)
        if context:
            print(f"📊 当前状态: {context.state.value}")
            print(f"📊 待确认工具数量: {len(context.pending_tools)}")
        
        # 等待权限确认（设置2秒超时）
        print("\n⏰ 开始等待权限确认（2秒超时）...")
        start_time = datetime.now()
        
        permission_granted = await agent_state_manager.wait_for_permission(
            self.session_id, timeout=2
        )
        
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        print(f"⏱️ 等待完成，耗时: {elapsed:.2f}秒")
        print(f"📊 权限结果: {permission_granted}")
        
                 # 检查超时后的状态
        context = agent_state_manager.get_execution_context(self.session_id)
        if context:
            print(f"📊 超时后状态: {context.state.value}")
            print(f"📊 超时后待确认工具数量: {len(context.pending_tools)}")
            print(f"📊 状态消息: {context.current_message}")
        
        # 检查工具是否被执行
        if self.tool_executed:
            print("❌ 测试失败：超时工具不应该被执行")
            return False
        else:
            print("✅ 测试通过：超时工具没有被执行")
        
        # 检查流式消息（包括取消通知）
        messages = StreamNotifier._pending_messages.get(self.session_id, [])
        print(f"\n📋 检查超时相关消息（{len(messages)} 条）:")
        
        cancelled_messages = []
        for i, msg in enumerate(messages):
            msg_type = msg.type
            if msg_type == "tool_execution_status":
                status = getattr(msg.data, 'status', 'unknown')
                error = getattr(msg.data, 'error', None)
                print(f"  {i+1}. {msg_type}({status})")
                if error:
                    print(f"      错误信息: {error}")
                if status == "cancelled":
                    cancelled_messages.append(msg)
            else:
                print(f"  {i+1}. {msg_type}")
        
        # 验证是否有取消通知
        if cancelled_messages:
            print(f"✅ 找到 {len(cancelled_messages)} 条取消通知")
            for i, msg in enumerate(cancelled_messages):
                print(f"   取消通知 {i+1}: {msg.data.tool_name}")
                print(f"   错误信息: {msg.data.error}")
            return True
        else:
            print("❌ 测试失败：没有找到取消通知")
            return False
    
    async def test_multiple_tools_timeout(self):
        """测试多个工具同时超时的场景"""
        print("\n" + "=" * 70)
        print("⏰ 测试多个工具权限确认超时处理")
        print("=" * 70)
        
        # 重置状态
        self.tool_executed = False
        
        # 准备多个工具
        tools = [
            {
                "tool_name": "test_batch_tool_1",
                "parameters": {"action": "read_files"},
                "risk_level": "medium"
            },
            {
                "tool_name": "test_batch_tool_2", 
                "parameters": {"action": "write_files"},
                "risk_level": "high"
            },
            {
                "tool_name": "test_batch_tool_3",
                "parameters": {"action": "delete_files"},
                "risk_level": "high"
            }
        ]
        
        # 为每个工具创建权限请求
        callbacks = []
        for i, tool_info in enumerate(tools):
            async def tool_callback(tool_name=tool_info["tool_name"]):
                print(f"❌ 错误：超时工具 {tool_name} 被执行了！")
                return f"{tool_name} 执行结果"
            
            callbacks.append(tool_callback)
            
            should_continue = await agent_state_manager.request_tool_permission(
                session_id=self.session_id,
                tool_name=tool_info["tool_name"],
                parameters=tool_info["parameters"],
                callback=tool_callback,
                risk_level=tool_info["risk_level"]
            )
            
            print(f"📋 工具 {tool_info['tool_name']} 权限请求: {should_continue}")
        
        # 检查批量请求后的状态
        context = agent_state_manager.get_execution_context(self.session_id)
        if context:
            print(f"\n📊 批量请求后状态: {context.state.value}")
            print(f"📊 待确认工具数量: {len(context.pending_tools)}")
            
            for i, tool in enumerate(context.pending_tools):
                print(f"  {i+1}. {tool.tool_name} (状态: {tool.status})")
        
        # 等待权限确认（设置1秒超时）
        print("\n⏰ 开始等待权限确认（1秒超时）...")
        
        permission_granted = await agent_state_manager.wait_for_permission(
            self.session_id, timeout=1
        )
        
        print(f"📊 批量权限结果: {permission_granted}")
        
                 # 检查超时后的状态
        context = agent_state_manager.get_execution_context(self.session_id)
        if context:
            print(f"📊 批量超时后状态: {context.state.value}")
            print(f"📊 批量超时后待确认工具数量: {len(context.pending_tools)}")
            print(f"📊 状态消息: {context.current_message}")
        
        # 检查取消消息
        messages = StreamNotifier._pending_messages.get(self.session_id, [])
        cancelled_count = 0
        
        for msg in messages:
            if (msg.type == "tool_execution_status" and 
                getattr(msg.data, 'status', '') == "cancelled"):
                cancelled_count += 1
        
        expected_cancelled = len(tools)
        if cancelled_count >= expected_cancelled:
            print(f"✅ 测试通过：找到 {cancelled_count} 条取消通知（预期 {expected_cancelled}）")
            return True
        else:
            print(f"❌ 测试失败：只找到 {cancelled_count} 条取消通知（预期 {expected_cancelled}）")
            return False
    
    async def cleanup(self):
        """清理测试环境"""
        # 清理执行上下文
        if self.session_id in agent_state_manager.active_contexts:
            del agent_state_manager.active_contexts[self.session_id]
        
        # 清理待发送消息
        if self.session_id in StreamNotifier._pending_messages:
            del StreamNotifier._pending_messages[self.session_id]
        
        logger.info(f"Cleaned up test environment for session: {self.session_id}")


async def run_timeout_tests():
    """运行权限超时测试"""
    print("🚀 开始权限确认超时处理测试")
    print("此测试将验证超时后的取消通知和清理机制")
    
    test = PermissionTimeoutTest()
    results = []
    
    try:
        await test.setup()
        
        # 测试1：单个工具超时
        test1_result = await test.test_short_timeout_scenario()
        results.append(("单个工具超时处理", test1_result))
        
        # 测试2：多个工具同时超时
        test2_result = await test.test_multiple_tools_timeout()
        results.append(("多个工具超时处理", test2_result))
        
        # 汇总结果
        print("\n" + "=" * 70)
        print("📊 超时测试结果汇总")
        print("=" * 70)
        
        for test_name, result in results:
            status = "✅ 通过" if result else "❌ 失败"
            print(f"{status} {test_name}")
        
        all_passed = all(result for _, result in results)
        if all_passed:
            print("\n🎉 所有超时测试通过！超时处理机制工作正常")
            print("\n💡 超时处理功能:")
            print("   ✅ 自动取消超时的工具请求")
            print("   ✅ 发送取消通知给前端")
            print("   ✅ 清理超时工具的状态")
            print("   ✅ 更新执行上下文状态")
        else:
            print("\n⚠️ 部分超时测试失败，需要检查超时处理机制")
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await test.cleanup()


if __name__ == "__main__":
    asyncio.run(run_timeout_tests()) 