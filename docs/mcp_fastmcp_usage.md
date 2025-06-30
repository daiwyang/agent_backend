# MCP Server Manager 使用指南

## 概述

MCP Server Manager 使用 **FastMCP** 库实现了对 Model Context Protocol (MCP) 服务器的管理。它支持多种连接方式，包括 HTTP/SSE、WebSocket 和 Stdio，并提供了工具权限管理功能。

## FastMCP 的优势

相比自己实现 MCP 协议，使用 FastMCP 有以下优势：

1. **协议兼容性**: 自动处理 MCP 协议的握手、消息格式等细节
2. **传输层抽象**: 自动推断和处理不同的传输方式
3. **类型安全**: 提供完整的类型注解和验证
4. **连接管理**: 自动处理连接生命周期
5. **错误处理**: 内置的错误处理和重试机制

## 支持的连接方式

### 1. HTTP/SSE 服务器

```python
server_config = {
    "id": "http_server",
    "name": "HTTP MCP 服务器",
    "url": "https://api.example.com/mcp",
    "headers": {"Authorization": "Bearer your-token"},
    "timeout": 30.0
}
```

### 2. 本地 Python 脚本

```python
server_config = {
    "id": "local_script",
    "name": "本地脚本服务器",
    "script": "./mcp_server.py"
}
```

### 3. Stdio 命令

```python
server_config = {
    "id": "stdio_server",
    "name": "Stdio 服务器",
    "command": "python",
    "args": ["./server.py", "--verbose"],
    "env": {"DEBUG": "true"},
    "cwd": "/path/to/server"
}
```

### 4. 多服务器配置

```python
server_config = {
    "id": "multi_server",
    "name": "多服务器配置",
    "transport": "stdio",
    "command": "node",
    "args": ["server.js"]
}
```

## 基本使用方法

### 1. 启动管理器

```python
from copilot.mcp.mcp_server_manager import mcp_server_manager

# 启动管理器
await mcp_server_manager.start()
```

### 2. 注册服务器

```python
# 注册服务器
server_config = {
    "id": "filesystem",
    "name": "文件系统服务器",
    "script": "./examples/mcp_servers/filesystem_server.py"
}

success = await mcp_server_manager.register_server(server_config)
if success:
    print("服务器注册成功")
```

### 3. 获取可用工具

```python
# 获取所有可用工具
tools = mcp_server_manager.get_available_tools()
for tool in tools:
    print(f"工具: {tool['name']}")
    print(f"描述: {tool['description']}")
    print(f"风险级别: {tool['risk_level']}")
```

### 4. 调用工具

```python
# 调用工具（带权限检查）
result = await mcp_server_manager.call_tool_with_permission(
    session_id="user_session_123",
    tool_name="filesystem:read_file",
    parameters={"file_path": "./README.md"},
    require_permission=True
)

if result["success"]:
    print("工具执行成功:", result["result"])
else:
    print("工具执行失败:", result["error"])
```

### 5. 获取服务器状态

```python
# 获取已连接的服务器
servers = mcp_server_manager.get_connected_servers()
for server in servers:
    print(f"服务器: {server['name']}")
    print(f"状态: {server['status']}")
    print(f"工具数量: {server['tools_count']}")
```

### 6. 断开服务器

```python
# 断开特定服务器
await mcp_server_manager.disconnect_server("filesystem")

# 停止管理器（断开所有服务器）
await mcp_server_manager.stop()
```

## 工具权限管理

MCP Server Manager 内置了工具权限管理功能：

### 风险级别

- **low**: 低风险操作，如只读查询
- **medium**: 中等风险操作，如文件读取
- **high**: 高风险操作，如代码执行、文件写入

### 权限流程

1. 工具被调用时，系统根据风险级别决定是否需要用户确认
2. 对于 medium 和 high 风险的工具，会向用户发送权限请求
3. 用户可以允许、拒绝或设置自动权限策略
4. 权限请求有超时机制（默认 5 分钟）

## 示例服务器

项目提供了两个示例 MCP 服务器：

### 1. 文件系统服务器 (`filesystem_server.py`)

提供文件操作功能：

- `read_file`: 读取文件内容
- `list_directory`: 列出目录内容
- `get_file_info`: 获取文件信息

### 2. 代码执行服务器 (`code_executor_server.py`)

提供代码执行功能：

- `execute_python_code`: 执行 Python 代码
- `check_python_syntax`: 检查 Python 语法
- `get_python_info`: 获取 Python 环境信息
- `execute_shell_command`: 执行 Shell 命令（安全模式下禁用）

## 完整示例

查看 `examples/mcp_server_example.py` 了解完整的使用示例：

```bash
cd /data/agent_backend
python examples/mcp_server_example.py
```

## 与 API 集成

MCP Server Manager 可以通过 FastAPI 路由暴露给前端：

```python
from fastapi import APIRouter
from copilot.mcp.mcp_server_manager import mcp_server_manager

router = APIRouter()

@router.get("/mcp/servers")
async def get_servers():
    """获取已连接的 MCP 服务器列表"""
    return mcp_server_manager.get_connected_servers()

@router.get("/mcp/tools")
async def get_tools():
    """获取所有可用工具"""
    return mcp_server_manager.get_available_tools()

@router.post("/mcp/servers/register")
async def register_server(config: dict):
    """注册新的 MCP 服务器"""
    success = await mcp_server_manager.register_server(config)
    return {"success": success}

@router.post("/mcp/tools/call")
async def call_tool(session_id: str, tool_name: str, parameters: dict):
    """调用 MCP 工具"""
    result = await mcp_server_manager.call_tool_with_permission(
        session_id=session_id,
        tool_name=tool_name,
        parameters=parameters
    )
    return result
```

## 配置建议

1. **开发环境**: 使用本地脚本方式，便于调试
2. **生产环境**: 使用 HTTP/SSE 方式，提供更好的稳定性
3. **安全考虑**: 始终启用权限检查，特别是对高风险工具
4. **性能优化**: 对于频繁使用的工具，考虑缓存连接

## 故障排除

### 常见问题

1. **连接失败**: 检查服务器配置和网络连接
2. **工具发现失败**: 确保 MCP 服务器正确实现了协议
3. **权限请求超时**: 检查权限管理器配置
4. **工具执行失败**: 查看日志了解具体错误信息

### 调试技巧

1. 启用详细日志记录
2. 使用示例服务器进行测试
3. 检查 FastMCP 的官方文档和示例
4. 使用内存传输方式进行快速测试

## 参考资源

- [FastMCP 官方文档](https://gofastmcp.com/)
- [MCP 协议规范](https://modelcontextprotocol.io/)
- [FastMCP 客户端指南](https://gofastmcp.com/clients/client)
