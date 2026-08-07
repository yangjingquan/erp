from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ERP 管理系统"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8085
    database_url: str = (
        "mysql+pymysql://root:changeme_root@127.0.0.1:3306/erp"
        "?charset=utf8mb4"
    )
    jwt_secret_key: str = "erp-development-secret-key-change-in-production-32"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5176",
            "http://localhost:5176",
        ]
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
