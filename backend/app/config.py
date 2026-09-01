from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "凤城云图 (Fengcheng-Yuntu)"
    API_V1_STR: str = "/api/v1"

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

    # ChromaDB 向量库持久化路径
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()