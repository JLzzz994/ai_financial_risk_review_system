"""应用配置。"""

import os
from functools import lru_cache

from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    """从环境变量读取的应用配置。"""

    app_name: str = "财务单据智能风险审核系统"
    environment: str = "development"
    log_level: str = "INFO"
    log_dir: str = "var/logs"
    database_url: str = "postgresql+asyncpg://app:app@postgres:5432/financial_review"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str = "development-only-change-me"
    jwt_issuer: str = "financial-review"

    model_config = ConfigDict(extra="ignore")

    @classmethod
    def from_environment(cls) -> "Settings":
        """从环境变量读取配置，未设置时使用安全开发默认值。"""
        values = {
            field: os.getenv(field.upper(), default)
            for field, default in {
                "app_name": "财务单据智能风险审核系统",
                "environment": "development",
                "log_level": "INFO",
                "log_dir": "var/logs",
                "database_url": "postgresql+asyncpg://app:app@postgres:5432/financial_review",
                "redis_url": "redis://redis:6379/0",
                "jwt_secret": "development-only-change-me",
                "jwt_issuer": "financial-review",
            }.items()
        }
        return cls(**values)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """构造并缓存全局应用配置。"""
    return Settings.from_environment()
