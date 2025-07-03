# WebSocket替代方案指南

本文档提供了多种轻量级的WebSocket替代方案，用于处理MCP工具的确认和结果返回。

## 方案对比

| 方案 | 实时性 | 复杂度 | 资源消耗 | 适用场景 |
|------|--------|--------|----------|----------|
| HTTP轮询 | 低 | 简单 | 低 | 对实时性要求不高的场景 |
| Server-Sent Events | 高 | 中等 | 中等 | 需要实时推送但不需要双向通信 |
| HTTP Long Polling | 中等 | 中等 | 中等 | 平衡实时性和资源消耗 |
| WebSocket | 高 | 复杂 | 高 | 需要高实时性和双向通信 |

## 方案1：HTTP轮询（推荐）

### 特点
- **最简单**：前端定期请求状态，后端存储在Redis中
- **资源友好**：按需请求，无长连接
- **容错性好**：网络中断不影响状态
- **易于调试**：标准HTTP请求响应

### 实现细节

#### 后端API端点
```
GET /agent_backend/api/polling/session-info/{session_id}  # 获取所有状态
GET /agent_backend/api/polling/tool-status/{session_id}   # 获取工具状态
GET /agent_backend/api/polling/permission-request/{session_id}  # 获取权限请求
POST /agent_backend/api/polling/permission-response/{session_id}  # 提交权限响应
GET /agent_backend/api/polling/tool-result/{session_id}   # 获取工具结果
POST /agent_backend/api/polling/clear-result/{session_id}  # 清除已读结果
```

#### 前端集成示例
```javascript
class PollingClient {
    constructor(sessionId, pollInterval = 2000) {
        this.sessionId = sessionId;
        this.pollInterval = pollInterval;
        this.isPolling = false;
    }
    
    startPolling() {
        if (this.isPolling) return;
        this.isPolling = true;
        this.poll();
    }
    
    async poll() {
        while (this.isPolling) {
            try {
                const response = await fetch(`/agent_backend/api/polling/session-info/${this.sessionId}`);
                const data = await response.json();
                
                if (data.success) {
                    this.handleStatusUpdate(data.data);
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
            
            await new Promise(resolve => setTimeout(resolve, this.pollInterval));
        }
    }
    
    handleStatusUpdate(data) {
        if (data.tool_status) {
            this.onToolStatusChange(data.tool_status);
        }
        if (data.permission_request) {
            this.onPermissionRequest(data.permission_request);
        }
        if (data.tool_result) {
            this.onToolResult(data.tool_result);
        }
    }
    
    async approvePermission(approved) {
        await fetch(`/agent_backend/api/polling/permission-response/${this.sessionId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ approved })
        });
    }
}
```

### 优化建议
- 轮询间隔：2-5秒（根据实时性需求调整）
- 指数退避：出错时增加轮询间隔
- 状态缓存：避免重复处理相同状态

## 方案2：Server-Sent Events (SSE)

### 特点
- **单向推送**：服务器主动推送，客户端监听
- **实时性好**：接近WebSocket的实时性
- **标准协议**：基于HTTP，易于代理和缓存
- **自动重连**：浏览器原生支持重连

### 实现细节

#### 后端API端点
```
GET /agent_backend/api/sse/events/{session_id}  # SSE事件流
POST /agent_backend/api/sse/permission-response/{session_id}  # 权限响应
```

#### 前端集成示例
```javascript
class SSEClient {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.eventSource = null;
    }
    
    connect() {
        this.eventSource = new EventSource(`/agent_backend/api/sse/events/${this.sessionId}`);
        
        this.eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleEvent(data);
        };
        
        this.eventSource.onerror = (error) => {
            console.error('SSE error:', error);
        };
    }
    
    handleEvent(data) {
        switch (data.type) {
            case 'tool_status':
                this.onToolStatusChange(data.data);
                break;
            case 'permission_request':
                this.onPermissionRequest(data.data);
                break;
            case 'tool_result':
                this.onToolResult(data.data);
                break;
            case 'heartbeat':
                this.onHeartbeat(data.timestamp);
                break;
        }
    }
    
    async approvePermission(approved) {
        await fetch(`/agent_backend/api/sse/permission-response/${this.sessionId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ approved })
        });
    }
    
    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
        }
    }
}
```

## 方案3：HTTP Long Polling

### 特点
- **准实时**：长连接等待状态变化
- **平衡性好**：实时性和资源消耗的平衡
- **兼容性好**：所有HTTP客户端都支持

### 实现示例
```javascript
class LongPollingClient {
    constructor(sessionId, timeout = 30000) {
        this.sessionId = sessionId;
        this.timeout = timeout;
        this.isPolling = false;
    }
    
    async longPoll() {
        while (this.isPolling) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), this.timeout);
                
                const response = await fetch(`/api/long-poll/${this.sessionId}`, {
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                if (response.ok) {
                    const data = await response.json();
                    this.handleUpdate(data);
                }
            } catch (error) {
                if (error.name !== 'AbortError') {
                    console.error('Long polling error:', error);
                    await new Promise(resolve => setTimeout(resolve, 5000));
                }
            }
        }
    }
}
```

## 迁移指南

### 从WebSocket迁移到HTTP轮询

1. **替换通知器**
   ```python
   # 原来的
   from copilot.core.websocket_notifier import WebSocketNotifier
   
   # 改为
   from copilot.core.simple_notifier import SimpleNotifier
   ```

2. **更新调用方式**
   ```python
   # 方法调用保持不变
   await SimpleNotifier.notify_tool_execution_start(session_id, tool_info)
   await SimpleNotifier.notify_tool_waiting_permission(session_id, tool_info)
   await SimpleNotifier.notify_tool_execution_complete(session_id, tool_info, result, success)
   ```

3. **前端修改**
   - 移除WebSocket连接代码
   - 添加轮询或SSE客户端
   - 更新权限响应提交方式

### 性能优化

1. **Redis优化**
   - 设置合理的过期时间
   - 使用Redis集群提高可用性
   - 监控Redis内存使用

2. **轮询优化**
   - 智能调整轮询间隔
   - 使用状态变化检测避免无效请求
   - 实现指数退避策略

3. **网络优化**
   - 启用HTTP/2推送
   - 使用CDN加速API请求
   - 实现请求去重

## 总结

**现已采用SSE方案**，它提供了最佳的平衡：
- **实时性好**：接近WebSocket的推送性能
- **标准协议**：基于HTTP，易于调试和部署
- **自动重连**：浏览器原生支持断线重连
- **资源高效**：单向推送，无需维护双向连接状态

相比WebSocket方案：
- ✅ 更简单的实现和维护
- ✅ 更好的网络兼容性
- ✅ 更低的资源消耗
- ✅ 内置的错误恢复机制

详细的SSE集成指南请参考：`docs/sse_integration_guide.md` 