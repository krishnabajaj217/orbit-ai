# \from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:latest"
    ollama_embedding_model: str = "nomic-embed-text"

    tavily_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


# @lru_cache
def get_settings() -> Settings:
    return Settings()