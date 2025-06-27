"""
验证Token优化修复效果
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from copilot.core.agent import CoreAgent


def test_missing_method_fix():
    """测试缺失方法修复"""
    print("🔍 测试_estimate_token_usage方法是否存在...")
    
    try:
        # 初始化CoreAgent
        agent = CoreAgent(provider="deepseek")
        
        # 检查方法是否存在
        if hasattr(agent, '_estimate_token_usage'):
            print("✅ _estimate_token_usage方法存在")
            
            # 测试方法调用
            result = agent._estimate_token_usage("测试输入", "测试回复")
            print(f"📊 方法调用成功，返回: {result}")
            
            # 验证返回格式
            required_keys = ["prompt_tokens", "completion_tokens", "total_tokens"]
            if all(key in result for key in required_keys):
                print("✅ 返回格式正确，包含所有必需字段")
            else:
                print("❌ 返回格式不完整")
                
        else:
            print("❌ _estimate_token_usage方法不存在")
            
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")


def test_chat_service_integration():
    """测试ChatService集成"""
    print("\n🔗 测试ChatService集成...")
    
    try:
        from copilot.service.chat_service import ChatService
        
        service = ChatService(provider="deepseek")
        print("✅ ChatService初始化成功")
        
        # 测试token计算器可用性
        if hasattr(service.core_agent, '_estimate_token_usage'):
            token_usage = service.core_agent._estimate_token_usage(
                "用户输入测试", "助手回复测试"
            )
            print(f"✅ ChatService可以正常调用token估算: {token_usage}")
        else:
            print("❌ ChatService无法调用token估算")
            
    except Exception as e:
        print(f"❌ ChatService集成测试失败: {e}")


if __name__ == "__main__":
    test_missing_method_fix()
    test_chat_service_integration()
    print("\n🎉 验证测试完成！")
