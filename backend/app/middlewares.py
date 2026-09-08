import time
import logging
import traceback
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
        client_ip = request.client.host if request.client else "unknown"
        url = request.url.path

        try:
            # 放行请求至具体的路由函数
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000

            # 记录常规访问日志 (如: [INFO] 200 OK - /api/v1/trip/generate - 1420ms)
            logger.info(f"[{response.status_code}] {request.method} {url} - {client_ip} - 耗时: {process_time:.2f}ms")
            return response

        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            # 记录灾难性崩溃日志，保留完整堆栈追踪
            error_trace = traceback.format_exc()
            logger.error(f"[500] 内部致命异常 - {request.method} {url} - 耗时: {process_time:.2f}ms\n{error_trace}")

            # 注意：此处抛出异常由 FastAPI 全局异常处理器接管
            raise e