from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from app.config import settings
from app.database import engine, Base
from app.routes.trip import router as trip_router

# 自动创建 SQLite 数据表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

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