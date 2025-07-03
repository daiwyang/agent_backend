"""
MCP工具包装器 - 处理MCP工具的包装、权限检查和执行
"""

import traceback
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from langchain_mcp_adapters.client import MultiServerMCPClient

from copilot.core.tool_result_processor import ToolResultProcessor
from copilot.core.stream_notifier import StreamNotifier
from copilot.mcp_client.mcp_server_manager import mcp_server_manager
from copilot.utils.logger import logger


class MCPToolWrapper:
    """MCP工具包装器 - 负责MCP工具的加载、包装和执行"""
    
    @classmethod
    async def get_mcp_tools(cls) -> List:
        """获取所有可用的MCP工具"""
        try:
            # 获取所有注册的MCP服务器配置
            servers_info = mcp_server_manager.get_servers_info()

            if not servers_info:
                logger.info("No MCP servers registered")
                return []

            # 构建MultiServerMCPClient配置
            mcp_config = {}
            for server in servers_info:
                server_config = mcp_server_manager.servers[server["id"]]["config"]

                # 转换为langchain-mcp-adapters格式
                if "command" in server_config and server_config["command"]:
                    # Stdio 服务器配置
                    mcp_config[server["id"]] = {
                        "command": server_config["command"], 
                        "args": server_config.get("args", []), 
                        "transport": "stdio"
                    }
                elif "url" in server_config and server_config["url"]:
                    # HTTP/SSE 服务器配置
                    mcp_config[server["id"]] = {
                        "url": server_config["url"], 
                        "transport": "streamable_http"
                    }
                else:
                    logger.warning(f"Invalid server config for {server['id']}: missing valid command or url")

            if not mcp_config:
                logger.info("No valid MCP server configurations found")
                return []

            # 使用MultiServerMCPClient获取工具
            client = MultiServerMCPClient(mcp_config)
            try:
                # 异步获取所有MCP工具
                all_tools = await client.get_tools()

                logger.info(f"Successfully loaded {len(all_tools)} MCP tools via langchain-mcp-adapters")

                # 包装所有MCP工具以集成权限检查和自定义逻辑
                wrapped_tools = [cls._wrap_tool(tool) for tool in all_tools]
                logger.info(f"Successfully wrapped {len(wrapped_tools)} MCP tools")

                return wrapped_tools

            except ExceptionGroup as eg:
                # 特别处理TaskGroup的异常
                logger.error(f"Error group calling client.get_tools(): {eg}")
                for i, e in enumerate(eg.exceptions):
                    logger.error(f"  Sub-exception {i+1}: {e}")
                    logger.debug(traceback.format_exc())
                return []
            except Exception as e:
                logger.error(f"Error calling client.get_tools(): {e}")
                # 打印详细的traceback以诊断TaskGroup问题
                logger.debug(traceback.format_exc())
                # 即使出错也返回空列表，避免整个agent崩溃
                return []

        except Exception as e:
            logger.error(f"Failed to load MCP tools via langchain-mcp-adapters: {e}")
            logger.debug(traceback.format_exc())
            return []

    @classmethod
    async def get_mcp_tools_for_servers(cls, server_ids: List[str]) -> List:
        """
        从指定MCP服务器获取工具

        Args:
            server_ids: MCP服务器ID列表

        Returns:
            List: 包装后的MCP工具列表
        """
        try:
            if not server_ids:
                return []

            # 获取所有服务器信息
            servers_info = mcp_server_manager.get_servers_info()

            # 过滤出指定的服务器
            target_servers = [server for server in servers_info if server["id"] in server_ids]

            if not target_servers:
                logger.info(f"No matching MCP servers found for IDs: {server_ids}")
                return []

            # 构建MultiServerMCPClient配置
            mcp_config = {}
            for server in target_servers:
                server_config = mcp_server_manager.servers[server["id"]]["config"]

                # 转换为langchain-mcp-adapters格式
                if "command" in server_config and server_config["command"]:
                    # Stdio 服务器配置
                    mcp_config[server["id"]] = {
                        "command": server_config["command"], 
                        "args": server_config.get("args", []), 
                        "transport": "stdio"
                    }
                elif "url" in server_config and server_config["url"]:
                    # HTTP/SSE 服务器配置
                    mcp_config[server["id"]] = {
                        "url": server_config["url"], 
                        "transport": "streamable_http"
                    }
                else:
                    logger.warning(f"Invalid server config for {server['id']}: missing valid command or url")

            if not mcp_config:
                logger.info("No valid MCP server configurations found for specified servers")
                return []

            # 使用MultiServerMCPClient获取工具
            client = MultiServerMCPClient(mcp_config)

            try:
                # 异步获取所有MCP工具
                all_tools = await client.get_tools()

                logger.info(f"Successfully loaded {len(all_tools)} MCP tools from servers: {server_ids}")

                # 包装所有MCP工具以集成权限检查和自定义逻辑
                wrapped_tools = [cls._wrap_tool(tool) for tool in all_tools]
                logger.info(f"Successfully wrapped {len(wrapped_tools)} MCP tools from specified servers")

                return wrapped_tools

            except Exception as e:
                logger.error(f"Error calling client.get_tools() for servers {server_ids}: {e}")
                logger.debug(traceback.format_exc())
                return []

        except Exception as e:
            logger.error(f"Failed to load MCP tools from servers {server_ids}: {e}")
            logger.debug(traceback.format_exc())
            return []

    @staticmethod
    def _wrap_tool(tool: Any) -> Any:
        """
        包装从 langchain-mcp-adapters 获取的工具，集成Agent状态管理器
        实现非阻塞的权限检查机制和结果推送
        """
        # 保存原始的执行函数
        original_arun = tool._arun

        async def custom_arun(*args, **kwargs) -> Any:
            """
            自定义的工具执行逻辑 - 集成Agent状态管理器和WebSocket推送
            """
            session_id = None

            # 从kwargs中获取session_id - 修正提取逻辑
            config = kwargs.get("config", {})
            if config and isinstance(config, dict) and "configurable" in config:
                session_id = config["configurable"].get("session_id")
            
            # 如果从config中无法获取session_id，尝试从agent_state_manager获取当前活跃的会话
            if not session_id:
                try:
                    from copilot.core.agent_state_manager import agent_state_manager
                    # 获取所有活跃上下文，找到状态为RUNNING的会话
                    for sid, context in agent_state_manager.active_contexts.items():
                        if context.state.value == "running":
                            session_id = sid
                            logger.info(f"Retrieved session_id from agent_state_manager: {session_id}")
                            break
                except Exception as e:
                    logger.debug(f"Failed to get session_id from agent_state_manager: {e}")

            # 确保config参数存在，并注入session_id
            if "config" not in kwargs:
                kwargs["config"] = {}
            
            # 如果config中没有session_id，但我们找到了session_id，就注入进去
            if session_id and "configurable" not in kwargs["config"]:
                kwargs["config"]["configurable"] = {"session_id": session_id}
            elif session_id and "session_id" not in kwargs["config"].get("configurable", {}):
                kwargs["config"].setdefault("configurable", {})["session_id"] = session_id

            logger.info(f"Executing wrapped tool: {tool.name} with session_id: {session_id}")
            logger.debug(f"Tool {tool.name} called with args: {args}, kwargs keys: {list(kwargs.keys())}")
            logger.debug(f"Tool {tool.name} config content: {config}")
            
            # 调试：输出完整的kwargs结构以了解传递过程
            if not session_id:
                logger.warning(f"Session ID is None for tool {tool.name}")
                logger.debug(f"Full kwargs structure: {kwargs}")
                for key, value in kwargs.items():
                    logger.debug(f"  {key}: {type(value)} = {value}")
                    if key == "config" and isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            logger.debug(f"    config.{sub_key}: {type(sub_value)} = {sub_value}")

            # 准备工具执行信息
            tool_execution_info = {
                "tool_name": tool.name,
                "session_id": session_id,
                "parameters": StreamNotifier.extract_tool_parameters(args),
                "start_time": datetime.now(UTC).isoformat(),
            }

            try:
                # 导入agent_state_manager以避免循环导入
                from copilot.core.agent_state_manager import agent_state_manager

                # 获取工具信息以确定风险级别
                tool_info = await mcp_server_manager._get_tool_info(tool.name)
                risk_level = tool_info.get("risk_level", "medium") if tool_info else "medium"
                tool_execution_info["risk_level"] = risk_level

                # 通知前端工具开始执行
                if session_id:
                    await StreamNotifier.notify_tool_execution_start(session_id, tool_execution_info)

                # 权限检查逻辑
                if risk_level in ["medium", "high"] and session_id:
                    # 检查或创建执行上下文
                    context = agent_state_manager.get_execution_context(session_id)
                    if not context:
                        context = agent_state_manager.create_execution_context(session_id)
                    
                    # 中高风险工具需要权限确认
                    logger.info(f"Medium/high-risk tool '{tool.name}' requires permission confirmation")
                    
                    # 需要权限确认，创建权限请求
                    async def tool_callback():
                        # 在回调中执行原始工具调用，确保传递config
                        raw_result = await original_arun(*args, **kwargs)
                        
                        # 通知前端工具执行完成
                        if session_id:
                            await StreamNotifier.notify_tool_execution_complete(
                                session_id, tool_execution_info, raw_result, success=True
                            )
                        
                        # 将原始结果转换为用户友好的消息
                        formatted_result = ToolResultProcessor.format_for_user(tool.name, raw_result)
                        # 返回二元组格式 (content, raw_output) 以满足 response_format='content_and_artifact'
                        return (formatted_result, raw_result)

                    # 提取参数用于显示（尽力而为）
                    display_params = {}
                    if args:
                        if isinstance(args[0], dict):
                            display_params = args[0]
                        else:
                            display_params = {"input": str(args[0])}

                    should_continue = await agent_state_manager.request_tool_permission(
                        session_id=session_id, 
                        tool_name=tool.name, 
                        parameters=display_params, 
                        callback=tool_callback, 
                        risk_level=risk_level
                    )

                    if not should_continue:
                        # 通知前端等待权限确认
                        if session_id:
                            await StreamNotifier.notify_tool_waiting_permission(session_id, tool_execution_info)
                        message = f"🔒 等待用户确认执行工具: {tool.name}"
                        # 返回二元组格式 (content, raw_output) 以满足 response_format='content_and_artifact'
                        return (message, {"status": "permission_required", "tool_name": tool.name})

                # 权限已确认或低风险工具，直接调用原始工具
                logger.debug(f"Calling original tool {tool.name} with config: {kwargs.get('config', {})}")
                raw_result = await original_arun(*args, **kwargs)
                logger.info(f"Tool {tool.name} executed successfully")
                
                # 通知前端工具执行完成
                if session_id:
                    await StreamNotifier.notify_tool_execution_complete(
                        session_id, tool_execution_info, raw_result, success=True
                    )
                
                # 将原始结果转换为用户友好的消息
                formatted_result = ToolResultProcessor.format_for_user(tool.name, raw_result)
                # 返回二元组格式 (content, raw_output) 以满足 response_format='content_and_artifact'
                return (formatted_result, raw_result)

            except Exception as e:
                logger.error(f"Exception in wrapped tool {tool.name}: {e}")
                logger.debug(traceback.format_exc())

                # 通知前端工具执行失败
                if session_id:
                    await StreamNotifier.notify_tool_execution_complete(
                        session_id, tool_execution_info, str(e), success=False
                    )

                # 如果包装器出错，尝试确保config参数并重试
                try:
                    if "config" not in kwargs:
                        kwargs["config"] = {}
                    logger.warning(f"Falling back to original tool call for {tool.name}")
                    raw_result = await original_arun(*args, **kwargs)
                    
                    # 通知前端重试成功
                    if session_id:
                        await StreamNotifier.notify_tool_execution_complete(
                            session_id, tool_execution_info, raw_result, success=True
                        )
                    
                    formatted_result = ToolResultProcessor.format_for_user(tool.name, raw_result)
                    # 返回二元组格式 (content, raw_output) 以满足 response_format='content_and_artifact'
                    return (formatted_result, raw_result)
                except Exception as orig_e:
                    logger.error(f"Original tool call also failed: {orig_e}")
                    
                    # 通知前端最终失败
                    if session_id:
                        await StreamNotifier.notify_tool_execution_complete(
                            session_id, tool_execution_info, str(orig_e), success=False
                        )
                    
                    error_message = f"工具 {tool.name} 执行失败: {str(orig_e)}"
                    # 返回二元组格式 (content, raw_output) 以满足 response_format='content_and_artifact'
                    return (error_message, {"status": "error", "error": str(orig_e)})

        # 替换原始的异步执行函数
        tool._arun = custom_arun

        logger.debug(f"Wrapped tool: {tool.name}")
        return tool 