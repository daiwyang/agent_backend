"""
数据库索引初始化脚本
为聊天历史管理创建必要的MongoDB索引
"""

import asyncio
from copilot.utils.mongo_client import MongoClient
from copilot.utils.logger import logger


async def create_indexes():
    """创建必要的数据库索引"""
    
    async with MongoClient() as mongo:
        try:
            # 为chat_sessions集合创建索引
            logger.info("Creating indexes for chat_sessions collection...")
            
            # 1. session_id 唯一索引
            await mongo.create_index("chat_sessions", "session_id", unique=True)
            
            # 2. user_id 索引（用于查询用户的所有会话）
            await mongo.create_index("chat_sessions", "user_id")
            
            # 3. 状态索引（用于过滤活跃/归档/删除的会话）
            await mongo.create_index("chat_sessions", "status")
            
            # 4. 复合索引：user_id + status（优化用户活跃会话查询）
            await mongo.create_index("chat_sessions", [("user_id", 1), ("status", 1)])
            
            # 5. last_activity 索引（用于按最后活动时间排序）
            await mongo.create_index("chat_sessions", "last_activity")
            
            
            # 为chat_messages集合创建索引
            logger.info("Creating indexes for chat_messages collection...")
            
            # 1. session_id 索引（用于查询会话的所有消息）
            await mongo.create_index("chat_messages", "session_id")
            
            # 2. timestamp 索引（用于按时间排序）
            await mongo.create_index("chat_messages", "timestamp")
            
            # 3. 复合索引：session_id + timestamp（优化会话消息查询）
            await mongo.create_index("chat_messages", [("session_id", 1), ("timestamp", 1)])
            
            # 4. 文本搜索索引（用于内容搜索）
            await mongo.create_index("chat_messages", [("content", "text")])
            
            # 5. role 索引（用于按角色过滤消息）
            await mongo.create_index("chat_messages", "role")
            
            logger.info("✅ All indexes created successfully!")
            
        except Exception as e:
            logger.error(f"❌ Failed to create indexes: {str(e)}")
            raise


async def main():
    """主函数"""
    logger.info("🚀 Starting database index initialization...")
    
    try:
        await create_indexes()
        logger.info("🎉 Database index initialization completed!")
        
    except Exception as e:
        logger.error(f"💥 Database index initialization failed: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
