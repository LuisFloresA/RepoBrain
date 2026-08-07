"""Cliente OpenAI-compatible vía el contrato `/chat/completions`.

Usa solo la stdlib (urllib) para no añadir dependencias de red en runtime.
Cubre OpenAI, DeepSeek, Gemini (endpoint OpenAI-compatible) y Ollama.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .base import LLMClient, LLMError


class OpenAICompatClient(LLMClient):
    """Cliente de chat vía el protocolo OpenAI `/chat/completions`."""

    name = "openai-compatible"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        provider: str = "openai",
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.provider = provider
        self.timeout = timeout

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"

    def complete(self, system: str, user: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        data = self._post_json(url, payload)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Respuesta inesperada del proveedor: {data}") from exc

    def _post_json(self, url: str, payload: dict) -> dict:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise LLMError(f"HTTP {exc.code} de {self.provider}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"Error de red con {self.provider}: {exc.reason}") from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise LLMError(f"Respuesta no JSON de {self.provider}: {exc}") from exc
