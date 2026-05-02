from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# here, all config values are loaded at startup and cached for the app's lifetime

# reads values from .env
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid", #app crashes on startup if a variable is not defined in settings
    )

    # Required: app crashes on startup if missing
    database_url: str
    openai_api_key: SecretStr = Field(...) # prevents key being accidentally printed in logs
    jwt_secret: str
    slack_webhook_url: str

    # Optional with sensible defaults
    jwt_algo: str = "HS256"
    cheap_model: str = "gpt-4o-mini"
    strong_model: str = "gpt-4o"
    classifier_path: str = "/app/ml/classifier.joblib"
    weather_cache_ttl: int = 600
    langchain_tracing_v2: bool = False
    langchain_api_key: str | None = None
    langchain_project: str = "smart-travel-planner"

    # LangSmith SDK (newer format coexists with LANGCHAIN_* vars)
    langsmith_tracing: str | None = None
    langsmith_endpoint: str | None = None
    langsmith_api_key: str | None = None
    langsmith_project: str | None = None


@lru_cache(maxsize=1) # .env file only read once and same settings object is reused everywhere
def get_settings() -> Settings:
    return Settings()
