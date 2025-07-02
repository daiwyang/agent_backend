import time
import traceback
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from copilot.mcp_client.mcp_server_manager import mcp_server_manager
from copilot.middleware.auth_middleware import authentication_middleware
from copilot.router import chat_router, mcp_router, user_router, websocket_router, agent_management_router
from copilot.utils.logger import logger
from copilot.utils.mongo_client import get_mongo_manager
from copilot.utils.redis_client import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动事件：初始化MongoDB和Redis连接池
    try:
        mongo_manager = await get_mongo_manager()
        logger.info("MongoDB connection pool initialized successfully")

        await init_redis()
        logger.info("Redis connection pool initialized successfully")

        # 启动MCP管理器
        await mcp_server_manager.start()
        logger.info("MCP server manager started")

        # 启动Agent状态管理器
        from copilot.core.agent_state_manager import agent_state_manager
        await agent_state_manager.start()
        logger.info("Agent state manager started")

        # 启动Agent管理器
        from copilot.core.agent_manager import agent_manager
        await agent_manager.start()
        logger.info("Agent manager started")

        # 初始化聊天服务
        from copilot.router.chat_router import get_chat_service
        await get_chat_service()
        logger.info("Chat service initialized successfully")
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

        # 停止MCP管理器
        await mcp_server_manager.stop()
        logger.info("MCP server manager stopped")

        # 停止Agent状态管理器
        from copilot.core.agent_state_manager import agent_state_manager
        await agent_state_manager.stop()
        logger.info("Agent state manager stopped")

        # 停止Agent管理器
        from copilot.core.agent_manager import agent_manager
        await agent_manager.stop()
        logger.info("Agent manager stopped")
    except Exception as e:
        logger.warning(f"Error closing connections: {str(e)}")


app = FastAPI(lifespan=lifespan)

app.include_router(chat_router.router, prefix="/agent_backend", tags=["agent_backend"])
app.include_router(user_router.router, prefix="/agent_backend", tags=["用户管理"])
app.include_router(mcp_router.router, prefix="/agent_backend", tags=["MCP工具"])
app.include_router(websocket_router.router, prefix="/agent_backend", tags=["WebSocket"])
app.include_router(agent_management_router.router, prefix="/agent_backend", tags=["Agent管理"])

# 添加CORS中间件
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# 添加认证中间件
app.middleware("http")(authentication_middleware)


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

    uvicorn.run(app, host="0.0.0.0", port=8000, timeout_keep_alive=30)
