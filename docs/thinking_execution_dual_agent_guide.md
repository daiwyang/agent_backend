# 思考-执行双Agent系统使用指南

## 系统概述

思考-执行双Agent系统是一个创新的AI架构，将用户请求的处理分为两个独立但协作的阶段：

1. **思考阶段 (ThinkingAgent)** - 专门负责理解用户意图、分析问题、制定详细的执行计划
2. **执行阶段 (ExecutionAgent)** - 根据思考阶段的计划，专注于执行具体的工具调用和任务处理

这种分离式设计带来了更好的可控性、可调试性，并且可以针对不同阶段使用不同的模型以优化性能和成本。

## 系统架构

```
用户输入
    ↓
ThinkingAgent (思考Agent)
    - 分析用户意图
    - 制定执行计划
    - 选择合适的工具
    ↓
AgentCoordinator (协调器)
    - 管理两个Agent的交互
    - 处理流式输出
    - 记录思考过程
    ↓
ExecutionAgent (执行Agent)
    - 根据计划执行任务
    - 调用具体工具
    - 生成最终结果
    ↓
用户响应
```

## 核心组件

### 1. ThinkingAgent (思考Agent)

**职责：**
- 解读用户输入，理解真实意图
- 分析问题复杂度和处理方式
- 制定详细的执行步骤计划
- 建议合适的工具和参数
- 不执行实际操作，只进行思考和规划

**特性：**
- 使用推理能力强的模型（默认：deepseek-chat）
- 生成结构化的执行计划
- 支持计划优化和反馈改进
- 考虑步骤依赖关系和优先级

### 2. ExecutionAgent (执行Agent)

**职责：**
- 接收思考Agent的规划结果
- 根据规划执行具体的工具调用
- 处理实际的任务执行
- 输出最终结果给用户

**特性：**
- 可以使用高效的执行模型
- 支持所有现有的工具和功能
- 维持上下文记忆功能
- 完整的流式输出

### 3. AgentCoordinator (协调器)

**职责：**
- 管理两个Agent的协作流程
- 处理思考到执行的数据传递
- 记录和管理思考历史
- 支持计划优化和重试机制

**特性：**
- 灵活的模式切换（思考模式/直接模式）
- 完整的错误处理和恢复
- 思考过程的存储和查询
- 性能监控和统计

## 配置选项

### 全局配置

```python
# 在ChatService创建时配置
chat_service = await ChatService.create(
    # 执行Agent配置
    provider="deepseek",
    model_name="deepseek-chat",
    
    # 思考模式配置
    thinking_mode_enabled=True,
    thinking_provider="deepseek", 
    thinking_model="deepseek-chat",
    save_thinking_process=True,
    
    # 上下文记忆配置
    context_memory_enabled=True,
    max_history_messages=10,
    max_context_tokens=120000
)
```

### 运行时配置

```python
# 动态切换思考模式
chat_service.configure_thinking_mode(
    enabled=True,
    thinking_provider="deepseek",
    thinking_model="deepseek-chat",
    save_thinking_process=True
)

# 获取当前配置
config = chat_service.get_thinking_mode_config()
```

## API接口文档

### 1. 配置管理接口（集成到现有API）

#### 获取配置信息
```http
GET /chat/context-memory/config
```

**响应：**
```json
{
    "message": "配置信息",
    "config": {
        "context_memory": {
            "context_memory_enabled": true,
            "max_history_messages": 10,
            "max_context_tokens": 120000
        },
        "thinking_mode": {
            "thinking_mode_enabled": true,
            "thinking_provider": "deepseek",
            "thinking_model": "deepseek-chat",
            "save_thinking_process": true,
            "cached_coordinators": 5
        }
    }
}
```

#### 配置系统设置
```http
POST /chat/context-memory/configure
Content-Type: application/json

{
    "enabled": true,
    "max_history_messages": 10,
    "thinking_mode_enabled": true,
    "thinking_provider": "deepseek",
    "thinking_model": "deepseek-chat",
    "save_thinking_process": true
}
```

### 2. 会话信息接口（集成到现有API）

#### 获取会话Agent信息
```http
GET /chat/sessions/{session_id}/agent-info
```

**响应：**
```json
{
    "session_id": "session_123",
    "agent_info": {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "context_memory": {
            "context_memory_enabled": true,
            "max_history_messages": 10,
            "actual_history_count": 5
        },
        "thinking_mode": {
            "session_id": "session_123",
            "thinking_mode_enabled": true,
            "thinking_provider": "deepseek",
            "thinking_model": "deepseek-chat",
            "has_coordinator": true,
            "thinking_history_count": 3,
            "latest_thinking": {
                "user_intent": "用户想要创建一个Python脚本",
                "estimated_complexity": "medium",
                "execution_plan_steps": 4,
                "timestamp": "2024-01-15T10:30:00"
            }
        },
        "provider_info": {...}
    }
}
```

