"""
Agent管理路由 - 提供Agent状态监控和管理功能
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional

from copilot.core.agent_manager import agent_manager
from copilot.core.agent_state_manager import agent_state_manager
from copilot.utils.logger import logger

router = APIRouter()


@router.get("/agent-stats")
async def get_agent_stats() -> Dict[str, Any]:
    """获取Agent管理器统计信息"""
    try:
        stats = agent_manager.get_agent_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        logger.error(f"Failed to get agent stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent statistics")


@router.get("/agent-sessions")
async def list_agent_sessions() -> Dict[str, Any]:
    """列出所有Agent会话"""
    try:
        sessions = agent_manager.list_sessions()
        return {"success": True, "data": {"sessions": sessions, "total_count": len(sessions)}}
    except Exception as e:
        logger.error(f"Failed to list agent sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to list agent sessions")


@router.delete("/agent-sessions/{session_id}")
async def remove_agent_session(session_id: str) -> Dict[str, Any]:
    """移除指定的Agent会话"""
    try:
        success = await agent_manager.remove_agent(session_id)
        return {"success": success, "message": f"Agent session {session_id} {'removed' if success else 'not found'}"}
    except Exception as e:
        logger.error(f"Failed to remove agent session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove agent session")


@router.get("/agent-execution-states")
async def get_agent_execution_states() -> Dict[str, Any]:
    """获取所有Agent执行状态"""
    try:
        states = []
        for session_id in agent_state_manager.active_contexts.keys():
            status = agent_state_manager.get_session_status(session_id)
            if status:
                states.append(status)

        return {"success": True, "data": {"execution_states": states, "total_count": len(states)}}
    except Exception as e:
        logger.error(f"Failed to get agent execution states: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent execution states")


@router.get("/agent-execution-states/{session_id}")
async def get_agent_execution_state(session_id: str) -> Dict[str, Any]:
    """获取指定会话的Agent执行状态"""
    try:
        status = agent_state_manager.get_session_status(session_id)
        if status:
            return {"success": True, "data": status}
        else:
            raise HTTPException(status_code=404, detail="Agent execution state not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get agent execution state for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent execution state")


@router.post("/agent-reload")
async def reload_agents(session_id: Optional[str] = None) -> Dict[str, Any]:
    """重新加载Agent实例"""
    try:
        # 需要导入聊天服务来调用reload方法
        from copilot.router.chat_router import get_chat_service

        chat_service = await get_chat_service()
        success = await chat_service.reload_agent(session_id)

        return {
            "success": success,
            "message": f"Agent {'for session ' + session_id if session_id else 'instances'} {'reloaded' if success else 'reload failed'}",
        }
    except Exception as e:
        logger.error(f"Failed to reload agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload agents")


@router.get("/agent-health")
async def check_agent_health() -> Dict[str, Any]:
    """检查Agent管理器健康状态"""
    try:
        agent_stats = agent_manager.get_agent_stats()

        # 简单的健康检查逻辑
        health_status = "healthy"
        issues = []

        # 检查是否有过多的Agent实例
        if agent_stats["total_agents"] > agent_manager.max_agents * 0.9:
            health_status = "warning"
            issues.append("High agent instance count")

        # 检查是否有太多空闲实例
        if agent_stats["idle_agents"] > agent_stats["total_agents"] * 0.8:
            health_status = "warning"
            issues.append("High idle agent ratio")

        return {
            "success": True,
            "data": {
                "status": health_status,
                "issues": issues,
                "stats": agent_stats,
                "timestamp": agent_manager.agents and min(info["last_used"].isoformat() for info in agent_manager.agents.values()) or None,
            },
        }
    except Exception as e:
        logger.error(f"Failed to check agent health: {e}")
        raise HTTPException(status_code=500, detail="Failed to check agent health")


@router.post("/agent-cleanup")
async def trigger_agent_cleanup() -> Dict[str, Any]:
    """手动触发Agent清理"""
    try:
        stats_before = agent_manager.get_agent_stats()

        # 清理最旧的10个Agent
        await agent_manager._cleanup_oldest_agents(10)

        stats_after = agent_manager.get_agent_stats()

        cleaned_count = stats_before["total_agents"] - stats_after["total_agents"]

        return {
            "success": True,
            "data": {"cleaned_agents": cleaned_count, "before": stats_before, "after": stats_after},
            "message": f"Cleaned up {cleaned_count} agent instances",
        }
    except Exception as e:
        logger.error(f"Failed to cleanup agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup agents")
