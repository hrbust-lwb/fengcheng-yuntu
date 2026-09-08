from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.config import settings
from app.database import engine, Base
from app.routes.trip import router as trip_router

# 核心修改：导入企业级监控中间件
from app.middlewares import AccessAndExceptionMiddleware

# 自动创建 SQLite 数据表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# 核心修改：挂载全局访问与异常拦截中间件
# 注意：FastAPI 的中间件是洋葱模型，后 add 的在最外层。
# 我们将其挂载在 CORS 之前，确保跨域请求也能被正确记录耗时。
app.add_middleware(AccessAndExceptionMiddleware)

# 允许跨域请求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载业务路由
app.include_router(trip_router, prefix=settings.API_V1_STR)

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "model": settings.LLM_MODEL_NAME,
        "amap_enrichment": settings.ENABLE_AMAP_ENRICHMENT
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)