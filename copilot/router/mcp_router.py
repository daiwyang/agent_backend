"""
MCP工具权限管理API路由
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from copilot.mcp.mcp_server_manager import mcp_server_manager
from copilot.mcp.tool_permission_manager import tool_permission_manager
from copilot.utils.auth import get_current_user_from_state

router = APIRouter(prefix="/mcp")


class ToolPermissionRequest(BaseModel):
    """工具权限请求模型"""

    request_id: str
    approved: bool


class MCPServerConfig(BaseModel):
    """MCP服务器配置模型 - 符合 FastMCP 标准"""

    id: str
    name: str

    # 1. HTTP/SSE 服务器
    url: Optional[str] = None
    auth: Optional[str] = None  # Bearer Token 或 "oauth"
    headers: Dict[str, str] = {}  # 自定义头部（如 X-API-Key）

    # 2. 本地 Python/Node.js 脚本（自动传输推理）
    script: Optional[str] = None  # .py 或 .js 文件路径

    # 3. Stdio 服务器
    command: Optional[str] = None
    args: List[str] = []
    env: Dict[str, str] = {}
    cwd: Optional[str] = None

    # 4. 完整的 MCP 配置
    transport: Optional[str] = None  # stdio|http|sse
    timeout: Optional[float] = 30.0

    # 5. 工具风险级别配置（可选）
    tool_risks: Dict[str, str] = {}  # {"tool_name": "low|medium|high"}


@router.get("/tools")
async def get_available_tools(current_user: dict = Depends(get_current_user_from_state)):
    """获取所有可用的MCP工具"""
    try:
        tools = mcp_server_manager.get_available_tools()
        return {"success": True, "tools": tools}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取工具列表失败: {str(e)}")


@router.get("/servers")
async def get_connected_servers(current_user: dict = Depends(get_current_user_from_state)):
    """获取已连接的MCP服务器"""
    try:
        servers = mcp_server_manager.get_servers_info()
        return {"success": True, "servers": servers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取服务器列表失败: {str(e)}")


@router.post("/servers/connect")
async def connect_server(server_config: MCPServerConfig, current_user: dict = Depends(get_current_user_from_state)):
    """连接到MCP服务器"""
    try:
        success = await mcp_server_manager.register_server(server_config.model_dump())
        if success:
            return {"success": True, "message": f"成功连接到服务器: {server_config.name}"}
        else:
            raise HTTPException(status_code=400, detail="连接服务器失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"连接服务器失败: {str(e)}")


@router.post("/servers/{server_id}/disconnect")
async def disconnect_server(server_id: str, current_user: dict = Depends(get_current_user_from_state)):
    """断开MCP服务器连接"""
    try:
        success = await mcp_server_manager.unregister_server(server_id)
        if success:
            return {"success": True, "message": f"成功断开服务器连接: {server_id}"}
        else:
            raise HTTPException(status_code=400, detail="断开服务器连接失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"断开服务器连接失败: {str(e)}")


@router.get("/permissions/{session_id}")
async def get_pending_permissions(session_id: str, current_user: dict = Depends(get_current_user_from_state)):
    """获取指定会话的待处理权限请求"""
    try:
        # 验证用户是否有权限访问该会话
        # 这里应该根据实际的权限体系进行验证

        requests = await tool_permission_manager.get_pending_requests(session_id)
        return {"success": True, "pending_requests": requests}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取权限请求失败: {str(e)}")


@router.post("/permissions/{session_id}/respond")
async def respond_to_permission(session_id: str, request: ToolPermissionRequest, current_user: dict = Depends(get_current_user_from_state)):
    """响应工具权限请求"""
    try:
        # 验证用户是否有权限操作该会话
        # 这里应该根据实际的权限体系进行验证

        success = await tool_permission_manager.handle_user_response(request_id=request.request_id, approved=request.approved, session_id=session_id)

        if success:
            action = "同意" if request.approved else "拒绝"
            return {"success": True, "message": f"已{action}工具执行请求"}
        else:
            raise HTTPException(status_code=400, detail="处理权限响应失败")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理权限响应失败: {str(e)}")


@router.post("/tools/{tool_name}/execute")
async def execute_tool_directly(
    tool_name: str, parameters: dict, session_id: str, require_permission: bool = True, current_user: dict = Depends(get_current_user_from_state)
):
    """直接执行MCP工具（用于测试）"""
    try:
        result = await mcp_server_manager.call_tool(
            tool_name=tool_name, parameters=parameters, session_id=session_id, require_permission=require_permission
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行工具失败: {str(e)}")
