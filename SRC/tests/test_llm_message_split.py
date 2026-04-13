from __future__ import annotations

import asyncio

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from Stores.LLM.Providers.Gemini import GeminiClient
from Stores.LLM.Providers.Ollama import OllamaClient


class _FakeResponse:
    def __init__(self, content: str = "ok") -> None:
        self.content = content
        self.usage_metadata = {"total_tokens": 3}


class _FakeChat:
    def __init__(self) -> None:
        self.last_messages = None

    def invoke(self, messages):
        self.last_messages = messages
        return _FakeResponse()


def test_ollama_generate_uses_system_and_human_roles(monkeypatch):
    fake_chat = _FakeChat()
    monkeypatch.setattr("Stores.LLM.Providers.Ollama.chat_model_for", lambda **kwargs: fake_chat)

    client = OllamaClient()
    text, _ = asyncio.run(client.generate("user payload", system="system rules"))

    assert text == "ok"
    assert isinstance(fake_chat.last_messages[0], SystemMessage)
    assert isinstance(fake_chat.last_messages[1], HumanMessage)
    assert fake_chat.last_messages[0].content == "system rules"
    assert fake_chat.last_messages[1].content == "user payload"


def test_gemini_generate_uses_system_and_human_roles(monkeypatch):
    fake_chat = _FakeChat()
    monkeypatch.setattr("Stores.LLM.Providers.Gemini.build_chat_gemini", lambda *args, **kwargs: fake_chat)

    client = GeminiClient()
    text, _ = asyncio.run(client.generate("runtime context", system="instructions"))

    assert text == "ok"
    assert isinstance(fake_chat.last_messages[0], SystemMessage)
    assert isinstance(fake_chat.last_messages[1], HumanMessage)
    assert fake_chat.last_messages[0].content == "instructions"
    assert fake_chat.last_messages[1].content == "runtime context"


def test_generate_requires_system_instructions():
    client = OllamaClient()
    with pytest.raises(ValueError, match="System instructions are required"):
        asyncio.run(client.generate("user payload", system=""))
