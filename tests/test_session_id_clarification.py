"""
Session ID 概念澄清测试
验证用户登录会话ID和聊天会话ID的正确分离
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from copilot.utils.auth import UserSession


class TestSessionIdClarification:
    """Session ID概念澄清测试类"""

    def test_user_session_properties(self):
        """测试UserSession类的属性和向后兼容性"""
        # 创建测试用户会话
        user_session = UserSession(
            user_id="user123",
            username="testuser",
            login_session_id="login_session_456",
            session_data={"session_id": "login_session_456"},
            user_info={"_id": "user123", "username": "testuser"}
        )

        # 验证属性
        assert user_session.user_id == "user123"
        assert user_session.username == "testuser"
        assert user_session.login_session_id == "login_session_456"
        
        # 验证向后兼容属性
        assert user_session.session_id == "login_session_456"
        
        # 验证to_dict方法
        user_dict = user_session.to_dict()
        assert user_dict["username"] == "testuser"

    def test_concept_separation(self):
        """测试概念分离的正确性"""
        # 用户登录会话ID和聊天会话ID是完全不同的概念
        login_session_id = "login_session_abc123"
        chat_session_id = "chat_session_xyz789"
        
        # 创建用户会话（包含登录会话ID）
        user_session = UserSession(
            user_id="user123",
            username="testuser",
            login_session_id=login_session_id,
            session_data={"session_id": login_session_id},
            user_info={}
        )
        
        # 验证两个ID的独立性
        assert user_session.login_session_id == login_session_id
        assert user_session.session_id == login_session_id  # 向后兼容
        assert user_session.login_session_id != chat_session_id  # 不同概念，不应该相等
        
        # 在实际使用中，聊天会话ID应该通过路径参数传递
        # 而用户认证通过token进行，返回包含登录会话ID的UserSession对象

    def test_user_session_to_dict(self):
        """测试UserSession的字典转换"""
        user_session = UserSession(
            user_id="user123",
            username="testuser",
            login_session_id="login_session_456",
            session_data={"role": "admin"},
            user_info={"email": "test@example.com"}
        )
        
        result = user_session.to_dict()
        
        # 验证字典包含必要的字段
        assert "username" in result
        assert "user_id" in result
        assert "login_session_id" in result
        assert result["username"] == "testuser"
        assert result["user_id"] == "user123"

    def test_user_session_different_instances(self):
        """测试不同用户会话实例的独立性"""
        user1 = UserSession(
            user_id="user1",
            username="user1",
            login_session_id="login1",
            session_data={},
            user_info={}
        )
        
        user2 = UserSession(
            user_id="user2", 
            username="user2",
            login_session_id="login2",
            session_data={},
            user_info={}
        )
        
        # 验证不同用户会话的独立性
        assert user1.user_id != user2.user_id
        assert user1.login_session_id != user2.login_session_id
        assert user1.session_id != user2.session_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 