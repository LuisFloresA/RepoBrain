"""Contrato del cliente LLM."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMError(Exception):
    """Error de comunicacion o respuesta invalida de un proveedor LLM."""


class LLMClient(ABC):
    """Contrato minimo de un proveedor LLM (prompt -> texto)."""

    name: str = "llm"

    @abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Devuelve la respuesta del modelo dado el system/user prompt."""