### 3. 聊天接口（无缝集成思考模式）

#### 智能聊天接口
```http
POST /chat/chat
Content-Type: application/json

{
    "session_id": "session_123",
    "message": "帮我创建一个Python计算器",
    "enable_mcp_tools": true,
    "attachments": [],
    "use_thinking_mode": true  // 可选，true=启用思考模式，false=直接模式，null=使用默认配置
}
```

**流式响应阶段：**

1. **思考阶段输出（当use_thinking_mode=true时）：**
```json
{"type": "thinking_start", "content": "🤔 正在分析您的需求...", "phase": "thinking"}
{"type": "thinking_result", "content": "💭 **分析结果**\n\n**用户意图**: 创建Python计算器...", "phase": "thinking"}
```

2. **执行阶段输出：**
```json
{"type": "execution_start", "content": "⚡ 开始执行任务...", "phase": "execution"}
{"type": "content", "content": "我将为您创建一个Python计算器...", "phase": "execution"}
```

3. **完成响应：**
```json
{
    "finished": true,
    "token_usage": {"total_tokens": 1500},
    "message_ids": {"user_message_id": "msg_1", "assistant_message_id": "msg_2"},
    "thinking_enabled": true,
    "phases_completed": {"thinking": true, "execution": true}
}
```

## 使用示例

### 1. Python SDK使用

```python
import asyncio
from copilot.service.chat_service import ChatService

async def main():
    # 配置系统设置（包括思考模式）
    chat_service = await ChatService.create()
    await chat_service.configure_context_memory(enabled=True, max_history_messages=10)
    await chat_service.configure_thinking_mode(
        enabled=True,
        thinking_provider="deepseek",
        thinking_model="deepseek-chat"
    )
    
    # 创建会话
    session_id = await chat_service.create_session("user_123")
    
    # 进行智能聊天（支持思考模式切换）
    async for chunk in chat_service.chat(
        session_id=session_id,
        message="帮我分析这个数据集并创建可视化图表",
        enable_tools=True,
        use_thinking_mode=True  # 明确启用思考模式
    ):
        if chunk.get("phase") == "thinking":
            print(f"[思考] {chunk.get('content')}")
        elif chunk.get("phase") == "execution":
            print(f"[执行] {chunk.get('content')}")
        elif chunk.get("finished"):
            print(f"完成！总计使用 {chunk.get('total_tokens')} tokens")

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. HTTP API使用

```javascript
// 配置系统设置（集成API）
async function configureSystem() {
    const response = await fetch('/chat/context-memory/configure', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            enabled: true,
            max_history_messages: 10,
            thinking_mode_enabled: true,
            thinking_provider: "deepseek",
            thinking_model: "deepseek-chat",
            save_thinking_process: true
        })
    });
    return response.json();
}

// 进行智能聊天（支持思考模式切换）
async function chatWithSmartMode(sessionId, message, useThinkingMode = true) {
    const response = await fetch('/chat/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            session_id: sessionId,
            message: message,
            enable_mcp_tools: true,
            use_thinking_mode: useThinkingMode  // 控制思考模式
        })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = JSON.parse(decoder.decode(value));
        
        if (chunk.phase === 'thinking') {
            console.log('🤔 思考中:', chunk.content);
        } else if (chunk.phase === 'execution') {
            console.log('⚡ 执行中:', chunk.content);
        } else if (chunk.finished) {
            console.log('✅ 完成，用时:', chunk.total_tokens, 'tokens');
        }
    }
}

// 获取会话详细信息（包括思考信息）
async function getSessionDetails(sessionId) {
    const response = await fetch(`/chat/sessions/${sessionId}/agent-info`);
    const data = await response.json();
    
    console.log('会话信息:', data.agent_info);
    console.log('思考模式状态:', data.agent_info.thinking_mode);
    return data;
}
```

## 最佳实践

### 1. 模型选择建议

**思考Agent：**
- 推荐使用推理能力强的模型：`deepseek-chat`, `gpt-4`, `claude-3.5-sonnet`
- 适当提高temperature以获得更多创造性思考

**执行Agent：**
- 可以使用高效的执行模型：`deepseek-chat`, `gpt-3.5-turbo`
- 或与思考Agent使用相同模型以保持一致性

### 2. 性能优化

```python
# 根据任务复杂度动态切换模式
async def smart_chat(session_id, message, complexity="auto"):
    if complexity == "simple":
        # 简单任务直接执行
        use_thinking = False
    elif complexity == "complex":
        # 复杂任务使用思考模式
        use_thinking = True
    else:
        # 自动判断（默认启用思考模式）
        use_thinking = True
    
    async for chunk in chat_service.chat(
        session_id=session_id,
        message=message,
        use_thinking_mode=use_thinking
    ):
        yield chunk
