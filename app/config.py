"""应用配置。"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_PATH = Path(__file__).resolve().parents[1]
env_file_path = PROJECT_PATH / ".env"


class Settings(BaseSettings):
    """
    接收 .env 文件中的环境变量。
    """

    app_name: str
    environment: str
    log_level: str
    log_dir: str
    app_host: str
    app_port: int
    document_backend: Literal["memory", "postgres"] = "memory"
    auth_backend: Literal["memory", "postgres"] = "memory"

    database_url: str
    redis_url: str
    celery_broker_url: str
    celery_result_backend: str
    celery_task_max_retries: int
    celery_task_timeout_seconds: int

    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool
    minio_presigned_url_ttl_seconds: int
    local_storage_path: str

    jwt_secret: str
    jwt_issuer: str
    jwt_algorithm: str
    jwt_expire_minutes: int
    auth_revocation_key_prefix: str
    auth_rate_limit_window_seconds: int
    auth_rate_limit_max_attempts: int

    llm_model_provider: str
    llm_model: str
    llm_base_url: str
    llm_api_key: str
    llm_timeout_seconds: int
    llm_temperature: float
    llm_prompt_version: str

    embedding_model_provider: str
    embedding_model: str
    embedding_base_url: str
    embedding_api_key: str
    embedding_timeout_seconds: int

    ocr_provider: str
    ocr_base_url: str
    ocr_api_key: str
    ocr_model: str
    ocr_timeout_seconds: int

    rag_top_k: int
    rag_rule_version: str
    external_model_calls_enabled: bool

    model_config = SettingsConfigDict(
        env_file=env_file_path,
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
