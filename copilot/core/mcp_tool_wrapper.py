"""
MCP工具包装器 - 统一MCP工具接口、权限管理和状态通知
"""

import traceback
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from langchain_mcp_adapters.client import MultiServerMCPClient

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
                    mcp_config[server["id"]] = {"command": server_config["command"], "args": server_config.get("args", []), "transport": "stdio"}
                elif "url" in server_config and server_config["url"]:
                    # HTTP/SSE 服务器配置
                    mcp_config[server["id"]] = {"url": server_config["url"], "transport": "streamable_http"}
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
                    mcp_config[server["id"]] = {"command": server_config["command"], "args": server_config.get("args", []), "transport": "stdio"}
                elif "url" in server_config and server_config["url"]:
                    # HTTP/SSE 服务器配置
                    mcp_config[server["id"]] = {"url": server_config["url"], "transport": "streamable_http"}
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
                "parameters": StreamNotifier.extract_tool_parameters(args, kwargs, tool.name),
                "start_time": datetime.now(UTC).isoformat(),
            }

            try:
                # 导入agent_state_manager以避免循环导入
                from copilot.core.agent_state_manager import agent_state_manager

                # 获取工具信息以确定风险级别
                tool_info = await mcp_server_manager._get_tool_info(tool.name)
                risk_level = tool_info.get("risk_level", "medium") if tool_info else "medium"
                tool_execution_info["risk_level"] = risk_level

                # 权限检查逻辑 - 先检查权限，再发送执行状态
                if risk_level in ["medium", "high"] and session_id:
                    # 检查或创建执行上下文
                    context = agent_state_manager.get_execution_context(session_id)
                    if not context:
                        context = agent_state_manager.create_execution_context(session_id)

                    # 中高风险工具需要权限确认
                    logger.info(f"Medium/high-risk tool '{tool.name}' requires permission confirmation")

                    # 使用已经提取的参数
                    display_params = tool_execution_info["parameters"]

                    # 发送权限请求和等待状态通知，获取request_id
                    request_id = None
                    if session_id:
                        # 发送权限请求，获取唯一的request_id
                        request_id = await StreamNotifier.send_tool_permission_request(
                            session_id=session_id, tool_name=tool.name, parameters=display_params, risk_level=risk_level
                        )

                        # 发送等待状态通知
                        await StreamNotifier.send_tool_execution_status(
                            session_id=session_id, request_id=request_id, tool_name=tool.name, status="waiting"
                        )

                    # 创建一个简单的权限检查，不传递回调函数
                    should_continue = await agent_state_manager.request_tool_permission(
                        session_id=session_id,
                        tool_name=tool.name,
                        parameters=display_params,
                        callback=None,  # 不使用回调，在主流程中执行
                        risk_level=risk_level,
                    )

                    if not should_continue and request_id:
                        # 🔥 关键修改：使用request_id精确等待权限确认
                        logger.info(f"Tool {tool.name} waiting for permission confirmation (request_id: {request_id})")

                        # 等待特定工具的权限确认结果（30秒超时）
                        permission_granted = await agent_state_manager.wait_for_permission_by_request_id(session_id, request_id, timeout=30)

                        if permission_granted:
                            logger.info(f"Permission granted for tool {tool.name} (request_id: {request_id}), executing now...")
                            # 权限已确认，在主流程中执行工具
                            if session_id:
                                await StreamNotifier.send_tool_execution_status(
                                    session_id=session_id, request_id=request_id, tool_name=tool.name, status="executing"
                                )

                            raw_result = await original_arun(*args, **kwargs)

                            if session_id:
                                # 通知前端工具执行完成，使用实际的工具结果数据
                                tool_execution_info["request_id"] = request_id
                                await StreamNotifier.notify_tool_execution_complete(session_id, tool_execution_info, raw_result, success=True)

                            # 🔥 关键修复：返回格式化结果给模型使用，通过聊天流过滤避免直接显示给用户
                            processed_result = MCPToolWrapper._format_for_ai(tool.name, raw_result)
                            # 返回二元组格式 (content, raw_output) 满足 response_format='content_and_artifact'
                            # content包含格式化结果供模型使用，聊天流过滤器会过滤掉工具消息
                            return (processed_result, raw_result)
                        else:
                            logger.info(f"Permission denied or timeout for tool {tool.name} (request_id: {request_id})")
                            error_message = f"工具 {tool.name} 的执行权限被拒绝或超时"
                            # 返回二元组格式满足langchain-mcp-adapters要求，content为空避免聊天流显示
                            return ("", {"status": "permission_denied", "tool_name": tool.name, "request_id": request_id})

                # 权限已确认或低风险工具，直接调用原始工具
                # 发送执行开始通知
                if session_id:
                    await StreamNotifier.notify_tool_execution_start(session_id, tool_execution_info)

                logger.debug(f"Calling original tool {tool.name} with config: {kwargs.get('config', {})}")
                
                # 添加预检查逻辑
                try:
                    # 检查工具是否有必要的属性
                    if not hasattr(tool, '_arun') and not hasattr(tool, 'arun'):
                        raise AttributeError(f"Tool {tool.name} missing async execution method")
                    
                    # 记录调用前的状态
                    logger.debug(f"Tool {tool.name} pre-execution check passed")
                    logger.debug(f"Args: {args}, Kwargs keys: {list(kwargs.keys())}")
                    
                    # 检查原始工具函数是否可调用
                    if not callable(original_arun):
                        raise TypeError(f"Original arun for tool {tool.name} is not callable")
                        
                except Exception as check_e:
                    logger.error(f"Pre-execution check failed for tool {tool.name}: {check_e}")
                    raise check_e
                
                raw_result = await original_arun(*args, **kwargs)
                logger.info(f"Tool {tool.name} executed successfully")

                # 通知前端工具执行完成
                if session_id:
                    await StreamNotifier.notify_tool_execution_complete(session_id, tool_execution_info, raw_result, success=True)

                # 🔥 关键修复：返回格式化结果给模型使用，通过聊天流过滤避免直接显示给用户
                processed_result = MCPToolWrapper._format_for_ai(tool.name, raw_result)
                # 返回二元组格式 (content, raw_output) 满足 response_format='content_and_artifact'
                # content包含格式化结果供模型使用，聊天流过滤器会过滤掉工具消息
                return (processed_result, raw_result)

            except Exception as e:
                logger.error(f"Exception in wrapped tool {tool.name}: {e}")
                logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
                logger.debug(traceback.format_exc())

                # 通知前端工具执行失败
                if session_id:
                    await StreamNotifier.notify_tool_execution_complete(session_id, tool_execution_info, str(e), success=False)

                # 如果包装器出错，尝试确保config参数并重试
                try:
                    if "config" not in kwargs:
                        kwargs["config"] = {}
                    logger.warning(f"Falling back to original tool call for {tool.name}")
                    logger.debug(f"Fallback kwargs: {kwargs}")
                    raw_result = await original_arun(*args, **kwargs)

                    # 通知前端重试成功
                    if session_id:
                        await StreamNotifier.notify_tool_execution_complete(session_id, tool_execution_info, raw_result, success=True)

                    processed_result = MCPToolWrapper._format_for_ai(tool.name, raw_result)
                    # 返回二元组格式 (content, raw_output) 满足 response_format='content_and_artifact'
                    # content 部分设为空字符串，避免在聊天流中显示工具结果
                    return ("", raw_result)
                except Exception as orig_e:
                    logger.error(f"Original tool call also failed: {orig_e}")
                    logger.error(f"Original exception details: {type(orig_e).__name__}: {str(orig_e)}")
                    logger.debug(f"Original tool traceback: {traceback.format_exc()}")

                    # 通知前端最终失败
                    if session_id:
                        await StreamNotifier.notify_tool_execution_complete(session_id, tool_execution_info, str(orig_e), success=False)

                    error_message = f"工具 {tool.name} 执行失败: {str(orig_e)}"
                    # 返回二元组格式 (content, raw_output) 满足 response_format='content_and_artifact'
                    return (error_message, {"status": "error", "error": str(orig_e)})

        # 替换原始的异步执行函数
        tool._arun = custom_arun

        logger.debug(f"Wrapped tool: {tool.name}")
        return tool

    @staticmethod
    def _format_for_ai(tool_name: str, raw_result: Any) -> str:
        """
        格式化工具结果给AI模型使用

        Args:
            tool_name: 工具名称
            raw_result: 工具的原始返回结果

        Returns:
            str: 格式化后的结果，包含实际数据内容
        """
        try:
            import json

            # 处理MCP工具的标准返回格式
            if isinstance(raw_result, dict):
                # 检查是否有content字段（MCP工具的标准格式）
                if "content" in raw_result:
                    content = raw_result["content"]
                    if isinstance(content, list) and len(content) > 0:
                        # 提取文本内容
                        text_parts = []
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                text_parts.append(item["text"])
                            elif isinstance(item, str):
                                text_parts.append(item)
                            else:
                                text_parts.append(str(item))
                        return "\n".join(text_parts)

                # 检查是否是包装后的结果格式
                if "success" in raw_result and "result" in raw_result:
                    result_data = raw_result["result"]
                    if isinstance(result_data, dict) and "processed_text" in result_data:
                        return result_data["processed_text"]
                    elif isinstance(result_data, dict) and "raw_output" in result_data:
                        return MCPToolWrapper._format_for_ai(tool_name, result_data["raw_output"])
                    else:
                        return str(result_data)

                # 对于结构化数据，直接返回JSON格式，不要前缀
                try:
                    formatted_json = json.dumps(raw_result, ensure_ascii=False, indent=2)
                    return formatted_json
                except:
                    return str(raw_result)

            elif isinstance(raw_result, str):
                # 尝试解析JSON字符串
                try:
                    parsed_data = json.loads(raw_result)
                    if isinstance(parsed_data, dict):
                        formatted_json = json.dumps(parsed_data, ensure_ascii=False, indent=2)
                        return formatted_json
                except:
                    pass
                # 直接返回字符串内容
                return raw_result

            else:
                # 其他类型转换为字符串
                return str(raw_result)

        except Exception as e:
            logger.warning(f"Error formatting tool result for AI: {e}")
            return f"工具执行完成，但结果格式化失败：{str(e)}"