```

### 3. 错误处理和重试

```python
async def robust_chat_with_retry(session_id, message, max_retries=2):
    for attempt in range(max_retries + 1):
        try:
            async for chunk in chat_service.chat(
                session_id=session_id, 
                message=message,
                use_thinking_mode=True  # 启用思考模式以获得更好的错误处理
            ):
                yield chunk
            break
        except Exception as e:
            if attempt < max_retries:
                # 重新尝试，可能调整思考模式
                logger.warning(f"尝试 {attempt + 1} 失败: {str(e)}")
                # 下次尝试使用更强的思考模式
                continue
            else:
                raise
```

### 4. 智能模式切换

```python
# 根据任务复杂度智能选择模式
async def adaptive_chat(session_id, message):
    # 简单的启发式规则判断任务复杂度
    complex_keywords = ["创建", "编程", "分析", "设计", "实现", "开发"]
    simple_keywords = ["什么是", "解释", "定义", "介绍"]
    
    if any(keyword in message for keyword in complex_keywords):
        use_thinking = True
        print("🧠 检测到复杂任务，启用思考模式")
    elif any(keyword in message for keyword in simple_keywords):
        use_thinking = False
        print("⚡ 检测到简单问题，使用直接模式")
    else:
        use_thinking = None  # 使用默认配置
        print("🔄 使用默认模式")
    
    async for chunk in chat_service.chat(
        session_id=session_id,
        message=message,
        use_thinking_mode=use_thinking
    ):
        yield chunk
```

## 监控和调试

### 1. 性能监控

```python
# 获取系统统计信息
async def get_system_stats():
    stats = {}
    for session_id in active_sessions:
        # 获取会话详细信息
        agent_info = await chat_service.get_session_agent_info(session_id)
        thinking_info = agent_info.get("thinking_mode", {})
        
        stats[session_id] = {
            "thinking_enabled": thinking_info.get("thinking_mode_enabled", False),
            "thinking_history_count": thinking_info.get("thinking_history_count", 0),
            "has_coordinator": thinking_info.get("has_coordinator", False)
        }
    return stats
```

### 2. 日志分析

系统会输出详细的日志信息：

```
[CHAT] 对话开始 [Session: session_123] ==================================================
[CHAT] 用户提问 [Session: session_123]: 帮我创建一个Python计算器
[ThinkingAgent] 开始分析用户输入: 帮我创建一个Python计算器...
[ThinkingAgent] 完成分析，生成了4个执行步骤
[AgentCoordinator] 思考模式处理完成，开始执行
[ExecutionAgent] 根据思考结果执行任务...
[CHAT] 任务完成 [Session: session_123] ==================================================
```

### 3. 故障排除

**常见问题：**

1. **思考Agent初始化失败**
   - 检查thinking_provider和thinking_model配置
   - 确认模型访问权限和配额
   - 通过`/chat/context-memory/config`获取当前配置

2. **协调器缓存问题**
   - 重启服务会自动清理协调器缓存
   - 检查会话状态和内存使用
   - 使用`/chat/sessions/{session_id}/agent-info`查看会话状态

3. **执行阶段错误**
   - 查看思考结果是否合理
   - 尝试切换到直接模式: `use_thinking_mode: false`
   - 调整thinking_model为更强的模型

## 配置参数详解

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `thinking_mode_enabled` | bool | true | 是否启用思考模式 |
| `thinking_provider` | str | "deepseek" | 思考Agent的LLM提供商 |
| `thinking_model` | str | "deepseek-chat" | 思考Agent的模型名称 |
| `save_thinking_process` | bool | true | 是否保存思考过程 |
| `context_memory_enabled` | bool | true | 执行Agent是否启用上下文记忆 |
| `max_history_messages` | int | 10 | 最大历史消息数量 |
| `max_context_tokens` | int | 120000 | 最大上下文token数量 |

## 更新日志

### v1.0.0 (2024-01-15)
- 实现基础的思考-执行双Agent架构
- 支持思考过程记录和查询
- 提供完整的API接口
- 集成现有的上下文记忆功能
- 支持计划优化和重试机制

---

## 技术支持

如有问题或建议，请联系开发团队或提交Issue。

**系统要求：**
- Python 3.8+
- FastAPI框架
- 支持的LLM提供商账号
- MongoDB和Redis（用于数据存储）

**相关文档：**
- [Agent上下文记忆指南](./agent_context_memory_guide.md)
- [多LLM提供商指南](./multi_llm_guide.md)
- [MCP工具集成指南](./mcp_tool_integration_fix.md) 