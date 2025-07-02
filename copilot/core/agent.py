"""
核心Agent - 支持多个LLM提供商和MCP工具
"""

import traceback
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from copilot.core.llm_factory import LLMFactory
from copilot.mcp_client.mcp_server_manager import mcp_server_manager
from copilot.utils.logger import logger
from copilot.utils.token_calculator import TokenCalculator


class CoreAgent:
    """核心Agent - 支持多个LLM提供商和MCP工具"""

    def __init__(self, provider: Optional[str] = None, model_name: Optional[str] = None, tools: List = None, mcp_tools: List = None, **llm_kwargs):
        """
        初始化Agent

        Args:
            provider: LLM提供商 (deepseek, openai, claude, moonshot, zhipu, qwen, gemini)
            model_name: 模型名称
            tools: 传统工具列表
            mcp_tools: MCP工具列表（从外部传入）
            **llm_kwargs: 传递给LLM的额外参数
        """
        self.provider = provider
        self.model_name = model_name
        self.tools = tools or []
        self.mcp_tools = mcp_tools or []
        self.llm_kwargs = llm_kwargs
        self.memory = MemorySaver()
        self.enable_mcp_tools = True  # 启用MCP工具支持

        # 初始化LLM
        try:
            self.llm = LLMFactory.create_llm(provider=provider, model=model_name, **llm_kwargs)
            logger.info(f"CoreAgent initialized with provider: {provider or 'default'}, model: {model_name or 'default'}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {str(e)}")
            raise

        # 合并MCP工具和传统工具
        all_tools = self._merge_tools()

        # 创建LangGraph agent
        self.graph = create_react_agent(
            self.llm, tools=all_tools, prompt="You are a helpful assistant. Please respond in Chinese.", checkpointer=self.memory
        )

    def _merge_tools(self) -> List:
        """合并传统工具和MCP工具"""
        merged_tools = self.tools.copy()

        if self.enable_mcp_tools and self.mcp_tools:
            merged_tools.extend(self.mcp_tools)
            logger.info(f"Added {len(self.mcp_tools)} MCP tools to agent")

        return merged_tools

    @classmethod
    async def create_with_mcp_tools(cls, provider: Optional[str] = None, model_name: Optional[str] = None, tools: List = None, **llm_kwargs):
        """
        异步创建带有MCP工具的Agent

        Args:
            provider: LLM提供商
            model_name: 模型名称
            tools: 传统工具列表
            **llm_kwargs: 传递给LLM的额外参数

        Returns:
            CoreAgent: 配置了MCP工具的Agent实例
        """
        # 获取MCP工具
        mcp_tools = await cls._get_mcp_tools()

        logger.info(
            f"Creating CoreAgent with provider: {provider}, model: {model_name}, tools: {len(tools) if tools else 0}, mcp_tools: {len(mcp_tools)}"
        )

        # 创建Agent实例
        return cls(provider=provider, model_name=model_name, tools=tools, mcp_tools=mcp_tools, **llm_kwargs)

    @classmethod
    async def _get_mcp_tools(cls) -> List:
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
                wrapped_tools = [cls._wrap_mcp_tool(tool) for tool in all_tools]
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

    @staticmethod
    def _wrap_mcp_tool(tool: Any) -> Any:
        """
        包装从 langchain-mcp-adapters 获取的工具，集成Agent状态管理器
        实现非阻塞的权限检查机制
        """
        # 保存原始的执行函数
        original_arun = tool._arun

        async def custom_arun(*args, **kwargs) -> Any:
            """
            自定义的工具执行逻辑 - 集成Agent状态管理器
            """
            session_id = None

            # 从kwargs中获取session_id - 修正提取逻辑
            config = kwargs.get("config", {})
            if config and isinstance(config, dict) and "configurable" in config:
                session_id = config["configurable"].get("session_id")

            # 确保config参数存在
            if "config" not in kwargs:
                kwargs["config"] = {}

            logger.info(f"Executing wrapped tool: {tool.name} with session_id: {session_id}")
            logger.debug(f"Tool {tool.name} called with args: {args}, kwargs keys: {list(kwargs.keys())}")

            try:
                # 导入agent_state_manager以避免循环导入
                from copilot.core.agent_state_manager import agent_state_manager

                # 获取工具信息以确定风险级别
                tool_info = await mcp_server_manager._get_tool_info(tool.name)
                risk_level = tool_info.get("risk_level", "medium") if tool_info else "medium"

                # 权限检查逻辑
                if risk_level in ["medium", "high"] and session_id:
                    # 检查是否已经有权限确认
                    context = agent_state_manager.get_execution_context(session_id)
                    if context and hasattr(context, "pending_tool_permissions"):
                        # 检查是否已经确认过这个工具
                        tool_key = f"{tool.name}_{hash(str(args))}"
                        if tool_key not in context.pending_tool_permissions:
                            # 需要权限确认，创建权限请求
                            async def tool_callback():
                                # 在回调中执行原始工具调用，确保传递config
                                return await original_arun(*args, **kwargs)

                            # 提取参数用于显示（尽力而为）
                            display_params = {}
                            if args:
                                if isinstance(args[0], dict):
                                    display_params = args[0]
                                else:
                                    display_params = {"input": str(args[0])}

                            should_continue = await agent_state_manager.request_tool_permission(
                                session_id=session_id, tool_name=tool.name, parameters=display_params, callback=tool_callback, risk_level=risk_level
                            )

                            if not should_continue:
                                return f"🔒 等待用户确认执行工具: {tool.name}"

                # 权限已确认或低风险工具，直接调用原始工具
                logger.debug(f"Calling original tool {tool.name} with config: {kwargs.get('config', {})}")
                result = await original_arun(*args, **kwargs)
                logger.info(f"Tool {tool.name} executed successfully")
                return result

            except Exception as e:
                logger.error(f"Exception in wrapped tool {tool.name}: {e}")
                logger.debug(traceback.format_exc())

                # 如果包装器出错，尝试确保config参数并重试
                try:
                    if "config" not in kwargs:
                        kwargs["config"] = {}
                    logger.warning(f"Falling back to original tool call for {tool.name}")
                    return await original_arun(*args, **kwargs)
                except Exception as orig_e:
                    logger.error(f"Original tool call also failed: {orig_e}")
                    return f"Tool execution failed: {str(orig_e)}"

        # 替换原始的异步执行函数
        tool._arun = custom_arun

        logger.debug(f"Wrapped tool: {tool.name}")
        return tool

    async def chat(
        self,
        message: str,
        thread_id: Optional[str] = None,
        session_id: Optional[str] = None,
        images: Optional[List] = None,
        enable_tools: bool = True,
    ):
        """
        统一的流式聊天接口，支持多模态、工具调用和权限确认

        Args:
            message: 用户消息
            thread_id: 线程ID（用于会话管理）
            session_id: 会话ID（用于MCP工具权限管理）
            images: 图片列表（多模态输入）
            enable_tools: 是否启用工具调用

        Yields:
            str: 响应片段
        """
        # 设置当前会话ID，供MCP工具使用
        self._current_session_id = session_id

        try:
            # 导入agent_state_manager和AgentExecutionState
            from copilot.core.agent_state_manager import AgentExecutionState, agent_state_manager

            # 创建或获取执行上下文
            if session_id:
                context = agent_state_manager.get_execution_context(session_id)
                if not context:
                    context = agent_state_manager.create_execution_context(session_id, thread_id)
                context.update_state(AgentExecutionState.RUNNING)

            # 1. 准备配置
            config = self._prepare_config(thread_id, session_id)

            # 2. 构建输入消息
            inputs = await self._build_inputs(message, images, session_id, enable_tools)

            # 3. 使用流式输出
            async for chunk in self._chat_stream_with_permission_handling(inputs, config, session_id):
                yield chunk

        finally:
            # 清理会话ID
            self._current_session_id = None

    def _prepare_config(self, thread_id: Optional[str], session_id: Optional[str]) -> Dict:
        """准备LangGraph配置"""
        config = {}
        if thread_id:
            config["configurable"] = {"thread_id": thread_id}
        if session_id:
            config.setdefault("configurable", {})["session_id"] = session_id
        return config

    async def _build_inputs(self, message: str, images: Optional[List], session_id: Optional[str], enable_tools: bool) -> Dict:
        """构建输入消息"""
        # 处理MCP工具的session_id注入
        # 注意：现在通过包装器注入session_id，这里的代码可能需要调整或移除
        # if session_id and enable_tools and self.enable_mcp_tools:
        #     message = f"[SESSION_ID:{session_id}] {message}"

        # 构建消息内容
        if images and self._supports_multimodal():
            # 多模态输入
            content = [{"type": "text", "text": message}]
            for img in images:
                processed_img = await self._preprocess_image(img)
                content.append(processed_img)
        else:
            # 纯文本输入
            content = message

        logger.debug(f"Prepared input content: {content}")

        return {"messages": [{"role": "user", "content": content}]}

    def _supports_multimodal(self) -> bool:
        """检查当前提供商是否支持多模态"""
        return self.provider in ["openai", "claude", "gemini"]

    async def _chat_stream_with_permission_handling(self, inputs: Dict, config: Dict, session_id: Optional[str]) -> AsyncGenerator[str, None]:
        """带权限处理的流式聊天方法"""
        try:
            from copilot.core.agent_state_manager import AgentExecutionState, agent_state_manager

            # 第一阶段：正常执行直到遇到权限确认
            async for chunk in self._chat_stream_internal(inputs, config):
                # 检查是否遇到权限确认请求
                if "🔒 等待用户确认执行工具:" in str(chunk):
                    yield chunk

                    # 如果有session_id，等待权限确认
                    if session_id:
                        context = agent_state_manager.get_execution_context(session_id)
                        if context and context.state == AgentExecutionState.WAITING_PERMISSION:
                            yield "\n\n⏳ 请在聊天界面中确认是否允许执行此工具...\n"

                            # 等待用户权限确认
                            permission_granted = await agent_state_manager.wait_for_permission(session_id, timeout=300)

                            if permission_granted:
                                yield "✅ 权限已确认，继续执行...\n"
                                # 继续执行 - 这里可能需要重新调用Agent或恢复执行
                                # 由于权限确认后工具已经在回调中执行，这里主要是状态同步
                                context.update_state(AgentExecutionState.COMPLETED)
                            else:
                                yield "❌ 权限被拒绝或超时，执行已停止。\n"
                                context.update_state(AgentExecutionState.PAUSED)
                                break
                else:
                    yield chunk

        except Exception as e:
            logger.error(f"Error in chat_stream_with_permission_handling: {str(e)}")
            yield f"处理请求时出现错误: {str(e)}"

    async def _chat_stream_internal(self, inputs: Dict, config: Dict) -> AsyncGenerator[str, None]:
        """内部流式聊天方法"""
        try:
            # 尝试使用流式输出
            async for chunk in self.graph.astream(inputs, config=config, stream_mode="messages"):
                if chunk and len(chunk) >= 2:
                    message_chunk, _ = chunk
                    if hasattr(message_chunk, "content") and message_chunk.content:
                        yield str(message_chunk.content)
            return
        except Exception as e:
            logger.warning(f"Streaming failed: {str(e)}, falling back to chunk mode")

        # 回退到分块模式
        try:
            async for chunk in self.graph.astream(inputs, config=config, stream_mode="updates"):
                if "agent" in chunk and "messages" in chunk["agent"]:
                    for msg in chunk["agent"]["messages"]:
                        if hasattr(msg, "content") and msg.content:
                            content = str(msg.content)
                            # 简单分块
                            for i in range(0, len(content), 30):
                                yield content[i : i + 30]
                            return
        except Exception as e:
            logger.error(f"Error in chat_stream: {str(e)}")
            yield f"处理请求时出现错误: {str(e)}"

    def get_provider_info(self) -> Dict[str, Any]:
        """
        获取当前使用的提供商信息

        Returns:
            Dict[str, Any]: 提供商信息
        """
        return {"provider": self.provider, "model": self.model_name, "available_providers": LLMFactory.get_available_providers()}

    def switch_provider(self, provider: str, model_name: Optional[str] = None, **llm_kwargs) -> bool:
        """
        切换LLM提供商

        Args:
            provider: 新的提供商
            model_name: 新的模型名称
            **llm_kwargs: 传递给LLM的额外参数

        Returns:
            bool: 是否切换成功
        """
        try:
            # 验证提供商是否可用
            if not LLMFactory.validate_provider(provider):
                logger.error(f"Provider {provider} is not available (missing API key)")
                return False

            # 创建新的LLM实例
            new_llm = LLMFactory.create_llm(provider=provider, model=model_name, **llm_kwargs)

            # 更新实例变量
            self.provider = provider
            self.model_name = model_name
            self.llm_kwargs = llm_kwargs
            self.llm = new_llm

            # 重新创建agent - 注意要使用合并后的工具
            all_tools = self._merge_tools()
            self.graph = create_react_agent(
                self.llm, tools=all_tools, prompt="You are a helpful assistant. Please respond in Chinese.", checkpointer=self.memory
            )

            logger.info(f"Successfully switched to provider: {provider}, model: {model_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to switch provider: {str(e)}")
            return False

    async def _preprocess_image(self, image_data: dict) -> dict:
        """
        图片预处理
        - 格式转换
        - 尺寸调整
        - 质量压缩
        """
        # 根据不同提供商处理图片格式
        if self.provider == "openai":
            return {
                "type": "image_url",
                "image_url": {"url": image_data.get("url") or f"data:{image_data.get('mime_type', 'image/jpeg')};base64,{image_data.get('base64')}"},
            }
        elif self.provider == "claude":
            return {
                "type": "image",
                "source": {"type": "base64", "media_type": image_data.get("mime_type", "image/jpeg"), "data": image_data.get("base64")},
            }
        else:
            # 默认格式
            return {
                "type": "image",
                "source": {"type": "base64", "media_type": image_data.get("mime_type", "image/jpeg"), "data": image_data.get("base64")},
            }

    def _estimate_token_usage(self, prompt: str, completion: str) -> Dict[str, int]:
        """
        估算token使用量

        Args:
            prompt: 用户输入
            completion: 模型回复

        Returns:
            Dict[str, int]: token使用量统计
        """
        try:
            # 获取当前模型的key
            model_key = TokenCalculator.get_model_key(self.provider, self.model_name)

            # 计算token使用量
            usage = TokenCalculator.calculate_usage(prompt, completion, model_key)

            return usage.to_dict()

        except Exception as e:
            logger.warning(f"Token estimation failed: {str(e)}")
            # 返回默认值，避免系统崩溃
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def get_token_calculator(self) -> TokenCalculator:
        """获取token计算器实例"""
        return TokenCalculator()

    async def update_mcp_tools(self, mcp_tools: List) -> bool:
        """
        动态更新Agent的MCP工具

        Args:
            mcp_tools: 新的MCP工具列表

        Returns:
            bool: 是否更新成功
        """
        try:
            # 更新MCP工具列表
            self.mcp_tools = mcp_tools

            # 重新合并所有工具
            all_tools = self._merge_tools()

            # 重新创建LangGraph agent
            self.graph = create_react_agent(
                self.llm, tools=all_tools, prompt="You are a helpful assistant. Please respond in Chinese.", checkpointer=self.memory
            )

            logger.info(f"Successfully updated Agent with {len(mcp_tools)} MCP tools")
            return True

        except Exception as e:
            logger.error(f"Failed to update MCP tools: {e}")
            return False

    async def reload_mcp_tools_from_servers(self, server_ids: List[str]) -> bool:
        """
        从指定服务器重新加载MCP工具

        Args:
            server_ids: MCP服务器ID列表

        Returns:
            bool: 是否重新加载成功
        """
        try:
            # 获取指定服务器的MCP工具
            mcp_tools = await self._get_mcp_tools_for_servers(server_ids)

            # 更新工具
            return await self.update_mcp_tools(mcp_tools)

        except Exception as e:
            logger.error(f"Failed to reload MCP tools from servers {server_ids}: {e}")
            return False

    @classmethod
    async def _get_mcp_tools_for_servers(cls, server_ids: List[str]) -> List:
        """
        从指定MCP服务器获取工具

        Args:
            server_ids: MCP服务器ID列表

        Returns:
            List: 包装后的MCP工具列表
        """
        try:
            from copilot.mcp_client.mcp_server_manager import mcp_server_manager

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
            from langchain_mcp_adapters.client import MultiServerMCPClient

            client = MultiServerMCPClient(mcp_config)

            try:
                # 异步获取所有MCP工具
                all_tools = await client.get_tools()

                logger.info(f"Successfully loaded {len(all_tools)} MCP tools from servers: {server_ids}")

                # 包装所有MCP工具以集成权限检查和自定义逻辑
                wrapped_tools = [cls._wrap_mcp_tool(tool) for tool in all_tools]
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
