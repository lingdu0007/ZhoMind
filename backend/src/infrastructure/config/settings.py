from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    app_name: str = "ZhoMind Backend"
    env: str = Field(default="local")
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = Field(default="sqlite+aiosqlite:///./zhomind.db")
    queue_backend: str = "memory"

    milvus_host: str = "127.0.0.1"
    milvus_port: int = 19530

    siliconflow_api_key: str | None = None
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    llm_model: str = "Qwen/Qwen3.5-27B"
    embedding_model: str = "Qwen/Qwen3-Embedding-8B"
    rerank_model: str = "Qwen/Qwen3-Reranker-8B"

    auth_jwt_secret: str = Field(default="dev-secret-change-me")
    auth_jwt_algorithm: str = "HS256"

    @model_validator(mode="after")
    def validate_required_settings(self) -> "Settings":
        if self.env in {"dev", "prod"} and not self.siliconflow_api_key:
            raise ValueError("SILICONFLOW_API_KEY is required when env is dev/prod")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
