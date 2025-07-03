# 统一聊天流前端集成指南

## 概述

本指南介绍如何在前端集成统一的聊天流通信方案，该方案将聊天消息和工具权限确认统一到一个HTTP流式接口中，提供一致的用户体验。

## 核心优势

### 🎯 统一体验
- **单一通信流**：所有交互都通过聊天流完成
- **一致界面**：权限确认作为对话的自然部分
- **简化前端**：只需处理一个HTTP流

### 🚀 技术优势  
- **架构简洁**：移除了SSE依赖，使用HTTP StreamingResponse
- **易于维护**：统一的消息处理逻辑
- **性能更好**：减少通信开销

## API端点

### 1. 流式聊天接口
```
POST /api/chat/chat
Content-Type: application/json
Authorization: Bearer <token>

{
    "session_id": "session_123",
    "message": "请帮我创建一个文件",
    "enable_mcp_tools": true,
    "attachments": []
}
```

### 2. 权限响应接口
```
POST /api/chat/permission-response  
Content-Type: application/json
Authorization: Bearer <token>

{
    "session_id": "session_123",
    "request_id": "req_456",
    "approved": true,
    "user_feedback": "同意执行"
}
```

## 消息类型定义

### 基本聊天消息
```javascript
// 开始消息
{
    "type": "start",
    "session_id": "session_123"
}

// 内容消息
{
    "type": "content", 
    "content": "AI回复的文本内容"
}

// 结束消息
{
    "type": "end",
    "session_id": "session_123",
    "message_ids": {
        "user_message_id": "msg_123",
        "assistant_message_id": "msg_124"
    }
}

// 错误消息
{
    "type": "error",
    "content": "错误描述",
    "error_code": "ERROR_CODE"
}
```

### 工具权限确认消息

#### 权限请求消息
```javascript
{
    "type": "tool_permission_request",
    "session_id": "session_123", 
    "timestamp": "2025-07-03T09:51:43.927892Z",
    "data": {
        "request_id": "req_456",
        "tool_name": "file_write",
        "tool_description": "工具 file_write 需要执行",
        "parameters": {
            "path": "/tmp/test.txt",
            "content": "Hello World"
        },
        "risk_level": "medium",
        "reasoning": "需要写入测试文件"
    }
}
```

#### 执行状态消息
```javascript
{
    "type": "tool_execution_status",
    "session_id": "session_123",
    "timestamp": "2025-07-03T09:51:43.927892Z", 
    "data": {
        "request_id": "req_456",
        "tool_name": "file_write",
        "status": "waiting|executing|completed|failed|cancelled",
        "result": "执行结果（可选）",
        "error": "错误信息（可选）",
        "progress": 75  // 进度百分比（可选）
    }
}
```

## 前端实现示例

### JavaScript/TypeScript 实现

