# SSE实时推送集成指南

本指南介绍如何使用Server-Sent Events (SSE) 方案替代WebSocket，实现MCP工具状态的实时推送。

## 架构概述

```
前端 ──[SSE连接]──> 后端SSE路由 ──[Redis订阅]──> Redis发布订阅
                                                    ↑
MCP工具执行 ──[状态变化]──> SimpleNotifier ──[发布事件]──┘
```

## API端点

### 1. 建立SSE连接
```
GET /agent_backend/api/sse/events/{session_id}
```
- **功能**：建立SSE连接，接收实时事件推送
- **认证**：需要Bearer Token
- **返回**：SSE事件流

### 2. 提交权限响应
```
POST /agent_backend/api/sse/permission-response/{session_id}
```
- **功能**：提交工具权限确认
- **认证**：需要Bearer Token
- **请求体**：
```json
{
    "approved": true,
    "reason": "用户同意执行此工具"
}
```

### 3. 健康检查
```
GET /agent_backend/api/sse/health/{session_id}
```
- **功能**：检查SSE连接状态
- **认证**：需要Bearer Token

## 事件类型

SSE推送的事件类型包括：

### 1. 工具状态事件
```json
{
    "type": "tool_status",
    "data": {
        "status": "executing",
        "tool_name": "file_search",
        "timestamp": "2024-01-15T10:30:00Z",
        "details": {
            "parameters": {"query": "example"},
            "risk_level": "medium",
            "start_time": "2024-01-15T10:30:00Z"
        }
    }
}
```

### 2. 权限请求事件
```json
{
    "type": "permission_request",
    "data": {
        "tool_name": "file_edit",
        "parameters": {"file": "example.py"},
        "risk_level": "high",
        "timestamp": "2024-01-15T10:30:00Z",
        "status": "pending"
    }
}
```

### 3. 工具结果事件
```json
{
    "type": "tool_result",
    "data": {
        "tool_name": "file_search",
        "result": {"matches": 5},
        "success": true,
        "timestamp": "2024-01-15T10:30:15Z"
    }
}
```

### 4. 心跳事件
```json
{
    "type": "heartbeat",
    "timestamp": 1642234200.123
}
```

## 前端集成示例

### TypeScript/JavaScript 客户端

```typescript
class SSEClient {
    private eventSource: EventSource | null = null;
    private sessionId: string;
    private token: string;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 1000;

    constructor(sessionId: string, token: string) {
        this.sessionId = sessionId;
        this.token = token;
    }

    connect(): void {
        if (this.eventSource) {
            this.eventSource.close();
        }

        // 注意：EventSource不支持自定义headers，需要通过查询参数传递token
        const url = `/agent_backend/api/sse/events/${this.sessionId}?token=${encodeURIComponent(this.token)}`;
        
        this.eventSource = new EventSource(url);

        this.eventSource.onopen = (event) => {
            console.log('SSE连接已建立');
            this.reconnectAttempts = 0;
            this.onConnectionOpen?.(event);
        };

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleEvent(data);
            } catch (error) {
                console.error('解析SSE消息失败:', error);
            }
        };

        this.eventSource.onerror = (event) => {
            console.error('SSE连接错误:', event);
            this.handleReconnect();
        };
    }

    private handleEvent(data: any): void {
        switch (data.type) {
            case 'tool_status':
                this.onToolStatusChange?.(data.data);
                break;
            case 'permission_request':
                this.onPermissionRequest?.(data.data);
                break;
            case 'tool_result':
                this.onToolResult?.(data.data);
                break;
            case 'permission_cleared':
                this.onPermissionCleared?.(data.data);
                break;
            case 'result_cleared':
                this.onResultCleared?.(data.data);
                break;
            case 'permission_response_result':
                this.onPermissionResponseResult?.(data.data);
                break;
            case 'heartbeat':
                this.onHeartbeat?.(data.timestamp);
                break;
            case 'error':
                this.onError?.(data.message);
                break;
            default:
                console.warn('未知的SSE事件类型:', data.type);
        }
    }

    private handleReconnect(): void {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
            
            console.log(`${delay}ms后尝试重连...`);
            setTimeout(() => {
                this.connect();
            }, delay);
        } else {
            console.error('达到最大重连次数，停止重连');
            this.onMaxReconnectAttemptsReached?.();
        }
    }

    async approvePermission(approved: boolean, reason: string = ''): Promise<boolean> {
        try {
            const response = await fetch(
                `/agent_backend/api/sse/permission-response/${this.sessionId}`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this.token}`
                    },
                    body: JSON.stringify({ approved, reason })
                }
            );

            const result = await response.json();
            return result.success;
        } catch (error) {
            console.error('提交权限响应失败:', error);
            return false;
        }
    }

    async checkHealth(): Promise<any> {
        try {
            const response = await fetch(
                `/agent_backend/api/sse/health/${this.sessionId}`,
                {
                    headers: {
                        'Authorization': `Bearer ${this.token}`
                    }
                }
            );
            return await response.json();
        } catch (error) {
            console.error('健康检查失败:', error);
            return null;
        }
    }

    disconnect(): void {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

    // 事件回调
    onConnectionOpen?: (event: Event) => void;
    onToolStatusChange?: (status: any) => void;
    onPermissionRequest?: (request: any) => void;
    onToolResult?: (result: any) => void;
    onPermissionCleared?: (data: any) => void;
    onResultCleared?: (data: any) => void;
    onPermissionResponseResult?: (result: any) => void;
    onHeartbeat?: (timestamp: number) => void;
    onError?: (message: string) => void;
    onMaxReconnectAttemptsReached?: () => void;
}
```

### React 组件示例

```tsx
import React, { useEffect, useState, useRef } from 'react';

