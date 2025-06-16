"""
完整测试套件
运行所有测试模块
"""

import asyncio
import sys
import argparse
from typing import List

from test_authentication import AuthenticationTester
from test_session_management import SessionTester
from test_chat_functionality import ChatTester


class TestSuite:
    """测试套件管理器"""
    
    def __init__(self):
        self.testers = {
            "auth": AuthenticationTester,
            "session": SessionTester,
            "chat": ChatTester
        }
    
    async def run_test(self, test_name: str):
        """运行单个测试"""
        if test_name not in self.testers:
            print(f"❌ 未知的测试模块: {test_name}")
            print(f"可用的测试模块: {', '.join(self.testers.keys())}")
            return False
        
        tester_class = self.testers[test_name]
        tester = tester_class()
        
        try:
            await tester.run_all_tests()
            return True
        except Exception as e:
            print(f"❌ 测试模块 {test_name} 执行失败: {e}")
            return False
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("🧪 开始完整测试套件...")
        print("=" * 80)
        
        results = {}
        test_order = ["auth", "session", "chat"]
        
        for test_name in test_order:
            print(f"\n🔄 运行 {test_name} 测试...")
            try:
                success = await self.run_test(test_name)
                results[test_name] = success
            except Exception as e:
                print(f"❌ {test_name} 测试异常: {e}")
                results[test_name] = False
            
            print(f"{'✅' if results[test_name] else '❌'} {test_name} 测试完成")
        
        # 输出测试总结
        print("\n" + "=" * 80)
        print("📊 测试结果总结:")
        print("=" * 80)
        
        success_count = sum(1 for success in results.values() if success)
        total_count = len(results)
        
        for test_name, success in results.items():
            status = "✅ 通过" if success else "❌ 失败"
            print(f"{test_name:20} : {status}")
        
        print("-" * 80)
        print(f"总计: {success_count}/{total_count} 测试通过")
        
        if success_count == total_count:
            print("🎉 所有测试都通过了！")
        else:
            print("⚠️  部分测试失败，请检查日志")
        
        return success_count == total_count


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="Agent Backend 测试套件")
    parser.add_argument(
        "--test", 
        choices=["all", "auth", "session", "chat"],
        default="all",
        help="要运行的测试模块"
    )
    parser.add_argument(
        "--server",
        default="http://localhost:8000", 
        help="服务器地址"
    )
    
    args = parser.parse_args()
    
    # 设置服务器地址
    if args.server != "http://localhost:8000":
        from test_config import TestConfig
        TestConfig.BASE_URL = args.server
    
    print(f"🚀 Agent Backend 测试套件")
    print(f"📡 目标服务器: {args.server}")
    print(f"🧪 测试模块: {args.test}")
    
    suite = TestSuite()
    
    try:
        if args.test == "all":
            success = await suite.run_all_tests()
        else:
            success = await suite.run_test(args.test)
        
        # 设置退出代码
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 测试套件执行异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