```javascript
class UnifiedChatClient {
    constructor(sessionId) {
        this.sessionId = sessionId;
        this.pendingPermissions = new Map(); // 存储待确认的权限请求
    }

    /**
     * 发送聊天消息并处理流式响应
     */
    async sendMessage(message, enableTools = true) {
        const response = await fetch('/api/chat/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.getToken()}`
            },
            body: JSON.stringify({
                session_id: this.sessionId,
                message: message,
                enable_mcp_tools: enableTools
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return this.processStream(response);
    }

    /**
     * 处理流式响应
     */
    async processStream(response) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n').filter(line => line.trim());

                for (const line of lines) {
                    try {
                        const message = JSON.parse(line);
                        await this.handleMessage(message);
                    } catch (e) {
                        console.warn('Failed to parse message:', line, e);
                    }
                }
            }
        } finally {
            reader.releaseLock();
        }
    }

    /**
     * 处理不同类型的消息
     */
    async handleMessage(message) {
        switch (message.type) {
            case 'start':
                this.onChatStart(message);
                break;
            case 'content':
                this.onChatContent(message);
                break;
            case 'end':
                this.onChatEnd(message);
                break;
            case 'error':
                this.onError(message);
                break;
            case 'tool_permission_request':
                await this.onToolPermissionRequest(message);
                break;
            case 'tool_execution_status':
                this.onToolExecutionStatus(message);
                break;
            default:
                console.warn('Unknown message type:', message.type);
        }
    }

    /**
     * 聊天开始
     */
    onChatStart(message) {
        console.log('💬 聊天开始:', message.session_id);
        // 显示"正在思考..."指示器
        this.showThinkingIndicator();
    }

    /**
     * 接收聊天内容
     */
    onChatContent(message) {
        console.log('📝 内容:', message.content);
        // 将内容追加到聊天界面
        this.appendToChat(message.content, 'assistant');
    }

    /**
     * 聊天结束
     */
    onChatEnd(message) {
        console.log('✅ 聊天结束:', message.session_id);
        // 隐藏"正在思考..."指示器
        this.hideThinkingIndicator();
        // 保存消息ID用于后续引用
        this.lastMessageIds = message.message_ids;
    }

    /**
     * 处理错误
     */
    onError(message) {
        console.error('❌ 错误:', message.content);
        this.showError(message.content);
        this.hideThinkingIndicator();
    }

    /**
     * 处理工具权限请求
     */
    async onToolPermissionRequest(message) {
        const { data } = message;
        const { request_id, tool_name, tool_description, parameters, risk_level, reasoning } = data;

        console.log('🔒 权限请求:', tool_name, parameters);

        // 存储权限请求
        this.pendingPermissions.set(request_id, data);

        // 显示权限确认UI
        const permissionData = {
            requestId: request_id,
            toolName: tool_name,
            description: tool_description,
            parameters: parameters,
            riskLevel: risk_level,
            reasoning: reasoning
        };

        await this.showPermissionDialog(permissionData);
    }

    /**
     * 处理工具执行状态
     */
    onToolExecutionStatus(message) {
        const { data } = message;
        const { request_id, tool_name, status, result, error, progress } = data;

        console.log(`⚙️ 工具状态: ${tool_name} - ${status}`, { result, error, progress });

        switch (status) {
            case 'waiting':
                this.showToolStatus(tool_name, '⏳ 等待权限确认...');
                break;
            case 'executing':
                this.showToolStatus(tool_name, '🔄 正在执行...');
                if (progress !== null) {
                    this.updateToolProgress(tool_name, progress);
                }
                break;
            case 'completed':
                this.showToolStatus(tool_name, '✅ 执行完成');
                if (result) {
                    this.appendToChat(`工具执行结果: ${result}`, 'tool-result');
                }
                this.removePermissionRequest(request_id);
                break;
            case 'failed':
                this.showToolStatus(tool_name, '❌ 执行失败');
                if (error) {
                    this.showError(`工具执行失败: ${error}`);
                }
                this.removePermissionRequest(request_id);
                break;
            case 'cancelled':
                this.showToolStatus(tool_name, '🚫 已取消');
                this.removePermissionRequest(request_id);
                break;
        }
    }

    /**
     * 显示权限确认对话框
     */
    async showPermissionDialog(permissionData) {
        const { requestId, toolName, description, parameters, riskLevel, reasoning } = permissionData;

        // 创建权限确认UI
        const dialog = document.createElement('div');
        dialog.className = 'permission-dialog';
        dialog.innerHTML = `
            <div class="permission-content">
                <h3>🔒 工具权限确认</h3>
                <div class="tool-info">
                    <p><strong>工具名称:</strong> ${toolName}</p>
                    <p><strong>描述:</strong> ${description}</p>
                    <p><strong>风险级别:</strong> <span class="risk-${riskLevel}">${riskLevel}</span></p>
                    ${reasoning ? `<p><strong>原因:</strong> ${reasoning}</p>` : ''}
                </div>
                <div class="tool-parameters">
                    <h4>参数:</h4>
                    <pre>${JSON.stringify(parameters, null, 2)}</pre>
                </div>
                <div class="permission-actions">
                    <button class="btn-approve">✅ 同意</button>
                    <button class="btn-deny">❌ 拒绝</button>
                </div>
            </div>
        `;

        // 添加事件监听器
        dialog.querySelector('.btn-approve').onclick = () => {
            this.respondToPermission(requestId, true, '用户同意执行');
            dialog.remove();
        };

        dialog.querySelector('.btn-deny').onclick = () => {
            this.respondToPermission(requestId, false, '用户拒绝执行');
            dialog.remove();
        };

        // 显示对话框
        document.body.appendChild(dialog);
    }

    /**
     * 响应权限请求
     */
    async respondToPermission(requestId, approved, feedback = '') {
        try {
            const response = await fetch('/api/chat/permission-response', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.getToken()}`
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    request_id: requestId,
                    approved: approved,
                    user_feedback: feedback
                })
            });

            if (!response.ok) {
                throw new Error(`权限响应失败: ${response.status}`);
            }

            const result = await response.json();
            console.log('权限响应结果:', result);

        } catch (error) {
            console.error('权限响应错误:', error);
            this.showError('权限响应失败，请重试');
        }
    }

    /**
     * 移除权限请求
     */
    removePermissionRequest(requestId) {
        this.pendingPermissions.delete(requestId);
    }

    // UI辅助方法
    showThinkingIndicator() {
        const indicator = document.createElement('div');
        indicator.id = 'thinking-indicator';
        indicator.innerHTML = '🤔 正在思考...';
        document.getElementById('chat-container').appendChild(indicator);
    }

    hideThinkingIndicator() {
        const indicator = document.getElementById('thinking-indicator');
        if (indicator) indicator.remove();
    }

    appendToChat(content, sender) {
        const chatContainer = document.getElementById('chat-container');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}`;
        messageDiv.textContent = content;
        chatContainer.appendChild(messageDiv);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    showToolStatus(toolName, status) {
        // 在聊天界面显示工具状态
        this.appendToChat(`${toolName}: ${status}`, 'tool-status');
    }

    updateToolProgress(toolName, progress) {
        // 更新工具执行进度
        const progressBar = document.getElementById(`progress-${toolName}`);
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
        }
    }

    showError(message) {
        this.appendToChat(`错误: ${message}`, 'error');
    }

    getToken() {
        // 返回认证token
        return localStorage.getItem('auth_token');
    }
}
```

### React实现示例

```jsx
import React, { useState, useCallback, useRef, useEffect } from 'react';

