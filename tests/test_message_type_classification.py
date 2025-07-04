"""
测试消息类型分类功能
"""
import pytest
from copilot.core.chat_stream_handler import ChatStreamHandler, ChatConfig
from copilot.model.chat_model import ThinkingMessage, AnswerMessage, SystemMessage, ErrorMessage


class MockMessage:
    """模拟消息对象"""
    def __init__(self, content, tool_calls=None, additional_kwargs=None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.additional_kwargs = additional_kwargs or {}
        self.role = "assistant"
        self.type = "ai"


class TestMessageTypeClassification:
    """测试消息类型分类"""
    
    def setup_method(self):
        """设置测试环境"""
        self.handler = ChatStreamHandler(None)  # graph不需要实际的图
    
    def test_thinking_message_classification(self):
        """测试思考消息分类"""
        # 测试中文思考关键词
        thinking_message = MockMessage("让我分析一下这个问题的核心要点")
        result = self.handler._classify_ai_message(thinking_message)
        assert result == "thinking"
        
        # 测试英文思考关键词
        thinking_message_en = MockMessage("Let me analyze this problem step by step")
        result = self.handler._classify_ai_message(thinking_message_en)
        assert result == "thinking"
    
    def test_response_message_classification(self):
        """测试回答消息分类"""
        # 测试回答关键词
        response_message = MockMessage("根据查询结果，我找到了相关信息")
        result = self.handler._classify_ai_message(response_message)
        assert result == "response"
        
        # 测试一般回答
        normal_message = MockMessage("这是一个正常的回答")
        result = self.handler._classify_ai_message(normal_message)
        assert result == "default"
    
    def test_tool_call_classification(self):
        """测试工具调用消息分类"""
        # 有工具调用的消息应该被归类为思考
        tool_message = MockMessage("我需要调用工具来帮助回答", tool_calls=[{"name": "test_tool"}])
        result = self.handler._classify_ai_message(tool_message)
        assert result == "thinking"
    
    def test_message_models(self):
        """测试消息模型"""
        # 测试思考消息模型
        thinking_msg = ThinkingMessage(
            session_id="test_session",
            content="🤔 **AI思考中**：让我分析这个问题"
        )
        assert thinking_msg.type == "thinking"
        
        # 测试回答消息模型
        answer_msg = AnswerMessage(
            session_id="test_session",
            content="根据分析，我的回答是..."
        )
        assert answer_msg.type == "answer"
        
        # 测试系统消息模型
        system_msg = SystemMessage(
            session_id="test_session",
            content="系统提示信息"
        )
        assert system_msg.type == "system"
        
        # 测试错误消息模型
        error_msg = ErrorMessage(
            session_id="test_session",
            content="发生了错误",
            error_code="ERR_001"
        )
        assert error_msg.type == "error"
    
    def test_config_keywords(self):
        """测试配置关键词"""
        # 确保关键词配置正确
        assert "让我" in ChatConfig.THINKING_KEYWORDS_ZH
        assert "我需要" in ChatConfig.THINKING_KEYWORDS_ZH
        assert "Let me" in ChatConfig.THINKING_KEYWORDS_EN
        assert "I need to" in ChatConfig.THINKING_KEYWORDS_EN
        assert "根据查询结果" in ChatConfig.RESPONSE_KEYWORDS_ZH
        assert "基于搜索结果" in ChatConfig.RESPONSE_KEYWORDS_ZH


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 