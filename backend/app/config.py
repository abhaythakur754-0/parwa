from pydantic_settings import BaseSettings, SettingsConfigDict

class AppConfig(BaseSettings):
    """
    FastAPI-specific application settings.
    Separated from core infrastructure settings for cleaner architecture.
    """
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    title: str = "PARWA API"
    description: str = "PARWA Multi-Tenant Support & AI Automation Backbone"
    version: str = "1.0.0"
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    
    # CORS settings (placeholder for defaults)
    allow_origins: list[str] = ["*"]

app_config = AppConfig()
