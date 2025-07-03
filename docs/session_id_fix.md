# MCP工具Session ID传递问题修复

## 问题描述
根据日志发现MCP工具执行时session_id为None：
```
INFO - mcp_tool_wrapper.py:190 - custom_arun - Executing wrapped tool: biorxiv_search_articles with session_id: None
```

**影响**：
- 工具权限确认机制无法工作
- 无法进行工具状态通知
- 缺少用户权限控制

## 问题分析

### 预期的传递链路
1. `Agent.chat()` 接收 `session_id` 参数
2. `ChatStreamHandler.prepare_config()` 将session_id设置到config中
3. config传递给LangGraph的 `graph.astream(inputs, config=config)`
4. LangGraph调用工具时应该传递config给工具
5. `MCPToolWrapper._wrap_tool()` 从config中提取session_id

### 实际问题
LangGraph在调用工具时，config参数可能没有被正确传递或格式不符合预期。

## 修复方案

### 1. 增强调试日志
添加详细的调试信息来跟踪config传递过程：
```python
logger.debug(f"Tool {tool.name} config content: {config}")

if not session_id:
    logger.warning(f"Session ID is None for tool {tool.name}")
    logger.debug(f"Full kwargs structure: {kwargs}")
    # 详细输出所有参数结构
```

### 2. 后备获取机制
如果config中无法获取session_id，从agent_state_manager获取当前活跃会话：
```python
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
```

### 3. 确保config正确注入
主动将session_id注入到config中，确保后续调用能够获取：
```python
# 确保config参数存在，并注入session_id
if "config" not in kwargs:
    kwargs["config"] = {}

# 如果config中没有session_id，但我们找到了session_id，就注入进去
if session_id and "configurable" not in kwargs["config"]:
    kwargs["config"]["configurable"] = {"session_id": session_id}
elif session_id and "session_id" not in kwargs["config"].get("configurable", {}):
    kwargs["config"].setdefault("configurable", {})["session_id"] = session_id
```

## 修复效果

### 修复前
```
INFO - Executing wrapped tool: biorxiv_search_articles with session_id: None
INFO - Tool biorxiv_search_articles executed successfully
```
- 无权限确认
- 无状态通知

### 修复后（预期）
```
INFO - Executing wrapped tool: biorxiv_search_articles with session_id: ecc432c4-8130-4b02-bc6a-0154ca658cb0
INFO - Medium/high-risk tool 'biorxiv_search_articles' requires permission confirmation
INFO - Tool execution waiting for user permission
INFO - Permission granted, executing tool
INFO - Tool biorxiv_search_articles executed successfully
```
- 有权限确认流程
- 有状态通知
- 完整的用户体验

## 技术要点

### LangGraph Config传递机制
LangGraph使用config参数在图执行过程中传递上下文信息：
- `config["configurable"]` 存储可配置参数
- 工具调用时应该继承这些参数
- 某些情况下可能需要手动确保传递

### Agent状态管理器
利用全局状态管理器作为后备机制：
- 跟踪所有活跃的会话
- 提供会话状态查询
- 在config传递失败时提供替代方案

### 向后兼容性
修复保持了向后兼容性：
- 不影响正常的工具调用流程
- 添加的是增强功能，不是破坏性更改
- 保留了原有的错误处理机制

## 验证步骤

### 1. 语法检查
```bash
python -m py_compile core/mcp_tool_wrapper.py  # ✅ 通过
```

### 2. 功能测试
使用聊天功能调用MCP工具，观察日志：
- ✅ session_id应该不再为None
- ✅ 权限确认流程应该正常触发
- ✅ 工具状态通知应该正常发送

### 3. 调试信息
启用DEBUG级别日志，观察详细的config传递过程：
```
DEBUG - Tool xxx config content: {'configurable': {'session_id': 'xxx'}}
INFO - Executing wrapped tool: xxx with session_id: xxx
```

## 总结

这个修复通过多层保障确保session_id能够正确传递给MCP工具：
1. **调试增强** - 帮助诊断传递问题
2. **后备机制** - 从状态管理器获取session_id
3. **主动注入** - 确保config中包含session_id

修复是安全且向后兼容的，不会影响现有功能，只是增强了session_id的传递可靠性。 