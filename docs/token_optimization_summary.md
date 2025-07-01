"""
Token优化方案总结
================

## 🎯 优化目标

1. **解决_estimate_token_usage方法缺失问题**
2. **简化token获取和处理逻辑**
3. **统一token数据结构**
4. **增强错误处理机制**

## 🔧 优化方案

### 1. 创建TokenCalculator工具类 (`utils/token_calculator.py`)

**核心功能：**

- ✅ 基于字符数的简单token估算
- ✅ 支持不同模型的token率
- ✅ 中文文本特殊处理
- ✅ 安全的数据提取
- ✅ 完善的错误处理

**TokenUsage数据类：**

```python
@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
```

### 2. 在CoreAgent中添加token估算方法

**新增方法：**

- `_estimate_token_usage()`: 解决方法缺失问题
- `get_token_calculator()`:  获取计算器实例

### 3. 简化ChatService中的token处理

**优化前的问题：**

- ❌ 重复的token提取逻辑
- ❌ 两个相似的保存方法
- ❌ 缺乏错误处理

**优化后：**

- ✅ 统一的`_save_conversation()`方法
- ✅ 安全的token数据提取
- ✅ 保持向后兼容性

## 📊 优化效果

### 1. 代码简化

**优化前：**

```python
# 在多个地方重复提取token
user_token_count = token_usage.get("prompt_tokens", 0) if token_usage else 0
assistant_token_count = token_usage.get("completion_tokens", 0) if token_usage else 0
total_tokens = token_usage.get("total_tokens", 0) if token_usage else 0
```

**优化后：**

```python
# 统一安全提取
usage = TokenCalculator.safe_extract_tokens(token_usage)
```

### 2. 错误处理

**优化前：**

- 可能因为token_usage为None而出错
- 缺少对异常情况的处理

**优化后：**

- 安全的数据提取，自动处理None情况
- 完善的异常处理和降级机制

### 3. 可维护性

**优化前：**

- 代码重复，修改需要多处更新
- 缺少统一的token计算逻辑

**优化后：**

- 单一责任原则，token计算集中管理
- 易于扩展和维护

## 🚀 使用示例

### 简单token估算

```python
from copilot.utils.token_calculator import TokenCalculator

# 估算单个文本的token数量
tokens = TokenCalculator.estimate_tokens("Hello World", "gpt-4")

# 计算完整对话的token使用量
usage = TokenCalculator.calculate_usage(prompt, completion, "deepseek")
print(f"总计: {usage.total_tokens} tokens")
```

### 在ChatService中使用

```python
# 自动调用优化后的方法
token_usage = self.core_agent._estimate_token_usage(message, response)
await self._save_conversation(session_id, message, response, token_usage)
```

## 🔍 性能特点

- **快速**: 基于字符数估算，无需调用外部API
- **准确**: 针对不同模型和语言优化
- **安全**: 完善的错误处理，不会导致系统崩溃
- **兼容**: 保持原有API接口不变

## 📈 模型支持

| 提供商 | 模型标识 | Token率 | 特殊处理 |
|--------|----------|---------|----------|
| OpenAI | gpt-4/gpt-3.5 | 4.0 | 标准处理 |
| DeepSeek | deepseek | 3.5 | 中文优化 |
| Claude | claude | 4.5 | 标准处理 |
| Qwen | qwen | 2.0 | 中文优化 |
| 智谱 | zhipu | 2.5 | 中文优化 |
| Moonshot | moonshot | 3.0 | 中文优化 |
| Gemini | gemini | 4.0 | 标准处理 |

## ✅ 测试验证

运行测试：

```bash
cd /data/agent_backend
python tests/test_token_optimization.py
```

所有功能已通过测试验证！

## 📊 交互流程图

### 1. 整体Token计算流程

```mermaid
flowchart TD
    A[用户发送消息] --> B[ChatService.chat()]
    B --> C[CoreAgent处理消息]
    C --> D[LLM生成回复]
    D --> E[CoreAgent._estimate_token_usage()]
    E --> F[TokenCalculator.get_model_key()]
    F --> G[TokenCalculator.calculate_usage()]
    G --> H[返回TokenUsage对象]
    H --> I[ChatService._save_conversation()]
    I --> J[保存到数据库和缓存]
    
    %% 样式定义
    classDef userAction fill:#e1f5fe
    classDef service fill:#f3e5f5
    classDef calculator fill:#e8f5e8
    classDef storage fill:#fff3e0
    
    class A userAction
    class B,C,I service
    class E,F,G,H calculator
    class J storage
```

### 2. TokenCalculator详细处理流程

```mermaid
flowchart TD
    A[开始Token估算] --> B{文本是否为空?}
    B -->|是| C[返回0]
    B -->|否| D[获取字符数量]
    D --> E[根据模型获取Token率]
    E --> F[基础Token估算: 字符数/Token率]
    F --> G{包含中文字符?}
    G -->|是| H[计算中文比例]
    G -->|否| I[返回基础估算]
    H --> J[应用中文调整因子: +50%]
    J --> K[返回调整后Token数]
    
    %% 异常处理路径
    L[异常发生] --> M[记录警告日志]
    M --> N[降级处理: 字符数/4]
    
    %% 样式定义
    classDef process fill:#e3f2fd
    classDef decision fill:#fff3e0
    classDef result fill:#e8f5e8
    classDef error fill:#ffebee
    
    class A,D,E,F,H,J process
    class B,G decision
    class C,I,K result
    class L,M,N error
```

### 3. 数据流转关系图

```mermaid
sequenceDiagram
    participant U as 用户
    participant CS as ChatService
    participant CA as CoreAgent
    participant TC as TokenCalculator
    participant DB as 数据库/缓存
    
    U->>CS: 发送消息
    CS->>CA: 调用chat方法
    CA->>CA: 处理消息并生成回复
    CA->>TC: _estimate_token_usage(prompt, completion)
    
    Note over TC: Token计算过程
    TC->>TC: get_model_key(provider, model)
    TC->>TC: estimate_tokens(prompt, model_key)
    TC->>TC: estimate_tokens(completion, model_key)
    TC->>TC: 创建TokenUsage对象
    
    TC-->>CA: 返回token使用量字典
    CA-->>CS: 返回完整响应
    CS->>CS: _save_conversation()
    CS->>TC: safe_extract_tokens(token_data)
    TC-->>CS: 返回TokenUsage对象
    CS->>DB: 保存消息和Token统计
    CS-->>U: 返回聊天响应
```

### 4. 错误处理机制

```mermaid
flowchart TD
    A[Token计算开始] --> B{输入验证}
    B -->|失败| C[记录警告日志]
    C --> D[返回默认TokenUsage]
    
    B -->|成功| E[执行Token估算]
    E --> F{估算是否成功?}
    F -->|失败| G[捕获异常]
    G --> H[记录错误日志]
    H --> I[执行降级策略]
    I --> J[字符数/4的简单估算]
    J --> K[返回最小安全值]
    
    F -->|成功| L[返回准确估算]
    
    %% 样式定义
    classDef normal fill:#e3f2fd
    classDef error fill:#ffebee
    classDef fallback fill:#fff8e1
    classDef success fill:#e8f5e8
    
    class A,B,E,F normal
    class C,G,H error
    class D,I,J,K fallback
    class L success
```

### 5. 模型适配策略

```mermaid
flowchart TD
    A[获取模型信息] --> B{model_name存在?}
    B -->|是| C[按model_name匹配]
    B -->|否| D[按provider匹配]
    
    C --> E{匹配成功?}
    E -->|是| F[返回对应Token率]
    E -->|否| G[使用provider匹配]
    
    D --> H{provider匹配?}
    H -->|是| F
    H -->|否| I[使用默认Token率: 4.0]
    
    G --> H
    
    %% Token率说明
    J[Token率配置]
    J --> K[OpenAI: 4.0]
    J --> L[DeepSeek: 3.5]
    J --> M[Qwen: 2.0]
    J --> N[智谱: 2.5]
    J --> O[其他: 4.0]
    
    %% 样式定义
    classDef decision fill:#fff3e0
    classDef process fill:#e3f2fd
    classDef config fill:#f3e5f5
    classDef result fill:#e8f5e8
    
    class B,E,H decision
    class A,C,D,G process
    class J,K,L,M,N,O config
    class F,I result
```

### 6. 优化前后对比流程

```mermaid
graph TB
    subgraph "优化前"
        A1[多处重复Token提取] --> B1[容易出现None错误]
        B1 --> C1[缺少统一处理逻辑]
        C1 --> D1[维护困难]
    end
    
    subgraph "优化后"
        A2[统一TokenCalculator] --> B2[安全的数据提取]
        B2 --> C2[完善的错误处理]
        C2 --> D2[易于维护和扩展]
    end
    
    %% 样式定义
    classDef old fill:#ffebee
    classDef new fill:#e8f5e8
    
    class A1,B1,C1,D1 old
    class A2,B2,C2,D2 new
```

## 💡 关键优化点

### 1. **统一入口**

- 所有Token计算都通过`TokenCalculator`类
- 避免代码重复和不一致

### 2. **安全处理**

- `safe_extract_tokens()`确保数据安全
- 降级策略保证系统稳定性

### 3. **模型适配**

- 自动识别模型类型和提供商
- 针对中文优化的特殊处理

### 4. **向后兼容**

- 保持原有API接口不变
- 无缝升级现有代码

这个流程图清晰地展示了Token优化方案的完整交互过程，从用户请求到最终数据存储的每个环节都有详细说明。

### 7. MCP工具调用完整流程

```mermaid
flowchart TD
    A[用户请求工具调用] --> B[CoreAgent.chat()]
    B --> C[LLM决定调用工具]
    C --> D[MCPServerManager.call_tool()]
    D --> E[解析工具名称]
    E --> F{工具是否存在?}
    F -->|否| G[返回工具未找到错误]
    F -->|是| H[获取工具信息]
    H --> I{需要权限检查?}
    I -->|否| M[直接执行工具]
    I -->|是| J[检查风险级别]
    J --> K{风险级别}
    K -->|low| M
    K -->|medium/high| L[请求用户权限]
    
    L --> N[ToolPermissionManager处理]
    N --> O[通过WebSocket发送权限请求]
    O --> P[用户在前端确认/拒绝]
    P --> Q{用户是否同意?}
    Q -->|拒绝| R[返回权限被拒绝]
    Q -->|同意| M
    Q -->|超时| S[返回请求超时]
    
    M --> T[FastMCP Client执行工具]
    T --> U{执行是否成功?}
    U -->|失败| V[返回执行错误]
    U -->|成功| W[处理工具结果]
    W --> X[返回执行结果给LLM]
    X --> Y[LLM生成最终回复]
    Y --> Z[返回给用户]
    
    %% 样式定义
    classDef userAction fill:#e1f5fe
    classDef llmProcess fill:#f3e5f5
    classDef mcpCore fill:#e8f5e8
    classDef permission fill:#fff3e0
    classDef result fill:#ffebee
    
    class A,P userAction
    class B,C,X,Y,Z llmProcess
    class D,E,H,M,T,W mcpCore
    class I,J,K,L,N,O,Q permission
    class G,R,S,V result
```

### 8. MCP权限管理详细流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant LLM as LLM引擎
    participant MCP as MCPServerManager
    participant TPM as ToolPermissionManager
    participant WS as WebSocket
    participant Client as 前端客户端
    
    U->>LLM: 发送需要工具的请求
    LLM->>MCP: call_tool(tool_name, params, session_id)
    
    Note over MCP: 工具解析和权限检查
    MCP->>MCP: 解析工具名称
    MCP->>MCP: 检查风险级别
    
    alt 低风险工具
        MCP->>MCP: 直接执行工具
        MCP->>LLM: 返回执行结果
    else 中高风险工具
        MCP->>TPM: request_tool_permission()
        TPM->>TPM: 创建权限请求
        TPM->>WS: 通过WebSocket通知前端
        WS->>Client: tool_permission_request
        
        Client->>U: 显示权限确认对话框
        U->>Client: 确认/拒绝
        Client->>WS: tool_permission_response
        WS->>TPM: handle_user_response()
        
        alt 用户同意
            TPM->>TPM: 设置状态为APPROVED
            TPM->>MCP: 返回true
            MCP->>MCP: 执行工具
            MCP->>LLM: 返回执行结果
        else 用户拒绝
            TPM->>TPM: 设置状态为REJECTED
            TPM->>MCP: 返回false
            MCP->>LLM: 返回权限被拒绝错误
        else 超时
            TPM->>TPM: 设置状态为TIMEOUT
            TPM->>MCP: 返回false
            MCP->>LLM: 返回超时错误
        end
    end
    
    LLM->>U: 生成包含工具结果的回复
```

### 9. MCP服务器注册和工具发现流程

```mermaid
flowchart TD
    A[启动MCP服务器管理器] --> B[加载服务器配置]
    B --> C[验证配置有效性]
    C --> D{配置是否有效?}
    D -->|否| E[记录错误日志]
    D -->|是| F[创建FastMCP Client]
    F --> G[建立连接]
    G --> H{连接是否成功?}
    H -->|否| I[连接失败,记录错误]
    H -->|是| J[发送ping验证]
    J --> K[调用list_tools()发现工具]
    K --> L[解析工具信息]
    L --> M[应用风险级别配置]
    M --> N[更新全局工具索引]
    N --> O[注册完成]
    
    %% 并行处理多个服务器
    O --> P[监听服务器状态]
    P --> Q[定期健康检查]
    
    %% 样式定义
    classDef config fill:#e3f2fd
    classDef connection fill:#e8f5e8
    classDef discovery fill:#fff3e0
    classDef management fill:#f3e5f5
    
    class A,B,C,D config
    class F,G,H,I,J connection
    class K,L,M,N discovery
    class O,P,Q management
```

### 10. 工具执行和结果处理流程

```mermaid
flowchart TD
    A[接收工具调用请求] --> B[解析工具参数]
    B --> C[FastMCP Client执行]
    C --> D{执行结果类型}
    
    D -->|文本内容| E[提取text字段]
    D -->|复杂对象| F[转换为字符串]
    D -->|错误| G[格式化错误信息]
    
    E --> H[合并多个文本片段]
    F --> I[序列化对象]
    G --> J[包装错误响应]
    
    H --> K[返回处理后结果]
    I --> K
    J --> L[返回错误响应]
    
    K --> M[LLM处理工具结果]
    L --> N[LLM处理错误信息]
    
    M --> O[生成包含结果的回复]
    N --> P[生成错误说明回复]
    
    %% 样式定义
    classDef process fill:#e3f2fd
    classDef result fill:#e8f5e8
    classDef error fill:#ffebee
    classDef llm fill:#f3e5f5
    
    class A,B,C process
    class D,E,F,H,I,K result
    class G,J,L,N error
    class M,O,P llm
```

### 11. MCP工具风险级别管理

```mermaid
flowchart TD
    A[工具调用请求] --> B[获取工具信息]
    B --> C[检查tool_risks配置]
    C --> D{工具风险级别}
    
    D -->|low| E[直接执行<br/>无需用户确认]
    D -->|medium| F[需要用户确认<br/>5分钟超时]
    D -->|high| G[需要用户确认<br/>显示警告标识]
    D -->|未配置| H[使用默认级别: medium]
    
    E --> I[立即调用FastMCP]
    F --> J[发起权限请求]
    G --> J
    H --> J
    
    J --> K[WebSocket通知前端]
    K --> L[用户界面显示确认框]
    L --> M{用户操作}
    
    M -->|同意| N[记录用户同意]
    M -->|拒绝| O[记录用户拒绝]
    M -->|无响应| P[超时处理]
    
    N --> I
    O --> Q[返回权限拒绝错误]
    P --> R[返回超时错误]
    
    I --> S[工具执行成功]
    Q --> T[向用户说明权限被拒绝]
    R --> U[向用户说明请求超时]
    
    %% 样式定义
    classDef risk fill:#e3f2fd
    classDef permission fill:#fff3e0
    classDef execute fill:#e8f5e8
    classDef result fill:#f3e5f5
    
    class A,B,C,D,H risk
    class F,G,J,K,L,M permission
    class E,I,S execute
    class N,O,P,Q,R,T,U result
```

## 🔧 MCP工具调用与Token优化的集成

### MCP调用中的Token统计

在MCP工具调用过程中，Token统计同样适用：

```mermaid
flowchart LR
    A[用户消息 + 工具需求] --> B[Token估算: 用户输入]
    B --> C[MCP工具执行]
    C --> D[工具结果 + LLM回复]
    D --> E[Token估算: 完整回复]
    E --> F[保存Token统计信息]
    
    %% 包含工具调用的metadata
    G[工具调用元数据] --> H[工具名称、参数、执行时间]
    H --> I[包含在消息metadata中]
    I --> F
```

### 关键集成点

1. **权限确认与WebSocket**：
   - MCP工具调用的权限请求通过WebSocket实时通知
   - 前端显示工具信息和风险级别供用户确认

2. **Token计算增强**：
   - 工具调用的输入输出都计入Token统计
   - 支持包含工具结果的复杂回复计算

3. **统一错误处理**：
   - MCP调用失败时的降级机制
   - Token计算异常时的安全处理

### 实际应用场景

- **文件操作**：用户授权后的文件读写操作
- **系统命令**：需要权限确认的shell命令执行  
- **外部API**：调用第三方服务的工具
- **数据处理**：复杂的数据分析和处理工具

这个完整的流程确保了MCP工具调用的安全性、可控性和Token使用的准确统计。

## 🔌 WebSocket在MCP工具调用中的具体使用

### 当前实现状态

**WebSocket在MCP工具调用过程中的关键作用：**

```mermaid
sequenceDiagram
    participant TPM as ToolPermissionManager
    participant Redis as Redis发布订阅
    participant WS as WebSocket管理器
    participant Client as 前端客户端
    
    Note over TPM,Client: 当前实现 vs 预期实现
    
    TPM->>Redis: 发布权限请求 (当前实现)
    Note right of Redis: _notify_frontend() 仅发布Redis消息
    
    TPM->>WS: 直接WebSocket通知 (应该实现)
    WS->>Client: tool_permission_request
    Client->>WS: tool_permission_response  
    WS->>TPM: handle_user_response()
```

### WebSocket消息类型详解

#### 1. 工具权限请求 (`tool_permission_request`)

**发送方向**: 后端 → 前端
**触发时机**: MCP工具需要用户权限确认时

```json
{
    "type": "tool_permission_request",
    "data": {
        "request_id": "uuid-string",
        "session_id": "session-uuid",
        "tool_name": "file_operations::read_file",
        "tool_description": "读取指定文件的内容",
        "parameters": {
            "file_path": "/home/user/document.txt"
        },
        "risk_level": "medium",
        "expiry_time": "2025-07-01T12:35:00Z"
    }
}
```

#### 2. 用户权限响应 (`tool_permission_response`)

**发送方向**: 前端 → 后端  
**触发时机**: 用户在前端确认或拒绝工具执行

```json
{
    "type": "tool_permission_response", 
    "data": {
        "request_id": "uuid-string",
        "approved": true,
        "user_comment": "允许读取配置文件"
    }
}
```

#### 3. 权限响应确认 (`tool_permission_response_ack`)

**发送方向**: 后端 → 前端
**触发时机**: 后端收到用户响应后的确认

```json
{
    "type": "tool_permission_response_ack",
    "data": {
        "request_id": "uuid-string", 
        "success": true,
        "approved": true
    }
}
```

### WebSocket在流程中的使用位置

```mermaid
flowchart TD
    A[LLM决定调用工具] --> B[MCPServerManager.call_tool()]
    B --> C{检查风险级别}
    C -->|low| D[直接执行]
    C -->|medium/high| E[ToolPermissionManager.request_tool_permission()]
    
    E --> F[创建权限请求对象]
    F --> G[存储到Redis和内存]
    G --> H[📡 WebSocket通知前端]
    
    H --> I[前端显示权限确认对话框]
    I --> J[用户选择: 同意/拒绝]
    J --> K[📡 WebSocket发送用户响应]
    
    K --> L[ToolPermissionManager.handle_user_response()]
    L --> M[更新权限状态]
    M --> N[触发等待事件]
    N --> O[📡 WebSocket发送确认]
    
    O --> P{用户是否同意?}
    P -->|是| D
    P -->|否| Q[返回权限拒绝错误]
    
    D --> R[执行MCP工具]
    R --> S[📡 可选: WebSocket通知执行结果]
    
    %% 样式定义
    classDef websocket fill:#e1f5fe,stroke:#0277bd,stroke-width:3px
    classDef process fill:#f3e5f5
    classDef decision fill:#fff3e0
    
    class H,K,O,S websocket
    class A,B,E,F,G,L,M,N,R process
    class C,I,J,P decision
```

### 实现状态说明

#### ✅ 已实现的WebSocket功能

1. **WebSocket路由设置** (`websocket_router.py`)
   - `/ws/{session_id}` 和 `/ws?session_id=xxx` 端点
   - 连接管理和消息路由

2. **消息处理框架** (`websocket_manager.py`)  
   - `handle_websocket_message()` 处理不同消息类型
   - `tool_permission_response` 消息处理
   - `get_pending_permissions` 查询功能

3. **连接管理**
   - 按session_id管理WebSocket连接
   - 支持一个会话多个连接
   - 自动清理失效连接

#### ⚠️ 需要完善的部分

1. **直接WebSocket通知**

   ```python
   # 当前: 仅Redis发布
   await redis_client.publish(channel, message)
   
   # 应该: 直接WebSocket通知
   await notify_tool_permission_request(session_id, request_data)
   ```

2. **Redis订阅集成**
   - 需要后台任务监听Redis发布的消息
   - 将Redis消息转发到WebSocket

3. **工具执行结果通知**
   - 可选择性通知工具执行成功/失败
   - 长时间运行工具的进度更新

### 完整的WebSocket使用场景

#### 场景1: 文件读取权限确认

```
用户: "帮我读取配置文件的内容"
→ LLM: 决定调用 file_operations::read_file
→ WebSocket: 发送权限请求到前端  
→ 前端: 显示 "是否允许读取 /config/app.conf ?"
→ 用户: 点击"允许"
→ WebSocket: 发送用户同意响应
→ 后端: 执行文件读取工具
→ LLM: 返回文件内容给用户
```

#### 场景2: 系统命令执行确认  

```
用户: "帮我查看服务器磁盘使用情况"
→ LLM: 决定调用 system::exec_command
→ WebSocket: 发送高风险工具权限请求
→ 前端: 显示 "是否允许执行 'df -h' 命令?" (红色警告)
→ 用户: 确认后点击"允许"  
→ WebSocket: 发送用户同意响应
→ 后端: 执行系统命令
→ WebSocket: (可选) 通知执行完成
→ LLM: 返回磁盘使用情况
```

这样WebSocket就成为了MCP工具调用中**用户授权**的关键通信桥梁！
