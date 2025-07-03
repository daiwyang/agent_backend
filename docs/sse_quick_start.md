# SSE快速启动指南

## 概述

Server-Sent Events (SSE) 方案已成功替代WebSocket，提供更稳定、更轻量级的实时推送服务。

## 🚀 后端启动

### 1. 安装依赖
```bash
pip install sse-starlette>=1.6.0
```

### 2. 启动服务
```bash
python copilot/main.py
```

服务启动后，SSE管理器会自动初始化并监听Redis事件。

## 📡 API端点

### SSE事件流
```
GET /agent_backend/api/sse/events/{session_id}?token={user_token}
```

### 权限响应
```
POST /agent_backend/api/sse/permission-response/{session_id}
Content-Type: application/json
Authorization: Bearer {token}

{
    "approved": true,
    "reason": "用户同意"
}
```

### 健康检查
```
GET /agent_backend/api/sse/health/{session_id}
Authorization: Bearer {token}
```

## 🔧 前端集成

### 基础SSE客户端
```javascript
const sessionId = 'your-session-id';
const token = 'your-auth-token';

// 建立SSE连接
const eventSource = new EventSource(
    `/agent_backend/api/sse/events/${sessionId}?token=${encodeURIComponent(token)}`
);

// 监听消息
eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('收到事件:', data.type, data.data);
    
    switch (data.type) {
        case 'tool_status':
            console.log('工具状态:', data.data.status);
            break;
        case 'permission_request':
            console.log('权限请求:', data.data.tool_name);
            // 显示确认对话框
            showPermissionDialog(data.data);
            break;
        case 'tool_result':
            console.log('工具结果:', data.data.success);
            break;
        case 'heartbeat':
            console.log('心跳:', new Date(data.timestamp));
            break;
    }
};

// 错误处理
eventSource.onerror = function(event) {
    console.error('SSE连接错误:', event);
};

// 提交权限响应
async function approvePermission(approved, reason = '') {
    const response = await fetch(`/agent_backend/api/sse/permission-response/${sessionId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ approved, reason })
    });
    
    const result = await response.json();
    console.log('权限响应结果:', result);
}
```

### React Hook示例
```jsx
import { useEffect, useState } from 'react';

function useSSEConnection(sessionId, token) {
    const [toolStatus, setToolStatus] = useState(null);
    const [permissionRequest, setPermissionRequest] = useState(null);
    const [isConnected, setIsConnected] = useState(false);

    useEffect(() => {
        const eventSource = new EventSource(
            `/agent_backend/api/sse/events/${sessionId}?token=${encodeURIComponent(token)}`
        );

        eventSource.onopen = () => setIsConnected(true);
        eventSource.onerror = () => setIsConnected(false);

        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            switch (data.type) {
                case 'tool_status':
                    setToolStatus(data.data);
                    break;
                case 'permission_request':
                    setPermissionRequest(data.data);
                    break;
                case 'permission_cleared':
                    setPermissionRequest(null);
                    break;
            }
        };

        return () => {
            eventSource.close();
        };
    }, [sessionId, token]);

    const approvePermission = async (approved, reason = '') => {
        const response = await fetch(`/agent_backend/api/sse/permission-response/${sessionId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ approved, reason })
        });
        
        return await response.json();
    };

    return { toolStatus, permissionRequest, isConnected, approvePermission };
}
```

## 🛡️ 错误处理

### 自动重连机制
```javascript
class SSEClient {
    constructor(sessionId, token) {
        this.sessionId = sessionId;
        this.token = token;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.eventSource = null;
    }

    connect() {
        const url = `/agent_backend/api/sse/events/${this.sessionId}?token=${encodeURIComponent(this.token)}`;
        this.eventSource = new EventSource(url);

        this.eventSource.onopen = () => {
            console.log('SSE连接成功');
            this.reconnectAttempts = 0;
        };

        this.eventSource.onerror = () => {
            console.error('SSE连接错误');
            this.handleReconnect();
        };

        this.eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
    }

    handleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.pow(2, this.reconnectAttempts) * 1000;
            
            console.log(`${delay}ms后重连...`);
            setTimeout(() => this.connect(), delay);
        } else {
            console.error('达到最大重连次数');
        }
    }

    handleMessage(data) {
        // 处理消息
    }

    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
        }
    }
}
```

## 📊 监控和调试

### 健康检查
```javascript
async function checkSSEHealth(sessionId, token) {
    const response = await fetch(`/agent_backend/api/sse/health/${sessionId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    
    const health = await response.json();
    console.log('SSE健康状态:', health.data);
}
```

### 浏览器调试
1. 打开开发者工具
2. 进入Network面板
3. 筛选"EventSource"类型
4. 查看SSE连接状态和消息

### 服务器日志
```bash
# 查看SSE相关日志
tail -f /path/to/logs | grep "SSE\|SimpleNotifier"
```

## 🔍 故障排除

### 常见问题

1. **连接立即断开**
   - 检查token是否有效
   - 验证session_id权限
   - 查看服务器日志

2. **事件接收延迟**
   - 检查Redis连接状态
   - 查看网络延迟
   - 验证事件发布逻辑

3. **内存使用过高**
   - 监控事件队列大小
   - 检查连接数量
   - 验证清理机制

### 调试命令
```bash
# 检查Redis发布订阅
redis-cli monitor | grep sse_events

# 查看SSE连接数
curl -H "Authorization: Bearer $TOKEN" \
    http://localhost:8000/agent_backend/api/sse/health/$SESSION_ID
```

## 📈 性能优化

### 建议配置
- **心跳间隔**: 30秒
- **事件队列大小**: 100条
- **Redis过期时间**: 5-10分钟
- **最大重连次数**: 5次

### 生产环境
- 使用Redis集群
- 配置负载均衡
- 启用监控告警
- 设置资源限制

## 📚 更多资源

- [完整集成指南](./sse_integration_guide.md)
- [迁移总结](./sse_migration_summary.md)
- [WebSocket替代方案对比](./websocket_alternatives.md)

---

🎉 **恭喜！** 您现在已经可以使用高性能的SSE实时推送服务了！ 