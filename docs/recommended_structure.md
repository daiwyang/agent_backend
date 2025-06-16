# 推荐的项目目录结构

## 当前问题分析

1. **service层和agent层功能重叠** - 服务文件分散在两个目录
2. **config配置分散** - 配置逻辑和配置文件分离
3. **agent目录职责不清** - 混合了业务服务和核心agent功能

## 推荐的目录结构

```
copilot/
├── main.py                    # 应用入口
├── config/                    # 配置管理
│   ├── __init__.py
│   ├── settings.py           # 配置类和逻辑（从utils/config.py移动）
│   ├── config.dev.yaml       # 开发环境配置
│   └── config.work.yaml      # 工作环境配置
├── model/                     # 数据模型层
│   ├── __init__.py
│   ├── user_model.py         # 用户相关模型
│   └── chat_model.py         # 聊天相关模型
├── service/                   # 业务逻辑服务层
│   ├── __init__.py
│   ├── user_service.py       # 用户服务
│   ├── chat_service.py       # 聊天服务（从agent/session_service.py移动）
│   ├── stats_service.py      # 统计服务（从agent/stats_service.py移动）
│   └── history_service.py    # 历史管理服务（从agent/chat_history_manager.py移动）
├── core/                      # 核心智能体功能
│   ├── __init__.py
│   ├── agent.py              # 核心智能体（从agent/core_agent.py移动）
│   └── session_manager.py    # 会话管理（从agent/session_manager.py移动）
├── router/                    # API路由层
│   ├── __init__.py
│   ├── user_router.py        # 用户路由
│   └── chat_router.py        # 聊天路由
├── utils/                     # 工具和帮助函数
│   ├── __init__.py
│   ├── auth.py               # 认证工具
│   ├── logger.py             # 日志工具
│   ├── mongo_client.py       # MongoDB客户端
│   ├── redis_client.py       # Redis客户端
│   └── self_request.py       # 请求工具
└── middleware/                # 中间件（可选）
    ├── __init__.py
    └── cors_middleware.py
```

## 重构建议

### 1. 统一服务层

将以下文件移动到 `service/` 目录：

- `agent/session_service.py` → `service/chat_service.py`
- `agent/stats_service.py` → `service/stats_service.py`
- `agent/chat_history_manager.py` → `service/history_service.py`

### 2. 明确核心功能

创建 `core/` 目录，专门存放核心智能体功能：

- `agent/core_agent.py` → `core/agent.py`
- `agent/session_manager.py` → `core/session_manager.py`

### 3. 统一配置管理

- `utils/config.py` → `config/settings.py`
- 将配置逻辑和配置文件放在同一目录

### 4. 添加包初始化文件

为每个目录添加 `__init__.py` 文件，明确包的导出

## 依赖关系层次

```
router (路由层)
    ↓
service (业务服务层)
    ↓
core (核心功能层)
    ↓
model (数据模型层)
    ↓
utils (工具层)
```

## 重构后的好处

1. **清晰的分层架构** - 每层职责明确
2. **便于维护** - 相同功能的代码集中管理
3. **易于扩展** - 添加新功能时有明确的放置位置
4. **符合最佳实践** - 遵循常见的Python项目结构规范
