from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rootsignal"
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: str = ""
    voyage_api_key: str = ""
    encryption_key: str = ""
    base_url: str = "http://localhost:8000"


settings = Settings()
