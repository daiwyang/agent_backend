#!/usr/bin/env python3
"""
测试AI思考和回答分类功能
"""

import asyncio
import os
import sys
from typing import Any, Dict

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot.core.chat_stream_handler import ChatStreamHandler


class MockAIMessage:
    """模拟AI消息"""

    def __init__(self, content: str, tool_calls=None, additional_kwargs=None):
        self.content = content
        self.role = "assistant"
        self.type = "ai"
        self.tool_calls = tool_calls or []
        self.additional_kwargs = additional_kwargs or {}


async def main():
    """主测试函数"""
    print("🧪 测试AI思考和回答分类功能")
    print("=" * 60)

    # 创建聊天流处理器实例
    handler = ChatStreamHandler(None)

    # 测试用例
    test_cases = [
        # 工具相关思考
        {
            "message": MockAIMessage(
                "我需要查询相关的机器学习期刊信息来回答您的问题。", tool_calls=[{"id": "call_1", "function": {"name": "pubmed_search"}}]
            ),
            "description": "思考阶段 - 有工具调用 + 思考模式",
            "expected": "thinking",
        },
        {
            "message": MockAIMessage("让我为您搜索一下高影响因子的期刊。", tool_calls=[{"id": "call_1", "function": {"name": "pubmed_search"}}]),
            "description": "思考阶段 - 有工具调用 + 让我模式",
            "expected": "thinking",
        },
        {
            "message": MockAIMessage("为了回答您的问题，我需要使用搜索工具。", tool_calls=[{"id": "call_1", "function": {"name": "search"}}]),
            "description": "思考阶段 - 有工具调用 + 为了回答模式",
            "expected": "thinking",
        },
        # 非工具相关思考 - 问题分析
        {
            "message": MockAIMessage("这个问题需要我们从多个角度来分析。首先，我们要考虑技术可行性..."),
            "description": "思考阶段 - 问题分析（无工具）",
            "expected": "thinking",
        },
        {
            "message": MockAIMessage("让我分析一下这个算法的时间复杂度。考虑到数据量的增长..."),
            "description": "思考阶段 - 算法分析（无工具）",
            "expected": "thinking",
        },
        {
            "message": MockAIMessage("考虑到您的需求，关键在于如何平衡性能和可维护性"),
            "description": "思考阶段 - 需求分析（无工具）",
            "expected": "thinking",
        },
        {
            "message": MockAIMessage("值得思考的是，这种设计模式在不同场景下的适用性"),
            "description": "思考阶段 - 设计分析（无工具）",
            "expected": "thinking",
        },
        # 非工具相关思考 - 推理过程
        {
            "message": MockAIMessage("从逻辑上讲，如果我们采用这种方法，会带来以下好处..."),
            "description": "思考阶段 - 逻辑推理（无工具）",
            "expected": "thinking",
        },
        {
            "message": MockAIMessage("综合考虑各种因素，我认为最佳方案应该包含以下要素"),
            "description": "思考阶段 - 综合分析（无工具）",
            "expected": "thinking",
        },
        {"message": MockAIMessage("权衡利弊后，我建议采用渐进式的实施策略"), "description": "思考阶段 - 权衡分析（无工具）", "expected": "thinking"},
        # 非工具相关思考 - 方案规划
        {
            "message": MockAIMessage("制定策略时，我们需要按照以下步骤进行：1) 需求调研..."),
            "description": "思考阶段 - 策略制定（无工具）",
            "expected": "thinking",
        },
        {
            "message": MockAIMessage("设计思路应该遵循模块化原则，具体实现可以分为几个阶段"),
            "description": "思考阶段 - 设计规划（无工具）",
            "expected": "thinking",
        },
        # 回答阶段
        {
            "message": MockAIMessage("根据查询结果，我为您推荐以下高影响因子期刊："),
            "description": "回答阶段 - 根据查询结果模式",
            "expected": "response",
        },
        {"message": MockAIMessage("基于搜索结果，以下是相关的期刊信息："), "description": "回答阶段 - 基于搜索结果模式", "expected": "response"},
        {"message": MockAIMessage("查询结果显示有以下期刊符合您的要求："), "description": "回答阶段 - 查询结果显示模式", "expected": "response"},
        # 默认消息
        {"message": MockAIMessage("您好！我是AI助手，很高兴为您服务。"), "description": "普通消息 - 无特殊模式", "expected": "default"},
        {"message": MockAIMessage("机器学习是一个非常有趣的领域，包含多个子领域。"), "description": "普通消息 - 直接回答", "expected": "default"},
        # 工具调用但无明确模式
        {
            "message": MockAIMessage("这里有一些相关信息...", tool_calls=[{"id": "call_1", "function": {"name": "search"}}]),
            "description": "思考阶段 - 有工具调用但无明确思考模式",
            "expected": "thinking",
        },
        # 英文测试
        {
            "message": MockAIMessage("I need to search for relevant journals.", tool_calls=[{"id": "call_1", "function": {"name": "search"}}]),
            "description": "英文思考阶段 - 工具相关",
            "expected": "thinking",
        },
        {
            "message": MockAIMessage("Let me analyze this problem from different perspectives."),
            "description": "英文思考阶段 - 问题分析（无工具）",
            "expected": "thinking",
        },
        {
            "message": MockAIMessage("Considering the complexity, we need to think deeper about the solution."),
            "description": "英文思考阶段 - 深度分析（无工具）",
            "expected": "thinking",
        },
        {"message": MockAIMessage("Based on the results, here are the recommended journals:"), "description": "英文回答阶段", "expected": "response"},
    ]

    # 执行测试
    passed = 0
    failed = 0

    for i, test_case in enumerate(test_cases, 1):
        message = test_case["message"]
        description = test_case["description"]
        expected = test_case["expected"]

        # 测试分类
        result = handler._classify_ai_message(message)

        print(f"测试 {i}: {description}")
        print(f"  消息内容: {message.content[:50]}...")
        print(f"  是否有工具调用: {bool(message.tool_calls)}")
        print(f"  期望分类: {expected}")
        print(f"  实际分类: {result}")

        if result == expected:
            print("  ✅ 分类正确")
            passed += 1
        else:
            print("  ❌ 分类错误")
            failed += 1
        print()

    # 测试格式化输出
    print("🧪 测试格式化输出")
    print("-" * 30)

    thinking_message = MockAIMessage("我需要查询相关信息", tool_calls=[{"id": "call_1"}])
    response_message = MockAIMessage("根据查询结果，答案是...")
    default_message = MockAIMessage("您好，我是AI助手")

    thinking_type = handler._classify_ai_message(thinking_message)
    response_type = handler._classify_ai_message(response_message)
    default_type = handler._classify_ai_message(default_message)

    print(f"思考消息格式化:")
    if thinking_type == "thinking":
        print(f"  🤔 **AI思考中**：{thinking_message.content}")

    print(f"回答消息格式化:")
    if response_type == "response":
        print(f"  💬 **AI回答**：{response_message.content}")

    print(f"默认消息格式化:")
    if default_type == "default":
        print(f"  {default_message.content}")

    print()
    print("=" * 60)
    print(f"✅ 测试完成！通过: {passed}, 失败: {failed}")

    if failed == 0:
        print("🎉 所有测试都通过了！")
    else:
        print(f"⚠️  有 {failed} 个测试失败，需要优化分类逻辑")


if __name__ == "__main__":
    asyncio.run(main())
