import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.tools import BaseTool
from typing import Any, Type
from pydantic.v1 import BaseModel, Field

from copilot.core.agent import CoreAgent
from copilot.mcp_client.mcp_server_manager import mcp_server_manager

# 创建一个空的 Pydantic 模型作为 schema
class MockToolSchema(BaseModel):
    query: str = Field(description="The query to search for")


# 创建一个模拟的 LangChain 工具，继承自 BaseTool
class MockLangChainTool(BaseTool):
    name: str = "mock_tool"
    description: str = "A mock tool for testing"
    args_schema: Type[BaseModel] = MockToolSchema
    
    def _run(self, *args: Any, **kwargs: Any) -> Any:
        # 同步执行不是必需的
        raise NotImplementedError("This tool does not support sync execution")

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        # 异步执行的原始实现
        return "original arun result"

def create_mock_tool(name="mock_tool"):
    """创建一个真实的模拟工具实例"""
    tool = MockLangChainTool(name=name)
    # 我们仍然可以模拟 _arun 以便在测试中控制它
    tool._arun = AsyncMock(return_value="original arun result")
    return tool

@pytest.mark.asyncio
@patch('copilot.core.agent.CoreAgent._get_mcp_tools', new_callable=AsyncMock)
async def test_mcp_tool_wrapping_and_execution(mock_get_mcp_tools):
    """
    测试 CoreAgent 是否能正确包装 MCP 工具，并通过 mcp_server_manager.call_tool 执行。
    """
    # 1. 准备 Mock 数据
    mock_session_id = "test-session-12345"
    mock_tool_name = "test_mcp_tool"
    mock_tool_input = {"query": "hello"}

    # 模拟的 mcp_server_manager.call_tool
    mcp_server_manager.call_tool = AsyncMock()

    # 2. 设置 Mock 环境
    # 直接模拟 _get_mcp_tools 的返回结果
    unwrapped_tool = create_mock_tool(name=mock_tool_name)
    mock_get_mcp_tools.return_value = [unwrapped_tool]

    # 3. 场景一：成功的工具调用
    # --------------------------------------------------
    success_response = {
        "success": True,
        "result": {"processed_text": "Tool executed successfully"}
    }
    mcp_server_manager.call_tool.return_value = success_response

    # 初始化 Agent，这将调用我们模拟的 _get_mcp_tools 并自动包装工具
    agent = await CoreAgent.create_with_mcp_tools()
    
    # 从 agent 中找到我们包装后的工具
    agent_tool = next((t for t in agent.mcp_tools if t.name == mock_tool_name), None)

    assert agent_tool is not None, "包装后的工具未在 agent.mcp_tools 中找到"
    assert isinstance(agent_tool, BaseTool), "工具应该是 BaseTool 的一个实例"

    # 模拟 LangGraph 的调用方式，传入 config
    result = await agent_tool._arun(mock_tool_input, config={"configurable": {"session_id": mock_session_id}})

    # 断言：
    # a. mcp_server_manager.call_tool 被调用了一次
    mcp_server_manager.call_tool.assert_called_once()
    
    # b. 检查传递给 call_tool 的参数是否正确
    call_args = mcp_server_manager.call_tool.call_args
    assert call_args.kwargs['tool_name'] == mock_tool_name
    assert call_args.kwargs['parameters'] == mock_tool_input
    assert call_args.kwargs['session_id'] == mock_session_id
    assert call_args.kwargs['require_permission'] is True

    # c. 检查最终返回结果是否为处理后的文本
    assert result == success_response["result"]["processed_text"]

    # 4. 场景二：工具调用失败（例如，权限拒绝）
    # --------------------------------------------------
    # 重置 mock
    mcp_server_manager.call_tool.reset_mock()

    # 配置 call_tool 在此场景下返回失败结果
    failure_response = {
        "success": False,
        "error": "Permission Denied",
        "result": "User rejected the tool execution."
    }
    mcp_server_manager.call_tool.return_value = failure_response

    # 再次调用工具
    result_failed = await agent_tool._arun(mock_tool_input, config={"configurable": {"session_id": mock_session_id}})

    # 断言：
    # a. call_tool 被再次调用
    mcp_server_manager.call_tool.assert_called_once()

    # b. 返回给LLM的应该是一个清晰的错误信息
    expected_error_msg = f"Tool execution failed: {failure_response['error']}. Reason: {failure_response['result']}"
    assert result_failed == expected_error_msg

    # 清理
    mcp_server_manager.call_tool.reset_mock()

