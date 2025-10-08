from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = Field(default="Comment Moderation Service")
    database_url: str = Field(
        default="postgresql+psycopg://moderator:moderator@localhost:5432/comment_moderation",
        env="DATABASE_URL",
    )
    sqlite_fallback_url: str = Field(
        default="sqlite+aiosqlite:///./comment_moderation.db",
        env="SQLITE_FALLBACK_URL",
    )
    allow_sqlite_fallback: bool = Field(default=True, env="ALLOW_SQLITE_FALLBACK")
    generate_demo_data: bool = Field(default=True, env="GENERATE_DEMO_DATA")
    admin_demo_username: str = Field(default="moderator")
    admin_demo_password: str = Field(default="moderator")
    admin_demo_email: str = Field(default="moderator@example.com")
    service_demo_name: str = Field(default="Demo Service")
    service_demo_contact: str = Field(default="demo@example.com")

    @field_validator("database_url")
    def validate_dsn(cls, value: str) -> str:
        allowed_schemes = ("postgresql", "sqlite")
        if not value.startswith(allowed_schemes):
            raise ValueError(
                "DATABASE_URL must use one of the supported drivers: postgresql, sqlite"
            )
        return value


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
