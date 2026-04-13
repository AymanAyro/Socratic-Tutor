from functools import lru_cache

from pydantic import AliasChoices, Field
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
    gemini_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    )

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

    # Stage 2 — LangGraph teaching phases (single-concept arc)
    enable_stage2_graph: bool = False
    langgraph_checkpoint_backend: str = "postgres"  # postgres | memory
    min_probe_turns: int = 5
    max_probe_turns_default: int = 5
    mastery_confidence_threshold: float = 0.85
    reveal_poll_timeout_seconds: float = 10.0
    reveal_poll_interval_seconds: float = 0.5
    report_output_dir: str = "reports"
    report_template_dir: str = "templates/report"
    pdf_generation_timeout_seconds: float = 30.0
    mermaid_render_timeout_seconds: float = 10.0
    mermaid_fallback_on_error: bool = True

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

    @property
    def postgres_checkpoint_conninfo(self) -> str:
        """psycopg connection string for LangGraph PostgresSaver (no +driver suffix)."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