const UnifiedChatComponent = ({ sessionId, authToken }) => {
    const [messages, setMessages] = useState([]);
    const [inputValue, setInputValue] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [pendingPermissions, setPendingPermissions] = useState(new Map());
    const chatContainerRef = useRef(null);

    // 发送消息
    const sendMessage = useCallback(async (message) => {
        if (!message.trim()) return;

        // 添加用户消息到界面
        setMessages(prev => [...prev, { type: 'user', content: message, timestamp: new Date() }]);
        setInputValue('');
        setIsLoading(true);

        try {
            const response = await fetch('/api/chat/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    message: message,
                    enable_mcp_tools: true
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            await processStream(response);
        } catch (error) {
            console.error('发送消息失败:', error);
            setMessages(prev => [...prev, { 
                type: 'error', 
                content: `发送失败: ${error.message}`, 
                timestamp: new Date() 
            }]);
        } finally {
            setIsLoading(false);
        }
    }, [sessionId, authToken]);

    // 处理流式响应
    const processStream = async (response) => {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantMessageBuffer = '';

        try {
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n').filter(line => line.trim());

                for (const line of lines) {
                    try {
                        const message = JSON.parse(line);
                        
                        switch (message.type) {
                            case 'start':
                                // 开始新的助手消息
                                assistantMessageBuffer = '';
                                break;
                                
                            case 'content':
                                // 累积助手消息内容
                                assistantMessageBuffer += message.content;
                                setMessages(prev => {
                                    const lastMessage = prev[prev.length - 1];
                                    if (lastMessage && lastMessage.type === 'assistant' && lastMessage.isStreaming) {
                                        // 更新现有的流式消息
                                        return [
                                            ...prev.slice(0, -1),
                                            { ...lastMessage, content: assistantMessageBuffer }
                                        ];
                                    } else {
                                        // 创建新的流式消息
                                        return [...prev, {
                                            type: 'assistant',
                                            content: assistantMessageBuffer,
                                            timestamp: new Date(),
                                            isStreaming: true
                                        }];
                                    }
                                });
                                break;
                                
                            case 'end':
                                // 完成流式消息
                                setMessages(prev => {
                                    const lastMessage = prev[prev.length - 1];
                                    if (lastMessage && lastMessage.isStreaming) {
                                        return [
                                            ...prev.slice(0, -1),
                                            { ...lastMessage, isStreaming: false }
                                        ];
                                    }
                                    return prev;
                                });
                                break;
                                
                            case 'tool_permission_request':
                                handleToolPermissionRequest(message);
                                break;
                                
                            case 'tool_execution_status':
                                handleToolExecutionStatus(message);
                                break;
                                
                            case 'error':
                                setMessages(prev => [...prev, {
                                    type: 'error',
                                    content: message.content,
                                    timestamp: new Date()
                                }]);
                                break;
                        }
                    } catch (e) {
                        console.warn('Failed to parse message:', line, e);
                    }
                }
            }
        } finally {
            reader.releaseLock();
        }
    };

    // 处理工具权限请求
    const handleToolPermissionRequest = (message) => {
        const { data } = message;
        setPendingPermissions(prev => new Map(prev.set(data.request_id, data)));
        
        // 添加权限请求消息到聊天
        setMessages(prev => [...prev, {
            type: 'tool_permission_request',
            data: data,
            timestamp: new Date()
        }]);
    };

    // 处理工具执行状态
    const handleToolExecutionStatus = (message) => {
        const { data } = message;
        
        // 添加状态消息到聊天
        setMessages(prev => [...prev, {
            type: 'tool_execution_status',
            data: data,
            timestamp: new Date()
        }]);

        // 如果工具执行完成或失败，移除权限请求
        if (['completed', 'failed', 'cancelled'].includes(data.status)) {
            setPendingPermissions(prev => {
                const newMap = new Map(prev);
                newMap.delete(data.request_id);
                return newMap;
            });
        }
    };

    // 响应权限请求
    const respondToPermission = async (requestId, approved, feedback = '') => {
        try {
            const response = await fetch('/api/chat/permission-response', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    request_id: requestId,
                    approved: approved,
                    user_feedback: feedback
                })
            });

            if (!response.ok) {
                throw new Error(`权限响应失败: ${response.status}`);
            }

            // 移除权限请求
            setPendingPermissions(prev => {
                const newMap = new Map(prev);
                newMap.delete(requestId);
                return newMap;
            });

        } catch (error) {
            console.error('权限响应错误:', error);
            setMessages(prev => [...prev, {
                type: 'error',
                content: '权限响应失败，请重试',
                timestamp: new Date()
            }]);
        }
    };

    // 自动滚动到底部
    useEffect(() => {
        if (chatContainerRef.current) {
            chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
        }
    }, [messages]);

    return (
        <div className="unified-chat">
            <div className="chat-container" ref={chatContainerRef}>
                {messages.map((message, index) => (
                    <MessageComponent 
                        key={index} 
                        message={message} 
                        onPermissionResponse={respondToPermission}
                    />
                ))}
                {isLoading && <div className="thinking-indicator">🤔 正在思考...</div>}
            </div>
            
            <div className="chat-input">
                <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && sendMessage(inputValue)}
                    placeholder="输入消息..."
                    disabled={isLoading}
                />
                <button onClick={() => sendMessage(inputValue)} disabled={isLoading}>
                    发送
                </button>
            </div>
        </div>
    );
};

