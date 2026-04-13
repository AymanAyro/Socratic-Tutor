import asyncio
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from Stores.LLM.langchain_factory import build_chat_gemini, get_langchain_embeddings
from config import get_settings


def _stringify_lc_content(content: Any) -> str:
    """Normalize LangChain message content (str or list of text blocks from Gemini/Gemma)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
                else:
                    inner = block.get("content")
                    if isinstance(inner, str):
                        parts.append(inner)
            else:
                t = getattr(block, "text", None)
                if isinstance(t, str):
                    parts.append(t)
        return "".join(parts).strip()
    return str(content).strip()


def _usage_tokens(msg) -> int:
    um = getattr(msg, "usage_metadata", None) or {}
    return int(
        um.get("total_tokens")
        or (um.get("input_tokens", 0) + um.get("output_tokens", 0))
        or 0
    )


class GeminiClient:
    """Gemini via LangChain (`langchain-google-genai`)."""

    def __init__(self) -> None:
        self._settings = get_settings()

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        emb = get_langchain_embeddings()

        def _run() -> list[list[float]]:
            return emb.embed_documents(texts)

        return await asyncio.to_thread(_run)

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        json_mode: bool = False,
    ) -> tuple[str, int]:
        mid = model or self._settings.generation_model_id
        chat = build_chat_gemini(mid, json_mode=json_mode)
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))

        def _run() -> tuple[str, int]:
            out = chat.invoke(messages)
            raw = getattr(out, "content", out) if hasattr(out, "content") else out
            text = _stringify_lc_content(raw)
            return text, _usage_tokens(out)

        return await asyncio.to_thread(_run)

    async def generate_stream(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        mid = model or self._settings.generation_model_id
        chat = build_chat_gemini(mid, json_mode=False)
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))

        def _collect() -> list[str]:
            parts: list[str] = []
            for chunk in chat.stream(messages):
                c = getattr(chunk, "content", None)
                if c is None:
                    continue
                s = _stringify_lc_content(c)
                if s:
                    parts.append(s)
            return parts

        parts = await asyncio.to_thread(_collect)
        for p in parts:
            yield p
