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
- `get_token_calculator()`: 获取计算器实例

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
"""
