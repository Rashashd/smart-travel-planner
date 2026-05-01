from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    # Required — app crashes on startup if missing
    database_url: str
    openai_api_key: str = Field(..., min_length=1)
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

    # LangSmith SDK (newer format — coexists with LANGCHAIN_* vars)
    langsmith_tracing: str | None = None
    langsmith_endpoint: str | None = None
    langsmith_api_key: str | None = None
    langsmith_project: str | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
