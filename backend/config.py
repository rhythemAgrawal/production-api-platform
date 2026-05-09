from pathlib import Path

from pydantic import Field, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    database_url: str = Field(
        default="postgresql+psycopg://localhost:5432/production_api_platform",
        alias="DATABASE_URL",
    )

    jwt_private_key_path: str = Field(alias="JWT_PRIVATE_KEY_PATH")
    jwt_public_key_path: str = Field(alias="JWT_PUBLIC_KEY_PATH")
    jwt_algorithm: str = Field(default="RS256", alias="JWT_ALGORITHM")
    jwt_access_token_expires_seconds: int = Field(
        default=600,
        alias="JWT_ACCESS_TOKEN_EXPIRES_SECONDS"
    )

    redis_url: str = Field(alias="REDIS_URL")
    redis_port: int = Field(alias="REDIS_PORT")
    token_bucket_script_path: str = Field(alias="TOKEN_BUCKET_SCRIPT_PATH")

    otel_exporter_endpoint: str = Field(alias="OTEL_EXPORTER_OTLP_ENDPOINT")
    app_name: str = Field(alias="APP_NAME")
    environment: str = Field(alias="ENVIRONMENT")

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

class RateLimitConfig(BaseModel):
    capacity: int = 100
    refill_rate: int = 2
    requested: int = 1
    ttl: int = 60

RATE_LIMIT_RULES = {
    "/login": {"capacity": 5, "refill_rate": 1}
}

def get_rate_limit_config(path: str) -> RateLimitConfig:
    rule = RATE_LIMIT_RULES.get(path)
    if rule:
        return RateLimitConfig(**rule)

    return RateLimitConfig()
