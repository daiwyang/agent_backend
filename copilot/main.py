import time
import traceback
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from copilot.utils.logger import logger

app = FastAPI()


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
