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
    # Gemini “thinking” / reasoning tokens (API: https://ai.google.dev/gemini-api/docs/thinking )
    # - 2.5 Flash / Flash-Lite: thinking_budget=0 disables thinking (fastest). -1 = dynamic API behavior.
    # - 2.5 Pro: thinking cannot be fully disabled; avoid 0 or use another model.
    # - Gemini 3+: set gemini_thinking_level (e.g. minimal, low) instead; if set, thinking_budget is not sent.
    gemini_thinking_budget: int | None = Field(
        default=1,
        validation_alias=AliasChoices("GEMINI_THINKING_BUDGET"),
    )
    gemini_thinking_level: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_THINKING_LEVEL"),
    )
    llm_temperature: float = Field(default=0.3, validation_alias=AliasChoices("LLM_TEMPERATURE"))
    llm_top_p: float = Field(default=0.9, validation_alias=AliasChoices("LLM_TOP_P"))
    llm_top_k: int | None = Field(default=40, validation_alias=AliasChoices("LLM_TOP_K"))
    llm_max_output_tokens: int | None = Field(
        default=1024, validation_alias=AliasChoices("LLM_MAX_OUTPUT_TOKENS")
    )
    llm_repeat_penalty: float | None = Field(
        default=1.05, validation_alias=AliasChoices("LLM_REPEAT_PENALTY")
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
    # psycopg checkpoint pool (main.py): TCP keepalives + idle recycle reduce dropped conns (e.g. Win 10053, Docker NAT).
    langgraph_checkpoint_tcp_keepalive: bool = True
    langgraph_checkpoint_keepalives_idle: int = 30
    langgraph_checkpoint_keepalives_interval: int = 10
    langgraph_checkpoint_keepalives_count: int = 3
    # 0 = use psycopg_pool default max_idle (600s). Lower values recycle pooled connections sooner.
    langgraph_checkpoint_pool_max_idle_seconds: float = 180.0
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
