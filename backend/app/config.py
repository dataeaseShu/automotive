from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    # 阿里云百炼
    DASHSCOPE_API_KEY: str = ""
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DASHSCOPE_MODEL: str = "qwen-plus"

    # 巨量本地推
    JULIANG_APP_ID: str = ""
    JULIANG_APP_SECRET: str = ""
    JULIANG_API_BASE: str = "https://api.jinritemai.com"

    # 功能开关
    USE_MOCK: bool = True

    # 业务规则常量
    SESSION_TTL: int = 3600
    MAX_PRODUCTS: int = 10
    MAX_CREATIVES: int = 10
    MAX_UPLOADS: int = 10

    # 置信度阈值：低于此值触发追问
    CONFIDENCE_THRESHOLD: float = 0.7

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
