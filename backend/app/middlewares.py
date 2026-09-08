import time
import logging
import traceback
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# 配置企业级日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("yuntu_monitor")

class AccessAndExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        client_ip = request.client.host if request.client else "unknown"
        url = request.url.path

        try:
            # 放行请求至具体的路由函数
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000

            # 记录常规访问日志 (如: [INFO] 200 OK - /api/v1/trip/generate - 1420ms)
            logger.info(
                "[%s] %s %s - client=%s request_id=%s duration_ms=%.2f",
                response.status_code, request.method, url, client_ip, request_id, process_time
            )
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception:
            process_time = (time.time() - start_time) * 1000
            # 记录灾难性崩溃日志，保留完整堆栈追踪
            error_trace = traceback.format_exc()
            logger.error(
                "[500] 内部致命异常 - %s %s - client=%s request_id=%s duration_ms=%.2f\n%s",
                request.method, url, client_ip, request_id, process_time, error_trace
            )

            # 注意：此处抛出异常由 FastAPI 全局异常处理器接管
            raise
