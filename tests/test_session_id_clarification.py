"""
测试 Session ID 概念澄清的修正
验证聊天会话ID和用户登录会话ID的正确区分
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException, Request
from copilot.utils.auth import UserSession, verify_chat_session_access, get_sse_user_with_chat_permission
from copilot.core.session_manager import SessionInfo
from datetime import datetime


class TestSessionIdClarification:
    """测试Session ID概念澄清"""

    def test_user_session_properties(self):
        """测试UserSession类的属性正确性"""
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

    @pytest.mark.asyncio
    async def test_verify_chat_session_access_success(self):
        """测试聊天会话权限验证 - 成功案例"""
        # 创建测试用户会话
        user_session = UserSession(
            user_id="user123",
            username="testuser",
            login_session_id="login_session_456",
            session_data={},
            user_info={}
        )

        # 创建测试聊天会话信息
        chat_session_info = SessionInfo(
            session_id="chat_session_789",
            user_id="user123",  # 相同用户ID
            window_id="window1",
            created_at=datetime.now(),
            last_activity=datetime.now(),
            context={},
            thread_id="thread1"
        )

        # 模拟session_manager
        with patch('copilot.router.sse_router.session_manager') as mock_session_manager:
            mock_session_manager.get_session = AsyncMock(return_value=chat_session_info)
            
            # 执行权限验证
            result = await verify_chat_session_access("chat_session_789", user_session)
            
            # 验证结果
            assert result is True
            mock_session_manager.get_session.assert_called_once_with("chat_session_789")

    @pytest.mark.asyncio
    async def test_verify_chat_session_access_fail_wrong_user(self):
        """测试聊天会话权限验证 - 用户不匹配"""
        # 创建测试用户会话
        user_session = UserSession(
            user_id="user123",
            username="testuser",
            login_session_id="login_session_456",
            session_data={},
            user_info={}
        )

        # 创建测试聊天会话信息（不同用户）
        chat_session_info = SessionInfo(
            session_id="chat_session_789",
            user_id="user456",  # 不同用户ID
            window_id="window1",
            created_at=datetime.now(),
            last_activity=datetime.now(),
            context={},
            thread_id="thread1"
        )

        # 模拟session_manager
        with patch('copilot.router.sse_router.session_manager') as mock_session_manager:
            mock_session_manager.get_session = AsyncMock(return_value=chat_session_info)
            
            # 执行权限验证
            result = await verify_chat_session_access("chat_session_789", user_session)
            
            # 验证结果
            assert result is False

    @pytest.mark.asyncio
    async def test_verify_chat_session_access_fail_not_found(self):
        """测试聊天会话权限验证 - 会话不存在"""
        # 创建测试用户会话
        user_session = UserSession(
            user_id="user123",
            username="testuser",
            login_session_id="login_session_456",
            session_data={},
            user_info={}
        )

        # 模拟session_manager返回None
        with patch('copilot.router.sse_router.session_manager') as mock_session_manager:
            mock_session_manager.get_session = AsyncMock(return_value=None)
            
            # 执行权限验证
            result = await verify_chat_session_access("nonexistent_session", user_session)
            
            # 验证结果
            assert result is False

    @pytest.mark.asyncio
    async def test_get_sse_user_with_chat_permission_success(self):
        """测试SSE用户认证和权限验证 - 成功案例"""
        # 创建mock请求
        mock_request = Mock(spec=Request)
        
        # 创建测试用户会话
        user_session = UserSession(
            user_id="user123",
            username="testuser",
            login_session_id="login_session_456",
            session_data={},
            user_info={}
        )

        # 模拟get_authenticated_user和verify_chat_session_access
        with patch('copilot.router.sse_router.get_authenticated_user') as mock_auth, \
             patch('copilot.router.sse_router.verify_chat_session_access') as mock_verify:
            
            mock_auth.return_value = user_session
            mock_verify.return_value = True
            
            # 执行认证和权限验证
            result = await get_sse_user_with_chat_permission(
                "chat_session_789", mock_request, "test_token"
            )
            
            # 验证结果
            assert result == user_session
            mock_auth.assert_called_once_with(mock_request, None, "test_token")
            mock_verify.assert_called_once_with("chat_session_789", user_session)

    @pytest.mark.asyncio
    async def test_get_sse_user_with_chat_permission_fail_no_access(self):
        """测试SSE用户认证和权限验证 - 无权限访问"""
        # 创建mock请求
        mock_request = Mock(spec=Request)
        
        # 创建测试用户会话
        user_session = UserSession(
            user_id="user123",
            username="testuser",
            login_session_id="login_session_456",
            session_data={},
            user_info={}
        )

        # 模拟get_authenticated_user和verify_chat_session_access
        with patch('copilot.router.sse_router.get_authenticated_user') as mock_auth, \
             patch('copilot.router.sse_router.verify_chat_session_access') as mock_verify:
            
            mock_auth.return_value = user_session
            mock_verify.return_value = False  # 无权限访问
            
            # 执行认证和权限验证，应该抛出异常
            with pytest.raises(HTTPException) as exc_info:
                await get_sse_user_with_chat_permission(
                    "chat_session_789", mock_request, "test_token"
                )
            
            # 验证异常信息
            assert exc_info.value.status_code == 403
            assert "无权限访问该聊天会话" in str(exc_info.value.detail)

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 