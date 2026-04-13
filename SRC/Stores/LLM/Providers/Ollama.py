import asyncio
from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage

from Stores.LLM.langchain_factory import chat_model_for
from config import get_settings


def _require_system(system: str | None) -> str:
    if not system or not system.strip():
        raise ValueError("System instructions are required for LLM generation.")
    return system.strip()


def _usage_tokens(msg) -> int:
    um = getattr(msg, "usage_metadata", None) or {}
    return int(
        um.get("total_tokens")
        or (um.get("input_tokens", 0) + um.get("output_tokens", 0))
        or 0
    )


class OllamaClient:
    def __init__(self) -> None:
        self._settings = get_settings()

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        m = model or self._settings.embedding_model_id
        from langchain_ollama import OllamaEmbeddings

        emb = OllamaEmbeddings(model=m, base_url=self._settings.ollama_base_url)

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
        chat = chat_model_for(model_id=mid, json_mode=json_mode)
        system_text = _require_system(system)
        messages = []
        messages.append(SystemMessage(content=system_text))
        messages.append(HumanMessage(content=prompt))

        def _run() -> tuple[str, int]:
            out = chat.invoke(messages)
            text = (out.content or "").strip() if hasattr(out, "content") else str(out).strip()
            return text, _usage_tokens(out)

        return await asyncio.to_thread(_run)

    async def generate_stream(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        mid = model or self._settings.generation_model_id
        chat = chat_model_for(model_id=mid, json_mode=False)
        system_text = _require_system(system)
        messages = []
        messages.append(SystemMessage(content=system_text))
        messages.append(HumanMessage(content=prompt))

        def _collect() -> list[str]:
            parts: list[str] = []
            for chunk in chat.stream(messages):
                c = getattr(chunk, "content", None)
                if c:
                    parts.append(c)
            return parts

        parts = await asyncio.to_thread(_collect)
        for p in parts:
            yield p
