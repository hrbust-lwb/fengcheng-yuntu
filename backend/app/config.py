from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "凤城云图 (Fengcheng-Yuntu)"
    API_V1_STR: str = "/api/v1"

    # 浏览器跨域白名单，生产环境应替换为实际前端域名
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ]

    # 大语言模型配置 (默认值留空，运行时自动从 .env 读取)
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL_NAME: str = "deepseek-chat"

    # 高德开放平台 Web 服务配置
    AMAP_WEB_KEY: str = ""
    AMAP_TIMEOUT_SECONDS: int = 15
    ENABLE_AMAP_ENRICHMENT: bool = True

    # 存储与缓存配置
    REDIS_URL: str = "redis://localhost:6379/0"
    ENABLE_REDIS_CACHE: bool = False
    DATABASE_URL: str = "sqlite:///./fengcheng.db"

    # FAISS 混合检索配置
    FAISS_INDEX_DIR: str = "./data/faiss_index"
    EMBEDDING_MODEL_NAME: str = "paraphrase-multilingual-MiniLM-L12-v2"
    RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-base"
    ENABLE_RERANKER: bool = True

    # Docker 工具沙箱配置
    ENABLE_DOCKER_SANDBOX: bool = False
    TOOL_SANDBOX_IMAGE: str = "fengcheng-tool-sandbox:latest"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
