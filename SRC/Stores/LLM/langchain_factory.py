"""
LangChain chat + embedding factories (Ollama / Google GenAI).
Context7 library IDs used: /langchain-ai/langchain-google, /websites/langchain_oss_python_langchain

Optional tracing: set LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY for LangSmith.
"""

from __future__ import annotations

import os

from typing import Any

from config import Settings, get_settings


def _maybe_enable_langsmith() -> None:
    if os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("1", "true", "yes"):
        # LangChain reads LANGCHAIN_API_KEY / LANGCHAIN_PROJECT from env
        return


def get_langchain_embeddings():
    """Shared LangChain Embeddings (used by LlamaIndex LangchainEmbedding and LC adapters)."""
    _maybe_enable_langsmith()
    s = get_settings()
    if s.embedding_backend.upper() == "GEMINI":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        kwargs: dict = {"model": s.embedding_model_id}
        if s.google_cloud_project.strip():
            kwargs["vertexai"] = True
            kwargs["project"] = s.google_cloud_project.strip()
            kwargs["location"] = s.google_cloud_location.strip() or "us-central1"
        elif s.gemini_api_key.strip():
            kwargs["google_api_key"] = s.gemini_api_key.strip()
        return GoogleGenerativeAIEmbeddings(**kwargs)
    from langchain_ollama import OllamaEmbeddings

    return OllamaEmbeddings(model=s.embedding_model_id, base_url=s.ollama_base_url)


def build_chat_ollama(model: str, json_mode: bool = False):
    from langchain_ollama import ChatOllama

    s = get_settings()
    kwargs: dict = {
        "model": model,
        "base_url": s.ollama_base_url,
        "timeout": s.llm_request_timeout,
        "temperature": s.llm_temperature,
        "top_p": s.llm_top_p,
    }
    if s.llm_top_k is not None:
        kwargs["top_k"] = s.llm_top_k
    if s.llm_max_output_tokens is not None:
        kwargs["num_predict"] = s.llm_max_output_tokens
    if s.llm_repeat_penalty is not None:
        kwargs["repeat_penalty"] = s.llm_repeat_penalty
    if json_mode:
        kwargs["format"] = "json"
    reasoning = s.ollama_reasoning
    chat_model_fields = getattr(ChatOllama, "model_fields", {}) or {}
    if reasoning is not None and "reasoning" in chat_model_fields:
        # Newer langchain_ollama versions expose `reasoning` directly on ChatOllama.
        kwargs["reasoning"] = reasoning
        return ChatOllama(**kwargs)

    chat = ChatOllama(**kwargs)
    if reasoning is not None:
        # Older langchain_ollama versions can still forward `think` at request-time.
        return chat.bind(think=reasoning)
    return chat


def _gemini_thinking_kwargs(settings: Settings) -> dict[str, Any]:
    """Map config to LangChain Gemini thinking controls (when supported by the installed SDK)."""
    out: dict[str, Any] = {}
    level = (settings.gemini_thinking_level or "").strip()
    if level:
        out["thinking_level"] = level
        return out
    if settings.gemini_thinking_budget is not None:
        out["thinking_budget"] = settings.gemini_thinking_budget
    return out


def _gemini_api_model_supports_thinking_kw(model: str) -> bool:
    """Gemma on the Gemini API does not accept Gemini 2.5/3 thinking_* fields; sending them yields 400 INVALID_ARGUMENT."""
    base = (model or "").strip().lower()
    if base.startswith("models/"):
        base = base[len("models/") :]
    return not base.startswith("gemma")


def build_chat_gemini(model: str, json_mode: bool = False) -> Any:
    from langchain_google_genai import ChatGoogleGenerativeAI

    s = get_settings()
    kwargs: dict = {
        "model": model,
        "temperature": s.llm_temperature,
        "top_p": s.llm_top_p,
    }
    if s.llm_top_k is not None:
        kwargs["top_k"] = s.llm_top_k
    if s.llm_max_output_tokens is not None:
        kwargs["max_output_tokens"] = s.llm_max_output_tokens
    if s.google_cloud_project.strip():
        kwargs["vertexai"] = True
        kwargs["project"] = s.google_cloud_project.strip()
        kwargs["location"] = s.google_cloud_location.strip() or "us-central1"
    elif s.gemini_api_key.strip():
        kwargs["google_api_key"] = s.gemini_api_key.strip()
    if _gemini_api_model_supports_thinking_kw(model):
        kwargs.update(_gemini_thinking_kwargs(s))
    if json_mode:
        kwargs["model_kwargs"] = {"response_mime_type": "application/json"}
    return ChatGoogleGenerativeAI(**kwargs)


def chat_model_for(settings: Settings | None = None, model_id: str | None = None, json_mode: bool = False):
    s = settings or get_settings()
    mid = model_id or s.generation_model_id
    _maybe_enable_langsmith()
    if s.generation_backend.upper() == "GEMINI":
        return build_chat_gemini(mid, json_mode=json_mode)
    return build_chat_ollama(mid, json_mode=json_mode)


def classifier_structured_model():
    """Chat model for classifier: Ollama uses JSON format; Gemini uses json_schema on invoke."""
    s = get_settings()
    use_json_format = s.generation_backend.upper() != "GEMINI"
    return chat_model_for(model_id=s.classifier_model_id, json_mode=use_json_format)