// 消息组件
const MessageComponent = ({ message, onPermissionResponse }) => {
    switch (message.type) {
        case 'user':
            return (
                <div className="message user">
                    <div className="message-content">{message.content}</div>
                </div>
            );
            
        case 'assistant':
            return (
                <div className="message assistant">
                    <div className="message-content">
                        {message.content}
                        {message.isStreaming && <span className="cursor">|</span>}
                    </div>
                </div>
            );
            
        case 'tool_permission_request':
            return (
                <ToolPermissionCard 
                    data={message.data} 
                    onResponse={onPermissionResponse} 
                />
            );
            
        case 'tool_execution_status':
            return <ToolStatusCard data={message.data} />;
            
        case 'error':
            return (
                <div className="message error">
                    <div className="message-content">❌ {message.content}</div>
                </div>
            );
            
        default:
            return null;
    }
};

// 工具权限确认卡片
const ToolPermissionCard = ({ data, onResponse }) => {
    const { request_id, tool_name, tool_description, parameters, risk_level, reasoning } = data;
    
    return (
        <div className="tool-permission-card">
            <div className="card-header">
                <h4>🔒 工具权限确认</h4>
                <span className={`risk-badge risk-${risk_level}`}>{risk_level}</span>
            </div>
            <div className="card-content">
                <p><strong>工具:</strong> {tool_name}</p>
                <p><strong>描述:</strong> {tool_description}</p>
                {reasoning && <p><strong>原因:</strong> {reasoning}</p>}
                <details>
                    <summary>查看参数</summary>
                    <pre>{JSON.stringify(parameters, null, 2)}</pre>
                </details>
            </div>
            <div className="card-actions">
                <button 
                    className="btn-approve"
                    onClick={() => onResponse(request_id, true, '用户同意执行')}
                >
                    ✅ 同意
                </button>
                <button 
                    className="btn-deny"
                    onClick={() => onResponse(request_id, false, '用户拒绝执行')}
                >
                    ❌ 拒绝
                </button>
            </div>
        </div>
    );
};

