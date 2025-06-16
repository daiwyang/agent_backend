# 测试系统说明

## 概述

本项目包含完整的测试套件，用于验证Agent Backend系统的各个功能模块。测试代码位于 `tests/` 目录下，采用模块化设计，便于维护和扩展。

## 测试结构

```
tests/
├── __init__.py                    # 测试模块初始化
├── test_config.py                 # 测试配置和公共工具
├── test_authentication.py         # 认证系统测试
├── test_session_management.py     # 会话管理测试
├── test_chat_functionality.py     # 聊天功能测试
├── test_suite.py                  # 完整测试套件
├── run_tests.sh                   # 测试运行脚本
└── README.md                      # 本文档
```

## 测试模块

### 1. 认证系统测试 (test_authentication.py)

测试用户注册、登录、认证中间件等功能：

- **公开接口测试**: 验证不需要认证的接口
- **保护接口测试**: 验证需要认证的接口
- **用户注册**: 测试用户注册功能
- **用户登录**: 测试JWT token生成和Redis会话创建
- **认证访问**: 使用有效token访问保护接口
- **会话管理**: 测试Redis会话的创建和验证
- **无效认证**: 测试各种无效认证情况

### 2. 会话管理测试 (test_session_management.py)

测试Redis会话管理功能：

- **多设备登录**: 模拟多个设备同时登录
- **会话列表**: 获取用户的所有活跃会话
- **会话撤销**: 撤销指定会话
- **全设备退出**: 退出所有设备登录
- **会话安全**: 验证会话权限和安全性

### 3. 聊天功能测试 (test_chat_functionality.py)

测试聊天相关功能：

- **创建会话**: 创建新的聊天会话
- **会话列表**: 获取聊天会话列表
- **发送消息**: 测试聊天消息发送（流式响应）
- **聊天历史**: 获取聊天历史记录
- **消息搜索**: 搜索聊天记录
- **统计信息**: 获取聊天统计数据
- **删除会话**: 删除聊天会话

## 使用方法

### 1. 安装依赖

```bash
pip install aiohttp
```

### 2. 启动服务器

确保Agent Backend服务器已启动在默认端口：

```bash
cd /data/agent_backend
python copilot/main.py
```

### 3. 运行测试

#### 使用测试脚本（推荐）

```bash
# 运行所有测试
./tests/run_tests.sh

# 只运行认证测试
./tests/run_tests.sh --test auth

# 指定服务器地址
./tests/run_tests.sh --server http://192.168.1.100:8000

# 查看帮助
./tests/run_tests.sh --help
```

#### 直接运行Python

```bash
cd tests

# 运行所有测试
python test_suite.py

# 运行特定测试
python test_suite.py --test auth
python test_suite.py --test session
python test_suite.py --test chat

# 指定服务器地址
python test_suite.py --server http://localhost:8001
```

#### 运行单个测试模块

```bash
cd tests

# 认证测试
python test_authentication.py

# 会话管理测试
python test_session_management.py

# 聊天功能测试
python test_chat_functionality.py
```

## 测试配置

### 配置文件 (test_config.py)

```python
class TestConfig:
    # 服务器配置
    BASE_URL = "http://localhost:8000"
    
    # 测试用户数据
    TEST_USER = {
        "username": "test_user_auth",
        "email": "test_auth@example.com",
        "password": "test_password123",
        "full_name": "认证测试用户"
    }
    
    # 其他配置...
```

### 环境变量

- `TEST_BASE_URL`: 覆盖默认服务器地址
- `TEST_MODULE`: 覆盖默认测试模块

```bash
export TEST_BASE_URL="http://192.168.1.100:8000"
export TEST_MODULE="auth"
./tests/run_tests.sh
```

## 测试输出

### 成功示例

```
🚀 Agent Backend 测试套件
📡 目标服务器: http://localhost:8000
🧪 测试模块: all

=== 测试公开接口 ===
✅ GET /docs: 200
✅ GET /openapi.json: 200
✅ GET /agent_backend/user/health: 200

=== 测试未认证的保护接口 ===
✅ GET /agent_backend/chat/sessions: 401
   响应: 缺少认证信息

=== 测试用户注册 ===
✅ POST /agent_backend/user/register: 200
   注册成功: 注册成功

...

📊 测试结果总结:
====================
auth                 : ✅ 通过
session              : ✅ 通过
chat                 : ✅ 通过
────────────────────
总计: 3/3 测试通过
🎉 所有测试都通过了！
```

### 失败示例

```
❌ POST /agent_backend/user/login: 500
   登录失败: Internal Server Error

⚠️  跳过认证端点测试 - 无有效token

📊 测试结果总结:
====================
auth                 : ❌ 失败
session              : ❌ 失败
chat                 : ❌ 失败
────────────────────
总计: 0/3 测试通过
⚠️  部分测试失败，请检查日志
```

## 故障排除

### 常见问题

1. **连接被拒绝**

   ```
   aiohttp.client_exceptions.ClientConnectorError: Cannot connect to host localhost:8000
   ```

   **解决方案**: 确保服务器已启动并监听正确端口

2. **认证失败**

   ```
   ❌ POST /agent_backend/user/login: 401
   ```

   **解决方案**: 检查用户数据和数据库连接

3. **Redis连接失败**

   ```
   Redis connection failed
   ```

   **解决方案**: 确保Redis服务已启动并配置正确

4. **依赖包缺失**

   ```
   ModuleNotFoundError: No module named 'aiohttp'
   ```

   **解决方案**: 安装所需依赖包

### 调试方法

1. **详细日志**: 检查服务器日志文件
2. **单步测试**: 运行单个测试模块进行调试
3. **网络检查**: 使用curl测试API接口
4. **数据库检查**: 验证MongoDB和Redis连接状态

## 扩展测试

### 添加新测试

1. 在 `tests/` 目录下创建新的测试文件
2. 继承或使用 `test_config.py` 中的配置和工具
3. 在 `test_suite.py` 中注册新的测试模块

### 自定义配置

可以通过修改 `test_config.py` 来自定义测试配置：

- 修改测试用户数据
- 添加新的API路径
- 调整超时时间
- 配置测试环境

## 持续集成

测试脚本支持命令行参数和环境变量，便于集成到CI/CD流程中：

```bash
# GitHub Actions 示例
- name: Run tests
  run: |
    ./tests/run_tests.sh --server http://localhost:8000
  env:
    TEST_BASE_URL: http://localhost:8000
```

## 性能测试

当前测试主要关注功能正确性，如需性能测试，建议：

1. 使用专门的性能测试工具（如 locust）
2. 增加并发测试用例
3. 监控服务器资源使用情况
4. 分析响应时间和吞吐量