interface ToolStatus {
    status: string;
    tool_name: string;
    timestamp: string;
    details: any;
}

interface PermissionRequest {
    tool_name: string;
    parameters: any;
    risk_level: string;
    timestamp: string;
    status: string;
}

const MCPToolMonitor: React.FC<{ sessionId: string; token: string }> = ({ 
    sessionId, 
    token 
}) => {
    const [toolStatus, setToolStatus] = useState<ToolStatus | null>(null);
    const [permissionRequest, setPermissionRequest] = useState<PermissionRequest | null>(null);
    const [isConnected, setIsConnected] = useState(false);
    const sseClient = useRef<SSEClient | null>(null);

    useEffect(() => {
        // 创建SSE客户端
        sseClient.current = new SSEClient(sessionId, token);
        
        // 设置事件处理器
        sseClient.current.onConnectionOpen = () => {
            setIsConnected(true);
        };
        
        sseClient.current.onToolStatusChange = (status) => {
            setToolStatus(status);
        };
        
        sseClient.current.onPermissionRequest = (request) => {
            setPermissionRequest(request);
        };
        
        sseClient.current.onPermissionCleared = () => {
            setPermissionRequest(null);
        };
        
        sseClient.current.onError = (message) => {
            console.error('SSE错误:', message);
            setIsConnected(false);
        };
        
        // 建立连接
        sseClient.current.connect();
        
        // 清理函数
        return () => {
            sseClient.current?.disconnect();
        };
    }, [sessionId, token]);

    const handlePermissionResponse = async (approved: boolean) => {
        if (sseClient.current) {
            const success = await sseClient.current.approvePermission(
                approved, 
                approved ? '用户同意' : '用户拒绝'
            );
            
            if (success) {
                setPermissionRequest(null);
            }
        }
    };

    return (
        <div className="mcp-tool-monitor">
            <div className="connection-status">
                状态: {isConnected ? '已连接' : '未连接'}
            </div>
            
            {toolStatus && (
                <div className="tool-status">
                    <h3>工具状态</h3>
                    <p>工具: {toolStatus.tool_name}</p>
                    <p>状态: {toolStatus.status}</p>
                    <p>时间: {new Date(toolStatus.timestamp).toLocaleString()}</p>
                </div>
            )}
            
            {permissionRequest && (
                <div className="permission-request">
                    <h3>权限确认</h3>
                    <p>工具: {permissionRequest.tool_name}</p>
                    <p>风险级别: {permissionRequest.risk_level}</p>
                    <p>参数: {JSON.stringify(permissionRequest.parameters)}</p>
                    
                    <div className="permission-buttons">
                        <button 
                            onClick={() => handlePermissionResponse(true)}
                            className="approve-btn"
                        >
                            同意
                        </button>
                        <button 
                            onClick={() => handlePermissionResponse(false)}
                            className="reject-btn"
                        >
                            拒绝
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default MCPToolMonitor;
```

## 性能优化建议

### 1. 连接管理
- 实现自动重连机制
- 使用指数退避算法
- 设置最大重连次数限制

### 2. 事件处理
- 对大量事件进行去重和节流
- 实现事件队列避免阻塞
- 合理设置心跳间隔

### 3. 错误处理
- 实现完善的错误恢复机制
- 记录连接状态和错误日志
- 提供降级方案（如轮询）

### 4. 资源管理
- 及时清理断开的连接
- 合理设置Redis过期时间
- 监控内存使用情况

## 故障排除

### 常见问题

1. **连接频繁断开**
   - 检查网络稳定性
   - 调整心跳间隔
   - 检查代理服务器配置

2. **事件丢失**
   - 检查Redis连接状态
   - 增加事件队列大小
   - 实现事件持久化

3. **内存泄漏**
   - 及时清理事件订阅
   - 设置合理的过期时间
   - 监控连接数量

### 调试技巧

- 使用浏览器开发者工具查看SSE连接
- 检查Redis中的发布订阅状态
- 查看服务器日志定位问题

## 总结

SSE方案相比WebSocket具有以下优势：
- **简单易用**：基于HTTP，易于调试和维护
- **自动重连**：浏览器原生支持重连
- **防火墙友好**：使用标准HTTP端口
- **单向通信**：满足大多数推送需求

这个优化后的SSE实现提供了高性能的实时推送能力，同时保持了代码的简洁性和可维护性。 