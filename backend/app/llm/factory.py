"""Fábrica de clientes LLM según la configuración.

Sin `LLM_API_KEY` configurada se usa siempre `MockLLM` (anti-bloqueo): el
demo de `/ask` funciona sin token, mostrando el pipeline real.
"""

from __future__ import annotations

from app.core.config import settings
from app.llm.base import LLMClient
from app.llm.mock import MockLLM
from app.llm.openai import OpenAICompatClient

# provider -> (base_url por defecto, modelo por defecto)
_PROVIDER_DEFAULTS: dict[str, tuple[str, str]] = {
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat"),
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "gemini-2.0-flash",
    ),
    "ollama": ("http://localhost:11434/v1", "llama3.1"),
}


def get_llm_client() -> LLMClient:
    provider = (settings.llm_provider or "mock").lower()
    if provider == "mock" or not settings.llm_api_key:
        return MockLLM()

    default_url, default_model = _PROVIDER_DEFAULTS.get(
        provider, _PROVIDER_DEFAULTS["openai"]
    )
    return OpenAICompatClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model or default_model,
        base_url=settings.llm_base_url or default_url,
        provider=provider,
        timeout=settings.llm_timeout_seconds,
    )
