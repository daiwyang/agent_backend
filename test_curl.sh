#!/bin/bash

# 测试流式HTTP输出

echo "1. 创建会话..."
SESSION_RESPONSE=$(curl -s -X POST http://127.0.0.1:8002/agent_backend/chat/sessions \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_user", "window_id": "test_window"}')

echo "会话创建响应: $SESSION_RESPONSE"

# 提取session_id  
SESSION_ID=$(echo $SESSION_RESPONSE | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)
echo "会话ID: $SESSION_ID"

echo ""
echo "2. 发送聊天消息（流式响应）..."
echo "开始接收流式数据:"
echo "---"

curl -X POST http://127.0.0.1:8002/agent_backend/chat/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\", \"message\": \"你好，请介绍一下你自己\"}" \
  --no-buffer \
  -N

echo ""
echo "---"
echo "流式测试完成"
