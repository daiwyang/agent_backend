"""
MCP路由器 - 提供MCP服务器和Agent级别工具管理的API
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from copilot.mcp_client.mcp_server_manager import mcp_server_manager
from copilot.utils.auth import get_current_user_from_state
from copilot.utils.logger import logger

router = APIRouter(prefix="/mcp", tags=["MCP"])


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


class AgentMCPConfig(BaseModel):
    """Agent MCP服务器配置模型"""

    session_id: str
    server_ids: List[str]


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


@router.post("/refresh")
async def refresh_mcp_tools(current_user: dict = Depends(get_current_user_from_state)):
    """手动刷新聊天服务中的 MCP 工具"""
    try:
        # 直接调用ChatService的reload_agent方法
        from copilot.router.chat_router import get_chat_service
        chat_service = await get_chat_service()
        success = await chat_service.reload_agent()
        
        if success:
            return {"success": True, "message": "MCP 工具已成功刷新"}
        else:
            raise HTTPException(status_code=500, detail="刷新 MCP 工具失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"刷新 MCP 工具失败: {str(e)}")


@router.post("/servers/connect")
async def connect_server(server_config: MCPServerConfig, current_user: dict = Depends(get_current_user_from_state)):
    """连接到MCP服务器"""
    try:
        success = await mcp_server_manager.register_server(server_config.model_dump())
        if success:
            # MCP服务器连接成功后，通知相关Agent更新工具
            try:
                from copilot.core.agent_manager import agent_manager
                
                # 目前为所有现有Agent添加新服务器（可选择性配置）
                # 实际应用中可以通过用户设置来决定哪些Agent使用哪些服务器
                updated_sessions = []
                for session_id in agent_manager.agents.keys():
                    success = await agent_manager.add_agent_mcp_server(session_id, server_config.id)
                    if success:
                        updated_sessions.append(session_id)
                
                logger.info(f"Successfully updated {len(updated_sessions)} agents after connecting server: {server_config.name}")
                
                return {
                    "success": True, 
                    "message": f"成功连接到服务器: {server_config.name}",
                    "updated_sessions": len(updated_sessions)
                }
            except Exception as reload_error:
                logger.error(f"Failed to update agents after server connection: {str(reload_error)}")
                # 连接成功，但Agent更新失败
                return {
                    "success": True,
                    "message": f"服务器连接成功: {server_config.name}，但部分Agent更新失败",
                    "warning": str(reload_error)
                }
        else:
            raise HTTPException(status_code=400, detail="连接服务器失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"连接服务器失败: {str(e)}")


@router.post("/servers/{server_id}/disconnect")
async def disconnect_server(server_id: str, current_user: dict = Depends(get_current_user_from_state)):
    """断开MCP服务器连接"""
    try:
        # 先获取使用此服务器的会话列表
        from copilot.core.agent_manager import agent_manager
        affected_sessions = agent_manager.get_sessions_using_server(server_id)
        
        success = await mcp_server_manager.unregister_server(server_id)
        if success:
            # MCP服务器断开成功后，从相关Agent中移除该服务器的工具
            try:
                updated_sessions = []
                for session_id in affected_sessions:
                    success = await agent_manager.remove_agent_mcp_server(session_id, server_id)
                    if success:
                        updated_sessions.append(session_id)
                        
                logger.info(f"Successfully updated {len(updated_sessions)} agents after disconnecting server: {server_id}")
                
                return {
                    "success": True, 
                    "message": f"成功断开服务器连接: {server_id}",
                    "affected_sessions": len(affected_sessions),
                    "updated_sessions": len(updated_sessions)
                }
            except Exception as reload_error:
                logger.error(f"Failed to update agents after server disconnection: {str(reload_error)}")
                # 断开成功，但Agent更新失败
                return {
                    "success": True,
                    "message": f"服务器断开成功: {server_id}，但部分Agent更新失败",
                    "affected_sessions": len(affected_sessions),
                    "warning": str(reload_error)
                }
        else:
            raise HTTPException(status_code=400, detail="断开服务器连接失败")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"断开服务器连接失败: {str(e)}")


@router.post("/tools/{tool_name}/execute")
async def execute_tool_directly(
    tool_name: str, parameters: dict, session_id: str, require_permission: bool = True, current_user: dict = Depends(get_current_user_from_state)
):
    """
    直接执行MCP工具（用于测试和调试）
    注意：生产环境建议通过Agent执行工具以获得完整的权限管理和状态跟踪
    """
    try:
        result = await mcp_server_manager.call_tool(
            tool_name=tool_name, parameters=parameters, session_id=session_id, require_permission=require_permission
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行工具失败: {str(e)}")


# === Agent级别MCP工具管理API ===

@router.get("/agents/{session_id}/servers")
async def get_agent_mcp_servers(session_id: str, current_user: dict = Depends(get_current_user_from_state)):
    """获取指定Agent使用的MCP服务器"""
    try:
        from copilot.core.agent_manager import agent_manager
        
        server_ids = agent_manager.get_agent_mcp_servers(session_id)
        
        # 获取服务器详细信息
        all_servers = mcp_server_manager.get_servers_info()
        agent_servers = [
            server for server in all_servers 
            if server["id"] in server_ids
        ]
        
        return {
            "success": True,
            "session_id": session_id,
            "server_ids": list(server_ids),
            "servers": agent_servers,
            "server_count": len(server_ids)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取Agent MCP服务器失败: {str(e)}")


@router.post("/agents/{session_id}/servers")
async def set_agent_mcp_servers(session_id: str, config: AgentMCPConfig, current_user: dict = Depends(get_current_user_from_state)):
    """设置指定Agent的MCP服务器配置"""
    try:
        from copilot.core.agent_manager import agent_manager
        
        # 验证服务器ID是否有效
        all_servers = mcp_server_manager.get_servers_info()
        valid_server_ids = {server["id"] for server in all_servers}
        
        invalid_ids = set(config.server_ids) - valid_server_ids
        if invalid_ids:
            raise HTTPException(
                status_code=400, 
                detail=f"无效的服务器ID: {list(invalid_ids)}"
            )
        
        # 设置Agent的MCP服务器
        success = await agent_manager.set_agent_mcp_servers(session_id, set(config.server_ids))
        
        if success:
            return {
                "success": True,
                "message": f"成功为Agent {session_id} 设置MCP服务器",
                "session_id": session_id,
                "server_ids": config.server_ids,
                "server_count": len(config.server_ids)
            }
        else:
            raise HTTPException(status_code=400, detail="设置Agent MCP服务器失败")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置Agent MCP服务器失败: {str(e)}")


@router.post("/agents/{session_id}/servers/{server_id}/add")
async def add_agent_mcp_server(session_id: str, server_id: str, current_user: dict = Depends(get_current_user_from_state)):
    """为指定Agent添加MCP服务器"""
    try:
        from copilot.core.agent_manager import agent_manager
        
        # 验证服务器是否存在
        all_servers = mcp_server_manager.get_servers_info()
        if not any(server["id"] == server_id for server in all_servers):
            raise HTTPException(status_code=404, detail=f"服务器不存在: {server_id}")
        
        success = await agent_manager.add_agent_mcp_server(session_id, server_id)
        
        if success:
            return {
                "success": True,
                "message": f"成功为Agent {session_id} 添加MCP服务器 {server_id}",
                "session_id": session_id,
                "server_id": server_id
            }
        else:
            raise HTTPException(status_code=400, detail="添加Agent MCP服务器失败")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加Agent MCP服务器失败: {str(e)}")


@router.post("/agents/{session_id}/servers/{server_id}/remove") 
async def remove_agent_mcp_server(session_id: str, server_id: str, current_user: dict = Depends(get_current_user_from_state)):
    """从指定Agent移除MCP服务器"""
    try:
        from copilot.core.agent_manager import agent_manager
        
        success = await agent_manager.remove_agent_mcp_server(session_id, server_id)
        
        if success:
            return {
                "success": True,
                "message": f"成功从Agent {session_id} 移除MCP服务器 {server_id}",
                "session_id": session_id,
                "server_id": server_id
            }
        else:
            return {
                "success": True,
                "message": f"Agent {session_id} 未使用服务器 {server_id}，无需移除",
                "session_id": session_id,
                "server_id": server_id
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"移除Agent MCP服务器失败: {str(e)}")


@router.get("/servers/{server_id}/agents")
async def get_server_agents(server_id: str, current_user: dict = Depends(get_current_user_from_state)):
    """获取使用指定MCP服务器的所有Agent"""
    try:
        from copilot.core.agent_manager import agent_manager
        
        # 验证服务器是否存在
        all_servers = mcp_server_manager.get_servers_info()
        server_info = next((s for s in all_servers if s["id"] == server_id), None)
        if not server_info:
            raise HTTPException(status_code=404, detail=f"服务器不存在: {server_id}")
        
        sessions = agent_manager.get_sessions_using_server(server_id)
        
        # 获取会话详细信息
        session_details = []
        for session_id in sessions:
            if session_id in agent_manager.agents:
                agent_info = agent_manager.agents[session_id]
                session_details.append({
                    "session_id": session_id,
                    "provider": agent_info.get("provider"),
                    "model_name": agent_info.get("model_name"),
                    "created_at": agent_info["created_at"].isoformat(),
                    "last_used": agent_info["last_used"].isoformat()
                })
        
        return {
            "success": True,
            "server_id": server_id,
            "server_name": server_info["name"],
            "sessions": sessions,
            "session_count": len(sessions),
            "session_details": session_details
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取服务器使用Agent失败: {str(e)}")


@router.post("/servers/{server_id}/reload")
async def reload_server_agents(server_id: str, current_user: dict = Depends(get_current_user_from_state)):
    """重新加载使用指定MCP服务器的所有Agent"""
    try:
        from copilot.core.agent_manager import agent_manager
        
        # 验证服务器是否存在
        all_servers = mcp_server_manager.get_servers_info()
        if not any(server["id"] == server_id for server in all_servers):
            raise HTTPException(status_code=404, detail=f"服务器不存在: {server_id}")
        
        updated_sessions = await agent_manager.reload_agents_for_server(server_id)
        
        return {
            "success": True,
            "message": f"成功重新加载使用服务器 {server_id} 的Agent",
            "server_id": server_id,
            "updated_sessions": updated_sessions,
            "updated_count": len(updated_sessions)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重新加载服务器Agent失败: {str(e)}")
