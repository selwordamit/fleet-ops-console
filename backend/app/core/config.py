from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Fleet Operations Console"
    environment: str = "development"
    debug: bool = False 
    api_prefix: str = "/api" # Instead of hardcoding "/api" in the route definitions, we can use this setting.

    # asyncpg driver so SQLAlchemy's async engine can use it directly in Phase 02B.2.
    database_url: str = "postgresql+asyncpg://fleetops:fleetops@localhost:5432/fleetops"

    model_config = {"env_file": ".env"}


@lru_cache 
def get_settings() -> Settings:
    # Cached so the .env file is read once, not on every call.
    return Settings()


settings = get_settings()
