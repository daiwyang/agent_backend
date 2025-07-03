# Response Format 错误修复

## 问题描述

用户报告了以下错误：
```
Error: ValueError("Since response_format='content_and_artifact' a two-tuple of the message content and raw tool output is expected. Instead generated response of type: <class 'str'>.")
```

## 根本原因

LangGraph框架期望工具返回一个二元组格式 `(content, raw_output)`，这是因为配置了 `response_format='content_and_artifact'`。但我们的MCPToolWrapper中的工具只返回了字符串格式。

## 修复方案

### 1. 修改MCPToolWrapper的返回格式

在 `copilot/core/mcp_tool_wrapper.py` 中，将所有工具返回语句从字符串格式改为二元组格式：

#### 成功执行
```python
# 修复前
return ToolResultProcessor.format_for_user(tool.name, raw_result)

# 修复后
formatted_result = ToolResultProcessor.format_for_user(tool.name, raw_result)
return (formatted_result, raw_result)
```

#### 权限等待
```python
# 修复前
return f"🔒 等待用户确认执行工具: {tool.name}"

# 修复后
message = f"🔒 等待用户确认执行工具: {tool.name}"
return (message, {"status": "permission_required", "tool_name": tool.name})
```

#### 执行失败
```python
# 修复前
return f"工具 {tool.name} 执行失败: {str(error)}"

# 修复后
error_message = f"工具 {tool.name} 执行失败: {str(error)}"
return (error_message, {"status": "error", "error": str(error)})
```

### 2. 二元组格式说明

- **第一个元素（content）**：用户友好的显示消息
- **第二个元素（artifact）**：原始数据或结构化状态信息

## 测试验证

创建了测试脚本验证修复效果：

```python
# 验证二元组格式
tuple_result = (formatted_result, raw_result)
content, artifact = tuple_result  # 可以正常解包
```

测试结果：
- ✅ 成功执行返回格式正确
- ✅ 错误响应返回格式正确  
- ✅ 权限确认返回格式正确

## 影响范围

- `copilot/core/mcp_tool_wrapper.py` - 主要修复文件
- 所有MCP工具调用现在都符合LangGraph的期望格式
- 不影响StreamNotifier中的内部处理逻辑

## 结果

修复后，工具调用不再出现 `response_format='content_and_artifact'` 错误，系统可以正常处理工具权限确认和执行流程。 