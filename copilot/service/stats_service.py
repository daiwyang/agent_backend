"""
统计服务 - 处理聊天统计相关功能
"""

from typing import Dict, Any, List, Optional
from copilot.utils.logger import logger


class StatsService:
    """统计服务"""

    def __init__(self):
        self._chat_history_manager = None

    @property
    def chat_history_manager(self):
        """延迟初始化聊天历史管理器"""
        if self._chat_history_manager is None:
            from copilot.service.history_service import chat_history_manager

            self._chat_history_manager = chat_history_manager
        return self._chat_history_manager

    async def get_user_chat_history(self, user_id: str) -> List:
        """获取用户的所有聊天历史"""
        try:
            return await self.chat_history_manager.get_user_chat_history(user_id)
        except Exception as e:
            logger.error(f"Error getting user chat history: {str(e)}")
            return []

    async def search_chat_history(self, user_id: str, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """搜索用户的聊天历史"""
        try:
            return await self.chat_history_manager.search_chat_history(user_id, query, limit)
        except Exception as e:
            logger.error(f"Error searching chat history: {str(e)}")
            return []

    async def get_chat_stats(self, user_id: str = None) -> Dict[str, Any]:
        """获取聊天统计信息"""
        try:
            return await self.chat_history_manager.get_chat_stats(user_id)
        except Exception as e:
            logger.error(f"Error getting chat stats: {str(e)}")
            return {"total_messages": 0, "total_sessions": 0, "total_users": 0 if user_id else 0, "error": str(e)}
