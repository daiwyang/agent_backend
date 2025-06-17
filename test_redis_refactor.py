#!/usr/bin/env python3
"""
测试重构后的 Redis 客户端
"""

import asyncio
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, '/data/agent_backend')

from copilot.utils.redis_client import get_redis, redis_client, init_redis, close_redis


async def test_redis_functionality():
    """测试 Redis 客户端功能"""
    print("🧪 开始测试 Redis 客户端...")
    
    try:
        # 初始化
        await init_redis()
        print("✅ Redis 初始化成功")
        
        # 测试基础操作
        async with get_redis() as redis:
            # 测试设置和获取
            await redis.set("test_key", "hello_world", ex=60)
            value = await redis.get("test_key")
            assert value == "hello_world", f"期望 'hello_world'，实际 '{value}'"
            print("✅ 基础 set/get 操作正常")
            
            # 测试集合操作
            await redis.sadd("test_set", "item1", "item2")
            members = await redis.smembers("test_set")
            assert "item1" in members and "item2" in members
            print("✅ 集合操作正常")
            
            # 测试健康检查
            is_healthy = await redis.ping()
            assert is_healthy is True
            print("✅ 健康检查正常")
            
            # 测试过期时间
            ttl = await redis.ttl("test_key")
            assert ttl > 0 and ttl <= 60
            print("✅ TTL 操作正常")
        
        # 测试全局实例
        await redis_client.set("global_test", "global_value")
        global_value = await redis_client.get("global_test")
        assert global_value == "global_value"
        print("✅ 全局实例操作正常")
        
        # 测试便捷方法
        call_count = 0
        async def expensive_func():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"
        
        # 第一次调用应该执行函数
        result1 = await redis_client.get_or_set("cache_test", expensive_func, ex=60)
        # 第二次调用应该从缓存获取
        result2 = await redis_client.get_or_set("cache_test", expensive_func, ex=60)
        
        assert result1 == result2 == "result_1"
        assert call_count == 1  # 函数只被调用一次
        print("✅ 缓存便捷方法正常")
        
        # 测试计数器
        counter1 = await redis_client.increment_with_expire("counter_test", 1, 60)
        counter2 = await redis_client.increment_with_expire("counter_test", 2, 60)
        assert counter1 == 1 and counter2 == 3
        print("✅ 计数器操作正常")
        
        # 清理测试数据
        await redis_client.delete("test_key", "test_set", "global_test", "cache_test", "counter_test")
        print("✅ 清理测试数据完成")
        
        # 关闭连接
        await close_redis()
        print("✅ Redis 连接关闭成功")
        
        print("\n🎉 所有测试通过！新的 Redis 客户端工作正常。")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_redis_functionality())
    sys.exit(0 if success else 1)
