from Stores.LLM.Providers.Gemini import GeminiClient
from Stores.LLM.Providers.Ollama import OllamaClient
from config import get_settings


def get_generation_client():
    s = get_settings()
    if s.generation_backend.upper() == "GEMINI":
        return GeminiClient()
    return OllamaClient()


def get_embedding_client():
    s = get_settings()
    if s.embedding_backend.upper() == "GEMINI":
        return GeminiClient()
    return OllamaClient()
