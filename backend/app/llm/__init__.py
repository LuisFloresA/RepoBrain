"""Clientes LLM multi-proveedor para Q&A.

Contrato común: `complete(system, user) -> str`. Los proveedores reales
hablan el protocolo `/chat/completions` (OpenAI, DeepSeek, Gemini vía su
endpoint OpenAI-compatible, Ollama). `MockLLM` cubre el modo demo sin API key.
"""

from .base import LLMClient, LLMError
from .factory import get_llm_client
from .mock import MockLLM
from .openai import OpenAICompatClient

__all__ = [
    "LLMClient",
    "LLMError",
    "MockLLM",
    "OpenAICompatClient",
    "get_llm_client",
]
