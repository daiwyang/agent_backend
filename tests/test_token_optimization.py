"""
Token计算优化测试
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot.utils.token_calculator import TokenCalculator, TokenUsage


def test_token_calculator():
    """测试Token计算器"""
    print("🧪 测试Token计算器")
    
    # 测试基本token估算
    text = "Hello, this is a test message. 你好，这是一个测试消息。"
    tokens = TokenCalculator.estimate_tokens(text, "gpt-4")
    print(f"📝 文本: {text}")
    print(f"🔢 估算tokens: {tokens}")
    
    # 测试完整用法计算
    prompt = "请帮我写一个Python函数"
    completion = "好的，我来帮你写一个Python函数：\n\ndef example_function():\n    return 'Hello World'"
    
    usage = TokenCalculator.calculate_usage(prompt, completion, "deepseek")
    print(f"\n💬 对话token统计:")
    print(f"   用户输入: {usage.prompt_tokens} tokens")
    print(f"   模型回复: {usage.completion_tokens} tokens") 
    print(f"   总计: {usage.total_tokens} tokens")
    
    # 测试安全提取
    test_data = {"prompt_tokens": 15, "completion_tokens": 25, "total_tokens": 40}
    safe_usage = TokenCalculator.safe_extract_tokens(test_data)
    print(f"\n🛡️ 安全提取测试: {safe_usage.to_dict()}")
    
    # 测试错误情况
    invalid_data = None
    safe_usage_none = TokenCalculator.safe_extract_tokens(invalid_data)
    print(f"🚫 None数据处理: {safe_usage_none.to_dict()}")
    
    print("✅ Token计算器测试完成！")


def test_model_mapping():
    """测试模型映射"""
    print("\n🗺️ 测试模型映射")
    
    test_cases = [
        ("openai", "gpt-4-turbo"),
        ("deepseek", "deepseek-chat"),
        ("claude", "claude-3-sonnet"),
        ("qwen", "qwen-max"),
        ("unknown", "unknown-model")
    ]
    
    for provider, model in test_cases:
        key = TokenCalculator.get_model_key(provider, model)
        print(f"🔑 {provider}/{model} -> {key}")
    
    print("✅ 模型映射测试完成！")


if __name__ == "__main__":
    test_token_calculator()
    test_model_mapping()
    print("\n🎉 所有测试完成！")
