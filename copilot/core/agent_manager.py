"""
Agent管理器 - 为每个用户会话维护独立的Agent实例
解决多用户并发问题
"""

import asyncio
from datetime import datetime, UTC, timedelta
from typing import Dict, Optional, Any, List, Set
from copilot.core.agent import CoreAgent
from copilot.utils.logger import logger


class AgentManager:
    """Agent管理器 - 管理多用户的Agent实例"""
    
    def __init__(self):
        # session_id -> {"agent": CoreAgent, "created_at": datetime, "last_used": datetime}
        self.agents: Dict[str, Dict[str, Any]] = {}
        # session_id -> Set[server_id] 每个Agent使用的MCP服务器
        self.agent_mcp_servers: Dict[str, Set[str]] = {}
        self.cleanup_task = None
        self.max_agents = 100  # 最大Agent实例数
        self.agent_ttl = 3600  # Agent实例存活时间（秒）
        
    async def start(self):
        """启动Agent管理器"""
        self.cleanup_task = asyncio.create_task(self._cleanup_expired_agents())
        logger.info("AgentManager started")
        
    async def stop(self):
        """停止Agent管理器"""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
                
        # 清理所有Agent实例
        self.agents.clear()
        self.agent_mcp_servers.clear()
        logger.info("AgentManager stopped")
        
    async def get_agent(
        self, 
        session_id: str, 
        provider: Optional[str] = None, 
        model_name: Optional[str] = None,
        tools: List = None,
        **llm_kwargs
    ) -> CoreAgent:
        """
        获取指定会话的Agent实例
        
        Args:
            session_id: 会话ID
            provider: LLM提供商
            model_name: 模型名称
            tools: 传统工具列表
            **llm_kwargs: LLM参数
            
        Returns:
            CoreAgent: 该会话的专用Agent实例
        """
        current_time = datetime.now(UTC)
        
        # 检查是否已存在该会话的Agent
        if session_id in self.agents:
            agent_info = self.agents[session_id]
            agent_info["last_used"] = current_time
            
            # 检查Agent配置是否需要更新
            if self._should_update_agent(agent_info["agent"], provider, model_name, **llm_kwargs):
                logger.info(f"Agent configuration changed for session {session_id}, recreating...")
                await self._remove_agent(session_id)
            else:
                logger.debug(f"Reusing existing agent for session: {session_id}")
                return agent_info["agent"]
        
        # 检查是否需要清理以腾出空间
        if len(self.agents) >= self.max_agents:
            await self._cleanup_oldest_agents(10)  # 清理10个最旧的Agent
            
        # 创建新的Agent实例
        logger.info(f"Creating new agent for session: {session_id}")
        agent = await CoreAgent.create_with_mcp_tools(
            provider=provider,
            model_name=model_name,
            tools=tools,
            **llm_kwargs
        )
        
        # 存储Agent实例
        self.agents[session_id] = {
            "agent": agent,
            "created_at": current_time,
            "last_used": current_time,
            "provider": provider,
            "model_name": model_name,
            "llm_kwargs": llm_kwargs
        }
        
        logger.info(f"Created agent for session {session_id} with provider: {provider}, model: {model_name}")
        return agent
        
    async def remove_agent(self, session_id: str) -> bool:
        """
        移除指定会话的Agent实例
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 是否成功移除
        """
        return await self._remove_agent(session_id)
        
    async def _remove_agent(self, session_id: str) -> bool:
        """内部方法：移除Agent实例"""
        if session_id in self.agents:
            del self.agents[session_id]
            # 清理MCP服务器配置
            if session_id in self.agent_mcp_servers:
                del self.agent_mcp_servers[session_id]
            logger.info(f"Removed agent for session: {session_id}")
            return True
        return False
        
    def _should_update_agent(
        self, 
        agent: CoreAgent, 
        provider: Optional[str], 
        model_name: Optional[str],
        **llm_kwargs
    ) -> bool:
        """检查是否需要更新Agent配置"""
        if provider and agent.provider != provider:
            return True
        if model_name and agent.model_name != model_name:
            return True
        # 这里可以添加更多的配置比较逻辑
        return False
        
    async def _cleanup_expired_agents(self):
        """清理过期的Agent实例"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟清理一次
                
                current_time = datetime.now(UTC)
                expired_sessions = []
                
                for session_id, agent_info in self.agents.items():
                    # 检查是否过期
                    if (current_time - agent_info["last_used"]).total_seconds() > self.agent_ttl:
                        expired_sessions.append(session_id)
                        
                # 清理过期的Agent
                for session_id in expired_sessions:
                    await self._remove_agent(session_id)
                    
                if expired_sessions:
                    logger.info(f"Cleaned up {len(expired_sessions)} expired agents")
                    
            except Exception as e:
                logger.error(f"Error in agent cleanup task: {e}")
                
    async def _cleanup_oldest_agents(self, count: int):
        """清理最旧的Agent实例"""
        if len(self.agents) <= count:
            return
            
        # 按最后使用时间排序
        sorted_agents = sorted(
            self.agents.items(),
            key=lambda x: x[1]["last_used"]
        )
        
        # 清理最旧的几个
        for i in range(min(count, len(sorted_agents))):
            session_id = sorted_agents[i][0]
            await self._remove_agent(session_id)
            
        logger.info(f"Cleaned up {count} oldest agents to make room")
        
    def get_agent_stats(self) -> Dict[str, Any]:
        """获取Agent管理统计信息"""
        current_time = datetime.now(UTC)
        active_count = 0
        idle_count = 0
        
        for agent_info in self.agents.values():
            # 5分钟内使用过的算作活跃
            if (current_time - agent_info["last_used"]).total_seconds() < 300:
                active_count += 1
            else:
                idle_count += 1
                
        return {
            "total_agents": len(self.agents),
            "active_agents": active_count,
            "idle_agents": idle_count,
            "max_agents": self.max_agents,
            "agent_ttl": self.agent_ttl
        }
        
    def list_sessions(self) -> List[Dict[str, Any]]:
        """列出所有会话信息"""
        sessions = []
        for session_id, agent_info in self.agents.items():
            mcp_servers = list(self.agent_mcp_servers.get(session_id, set()))
            sessions.append({
                "session_id": session_id,
                "provider": agent_info.get("provider"),
                "model_name": agent_info.get("model_name"),
                "mcp_servers": mcp_servers,
                "mcp_server_count": len(mcp_servers),
                "created_at": agent_info["created_at"].isoformat(),
                "last_used": agent_info["last_used"].isoformat(),
                "age_seconds": (datetime.now(UTC) - agent_info["created_at"]).total_seconds()
            })
            
        return sorted(sessions, key=lambda x: x["last_used"], reverse=True)

    async def set_agent_mcp_servers(self, session_id: str, server_ids: Set[str]) -> bool:
        """
        为指定Agent设置MCP服务器配置
        
        Args:
            session_id: 会话ID
            server_ids: MCP服务器ID集合
            
        Returns:
            bool: 是否设置成功
        """
        try:
            if session_id not in self.agents:
                logger.warning(f"Agent not found for session: {session_id}")
                return False
                
            # 更新MCP服务器配置
            self.agent_mcp_servers[session_id] = server_ids.copy()
            
            # 更新Agent的MCP工具
            await self._update_agent_mcp_tools(session_id, server_ids)
            
            logger.info(f"Updated MCP servers for session {session_id}: {server_ids}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set MCP servers for session {session_id}: {e}")
            return False
    
    async def add_agent_mcp_server(self, session_id: str, server_id: str) -> bool:
        """
        为指定Agent添加MCP服务器
        
        Args:
            session_id: 会话ID  
            server_id: MCP服务器ID
            
        Returns:
            bool: 是否添加成功
        """
        try:
            if session_id not in self.agents:
                logger.warning(f"Agent not found for session: {session_id}")
                return False
                
            if session_id not in self.agent_mcp_servers:
                self.agent_mcp_servers[session_id] = set()
                
            self.agent_mcp_servers[session_id].add(server_id)
            
            # 更新Agent的MCP工具
            await self._update_agent_mcp_tools(session_id, self.agent_mcp_servers[session_id])
            
            logger.info(f"Added MCP server {server_id} to session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add MCP server {server_id} to session {session_id}: {e}")
            return False
    
    async def remove_agent_mcp_server(self, session_id: str, server_id: str) -> bool:
        """
        从指定Agent移除MCP服务器
        
        Args:
            session_id: 会话ID
            server_id: MCP服务器ID
            
        Returns:
            bool: 是否移除成功
        """
        try:
            if session_id not in self.agents:
                logger.warning(f"Agent not found for session: {session_id}")
                return False
                
            if session_id in self.agent_mcp_servers:
                self.agent_mcp_servers[session_id].discard(server_id)
                
                # 更新Agent的MCP工具
                await self._update_agent_mcp_tools(session_id, self.agent_mcp_servers[session_id])
                
                logger.info(f"Removed MCP server {server_id} from session {session_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to remove MCP server {server_id} from session {session_id}: {e}")
            return False
    
    async def reload_agents_for_server(self, server_id: str) -> List[str]:
        """
        重新加载使用指定MCP服务器的所有Agent
        
        Args:
            server_id: MCP服务器ID
            
        Returns:
            List[str]: 已更新的会话ID列表
        """
        updated_sessions = []
        
        try:
            for session_id, server_ids in self.agent_mcp_servers.items():
                if server_id in server_ids:
                    success = await self._update_agent_mcp_tools(session_id, server_ids)
                    if success:
                        updated_sessions.append(session_id)
                        
            logger.info(f"Reloaded {len(updated_sessions)} agents for MCP server: {server_id}")
            return updated_sessions
            
        except Exception as e:
            logger.error(f"Failed to reload agents for server {server_id}: {e}")
            return updated_sessions
    
    async def _update_agent_mcp_tools(self, session_id: str, server_ids: Set[str]) -> bool:
        """
        更新Agent的MCP工具
        
        Args:
            session_id: 会话ID
            server_ids: MCP服务器ID集合
            
        Returns:
            bool: 是否更新成功
        """
        try:
            if session_id not in self.agents:
                return False
                
            agent = self.agents[session_id]["agent"]
            
            # 从MCP服务器管理器获取指定服务器的工具
            from copilot.mcp_client.mcp_server_manager import mcp_server_manager
            mcp_tools = await self._get_mcp_tools_for_servers(server_ids)
            
            # 更新Agent的MCP工具
            await agent.update_mcp_tools(mcp_tools)
            
            logger.info(f"Updated MCP tools for session {session_id} with {len(mcp_tools)} tools from servers: {server_ids}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update MCP tools for session {session_id}: {e}")
            return False
    
    async def _get_mcp_tools_for_servers(self, server_ids: Set[str]) -> List:
        """
        从指定的MCP服务器获取工具
        
        Args:
            server_ids: MCP服务器ID集合
            
        Returns:
            List: 包装后的MCP工具列表
        """
        try:
            if not server_ids:
                return []
                
            # 使用MCPToolWrapper获取指定服务器的工具
            from copilot.core.mcp_tool_wrapper import MCPToolWrapper
            mcp_tools = await MCPToolWrapper.get_mcp_tools_for_servers(list(server_ids))
            
            logger.info(f"Retrieved {len(mcp_tools)} MCP tools from servers: {server_ids}")
            return mcp_tools
            
        except Exception as e:
            logger.error(f"Failed to get MCP tools for servers {server_ids}: {e}")
            return []
    
    def get_agent_mcp_servers(self, session_id: str) -> Set[str]:
        """
        获取指定Agent使用的MCP服务器
        
        Args:
            session_id: 会话ID
            
        Returns:
            Set[str]: MCP服务器ID集合
        """
        return self.agent_mcp_servers.get(session_id, set()).copy()
    
    def get_sessions_using_server(self, server_id: str) -> List[str]:
        """
        获取使用指定MCP服务器的所有会话
        
        Args:
            server_id: MCP服务器ID
            
        Returns:
            List[str]: 会话ID列表
        """
        sessions = []
        for session_id, server_ids in self.agent_mcp_servers.items():
            if server_id in server_ids:
                sessions.append(session_id)
        return sessions


# 全局Agent管理器实例
agent_manager = AgentManager() 