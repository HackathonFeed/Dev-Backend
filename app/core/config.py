from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "HackathonFeed API"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"

    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"

    jwt_secret_key: str = "change-this-to-a-long-random-secret-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    supabase_url: str | None = None
    supabase_service_key: str | None = None
    supabase_key: str | None = None
    use_supabase_hackathons: bool = True
    prefer_supabase_rest: bool = True  # env: PREFER_SUPABASE_REST

    gemini_api_key: str | None = None
    google_client_id: str | None = None

    # AWS Bedrock
    # Option A — Long-term Bedrock API Key (recommended, created in Bedrock console)
    bedrock_api_key: str | None = None
    # Option B — IAM credentials (fallback if no API key)
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "amazon.nova-micro-v1:0"

    # Razorpay
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None

    # SMTP (Gmail)
    smtp_email: str | None = None
    smtp_password: str | None = None   # Gmail App Password
    smtp_from_name: str = "HackathonFeed"

    @property
    def effective_supabase_key(self) -> str | None:
        return self.supabase_service_key or self.supabase_key

    @property
    def database_configured(self) -> bool:
        placeholders = ("YOUR-DB-PASSWORD", "YOUR-PASSWORD", "your-password")
        return not any(value in self.database_url for value in placeholders)

    @property
    def use_supabase_data_layer(self) -> bool:
        return self.prefer_supabase_rest and bool(self.supabase_url and self.effective_supabase_key)

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
