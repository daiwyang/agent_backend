"""
MCP Server 管理器 - 基于 FastMCP Client API 的轻量级封装
直接使用 fastmcp Client，最小化中间层，专注于业务逻辑
"""

from typing import Any, Dict, List, Optional

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from copilot.mcp.tool_permission_manager import tool_permission_manager
from copilot.utils.logger import logger


class MCPServerManager:
    """
    MCP服务器管理器 - 直接基于 FastMCP Client API

    去除不必要的中间层，直接使用 fastmcp.Client 作为核心
    只封装必要的业务逻辑：配置管理、工具注册、权限控制
    """

    def __init__(self):
        # 服务器注册信息：{server_id: {"client": Client, "config": dict, "tools": dict}}
        self.servers: Dict[str, Dict[str, Any]] = {}

        # 全局工具索引：{tool_full_name: tool_info}
        # tool_full_name 格式: "server_id::tool_name"
        self.tools_index: Dict[str, Dict[str, Any]] = {}

    async def start(self):
        """启动MCP服务器管理器"""
        await tool_permission_manager.start()
        logger.info("MCPServerManager started with FastMCP")

    async def stop(self):
        """停止MCP服务器管理器"""
        # 清理所有服务器
        for server_id in list(self.servers.keys()):
            await self.unregister_server(server_id)

        await tool_permission_manager.stop()
        logger.info("MCPServerManager stopped")

    async def register_server(self, server_config: Dict[str, Any]) -> bool:
        """
        注册 MCP 服务器

        Args:
            server_config: 标准 FastMCP 配置
            {
                "id": "unique_server_id",
                "name": "Server Name",

                # FastMCP 支持的配置：
                "url": "https://api.example.com/mcp",  # HTTP/SSE
                "auth": "token" | "oauth",             # 身份验证
                "headers": {"X-API-Key": "key"},       # 自定义头部
                "script": "./server.py",               # 本地脚本
                "command": "python", "args": [...],    # Stdio
                "transport": "stdio|http|sse",         # 传输方式
                "timeout": 30.0,

                # 业务配置：
                "tool_risks": {"tool_name": "low|medium|high"}
            }

        Returns:
            bool: 注册是否成功
        """
        server_id = server_config["id"]

        try:
            if server_id in self.servers:
                logger.error(f"Server already registered: {server_id}")
                return False

            if not self._validate_config(server_config):
                return False

            logger.info(f"Registering MCP server: {server_id}")

            # 直接使用 FastMCP Client
            client = self._create_client(server_config)

            # 连接并发现工具
            tools = await self._discover_tools(client, server_config)

            if tools is None:  # 连接失败
                return False

            # 注册服务器和工具
            self.servers[server_id] = {"client": client, "config": server_config, "tools": tools}

            # 更新全局工具索引
            self._update_tools_index(server_id, tools, server_config)

            logger.info(f"Successfully registered server {server_id} with {len(tools)} tools")
            return True

        except Exception as e:
            logger.error(f"Failed to register server {server_id}: {e}")
            return False

    async def unregister_server(self, server_id: str) -> bool:
        """注销 MCP 服务器"""
        try:
            if server_id not in self.servers:
                logger.warning(f"Server not registered: {server_id}")
                return False

            # 清理工具索引
            tools_to_remove = [name for name in self.tools_index.keys() if name.startswith(f"{server_id}::")]
            for tool_name in tools_to_remove:
                del self.tools_index[tool_name]

            # 清理服务器
            del self.servers[server_id]

            logger.info(f"Unregistered server: {server_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to unregister server {server_id}: {e}")
            return False

    async def call_tool(
        self, tool_name: str, parameters: Dict[str, Any], session_id: Optional[str] = None, require_permission: bool = True
    ) -> Dict[str, Any]:
        """
        调用工具

        Args:
            tool_name: 工具全名 "server_id::tool_name" 或简名 "tool_name"
            parameters: 工具参数
            session_id: 会话ID（权限检查需要）
            require_permission: 是否需要权限检查

        Returns:
            Dict: {"success": bool, "result": Any, "error": str}
        """
        try:
            # 解析工具名称
            full_tool_name = self._resolve_tool_name(tool_name)
            if not full_tool_name:
                return {"success": False, "error": f"Tool not found: {tool_name}", "result": None}

            tool_info = self.tools_index[full_tool_name]
            server_id, actual_tool_name = full_tool_name.split("::", 1)

            # 权限检查
            if require_permission and session_id:
                if not await self._check_permission(session_id, tool_info, parameters):
                    return {"success": False, "error": "Permission denied or request timed out", "result": None, "permission_required": True}

            # 直接使用 FastMCP Client 调用工具
            client = self.servers[server_id]["client"]

            async with client:
                result = await client.call_tool(actual_tool_name, parameters)

                # 处理 FastMCP 结果格式
                processed_result = self._process_tool_result(result)

                logger.info(f"Tool executed successfully: {full_tool_name}")
                return {"success": True, "result": processed_result, "error": None}

        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return {"success": False, "error": str(e), "result": None}

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取所有可用工具"""
        return list(self.tools_index.values())

    def get_servers_info(self) -> List[Dict[str, Any]]:
        """获取服务器信息"""
        servers = []
        for server_id, server_data in self.servers.items():
            config = server_data["config"]
            tools = server_data["tools"]

            servers.append(
                {
                    "id": server_id,
                    "name": config.get("name", server_id),
                    "status": "connected",  # 简化状态管理
                    "tools_count": len(tools),
                    "tools": list(tools.keys()),
                }
            )
        return servers

    def _create_client(self, config: Dict[str, Any]) -> Client:
        """根据配置创建 FastMCP Client"""

        # HTTP/SSE 服务器
        if "url" in config:
            url = config["url"]
            timeout = config.get("timeout", 30.0)

            # 处理身份验证
            auth = config.get("auth")
            headers = config.get("headers")

            if headers and not auth:
                # 自定义头部认证
                transport = StreamableHttpTransport(url=url, headers=headers)
                return Client(transport, timeout=timeout)
            elif auth:
                # 标准认证（Bearer/OAuth）
                return Client(url, auth=auth, timeout=timeout)
            else:
                # 无认证
                return Client(url, timeout=timeout)

        # 本地脚本
        elif "script" in config:
            return Client(config["script"])

        # Stdio 命令
        elif "command" in config:
            mcp_config = {
                "mcpServers": {
                    config["id"]: {
                        "transport": "stdio",
                        "command": config["command"],
                        "args": config.get("args", []),
                        "env": config.get("env", {}),
                        "cwd": config.get("cwd"),
                    }
                }
            }
            return Client(mcp_config)

        # 完整 MCP 配置
        elif "transport" in config:
            mcp_config = {"mcpServers": {config["id"]: {k: v for k, v in config.items() if k not in ["id", "name", "tool_risks"]}}}
            return Client(mcp_config)

        else:
            raise ValueError(f"Invalid server configuration")

    async def _discover_tools(self, client: Client, config: Dict[str, Any]) -> Optional[Dict[str, Dict[str, Any]]]:
        """发现工具"""
        try:
            async with client:
                # 验证连接
                await client.ping()

                # 获取工具列表
                tools_response = await client.list_tools()

                tools = {}
                tool_risks = config.get("tool_risks", {})

                for tool in tools_response.tools:
                    tools[tool.name] = {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema or {},
                        "risk_level": tool_risks.get(tool.name, "medium"),
                    }

                return tools

        except Exception as e:
            logger.error(f"Failed to discover tools: {e}")
            return None

    def _update_tools_index(self, server_id: str, tools: Dict[str, Dict[str, Any]], config: Dict[str, Any]):
        """更新全局工具索引"""
        for tool_name, tool_info in tools.items():
            full_name = f"{server_id}::{tool_name}"

            self.tools_index[full_name] = {**tool_info, "server_id": server_id, "server_name": config.get("name", server_id), "full_name": full_name}

    def _resolve_tool_name(self, tool_name: str) -> Optional[str]:
        """解析工具名称，支持简名和全名"""
        # 如果是全名，直接查找
        if "::" in tool_name and tool_name in self.tools_index:
            return tool_name

        # 如果是简名，查找匹配的工具
        matches = [name for name in self.tools_index.keys() if name.split("::", 1)[1] == tool_name]

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            logger.warning(f"Multiple tools named '{tool_name}': {matches}")
            return matches[0]  # 返回第一个匹配
        else:
            return None

    async def _check_permission(self, session_id: str, tool_info: Dict[str, Any], parameters: Dict[str, Any]) -> bool:
        """检查工具权限"""
        risk_level = tool_info.get("risk_level", "medium")

        # 低风险工具直接放行
        if risk_level == "low":
            return True

        # 中高风险工具需要用户确认
        return await tool_permission_manager.request_tool_permission(
            session_id=session_id,
            tool_name=tool_info["name"],
            tool_description=tool_info["description"],
            parameters=parameters,
            risk_level=risk_level,
            timeout=300,
        )

    def _process_tool_result(self, result: Any) -> Any:
        """处理 FastMCP 工具调用结果"""
        if hasattr(result, "content") and result.content:
            # 提取文本内容
            text_parts = []
            for content in result.content:
                if hasattr(content, "text"):
                    text_parts.append(content.text)
            return "\n".join(text_parts) if text_parts else str(result)
        else:
            return str(result)

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """验证服务器配置"""
        if not config.get("id"):
            logger.error("Missing required field: 'id'")
            return False

        if not config.get("name"):
            logger.error("Missing required field: 'name'")
            return False

        # 验证连接配置
        connection_fields = ["url", "script", "command", "transport"]
        if not any(config.get(field) for field in connection_fields):
            logger.error("Must specify at least one connection method")
            return False

        # 验证风险级别
        tool_risks = config.get("tool_risks", {})
        valid_levels = {"low", "medium", "high"}
        for tool_name, risk in tool_risks.items():
            if risk not in valid_levels:
                logger.error(f"Invalid risk level '{risk}' for tool '{tool_name}'")
                return False

        return True


# 全局实例
mcp_server_manager = MCPServerManager()
