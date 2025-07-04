# StreamNotifier UnboundLocalError 修复总结

## 问题描述

在工具执行过程中，系统出现了 `UnboundLocalError` 错误：

```
UnboundLocalError("cannot access local variable 'StreamNotifier' where it is not associated with a value")
```

这个错误导致工具无法正常执行，并且会在超时测试过程中反复出现。

## 问题原因

在 `copilot/core/mcp_tool_wrapper.py` 文件中，存在以下问题：

1. **重复导入问题**：
   - 文件顶部有全局导入：`from copilot.core.stream_notifier import StreamNotifier`
   - 在 `custom_arun` 函数内部又有本地导入：`from copilot.core.stream_notifier import StreamNotifier`

2. **Python 变量作用域规则**：
   - 当 Python 解释器在函数内部看到 `from ... import StreamNotifier` 时，会将 `StreamNotifier` 视为本地变量
   - 但在执行本地导入语句之前，如果代码尝试访问 `StreamNotifier`，就会抛出 `UnboundLocalError`

## 修复方案

移除函数内部的重复导入语句，依赖文件顶部的全局导入：

### 修复前的代码

```python
# 发送权限请求和等待状态通知，获取request_id
request_id = None
if session_id:
    # 发送权限请求，获取唯一的request_id
    from copilot.core.stream_notifier import StreamNotifier  # ❌ 重复导入

    request_id = await StreamNotifier.send_tool_permission_request(
        session_id=session_id, tool_name=tool.name, parameters=display_params, risk_level=risk_level
    )
```

### 修复后的代码

```python
# 发送权限请求和等待状态通知，获取request_id
request_id = None
if session_id:
    # 发送权限请求，获取唯一的request_id
    request_id = await StreamNotifier.send_tool_permission_request(
        session_id=session_id, tool_name=tool.name, parameters=display_params, risk_level=risk_level
    )
```

## 修复验证

创建了专门的测试文件 `tests/test_streamnotifier_fix.py` 来验证修复效果：

1. **高风险工具测试**：验证需要权限确认的工具能正常访问 `StreamNotifier`
2. **低风险工具测试**：验证直接执行的工具能正常访问 `StreamNotifier`

测试结果：

- ✅ StreamNotifier UnboundLocalError 修复成功!
- ✅ 低风险工具 StreamNotifier 访问正常!

## 影响范围

此修复影响所有使用 MCP 工具的功能：

- **权限确认流程**：现在能正常发送权限请求和状态通知
- **工具执行状态**：现在能正常通知工具执行状态
- **超时处理**：30秒超时测试现在能正常工作

## 技术细节

1. **Python 作用域规则**：函数内部的 `import` 语句会将导入的名称视为本地变量
2. **最佳实践**：避免在函数内部重复导入已在模块顶部导入的名称
3. **调试技巧**：`UnboundLocalError` 通常意味着变量在赋值前被使用，或者存在作用域问题

## 修复文件

- `copilot/core/mcp_tool_wrapper.py`：移除重复导入
- `tests/test_streamnotifier_fix.py`：添加验证测试

## 结论

通过移除重复的本地导入语句，成功解决了 `StreamNotifier` 的 `UnboundLocalError` 问题。现在所有工具都能正常执行，权限确认流程也能正常工作。

这是一个典型的 Python 作用域问题，修复后系统的稳定性和可靠性得到了显著提升。
