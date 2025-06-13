import time
import traceback
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from copilot.router import chat_router
from copilot.utils.logger import logger
from copilot.utils.mongo_client import get_mongo_manager
from copilot.utils.redis_client import get_redis_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动事件：初始化MongoDB和Redis连接池
    try:
        mongo_manager = await get_mongo_manager()
        logger.info("MongoDB connection pool initialized successfully")

        redis_manager = get_redis_manager()
        await redis_manager.initialize()
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

        redis_manager = get_redis_manager()
        await redis_manager.close()
        logger.info("Redis connections closed")
    except Exception as e:
        logger.warning(f"Error closing connections: {str(e)}")


app = FastAPI(lifespan=lifespan)

app.include_router(chat_router.router, prefix="/agent_backend", tags=["agent_backend"])

# 添加CORS中间件
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


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

    uvicorn.run(app, host="0.0.0.0", port=8000)
