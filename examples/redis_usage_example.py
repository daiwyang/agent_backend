"""
重构后的 Redis 客户端使用示例

展示了新的简洁、智能的 Redis 客户端使用方式
"""

import asyncio
from copilot.utils.redis_client import get_redis, redis_client, init_redis, close_redis


async def main():
    """主要的使用示例"""
    
    # 1. 初始化 Redis 连接（应用启动时）
    await init_redis()
    print("✅ Redis 初始化完成")
    
    # 2. 使用推荐的上下文管理器方式（推荐）
    async with get_redis() as redis:
        # 基础操作
        await redis.set("test_key", "hello world", ex=60)
        value = await redis.get("test_key")
        print(f"获取到的值: {value}")
        
        # 集合操作
        await redis.sadd("test_set", "item1", "item2", "item3")
        members = await redis.smembers("test_set")
        print(f"集合成员: {members}")
        
        # 健康检查
        is_healthy = await redis.ping()
        print(f"Redis 健康状态: {is_healthy}")
    
    # 3. 直接使用全局实例（适合简单场景）
    await redis_client.set("simple_key", "simple_value")
    simple_value = await redis_client.get("simple_key")
    print(f"简单获取: {simple_value}")
    
    # 4. 便捷方法示例
    async def expensive_operation():
        """模拟耗时操作"""
        await asyncio.sleep(0.1)
        return "cached_result"
    
    # 缓存操作：如果不存在则计算并设置
    result = await redis_client.get_or_set(
        "cache_key", 
        expensive_operation, 
        ex=300  # 5分钟过期
    )
    print(f"缓存结果: {result}")
    
    # 5. 计数器操作
    counter = await redis_client.increment_with_expire("counter", amount=1, ex=3600)
    print(f"计数器值: {counter}")
    
    # 6. 安全的键扫描（替代 KEYS 命令）
    async for key in redis_client.scan_iter(match="test_*", count=100):
        print(f"扫描到的键: {key}")
    
    # 清理
    await redis_client.delete("test_key", "test_set", "simple_key", "cache_key", "counter")
    
    # 7. 应用关闭时
    await close_redis()
    print("✅ Redis 连接已关闭")


async def session_example():
    """会话管理示例"""
    await init_redis()
    
    # 用户会话管理
    session_id = "user_123_session"
    session_data = {
        "user_id": "123",
        "username": "alice",
        "login_time": "2025-01-01T10:00:00Z"
    }
    
    async with get_redis() as redis:
        # 存储会话，30分钟过期
        await redis.set(f"session:{session_id}", str(session_data), ex=1800)
        
        # 检查会话是否存在
        exists = await redis.exists(f"session:{session_id}")
        if exists:
            print("✅ 会话有效")
        
        # 延长会话时间
        await redis.expire(f"session:{session_id}", 3600)
        
        # 获取剩余时间
        ttl = await redis.ttl(f"session:{session_id}")
        print(f"会话剩余时间: {ttl} 秒")
    
    await close_redis()


async def error_handling_example():
    """异常处理示例"""
    await init_redis()
    
    try:
        async with get_redis() as redis:
            # 这些操作会被自动记录异常日志
            await redis.get("some_key")
            await redis.set("some_key", "some_value")
            
    except Exception as e:
        print(f"处理 Redis 异常: {e}")
        # 异常已经被自动记录到日志中
    
    await close_redis()


if __name__ == "__main__":
    print("🚀 Redis 客户端使用示例")
    print("=" * 50)
    
    # 运行基础示例
    asyncio.run(main())
    
    print("\n" + "=" * 50)
    print("📝 会话管理示例")
    asyncio.run(session_example())
    
    print("\n" + "=" * 50)
    print("⚠️ 异常处理示例")
    asyncio.run(error_handling_example())
