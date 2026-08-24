from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SOC 2 Analyzer API"
    environment: str = "development"
    api_prefix: str = "/api"
    log_level: str = "INFO"
    max_upload_mb: int = 25
    report_ttl_minutes: int = 15
    auth_store_path: str = "/app/auth/credentials.json"
    session_ttl_minutes: int = 480
    use_https: bool = False
    cookie_domain: str | None = None
    frontend_origin: str = "http://localhost:5191"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
