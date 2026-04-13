from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from Stores.LLM.Providers.Gemini import GeminiClient
from Stores.LLM.Providers.Ollama import OllamaClient
from Stores.LLM import langchain_factory


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


def test_build_chat_ollama_uses_reasoning_constructor_when_supported(monkeypatch):
    class _FakeChat:
        model_fields = {"reasoning": object()}

        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_settings = type(
        "S",
        (),
        {
            "ollama_base_url": "http://127.0.0.1:11434",
            "llm_request_timeout": 30.0,
            "llm_temperature": 0.3,
            "llm_top_p": 0.9,
            "llm_top_k": 40,
            "llm_max_output_tokens": 256,
            "llm_repeat_penalty": 1.05,
            "ollama_reasoning": False,
        },
    )()

    monkeypatch.setattr(langchain_factory, "get_settings", lambda: fake_settings)
    monkeypatch.setitem(sys.modules, "langchain_ollama", SimpleNamespace(ChatOllama=_FakeChat))

    chat = langchain_factory.build_chat_ollama("qwen3")
    assert isinstance(chat, _FakeChat)
    assert chat.kwargs["reasoning"] is False


def test_build_chat_ollama_falls_back_to_think_bind(monkeypatch):
    class _FakeChat:
        model_fields = {}

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.bound = None

        def bind(self, **kwargs):
            self.bound = kwargs
            return self

    fake_settings = type(
        "S",
        (),
        {
            "ollama_base_url": "http://127.0.0.1:11434",
            "llm_request_timeout": 30.0,
            "llm_temperature": 0.3,
            "llm_top_p": 0.9,
            "llm_top_k": 40,
            "llm_max_output_tokens": 256,
            "llm_repeat_penalty": 1.05,
            "ollama_reasoning": False,
        },
    )()

    monkeypatch.setattr(langchain_factory, "get_settings", lambda: fake_settings)
    monkeypatch.setitem(sys.modules, "langchain_ollama", SimpleNamespace(ChatOllama=_FakeChat))

    chat = langchain_factory.build_chat_ollama("qwen3")
    assert isinstance(chat, _FakeChat)
    assert chat.bound == {"think": False}
