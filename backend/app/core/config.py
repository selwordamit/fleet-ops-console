from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Fleet Operations Console"
    environment: str = "development"
    debug: bool = False 
    api_prefix: str = "/api" 
    database_url: str = "postgresql+asyncpg://fleetops:fleetops@localhost:5432/fleetops"
    redis_url: str = "redis://localhost:6379/0"
    low_battery_threshold: float = 15.0
    model_config = {"env_file": ".env"}


@lru_cache 
def get_settings() -> Settings:
    # Cached so the .env file is read once, not on every call.
    return Settings()

settings = get_settings()