// 工具状态卡片
const ToolStatusCard = ({ data }) => {
    const { tool_name, status, result, error, progress } = data;
    
    const getStatusIcon = (status) => {
        switch (status) {
            case 'waiting': return '⏳';
            case 'executing': return '🔄';
            case 'completed': return '✅';
            case 'failed': return '❌';
            case 'cancelled': return '🚫';
            default: return '❓';
        }
    };
    
    return (
        <div className="tool-status-card">
            <div className="status-header">
                <span className="status-icon">{getStatusIcon(status)}</span>
                <span className="tool-name">{tool_name}</span>
                <span className="status-text">{status}</span>
            </div>
            {progress !== null && progress !== undefined && (
                <div className="progress-bar">
                    <div className="progress-fill" style={{width: `${progress}%`}}></div>
                </div>
            )}
            {result && (
                <div className="tool-result">
                    <strong>结果:</strong> {result}
                </div>
            )}
            {error && (
                <div className="tool-error">
                    <strong>错误:</strong> {error}
                </div>
            )}
        </div>
    );
};

export default UnifiedChatComponent;
```

## CSS样式示例

```css
.unified-chat {
    display: flex;
    flex-direction: column;
    height: 100vh;
    max-width: 800px;
    margin: 0 auto;
    border: 1px solid #ddd;
    border-radius: 8px;
    overflow: hidden;
}

.chat-container {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    background-color: #f9f9f9;
}

.message {
    margin-bottom: 16px;
    max-width: 80%;
}

.message.user {
    margin-left: auto;
}

.message.user .message-content {
    background-color: #007bff;
    color: white;
    padding: 12px 16px;
    border-radius: 18px 18px 4px 18px;
}

.message.assistant .message-content {
    background-color: white;
    color: #333;
    padding: 12px 16px;
    border-radius: 18px 18px 18px 4px;
    border: 1px solid #e1e5e9;
}

.message.error .message-content {
    background-color: #f8d7da;
    color: #721c24;
    padding: 12px 16px;
    border-radius: 8px;
    border: 1px solid #f5c6cb;
}

/* 工具权限确认卡片 */
.tool-permission-card {
    background: white;
    border: 2px solid #ffc107;
    border-radius: 12px;
    padding: 16px;
    margin: 16px 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.card-header h4 {
    margin: 0;
    color: #856404;
}

.risk-badge {
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: bold;
    text-transform: uppercase;
}

.risk-low {
    background-color: #d4edda;
    color: #155724;
}

.risk-medium {
    background-color: #fff3cd;
    color: #856404;
}

.risk-high {
    background-color: #f8d7da;
    color: #721c24;
}

.card-content {
    margin-bottom: 16px;
}

.card-content details {
    margin-top: 8px;
}

.card-content pre {
    background-color: #f8f9fa;
    padding: 8px;
    border-radius: 4px;
    font-size: 12px;
    overflow-x: auto;
}

.card-actions {
    display: flex;
    gap: 12px;
}

.btn-approve {
    background-color: #28a745;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-weight: bold;
}

.btn-approve:hover {
    background-color: #218838;
}

.btn-deny {
    background-color: #dc3545;
    color: white;
    border: none;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-weight: bold;
}

.btn-deny:hover {
    background-color: #c82333;
}

/* 工具状态卡片 */
.tool-status-card {
    background: white;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
}

.status-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
}

.status-icon {
    font-size: 16px;
}

