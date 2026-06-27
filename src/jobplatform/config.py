from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/jobplatform"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production-minimum-32-chars"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 10
    openai_api_key: str = ""


settings = Settings()
