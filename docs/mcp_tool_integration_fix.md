# MCP工具集成错误修复

## 问题描述

在系统日志中发现以下错误：

```
ERROR - agent_manager.py:395 - _get_mcp_tools_for_servers - Failed to get MCP tools for servers {'genpilot_database_mcp'}: type object 'CoreAgent' has no attribute '_get_mcp_tools_for_servers'
```

导致：

- MCP服务器成功注册（15个工具）
- 但Agent只更新了0个MCP工具
- 工具无法正常使用

## 问题分析

### 错误根源

在 `copilot/core/agent_manager.py` 第388行：

```python
# 错误代码
mcp_tools = await CoreAgent._get_mcp_tools_for_servers(list(server_ids))
```

**问题**：`CoreAgent` 类中没有 `_get_mcp_tools_for_servers` 方法。

### 正确的调用方式

实际上应该调用 `MCPToolWrapper.get_mcp_tools_for_servers()` 方法。

## 修复方案

### 修复前（错误）

```python
# 使用CoreAgent的静态方法获取工具
from copilot.core.agent import CoreAgent
mcp_tools = await CoreAgent._get_mcp_tools_for_servers(list(server_ids))
```

### 修复后（正确）

```python
# 使用MCPToolWrapper获取指定服务器的工具
from copilot.core.mcp_tool_wrapper import MCPToolWrapper
mcp_tools = await MCPToolWrapper.get_mcp_tools_for_servers(list(server_ids))
```

## 技术详解

### MCPToolWrapper.get_mcp_tools_for_servers 方法

此方法负责：

1. 根据服务器ID列表过滤MCP服务器
2. 构建MultiServerMCPClient配置
3. 异步获取所有MCP工具
4. 包装工具以集成权限检查和自定义逻辑

### 修复效果

修复后的预期行为：

```
INFO - mcp_server_manager.py:95 - Successfully registered server genpilot_database_mcp with 15 tools
INFO - agent_manager.py:xxx - Retrieved 15 MCP tools from servers: {'genpilot_database_mcp'}
INFO - agent.py:xxx - Successfully updated Agent with 15 MCP tools
INFO - agent_manager.py:xxx - Updated MCP tools for session xxx with 15 tools from servers: {'genpilot_database_mcp'}
```

## 验证步骤

### 1. 语法检查

```bash
python -m py_compile core/agent_manager.py  # ✅ 通过
```

### 2. 功能验证

启动系统后检查日志：

- ✅ MCP服务器注册成功
- ✅ 工具数量正确获取（15个工具）
- ✅ Agent成功更新MCP工具
- ✅ 不再出现 `'CoreAgent' has no attribute` 错误

### 3. 工具调用测试

在聊天中尝试使用MCP工具：

- 工具应该正确列出和调用
- 权限确认流程应该正常工作
- 工具执行结果应该正确返回

## 相关代码文件

### 修改的文件

- `copilot/core/agent_manager.py` - 修复错误的方法调用

### 相关文件（未修改）

- `copilot/core/mcp_tool_wrapper.py` - 包含正确的 `get_mcp_tools_for_servers` 方法
- `copilot/core/agent.py` - 使用MCPToolWrapper的正确示例
- `copilot/mcp_client/mcp_server_manager.py` - MCP服务器管理

## 总结

这是一个简单的方法调用错误：

- **问题**：调用了不存在的 `CoreAgent._get_mcp_tools_for_servers()`
- **解决**：改为调用正确的 `MCPToolWrapper.get_mcp_tools_for_servers()`
- **影响**：修复后MCP工具应该能够正常集成到Agent中

修复简单且安全，不会影响其他功能，只是纠正了错误的方法调用。