.tool-name {
    font-weight: bold;
    color: #495057;
}

.status-text {
    font-size: 12px;
    color: #6c757d;
    text-transform: uppercase;
}

.progress-bar {
    width: 100%;
    height: 4px;
    background-color: #e9ecef;
    border-radius: 2px;
    overflow: hidden;
    margin: 8px 0;
}

.progress-fill {
    height: 100%;
    background-color: #007bff;
    transition: width 0.3s ease;
}

.tool-result, .tool-error {
    margin-top: 8px;
    padding: 8px;
    border-radius: 4px;
    font-size: 14px;
}

.tool-result {
    background-color: #d4edda;
    color: #155724;
}

.tool-error {
    background-color: #f8d7da;
    color: #721c24;
}

/* 输入框 */
.chat-input {
    display: flex;
    padding: 16px;
    background-color: white;
    border-top: 1px solid #ddd;
}

.chat-input input {
    flex: 1;
    padding: 12px;
    border: 1px solid #ddd;
    border-radius: 24px;
    outline: none;
    font-size: 14px;
}

.chat-input input:focus {
    border-color: #007bff;
}

.chat-input button {
    margin-left: 12px;
    padding: 12px 24px;
    background-color: #007bff;
    color: white;
    border: none;
    border-radius: 24px;
    cursor: pointer;
    font-weight: bold;
}

.chat-input button:hover:not(:disabled) {
    background-color: #0056b3;
}

.chat-input button:disabled {
    background-color: #6c757d;
    cursor: not-allowed;
}

/* 思考指示器 */
.thinking-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background-color: #f8f9fa;
    border-radius: 18px;
    color: #6c757d;
    font-style: italic;
    margin-bottom: 16px;
}

/* 流式输入光标 */
.cursor {
    animation: blink 1s infinite;
}

@keyframes blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
}
```

## 最佳实践

### 1. 错误处理
```javascript
// 实现重试机制
async function sendMessageWithRetry(message, maxRetries = 3) {
    for (let i = 0; i < maxRetries; i++) {
        try {
            return await chatClient.sendMessage(message);
        } catch (error) {
            if (i === maxRetries - 1) throw error;
            await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
        }
    }
}

// 网络状态检测
window.addEventListener('online', () => {
    console.log('网络已连接');
    // 重新发送失败的消息
});

window.addEventListener('offline', () => {
    console.log('网络已断开');
    // 显示离线提示
});
```

### 2. 性能优化
```javascript
// 消息去重
const messageCache = new Set();

function isDuplicateMessage(message) {
    const key = `${message.type}_${message.timestamp}_${JSON.stringify(message.content || message.data)}`;
    if (messageCache.has(key)) {
        return true;
    }
    messageCache.add(key);
    return false;
}

// 内存管理
function cleanupOldMessages() {
    const maxMessages = 1000;
    if (messages.length > maxMessages) {
        setMessages(prev => prev.slice(-maxMessages));
    }
}
```

### 3. 用户体验
```javascript
// 自动保存草稿
const draftKey = `chat_draft_${sessionId}`;

function saveDraft(content) {
    localStorage.setItem(draftKey, content);
}

function loadDraft() {
    return localStorage.getItem(draftKey) || '';
}

function clearDraft() {
    localStorage.removeItem(draftKey);
}

// 消息状态指示
function showMessageStatus(messageId, status) {
    // sending, sent, delivered, failed
    const statusIcon = document.querySelector(`[data-message-id="${messageId}"] .status-icon`);
    if (statusIcon) {
        statusIcon.className = `status-icon ${status}`;
    }
}
```

## 总结

统一聊天流方案提供了：

### ✅ 完整的解决方案
- **统一接口**：单一HTTP流处理所有交互
- **结构化消息**：清晰的消息类型定义
- **权限管理**：无缝的工具权限确认流程

### 🎯 最佳用户体验
- **实时响应**：流式内容传输
- **直观界面**：权限确认作为对话的自然部分
- **状态反馈**：完整的工具执行状态追踪

### 🔧 开发友好
- **类型安全**：完整的TypeScript支持
- **易于集成**：提供多种前端框架示例
- **扩展性强**：支持自定义消息类型

通过这个统一的方案，前端开发者可以轻松构建功能丰富、用户体验优秀的AI聊天应用。 