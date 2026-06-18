from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CORS_ORIGINS = [
    "https://pro.openbb.co",
    "https://pro.openbb.dev",
    "http://localhost:1420",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "OpenBullet"
    app_version: str = "0.1.0"
    app_host: str = "127.0.0.1"
    app_port: int = 5050
    app_reload: bool = True
    cors_origins_raw: str = Field(
        default=",".join(DEFAULT_CORS_ORIGINS),
        validation_alias="CORS_ORIGINS",
    )
    akshare_a_stock_limit: int = 100
    akshare_a_stock_cache_ttl_seconds: int = 60
    dividend_cache_ttl_seconds: int = 86400

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
