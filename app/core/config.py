from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "health-events-backend"
    app_env: str = "dev"
    api_prefix: str = "/api/v1"

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/health_events"
    )

    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    jwt_secret_key: str = "dev-placeholder-jwt-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str | None = None

    demo_hospital_user_password: str | None = None
    demo_clinician_user_password: str | None = None
    demo_auditor_user_password: str | None = None

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
