"""
聊天历史管理示例
演示如何使用新的聊天历史持久化功能
"""

import asyncio
from datetime import datetime
from copilot.agent.multi_session_agent import MultiSessionAgent
from copilot.agent.chat_history_manager import chat_history_manager
from copilot.utils.logger import logger


async def demo_chat_history():
    """演示聊天历史管理功能"""
    
    logger.info("🚀 开始聊天历史管理演示...")
    
    # 创建Agent实例
    agent = MultiSessionAgent()
    
    # 用户信息
    user_id = "demo_user_001"
    window_id = "window_001"
    
    try:
        # 1. 创建会话
        logger.info("📝 创建新会话...")
        session_id = await agent.create_session(user_id, window_id)
        logger.info(f"✅ 会话创建成功: {session_id}")
        
        # 2. 进行几轮对话
        logger.info("💬 开始对话...")
        messages = [
            "你好！",
            "今天天气怎么样？",
            "请帮我写一个Python函数",
            "谢谢你的帮助"
        ]
        
        for i, message in enumerate(messages, 1):
            logger.info(f"👤 用户消息 {i}: {message}")
            
            try:
                response = await agent.chat(session_id, message)
                for msg in response.messages:
                    logger.info(f"🤖 AI响应 {i}: {msg.content[:100]}...")
            except Exception as e:
                logger.error(f"❌ 对话失败: {str(e)}")
        
        # 3. 获取内存中的聊天历史
        logger.info("📖 获取内存中的聊天历史...")
        memory_history = await agent.get_chat_history(session_id, from_db=False)
        logger.info(f"内存历史消息数量: {len(memory_history)}")
        
        # 4. 获取数据库中的聊天历史
        logger.info("🗄️ 获取数据库中的聊天历史...")
        db_history = await agent.get_chat_history(session_id, from_db=True)
        logger.info(f"数据库历史消息数量: {len(db_history)}")
        
        for msg in db_history:
            logger.info(f"  {msg.role}: {msg.content[:50]}...")
        
        # 5. 模拟会话超时（删除Redis中的会话）
        logger.info("⏰ 模拟会话超时...")
        await agent.delete_session(session_id, archive=True)
        
        # 6. 尝试恢复会话
        logger.info("🔄 尝试恢复会话...")
        restored_session = await agent.session_manager.get_session(session_id)
        if restored_session:
            logger.info("✅ 会话成功从数据库恢复!")
            
            # 继续对话
            continue_message = "会话恢复后的第一条消息"
            logger.info(f"👤 恢复后消息: {continue_message}")
            response = await agent.chat(session_id, continue_message)
            for msg in response.messages:
                logger.info(f"🤖 恢复后响应: {msg.content[:100]}...")
        else:
            logger.warning("⚠️ 会话恢复失败")
        
        # 7. 获取用户的所有聊天历史
        logger.info("📚 获取用户的所有聊天历史...")
        user_history = await agent.get_user_chat_history(user_id)
        logger.info(f"用户总会话数: {len(user_history)}")
        
        # 8. 搜索聊天历史
        logger.info("🔍 搜索聊天历史...")
        search_results = await agent.search_chat_history(user_id, "天气", limit=5)
        logger.info(f"搜索结果数量: {len(search_results)}")
        for result in search_results:
            logger.info(f"  找到: {result['content'][:50]}...")
        
        # 9. 获取统计信息
        logger.info("📊 获取统计信息...")
        stats = await agent.get_chat_stats(user_id)
        logger.info(f"统计信息: {stats}")
        
        # 10. 最终清理（可选）
        logger.info("🧹 清理演示数据...")
        await chat_history_manager.delete_session(session_id, hard_delete=True)
        logger.info("✅ 演示数据清理完成")
        
        logger.info("🎉 聊天历史管理演示完成!")
        
    except Exception as e:
        logger.error(f"💥 演示过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()


async def demo_persistence_benefits():
    """演示持久化的好处"""
    
    logger.info("🎯 演示持久化的好处...")
    
    agent = MultiSessionAgent()
    user_id = "persistence_demo_user"
    
    # 创建会话并进行对话
    session_id = await agent.create_session(user_id, "demo_window")
    
    # 保存一些重要信息
    important_messages = [
        "我的生日是1990年5月15日",
        "我住在北京市朝阳区",
        "我的工作是软件工程师",
        "我喜欢阅读和编程"
    ]
    
    logger.info("💾 保存重要个人信息...")
    for msg in important_messages:
        await agent.chat(session_id, msg)
    
    # 模拟会话超时
    logger.info("⏱️ 模拟会话超时...")
    await agent.delete_session(session_id, archive=True)
    
    # 一段时间后，用户返回...
    logger.info("👋 用户重新开始对话...")
    
    # 创建新会话
    new_session_id = await agent.create_session(user_id, "new_window")
    
    # 查找之前的对话历史
    logger.info("🔍 查找用户历史信息...")
    birthday_results = await agent.search_chat_history(user_id, "生日")
    location_results = await agent.search_chat_history(user_id, "北京")
    
    if birthday_results:
        logger.info(f"找到生日信息: {birthday_results[0]['content']}")
    if location_results:
        logger.info(f"找到地址信息: {location_results[0]['content']}")
    
    logger.info("✨ 持久化让我们能够:")
    logger.info("  1. 跨会话保持用户信息")
    logger.info("  2. 提供连续的用户体验")
    logger.info("  3. 支持历史对话检索")
    logger.info("  4. 进行数据分析和改进")


async def main():
    """主函数"""
    try:
        await demo_chat_history()
        print("\n" + "="*50 + "\n")
        await demo_persistence_benefits()
        
    except Exception as e:
        logger.error(f"演示失败: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
