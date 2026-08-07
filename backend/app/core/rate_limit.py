"""Rate limiting por IP sobre la API (ventana deslizante en memoria).

Mitiga abuso/DoS en endpoints como `/api/repos`, `/search` y `/ask`.
Se aplica a todas las rutas bajo `settings.api_prefix`; `0` lo desactiva.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.core.config import settings

_WINDOW_SECONDS = 60

_state: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def reset_rate_limits() -> None:
    """Limpia el estado (usado en tests y al reiniciar la app)."""
    with _lock:
        _state.clear()


class RateLimitMiddleware:
    """Devuelve 429 cuando una IP supera el límite por minuto."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = settings.request_rate_limit_per_minute
        path = scope.get("path", "")
        if limit <= 0 or not path.startswith(settings.api_prefix):
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        key = client[0] if client else "unknown"
        retry_after = self._check(key, limit)
        if retry_after is not None:
            await self._deny(retry_after, scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _check(self, key: str, limit: int) -> int | None:
        """Registra la petición y devuelve segundos de espera si excede el límite."""
        now = time.monotonic()
        with _lock:
            window = _state[key]
            while window and now - window[0] > _WINDOW_SECONDS:
                window.popleft()
            if len(window) >= limit:
                return max(1, int(_WINDOW_SECONDS - (now - window[0])) + 1)
            window.append(now)
            return None

    @staticmethod
    async def _deny(retry_after: int, scope, receive, send) -> None:
        body = b'{"detail":"Demasiadas peticiones. Intenta en unos segundos."}'
        headers = [
            (b"content-type", b"application/json"),
            (b"retry-after", str(retry_after).encode("latin-1")),
            (b"x-content-type-options", b"nosniff"),
            (b"content-security-policy", b"default-src 'none'"),
        ]
        message = {
            "type": "http.response.start",
            "status": 429,
            "headers": headers,
        }
        await send(message)
        await send({"type": "http.response.body", "body": body})
