# 多 LLM 提供商支持指南

## 概述

现在系统已经支持多个 LLM 提供商，不再仅限于 DeepSeek。你可以根据需要选择和切换不同的提供商。

## 支持的提供商

| 提供商 | 模型 | 多模态 | 中文优化 | 编程优化 |
|--------|------|--------|----------|----------|
| **DeepSeek** | deepseek-chat | ❌ | ✅ | ✅ |
| **OpenAI** | gpt-4o | ✅ | ✅ | ✅ |
| **Claude** | claude-3-5-sonnet | ✅ | ✅ | ✅ |
| **Moonshot** | moonshot-v1-8k | ❌ | ✅ | ✅ |
| **智谱AI** | glm-4 | ✅ | ✅ | ✅ |
| **通义千问** | qwen-max | ❌ | ✅ | ✅ |
| **Gemini** | gemini-pro | ✅ | ✅ | ✅ |

## 配置环境变量

### 1. DeepSeek (原有支持)

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"
```

### 2. OpenAI

```bash
export OPENAI_API_KEY="your-openai-api-key"
```

### 3. Claude (Anthropic)

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

### 4. Moonshot (月之暗面)

```bash
export MOONSHOT_API_KEY="your-moonshot-api-key"
```

### 5. 智谱AI

```bash
export ZHIPU_API_KEY="your-zhipu-api-key"
```

### 6. 通义千问 (阿里云)

```bash
export DASHSCOPE_API_KEY="your-dashscope-api-key"
```

### 7. Gemini (Google)

```bash
export GOOGLE_API_KEY="your-google-api-key"
```

## 安装依赖

更新依赖包以支持多个提供商：

```bash
pip install -r requirements.txt
```

主要新增的依赖：

- `langchain-openai`
- `langchain-anthropic`
- `langchain-google-genai`
- `langchain-community`

## 使用方法

### 1. 代码中使用

#### 创建特定提供商的 Agent

```python
from copilot.core.agent import CoreAgent

# 使用 OpenAI
agent = CoreAgent(provider="openai", model_name="gpt-4o")

# 使用 Claude
agent = CoreAgent(provider="claude", model_name="claude-3-5-sonnet-20241022")

# 使用默认提供商 (配置文件中指定)
agent = CoreAgent()
```

#### 创建特定提供商的 ChatService

```python
from copilot.service.chat_service import ChatService

# 使用智谱AI
chat_service = ChatService(provider="zhipu", model_name="glm-4")

# 使用通义千问
chat_service = ChatService(provider="qwen", model_name="qwen-max")
```

#### 运行时切换提供商

```python
# 切换到另一个提供商
success = agent.switch_provider("openai", "gpt-4o")
if success:
    print("切换成功")
```

### 2. API 使用

#### 获取提供商信息

```bash
curl -X GET "http://localhost:8000/chat/providers"
```

#### 切换提供商

```bash
curl -X POST "http://localhost:8000/chat/providers/switch" \
  -H "Content-Type: application/json" \
  -d '{"provider": "openai", "model": "gpt-4o"}'
```

### 3. 命令行管理工具

运行管理界面：

```bash
python llm_manager_cli.py
```

功能包括：

- 查看提供商状态
- 切换提供商
- 测试连接
- 聊天测试

### 4. 测试脚本

运行完整测试：

```bash
python test_multi_llm.py
```

## 配置文件

在 `config.dev.yaml` 中配置默认提供商和参数：

```yaml
llm:
  default_provider: "deepseek"  # 默认提供商
  providers:
    deepseek:
      model: "deepseek-chat"
      temperature: 0.7
      streaming: true
      api_key_env: "DEEPSEEK_API_KEY"
    
    openai:
      model: "gpt-4o"
      temperature: 0.7
      streaming: true
      api_key_env: "OPENAI_API_KEY"
    
    # ... 其他提供商配置
```

## 推荐使用场景

### 🎯 通用聊天

1. **OpenAI GPT-4** - 综合能力最强
2. **Claude-3.5-Sonnet** - 对话质量高
3. **DeepSeek** - 性价比高

### 🖼️ 多模态 (图片分析)

1. **OpenAI GPT-4V** - 图片理解能力强
2. **Claude-3-Vision** - 图片分析详细
3. **Gemini Pro Vision** - Google 生态

### 💻 编程助手

1. **Claude-3.5-Sonnet** - 代码质量高
2. **DeepSeek** - 中文代码注释
3. **OpenAI GPT-4** - 架构设计

### 🀄 中文对话

1. **DeepSeek** - 中文原生优化
2. **Moonshot** - 中文理解好
3. **智谱AI** - 本土化程度高
4. **通义千问** - 阿里云生态

## 错误处理

系统会自动处理以下情况：

- API 密钥缺失或无效
- 提供商服务不可用
- 自动回退到默认提供商

## 注意事项

1. **API 费用**: 不同提供商的计费方式不同，请注意使用成本
2. **速率限制**: 各提供商都有请求频率限制
3. **模型能力**: 不是所有模型都支持相同功能（如多模态）
4. **网络访问**: 某些提供商可能需要特殊网络配置

## 故障排除

### 1. 提供商不可用

```bash
# 检查 API 密钥是否设置
echo $OPENAI_API_KEY

# 测试提供商连接
python test_multi_llm.py
```

### 2. 依赖包问题

```bash
# 重新安装依赖
pip install -r requirements.txt --upgrade
```

### 3. 配置文件问题

确保 `config.dev.yaml` 中包含所需的提供商配置。

## 开发指南

### 添加新的提供商

1. 在 `llm_factory.py` 中添加新的创建方法
2. 更新 `config.dev.yaml` 配置
3. 在 `requirements.txt` 中添加依赖
4. 更新文档和测试

### 自定义参数

```python
# 传递自定义参数给 LLM
agent = CoreAgent(
    provider="openai",
    model_name="gpt-4",
    temperature=0.9,
    max_tokens=2048,
    top_p=0.9
)
```

## 示例项目

查看 `examples/` 目录中的示例代码，了解如何在实际项目中使用多个 LLM 提供商。
