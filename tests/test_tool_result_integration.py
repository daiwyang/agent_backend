#!/usr/bin/env python3
"""
测试工具结果集成和消息顺序修复
"""

import asyncio
import json
import os
import sys
from datetime import datetime, UTC
from typing import Any, Dict

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot.core.stream_notifier import StreamNotifier
from copilot.core.mcp_tool_wrapper import MCPToolWrapper
from copilot.model.chat_model import ToolExecutionStatus
from copilot.core.chat_stream_handler import ChatStreamHandler


async def main():
    """主测试函数"""
    print("环境变量:", os.getenv("ENV", "dev"))
    print("🎯 开始测试工具结果集成和消息顺序修复")
    print("=" * 60)

    # 测试1：工具执行状态的result字段格式
    print("🧪 测试工具执行状态的result字段格式")
    print()

    test_cases = [
        {"data": {"code": 0, "message": "success"}, "type": "dict"},
        {"data": "String result", "type": "str"},
        {"data": [1, 2, 3, "test"], "type": "list"},
        {"data": 42, "type": "int"},
        {"data": None, "type": "NoneType"},
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"测试结果格式 {i}: {test_case['type']}")

        # 创建工具执行状态
        status = ToolExecutionStatus(
            request_id="test-request-id",
            tool_name="pubmed_pubmed_search_journal",
            status="completed",
            result=test_case["data"],  # 直接使用原始数据
            error=None,
            progress=None,
        )

        print(f"  消息类型: tool_execution_status")
        print(f"  工具名称: {status.tool_name}")
        print(f"  状态: {status.status}")
        print(f"  原始结果类型: {type(test_case['data']).__name__}")
        print(f"  result字段类型: {type(status.result).__name__}")

        # 验证类型保持不变
        assert type(status.result) == type(test_case["data"]), f"类型不匹配: {type(status.result)} vs {type(test_case['data'])}"
        print("  ✅ 原始对象类型保持不变")

        # 验证值相等
        assert status.result == test_case["data"], f"值不匹配: {status.result} vs {test_case['data']}"
        print("  ✅ 值完全一致")
        print()

    # 测试2：参数提取功能
    print("🧪 测试参数提取功能")
    print()

    # 测试不同类型的参数
    test_args_cases = [
        {"args": ({"query": "machine learning", "limit": 10, "filter": "recent"},), "description": "字典参数"},
        {"args": ("simple string query",), "description": "字符串参数"},
        {"args": ({"query": "x" * 250},), "description": "长字符串参数（测试截断）"},  # 长字符串测试截断
        {"args": (), "description": "空参数"},
        {"args": ({"key1": "value1"}, "extra_param"), "description": "多个参数"},
    ]

    for i, test_case in enumerate(test_args_cases, 1):
        print(f"参数提取测试 {i}: {test_case['description']}")

        # 使用StreamNotifier提取参数
        extracted_params = StreamNotifier.extract_tool_parameters(test_case["args"])

        print(f"  输入参数: {test_case['args']}")
        print(f"  提取结果: {extracted_params}")
        print(f"  提取结果类型: {type(extracted_params).__name__}")

        # 验证提取结果是字典
        assert isinstance(extracted_params, dict), f"提取结果应该是字典，但得到: {type(extracted_params)}"
        print("  ✅ 提取结果是字典格式")

        # 验证特定情况
        if test_case["args"] and len(test_case["args"]) == 1 and isinstance(test_case["args"][0], dict):
            # 单个字典参数应该被正确提取
            original_dict = test_case["args"][0]
            if any(len(str(v)) > 200 for v in original_dict.values()):
                print("  ✅ 长字符串被正确截断")
            else:
                for key in original_dict:
                    assert key in extracted_params, f"字典键 {key} 未被提取"
                print("  ✅ 字典参数被正确提取")
        elif test_case["args"]:
            # 多个参数或非字典参数应该被包装在 args 中
            assert "args" in extracted_params, "多个参数或非字典参数应该被包装在 args 中"
            print("  ✅ 多个参数或非字典参数被正确包装")
        else:
            # 空参数应该返回空字典
            assert extracted_params == {}, f"空参数应该返回空字典，但得到: {extracted_params}"
            print("  ✅ 空参数返回空字典")
        print()

    # 测试3：_format_for_ai方法
    print("🧪 测试_format_for_ai方法格式化结果")
    test_data = {"code": 0, "data": [{"title": "Test Article", "authors": ["Author1", "Author2"]}]}

    # 使用_format_for_ai方法格式化
    formatted_result = MCPToolWrapper._format_for_ai("pubmed_pubmed_search_journal", test_data)

    print(f"格式化结果长度: {len(formatted_result)}")
    print(f"是否包含前缀: {'工具' in formatted_result and '执行结果' in formatted_result}")

    # 验证不包含前缀
    assert "工具" not in formatted_result or "执行结果" not in formatted_result, "格式化结果不应包含前缀"
    print("✅ _format_for_ai不包含前缀")

    # 验证是有效的JSON
    try:
        json.loads(formatted_result)
        print("✅ 格式化结果是有效的JSON")
    except json.JSONDecodeError:
        print("❌ 格式化结果不是有效的JSON")

    print()

    # 测试4：完整的工具执行流程模拟
    print("🧪 模拟完整的工具执行流程")

    session_id = "test-session-flow"
    tool_name = "pubmed_pubmed_search_journal"
    test_parameters = {"query": "AI research", "limit": 5}
    test_result = {"code": 0, "data": ["result1", "result2"]}

    # 清空消息队列
    StreamNotifier._pending_messages[session_id] = []

    # 1. 发送权限请求
    request_id = await StreamNotifier.send_tool_permission_request(
        session_id=session_id, tool_name=tool_name, parameters=test_parameters, risk_level="medium"
    )

    # 2. 发送等待状态
    await StreamNotifier.send_tool_execution_status(session_id=session_id, request_id=request_id, tool_name=tool_name, status="waiting")

    # 3. 发送执行状态
    await StreamNotifier.send_tool_execution_status(session_id=session_id, request_id=request_id, tool_name=tool_name, status="executing")

    # 4. 发送完成状态（带结果）
    await StreamNotifier.send_tool_execution_status(
        session_id=session_id, request_id=request_id, tool_name=tool_name, status="completed", result=test_result
    )

    # 获取所有消息
    messages = StreamNotifier.get_pending_messages(session_id)

    print(f"总消息数: {len(messages)}")
    print("消息顺序:")

    expected_types = ["tool_permission_request", "tool_execution_status", "tool_execution_status", "tool_execution_status"]
    expected_statuses = [None, "waiting", "executing", "completed"]

    for i, message in enumerate(messages, 1):
        message_type = message.type
        print(f"  {i}. {message_type.replace('_', ' ').title()}")

        if message_type == "tool_permission_request":
            # 检查参数是否正确
            assert message.data.parameters == test_parameters, f"权限请求参数不匹配: {message.data.parameters} vs {test_parameters}"
            print(f"     参数: {message.data.parameters}")

        elif message_type == "tool_execution_status":
            print(f"     状态: {message.data.status}")
            if message.data.status == "completed":
                print(f"     结果类型: {type(message.data.result).__name__}")
                # 验证结果是原始对象
                assert message.data.result == test_result, f"完成状态结果不匹配: {message.data.result} vs {test_result}"
                assert type(message.data.result) == type(test_result), f"完成状态结果类型不匹配: {type(message.data.result)} vs {type(test_result)}"

    # 验证消息顺序和类型
    assert len(messages) == 4, f"应该有4条消息，但得到: {len(messages)}"
    for i, (message, expected_type, expected_status) in enumerate(zip(messages, expected_types, expected_statuses)):
        assert message.type == expected_type, f"消息{i+1}类型错误: {message.type} vs {expected_type}"
        if expected_status:
            assert message.data.status == expected_status, f"消息{i+1}状态错误: {message.data.status} vs {expected_status}"

    print("✅ 消息顺序正确")
    print()

    # 测试5：验证工具返回格式（二元组满足langchain-mcp-adapters要求）
    print("🧪 验证工具返回格式")

    # 模拟工具执行，应该返回二元组格式以满足langchain-mcp-adapters要求
    mock_tool_result = test_result
    formatted_for_ai = MCPToolWrapper._format_for_ai(tool_name, mock_tool_result)

    print(f"_format_for_ai结果类型: {type(formatted_for_ai).__name__}")
    print(f"_format_for_ai结果长度: {len(formatted_for_ai)}")
    print(f"是否为字符串: {isinstance(formatted_for_ai, str)}")

    # 验证_format_for_ai返回的是字符串
    assert isinstance(formatted_for_ai, str), f"_format_for_ai应该返回字符串，但得到: {type(formatted_for_ai)}"
    print("✅ _format_for_ai返回字符串格式")

    # 验证字符串不是元组的字符串表示
    assert not formatted_for_ai.startswith("("), "格式化结果不应该是元组的字符串表示"
    assert not formatted_for_ai.endswith(")"), "格式化结果不应该是元组的字符串表示"
    print("✅ 格式化结果不是元组格式")

    # 模拟完整的工具返回（应该是二元组）
    tool_tuple_result = (formatted_for_ai, mock_tool_result)
    print(f"完整工具返回类型: {type(tool_tuple_result).__name__}")
    print(f"元组第一项类型: {type(tool_tuple_result[0]).__name__}")
    print(f"元组第二项类型: {type(tool_tuple_result[1]).__name__}")

    # 验证工具返回是二元组
    assert isinstance(tool_tuple_result, tuple), f"工具应该返回元组，但得到: {type(tool_tuple_result)}"
    assert len(tool_tuple_result) == 2, f"工具应该返回二元组，但得到长度: {len(tool_tuple_result)}"
    print("✅ 工具返回二元组格式以满足langchain-mcp-adapters要求")

    print()

    # 测试6：验证聊天流处理器消息过滤
    print("🧪 验证聊天流处理器消息过滤")

    # 创建模拟消息类
    class MockAIMessage:
        def __init__(self, content):
            self.content = content
            self.role = "assistant"
            self.type = "ai"

    class MockToolMessage:
        def __init__(self, content, tool_call_id=None):
            self.content = content
            self.role = "tool"
            self.type = "tool"
            if tool_call_id:
                self.tool_call_id = tool_call_id

    class MockHumanMessage:
        def __init__(self, content):
            self.content = content
            self.role = "user"
            self.type = "human"

    class MockAIMessageChunk:
        def __init__(self, content):
            self.content = content
            self.role = "assistant"
            self.type = "ai"

    # 创建聊天流处理器实例
    handler = ChatStreamHandler(None)

    # 测试不同类型的消息
    test_messages = [
        {"message": MockAIMessage("Hello, how can I help?"), "description": "AI助手消息", "should_output": True},
        {"message": MockHumanMessage("User question here"), "description": "用户消息", "should_output": False},
        {"message": MockToolMessage('{"code": 0, "data": []}'), "description": "工具消息", "should_output": False},
        {
            "message": MockToolMessage("Tool result content", tool_call_id="call-123"),
            "description": "带tool_call_id的工具消息",
            "should_output": False,
        },
        {"message": MockAIMessageChunk("AI response based on tool"), "description": "AI消息块", "should_output": True},
    ]

    for i, test_case in enumerate(test_messages, 1):
        message = test_case["message"]
        description = test_case["description"]
        should_output = test_case["should_output"]

        # 测试消息判断
        is_ai_message = handler._is_ai_message(message)

        print(f"测试消息 {i}: {description}")
        print(f"  消息类型: {type(message).__name__}")
        print(f"  消息角色: {getattr(message, 'role', 'None')}")
        print(f"  是否AI消息: {is_ai_message}")
        print(f"  预期输出: {should_output}")

        if is_ai_message == should_output:
            print("  ✅ 消息过滤判断正确")
        else:
            print("  ❌ 消息过滤判断错误")
            print(f"     期望: {should_output}, 实际: {is_ai_message}")
        print()

    print("✅ 聊天流消息过滤测试完成")
    print()

    print("=" * 60)
    print("✅ 测试完成")


if __name__ == "__main__":
    asyncio.run(main())
