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
    }
    if json_mode:
        kwargs["format"] = "json"
    return ChatOllama(**kwargs)


def build_chat_gemini(model: str, json_mode: bool = False) -> Any:
    from langchain_google_genai import ChatGoogleGenerativeAI

    s = get_settings()
    kwargs: dict = {"model": model}
    if s.google_cloud_project.strip():
        kwargs["vertexai"] = True
        kwargs["project"] = s.google_cloud_project.strip()
        kwargs["location"] = s.google_cloud_location.strip() or "us-central1"
    elif s.gemini_api_key.strip():
        kwargs["google_api_key"] = s.gemini_api_key.strip()
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
