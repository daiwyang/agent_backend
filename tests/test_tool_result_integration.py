#!/usr/bin/env python3
"""
测试工具结果集成和消息顺序的修复效果
"""
import asyncio
import json
from typing import Dict, List, Any
from unittest.mock import AsyncMock, MagicMock

from copilot.core.stream_notifier import StreamNotifier


async def test_tool_execution_status_result():
    """测试工具执行状态的result字段格式"""
    print("🧪 测试工具执行状态的result字段格式")
    
    # 模拟工具执行信息
    tool_info = {
        "tool_name": "pubmed_pubmed_search_journal",
        "parameters": {},
        "request_id": "test-request-123"
    }
    
    # 模拟工具结果 - 这里模拟不同格式的结果
    test_results = [
        # 字典格式
        {
            "code": 0,
            "data": [
                {
                    "journal_full_name": "CA-A CANCER JOURNAL FOR CLINICIANS",
                    "journal_name": "CA-CANCER J CLIN",
                    "issn": "0007-9235",
                    "IF": 232.4,
                    "category": "ONCOLOGY"
                }
            ]
        },
        # 字符串格式
        "工具执行成功，返回了10个期刊信息",
        # 列表格式
        [{"journal": "Nature", "IF": 42.8}, {"journal": "Science", "IF": 41.0}],
        # 数字格式
        12345,
        # None值
        None
    ]
    
    for i, mock_result in enumerate(test_results):
        print(f"\n测试结果格式 {i+1}: {type(mock_result).__name__}")
        
        # 模拟StreamNotifier的消息队列
        StreamNotifier._pending_messages = {}
        
        # 测试notify_tool_execution_complete
        session_id = f"test-session-{i}"
        await StreamNotifier.notify_tool_execution_complete(
            session_id=session_id,
            tool_info=tool_info,
            result=mock_result,
            success=True
        )
        
        # 检查发送的消息
        messages = StreamNotifier.get_pending_messages(session_id)
        
        if messages:
            message = messages[0]
            print(f"  消息类型: {message.type}")
            print(f"  工具名称: {message.data.tool_name}")
            print(f"  状态: {message.data.status}")
            print(f"  原始结果类型: {type(mock_result).__name__}")
            print(f"  result字段类型: {type(message.data.result).__name__}")
            
            # 验证类型是否保持一致
            if type(message.data.result) == type(mock_result):
                print(f"  ✅ 原始对象类型保持不变")
                # 对于结构化数据，验证内容
                if isinstance(mock_result, dict) and message.data.result == mock_result:
                    print(f"  ✅ 字典内容完全一致")
                elif isinstance(mock_result, list) and message.data.result == mock_result:
                    print(f"  ✅ 列表内容完全一致")
                elif mock_result == message.data.result:
                    print(f"  ✅ 值完全一致")
            else:
                print(f"  ❌ 对象类型被改变")
                print(f"     期望: {type(mock_result).__name__}")
                print(f"     实际: {type(message.data.result).__name__}")
        else:
            print("  ❌ 没有发送消息")


async def test_format_for_ai():
    """测试_format_for_ai方法是否不包含前缀"""
    print("\n🧪 测试_format_for_ai方法格式化结果")
    
    from copilot.core.mcp_tool_wrapper import MCPToolWrapper
    
    # 模拟工具结果
    mock_result = {
        "code": 0,
        "data": [
            {
                "journal_name": "Test Journal",
                "IF": 10.5
            }
        ]
    }
    
    # 测试格式化结果
    formatted_result = MCPToolWrapper._format_for_ai("test_tool", mock_result)
    
    print(f"格式化结果长度: {len(formatted_result)}")
    print(f"是否包含前缀: {'工具' in formatted_result}")
    
    # 检查是否不包含前缀
    if "工具" not in formatted_result and "执行结果" not in formatted_result:
        print("✅ _format_for_ai不包含前缀")
    else:
        print("❌ _format_for_ai仍然包含前缀")
        print(f"前50个字符: {formatted_result[:50]}")
    
    # 检查是否是有效的JSON
    try:
        parsed = json.loads(formatted_result)
        print("✅ 格式化结果是有效的JSON")
    except json.JSONDecodeError:
        print("❌ 格式化结果不是有效的JSON")


async def simulate_tool_execution_flow():
    """模拟完整的工具执行流程"""
    print("\n🧪 模拟完整的工具执行流程")
    
    session_id = "test-session-flow"
    tool_name = "pubmed_pubmed_search_journal"
    
    # 清空消息队列
    StreamNotifier._pending_messages = {}
    
    # 步骤1: 发送权限请求
    request_id = await StreamNotifier.send_tool_permission_request(
        session_id=session_id,
        tool_name=tool_name,
        parameters={},
        risk_level="medium"
    )
    
    # 步骤2: 发送等待状态
    await StreamNotifier.send_tool_execution_status(
        session_id=session_id,
        request_id=request_id,
        tool_name=tool_name,
        status="waiting"
    )
    
    # 步骤3: 发送执行状态
    await StreamNotifier.send_tool_execution_status(
        session_id=session_id,
        request_id=request_id,
        tool_name=tool_name,
        status="executing"
    )
    
    # 步骤4: 发送完成状态（带结果）
    mock_result = {
        "code": 0,
        "data": [{"journal_name": "Test Journal", "IF": 10.5}]
    }
    
    tool_info = {
        "tool_name": tool_name,
        "request_id": request_id,
        "parameters": {}
    }
    
    await StreamNotifier.notify_tool_execution_complete(
        session_id=session_id,
        tool_info=tool_info,
        result=mock_result,
        success=True
    )
    
    # 检查消息顺序
    messages = StreamNotifier.get_pending_messages(session_id)
    
    print(f"总消息数: {len(messages)}")
    print("消息顺序:")
    for i, msg in enumerate(messages):
        if msg.type == "tool_permission_request":
            print(f"  {i+1}. 权限请求")
        elif msg.type == "tool_execution_status":
            print(f"  {i+1}. 执行状态: {msg.data.status}")
            if msg.data.result:
                result_type = type(msg.data.result).__name__
                print(f"     结果类型: {result_type}")
    
    # 验证顺序
    expected_sequence = ["tool_permission_request", "waiting", "executing", "completed"]
    actual_sequence = []
    
    for msg in messages:
        if msg.type == "tool_permission_request":
            actual_sequence.append("tool_permission_request")
        elif msg.type == "tool_execution_status":
            actual_sequence.append(msg.data.status)
    
    if actual_sequence == expected_sequence:
        print("✅ 消息顺序正确")
    else:
        print("❌ 消息顺序错误")
        print(f"期望: {expected_sequence}")
        print(f"实际: {actual_sequence}")


async def main():
    """主测试函数"""
    print("🎯 开始测试工具结果集成和消息顺序修复")
    print("=" * 60)
    
    await test_tool_execution_status_result()
    await test_format_for_ai()
    await simulate_tool_execution_flow()
    
    print("\n" + "=" * 60)
    print("✅ 测试完成")


if __name__ == "__main__":
    asyncio.run(main()) 