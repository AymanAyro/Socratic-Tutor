from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    generation_backend: str = "OLLAMA"  # GEMINI | OLLAMA
    embedding_backend: str = "OLLAMA"
    classifier_model_id: str = "phi3:mini"
    generation_model_id: str = "qwen2.5:7b"
    embedding_model_id: str = "nomic-embed-text"
    ollama_base_url: str = "http://127.0.0.1:11434"
    gemini_api_key: str = ""

    # GCP / Vertex (optional; when set, Gemini uses Vertex instead of API key)
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    google_application_credentials: str = ""

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 15432
    postgres_db: str = "socratic_tutor"
    postgres_user: str = "tutor"
    postgres_password: str = "changeme"

    # Redis
    redis_url: str = "redis://127.0.0.1:6379/0"

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    # Engine
    max_stuck_streak: int = 3
    max_guardrail_retries: int = 2
    repetition_similarity_threshold: float = 0.82
    exam_target_turns: int = 5
    context_max_raw_turns: int = 3
    context_max_tokens: int = 2200
    llm_request_timeout: float = 60.0

    # Prompt versioning
    default_prompt_version: str = "v1.0.0"
    enable_ab_testing: bool = False

    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:24678"

    # Logging / debugging (LOG_LEVEL=DEBUG, SQLALCHEMY_ECHO=true)
    log_level: str = "INFO"
    sqlalchemy_echo: bool = False

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
