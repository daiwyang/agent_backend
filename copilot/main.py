import time
import traceback
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from copilot.router import chat_router, user_router
from copilot.utils.logger import logger
from copilot.utils.mongo_client import get_mongo_manager
from copilot.utils.redis_client import init_redis, close_redis
from copilot.service.user_service import UserService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动事件：初始化MongoDB和Redis连接池
    try:
        mongo_manager = await get_mongo_manager()
        logger.info("MongoDB connection pool initialized successfully")

        await init_redis()
        logger.info("Redis connection pool initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize connection pools: {str(e)}")
        raise

    yield

    # 关闭事件：清理MongoDB和Redis连接
    try:
        mongo_manager = await get_mongo_manager()
        await mongo_manager.close()
        logger.info("MongoDB connections closed")

        await close_redis()
        logger.info("Redis connections closed")
    except Exception as e:
        logger.warning(f"Error closing connections: {str(e)}")


app = FastAPI(lifespan=lifespan)

app.include_router(chat_router.router, prefix="/agent_backend", tags=["agent_backend"])
app.include_router(user_router.router, prefix="/agent_backend", tags=["用户管理"])

# 添加CORS中间件
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# 创建HTTPBearer实例和用户服务实例
security = HTTPBearer(auto_error=False)
user_service = UserService()

# 定义需要认证的路径前缀
PROTECTED_PATHS = [
    "/agent_backend/chat",  # 聊天相关接口需要认证
    "/agent_backend/user/profile",  # 用户信息管理需要认证
    "/agent_backend/user/update",  # 用户信息更新需要认证
    "/agent_backend/user/me",  # 获取当前用户信息需要认证
]

# 定义公开路径（不需要认证）
PUBLIC_PATHS = [
    "/agent_backend/user/register",  # 用户注册
    "/agent_backend/user/login",     # 用户登录
    "/agent_backend/chat/health",    # 健康检查（如果存在）
    "/docs",  # API文档
    "/openapi.json",  # OpenAPI规范
    "/redoc",  # ReDoc文档
    "/",  # 根路径
]


@app.middleware("http")
async def authentication_middleware(request: Request, call_next):
    """用户认证中间件"""
    path = request.url.path
    
    # 检查是否为公开路径
    if any(path.startswith(public_path) for public_path in PUBLIC_PATHS):
        return await call_next(request)
    
    # 检查是否为需要保护的路径
    if any(path.startswith(protected_path) for protected_path in PROTECTED_PATHS):
        # 获取Authorization header
        authorization = request.headers.get("Authorization")
        
        if not authorization:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 401,
                    "message": "缺少认证信息",
                    "detail": "请提供有效的Authorization header"
                }
            )
        
        # 验证Bearer token格式
        if not authorization.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 401,
                    "message": "无效的认证格式",
                    "detail": "Authorization header必须使用Bearer格式"
                }
            )
        
        # 提取token
        token = authorization.split(" ")[1] if len(authorization.split(" ")) == 2 else None
        
        if not token:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 401,
                    "message": "无效的认证信息",
                    "detail": "无法获取有效的token"
                }
            )
        
        try:
            # 验证token
            username = await user_service.verify_token(token)
            if username is None:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "code": 401,
                        "message": "认证失败",
                        "detail": "无效或过期的token"
                    }
                )
            
            # 获取用户信息
            user = await user_service.get_user_by_username(username)
            if user is None:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "code": 401,
                        "message": "用户不存在",
                        "detail": "无法找到对应的用户信息"
                    }
                )
            
            # 检查用户是否被禁用
            if not user.get("is_active", True):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "code": 403,
                        "message": "用户账户已被禁用",
                        "detail": "请联系管理员激活账户"
                    }
                )
            
            # 将用户信息添加到请求状态中，供后续处理使用
            request.state.current_user = user
            
        except Exception as e:
            logger.error(f"认证过程中发生错误: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 401,
                    "message": "认证验证失败",
                    "detail": "无法验证用户身份"
                }
            )
    
    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    idem = uuid.uuid4()
    client_ip = request.client.host if request.client else None
    logger.info(f"RID:{idem} Request PATH:{request.url}", extra={"clientip": client_ip})
    start_time = time.time()
    response: Response = await call_next(request)
    run_time = (time.time() - start_time) * 1000
    process_time = "{0:.2f}".format(run_time)
    logger.info(
        f"RID:{idem} Completed_in:{process_time}ms StatusCode:{response.status_code}",
        extra={"clientip": client_ip},
    )
    return response


@app.exception_handler(Exception)
async def http_exception_handler(request: Request, exc: Exception):
    host = request.client.host if request.client else "unknown"
    logger.error(f"RID:{uuid.uuid4()} Request PATH:{request.url}", extra={"clientip": host})
    logger.error(f"headers:{request.url}")
    logger.error(exc)
    logger.error(traceback.format_exc())
    return JSONResponse(
        {
            "code": 500,
            "message": "Request Validation error",
            "err_detial": str(exc),
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        # 禁用访问日志减少缓冲
        access_log=False,
        # 确保没有响应缓冲
        timeout_keep_alive=30,
    )
