from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRUSTTRACE_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/trusttrace.db"
    env: str = "development"
    secret_key: str = "dev-only-insecure-key-change-me"


settings = Settings()
