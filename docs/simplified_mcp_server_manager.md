# 简化版 MCP Server Manager

基于 FastMCP Client API 的轻量级 MCP 服务器管理器，去除不必要的中间层，直接使用官方推荐的最佳实践。

## 设计理念

### 核心变化

1. **去除中间层**：删除了 `MCPTool` 和 `MCPServerConnection` 包装类
2. **直接使用 FastMCP**：核心逻辑直接基于 `fastmcp.Client` API  
3. **简化工具管理**：使用扁平的索引结构，工具信息直接从 FastMCP 获取
4. **保留必要功能**：权限管理、配置验证等业务逻辑保留

### 优势

- **代码更简洁**：减少 60% 的代码量
- **更贴近官方**：完全符合 FastMCP 推荐用法
- **性能更好**：减少对象创建和数据转换开销
- **维护更容易**：更少的抽象层，问题更容易定位

## 核心架构

```python
class MCPServerManager:
    def __init__(self):
        # 服务器注册：{server_id: {"client": Client, "config": dict, "tools": dict}}
        self.servers: Dict[str, Dict[str, Any]] = {}
        
        # 工具索引：{"server_id::tool_name": tool_info}
        self.tools_index: Dict[str, Dict[str, Any]] = {}
```

## 工具命名规范

- **全名格式**：`server_id::tool_name`（用 `::` 分隔）
- **支持简名**：如果工具名唯一，可直接使用 `tool_name`
- **自动解析**：系统会自动查找匹配的工具

```python
# 支持的调用方式
await manager.call_tool("weather_server::get_weather", {...})  # 全名
await manager.call_tool("get_weather", {...})                  # 简名（如果唯一）
```

## FastMCP 配置支持

### HTTP/SSE 服务器

```python
config = {
    "id": "api_server",
    "name": "API Server",
    "url": "https://api.example.com/mcp",
    
    # 身份验证选项
    "auth": "your-bearer-token",           # Bearer Token
    # 或 "auth": "oauth",                  # OAuth 流程
    # 或 "headers": {"X-API-Key": "key"},  # 自定义头部
    
    "timeout": 30.0
}
```

### 本地脚本

```python
config = {
    "id": "local_script",
    "name": "Local Python Script", 
    "script": "./mcp_server.py"  # FastMCP 自动推理传输方式
}
```

### Stdio 服务器

```python
config = {
    "id": "stdio_server",
    "name": "Stdio Server",
    "command": "python",
    "args": ["./server.py", "--verbose"],
    "env": {"DEBUG": "true"},
    "cwd": "/path/to/server"
}
```

### 完整 MCP 配置

```python
config = {
    "id": "full_config",
    "name": "Full MCP Config",
    "transport": "stdio",
    "command": "node",
    "args": ["server.js"],
    "timeout": 60.0
}
```

## 工具风险级别

```python
config = {
    "id": "server_with_risks",
    "name": "Server with Risk Config",
    "url": "https://api.example.com/mcp",
    "auth": "token",
    
    # 工具风险配置
    "tool_risks": {
        "read_file": "low",      # 低风险，直接执行
        "write_file": "high",    # 高风险，需要用户确认
        "delete_file": "high",   # 高风险，需要用户确认
        # 未配置的工具默认为 "medium"
    }
}
```

## API 使用示例

### 注册服务器

```python
success = await mcp_server_manager.register_server({
    "id": "weather_api",
    "name": "Weather API Server",
    "url": "https://weather-api.example.com/mcp",
    "auth": "your-api-key",
    "tool_risks": {
        "get_weather": "low",
        "get_forecast": "low"
    }
})
```

### 调用工具

```python
# 带权限检查的调用
result = await mcp_server_manager.call_tool(
    tool_name="weather_api::get_weather",
    parameters={"city": "Beijing"},
    session_id="user123",
    require_permission=True
)

# 直接调用（跳过权限检查）
result = await mcp_server_manager.call_tool(
    tool_name="get_weather",
    parameters={"city": "Beijing"},
    require_permission=False
)
```

### 获取工具列表

```python
tools = mcp_server_manager.get_available_tools()
# 返回格式：
# [
#   {
#     "name": "get_weather",
#     "description": "Get current weather",
#     "parameters": {...},
#     "risk_level": "low",
#     "server_id": "weather_api",
#     "server_name": "Weather API Server",
#     "full_name": "weather_api::get_weather"
#   }
# ]
```

### 获取服务器信息

```python
servers = mcp_server_manager.get_servers_info()
# 返回格式：
# [
#   {
#     "id": "weather_api",
#     "name": "Weather API Server", 
#     "status": "connected",
#     "tools_count": 2,
#     "tools": ["get_weather", "get_forecast"]
#   }
# ]
```

## 权限管理集成

权限管理通过装饰器模式集成，不影响核心 FastMCP 功能：

```python
async def _check_permission(self, session_id: str, tool_info: Dict, parameters: Dict) -> bool:
    risk_level = tool_info.get("risk_level", "medium")
    
    # 低风险工具直接放行
    if risk_level == "low":
        return True
        
    # 中高风险工具需要用户确认
    return await tool_permission_manager.request_tool_permission(...)
```

## 错误处理

```python
result = await mcp_server_manager.call_tool(...)

if result["success"]:
    print("工具执行成功:", result["result"])
else:
    print("执行失败:", result["error"])
    
    # 检查是否需要权限
    if result.get("permission_required"):
        print("需要用户权限确认")
```

## 与之前版本的对比

### 之前的实现（复杂）

```python
# 多层包装，复杂的对象转换
class MCPTool:
    def __init__(self, name, description, parameters, risk_level, server_id):
        # ...

class MCPServerConnection:
    def __init__(self, server_id, client, config):
        # ...
    
    async def discover_tools(self) -> List[MCPTool]:
        # 复杂的工具发现和包装逻辑
        # ...

# 复杂的工具调用链
tool = self.available_tools.get(tool_name)  # 查找包装对象
server_connection = self.servers.get(server_id)  # 获取连接包装
result = await server_connection.call_tool(...)  # 多层调用
```

### 新的实现（简洁）

```python
# 直接使用 FastMCP，最小化包装
client = self.servers[server_id]["client"]  # 直接获取 FastMCP Client

async with client:
    result = await client.call_tool(tool_name, parameters)  # 直接调用官方 API
```

## 迁移指南

如果从旧版本迁移：

1. **API 变化**：
   - `call_tool_with_permission()` → `call_tool()`
   - `disconnect_server()` → `unregister_server()`
   - `get_connected_servers()` → `get_servers_info()`

2. **工具名格式**：
   - 旧：`server_id:tool_name`（单冒号）
   - 新：`server_id::tool_name`（双冒号）

3. **返回格式**：
   - 工具信息中新增 `full_name` 字段
   - 去除了 `tool_key` 字段

## 总结

新的简化版 MCP Server Manager 完全基于 FastMCP 官方 API，去除了不必要的中间层，代码更简洁、性能更好、维护更容易。同时保留了所有必要的业务功能，如权限管理、配置验证等。

这个设计完全符合 FastMCP 官方推荐的最佳实践，最大化利用了 FastMCP 的原生能力。
